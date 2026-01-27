import json
from pathlib import Path
from typing import Dict, Set, Optional

# --------------------------------------------------
# File path
# --------------------------------------------------

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "data" / "schemaorg.jsonld"

# --------------------------------------------------
# Internal cache (singleton)
# --------------------------------------------------

_SCHEMA_GRAPH: Optional[Dict[str, Set[str]]] = None


# --------------------------------------------------
# Public loader (SAFE)
# --------------------------------------------------

def load_schemaorg_ontology() -> Dict[str, Set[str]]:
    """
    Lazily loads and caches schema.org class hierarchy.

    Returns:
        Dict[parent_type, Set[child_types]]
    """
    global _SCHEMA_GRAPH

    if _SCHEMA_GRAPH is None:
        print("✅ Loading schema.org ontology (once per process)")
        _SCHEMA_GRAPH = _build_schema_graph()

    return _SCHEMA_GRAPH


# --------------------------------------------------
# Internal builder
# --------------------------------------------------

def _build_schema_graph() -> Dict[str, Set[str]]:
    """
    Builds schema.org class hierarchy:
    parent_type -> set(child_types)
    """
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    graph: Dict[str, Set[str]] = {}

    for item in data.get("@graph", []):
        if item.get("@type") != "rdfs:Class":
            continue

        cls = _normalize(item.get("@id"))
        if not cls:
            continue

        parents = item.get("rdfs:subClassOf", [])
        if not isinstance(parents, list):
            parents = [parents]

        for parent in parents:
            parent_cls = _normalize(parent.get("@id"))
            if parent_cls:
                graph.setdefault(parent_cls, set()).add(cls)

    return graph


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def _normalize(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    return (
        value
        .replace("schema:", "")
        .replace("https://schema.org/", "")
        .strip()
    )
