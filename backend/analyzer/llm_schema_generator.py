import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from openai import AsyncOpenAI

from backend.analyzer.schemaorg_loader import load_schemaorg_ontology

load_dotenv()
logger = logging.getLogger(__name__)

_client: Optional[AsyncOpenAI] = None


# --------------------------------------------------
# CLIENT SINGLETON
# --------------------------------------------------

def get_client():
    global _client

    if _client is None:

        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")

        _client = AsyncOpenAI(
            api_key=api_key,
            timeout=40.0   # ⭐ prevents hanging
        )

    return _client


# --------------------------------------------------
# VALIDATE SCHEMA TYPE
# --------------------------------------------------

def is_valid_schema(schema_json: Dict) -> bool:
    """
    Prevent hallucinated schema types.
    """

    schema_graph = load_schemaorg_ontology()

    schema_type = schema_json.get("@type")

    if not schema_type:
        return False

    # flatten ontology
    all_types = set(schema_graph.keys())
    for children in schema_graph.values():
        all_types.update(children)

    return schema_type in all_types


# --------------------------------------------------
# GENERATOR
# --------------------------------------------------

async def generate_schema_ai(
    schema_name: str,
    entities: Dict[str, Any],
    signals: Dict[str, Any],
    url: Optional[str]
) -> Dict:

    client = get_client()

    prompt = f"""
You are a world-class technical SEO engineer.

Generate a VALID schema.org JSON-LD.

TARGET SCHEMA:
{schema_name}

PAGE URL:
{url}

DETECTED ENTITIES:
{json.dumps(entities)[:3500]}

SEO SIGNALS:
{json.dumps(signals)[:1500]}

RULES:

- Return VALID JSON-LD ONLY
- Include "@context": "https://schema.org"
- Use ONLY official schema.org types
- Do NOT invent properties
- Omit unknown fields
- No markdown
- No explanations
- No comments
"""

    for attempt in range(2):

        try:

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": "Return ONLY JSON."},
                    {"role": "user", "content": prompt}
                ]
            )

            text = response.choices[0].message.content.strip()

            schema_json = json.loads(text)

            # ⭐ ontology validation
            if not is_valid_schema(schema_json):

                logger.warning(
                    f"Invalid schema type generated: {schema_json.get('@type')}"
                )

                raise ValueError("Hallucinated schema")

            return schema_json


        except Exception as e:

            logger.warning(f"Schema generation failed (attempt {attempt+1})")
            logger.warning(str(e))

            if attempt == 1:
                logger.error("LLM RAW OUTPUT:")
                logger.error(text if 'text' in locals() else "No output")

                return {
                    "error": "Schema generation failed",
                    "schema_requested": schema_name
                }

            await asyncio.sleep(1)  # small retry delay
