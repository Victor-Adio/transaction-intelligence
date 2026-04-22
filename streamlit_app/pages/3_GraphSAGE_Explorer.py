"""
GraphSAGE Explorer — Streamlit page.

Demonstrates GraphSAGE neighbourhood aggregation vs. text-only embeddings.
Embedding vectors are loaded from local CSV files:
  - merchant_embeddings.csv / user_embeddings.csv (committed to git)
  - transaction_embeddings_slim.csv (1000-sample, committed to git)
  - transaction_embeddings.csv (full 5000, local-only — if present, takes priority)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from services.graphsage_sim import (
    load_all_embeddings,
    load_graph_edges,
    compute_sage_merchant_embeddings,
    compute_sage_user_embeddings,
    inject_new_merchant,
    build_merchant_umap_df,
    build_2hop_umap,
    top_risk_transaction_ids,
    nearest_merchants,
    cosine_similarity,
)

ROOT = Path(__file__).resolve().parents[2]

st.set_page_config(
    page_title="GraphSAGE Explorer | Transaction Intelligence",
    page_icon="🧠",
    layout="wide",
)

# ── Header ──────────────────────────────────────────────────────────────────
st.markdown("""
<h1 style='margin-bottom:0'>🧠 GraphSAGE Explorer</h1>
<p style='color:#aaa;font-size:1.05rem;margin-top:4px'>
Graph Neural Network aggregation — neighbourhood-aware embeddings vs. text-only embeddings.
</p>
""", unsafe_allow_html=True)

st.info(
    "**What GraphSAGE does:** Instead of representing a merchant by its own description alone, "
    "GraphSAGE aggregates the embeddings of every connected transaction and user. "
    "A brand-new merchant with no fraud history is immediately enriched by the risk signals "
    "of the entities already linked to it in the graph."
)

# ── Sidebar controls ────────────────────────────────────────────────────────
st.sidebar.header("🧠 GraphSAGE Settings")
alpha = st.sidebar.slider(
    "Self-weight α", 0.1, 0.9, 0.5, step=0.05,
    help="α × own embedding + (1-α) × mean(neighbour embeddings). "
         "Lower α = more neighbourhood influence.",
)
n_neighbors = st.sidebar.slider("UMAP n_neighbors", 5, 30, 10)
min_dist    = st.sidebar.slider("UMAP min_dist", 0.01, 0.5, 0.15, step=0.01)
top_risk_n  = st.sidebar.slider(
    "Risk transactions injected to new merchant", 3, 20, 8,
    help="How many high-risk transaction embeddings are connected to the synthetic new merchant.",
)
st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    **Reading the plots:**
    - Each dot = one merchant / user
    - Position = semantic similarity (closer = more alike)
    - ⭐ Yellow star = synthetic new merchant
    - Left panel: text-only embedding (no graph)
    - Right panel: GraphSAGE-aggregated (graph-aware)
    """
)

# ── TigerGraph client (fallback when CSVs absent) ───────────────────────────
@st.cache_resource(show_spinner=False)
def _get_tg_client():
    from services.connection import get_tg_client
    return get_tg_client()


# ── Load data (cached across rerenders) ─────────────────────────────────────
@st.cache_data(show_spinner=False)
def _load_data():
    tg = _get_tg_client()
    txn_risk, txn_beh, merch, user = load_all_embeddings(tg_client=tg)
    txn_to_merch, txn_to_user, merch_to_txn, user_to_txn = load_graph_edges()
    meta_merch = pd.read_csv(ROOT / "data" / "embedding_prep_merchants.csv", dtype=str)
    meta_user  = pd.read_csv(ROOT / "data" / "embedding_prep_users.csv",  dtype=str)
    return txn_risk, txn_beh, merch, user, txn_to_merch, txn_to_user, merch_to_txn, user_to_txn, meta_merch, meta_user


with st.spinner("Loading embeddings and graph edges…"):
    (txn_risk, txn_beh, merch_embs, user_embs,
     txn_to_merch, txn_to_user, merch_to_txn, user_to_txn,
     meta_merch, meta_user) = _load_data()

