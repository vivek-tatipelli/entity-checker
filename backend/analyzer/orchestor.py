import logging
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

logger = logging.getLogger(__name__)


# --------------------------------------------------
# Normalization
# --------------------------------------------------

def _normalize_entities(
    entities: List[Dict[str, Any]],
    source: str,
    base_confidence: float
) -> List[NormalizedEntity]:
    normalized: List[NormalizedEntity] = []

    for e in entities:
        normalized.append(
            NormalizedEntity(
                type=str(e.get("@type", "Thing")),
                properties=e.get("properties") or e,
                source=source,
                confidence=base_confidence,
                raw=e
            )
        )

    return normalized


# --------------------------------------------------
# Orchestrator
# --------------------------------------------------

def analyze_html(html: str, url: Optional[str] = None) -> Dict[str, Any]:
    """
    Main orchestration pipeline for single-page analysis.
    """

    # ---------------- HTML ----------------
    soup = make_soup(html)

    # ---------------- Extraction ----------------
    jsonld_entities = JSONLDExtractor.extract_json_ld(soup)
    microdata_entities = MicrodataExtractor.extract_microdata(soup)
    rdfa_entities = RDFaExtractor.extract_rdfa(soup)

    # ---------------- Normalization ----------------
    entities: List[NormalizedEntity] = []

    entities += _normalize_entities(jsonld_entities, "jsonld", 0.9)
    entities += _normalize_entities(microdata_entities, "microdata", 0.7)
    entities += _normalize_entities(rdfa_entities, "rdfa", 0.6)

    # ---------------- Ontology Type Resolution ----------------
    for entity in entities:
        entity.resolved_types = resolve_types(entity.type)

    entities = merge_entities(entities)
    
    # ---------------- Confidence Enrichment (INTELLIGENCE STEP) ----------------
    for entity in entities:
        enrich_confidence(entity)

    # ---------------- Organization Resolution ----------------
    organization = resolve_organization(
        entities=entities,
        page_url=url
    )

    # ---------------- SEO Signals ----------------
    signals = SEOMetricsAnalyzer().analyze(html, soup)

    # ---------------- Suggestions ----------------
    suggestion_engine = SuggestionEngine(
        rules_path="backend/analyzer/suggestion_rules.yaml"
    )

    suggestions = suggestion_engine.generate(
        entities=entities,
        signals=signals
    )

    # ---------------- Entity Summary (API-safe, READ-ONLY) ----------------
    entity_summary: Dict[str, Dict[str, Any]] = {}

    for e in entities:
        primary_type = e.type

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

    # ---------------- Final Response ----------------
    return {
        "url": url,
        "total_entities": len(entities),
        "entities": entity_summary,
        "organization": organization,
        "signals": signals,
        "suggestions": suggestions
    }
