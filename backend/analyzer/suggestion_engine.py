import yaml
from typing import Dict, Any, Set, List
from pathlib import Path
from backend.analyzer.type_resolver import is_subclass


# ==================================================
# Schema Satisfaction Rules (Semantic Completeness)
# ==================================================

SCHEMA_SATISFACTION_RULES = {

    # ---------------- FAQ ----------------
    "FAQPage": {
        "any_of": [
            {"Question", "Answer"},
        ]
    },
    "Question": {
        "any_of": [
            {"FAQPage"},
        ]
    },
    "Answer": {
        "any_of": [
            {"FAQPage"},
        ]
    },

    # ---------------- CONTENT ----------------
    "Article": {
        "any_of": [
            {"BlogPosting"},
            {"NewsArticle"},
        ]
    },
    "BlogPosting": {
        "any_of": [
            {"Article"},
        ]
    },
    "NewsArticle": {
        "any_of": [
            {"Article"},
        ]
    },

    # ---------------- PRODUCT / ECOMMERCE ----------------
    "Product": {
        "any_of": [
            {"Offer"},
            {"AggregateOffer"},
        ]
    },
    "Offer": {
        "any_of": [
            {"Product"},
        ]
    },
    "AggregateOffer": {
        "any_of": [
            {"Product"},
        ]
    },
    "Review": {
        "any_of": [
            {"AggregateRating"},
        ]
    },
    "Rating": {
        "any_of": [
            {"AggregateRating"},
        ]
    },

    # ---------------- ORGANIZATION / LOCAL ----------------
    "Organization": {
        "any_of": [
            {"LocalBusiness"},
        ]
    },
    "LocalBusiness": {
        "any_of": [
            {"Organization"},
        ]
    },
    "PostalAddress": {
        "any_of": [
            {"LocalBusiness"},
            {"Organization"},
        ]
    },
    "GeoCoordinates": {
        "any_of": [
            {"Place"},
            {"LocalBusiness"},
        ]
    },

    # ---------------- MEDIA ----------------
    "VideoObject": {
        "any_of": [
            {"Clip"},
        ]
    },
    "ImageObject": {
        "any_of": [
            {"MediaObject"},
        ]
    },

    # ---------------- NAVIGATION ----------------
    "BreadcrumbList": {
        "any_of": [
            {"WebPage"},
            {"SiteNavigationElement"},
        ]
    },

    # ---------------- WEBSITE ----------------
    "WebPage": {
        "any_of": [
            {"Article"},
            {"Product"},
            {"FAQPage"},
        ]
    },
    "WebSite": {
        "any_of": [
            {"SearchAction"},
        ]
    }
}