# ── Guard: stop if merchant/user embeddings missing ─────────────────────────
if not merch_embs or not user_embs:
    st.error(
        "**Merchant or user embedding files not found.** "
        "Ensure `data/merchant_embeddings.csv` and `data/user_embeddings.csv` exist in the repo.",
        icon="❌",
    )
    st.stop()

txn_available = bool(txn_risk)
_tg = _get_tg_client()
_source_label = f"TigerGraph (`{_tg.host}`)" if _tg else "local CSV files"

st.success(
    f"Loaded **{len(merch_embs):,}** merchant · "
    f"**{len(user_embs):,}** user · "
    f"**{len(txn_risk):,}** transaction embeddings  "
    f"from **{_source_label}**  |  "
    f"**{sum(len(v) for v in merch_to_txn.values()):,}** merchant–transaction edges"
)
if not txn_available:
    st.warning(
        "Transaction embeddings could not be loaded from TigerGraph or local CSV. "
        "Merchant and User cluster tabs still work. "
        "For Cold-Start, 2-Hop, and Similarity Probe: ensure TigerGraph credentials "
        "are saved in the **Hybrid Search** sidebar and the export queries are installed.",
        icon="⚠️",
    )

# ── Module-level helpers (avoid redefining inside with-blocks) ──────────────
_meta_idx = meta_merch.set_index("merchant_id") if "merchant_id" in meta_merch.columns else pd.DataFrame()


def _nn_df(nn: list[tuple[str, float]]) -> pd.DataFrame:
    """Format nearest-neighbour results as a DataFrame for display."""
    rows = []
    for mid, sim in nn:
        def _get(col: str, default: str = "—") -> str:
            if not _meta_idx.empty and mid in _meta_idx.index and col in _meta_idx.columns:
                return str(_meta_idx.at[mid, col])
            return default
        rows.append({
            "Merchant":   _get("merchant_name", mid),
            "City":       _get("merchant_city"),
            "Category":   _get("merchant_category_text"),
            "Similarity": round(sim, 4),
        })
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def _cached_2hop(alpha: float, n_neighbors: int, min_dist: float):
    return build_2hop_umap(
        merch_embs, user_embs, txn_risk,
        merch_to_txn, txn_to_user, user_to_txn,
        alpha, n_neighbors, min_dist,
    )


# ── Tabs ────────────────────────────────────────────────────────────────────
tab_merch, tab_user, tab_cold, tab_2hop, tab_explain = st.tabs([
    "🏪 Merchant Clusters",
    "👤 User Clusters",
    "⭐ Cold-Start Demo",
    "🔗 2-Hop Aggregation",
    "📖 How It Works",
])


