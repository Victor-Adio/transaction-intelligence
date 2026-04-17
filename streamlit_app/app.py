from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from services.embeddings import QueryEmbedder
from services.tigergraph_client import TigerGraphDemoClient
from services.connection import load_saved_connection, get_tg_client
from services.cluster_viz import graph_network_figure


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "all-MiniLM-L6-v2"
CONNECTION_STATE_FILE = ROOT / ".streamlit_connection.json"


# ---------------------------------------------------------------------------
# Local merchant lookup — used to enrich TigerGraph results with city/country/
# region that the Merchant vertex schema does not store (those live in Location)
# ---------------------------------------------------------------------------
import csv as _csv

@st.cache_data(show_spinner=False)
def _load_merchant_lookup() -> dict[str, dict]:
    """Return {merchant_id: {name, city, country, region, mcc, type}} from CSV."""
    merch_file = ROOT / "data" / "vertices" / "merchants.csv"
    if not merch_file.exists():
        return {}
    lookup: dict[str, dict] = {}
    with open(merch_file, newline="", encoding="utf-8") as f:
        for row in _csv.DictReader(f):
            mid = row.get("merchant_id", "").strip()
            if mid:
                lookup[mid] = {
                    "name":    row.get("merchant_name", ""),
                    "city":    row.get("merchant_city", ""),
                    "country": row.get("merchant_country", "") or row.get("merchant_country_code", ""),
                    "region":  row.get("merchant_region_code", ""),
                    "mcc":     row.get("merchant_category_code", ""),
                    "type":    row.get("merchant_type", "") or row.get("merch_type", "") or row.get("merchant_category_code", ""),
                }
    return lookup

# ISO 4217 numeric → symbol mapping for common codes
CURRENCY_MAP: dict[int, str] = {
    840: "USD", 978: "EUR", 826: "GBP", 392: "JPY", 36: "AUD",
    124: "CAD", 756: "CHF", 156: "CNY", 356: "INR", 566: "NGN",
    710: "ZAR", 634: "QAR", 784: "AED", 682: "SAR", 702: "SGD",
}

SEARCH_MODES = {
    "🔍 Transaction Risk": {
        "vertex_type": "Transaction",
        "vector_attribute": "risk_embedding",
        "context_query": "Get_transaction_context",
        "summary_query": "Summarize_transaction_patterns",
        "description": "Find transactions semantically similar to your risk query — unusual geography, high value, off-hours, cash-like categories.",
        "example_queries": [
            "Suspicious high-value late-night cash transactions",
            "Cross-border transactions with high amounts in unusual regions",
            "Premium electronics purchases with elevated risk signals",
            "Transactions flagged as potential money laundering patterns",
        ],
    },
    "💳 Transaction Behaviour": {
        "vertex_type": "Transaction",
        "vector_attribute": "behaviour_emb",
        "context_query": "Get_transaction_context",
        "summary_query": "Summarize_transaction_patterns",
        "description": "Surface transactions by spending pattern — dining, travel, weekend leisure, or recurring category behaviour.",
        "example_queries": [
            "Premium international travel and airline spending",
            "Weekend dining and entertainment spend",
            "Regular grocery and supermarket purchases",
            "Luxury retail and high-end fashion transactions",
        ],
    },
    "🏪 Merchant Similarity": {
        "vertex_type": "Merchant",
        "vector_attribute": "embedding",
        "context_query": "Get_merchant_context",
        "summary_query": "Summarize_merchant_exposure",
        "description": "Identify merchants with similar transaction profiles — risk posture, dominant card type, spend category.",
        "example_queries": [
            "High-risk electronics merchants with large average transactions",
            "International luxury hospitality and hotel merchants",
            "Fuel stations and automotive merchants with frequent small payments",
            "Online marketplace merchants with high card-not-present volume",
        ],
    },
    "👤 User Similarity": {
        "vertex_type": "User",
        "vector_attribute": "embedding",
        "context_query": "Get_user_context",
        "summary_query": "Summarize_user_behavior",
        "description": "Find users with comparable spending behaviour or risk profile — useful for cohort analysis and fraud ring detection.",
        "example_queries": [
            "High-value international spenders with frequent cross-border activity",
            "Users with concentrated late-night cash-like transactions",
            "Affluent users with premium travel and hospitality spending",
            "Users showing irregular transaction timing and geography",
        ],
    },
}


