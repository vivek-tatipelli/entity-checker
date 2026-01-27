import re
import logging
from typing import Dict
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class SEOMetricsAnalyzer:
    """
    SEO Signals Analyzer (Layer-2)
    Produces strong, evidence-based signals for schema suggestions.
    NO entity extraction here.
    """

    def analyze(self, html: str, soup: BeautifulSoup) -> Dict:
        return {
            "meta": self._meta_signals(soup),
            "content": self._content_signals(soup),
            "media": self._media_signals(html, soup),
            "ecommerce": self._ecommerce_signals(html),
            "local": self._local_signals(soup),
            "structured_data_hints": self._structured_data_hints(html),
        }

    # --------------------------------------------------
    # META SIGNALS
    # --------------------------------------------------

    def _meta_signals(self, soup: BeautifulSoup) -> Dict:
        title = soup.find("title")
        description = soup.find("meta", attrs={"name": "description"})

        title_text = title.get_text(strip=True) if title else ""
        desc_text = description.get("content", "") if description else ""

        return {
            "title_present": bool(title_text),
            "title_length": len(title_text),
            "description_present": bool(desc_text),
            "description_length": len(desc_text),
        }

    # --------------------------------------------------
    # CONTENT SIGNALS
    # --------------------------------------------------

    def _content_signals(self, soup: BeautifulSoup) -> Dict:
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)
        text_lower = text.lower()
        word_count = len(text.split())

        faq_like = any(
            k in text_lower
            for k in ("faq", "faqs", "questions", "answers", "help")
        )

        return {
            "word_count": word_count,
            "long_form_content": word_count >= 600,
            "very_long_content": word_count >= 1200,
            "multiple_h1": len(soup.find_all("h1")) > 1,
            "faq_like_content": faq_like,
            "navigation_detected": bool(soup.find("nav")),
        }

    # --------------------------------------------------
    # MEDIA SIGNALS
    # --------------------------------------------------

    def _media_signals(self, html: str, soup: BeautifulSoup) -> Dict:
        html_lower = html.lower()
        images = soup.find_all("img")

        return {
            "youtube_embedded": any(
                d in html_lower
                for d in ("youtube.com", "youtu.be", "youtube-nocookie.com")
            ),
            "image_rich": len(images) >= 5,
        }

    # --------------------------------------------------
    # ECOMMERCE SIGNALS
    # --------------------------------------------------

    def _ecommerce_signals(self, html: str) -> Dict:
        html_lower = html.lower()
        price_pattern = re.compile(r"(₹|\$|€)\s?\d+")

        return {
            "product_detected": any(
                k in html_lower
                for k in ("add to cart", "buy now", "add-to-cart")
            ),
            "price_detected": bool(price_pattern.search(html_lower)),
            "multi_price_detected": len(price_pattern.findall(html_lower)) > 1,
            "review_detected": any(
                k in html_lower
                for k in ("review", "reviews", "rating", "ratings", "stars")
            ),
        }

    # --------------------------------------------------
    # LOCAL / BUSINESS SIGNALS
    # --------------------------------------------------

    def _local_signals(self, soup: BeautifulSoup) -> Dict:
        address = soup.find("address")

        phone_present = bool(
            soup.find(string=re.compile(r"\+?\d[\d\s\-]{8,}"))
        )

        return {
            "contact_present": bool(address or phone_present),
            "address_present": bool(address),
        }

    # --------------------------------------------------
    # STRUCTURED DATA HINTS
    # --------------------------------------------------

    def _structured_data_hints(self, html: str) -> Dict:
        html_lower = html.lower()

        return {
            "json_ld_present": "application/ld+json" in html_lower,
            "microdata_present": "itemscope" in html_lower,
            "rdfa_present": "typeof=" in html_lower,
        }
