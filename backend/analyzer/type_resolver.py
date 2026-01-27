from backend.analyzer.schemaorg_loader import load_schemaorg_ontology

def resolve_types(schema_type: str) -> set[str]:
    SCHEMA_GRAPH = load_schemaorg_ontology()
    resolved = {schema_type}
    resolved |= SCHEMA_GRAPH.get(schema_type, set())
    return resolved

def is_subclass(schema_type: str, parent: str) -> bool:
    return parent in resolve_types(schema_type)
