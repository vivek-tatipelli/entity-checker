from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from fastapi.concurrency import run_in_threadpool
from backend.services.fetcher import fetch_html
from backend.analyzer.orchestor import analyze_html

router = APIRouter()


@router.post("/analyze")
async def analyze(payload: Dict[str, Any]):
    """
    Analyze a single page (URL or raw HTML).
    """

    try:
        if "html" in payload:
            html = payload["html"]
            url = None

        elif "url" in payload:
            url = payload["url"]
            html = fetch_html(url)

        else:
            raise HTTPException(
                status_code=400,
                detail="Provide either 'url' or 'html'"
            )

        return await run_in_threadpool(analyze_html, html, url)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

