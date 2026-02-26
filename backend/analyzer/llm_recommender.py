import logging
import json
import os
from typing import Dict, List, Optional, Set
from dotenv import load_dotenv
from openai import AsyncOpenAI

from backend.analyzer.schemaorg_loader import load_schemaorg_ontology
from backend.analyzer.type_resolver import is_subclass

load_dotenv()

logger = logging.getLogger(__name__)

_client: Optional[AsyncOpenAI] = None
_SCHEMA_TYPES: Optional[Set[str]] = None


# --------------------------------------------------
# CONSTANT — STABLE RETURN SHAPE
# --------------------------------------------------

EMPTY_LLM_RESPONSE: Dict[str, List[str]] = {
    "strong": [],
    "recommended": [],
    "optional": []
}


# --------------------------------------------------
# CLIENT (Singleton)
# --------------------------------------------------

def _get_client() -> AsyncOpenAI:
    global _client

    if _client is None:

        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")

        _client = AsyncOpenAI(api_key=api_key)

    return _client


# --------------------------------------------------
# LOAD SCHEMA TYPES (Cached)
# --------------------------------------------------

def _get_all_schema_types() -> Set[str]:

    global _SCHEMA_TYPES

    if _SCHEMA_TYPES is None:

        graph = load_schemaorg_ontology()

        all_types = set(graph.keys())

        for children in graph.values():
            all_types.update(children)

        _SCHEMA_TYPES = all_types

        logger.info(f"✅ Loaded {len(_SCHEMA_TYPES)} schema.org types")

    return _SCHEMA_TYPES


# --------------------------------------------------
# LLM CALL
# --------------------------------------------------

async def _call_llm(prompt: str) -> str:

    client = _get_client()

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a world-class technical SEO and schema.org expert.\n"
                    "You ONLY recommend valid schema.org types.\n"
                    "You NEVER invent schema types.\n"
                    "You return STRICT JSON only."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        timeout=30
    )

    content = response.choices[0].message.content

    return content.strip() if content else "{}"


# --------------------------------------------------
# PROMPT
# --------------------------------------------------

def _build_prompt(
    url: str,
    entities: Dict,
    signals: Dict
) -> str:

    entities_str = json.dumps(entities)[:3500]
    signals_str = json.dumps(signals)[:3500]

    return f"""
URL:
{url}

Detected Entities:
{entities_str}

SEO Signals:
{signals_str}

TASK:
Infer the TRUE search intent of this page and recommend ONLY schema.org types that are NOT already present.

STRICT RULES:
- Use ONLY official schema.org type names
- Do NOT invent schemas
- Do NOT repeat detected entities
- Prefer high-confidence schemas
- Be conservative
- Return STRICT JSON

FORMAT:
{{
  "strong": [],
  "recommended": [],
  "optional": []
}}
"""


# --------------------------------------------------
# NORMALIZATION
# --------------------------------------------------

def _normalize_schema_name(name: str) -> str:

    name = name.strip()

    if not name:
        return name

    return name[0].upper() + name[1:]


def _filter_valid_schemas(
    schemas: List[str],
    existing_types: Set[str]
) -> List[str]:

    valid_types = _get_all_schema_types()

    cleaned = []

    for schema in schemas:

        schema = _normalize_schema_name(schema)

        if schema not in valid_types:
            continue

        if schema in existing_types:
            continue

        if any(
            is_subclass(schema, existing)
            or is_subclass(existing, schema)
            for existing in existing_types
        ):
            continue

        cleaned.append(schema)

    return cleaned


# --------------------------------------------------
# PUBLIC API — NEVER RETURNS NONE
# --------------------------------------------------

async def infer_page_intent(
    url: str,
    entities: Dict,
    signals: Dict
) -> Dict[str, List[str]]:
    """
    Always returns a stable schema dict.
    Never returns None.
    """

    prompt = _build_prompt(url, entities or {}, signals or {})

    try:

        logger.info("🧠 Running LLM semantic intent analysis...")

        response_text = await _call_llm(prompt)

        logger.info("====== RAW LLM RESPONSE ======")
        logger.info(response_text)

        parsed = json.loads(response_text or "{}")

        if not isinstance(parsed, dict):
            return EMPTY_LLM_RESPONSE

        # Ensure structure
        for key in ("strong", "recommended", "optional"):
            parsed.setdefault(key, [])

        existing_types = set((entities or {}).keys())

        cleaned: Dict[str, List[str]] = {}

        for level, schemas in parsed.items():

            if not isinstance(schemas, list):
                schemas = []

            cleaned[level] = _filter_valid_schemas(
                schemas,
                existing_types
            )

        logger.info("====== CLEANED LLM SUGGESTIONS ======")
        logger.info(json.dumps(cleaned, indent=2))

        return cleaned or EMPTY_LLM_RESPONSE

    except json.JSONDecodeError:
        logger.warning("LLM returned INVALID JSON")
        return EMPTY_LLM_RESPONSE

    except Exception as e:
        logger.warning(f"LLM inference failed for {url}: {e}")
        return EMPTY_LLM_RESPONSE


# --------------------------------------------------
# MERGE HELPER — PRODUCTION SAFE
# --------------------------------------------------

LEVEL_MAP = {
    "strong": "high",
    "recommended": "medium",
    "optional": "low"
}


def merge_llm_suggestions(
    rule_suggestions: Optional[Dict],
    llm_output: Optional[Dict]
) -> Dict:
    """
    NEVER crashes.
    NEVER returns None.
    """

    rule_suggestions = rule_suggestions or {}

    # 🔥 Critical guard
    if not llm_output or not isinstance(llm_output, dict):
        return rule_suggestions

    if not any(llm_output.values()):
        logger.info("LLM returned no additional schemas.")
        return rule_suggestions

    rule_suggestions.setdefault("LLM Intent", [])

    for level, schemas in llm_output.items():

        confidence = LEVEL_MAP.get(level, "low")

        for schema in schemas:

            rule_suggestions["LLM Intent"].append({
                "schema": schema,
                "confidence": confidence,
                "category": "Semantic",
                "reason": "Recommended via LLM intent analysis",
                "schema_url": f"https://schema.org/{schema}"
            })

    logger.info("✅ LLM suggestions merged successfully")

    return rule_suggestions
