from typing import Optional, List, Dict, Any
from backend.models.entity import NormalizedEntity
from backend.analyzer.type_resolver import is_subclass

def score_org(entity, page_domain=None):
    score = 0

    props = entity.properties

    if "name" in props:
        score += 2
    if "url" in props:
        score += 2
    if "logo" in props:
        score += 1
    if "sameAs" in props:
        score += 1

    score += entity.confidence
    return score


def resolve_organization(
    entities: List[NormalizedEntity],
    page_url: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Resolve the best Organization entity from extracted entities.
    """

    # Find all organization-like entities using ontology
    candidates = [
        e for e in entities
        if is_subclass(e.type, "Organization")
    ]

    if not candidates:
        return None

    # Pick the highest-confidence organization
    best = max(candidates, key=lambda e: e.confidence)

    return {
        "@type": best.type,
        "properties": best.properties,
        "confidence": best.confidence,
        "source": best.source
    }