class SuggestionEngine:
    """
    Rule + Signal + Ontology + Semantic Satisfaction
    schema suggestion engine (Production-grade)
    """

    # --------------------------------------------------
    # Ontology-based related schema expansion
    # --------------------------------------------------

    RELATED_SCHEMAS = {

        # -------- Content --------
        "Article": {"Author", "Publisher"},
        "BlogPosting": {"Author", "Publisher"},
        "NewsArticle": {"Author", "Publisher"},
        "HowTo": {"HowToStep", "HowToSupply", "HowToTool"},
        "FAQPage": {"Question", "Answer"},

        # -------- Media --------
        "VideoObject": {"Clip"},
        "ImageObject": {"MediaObject"},

        # -------- Organization / Local --------
        "Organization": {"WebSite", "ContactPoint"},
        "LocalBusiness": {
            "OpeningHoursSpecification",
            "PostalAddress",
            "GeoCoordinates"
        },

        # -------- Ecommerce --------
        "Product": {"Offer", "AggregateOffer", "Review"},
        "Offer": {"PriceSpecification"},
        "AggregateOffer": {"Offer"},
        "Review": {"Rating"},
    }

    # --------------------------------------------------
    # Init
    # --------------------------------------------------

    def __init__(self, rules_path: str):
        rules_file = Path(rules_path)

        with open(rules_file, "r", encoding="utf-8") as f:
            self.rules = yaml.safe_load(f) or []

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def generate(
        self,
        entities: List[Any],
        signals: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:

        # All resolved schema types present on page
        present_types: Set[str] = {
            t for e in entities for t in e.resolved_types
        }

        suggestions: List[Dict[str, Any]] = []
        suggested_schemas: Set[str] = set()

        # ---------------- Layer 1: Rule-based ----------------
        for rule in self.rules:
            if not self._rule_matches(rule, present_types, signals):
                continue

            schema = rule["suggest"]

            # Skip if already present (ontology-aware)
            if any(is_subclass(t, schema) for t in present_types):
                continue

            # Skip if semantically satisfied
            if self._is_schema_satisfied(schema, present_types):
                continue

            # Domain guard: Review must have Product
            if schema == "Review" and not any(
                is_subclass(t, "Product") for t in present_types
            ):
                continue

            if schema in suggested_schemas:
                continue

            suggestions.append({
                "schema": schema,
                "confidence": rule.get("confidence", "medium"),
                "category": rule.get("category", "General"),
                "reason": rule.get("reason", ""),
                "schema_url": f"https://schema.org/{schema}"
            })

            suggested_schemas.add(schema)

        # ---------------- Layer 3: Ontology-based expansion ----------------
        suggestions.extend(
            self._expand_related_schemas(
                present_types,
                suggested_schemas
            )
        )

        return self._group_by_category(suggestions)

    # --------------------------------------------------
    # Rule evaluation
    # --------------------------------------------------

    def _rule_matches(
        self,
        rule: Dict[str, Any],
        present_types: Set[str],
        signals: Dict[str, Any]
    ) -> bool:

        conditions = rule.get("when", {})

        for key, expected in conditions.items():

            if key == "missing_schema":
                if any(is_subclass(t, expected) for t in present_types):
                    return False
                continue

            if key.startswith("signal."):
                actual = self._get_signal_value(signals, key)
                if actual != expected:
                    return False
                continue

            return False

        return True

    # --------------------------------------------------
    # Ontology expansion (with dedupe + satisfaction)
    # --------------------------------------------------

    def _expand_related_schemas(
        self,
        present_types: Set[str],
        suggested_schemas: Set[str]
    ) -> List[Dict[str, Any]]:

        expanded: List[Dict[str, Any]] = []

        for present in present_types:
            for parent, related_set in self.RELATED_SCHEMAS.items():

                if not is_subclass(present, parent):
                    continue

                for related in related_set:

                    if any(is_subclass(t, related) for t in present_types):
                        continue

                    if self._is_schema_satisfied(related, present_types):
                        continue

                    if related in suggested_schemas:
                        continue

                    expanded.append({
                        "schema": related,
                        "confidence": "low",
                        "category": "Related",
                        "reason": f"Commonly used with {parent}",
                        "schema_url": f"https://schema.org/{related}"
                    })

                    suggested_schemas.add(related)

        return expanded

    # --------------------------------------------------
    # Semantic satisfaction (ontology-aware)
    # --------------------------------------------------

    def _is_schema_satisfied(
        self,
        target_schema: str,
        present_types: Set[str]
    ) -> bool:

        rule = SCHEMA_SATISFACTION_RULES.get(target_schema)
        if not rule:
            return False

        any_of_sets = rule.get("any_of", [])

        for required_set in any_of_sets:
            if all(
                any(is_subclass(t, required) for t in present_types)
                for required in required_set
            ):
                return True

        return False

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------

    def _get_signal_value(self, signals: Dict[str, Any], path: str):
        parts = path.replace("signal.", "").split(".")
        value = signals

        for part in parts:
            if not isinstance(value, dict):
                return None
            value = value.get(part)

        return value

    def _group_by_category(
        self,
        suggestions: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:

        grouped: Dict[str, List[Dict[str, Any]]] = {}

        for s in suggestions:
            grouped.setdefault(s["category"], []).append(s)

        return grouped