# ═══════════════════════════════════════════════════════════════════════════
# TAB 1 — MERCHANT CLUSTERS
# ═══════════════════════════════════════════════════════════════════════════
with tab_merch:
    st.subheader("Merchant Embeddings: Text-only vs. GraphSAGE")
    st.caption(
        "Left: each merchant placed by its own text summary only. "
        "Right: each merchant repositioned after absorbing its connected transactions' signals."
    )

    if txn_available:
        with st.spinner("Computing GraphSAGE merchant embeddings + UMAP (~20 s first run)…"):
            sage_merch = compute_sage_merchant_embeddings(
                merch_embs, txn_risk, merch_to_txn, alpha=alpha
            )
            orig_df, sage_df = build_merchant_umap_df(
                merch_embs, sage_merch, meta_merch,
                n_neighbors=n_neighbors, min_dist=min_dist,
            )
    else:
        # Without transaction embeddings, GraphSAGE == text-only.
        # Show text-only UMAP only, with a clear note.
        st.info(
            "Transaction embeddings not loaded — showing text-only merchant clusters. "
            "The GraphSAGE view requires transaction data.",
            icon="ℹ️",
        )
        with st.spinner("Computing merchant UMAP (text-only)…"):
            sage_merch = merch_embs  # no aggregation
            orig_df, _ = build_merchant_umap_df(
                merch_embs, sage_merch, meta_merch,
                n_neighbors=n_neighbors, min_dist=min_dist,
            )
        sage_df = orig_df.copy()

    colour_col = "category" if "category" in orig_df.columns else None
    palette    = px.colors.qualitative.Bold

    col_a, col_b = st.columns(2)

    with col_a:
        fig_orig = px.scatter(
            orig_df, x="x", y="y", color=colour_col,
            hover_name="entity_id",
            hover_data={k: True for k in ["category", "region"] if k in orig_df.columns},
            color_discrete_sequence=palette,
            title="Text-only Embedding",
            labels={"x": "UMAP-1", "y": "UMAP-2"},
            template="plotly_dark", opacity=0.80,
        )
        fig_orig.update_traces(marker_size=9)
        fig_orig.update_layout(height=460, showlegend=False)
        st.plotly_chart(fig_orig, use_container_width=True)

    with col_b:
        if txn_available:
            fig_sage = px.scatter(
                sage_df, x="x", y="y", color=colour_col,
                hover_name="entity_id",
                hover_data={k: True for k in ["category", "region"] if k in sage_df.columns},
                color_discrete_sequence=palette,
                title=f"GraphSAGE (α={alpha})",
                labels={"x": "UMAP-1", "y": "UMAP-2"},
                template="plotly_dark", opacity=0.80,
            )
            fig_sage.update_traces(marker_size=9)
            fig_sage.update_layout(height=460, showlegend=True, legend_title_text="Category")
            st.plotly_chart(fig_sage, use_container_width=True)
        else:
            st.caption("GraphSAGE view unavailable — transaction embeddings not loaded.")

    st.markdown(
        "**What to look for:** tighter within-category clusters in the GraphSAGE view — "
        "merchants that process similar transactions are pulled together even if their text descriptions differ."
    )


