import streamlit as st
import requests
import json
import os

# --------------------------------------------------
# Config
# --------------------------------------------------

BACKEND_URL = os.getenv("BACKEND_URL","")

API_URL = None

if BACKEND_URL:
    API_URL = f"{BACKEND_URL}/api/analyze"
else:
    API_URL = "http://localhost:8000/api/analyze"

st.set_page_config(
    page_title="Entity Checker",
    layout="wide",
    page_icon="🔎"
)

# --------------------------------------------------
# Helpers
# --------------------------------------------------

def call_api(payload: dict):
    resp = requests.post(API_URL, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


def json_view(data):
    st.json(data, expanded=True)


def compute_source_counts(entities: dict):
    counts = {"jsonld": 0, "microdata": 0, "rdfa": 0}
    for block in entities.values():
        for item in block.get("items", []):
            src = item.get("source", "")
            if src in counts:
                counts[src] += 1
    return counts


RECOMMENDATION_LABELS = {
    "high": "Strongly Recommended",
    "medium": "Recommended",
    "low": "Optional"
}

# --------------------------------------------------
# Header
# --------------------------------------------------

st.markdown(
    """
    <h1 style="text-align:center;">🔎 Entity Checker</h1>
    <p style="text-align:center;color:gray;">
    Structured Data • Entity Intelligence • Schema Recommendations
    </p>
    """,
    unsafe_allow_html=True
)

st.divider()

# --------------------------------------------------
# Input Card
# --------------------------------------------------

with st.container():
    st.subheader("🔧 Page Input")

    input_mode = st.radio(
        "Choose input type",
        ["URL", "Raw HTML"],
        horizontal=True
    )

    payload = {}

    if input_mode == "URL":
        url = st.text_input(
            "Page URL",
            placeholder="https://example.com"
        )
        if url:
            payload["url"] = url
    else:
        html = st.text_area(
            "Paste HTML",
            height=260,
            placeholder="<html>...</html>"
        )
        if html:
            payload["html"] = html

    analyze_clicked = st.button("🚀 Analyze Page", type="primary", use_container_width=True)

st.divider()

# --------------------------------------------------
# Results
# --------------------------------------------------

if analyze_clicked:
    if not payload:
        st.warning("Please provide a URL or HTML.")
        st.stop()

    with st.spinner("Analyzing structured data…"):
        try:
            result = call_api(payload)
        except Exception as e:
            st.error(f"Analysis failed: {e}")
            st.stop()

    # --------------------------------------------------
    # Overview Dashboard
    # --------------------------------------------------

    st.subheader("📊 Overview")

    entities = result.get("entities", {})
    source_counts = compute_source_counts(entities)

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Total Entities", result.get("total_entities", 0))
    c2.metric("JSON-LD", source_counts["jsonld"])
    c3.metric("Microdata", source_counts["microdata"])
    c4.metric("RDFa", source_counts["rdfa"])

    st.divider()

    # --------------------------------------------------
    # Extracted Entities
    # --------------------------------------------------

    st.subheader("Extracted Entities")

    if not entities:
        st.info("No structured data entities detected.")
    else:
        for schema_type, block in entities.items():
            with st.expander(
                f"{schema_type}",
                expanded=False
            ):
                json_view(block["items"])

    st.divider()

    # --------------------------------------------------
    # Schema Suggestions
    # --------------------------------------------------

    st.subheader("Schema Suggestions")

    suggestions_by_category = result.get("suggestions", {})

    # Flatten suggestions
    all_suggestions = []
    for items in suggestions_by_category.values():
        all_suggestions.extend(items)

    # Group by recommendation strength
    grouped_by_confidence = {
        "high": [],
        "medium": [],
        "low": []
    }

    for s in all_suggestions:
        level = s.get("confidence", "medium")
        grouped_by_confidence.setdefault(level, []).append(s)

    # Render: Title → Expander (confidence) → Category → Schema
    for level in ["high", "medium", "low"]:
        strength_label = RECOMMENDATION_LABELS[level]
        level_items = grouped_by_confidence[level]

        with st.expander(
            strength_label,
            expanded=False
        ):
            if not level_items:
                st.caption("No suggestions in this group.")
                continue

            # Group by category inside this confidence level
            category_map = {}
            for s in level_items:
                category = s.get("category", "General")
                category_map.setdefault(category, []).append(s)

            for category, items in category_map.items():
                st.markdown(f"#### {category}")

                for s in items:
                    with st.expander(
                        s["schema"],
                        expanded=False
                    ):
                        st.markdown(f"**Reason:** {s['reason']}")
                        st.markdown(
                            f"[Schema.org → {s['schema']}]({s['schema_url']})"
                        )

    st.divider()
    
    # --------------------------------------------------
    # Export Results
    # --------------------------------------------------

    st.subheader("📤 Export Results")

    export_suggestions = []
    for items in result.get("suggestions", {}).values():
        export_suggestions.extend(items)

    # 2. Summary data
    entities = result.get("entities", {})
    summary_rows = []

    for schema_type, block in entities.items():
        summary_rows.append({
            "schema": schema_type,
            "count": block.get("count", 0)
        })

    # -------- Export buttons --------

    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
        label="📄 Download Suggestions (JSON)",
        data=json.dumps(export_suggestions, indent=2),
        file_name="schema_suggestions.json",
        mime="application/json"
    )


    with col2:
        import pandas as pd
        df = pd.DataFrame(summary_rows)

        st.download_button(
            label="📊 Download Entity Summary (CSV)",
            data=df.to_csv(index=False),
            file_name="entity_summary.csv",
            mime="text/csv"
        )
