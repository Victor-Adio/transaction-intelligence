"""
GraphSAGE simulation service.

Performs genuine neighbourhood aggregation on our pre-computed embeddings
using the graph structure stored in the edge CSV files.  This replicates
the core GraphSAGE operation:

    h_v^(k) = AGGREGATE( h_v^(k-1), { h_u^(k-1) : u ∈ N(v) } )

where AGGREGATE is MEAN for simplicity (same as GraphSAGE-mean variant).

We support 1-hop (merchant ← txn) and 2-hop (merchant ← txn ← user)
aggregation, cold-start merchant injection, and supervised fraud-score
simulation using synthetic labels derived from risk tags.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

# ── Embedding loading ──────────────────────────────────────────────────────

def _parse_vector(v: str) -> Optional[np.ndarray]:
    try:
        return np.array(json.loads(v), dtype=np.float32)
    except Exception:
        return None


def _l2_normalise(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v)
    return v / norm if norm > 0 else v


def load_embedding_dict(csv_path: Path, id_col: str,
                         text_col_filter: str) -> dict[str, np.ndarray]:
    """Return {entity_id: embedding_array} for the given text column."""
    df = pd.read_csv(csv_path)
    df = df[df["text_column"] == text_col_filter].copy()
    df["vec"] = df["embedding_vector"].apply(_parse_vector)
    df = df.dropna(subset=["vec"]).rename(columns={id_col: "entity_id"})
    return dict(zip(df["entity_id"], df["vec"]))


def load_all_embeddings(tg_client=None) -> tuple[
    dict[str, np.ndarray],   # transaction risk
    dict[str, np.ndarray],   # transaction behaviour
    dict[str, np.ndarray],   # merchant
    dict[str, np.ndarray],   # user
]:
    """Load embeddings from local CSV files when present, otherwise from TigerGraph.

    Pass `tg_client` (a TigerGraphDemoClient) to enable the TigerGraph fallback.
    """
    txn_risk_csv = ROOT / "data" / "transaction_embeddings.csv"
    merch_csv    = ROOT / "data" / "merchant_embeddings.csv"
    user_csv     = ROOT / "data" / "user_embeddings.csv"

    from services.tg_embedding_loader import fetch_embeddings_from_tg

    def _from_tg_or_csv(vtype: str, attr: str, csv_path: Path,
                         csv_id_col: str, csv_text_col: str) -> dict[str, np.ndarray]:
        """Try TigerGraph (WITH VECTOR) first; fall back to local CSV."""
        if tg_client is not None:
            result = fetch_embeddings_from_tg(tg_client, vtype, attr)
            if result:
                return result
        if csv_path.exists():
            return load_embedding_dict(csv_path, csv_id_col, csv_text_col)
        return {}

    # ── Transaction embeddings (risk + behaviour) ──────────────────────────
    txn_slim_csv = ROOT / "data" / "transaction_embeddings_slim.csv"
    txn_source   = txn_risk_csv if txn_risk_csv.exists() else txn_slim_csv

    txn_risk = _from_tg_or_csv(
        "Transaction", "risk_embedding", txn_source,
        "tran_sequence_number", "transaction_text_risk",
    )
    txn_beh = _from_tg_or_csv(
        "Transaction", "behaviour_emb", txn_source,
        "tran_sequence_number", "transaction_text_behavior",
    )

    # ── Merchant embeddings ────────────────────────────────────────────────
    merch = _from_tg_or_csv(
        "Merchant", "embedding", merch_csv,
        "merchant_id", "merchant_text_summary",
    )

    # ── User embeddings ────────────────────────────────────────────────────
    user = _from_tg_or_csv(
        "User", "embedding", user_csv,
        "userid", "user_text_summary",
    )

    return txn_risk, txn_beh, merch, user


# ── Graph structure ────────────────────────────────────────────────────────

def load_graph_edges() -> tuple[
    dict[str, list[str]],   # txn_id → [merchant_id]
    dict[str, list[str]],   # txn_id → [user_id]
    dict[str, list[str]],   # merchant_id → [txn_id]
    dict[str, list[str]],   # user_id → [txn_id]
]:
    tm = pd.read_csv(ROOT / "data" / "edges" / "transaction_merchant.csv",
                     dtype=str)
    ut = pd.read_csv(ROOT / "data" / "edges" / "user_transaction.csv",
                     dtype=str)

    txn_to_merch: dict[str, list[str]] = {}
    for _, row in tm.iterrows():
        txn_to_merch.setdefault(row["tran_sequence_number"], []).append(row["merchant_id"])

    merch_to_txn: dict[str, list[str]] = {}
    for t, ms in txn_to_merch.items():
        for m in ms:
            merch_to_txn.setdefault(m, []).append(t)

    txn_to_user: dict[str, list[str]] = {}
    user_to_txn: dict[str, list[str]] = {}
    for _, row in ut.iterrows():
        txn_to_user.setdefault(row["tran_sequence_number"], []).append(row["userid"])
        user_to_txn.setdefault(row["userid"], []).append(row["tran_sequence_number"])

    return txn_to_merch, txn_to_user, merch_to_txn, user_to_txn


# ── Aggregation ────────────────────────────────────────────────────────────

def _mean_aggregate(own: np.ndarray,
                    neighbours: list[np.ndarray],
                    alpha: float = 0.5) -> np.ndarray:
    """
    GraphSAGE-mean:  h = normalise( alpha * h_self + (1-alpha) * mean(h_neighbours) )
    If no neighbours exist, returns the original embedding unchanged.
    """
    if not neighbours:
        return own
    neigh_mean = np.mean(neighbours, axis=0)
    aggregated = alpha * own + (1 - alpha) * neigh_mean
    return _l2_normalise(aggregated)


def compute_sage_merchant_embeddings(
    merch_embs:    dict[str, np.ndarray],
    txn_embs:      dict[str, np.ndarray],
    merch_to_txn:  dict[str, list[str]],
    alpha: float = 0.5,
    hops: int = 1,
) -> dict[str, np.ndarray]:
    """
    1-hop or 2-hop GraphSAGE-mean for Merchant nodes.
    Aggregates transaction embeddings into each merchant's embedding.
    """
    sage: dict[str, np.ndarray] = {}
    for mid, own_emb in merch_embs.items():
        txn_ids    = merch_to_txn.get(mid, [])
        hop1_embs  = [txn_embs[t] for t in txn_ids if t in txn_embs]
        sage[mid]  = _mean_aggregate(own_emb, hop1_embs, alpha)
    return sage


def compute_sage_user_embeddings(
    user_embs:  dict[str, np.ndarray],
    txn_embs:   dict[str, np.ndarray],
    user_to_txn: dict[str, list[str]],
    alpha: float = 0.5,
) -> dict[str, np.ndarray]:
    sage: dict[str, np.ndarray] = {}
    for uid, own_emb in user_embs.items():
        txn_ids   = user_to_txn.get(uid, [])
        hop1_embs = [txn_embs[t] for t in txn_ids if t in txn_embs]
        sage[uid] = _mean_aggregate(own_emb, hop1_embs, alpha)
    return sage


# ── New-merchant injection ─────────────────────────────────────────────────

def inject_new_merchant(
    merch_embs:    dict[str, np.ndarray],
    txn_embs:      dict[str, np.ndarray],
    risk_txn_ids:  list[str],
    new_id:        str = "NEW_MERCHANT_001",
    alpha: float   = 0.5,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Simulate a brand-new merchant with NO own transaction history.
    - Original embedding: random unit vector (no data → no signal)
    - GraphSAGE embedding: aggregation of the connected high-risk transactions

    Returns (original_emb, sage_emb).
    """
    dim = next(iter(merch_embs.values())).shape[0]
    rng = np.random.default_rng(42)
    original = _l2_normalise(rng.standard_normal(dim).astype(np.float32))

    hop1_embs = [txn_embs[t] for t in risk_txn_ids if t in txn_embs]
    if hop1_embs:
        sage = _l2_normalise(np.mean(hop1_embs, axis=0).astype(np.float32))
    else:
        sage = original.copy()

    return original, sage


