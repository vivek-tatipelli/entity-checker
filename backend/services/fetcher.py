import asyncio
import logging
import re
import json
from collections import Counter
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

MAX_HTML_SIZE = 5_000_000
MIN_VISIBLE_TEXT = 300
REQUEST_TIMEOUT = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
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
    for script in soup.find_all("script", type="application/ld+json"):
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
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.text[:MAX_HTML_SIZE]
    except Exception as e:
        logger.warning(f"Static fetch failed: {e}")
        return None


def fetch_dynamic_sync(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)
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

    html = fetch_static(url)
    fetch_mode = "static"

    if html:
        text = extract_visible_text(html)
        if not is_js_shell(text):
            metadata = extract_metadata(html)
        else:
            html = None

    if not html:
        fetch_mode = "dynamic"
        loop = asyncio.get_running_loop()
        html = await loop.run_in_executor(
            None,
            fetch_dynamic_sync,
            url
        )
        text = extract_visible_text(html)
        metadata = extract_metadata(html)

    entities = extract_entities(text, metadata, url)

    return {
        "url": url,
        "fetch_mode": fetch_mode,
        "html" : html,
        "text_length": len(text),
        "visible_text": text,
        "metadata": metadata,
        "entities": entities,
    }

