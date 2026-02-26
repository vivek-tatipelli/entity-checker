import streamlit as st
import requests,json
import os
import pandas as pd
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------
# CONFIG
# --------------------------------------------------

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

API_ANALYZE = f"{BACKEND_URL}/api/analyze"
API_SCHEMA = f"{BACKEND_URL}/api/generate-schema"

st.set_page_config(
    page_title="Entity Validator and Schema Generator",
    layout="wide"
)

# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------

defaults = {
    "urls": [],
    "htmls": [],
    "results": {},
    "schemas": {}
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# --------------------------------------------------
# API HELPERS
# --------------------------------------------------

def call_analyze_api(payload):
    r = requests.post(API_ANALYZE, json=payload, timeout=300)

    if r.status_code != 200:
        raise Exception(r.text)

    return r.json()


def generate_schema(schema_name, entities, signals, url):

    payload = {
        "schema": schema_name,
        "entities": entities,
        "signals": signals,
        "url": url
    }

    r = requests.post(API_SCHEMA, json=payload, timeout=300)

    if r.status_code != 200:
        st.error(f"Schema API Error:\n{r.text}")
        return None

    return r.json()


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def compute_source_counts(entities):
    counts = {"jsonld": 0, "microdata": 0, "rdfa": 0}

    for block in entities.values():
        for item in block.get("items", []):
            src = item.get("source", "").lower()
            if src in counts:
                counts[src] += 1

    return counts


# --------------------------------------------------
# EXCEL EXPORT (ENTERPRISE STYLE)
# --------------------------------------------------

def build_excel(results_map):

    output = BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:

        workbook = writer.book

        header = workbook.add_format({
            "bold": True,
            "border": 1,
            "align": "center",
            "fg_color": "#E7F3FF"
        })

        # ---------- SUMMARY ----------
        summary_rows = []

        for url, page in results_map.items():

            entities = page.get("entities", {})
            counts = compute_source_counts(entities)

            summary_rows.append({
                "URL": url,
                "Total Entities": page.get("total_entities", 0),
                "JSON-LD": counts["jsonld"],
                "Microdata": counts["microdata"],
                "RDFa": counts["rdfa"]
            })

        df_summary = pd.DataFrame(summary_rows)
        df_summary.to_excel(
            excel_writer=writer,
            sheet_name="Entities Count",
            index=False
        )

        sheet = writer.sheets["Entities Count"]

        for col, name in enumerate(df_summary.columns):
            sheet.write(0, col, name, header)
            sheet.set_column(col, col, 30)

        sheet.freeze_panes(1, 0)

        # ---------- ENTITIES ----------
        entity_rows = []

        for url, page in results_map.items():

            for schema, block in page.get("entities", {}).items():

                for item in block.get("items", []):

                    entity_rows.append({
                        "URL": url,
                        "Schema": schema,
                        "Name": str(item.get("properties", {}).get("name", "")),
                        "Source": str(item.get("source", "")),
                        "Confidence": float(item.get("confidence", 0))
                    })

        df_entities = pd.DataFrame(entity_rows)
        df_entities.to_excel(
            excel_writer=writer,
            sheet_name="Extracted Entities",
            index=False
        )

        sheet = writer.sheets["Extracted Entities"]

        for col, name in enumerate(df_entities.columns):
            sheet.write(0, col, name, header)
            sheet.set_column(col, col, 32)

        sheet.freeze_panes(1, 0)

        # ---------- SUGGESTIONS ----------
        suggestion_rows = []

        for url, page in results_map.items():

            for category, items in page.get("suggestions", {}).items():

                for s in items:

                    suggestion_rows.append({
                        "URL": url,
                        "Schema": s.get("schema"),
                        "Confidence": s.get("confidence"),
                        "Category": category,
                        "Reason": s.get("reason")
                    })

        df_suggestions = pd.DataFrame(suggestion_rows)
        df_suggestions.to_excel(
            excel_writer=writer,
            sheet_name="Suggested Schemas",
            index=False
        )

        sheet = writer.sheets["Suggested Schemas"]

        for col, name in enumerate(df_suggestions.columns):
            sheet.write(0, col, name, header)
            sheet.set_column(col, col, 36)

        sheet.freeze_panes(1, 0)

    output.seek(0)
    return output


# --------------------------------------------------
# UI
# --------------------------------------------------

st.title("🔎 Entity Validator and Schema Generator")
st.caption("Structured Data • Entities • Schema Recommendations")

st.divider()

mode = st.radio("Choose Input", ["URL", "Raw HTML"], horizontal=True)

# --------------------------------------------------
# INPUT
# --------------------------------------------------

if mode == "URL":

    col1, col2 = st.columns([4, 1])

    with col1:
        new_url = st.text_input("Add URL")

    with col2:
        st.write("")
        if st.button("➕ Add", disabled=len(st.session_state.urls) >= 5):
            if new_url and new_url not in st.session_state.urls:
                st.session_state.urls.append(new_url)

    st.caption(f"URLs added: {len(st.session_state.urls)} / 5")

    for i, url in enumerate(st.session_state.urls):
        c1, c2 = st.columns([9, 1])
        c1.write(url)

        if c2.button("❌", key=f"remove_url_{i}"):
            st.session_state.urls.pop(i)

else:

    new_html = st.text_area("Paste HTML", height=180)

    if st.button("➕ Add HTML", disabled=len(st.session_state.htmls) >= 5):
        if new_html.strip():
            st.session_state.htmls.append(new_html)

    st.caption(f"HTMLs added: {len(st.session_state.htmls)} / 5")

    for i, _ in enumerate(st.session_state.htmls):
        c1, c2 = st.columns([9, 1])
        c1.code(f"HTML {i+1}")

        if c2.button("❌", key=f"remove_html_{i}"):
            st.session_state.htmls.pop(i)

st.divider()

# --------------------------------------------------
# RUN AUDIT
# --------------------------------------------------

disabled = (
    (mode == "URL" and not st.session_state.urls) or
    (mode == "Raw HTML" and not st.session_state.htmls)
)

if st.button("🚀 Run Audit", width="stretch", disabled=disabled):

    st.session_state.schemas = {}  # prevent stale schemas

    payload = {}

    if mode == "URL":
        payload["urls"] = st.session_state.urls
    else:
        payload["htmls"] = st.session_state.htmls

    try:
        with st.spinner("Running audit..."):
            result = call_analyze_api(payload)

    except Exception as e:
        st.error(f"Audit failed:\n{e}")
        st.stop()

    if "results" in result:
        st.session_state.results = result["results"]
    else:
        st.session_state.results = {"Result": result}


# --------------------------------------------------
# DISPLAY RESULTS
# --------------------------------------------------

for url, page in st.session_state.results.items():

    with st.expander(
        f"🔗 {url}",
        expanded=len(st.session_state.results) == 1
    ):

        entities = page.get("entities", {})
        signals = page.get("signals", {})
        suggestions = page.get("suggestions", {})

        counts = compute_source_counts(entities)

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Total Entities", page.get("total_entities", 0))
        c2.metric("JSON-LD", counts["jsonld"])
        c3.metric("Microdata", counts["microdata"])
        c4.metric("RDFa", counts["rdfa"])

        st.divider()

        # ENTITIES
        with st.expander("🧩 Extracted Entities"):

            if not entities:
                st.info("No structured data found.")
            else:
                for schema, block in entities.items():
                    with st.expander(schema):
                        st.json(block["items"])

        # SUGGESTIONS + AI
        with st.expander("💡 Suggested Schemas"):

            if not suggestions:
                st.caption("No suggestions.")
            else:

                for category, items in suggestions.items():

                    st.markdown(f"### {category}")

                    for idx, s in enumerate(items):
                        schema_name = s["schema"]
                        key = f"{url}_{category}_{schema_name}_{idx}"

                        with st.expander(schema_name):
                            st.write(s["reason"])
                            if key not in st.session_state.schemas:

                                if st.button("Generate Schema",key=key):
                                    schema = generate_schema(schema_name, entities, signals, url)

                                    if schema:
                                        st.session_state.schemas[key] = schema

                            if key in st.session_state.schemas:
                                st.code(json.dumps(
                                        st.session_state.schemas[key],
                                        indent=2,
                                        ensure_ascii=False
                                    ),language="json"
                                )


        with st.expander("📦 Export Page Data"):
            st.download_button(
                "Download Page JSON",
                data=json.dumps(
                    page,
                    indent=2,
                    ensure_ascii=False
                ),
                file_name=f"audit_{url.replace('/','_')}.json",
                mime="application/json"
            )


# --------------------------------------------------
# GLOBAL EXCEL
# --------------------------------------------------

if st.session_state.results:

    excel = build_excel(st.session_state.results)

    st.download_button(
        "📊 Download Full Audit Excel",
        data=excel,
        file_name="entityscope_audit.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )