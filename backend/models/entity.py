from dataclasses import dataclass, field
from typing import Dict, Any, Set

@dataclass
class NormalizedEntity:
    type: str
    properties: Dict[str, Any]
    source: str                    # jsonld | microdata | rdfa
    confidence: float
    raw: Dict[str, Any]

    resolved_types: Set[str] = field(default_factory=set)