# ═══════════════════════════════════════════════════════════════════════════
# TAB 2 — USER CLUSTERS
# ═══════════════════════════════════════════════════════════════════════════
with tab_user:
    st.subheader("User Embeddings: Text-only vs. GraphSAGE")

    with st.spinner("Computing GraphSAGE user embeddings + UMAP (~20 s first run)…"):
        sage_user = compute_sage_user_embeddings(
            user_embs, txn_risk if txn_available else {}, user_to_txn, alpha=alpha
        )
        from umap import UMAP

        u_ids    = sorted(user_embs.keys())
        orig_u   = np.array([user_embs[i] for i in u_ids], dtype=np.float32)
        sage_u   = np.array([sage_user[i] for i in u_ids], dtype=np.float32)
        combined = np.vstack([orig_u, sage_u])
        coords   = UMAP(n_components=2, n_neighbors=n_neighbors,
                        min_dist=min_dist, random_state=42,
                        low_memory=True).fit_transform(combined)
        n = len(u_ids)
        oc, sc = coords[:n], coords[n:]

        meta_u = meta_user.set_index("userid") if "userid" in meta_user.columns else pd.DataFrame()

        def _udf(c: np.ndarray, label: str) -> pd.DataFrame:
            rows = []
            for i, uid in enumerate(u_ids):
                row = {"entity_id": uid, "x": float(c[i, 0]), "y": float(c[i, 1]), "source": label}
                if not meta_u.empty and uid in meta_u.index:
                    row["region"]   = meta_u.at[uid, "dominant_region"]       if "dominant_region"       in meta_u.columns else ""
                    row["spend"]    = meta_u.at[uid, "spend_profile"]          if "spend_profile"          in meta_u.columns else ""
                    row["category"] = meta_u.at[uid, "favorite_category_text"] if "favorite_category_text" in meta_u.columns else ""
                rows.append(row)
            return pd.DataFrame(rows)

        orig_udf = _udf(oc, "Text-only")
        sage_udf = _udf(sc, "GraphSAGE")

    if not txn_available:
        st.info(
            "Transaction embeddings not loaded — GraphSAGE view will look similar to text-only. "
            "Run locally with the full dataset for meaningful comparison.",
            icon="ℹ️",
        )

    col_a, col_b = st.columns(2)
    hcols = {k: True for k in ["region", "spend", "category"] if k in orig_udf.columns}

    with col_a:
        fig_ou = px.scatter(
            orig_udf, x="x", y="y",
            color="region" if "region" in orig_udf.columns else None,
            hover_name="entity_id", hover_data=hcols,
            color_discrete_sequence=px.colors.qualitative.Bold,
            title="Text-only Embedding", labels={"x": "UMAP-1", "y": "UMAP-2"},
            template="plotly_dark", opacity=0.75,
        )
        fig_ou.update_traces(marker_size=7)
        fig_ou.update_layout(height=460, showlegend=False)
        st.plotly_chart(fig_ou, use_container_width=True)

    with col_b:
        fig_su = px.scatter(
            sage_udf, x="x", y="y",
            color="region" if "region" in sage_udf.columns else None,
            hover_name="entity_id", hover_data=hcols,
            color_discrete_sequence=px.colors.qualitative.Bold,
            title=f"GraphSAGE (α={alpha})", labels={"x": "UMAP-1", "y": "UMAP-2"},
            template="plotly_dark", opacity=0.75,
        )
        fig_su.update_traces(marker_size=7)
        fig_su.update_layout(height=460, legend_title_text="Region")
        st.plotly_chart(fig_su, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════
# TAB 3 — COLD-START DEMO
# ═══════════════════════════════════════════════════════════════════════════
with tab_cold:
    st.subheader("⭐ Cold-Start: The New Merchant Demo")

    if not txn_available:
        st.info(
            "This demo injects a new merchant connected to high-risk transactions to show "
            "how GraphSAGE propagates risk on day one — even with zero transaction history. "
            "\n\nTransaction embeddings are required to run this. Run locally with the full dataset.",
            icon="ℹ️",
        )
    else:
        st.markdown(
            """
            We inject a **brand-new merchant** with:
            - ✗ Zero transaction history of its own
            - ✗ No fraud labels
            - ✓ Connected to the **top high-risk transactions** in the graph

            **Without GraphSAGE:** the new merchant has a random embedding — it looks neutral.  
            **With GraphSAGE:** the new merchant *inherits the risk signal* from its connected transactions
            and lands near other high-risk merchants in the embedding space.
            """
        )

        risk_txn_ids = top_risk_transaction_ids(txn_risk, top_n=top_risk_n)
        new_orig, new_sage = inject_new_merchant(
            merch_embs, txn_risk, risk_txn_ids,
            new_id="NEW_MERCHANT_⚠️", alpha=alpha,
        )

        st.markdown(f"**Injected merchant connected to:** `{len(risk_txn_ids)}` high-risk transactions")

        with st.spinner("Building UMAP with injected merchant (~20 s)…"):
            sage_merch_cs = compute_sage_merchant_embeddings(
                merch_embs, txn_risk, merch_to_txn, alpha=alpha
            )
            new_merchant_tuple = ("NEW_MERCHANT_⚠️", new_orig, new_sage)
            orig_cs, sage_cs = build_merchant_umap_df(
                merch_embs, sage_merch_cs, meta_merch,
                n_neighbors=n_neighbors, min_dist=min_dist,
                new_merchant=new_merchant_tuple,
            )

        def _add_star(fig: go.Figure, df: pd.DataFrame) -> go.Figure:
            star = df[df["entity_id"] == "NEW_MERCHANT_⚠️"]
            if not star.empty:
                fig.add_trace(go.Scatter(
                    x=star["x"], y=star["y"],
                    mode="markers+text",
                    text=["NEW MERCHANT ⚠️"],
                    textposition="top right",
                    textfont=dict(size=11, color="yellow"),
                    marker=dict(size=22, color="yellow", symbol="star",
                                line=dict(color="black", width=2)),
                    name="New Merchant",
                    showlegend=True,
                ))
            return fig

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Without GraphSAGE")
            st.caption("New merchant has no history → random embedding → looks harmless")
            fig_o = px.scatter(
                orig_cs[orig_cs["entity_id"] != "NEW_MERCHANT_⚠️"],
                x="x", y="y", color="category",
                hover_name="entity_id",
                color_discrete_sequence=px.colors.qualitative.Bold,
                template="plotly_dark", opacity=0.65,
                labels={"x": "UMAP-1", "y": "UMAP-2"},
            )
            fig_o.update_traces(marker_size=8)
            fig_o = _add_star(fig_o, orig_cs)
            fig_o.update_layout(height=500, showlegend=False,
                                 title="Text-only: New merchant appears neutral")
            st.plotly_chart(fig_o, use_container_width=True)

        with c2:
            st.markdown("#### With GraphSAGE")
            st.caption("New merchant absorbs risk signal from neighbours → lands in danger zone")
            fig_s = px.scatter(
                sage_cs[sage_cs["entity_id"] != "NEW_MERCHANT_⚠️"],
                x="x", y="y", color="category",
                hover_name="entity_id",
                color_discrete_sequence=px.colors.qualitative.Bold,
                template="plotly_dark", opacity=0.65,
                labels={"x": "UMAP-1", "y": "UMAP-2"},
            )
            fig_s.update_traces(marker_size=8)
            fig_s = _add_star(fig_s, sage_cs)
            fig_s.update_layout(height=500, legend_title_text="Category",
                                 title=f"GraphSAGE: New merchant pulled toward risk cluster (α={alpha})")
            st.plotly_chart(fig_s, use_container_width=True)

        st.markdown("---")
        st.subheader("Nearest Merchants: Before vs. After")
        st.caption("Which merchants does the new one look most like?")

        nn_orig = nearest_merchants(new_orig, merch_embs, top_n=5)
        nn_sage = nearest_merchants(new_sage, merch_embs, top_n=5)

        col_nn1, col_nn2 = st.columns(2)
        with col_nn1:
            st.markdown("**Without GraphSAGE** (text-only neighbours)")
            st.dataframe(_nn_df(nn_orig), use_container_width=True, hide_index=True)
            st.caption("Random position → neighbours are arbitrary")
        with col_nn2:
            st.markdown("**With GraphSAGE** (graph-aware neighbours)")
            st.dataframe(_nn_df(nn_sage), use_container_width=True, hide_index=True)
            st.caption("Positioned by risk context → neighbours share similar risk profile")

        st.success(
            "🎯 **Management punchline:** This new merchant has zero transactions. "
            "No rule engine would flag it. But its graph connections scream high risk. "
            "GraphSAGE catches it **on day one**."
        )


# ═══════════════════════════════════════════════════════════════════════════
# TAB 4 — 2-HOP AGGREGATION
# ═══════════════════════════════════════════════════════════════════════════
with tab_2hop:
    st.subheader("🔗 2-Hop Aggregation: Merchant ← Transaction ← User")
    st.markdown(
        """
        **1-hop** (current default): Each merchant absorbs signals from its own transactions.  
        **2-hop** (this tab): Each merchant absorbs signals from the *users* behind those transactions —
        after those users have already absorbed *their* transaction signals.

        This means a merchant that serves high-risk users inherits *all of that user's behavioural
        history across every other merchant they've visited* — not just the single transaction.
        Fraud rings and shared mule accounts become visible through this second layer of propagation.
        """
    )

    if not txn_available:
        st.info(
            "Transaction embeddings are required for 2-Hop Aggregation. "
            "Run locally with the full dataset to see this view.",
            icon="ℹ️",
        )
    else:
        with st.spinner("Computing 1-hop and 2-hop embeddings + UMAP (~30 s first run)…"):
            ids_2h, c_orig, c_1h, c_2h, sage_1h, sage_2h = _cached_2hop(alpha, n_neighbors, min_dist)

        meta_2h = meta_merch.set_index("merchant_id") if "merchant_id" in meta_merch.columns else pd.DataFrame()

        def _hop_df(coords: np.ndarray, label: str) -> pd.DataFrame:
            rows = []
            for i, mid in enumerate(ids_2h):
                row = {"entity_id": mid, "x": float(coords[i, 0]), "y": float(coords[i, 1]), "hop": label}
                if not meta_2h.empty and mid in meta_2h.index:
                    row["category"] = meta_2h.at[mid, "merchant_category_text"] if "merchant_category_text" in meta_2h.columns else ""
                    row["name"]     = meta_2h.at[mid, "merchant_name"]           if "merchant_name"           in meta_2h.columns else mid
                else:
                    row["category"] = ""
                    row["name"]     = mid
                rows.append(row)
            return pd.DataFrame(rows)

        df_o2 = _hop_df(c_orig, "Text-only")
        df_1h = _hop_df(c_1h,  "1-Hop (Txn→Merch)")
        df_2h = _hop_df(c_2h,  "2-Hop (Txn→User→Merch)")

        col1, col2, col3 = st.columns(3)
        for col, df, title in [
            (col1, df_o2, "Text-only"),
            (col2, df_1h, "1-Hop (Txn→Merch)"),
            (col3, df_2h, "2-Hop (Txn→User→Merch)"),
        ]:
            with col:
                fig = px.scatter(
                    df, x="x", y="y", color="category",
                    hover_name="name",
                    hover_data={"entity_id": True, "category": True},
                    color_discrete_sequence=px.colors.qualitative.Bold,
                    title=title,
                    labels={"x": "UMAP-1", "y": "UMAP-2"},
                    template="plotly_dark", opacity=0.80,
                )
                fig.update_traces(marker_size=8)
                fig.update_layout(height=420, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

        st.markdown(
            "**What to look for:** clusters tighten further in 2-hop — merchants serving "
            "similar *user profiles* are pulled together, not just merchants sharing transactions."
        )

        st.markdown("---")
        st.subheader("Embedding Shift: 1-Hop vs 2-Hop")
        st.caption("How much does each merchant's position change when we add the second aggregation layer?")

        shifts = []
        for mid in ids_2h:
            s1   = float(np.linalg.norm(sage_1h[mid] - merch_embs[mid]))
            s2   = float(np.linalg.norm(sage_2h[mid] - merch_embs[mid]))
            name = meta_2h.at[mid, "merchant_name"] if (not meta_2h.empty and mid in meta_2h.index and "merchant_name" in meta_2h.columns) else mid
            cat  = meta_2h.at[mid, "merchant_category_text"] if (not meta_2h.empty and mid in meta_2h.index and "merchant_category_text" in meta_2h.columns) else ""
            shifts.append({
                "Merchant": name, "Category": cat,
                "Shift (1-hop)": round(s1, 4), "Shift (2-hop)": round(s2, 4),
                "Δ (2-hop − 1-hop)": round(s2 - s1, 4),
            })

        shift_df = pd.DataFrame(shifts).sort_values("Δ (2-hop − 1-hop)", ascending=False)
        st.dataframe(shift_df.head(20), use_container_width=True, hide_index=True)
        st.caption(
            "Merchants with large Δ are most influenced by user-level risk propagation "
            "beyond what their own transactions reveal."
        )


# ═══════════════════════════════════════════════════════════════════════════
# TAB 5 — HOW IT WORKS + LIVE SIMILARITY PROBE
# ═══════════════════════════════════════════════════════════════════════════
with tab_explain:
    st.subheader("How GraphSAGE Works")

    col_a, col_b = st.columns([1, 1])

    with col_a:
        st.markdown(
            """
            #### The Core Idea

            A standard embedding represents each node from its own attributes alone:
            > *"This merchant sells electronics in Singapore."*

            GraphSAGE represents each node **through its neighbourhood as well**:
            > *"This merchant sells electronics in Singapore — and the majority of
            > users who transact here share patterns with high-risk profiles across
            > the network."*

            The second representation carries vastly more signal for risk and anomaly detection.

            ---

            #### The Aggregation Formula

            ```
            h_merchant = normalise(
                α × own_embedding
              + (1-α) × mean( embeddings of connected transactions )
            )
            ```

            | Parameter | Effect |
            |---|---|
            | **α → 1.0** | Pure text — ignores the graph |
            | **α = 0.5** | Equal weight: own signal + neighbourhood |
            | **α → 0.1** | Neighbourhood-dominant — graph drives the result |

            Adjust **Self-weight α** in the sidebar to see the effect live across all tabs.
            """
        )

    with col_b:
        st.markdown("#### Detection Comparison by Method")

        data = {
            "Scenario": [
                "Known fraudster transacts at new merchant",
                "Fraud ring shares a single merchant",
                "New card at a high-risk location",
                "User with clean history alters behaviour",
                "Dormant account suddenly activated",
            ],
            "Rule Engine":     ["❌ Misses",   "⚠️ Possible", "⚠️ Possible", "❌ Misses",   "❌ Misses"],
            "Text Embedding":  ["❌ Misses",   "❌ Misses",   "⚠️ Possible", "⚠️ Possible", "❌ Misses"],
            "GraphSAGE":       ["✅ Catches",  "✅ Catches",  "✅ Catches",  "✅ Catches",  "✅ Catches"],
        }
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

        st.markdown(
            """
            ---
            #### Why the graph changes everything

            Rule engines act on what is known today. Text embeddings surface semantic
            similarity but cannot see relationships.

            GraphSAGE propagates risk through connected entities — a new merchant
            inherits the risk profile of every transaction and user already linked
            to it in the graph, before a single fraud case is confirmed against it.

            The 2-Hop tab demonstrates the second layer: user-level behavioural
            history flows back through transactions and reaches the merchant,
            exposing shared mule accounts and fraud rings that no single hop can see.
            """
        )

    st.markdown("---")
    st.subheader("🔬 Live Similarity Probe")
    st.caption("Pick any merchant and see how its nearest neighbours change with GraphSAGE.")

    if not txn_available:
        st.info(
            "The Similarity Probe needs transaction embeddings to compute meaningful GraphSAGE "
            "representations. Without them, text-only and GraphSAGE views are identical. "
            "Run locally with the full dataset to see differentiated results.",
            icon="ℹ️",
        )
    else:
        sage_merch_probe = compute_sage_merchant_embeddings(
            merch_embs, txn_risk, merch_to_txn, alpha=alpha
        )
        merchant_list = sorted(merch_embs.keys())

        probe_meta = _meta_idx

        def _label(mid: str) -> str:
            if not probe_meta.empty and mid in probe_meta.index and "merchant_name" in probe_meta.columns:
                return f"{probe_meta.at[mid, 'merchant_name']}  ({mid})"
            return mid

        label_to_id  = {_label(mid): mid for mid in merchant_list}
        chosen_label = st.selectbox("Select a merchant", sorted(label_to_id.keys()))
        chosen       = label_to_id.get(chosen_label, "")

        if chosen:
            cc1, cc2 = st.columns(2)

            nn_o = nearest_merchants(merch_embs[chosen],       merch_embs,       top_n=6)
            nn_s = nearest_merchants(sage_merch_probe[chosen], sage_merch_probe, top_n=6)
            nn_o = [(m, s) for m, s in nn_o if m != chosen][:5]
            nn_s = [(m, s) for m, s in nn_s if m != chosen][:5]

            st.caption(f"Selected: **{_label(chosen)}**")

            with cc1:
                st.markdown("**Text-only neighbours**")
                st.dataframe(_nn_df(nn_o), use_container_width=True, hide_index=True)
            with cc2:
                st.markdown(f"**GraphSAGE neighbours (α={alpha})**")
                st.dataframe(_nn_df(nn_s), use_container_width=True, hide_index=True)

            orig_e = merch_embs[chosen]
            sage_e = sage_merch_probe[chosen]
            shift  = float(np.linalg.norm(orig_e - sage_e))
            sim    = cosine_similarity(orig_e, sage_e)
            st.metric("Embedding shift (L2 distance)", f"{shift:.4f}",
                       help="How much the embedding moved after neighbourhood aggregation")
            st.metric("Self-similarity before vs. after", f"{sim:.4f}",
                       help="1.0 = no change, lower = more neighbourhood influence")