# ── Connection helpers (load_saved_connection imported from services.connection) ─


def save_connection(payload: dict[str, object]) -> None:
    CONNECTION_STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def clear_saved_connection() -> None:
    if CONNECTION_STATE_FILE.exists():
        CONNECTION_STATE_FILE.unlink()


# ── Data extraction helpers ────────────────────────────────────────────────

def _currency_label(code: Any) -> str:
    """Convert a numeric or string currency code to a readable label."""
    if isinstance(code, int):
        return CURRENCY_MAP.get(code, str(code))
    return str(code) if code else "—"


def extract_transactions(results: list[dict]) -> pd.DataFrame:
    # "start_txns"  → Get_transaction_context
    # "txns"        → Get_user_context, Get_merchant_context, summary queries
    # "candidates"  → raw vector search results
    seen: set[str] = set()
    rows = []
    for block in results:
        for key in ("start_txns", "txns", "candidates"):
            for v in block.get(key, []):
                if v.get("v_type", "Transaction") != "Transaction":
                    continue
                vid = v.get("v_id", "")
                if vid in seen:
                    continue
                seen.add(vid)
                attrs = v.get("attributes", {})
                rows.append({
                    "ID":       vid,
                    "Amount":   attrs.get("amount_float") or attrs.get("Amount") or 0,
                    "Currency": _currency_label(attrs.get("Currency_code")),
                    "Channel":  attrs.get("Channel_type", ""),
                    "Response": attrs.get("response_code", ""),
                })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def extract_merchants(results: list[dict]) -> pd.DataFrame:
    ml = _load_merchant_lookup()
    seen: set[str] = set()
    rows = []
    for block in results:
        for key in ("related_merchants", "merchants", "candidates"):
            for v in block.get(key, []):
                if v.get("v_type", "Merchant") != "Merchant":
                    continue
                vid = v.get("v_id", "")
                if vid in seen:
                    continue
                seen.add(vid)
                attrs  = v.get("attributes", {})
                local  = ml.get(vid, {})
                # TG Merchant vertex only stores name/type; city/country/region come from local lookup
                rows.append({
                    "ID":      vid,
                    "Name":    attrs.get("merch_name") or local.get("name") or vid,
                    "City":    attrs.get("merch_city") or attrs.get("merchant_city") or local.get("city", "") or "—",
                    "Country": attrs.get("merchant_country") or attrs.get("merchant_country_code") or local.get("country", "") or "—",
                    "Region":  attrs.get("merch_region_code") or attrs.get("merchant_region_code") or local.get("region", "") or "—",
                    "Type":    attrs.get("merch_type") or local.get("type", "") or "—",
                })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def extract_users(results: list[dict]) -> pd.DataFrame:
    rows = []
    for block in results:
        for key in ("related_users", "users", "candidates"):
            for v in block.get(key, []):
                attrs = v.get("attributes", {})
                rows.append({
                    "User ID": v.get("v_id", ""),
                    "Issuer": attrs.get("dw_issuer_id", ""),
                    "Product": attrs.get("dw_product_cd", ""),
                    "Country": attrs.get("country_cd", ""),
                })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def extract_locations(results: list[dict]) -> pd.DataFrame:
    ml = _load_merchant_lookup()
    seen: set[str] = set()
    rows = []

    def _add(city: str, region: str, country: str, lat: str = "", lon: str = "") -> None:
        city    = city.strip()    if city    else ""
        region  = region.strip()  if region  else ""
        country = country.strip() if country else ""
        key = f"{city}|{region}|{country}"
        if key not in seen and any([city, region, country]):
            seen.add(key)
            rows.append({
                "City":    city    or "—",
                "Region":  region  or "—",
                "Country": country or "—",
                "Lat":     lat,
                "Lon":     lon,
            })

    for block in results:
        # Primary: Location vertices returned by GSQL context queries
        # l.country is the new attribute; fall back to merchant_country_code for
        # older loads that do not yet carry it.
        for key in ("related_locations", "locations"):
            for v in block.get(key, []):
                a = v.get("attributes", {})
                _add(
                    str(a.get("merch_city", "")),
                    str(a.get("merch_region_code", "")),
                    str(a.get("merchant_country", "") or a.get("merchant_country_code", "")),
                    str(a.get("latitude",  "")),
                    str(a.get("longitude", "")),
                )

        # Fallback 1: Merchant vertex attributes (TG schema may carry these)
        for key in ("related_merchants", "merchants", "candidates"):
            for v in block.get(key, []):
                if v.get("v_type", "") == "Merchant":
                    a   = v.get("attributes", {})
                    vid = v.get("v_id", "")
                    local = ml.get(vid, {})
                    _add(
                        str(a.get("merch_city", "") or a.get("merchant_city", "") or local.get("city", "")),
                        str(a.get("merch_region_code", "") or a.get("merchant_region_code", "") or local.get("region", "")),
                        str(a.get("merchant_country_code", "") or a.get("merch_country_code", "") or local.get("country", "")),
                    )

    # Fallback 2: if no locations from the graph at all, build from full merchant lookup
    # for every merchant ID that appears anywhere in the results
    if not rows:
        all_merchant_ids: set[str] = set()
        for block in results:
            for key in ("related_merchants", "merchants", "candidates", "txns", "start_txns"):
                for v in block.get(key, []):
                    if v.get("v_type", "") in ("Merchant", "") and v.get("v_id", ""):
                        all_merchant_ids.add(v["v_id"])
        for mid in all_merchant_ids:
            local = ml.get(mid, {})
            if local:
                _add(local.get("city", ""), local.get("region", ""), local.get("country", ""))

    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    if not df.empty and df[["Lat", "Lon"]].replace("", pd.NA).isna().all().all():
        df = df.drop(columns=["Lat", "Lon"])
    return df


