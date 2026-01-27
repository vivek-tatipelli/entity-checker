import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

MAX_HTML_SIZE = 5_000_000  


def validate_html(html: str) -> str:
    """
    Phase-1 HTML validator
    - Ensures html is usable
    - Prevents memory abuse
    """
    if not html or not isinstance(html, str):
        raise ValueError("Invalid HTML input")

    if len(html) > MAX_HTML_SIZE:
        raise ValueError("HTML size exceeds safe limit")

    return html


def make_soup(html: str) -> BeautifulSoup:
    """
    Create BeautifulSoup object safely
    """
    html = validate_html(html)

    try:
        soup = BeautifulSoup(html, "html.parser")
        return soup
    except Exception as e:
        logger.error(f"BeautifulSoup parse failed: {e}")
        raise ValueError("HTML parsing failed")


def extract_visible_text(soup: BeautifulSoup) -> str:
    """
    Extract visible text only (used by SEO signals)
    """
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    return soup.get_text(separator=" ", strip=True)
