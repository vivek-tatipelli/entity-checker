from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from backend.analyzer.llm_schema_generator import generate_schema_ai

router = APIRouter()


@router.post("/generate-schema")
async def generate_schema(payload: Dict[str, Any]):

    try:
        schema = payload.get("schema")
        entities = payload.get("entities")
        signals = payload.get("signals")
        url = payload.get("url")

        if not schema:
            raise HTTPException(400, "Schema required")

        result = await generate_schema_ai(
            schema,
            entities,
            signals,
            url
        )

        return result

    except Exception as e:
        raise HTTPException(500, str(e))
