"""
Cluster visualisation service.

Loads local embedding CSVs, reduces them to 2-D with UMAP, and
returns Plotly figures ready to be rendered in Streamlit.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[2]

_PALETTE = px.colors.qualitative.Bold

NODE_COLOURS = {
    "Transaction":          "#F4A261",
    "Merchant":             "#2A9D8F",
    "User":                 "#E76F51",
    "Location":             "#264653",
    "Transaction_DateTime": "#A8DADC",
    "MCC_Code":             "#457B9D",
}

# ── Helpers ────────────────────────────────────────────────────────────────

def _parse_vector(v: str) -> Optional[list[float]]:
    try:
        return json.loads(v)
    except Exception:
        return None


def _amount_band(amount: float) -> str:
    if amount < 50:    return "Micro (<50)"
    if amount < 200:   return "Small (50–200)"
    if amount < 1000:  return "Medium (200–1k)"
    if amount < 5000:  return "Large (1k–5k)"
    return "Premium (5k+)"


def load_embeddings(csv_path: Path, id_col: str,
                    text_col_filter: Optional[str] = None) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    if text_col_filter:
        df = df[df["text_column"] == text_col_filter].copy()
    df["vector"] = df["embedding_vector"].apply(_parse_vector)
    df = df.dropna(subset=["vector"])
    return df.rename(columns={id_col: "entity_id"})


def vectors_to_matrix(df: pd.DataFrame) -> np.ndarray:
    return np.array(df["vector"].tolist(), dtype=np.float32)


def reduce_umap(matrix: np.ndarray,
                n_neighbors: int = 15,
                min_dist: float = 0.1,
                seed: int = 42) -> np.ndarray:
    from umap import UMAP
    return UMAP(n_components=2, n_neighbors=n_neighbors,
                min_dist=min_dist, random_state=seed,
                low_memory=True).fit_transform(matrix)


# ── Cluster figures ────────────────────────────────────────────────────────

def _embeddings_from_tg_as_df(tg_client, vertex_type: str, vector_attr: str,
                               id_col: str) -> Optional[pd.DataFrame]:
    """Fetch embeddings from TigerGraph and return as a DataFrame with
    columns [id_col, 'vector'] — matching the shape of load_embeddings()."""
    if tg_client is None:
        return None
    try:
        from services.tg_embedding_loader import fetch_embeddings_from_tg
        emb_dict = fetch_embeddings_from_tg(tg_client, vertex_type, vector_attr)
        if not emb_dict:
            return None
        rows = [{"entity_id": vid, "vector": vec} for vid, vec in emb_dict.items()]
        return pd.DataFrame(rows)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("TG embedding fetch failed: %s", exc)
        return None


def transaction_cluster_figure(
    text_col: str = "transaction_text_risk",
    n_neighbors: int = 15,
    min_dist: float = 0.10,
    sample_n: int = 2000,
    extra_points: Optional[pd.DataFrame] = None,
    tg_client=None,
) -> go.Figure:
    # Full (78 MB, local only) → slim sample (16 MB, committed to git) → TigerGraph
    csv_full = ROOT / "data" / "transaction_embeddings.csv"
    csv_slim = ROOT / "data" / "transaction_embeddings_slim.csv"
    vector_attr = "risk_embedding" if "risk" in text_col else "behaviour_emb"

    if csv_full.exists():
        df = load_embeddings(csv_full, "tran_sequence_number", text_col_filter=text_col)
    elif csv_slim.exists():
        df = load_embeddings(csv_slim, "tran_sequence_number", text_col_filter=text_col)
    else:
        tg_df = _embeddings_from_tg_as_df(tg_client, "Transaction", vector_attr, "tran_sequence_number")
        if tg_df is None:
            raise FileNotFoundError(
                "Transaction embedding CSV not found. "
                "Commit `data/transaction_embeddings_slim.csv` to the repository to enable this view."
            )
        df = tg_df
    if len(df) > sample_n:
        df = df.sample(sample_n, random_state=42).reset_index(drop=True)

    mat    = vectors_to_matrix(df)
    coords = reduce_umap(mat, n_neighbors, min_dist)
    df["x"], df["y"] = coords[:, 0], coords[:, 1]

    # Enrich with metadata
    prep = ROOT / "data" / "embedding_prep_transactions.csv"
    colour_col = "amount_band"
    if prep.exists():
        prep_df = pd.read_csv(prep, usecols=[
            "tran_sequence_number", "transaction_amount",
            "merchant_category_code", "merchant_region_code", "risk_tags"
        ], dtype=str)
        prep_df["transaction_amount"] = pd.to_numeric(prep_df["transaction_amount"], errors="coerce")
        prep_df["amount_band"] = prep_df["transaction_amount"].apply(
            lambda v: _amount_band(v) if pd.notna(v) else "Unknown"
        )
        df = df.merge(
            prep_df.rename(columns={"tran_sequence_number": "entity_id"}),
            on="entity_id", how="left",
        )
    else:
        df["amount_band"] = "Unknown"
        df["merchant_category_code"] = ""
        df["merchant_region_code"] = ""

    hover = {k: True for k in ["merchant_category_code", "merchant_region_code", "amount_band", "risk_tags"]
             if k in df.columns}

    fig = px.scatter(
        df, x="x", y="y", color=colour_col,
        hover_name="entity_id", hover_data=hover,
        color_discrete_sequence=_PALETTE,
        title=f"Transaction Clusters — {text_col.replace('transaction_text_', '').upper()}",
        labels={"x": "UMAP-1", "y": "UMAP-2"},
        template="plotly_dark", opacity=0.7,
    )
    fig.update_traces(marker_size=5)

    # Overlay injected points (e.g. GraphSAGE-repositioned nodes)
    if extra_points is not None and not extra_points.empty:
        fig.add_trace(go.Scatter(
            x=extra_points["x"], y=extra_points["y"],
            mode="markers+text",
            text=extra_points.get("label", extra_points["entity_id"]),
            textposition="top center",
            marker=dict(size=14, color="yellow", symbol="star",
                        line=dict(color="black", width=1)),
            name="Injected / Highlighted",
            hovertext=extra_points.get("hover", extra_points["entity_id"]),
        ))

    fig.update_layout(height=580, legend_title_text=colour_col)
    return fig


def merchant_cluster_figure(
    n_neighbors: int = 10,
    min_dist: float = 0.15,
    extra_points: Optional[pd.DataFrame] = None,
    tg_client=None,
) -> go.Figure:
    csv = ROOT / "data" / "merchant_embeddings.csv"

    if csv.exists():
        df = load_embeddings(csv, "merchant_id", text_col_filter="merchant_text_summary")
    else:
        tg_df = _embeddings_from_tg_as_df(tg_client, "Merchant", "embedding", "merchant_id")
        if tg_df is None:
            raise FileNotFoundError(
                f"{csv}\n\nMerchant embedding CSV not found and no TigerGraph client provided."
            )
        df = tg_df
    mat    = vectors_to_matrix(df)
    coords = reduce_umap(mat, n_neighbors, min_dist)
    df["x"], df["y"] = coords[:, 0], coords[:, 1]

    prep = ROOT / "data" / "embedding_prep_merchants.csv"
    colour_col = "merchant_category_text"
    if prep.exists():
        cols = [c for c in ["merchant_id", "merchant_category_text", "merchant_region_code",
                             "average_amount", "amount_profile", "top_risk_tags"]
                if True]
        prep_df = pd.read_csv(prep, dtype=str)
        avail   = [c for c in cols if c in prep_df.columns]
        df = df.merge(
            prep_df[avail].rename(columns={"merchant_id": "entity_id"}),
            on="entity_id", how="left",
        )
    else:
        df["merchant_category_text"] = "Unknown"

    hover = {k: True for k in ["merchant_category_text", "merchant_region_code",
                                 "average_amount", "top_risk_tags"] if k in df.columns}

    fig = px.scatter(
        df, x="x", y="y", color=colour_col,
        hover_name="entity_id", hover_data=hover,
        color_discrete_sequence=_PALETTE,
        title="Merchant Embedding Clusters",
        labels={"x": "UMAP-1", "y": "UMAP-2"},
        template="plotly_dark", opacity=0.80,
    )
    fig.update_traces(marker_size=10)

    if extra_points is not None and not extra_points.empty:
        fig.add_trace(go.Scatter(
            x=extra_points["x"], y=extra_points["y"],
            mode="markers+text",
            text=extra_points.get("label", extra_points["entity_id"]),
            textposition="top right",
            marker=dict(size=18, color="yellow", symbol="star",
                        line=dict(color="black", width=1)),
            name="New Merchant (injected)",
            hovertext=extra_points.get("hover", extra_points["entity_id"]),
        ))

    fig.update_layout(height=560, legend_title_text="Category")
    return fig


def user_cluster_figure(
    n_neighbors: int = 12,
    min_dist: float = 0.12,
    tg_client=None,
) -> go.Figure:
    csv = ROOT / "data" / "user_embeddings.csv"

    if csv.exists():
        df = load_embeddings(csv, "userid", text_col_filter="user_text_summary")
    else:
        tg_df = _embeddings_from_tg_as_df(tg_client, "User", "embedding", "userid")
        if tg_df is None:
            raise FileNotFoundError(
                f"{csv}\n\nUser embedding CSV not found and no TigerGraph client provided."
            )
        df = tg_df
    mat    = vectors_to_matrix(df)
    coords = reduce_umap(mat, n_neighbors, min_dist)
    df["x"], df["y"] = coords[:, 0], coords[:, 1]

    prep = ROOT / "data" / "embedding_prep_users.csv"
    colour_col = "dominant_region"
    if prep.exists():
        prep_df = pd.read_csv(prep, dtype=str)
        avail = [c for c in ["userid", "dominant_region", "total_spend",
                              "favorite_category_text", "spend_profile", "top_risk_tags"]
                 if c in prep_df.columns]
        if "total_spend" in avail:
            prep_df["total_spend"] = pd.to_numeric(prep_df["total_spend"], errors="coerce")
            prep_df["spend_band"] = prep_df["total_spend"].apply(
                lambda v: _amount_band(v) if pd.notna(v) else "Unknown"
            )
            avail.append("spend_band")
        df = df.merge(
            prep_df[avail].rename(columns={"userid": "entity_id"}),
            on="entity_id", how="left",
        )
    else:
        df["dominant_region"] = "Unknown"

    hover = {k: True for k in ["dominant_region", "spend_band", "favorite_category_text",
                                 "top_risk_tags"] if k in df.columns}

    fig = px.scatter(
        df, x="x", y="y", color=colour_col,
        hover_name="entity_id", hover_data=hover,
        color_discrete_sequence=_PALETTE,
        title="User Embedding Clusters",
        labels={"x": "UMAP-1", "y": "UMAP-2"},
        template="plotly_dark", opacity=0.80,
    )
    fig.update_traces(marker_size=7)
    fig.update_layout(height=560, legend_title_text="Region")
    return fig


# ── Graph network figure ───────────────────────────────────────────────────

def graph_network_figure(context_results: list[dict]) -> go.Figure:
    """Interactive Plotly network from a TigerGraph context query result."""
    import networkx as nx

    G = nx.Graph()
    node_colour: dict[str, str] = {}
    node_label:  dict[str, str] = {}

    key_type_map = {
        "start_txns":           "Transaction",
        "related_transactions": "Transaction",
        "txns":                 "Transaction",
        "related_users":        "User",
        "users":                "User",
        "related_merchants":    "Merchant",
        "merchants":            "Merchant",
        "related_locations":    "Location",
        "locations":            "Location",
        "related_dt":           "Transaction_DateTime",
        "datetimes":            "Transaction_DateTime",
        "related_mcc":          "MCC_Code",
        "mcc_codes":            "MCC_Code",
    }

    for key, vtype in key_type_map.items():
        for block in context_results:
            for v in block.get(key, []):
                vid = v.get("v_id", "")
                if not vid:
                    continue
                G.add_node(vid)
                node_colour[vid] = NODE_COLOURS.get(vtype, "#999")
                attrs = v.get("attributes", {})
                label = (attrs.get("merch_name") or attrs.get("userid") or
                         attrs.get("merch_city") or vid[:10])
                node_label[vid] = label

    # Wire edges based on type co-membership in the same context block
    for block in context_results:
        txn_ids   = [v["v_id"] for v in block.get("start_txns",        []) + block.get("txns", [])]
        merch_ids = [v["v_id"] for v in block.get("related_merchants",  []) + block.get("merchants", [])]
        user_ids  = [v["v_id"] for v in block.get("related_users",      []) + block.get("users", [])]
        loc_ids   = [v["v_id"] for v in block.get("related_locations",  []) + block.get("locations", [])]
        mcc_ids   = [v["v_id"] for v in block.get("related_mcc",        []) + block.get("mcc_codes", [])]

        for t in txn_ids:
            for m in merch_ids: G.add_edge(t, m, label="Occurs")
            for u in user_ids:  G.add_edge(t, u, label="Initiate")
        for m in merch_ids:
            for l in loc_ids:   G.add_edge(m, l, label="Has")
            for c in mcc_ids:   G.add_edge(m, c, label="Categorized_by")

    if G.number_of_nodes() == 0:
        fig = go.Figure()
        fig.update_layout(title="No graph data yet — run a search first.",
                          template="plotly_dark")
        return fig

    pos = nx.spring_layout(G, seed=42, k=2.0)

    # Edge traces
    edge_x, edge_y = [], []
    for u, v in G.edges():
        x0, y0 = pos[u]; x1, y1 = pos[v]
        edge_x += [x0, x1, None]; edge_y += [y0, y1, None]

    edge_trace = go.Scatter(x=edge_x, y=edge_y, mode="lines",
                             line=dict(width=0.8, color="#666"),
                             hoverinfo="none")

    # Separate trace per node type for legend
    traces = [edge_trace]
    for vtype, colour in NODE_COLOURS.items():
        nodes = [n for n in G.nodes() if node_colour.get(n) == colour]
        if not nodes:
            continue
        traces.append(go.Scatter(
            x=[pos[n][0] for n in nodes],
            y=[pos[n][1] for n in nodes],
            mode="markers+text",
            text=[node_label.get(n, n) for n in nodes],
            textposition="top center",
            textfont=dict(size=8, color="white"),
            hovertext=nodes,
            hoverinfo="text",
            marker=dict(size=14, color=colour,
                        line=dict(width=1, color="white")),
            name=vtype,
        ))

    fig = go.Figure(data=traces)
    fig.update_layout(
        title="Graph Context Network",
        template="plotly_dark",
        height=520,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=10, r=10, t=40, b=10),
        legend_title_text="Node Type",
    )
    return fig