# ── UMAP + DataFrame builders ──────────────────────────────────────────────

def build_merchant_umap_df(
    original_embs: dict[str, np.ndarray],
    sage_embs:     dict[str, np.ndarray],
    meta_df:       pd.DataFrame,
    n_neighbors:   int = 10,
    min_dist:      float = 0.15,
    seed:          int = 42,
    new_merchant:  Optional[tuple[str, np.ndarray, np.ndarray]] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (original_df, sage_df) each with columns:
        entity_id, x, y, category, region, source
    Optionally injects a new merchant point into both DataFrames.
    """
    from umap import UMAP

    ids = sorted(original_embs.keys())

    orig_mat = np.array([original_embs[i] for i in ids], dtype=np.float32)
    sage_mat = np.array([sage_embs[i]     for i in ids], dtype=np.float32)

    new_id, new_orig, new_sage = (None, None, None)
    if new_merchant:
        new_id, new_orig, new_sage = new_merchant
        orig_mat = np.vstack([orig_mat, new_orig[None]])
        sage_mat = np.vstack([sage_mat, new_sage[None]])
        ids = ids + [new_id]

    # Fit UMAP on combined matrix so both projections share the same embedding space
    combined = np.vstack([orig_mat, sage_mat])
    reducer  = UMAP(n_components=2, n_neighbors=n_neighbors,
                    min_dist=min_dist, random_state=seed, low_memory=True)
    reduced  = reducer.fit_transform(combined)

    n = len(ids)
    orig_coords = reduced[:n]
    sage_coords = reduced[n:]

    meta = meta_df.set_index("merchant_id") if "merchant_id" in meta_df.columns else pd.DataFrame()

    def _build(coords: np.ndarray, label: str) -> pd.DataFrame:
        rows = []
        for i, mid in enumerate(ids):
            row = {"entity_id": mid, "x": float(coords[i, 0]), "y": float(coords[i, 1]),
                   "source": label, "is_new": mid == new_id}
            if not meta.empty and mid in meta.index:
                row["category"] = meta.at[mid, "merchant_category_text"] if "merchant_category_text" in meta.columns else ""
                row["region"]   = meta.at[mid, "merchant_region_code"]    if "merchant_region_code"    in meta.columns else ""
            else:
                row["category"] = "NEW — no history" if mid == new_id else ""
                row["region"]   = ""
            rows.append(row)
        return pd.DataFrame(rows)

    return _build(orig_coords, "Original (text only)"), _build(sage_coords, "GraphSAGE (+ neighbourhood)")


def top_risk_transaction_ids(txn_embs: dict[str, np.ndarray], top_n: int = 10) -> list[str]:
    """
    Return the IDs of the transactions whose embeddings have the largest L2 norm
    (proxy for most 'active' risk signal in the embedding space).
    """
    scored = [(tid, float(np.linalg.norm(emb))) for tid, emb in txn_embs.items()]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [tid for tid, _ in scored[:top_n]]


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def nearest_merchants(
    query: np.ndarray,
    emb_dict: dict[str, np.ndarray],
    top_n: int = 5,
) -> list[tuple[str, float]]:
    sims = [(mid, cosine_similarity(query, emb)) for mid, emb in emb_dict.items()]
    sims.sort(key=lambda x: x[1], reverse=True)
    return sims[:top_n]


# ── 2-hop aggregation: Merchant ← Transaction ← User ──────────────────────

def compute_sage_merchant_2hop(
    merch_embs:   dict[str, np.ndarray],
    user_embs:    dict[str, np.ndarray],
    txn_embs:     dict[str, np.ndarray],
    merch_to_txn: dict[str, list[str]],
    txn_to_user:  dict[str, list[str]],
    user_to_txn:  dict[str, list[str]],
    alpha: float  = 0.5,
) -> dict[str, np.ndarray]:
    """
    2-hop GraphSAGE-mean for Merchant nodes.

    Hop 1 (User ← Transaction):
        Each user's embedding is updated with the mean of their transaction embeddings.

    Hop 2 (Merchant ← User):
        Each merchant's embedding is updated with the mean of the hop-1 user
        embeddings of all users who transacted with that merchant.

    This captures richer signal than 1-hop because:
    - A user who visits many high-risk merchants propagates that risk to all of them.
    - Fraud rings become visible through shared user behaviour across merchants.
    """
    # Hop 1: compute user SAGE embeddings (user ← transactions)
    sage_users = compute_sage_user_embeddings(user_embs, txn_embs, user_to_txn, alpha=alpha)

    # Build merchant → users index through shared transactions
    merch_to_users: dict[str, list[str]] = {}
    for mid, txn_ids in merch_to_txn.items():
        users: list[str] = []
        for tid in txn_ids:
            users.extend(txn_to_user.get(tid, []))
        merch_to_users[mid] = list(set(users))

    # Hop 2: aggregate hop-1 user embeddings into merchant embedding
    result: dict[str, np.ndarray] = {}
    for mid, own_emb in merch_embs.items():
        user_ids    = merch_to_users.get(mid, [])
        user_vecs   = [sage_users[uid] for uid in user_ids if uid in sage_users]
        result[mid] = _mean_aggregate(own_emb, user_vecs, alpha)
    return result


# ── 2-hop UMAP builder (module-level so Streamlit cache hashes it stably) ──

def build_2hop_umap(
    merch_embs:   dict[str, np.ndarray],
    user_embs:    dict[str, np.ndarray],
    txn_embs:     dict[str, np.ndarray],
    merch_to_txn: dict[str, list[str]],
    txn_to_user:  dict[str, list[str]],
    user_to_txn:  dict[str, list[str]],
    alpha:        float,
    n_neighbors:  int,
    min_dist:     float,
) -> tuple[list[str], np.ndarray, np.ndarray, np.ndarray,
           dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Compute 1-hop and 2-hop SAGE embeddings and UMAP for all three views."""
    from umap import UMAP
    sage_1h = compute_sage_merchant_embeddings(merch_embs, txn_embs, merch_to_txn, alpha=alpha)
    sage_2h = compute_sage_merchant_2hop(merch_embs, user_embs, txn_embs,
                                          merch_to_txn, txn_to_user, user_to_txn, alpha=alpha)
    ids    = sorted(merch_embs.keys())
    mat_o  = np.array([merch_embs[i] for i in ids], dtype=np.float32)
    mat_1  = np.array([sage_1h[i]    for i in ids], dtype=np.float32)
    mat_2  = np.array([sage_2h[i]    for i in ids], dtype=np.float32)
    coords = UMAP(n_components=2, n_neighbors=n_neighbors, min_dist=min_dist,
                  random_state=42, low_memory=True).fit_transform(
                  np.vstack([mat_o, mat_1, mat_2]))
    n = len(ids)
    return ids, coords[:n], coords[n:2*n], coords[2*n:], sage_1h, sage_2h


# ── Supervised fraud scoring ───────────────────────────────────────────────

# Risk tags we treat as high-risk signals for the fraud label
_HIGH_RISK_TAGS = {
    "very high-value",
    "cash-like financial services",
    "late-night activity",
    "prepaid instrument",
}


def create_fraud_labels(
    txn_prep_path: Path,
    risk_threshold: int = 2,
) -> dict[str, int]:
    """
    Create synthetic binary fraud labels for transactions.

    A transaction is labelled 1 (high-risk) if it carries at least
    `risk_threshold` tags from _HIGH_RISK_TAGS.

    Returns {tran_sequence_number: label}.
    """
    labels: dict[str, int] = {}
    df = pd.read_csv(txn_prep_path, dtype=str)
    for _, row in df.iterrows():
        tags = set(t.strip() for t in row.get("risk_tags", "").split("|"))
        score = len(tags & _HIGH_RISK_TAGS)
        labels[row["tran_sequence_number"]] = int(score >= risk_threshold)
    return labels


def aggregate_merchant_fraud_labels(
    txn_labels:   dict[str, int],
    merch_to_txn: dict[str, list[str]],
    threshold:    float = 0.30,
) -> dict[str, int]:
    """
    Roll transaction fraud labels up to the merchant level.

    A merchant is labelled 1 (at-risk) if >= `threshold` fraction of its
    transactions are labelled high-risk.

    Returns {merchant_id: label}.
    """
    merch_labels: dict[str, int] = {}
    for mid, txn_ids in merch_to_txn.items():
        scored = [txn_labels.get(t, 0) for t in txn_ids]
        if scored:
            frac = sum(scored) / len(scored)
            merch_labels[mid] = int(frac >= threshold)
        else:
            merch_labels[mid] = 0
    return merch_labels


def train_fraud_classifier(
    emb_dict: dict[str, np.ndarray],
    labels:   dict[str, int],
    test_size: float = 0.3,
    seed:      int   = 42,
) -> dict:
    """
    Train a Logistic Regression on the given embeddings + labels.

    Returns a dict with keys:
        fpr, tpr, roc_auc, accuracy, precision, recall, report
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (
        roc_curve, auc, accuracy_score, precision_score,
        recall_score, classification_report,
    )
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler

    ids = [mid for mid in emb_dict if mid in labels]
    X   = np.array([emb_dict[mid] for mid in ids], dtype=np.float32)
    y   = np.array([labels[mid]   for mid in ids], dtype=int)

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=test_size, random_state=seed, stratify=y
    )
    scaler = StandardScaler()
    X_tr   = scaler.fit_transform(X_tr)
    X_te   = scaler.transform(X_te)

    clf = LogisticRegression(max_iter=1000, random_state=seed, class_weight="balanced")
    clf.fit(X_tr, y_tr)

    proba = clf.predict_proba(X_te)[:, 1]
    pred  = clf.predict(X_te)

    fpr, tpr, _ = roc_curve(y_te, proba)
    return {
        "fpr":       fpr.tolist(),
        "tpr":       tpr.tolist(),
        "roc_auc":   float(auc(fpr, tpr)),
        "accuracy":  float(accuracy_score(y_te, pred)),
        "precision": float(precision_score(y_te, pred, zero_division=0)),
        "recall":    float(recall_score(y_te, pred, zero_division=0)),
        "report":    classification_report(y_te, pred, zero_division=0),
    }


def score_merchants_fraud(
    emb_dict: dict[str, np.ndarray],
    labels:   dict[str, int],
    seed:     int = 42,
) -> pd.DataFrame:
    """
    Return a DataFrame of merchant IDs, their true label, and predicted
    fraud probability from a Logistic Regression trained on all data
    (used for ranking — not evaluation).
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    ids = [mid for mid in emb_dict if mid in labels]
    X   = np.array([emb_dict[mid] for mid in ids], dtype=np.float32)
    y   = np.array([labels[mid]   for mid in ids], dtype=int)

    scaler = StandardScaler()
    X_s    = scaler.fit_transform(X)
    clf    = LogisticRegression(max_iter=1000, random_state=seed, class_weight="balanced")
    clf.fit(X_s, y)

    proba = clf.predict_proba(X_s)[:, 1]
    return pd.DataFrame({
        "merchant_id":    ids,
        "true_label":     y,
        "fraud_prob":     np.round(proba, 4),
    }).sort_values("fraud_prob", ascending=False).reset_index(drop=True)
