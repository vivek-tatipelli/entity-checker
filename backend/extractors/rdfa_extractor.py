import logging
from typing import Dict, List, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class RDFaExtractor:
    """
    RDFa extractor with nested typeof support.
    """

    @staticmethod
    def extract_rdfa(soup: BeautifulSoup) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        nodes = soup.select("[typeof]")

        for node in nodes:
            try:
                entity = RDFaExtractor._extract_node(node)
                if entity:
                    results.append(entity)
            except Exception as e:
                logger.debug(f"RDFa parse error ignored: {e}")

        return results

    # --------------------------------------------------
    # Recursive extraction
    # --------------------------------------------------

    @staticmethod
    def _extract_node(node) -> Dict[str, Any]:
        typeof = node.get("typeof")
        if not typeof:
            return None

        schema_type = typeof.split(":")[-1]
        properties: Dict[str, Any] = {}

        for prop in node.select("[property]"):
            name = prop.get("property")
            if not name:
                continue

            value = prop.get("content") or prop.get_text(strip=True)
            if value:
                properties[name] = value

        return {
            "@type": schema_type,
            "properties": properties,
            "raw": {
                "typeof": typeof,
                "properties": properties
            }
        }
