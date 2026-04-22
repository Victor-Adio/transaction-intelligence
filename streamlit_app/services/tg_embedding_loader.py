"""
TigerGraph embedding loader.

Fetches pre-computed vector embeddings directly from TigerGraph by calling
installed GSQL export queries that use  PRINT <vertex_set> WITH VECTOR.

The  WITH VECTOR  clause (TigerGraph 4.1+) forces VECTOR attributes into the
REST++ JSON response.  Without it the HNSW index is query-only and vectors
never appear in vertex attribute payloads.

Query → result-key mapping
--------------------------
  Export_merchant_embeddings   → "merchants"   (Merchant.embedding)
  Export_user_embeddings       → "users"        (User.embedding)
  Export_transaction_embeddings→ "txns"         (Transaction.risk_embedding / behaviour_emb)

Usage
-----
    from services.tg_embedding_loader import fetch_embeddings_from_tg

    merch_embs = fetch_embeddings_from_tg(client, "Merchant", "embedding")
    # returns {merchant_id: np.ndarray(384,)}
    # returns {} if the query is not installed or WITH VECTOR is not supported
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)

# Maps vertex_type → installed export query name
_EXPORT_QUERY_MAP = {
    "Merchant":    "Export_merchant_embeddings",
    "User":        "Export_user_embeddings",
    "Transaction": "Export_transaction_embeddings",
}

# Maps vertex_type → result key in the query response
_RESULT_KEY_MAP = {
    "Merchant":    "merchants",
    "User":        "users",
    "Transaction": "txns",
}


def fetch_embeddings_from_tg(
    client,
    vertex_type: str,
    vector_attr: str,
    limit: int = 10_000,
) -> dict[str, np.ndarray]:
    """Return {vertex_id: embedding_array} by calling an installed GSQL export query.

    Parameters
    ----------
    client      : TigerGraphDemoClient — already authenticated
    vertex_type : "Merchant", "User", or "Transaction"
    vector_attr : name of the VECTOR attribute (e.g. "embedding", "risk_embedding")
    limit       : max vertices to fetch (only used for Transaction)
    """
    query_name = _EXPORT_QUERY_MAP.get(vertex_type)
    result_key = _RESULT_KEY_MAP.get(vertex_type)

    if not query_name:
        log.error("No export query defined for vertex type: %s", vertex_type)
        return {}

    params: list[tuple[str, str]] = []
    if vertex_type == "Transaction":
        params = [("batch_size", str(limit))]

    try:
        resp = client._restpp(
            f"query/{client.graphname}/{query_name}",
            params=params,
            timeout=120,
        )
    except Exception as exc:
        log.error("Failed to call %s: %s", query_name, exc)
        return {}

    results = resp.get("results", []) if isinstance(resp, dict) else []

    # Find the list of vertices in the results
    vertices: list[dict] = []
    for block in results:
        if isinstance(block, dict):
            # Direct key match
            if result_key and result_key in block:
                vertices = block[result_key]
                break
            # Fallback: take first list value
            for v in block.values():
                if isinstance(v, list) and v:
                    vertices = v
                    break
        if vertices:
            break

    if not vertices:
        log.warning(
            "%s returned 0 vertices. "
            "Query may not be installed — run scripts/install_queries.py",
            query_name,
        )
        return {}

    # Diagnostic: inspect first vertex to detect whether WITH VECTOR worked
    sample_attrs = vertices[0].get("attributes", {}) if vertices else {}
    if vector_attr not in sample_attrs:
        present = list(sample_attrs.keys())
        log.warning(
            "WITH VECTOR: '%s' not in first %s vertex attributes. "
            "Keys present: %s. "
            "Either the query was not reinstalled after adding WITH VECTOR, "
            "or this TigerGraph build does not support WITH VECTOR in PRINT.",
            vector_attr, vertex_type, present,
        )

    out: dict[str, np.ndarray] = {}
    missing_vec = 0
    for vertex in vertices:
        vid   = str(vertex.get("v_id", ""))
        attrs = vertex.get("attributes", {})
        raw   = attrs.get(vector_attr)

        if raw is None:
            missing_vec += 1
            continue

        if isinstance(raw, list) and len(raw) > 0:
            vec = np.array(raw, dtype=np.float32)
        elif isinstance(raw, str) and raw.strip().startswith("["):
            try:
                import json
                vec = np.array(json.loads(raw), dtype=np.float32)
            except Exception:
                continue
        else:
            missing_vec += 1
            continue

        if vec.ndim == 1 and len(vec) > 0:
            out[vid] = vec

    if missing_vec and not out:
        log.warning(
            "All %d %s vertices had no '%s' attribute. "
            "PRINT ... WITH VECTOR may not be returning the embedding on this build. "
            "Falling back to local CSV files.",
            len(vertices), vertex_type, vector_attr,
        )
    elif missing_vec:
        log.warning(
            "%d/%d %s vertices had no '%s' attribute.",
            missing_vec, len(vertices), vertex_type, vector_attr,
        )

    log.info(
        "TigerGraph WITH VECTOR: fetched %d/%d %s embeddings (%s)",
        len(out), len(vertices), vertex_type, vector_attr,
    )
    return out
