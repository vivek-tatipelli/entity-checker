import logging
import requests
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}

TIMEOUT = 30 
MAX_RESPONSE_SIZE = 5_000_000


def validate_url(url: str) -> str:
    """
    Phase-1 URL validator
    """
    if not url or not isinstance(url, str):
        raise ValueError("Invalid URL")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http/https URLs are allowed")

    if not parsed.netloc:
        raise ValueError("Invalid URL format")

    return url


def fetch_html(url: str) -> str:
    """
    Fetch HTML for ONE page only
    """
    url = validate_url(url)

    try:
        response = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True
        )

        response.raise_for_status()

        content = response.text
        if len(content) > MAX_RESPONSE_SIZE:
            raise ValueError("Response too large")

        return content

    except requests.RequestException as e:
        logger.error(f"Failed to fetch URL {url}: {e}")
        raise ValueError("Failed to fetch page")
