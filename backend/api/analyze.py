from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from fastapi.concurrency import run_in_threadpool
import asyncio

from backend.analyzer.orchestor import analyze_html
from backend.services.fetcher import extract_page

router = APIRouter()

MAX_URLS = 5
MAX_HTMLS = 5


# --------------------------------------------------
# URL PROCESSOR (PARALLEL SAFE)
# --------------------------------------------------

async def process_url(url: str):

    try:
        page = await extract_page(url)
        html = page["html"]

        result = await run_in_threadpool(
            analyze_html,
            html,
            url
        )

        result["fetch_mode"] = page.get("fetch_mode")

        return url, result

    except Exception as e:
        return url, {"error": str(e)}


# --------------------------------------------------
# HTML PROCESSOR
# --------------------------------------------------

async def process_html(i: int, html: str):

    try:
        result = await run_in_threadpool(
            analyze_html,
            html,
            None
        )

        return f"html_{i}", result

    except Exception as e:
        return f"html_{i}", {"error": str(e)}


# --------------------------------------------------
# ANALYZE ENDPOINT
# --------------------------------------------------

@router.post("/analyze")
async def analyze(payload: Dict[str, Any]):

    try:

        # ---------------- MULTIPLE URLS ----------------

        if "urls" in payload:

            urls = payload["urls"]

            if not isinstance(urls, list) or not urls:
                raise HTTPException(400, "'urls' must be a non-empty list")

            if len(urls) > MAX_URLS:
                raise HTTPException(
                    400, f"Maximum {MAX_URLS} URLs allowed"
                )

            tasks = [process_url(url) for url in urls]

            results_list = await asyncio.gather(*tasks)

            return {
                "total": len(results_list),
                "results": dict(results_list)
            }

        # ---------------- SINGLE URL ----------------

        if "url" in payload:

            url = payload["url"]

            key, value = await process_url(url)

            return {
                "total": 1,
                "results": {key: value}
            }

        # ---------------- MULTIPLE HTML ----------------

        if "htmls" in payload:

            htmls = payload["htmls"]

            if not isinstance(htmls, list) or not htmls:
                raise HTTPException(400, "'htmls' must be a non-empty list")

            if len(htmls) > MAX_HTMLS:
                raise HTTPException(
                    400, f"Maximum {MAX_HTMLS} HTMLs allowed"
                )

            tasks = [
                process_html(i, html)
                for i, html in enumerate(htmls, start=1)
            ]

            results_list = await asyncio.gather(*tasks)

            return {
                "total": len(results_list),
                "results": dict(results_list)
            }

        # ---------------- SINGLE HTML ----------------

        if "html" in payload:

            key, value = await process_html(1, payload["html"])

            return {
                "total": 1,
                "results": {key: value}
            }

        raise HTTPException(
            400,
            "Provide 'url', 'urls', 'html', or 'htmls'"
        )

    except HTTPException:
        raise

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, str(e))