def _extract_txn_vertices(summary: list[dict]) -> list[dict]:
    """Pull all Transaction vertex attribute dicts out of a summary results list."""
    txn_attrs = []
    for block in summary:
        for key in ("txns", "start_txns", "candidates"):
            for v in block.get(key, []):
                if isinstance(v, dict):
                    attrs = v.get("attributes", {})
                    if attrs:
                        txn_attrs.append(attrs)
    return txn_attrs


def render_summary_metrics(summary: list[dict], mode: str) -> None:
    """Render the summary payload as readable metrics and charts.

    The GSQL summary queries return vertex sets (txns, merchants, users)
    plus pre-aggregated histograms where possible.  Amount stats are computed
    here from the raw vertex attributes since GSQL TYP-8017 prevents
    accumulating amount_float server-side.
    """
    if not summary:
        st.info("No summary data returned.")
        return

    # Flatten all scalar / dict values from result blocks
    data: dict = {}
    for block in summary:
        for k, v in block.items():
            if not isinstance(v, list):          # skip vertex-set arrays
                data[k] = v
            elif k not in data:
                data[k] = v                      # keep first occurrence of lists

    # ── Amount stats — computed from returned transaction vertices ─────────
    txn_vertices = _extract_txn_vertices(summary)
    amounts = [
        float(a.get("amount_float") or a.get("Amount") or 0)
        for a in txn_vertices
        if (a.get("amount_float") or a.get("Amount"))
    ]
    total_amt = sum(amounts)
    max_amt   = max(amounts) if amounts else 0.0
    avg_amt   = total_amt / len(amounts) if amounts else 0.0

    # ── Transaction count — prefer GSQL counter, fall back to vertex list ──
    txn_count = int(data.get("txn_count", len(txn_vertices)))

    # ── Channel & response histograms — built from vertex attrs if absent ──
    channel_hist: dict[str, int] = dict(data.get("channel_histogram", {}))
    response_hist: dict[str, int] = dict(data.get("response_histogram", {}))
    if not channel_hist:
        for a in txn_vertices:
            ch = str(a.get("Channel_type") or "Unknown")
            channel_hist[ch] = channel_hist.get(ch, 0) + 1
    if not response_hist:
        for a in txn_vertices:
            rc = str(a.get("response_code") or "Unknown")
            response_hist[rc] = response_hist.get(rc, 0) + 1

    region_hist:  dict[str, int] = dict(data.get("region_histogram",  {}))
    country_hist: dict[str, int] = dict(data.get("country_histogram", {}))
    mcc_hist:     dict[str, int] = dict(data.get("mcc_histogram",     {}))

    # Extra counts for merchant / user modes
    merchant_count = int(data.get("merchant_count", 0))
    user_count     = int(data.get("user_count", 0))

    # ── Metric strip ───────────────────────────────────────────────────────
    cols = st.columns(5)
    cols[0].metric("Transactions", f"{txn_count:,}")
    cols[1].metric("Total Amount", f"{total_amt:,.2f}" if total_amt else "—")
    cols[2].metric("Avg Amount",   f"{avg_amt:,.2f}"   if avg_amt   else "—")
    cols[3].metric("Max Single Txn", f"{max_amt:,.2f}" if max_amt   else "—")
    if merchant_count:
        cols[4].metric("Merchants", f"{merchant_count:,}")
    elif user_count:
        cols[4].metric("Users", f"{user_count:,}")
    else:
        cols[4].metric("Vector Matches", f"{txn_count:,}")

    st.write("")
    col_a, col_b = st.columns(2)

    if channel_hist:
        with col_a:
            st.markdown("**Channel Mix**")
            st.bar_chart(pd.Series(channel_hist).sort_values(ascending=False))

    if region_hist:
        with col_b:
            st.markdown("**Region Distribution**")
            st.bar_chart(pd.Series(region_hist).sort_values(ascending=False))

    if country_hist:
        col_c, col_d = st.columns(2)
        with col_c:
            st.markdown("**Country Distribution**")
            st.bar_chart(pd.Series(country_hist).sort_values(ascending=False))

    if mcc_hist:
        st.markdown("**Merchant Category Codes (MCC)**")
        mcc_df = pd.DataFrame(
            list(mcc_hist.items()), columns=["MCC", "Count"]
        ).sort_values("Count", ascending=False)
        st.dataframe(mcc_df, use_container_width=True, hide_index=True)

    if response_hist:
        st.markdown("**Response Codes**")
        st.dataframe(
            pd.DataFrame(list(response_hist.items()), columns=["Code", "Count"]).sort_values("Count", ascending=False),
            use_container_width=True, hide_index=True,
        )


