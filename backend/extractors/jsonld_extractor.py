import json
import logging
from typing import Dict, List, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class JSONLDExtractor:
    """
    JSON-LD extractor with nested entity detection.
    """

    @staticmethod
    def extract_json_ld(soup: BeautifulSoup) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        scripts = soup.find_all("script", type="application/ld+json")

        for script in scripts:
            if not script.string:
                continue

            try:
                data = json.loads(script.string.strip())
                blocks = data if isinstance(data, list) else [data]

                for block in blocks:
                    JSONLDExtractor._extract_entities_recursive(block, results)

            except Exception as e:
                logger.debug(f"JSON-LD parse error ignored: {e}")

        return results

    # --------------------------------------------------
    # Recursive extraction
    # --------------------------------------------------

    @staticmethod
    def _extract_entities_recursive(
        obj: Any,
        collected: List[Dict[str, Any]]
    ):
        if isinstance(obj, dict):
            if "@type" in obj:
                cleaned = JSONLDExtractor._remove_imageobjects(obj)
                if cleaned:
                    collected.append(cleaned)

            for value in obj.values():
                JSONLDExtractor._extract_entities_recursive(value, collected)

        elif isinstance(obj, list):
            for item in obj:
                JSONLDExtractor._extract_entities_recursive(item, collected)

    # --------------------------------------------------
    # Cleanup helpers
    # --------------------------------------------------

    @staticmethod
    def _remove_imageobjects(obj):
        """
        Remove ImageObject nodes recursively.
        """
        if isinstance(obj, dict):
            if obj.get("@type") == "ImageObject":
                return None

            cleaned = {}
            for k, v in obj.items():
                v_clean = JSONLDExtractor._remove_imageobjects(v)
                if v_clean is not None:
                    cleaned[k] = v_clean
            return cleaned

        if isinstance(obj, list):
            return [
                item for item in
                (JSONLDExtractor._remove_imageobjects(i) for i in obj)
                if item is not None
            ]

        return obj
