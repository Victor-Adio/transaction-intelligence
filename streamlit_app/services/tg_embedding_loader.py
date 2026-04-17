"""
TigerGraph embedding loader.

Fetches pre-computed vector embeddings directly from TigerGraph vertex
attributes via the REST++ /graph/{name}/vertices endpoint.

This replaces reading from local CSV files — all embeddings live in TigerGraph
and do not need to be committed to the repository.

Usage
-----
    from services.tg_embedding_loader import fetch_embeddings_from_tg

    merch_embs = fetch_embeddings_from_tg(
        client,
        vertex_type    = "Merchant",
        vector_attr    = "embedding",
        id_attr        = "v_id",       # use the vertex primary ID
    )
    # returns {merchant_id: np.ndarray(384,)}
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import requests

log = logging.getLogger(__name__)

# Vertex type → (vector attribute name, primary-id attribute or "v_id")
# Update these if attribute names differ in your graph.
VERTEX_VECTOR_MAP: dict[str, tuple[str, str]] = {
    "Transaction": ("risk_embedding",  "v_id"),   # primary source for risk
    "Transaction_behaviour": ("behaviour_emb", "v_id"),   # alias used internally
    "Merchant":    ("embedding",       "v_id"),
    "User":        ("embedding",       "v_id"),
}


def fetch_embeddings_from_tg(
    client,                         # TigerGraphDemoClient instance
    vertex_type: str,
    vector_attr: str,
    limit: int = 10_000,
) -> dict[str, np.ndarray]:
    """Return {vertex_id: embedding_array} fetched live from TigerGraph.

    Uses the REST++ vertex endpoint:
        GET /restpp/graph/{graph}/vertices/{type}?limit={n}

    Parameters
    ----------
    client      : TigerGraphDemoClient — already authenticated
    vertex_type : e.g. "Merchant", "User", "Transaction"
    vector_attr : name of the VECTOR attribute on that vertex type
    limit       : maximum number of vertices to fetch (default 10,000)
    """
    path   = f"graph/{client.graphname}/vertices/{vertex_type}"
    params = {"limit": limit}

    try:
        resp = client._restpp(path, params=params)
    except Exception as exc:
        log.error("Failed to fetch %s embeddings from TigerGraph: %s", vertex_type, exc)
        return {}

    results = resp.get("results", []) if isinstance(resp, dict) else resp
    if not isinstance(results, list):
        return {}

    out: dict[str, np.ndarray] = {}
    for vertex in results:
        vid   = str(vertex.get("v_id", ""))
        attrs = vertex.get("attributes", {})
        raw   = attrs.get(vector_attr)

        if raw is None:
            continue

        # TigerGraph returns vectors as a list of floats or as a JSON string
        if isinstance(raw, list):
            vec = np.array(raw, dtype=np.float32)
        elif isinstance(raw, str) and raw.strip().startswith("["):
            try:
                import json
                vec = np.array(json.loads(raw), dtype=np.float32)
            except Exception:
                continue
        else:
            continue

        if vec.ndim == 1 and len(vec) > 0:
            out[vid] = vec

    log.info("Fetched %d %s embeddings from TigerGraph", len(out), vertex_type)
    return out