# ── Sidebar ────────────────────────────────────────────────────────────────

def render_sidebar() -> dict[str, object]:
    saved = load_saved_connection()
    default_host     = str(saved.get("host", os.getenv("TG_HOST", "")))
    default_graph    = str(saved.get("graph_name", os.getenv("TG_GRAPH_NAME", "Tran_graph")))
    default_username = str(saved.get("username", os.getenv("TG_USERNAME", "")))
    default_use_ssl  = bool(saved.get("use_ssl", True))
    default_password = str(saved.get("password", "")) if saved.get("save_password") else ""

    st.sidebar.image("https://www.tigergraph.com/wp-content/uploads/2023/01/TigerGraph_Logo_rgb.png", width=160)
    st.sidebar.markdown("---")

    st.sidebar.header("🔎 Search Controls")
    mode = st.sidebar.selectbox("Search Mode", list(SEARCH_MODES.keys()))
    mode_cfg = SEARCH_MODES[mode]

    example = st.sidebar.selectbox(
        "Example queries",
        ["(type your own below)"] + mode_cfg["example_queries"],
    )
    default_query = "" if example.startswith("(") else example
    query_text = st.sidebar.text_area(
        "Natural-language query",
        value=default_query,
        height=100,
        placeholder="Describe what you're looking for in plain English…",
    )
    top_k         = st.sidebar.slider("Top-K matches", 3, 20, 8)
    summary_limit = st.sidebar.slider("Context depth (per hop)", 5, 50, 15)

    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ TigerGraph Connection")
    host       = st.sidebar.text_input("Host URL", value=default_host)
    graph_name = st.sidebar.text_input("Graph name", value=default_graph)
    username   = st.sidebar.text_input("Username", value=default_username)
    password   = st.sidebar.text_input(
        "Secret (GraphStudio › Admin › Secrets)",
        type="password",
        value=default_password,
        help="A secret generated in TigerGraph GraphStudio — not your login password.",
    )
    use_ssl      = st.sidebar.checkbox("Use HTTPS", value=default_use_ssl)
    save_pwd     = st.sidebar.checkbox("Remember secret locally", value=bool(saved.get("save_password")),
                                        help="Stored in plain text — use on trusted machines only.")

    c1, c2 = st.sidebar.columns(2)
    if c1.button("💾 Save", use_container_width=True):
        save_connection({"host": host, "graph_name": graph_name, "username": username,
                         "use_ssl": use_ssl, "save_password": save_pwd,
                         "password": password if save_pwd else ""})
        st.sidebar.success("Saved.")
    if c2.button("🗑 Clear", use_container_width=True):
        clear_saved_connection()
        st.sidebar.success("Cleared.")

    return {
        "mode": mode, "mode_cfg": mode_cfg,
        "query_text": query_text, "top_k": top_k, "summary_limit": summary_limit,
        "host": host, "graph_name": graph_name, "username": username,
        "password": password, "use_ssl": use_ssl, "save_password": save_pwd,
        "remember_connection": bool(saved),
    }


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="Hybrid Search | Transaction Intelligence",
        page_icon="🔍",
        layout="wide",
    )

    st.markdown(
        """
        <h1 style='margin-bottom:0'>🔍 Hybrid Search</h1>
        <p style='color:#888;font-size:1.05rem;margin-top:4px'>
        Describe any pattern in plain English — TigerGraph finds semantically similar
        entities and expands the full graph context in a single query.
        </p>
        """,
        unsafe_allow_html=True,
    )

    config   = render_sidebar()
    mode_cfg = config["mode_cfg"]

    # ── Mode description banner ────────────────────────────────────────────
    st.info(f"**{config['mode']}** — {mode_cfg['description']}")

    # ── Search plan strip ──────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Vertex Type",     mode_cfg["vertex_type"])
    c2.metric("Vector Attribute", mode_cfg["vector_attribute"])
    c3.metric("Top-K",           config["top_k"])
    c4.metric("Context Depth",   config["summary_limit"])

    st.markdown("---")

    # ── Run button ─────────────────────────────────────────────────────────
    query_ready = bool(config["query_text"].strip() and config["password"].strip())
    run = st.button(
        "🚀 Run Hybrid Search",
        type="primary",
        use_container_width=True,
        disabled=not query_ready,
        help="Enter a query and your TigerGraph secret to run." if not query_ready else "",
    )

    if not query_ready and not run:
        st.markdown(
            """
            #### How to run
            1. Choose a **Search Mode** in the sidebar
            2. Select or type a **natural-language query**
            3. Enter your **TigerGraph secret** in the sidebar
            4. Click **Run Hybrid Search**
            """
        )
        return

    if run:
        # ── Embed query ────────────────────────────────────────────────────
        with st.spinner("Embedding your query…"):
            embedder     = QueryEmbedder(model_name=DEFAULT_MODEL)
            query_vector = embedder.encode_query(config["query_text"])

        # ── Connect ────────────────────────────────────────────────────────
        try:
            client = TigerGraphDemoClient(
                host=config["host"], graph_name=config["graph_name"],
                username=config["username"], password=config["password"],
                use_ssl=config["use_ssl"],
            )
        except Exception as e:
            st.error(f"Connection failed: {e}")
            return

        # ── Vector search ──────────────────────────────────────────────────
        with st.spinner(f"Vector search on `{mode_cfg['vertex_type']}.{mode_cfg['vector_attribute']}`…"):
            matches = client.search_top_k(
                vertex_type=mode_cfg["vertex_type"],
                vector_attribute=mode_cfg["vector_attribute"],
                query_vector=query_vector,
                top_k=int(config["top_k"]),
            )

        selected_ids = client.extract_ids(matches)

        if not selected_ids:
            st.warning("Vector search returned no matches. Check that embeddings are loaded into TigerGraph.")
            return

        # ── Graph context + summary ────────────────────────────────────────
        with st.spinner("Expanding graph context…"):
            context_payload = client.run_context_query(
                query_name=mode_cfg["context_query"],
                ids=selected_ids,
                limit=int(config["summary_limit"]),
            )
            summary_payload = client.run_summary_query(
                query_name=mode_cfg["summary_query"],
                ids=selected_ids,
            )

        ctx_results  = context_payload.get("results", []) if isinstance(context_payload, dict) else []
        summ_results = summary_payload.get("results", []) if isinstance(summary_payload, dict) else []

        ctx_missing  = isinstance(context_payload, dict) and context_payload.get("_missing")
        summ_missing = isinstance(summary_payload, dict) and summary_payload.get("_missing")

        # ── Results layout ─────────────────────────────────────────────────
        st.success(f"✅ Found **{len(selected_ids)}** semantic matches via vector search.")

        if ctx_missing or summ_missing:
            missing_queries = []
            if ctx_missing:
                missing_queries.append(f"`{mode_cfg['context_query']}`")
            if summ_missing:
                missing_queries.append(f"`{mode_cfg['summary_query']}`")
            st.warning(
                f"**Graph context queries not installed:** {', '.join(missing_queries)}\n\n"
                "Vector search results are shown below. To enable full graph context, install the queries "
                "from `gsql/query_pack.gsql` in GraphStudio › GSQL Editor, then run `INSTALL QUERY ALL`."
            )

        tab_exec, tab_txns, tab_merch, tab_users, tab_locs, tab_net, tab_raw = st.tabs([
            "📊 Executive Summary",
            "💳 Transactions",
            "🏪 Merchants",
            "👤 Users",
            "📍 Locations",
            "🕸️ Graph Network",
            "🔧 Raw JSON",
        ])

        with tab_exec:
            st.subheader("Executive Summary")
            st.caption(f"Query: _{config['query_text']}_")
            if summ_missing:
                st.info(
                    f"Summary query `{mode_cfg['summary_query']}` is not installed on TigerGraph. "
                    "Install queries from `gsql/query_pack.gsql` to see aggregated metrics here."
                )
            else:
                # Merge summary + context results so amount stats can always be
                # computed from vertex attributes even when histograms come from GSQL
                combined = summ_results + ctx_results
                render_summary_metrics(combined, config["mode"])

        with tab_txns:
            st.subheader("Matched Transactions")
            # Fall back to raw vector search results if context query is unavailable
            source = ctx_results if ctx_results else matches
            txn_df = extract_transactions(source)
            if not txn_df.empty:
                st.dataframe(txn_df, use_container_width=True, hide_index=True)
                label = "graph context" if ctx_results else "vector search matches (graph context query not installed)"
                st.caption(f"{len(txn_df)} transaction(s) from {label}")
            else:
                st.info("No transaction attributes returned — check that Transaction data is loaded.")

        with tab_merch:
            st.subheader("Connected Merchants")
            merch_df = extract_merchants(ctx_results)
            if ctx_missing:
                st.info(
                    f"Context query `{mode_cfg['context_query']}` is not installed. "
                    "Merchant graph context unavailable until queries are installed."
                )
            elif not merch_df.empty:
                st.dataframe(merch_df, use_container_width=True, hide_index=True)
                st.caption(f"{len(merch_df)} merchant(s) connected via graph hops")
            else:
                st.info("No merchant data in context — verify Merchant vertices and edges are loaded.")

        with tab_users:
            st.subheader("Connected Users")
            if ctx_missing:
                st.info(
                    f"Context query `{mode_cfg['context_query']}` is not installed. "
                    "User graph context unavailable until queries are installed."
                )
            else:
                user_df = extract_users(ctx_results)
                if not user_df.empty:
                    st.dataframe(user_df, use_container_width=True, hide_index=True)
                    st.caption(f"{len(user_df)} user(s) connected via graph hops")
                else:
                    st.info("No user data in context.")

        with tab_locs:
            st.subheader("Locations")
            if ctx_missing:
                st.info(
                    f"Context query `{mode_cfg['context_query']}` is not installed. "
                    "Location data unavailable until queries are installed."
                )
            else:
                loc_df = extract_locations(ctx_results)
                if not loc_df.empty:
                    st.dataframe(loc_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No location data in context.")

        with tab_net:
            st.subheader("Graph Context Network")
            st.caption("Interactive view of the entities and relationships returned by the graph traversal.")
            if ctx_missing:
                st.info(
                    f"Graph network requires context query `{mode_cfg['context_query']}` to be installed on TigerGraph. "
                    "Install queries from `gsql/query_pack.gsql` to enable this view."
                )
            elif ctx_results:
                try:
                    net_fig = graph_network_figure(ctx_results)
                    st.plotly_chart(net_fig, use_container_width=True)
                    st.caption(
                        "🟠 Transaction  🟢 Merchant  🔴 User  🔵 Location  🩵 DateTime  💙 MCC"
                    )
                except Exception as e:
                    st.warning(f"Could not render network graph: {e}")
            else:
                st.info("Run a search first to see the graph network.")

        with tab_raw:
            st.subheader("Raw API Responses")
            with st.expander("Vector Search Matches"):
                st.code(json.dumps(matches, indent=2, default=str), language="json")
            with st.expander("Graph Context"):
                st.code(json.dumps(context_payload, indent=2, default=str), language="json")
            with st.expander("Summary"):
                st.code(json.dumps(summary_payload, indent=2, default=str), language="json")
            with st.expander("Query Vector (first 32 dims)"):
                st.code(json.dumps(query_vector[:32], indent=2), language="json")
                st.caption(f"Full dimension: {len(query_vector)}")


# ── Landing page ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    st.set_page_config(
        page_title="Transaction Intelligence | TigerGraph",
        page_icon="⚡",
        layout="wide",
    )

    # ── Hero ──────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div style='padding:2.5rem 0 0.5rem 0'>
          <h1 style='font-size:3rem;font-weight:900;margin-bottom:0.3rem;letter-spacing:-1px'>
            ⚡ Transaction Intelligence
          </h1>
          <p style='font-size:1.25rem;color:#999;margin-top:0'>
            Vector Search &nbsp;·&nbsp; Graph Traversal &nbsp;·&nbsp; Neighbourhood Embeddings
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <p style='font-size:1rem;color:#bbb;max-width:780px;line-height:1.7'>
        A unified intelligence layer over transaction data — combining
        <strong>semantic vector search</strong> to find what you describe in plain English,
        and <strong>graph traversal</strong> to expand context across every connected merchant,
        user, and location. No SQL. No hardcoded rules. No labelled training data required.
        </p>
        """,
        unsafe_allow_html=True,
    )

    # ── Dataset stats strip ───────────────────────────────────────────────
    st.markdown("")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Transactions",        "5,000")
    m2.metric("Merchants",           "220")
    m3.metric("Users",               "848")
    m4.metric("Embedding Dimensions","384")
    m5.metric("Graph Edges",         "~11,000")

    st.markdown("---")

    # ── Capability cards ──────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3, gap="large")

    with c1:
        st.markdown(
            """
            <div style='background:#1a1f2e;border-radius:12px;padding:1.5rem;
                        border-left:4px solid #1753A4;height:100%'>
              <h3 style='margin-top:0;color:#6EA3FF'>🔍 Hybrid Search</h3>
              <p style='color:#ccc;font-size:0.95rem;line-height:1.65'>
                Describe any risk pattern or behaviour in plain English.
                TigerGraph finds the top matching transactions, merchants, or users
                via vector similarity — then expands the graph context across
                every connected entity in one query.
              </p>
              <p style='color:#888;font-size:0.85rem;margin-bottom:0'>
                Transaction Risk &nbsp;·&nbsp; Behaviour &nbsp;·&nbsp;
                Merchant &nbsp;·&nbsp; User Search
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            """
            <div style='background:#1a1f2e;border-radius:12px;padding:1.5rem;
                        border-left:4px solid #2E8B57;height:100%'>
              <h3 style='margin-top:0;color:#6EC98A'>🔬 Cluster Explorer</h3>
              <p style='color:#ccc;font-size:0.95rem;line-height:1.65'>
                Visualise 384-dimensional embeddings compressed into 2D by UMAP.
                Natural risk clusters emerge with no labels — every dot is a
                transaction, merchant, or user, coloured by their dominant
                risk or behaviour profile.
              </p>
              <p style='color:#888;font-size:0.85rem;margin-bottom:0'>
                5,000 transactions &nbsp;·&nbsp; 220 merchants &nbsp;·&nbsp; 848 users
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            """
            <div style='background:#1a1f2e;border-radius:12px;padding:1.5rem;
                        border-left:4px solid #8B45CC;height:100%'>
              <h3 style='margin-top:0;color:#C38EFF'>🧠 GraphSAGE Explorer</h3>
              <p style='color:#ccc;font-size:0.95rem;line-height:1.65'>
                See how Graph Neural Networks propagate risk signals across the
                network. A brand-new merchant with zero history is flagged on
                day one — because the graph already knows who its neighbours are.
              </p>
              <p style='color:#888;font-size:0.85rem;margin-bottom:0'>
                1-hop &nbsp;·&nbsp; 2-hop aggregation &nbsp;·&nbsp; Cold-start detection
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("")
    st.markdown("---")

    # ── What makes this different ─────────────────────────────────────────
    st.markdown("### What makes this different from traditional analytics")

    col_a, col_b = st.columns([1, 1], gap="large")
    with col_a:
        st.markdown(
            """
            | Capability | Rule Engine | SQL / BI | **This System** |
            |---|---|---|---|
            | Plain-English queries | ❌ | ❌ | ✅ |
            | Finds patterns not yet labelled | ❌ | ❌ | ✅ |
            | Traverses entity relationships | ⚠️ Hardcoded | ⚠️ Joins | ✅ Native |
            | Cold-start risk (new entity) | ❌ | ❌ | ✅ |
            | Explainable graph path | ❌ | ❌ | ✅ |
            | Setup time for new scenario | Days | Hours | **Seconds** |
            """
        )
    with col_b:
        st.markdown(
            """
            #### Architecture
            ```
            Natural-Language Query
                    │
                    ▼
            Sentence Transformer  ──▶  384-dim Vector
                    │
                    ▼
            TigerGraph HNSW Index  ──▶  Top-K Semantic Matches
                    │
                    ▼
            GSQL Graph Traversal  ──▶  Full Entity Context
                    │
                    ▼
            Executive Summary · Tables · Network Graph
            ```
            """
        )

    st.markdown("---")
    st.info("👈  Use the **sidebar navigation** to explore each capability.", icon="ℹ️")
