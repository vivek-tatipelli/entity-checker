from typing import Dict, List, Any, Optional
from pydantic import BaseModel

class EntityGroup(BaseModel):
    type: str
    count: int
    items: List[Dict[str, Any]]

class SignalsModel(BaseModel):
    meta: Dict[str, Any]
    content: Dict[str, Any]
    media: Dict[str, Any]
    structured_data_hints: Dict[str, Any]


class AnalyzeResponse(BaseModel):
    url: Optional[str]
    total_entities: int
    entities: Dict[str, EntityGroup]
    signals: SignalsModel
