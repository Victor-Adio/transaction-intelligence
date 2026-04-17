"""
Cluster Explorer — 2-D UMAP projections of all embeddings.
Loads embedding vectors from local CSV files when available,
or fetches them live from TigerGraph when CSVs are absent.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st
from services.connection import get_tg_client
from services.cluster_viz import (
    transaction_cluster_figure,
    merchant_cluster_figure,
    user_cluster_figure,
)

st.set_page_config(
    page_title="Cluster Explorer | Transaction Intelligence",
    page_icon="🔬",
    layout="wide",
)

st.markdown("""
<h1 style='margin-bottom:0'>🔬 Embedding Cluster Explorer</h1>
<p style='color:#aaa;font-size:1.05rem;margin-top:4px'>
2-D projections of 384-dimensional semantic embeddings.
Proximity reflects similarity — clusters emerge with zero labels.
</p>
""", unsafe_allow_html=True)

st.markdown(
    """
    <p style='font-size:0.95rem;color:#bbb;max-width:820px;line-height:1.7'>
    Every transaction, merchant, and user was encoded into a 384-dimensional vector
    capturing semantic meaning — amount patterns, geography, channel, category, and
    time-of-day signals. UMAP compresses these into two dimensions for visualisation
    while preserving neighbourhood relationships. What you see below is what the model
    <em>learned automatically</em>, with no fraud labels.
    </p>
    """,
    unsafe_allow_html=True,
)

st.markdown("---")

# ── Controls ───────────────────────────────────────────────────────────────
col_ctl, col_exp = st.columns([2, 1])
with col_ctl:
    entity = st.radio(
        "Select entity to visualise",
        ["🔴 Transaction Risk", "🟡 Transaction Behaviour", "🟢 Merchants", "🔵 Users"],
        horizontal=True,
    )

with col_exp:
    with st.expander("⚙️ UMAP parameters", expanded=False):
        n_neighbors = st.slider("n_neighbors", 5, 50, 15,
                                 help="Controls how many neighbours are considered "
                                      "when building the graph — higher = more global structure.")
        min_dist    = st.slider("min_dist", 0.01, 0.5, 0.1, step=0.01,
                                 help="Controls how tightly points are packed — "
                                      "lower = tighter clusters.")
        sample_n    = st.slider("Sample size (transactions)", 200, 5000, 2000, step=200,
                                 help="Number of transactions to project. "
                                      "Lower = faster render.")

st.markdown("---")

# ── Build TigerGraph client (used as fallback when CSVs are absent) ─────────
@st.cache_resource(show_spinner=False)
def _get_tg_client():
    return get_tg_client()

tg_client = _get_tg_client()

# ── Connection diagnostics ───────────────────────────────────────────────────
with st.expander("🔌 TigerGraph connection status", expanded=tg_client is None):
    if tg_client is None:
        from services.connection import load_saved_connection
        cfg = load_saved_connection()
        st.error("**TigerGraph client could not be built.**")
        st.markdown(f"- Host detected: `{cfg.get('host', 'not found')}`")
        st.markdown(f"- Graph: `{cfg.get('graph_name', 'not found')}`")
        st.markdown(f"- Secret present: `{'yes' if cfg.get('password') else 'NO — this is the problem'}`")
        st.markdown(
            "**Fix:** Go to Streamlit Cloud → your app → ⋮ → Settings → Secrets "
            "and make sure `[tigergraph]` section is filled in with `host`, `graph_name`, `username`, `secret`, `use_ssl`."
        )
    else:
        ping = tg_client.ping()
        if ping["ok"]:
            st.success(f"Connected to `{tg_client.host}` / graph `{tg_client.graphname}`")
            st.markdown(f"- Sample vertex ID: `{ping['vertex_id']}`")
            st.markdown(f"- Attributes returned: `{ping['attribute_keys']}`")
            if ping["has_embedding"]:
                st.success("✅ `embedding` vector attribute is visible — embeddings will be fetched from TigerGraph.")
            else:
                st.warning(
                    "⚠️ `embedding` attribute **not returned** by the REST++ vertex endpoint. "
                    "TigerGraph may not expose VECTOR attributes via `/restpp/graph/.../vertices`. "
                    "You may need to run the embedding generation scripts locally."
                )
        else:
            st.error(f"Connection failed: `{ping['error']}`")

# ── Render ──────────────────────────────────────────────────────────────────
with st.spinner("Computing UMAP projection… first run ~20 seconds"):
    try:
        if entity.startswith("🔴"):
            fig = transaction_cluster_figure("transaction_text_risk",     n_neighbors, min_dist, sample_n, tg_client=tg_client)
        elif entity.startswith("🟡"):
            fig = transaction_cluster_figure("transaction_text_behavior", n_neighbors, min_dist, sample_n, tg_client=tg_client)
        elif entity.startswith("🟢"):
            fig = merchant_cluster_figure(n_neighbors, min_dist, tg_client=tg_client)
        else:
            fig = user_cluster_figure(n_neighbors, min_dist, tg_client=tg_client)
        st.plotly_chart(fig, use_container_width=True)
    except FileNotFoundError as e:
        st.warning(
            "**Embedding file not found — and TigerGraph connection unavailable.**\n\n"
            "To fix this either:\n"
            "- Run `python scripts/generate_transaction_embeddings.py` locally, or\n"
            "- Enter your TigerGraph credentials in the **Hybrid Search** sidebar and click Save — "
            "embeddings will be fetched live from TigerGraph on next load.",
            icon="⚠️",
        )
    except Exception as e:
        st.error(f"Error generating cluster plot: {e}")

st.markdown("---")

st.markdown("#### How to read this chart")
r1, r2 = st.columns(2)
with r1:
    st.markdown(
        """
        | Visual Signal | What it means |
        |---|---|
        | **Nearby dots** | Similar semantic profile — same risk level, category, or region |
        | **Dense cluster** | Strong natural grouping the model discovered without labels |
        | **Isolated dot** | Unusual or anomalous entity — warrants investigation |
        | **Colour** | Amount band / MCC category / region (see legend) |
        | **Hover** | Shows entity ID and key attributes |
        """
    )
with r2:
    st.markdown(
        """
        #### Why this matters

        This chart is the visual proof that the embeddings capture **meaningful structure**
        without any labelling effort.

        When Hybrid Search finds "the top 8 matches to this query", it is navigating
        this exact geometry — finding the nearest neighbours in 384 dimensions and
        returning them in milliseconds via TigerGraph's HNSW index.

        A cluster of high-risk merchants here corresponds directly to a vector region
        that the search will surface when you describe similar patterns in Hybrid Search.
        """
    )
