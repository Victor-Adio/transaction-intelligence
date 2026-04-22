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

# ── TigerGraph client — primary source via WITH VECTOR ──────────────────────
@st.cache_resource(show_spinner=False)
def _get_tg_client():
    return get_tg_client()

tg_client = _get_tg_client()

# ── Data source banner ───────────────────────────────────────────────────────
_DATA_ROOT = Path(__file__).resolve().parents[2] / "data"

if tg_client is not None:
    st.success(
        f"**Live TigerGraph** · `{tg_client.host}` — "
        "embeddings will be fetched from TigerGraph using `PRINT … WITH VECTOR`.",
        icon="🔗",
    )
else:
    # Identify which CSV fallbacks are available
    _merch_csv = _DATA_ROOT / "merchant_embeddings.csv"
    _user_csv  = _DATA_ROOT / "user_embeddings.csv"
    _txn_ok    = (_DATA_ROOT / "transaction_embeddings.csv").exists() or \
                 (_DATA_ROOT / "transaction_embeddings_slim.csv").exists()
    missing = []
    if not _merch_csv.exists(): missing.append("merchant")
    if not _user_csv.exists():  missing.append("user")
    if not _txn_ok:             missing.append("transaction")
    if missing:
        st.warning(
            f"TigerGraph not connected and local CSV files missing for: **{', '.join(missing)}**. "
            "Enter credentials in the **Hybrid Search** sidebar and click Save to connect.",
            icon="⚠️",
        )
    else:
        st.info(
            "TigerGraph not connected — using pre-computed embedding CSV files. "
            "Enter credentials in the **Hybrid Search** sidebar to switch to live data.",
            icon="ℹ️",
        )

# ── Render ───────────────────────────────────────────────────────────────────
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
        st.error(
            f"**Embedding file not found:** {e}\n\n"
            "Ensure all required embedding CSVs are committed to the repository.",
            icon="❌",
        )
    except Exception as e:
        st.error(f"Error generating cluster plot: {e}", icon="❌")

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
