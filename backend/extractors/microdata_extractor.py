import logging
from typing import Dict, List, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class MicrodataExtractor:
    """
    Microdata extractor with nested itemscope support.
    """

    @staticmethod
    def extract_microdata(soup: BeautifulSoup) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        items = soup.select("[itemscope][itemtype]")

        for item in items:
            try:
                entity = MicrodataExtractor._extract_item(item)
                if entity:
                    results.append(entity)
            except Exception as e:
                logger.debug(f"Microdata parse error ignored: {e}")

        return results

    # --------------------------------------------------
    # Recursive extraction
    # --------------------------------------------------

    @staticmethod
    def _extract_item(node) -> Dict[str, Any]:
        itemtype = node.get("itemtype")
        if not itemtype:
            return None

        schema_type = itemtype.split("/")[-1]
        properties: Dict[str, Any] = {}

        for prop in node.select("[itemprop]"):
            name = prop.get("itemprop")
            if not name:
                continue

            if prop.has_attr("itemscope"):
                nested = MicrodataExtractor._extract_item(prop)
                if nested:
                    properties[name] = nested
            else:
                value = prop.get("content") or prop.get_text(strip=True)
                if value:
                    properties[name] = value

        return {
            "@type": schema_type,
            "properties": properties,
            "raw": {
                "itemtype": itemtype,
                "properties": properties
            }
        }
