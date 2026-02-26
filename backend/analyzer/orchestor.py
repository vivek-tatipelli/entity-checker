import logging
import asyncio
from typing import Dict, Any, Optional, List

from backend.analyzer.entity_merger import merge_entities
from backend.models.entity import NormalizedEntity
from backend.utils.html import make_soup
from backend.extractors.jsonld_extractor import JSONLDExtractor
from backend.extractors.microdata_extractor import MicrodataExtractor
from backend.extractors.rdfa_extractor import RDFaExtractor
from backend.signals.seo_metrics import SEOMetricsAnalyzer
from backend.analyzer.organization import resolve_organization
from backend.analyzer.suggestion_engine import SuggestionEngine
from backend.analyzer.type_resolver import resolve_types
from backend.analyzer.confidence import enrich_confidence
from backend.analyzer.llm_recommender import (
    infer_page_intent,
    merge_llm_suggestions
)

logger = logging.getLogger(__name__)

# --------------------------------------------------
# SINGLETONS
# --------------------------------------------------

SUGGESTION_ENGINE = SuggestionEngine(
    rules_path="backend/analyzer/suggestion_rules.yaml"
)

SEO_ANALYZER = SEOMetricsAnalyzer()


# --------------------------------------------------
# SAFE ASYNC RUNNER
# --------------------------------------------------

def run_async_safely(coro):

    try:
        loop = asyncio.get_running_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()

    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


# --------------------------------------------------
# NORMALIZATION
# --------------------------------------------------

def _normalize_entities(
    entities: List[Dict[str, Any]],
    source: str,
    base_confidence: float
) -> List[NormalizedEntity]:

    normalized: List[NormalizedEntity] = []

    for e in entities or []:  # ✅ Never iterate None
        try:
            normalized.append(
                NormalizedEntity(
                    type=str(e.get("@type", "Thing")),
                    properties=e.get("properties") or e,
                    source=source,
                    confidence=base_confidence,
                    raw=e
                )
            )
        except Exception:
            logger.exception("Failed to normalize entity")

    return normalized


# --------------------------------------------------
# ORCHESTRATOR
# --------------------------------------------------

def analyze_html(html: str, url: Optional[str] = None) -> Dict[str, Any]:
    """
    Resilient production pipeline.
    """

    try:

        if not html or len(html) < 500:
            logger.warning("⚠️ Empty or shell HTML received.")
        else:
            logger.info(f"HTML length: {len(html)}")

        soup = make_soup(html)

        # --------------------------------------------------
        # EXTRACTION (ISOLATED)
        # --------------------------------------------------

        try:
            jsonld_entities = JSONLDExtractor.extract_json_ld(soup) or []
        except Exception:
            logger.exception("JSON-LD extractor failed")
            jsonld_entities = []

        try:
            microdata_entities = MicrodataExtractor.extract_microdata(soup) or []
        except Exception:
            logger.exception("Microdata extractor failed")
            microdata_entities = []

        try:
            rdfa_entities = RDFaExtractor.extract_rdfa(soup) or []
        except Exception:
            logger.exception("RDFa extractor failed")
            rdfa_entities = []

        logger.info("=========== EXTRACTION DEBUG ===========")
        logger.info(f"JSON-LD: {len(jsonld_entities)}")
        logger.info(f"Microdata: {len(microdata_entities)}")
        logger.info(f"RDFa: {len(rdfa_entities)}")
        logger.info("=======================================")

        # --------------------------------------------------
        # NORMALIZATION
        # --------------------------------------------------

        entities: List[NormalizedEntity] = []

        entities += _normalize_entities(jsonld_entities, "jsonld", 0.9)
        entities += _normalize_entities(microdata_entities, "microdata", 0.7)
        entities += _normalize_entities(rdfa_entities, "rdfa", 0.6)

        # --------------------------------------------------
        # TYPE RESOLUTION
        # --------------------------------------------------

        for entity in entities:
            try:
                entity.resolved_types = resolve_types(entity.type) or []
            except Exception:
                logger.exception("Type resolver failed")
                entity.resolved_types = []

        # --------------------------------------------------
        # MERGE
        # --------------------------------------------------

        try:
            entities = merge_entities(entities) or []
        except Exception:
            logger.exception("Entity merge failed")
            entities = []

        # --------------------------------------------------
        # CONFIDENCE
        # --------------------------------------------------

        for entity in entities:
            try:
                enrich_confidence(entity)
            except Exception:
                logger.exception("Confidence enrichment failed")

        logger.info(f"✅ Final merged entities: {len(entities)}")

        # --------------------------------------------------
        # ORGANIZATION
        # --------------------------------------------------

        try:
            organization = resolve_organization(
                entities=entities,
                page_url=url
            ) or {}
        except Exception:
            logger.exception("Organization resolver failed")
            organization = {}

        # --------------------------------------------------
        # SEO SIGNALS
        # --------------------------------------------------

        try:
            signals = SEO_ANALYZER.analyze(html, soup) or {}
        except Exception:
            logger.exception("SEO analyzer failed")
            signals = {}

        # --------------------------------------------------
        # SUGGESTIONS
        # --------------------------------------------------

        try:
            suggestions = SUGGESTION_ENGINE.generate(
                entities=entities,
                signals=signals
            ) or {}
        except Exception:
            logger.exception("Suggestion engine failed")
            suggestions = {}

        # --------------------------------------------------
        # ENTITY SUMMARY
        # --------------------------------------------------

        entity_summary: Dict[str, Dict[str, Any]] = {}

        for e in entities:
            primary_type = e.type or "Thing"

            entity_summary.setdefault(
                primary_type,
                {
                    "count": 0,
                    "items": []
                }
            )

            entity_summary[primary_type]["count"] += 1
            entity_summary[primary_type]["items"].append({
                "@type": e.type,
                "properties": e.properties,
                "source": e.source,
                "confidence": e.confidence
            })

        entity_summary = entity_summary or {}

        # --------------------------------------------------
        # LLM FALLBACK
        # --------------------------------------------------

        llm_output = None

        if url and not entity_summary:
            try:
                logger.info("🧠 Running LLM intent inference...")

                llm_output = run_async_safely(
                    infer_page_intent(
                        url=url,
                        entities=entity_summary,
                        signals=signals
                    )
                )

            except Exception:
                logger.exception("LLM inference failed")

        # --------------------------------------------------
        # MERGE LLM
        # --------------------------------------------------

        try:
            suggestions = merge_llm_suggestions(
                suggestions,
                llm_output
            ) or {}
        except Exception:
            logger.exception("LLM merge failed")
            suggestions = suggestions or {}

        # --------------------------------------------------
        # FINAL CONTRACT CHECK
        # --------------------------------------------------

        assert isinstance(entity_summary, dict)
        assert isinstance(signals, dict)
        assert isinstance(suggestions, dict)
        assert isinstance(organization, dict)

        return {
            "url": url,
            "total_entities": len(entities),
            "entities": entity_summary,
            "organization": organization,
            "signals": signals,
            "suggestions": suggestions
        }

    except Exception as e:

        logger.exception("🔥 ORCHESTRATOR HARD FAILURE")

        # NEVER crash API — return structured error
        return {
            "url": url,
            "error": str(e),
            "total_entities": 0,
            "entities": {},
            "organization": {},
            "signals": {},
            "suggestions": {}
        }
