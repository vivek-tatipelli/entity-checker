import asyncio
import logging
import re
import json
from collections import Counter
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

MAX_HTML_SIZE = 5_000_000
MIN_VISIBLE_TEXT = 300
REQUEST_TIMEOUT = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
    "Connection": "keep-alive",
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_html(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup


def extract_visible_text(html: str) -> str:
    soup = clean_html(html)
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text


def extract_metadata(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.string.strip() if soup.title else None

    meta_desc = soup.find("meta", attrs={"name": "description"})
    meta_desc = meta_desc.get("content").strip() if meta_desc else None

    json_ld = []

    for script in soup.find_all("script"):
        t = script.get("type", "")
        if "ld+json" in t.lower():
            try:
                if script.string:
                    json_ld.append(json.loads(script.string))
            except Exception:
                continue

    return {
        "title": title,
        "meta_description": meta_desc,
        "json_ld_count": len(json_ld),
        "json_ld": json_ld
    }


def is_js_shell(text: str) -> bool:
    return len(text) < MIN_VISIBLE_TEXT


def fetch_static(url: str) -> str | None:
    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True
        )
        r.raise_for_status()
        return r.text[:MAX_HTML_SIZE]
    except Exception as e:
        logger.warning(f"Static fetch failed: {e}")
        return None

def fetch_dynamic_sync(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        page = browser.new_page()
        page.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9"
        })

        stealth_sync(page)

        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        page.wait_for_selector("body", timeout=15000)
        page.wait_for_timeout(3000)

        html = page.content()
        browser.close()

        return html[:MAX_HTML_SIZE]


def extract_entities(text: str, metadata: dict, url: str) -> dict:
    words = re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", text)
    freq = Counter(words)

    domain = urlparse(url).netloc.replace("www.", "")
    brand_guess = domain.split(".")[0].capitalize()

    entities = {
        "brand": metadata.get("title", "").split("|")[0].strip() if metadata.get("title") else brand_guess,
        "top_named_entities": [w for w, _ in freq.most_common(10)]
    }

    return entities


async def extract_page(url: str) -> dict:
    logger.info(f"Fetching: {url}")

    html = None
    fetch_mode = "static"

    for attempt in range(2):
        html = fetch_static(url)

        if not html:
            continue

        text = extract_visible_text(html)
        metadata = extract_metadata(html)

        has_structured = metadata.get("json_ld_count", 0) > 0
        sufficient_text = len(text) >= MIN_VISIBLE_TEXT
        html_size_ok = len(html) > 150_000

        logger.info(
            f"[STATIC attempt {attempt+1}] "
            f"text={len(text)} "
            f"jsonld={metadata.get('json_ld_count')} "
            f"html_size={len(html)}"
        )

        if sufficient_text and has_structured and html_size_ok:
            logger.info("✅ Static version accepted")
            break
        else:
            logger.info("⚠️ Static rejected → forcing retry/fallback")

        html = None

    if not html:
        fetch_mode = "dynamic"
        logger.info("⚠️ Falling back to dynamic rendering")

        loop = asyncio.get_running_loop()
        html = await loop.run_in_executor(
            None,
            fetch_dynamic_sync,
            url
        )

        text = extract_visible_text(html)
        metadata = extract_metadata(html)

        jsonld_count = metadata.get("json_ld_count", 0)

        logger.info(
            f"[DYNAMIC] text={len(text)} "
            f"jsonld={jsonld_count} "
            f"html_size={len(html)}"
        )

        if jsonld_count == 0:
            logger.warning("⚠️ Page may be bot-protected on cloud IP")

    entities = extract_entities(text, metadata, url)

    return {
        "url": url,
        "fetch_mode": fetch_mode,
        "html": html,
        "text_length": len(text),
        "visible_text": text,
        "metadata": metadata,
        "entities": entities,
    }

