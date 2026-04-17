from __future__ import annotations

import logging
from typing import Any

import requests

log = logging.getLogger(__name__)

requests.packages.urllib3.disable_warnings()


def _fetch_token(host: str, secret: str) -> str:
    """Fetch a JWT bearer token via POST /gsql/v1/tokens (TigerGraph 4.x)."""
    url = f"{host}/gsql/v1/tokens"
    resp = requests.post(url, json={"secret": secret}, verify=False, timeout=15)
    data = resp.json()
    if data.get("error") or not data.get("token"):
        raise RuntimeError(f"Token fetch failed: {data.get('message', data)}")
    return data["token"]


class TigerGraphDemoClient:
    """Thin REST client for TigerGraph 4.x using a bearer token directly.

    Bypasses pyTigerGraph's internal auth logic, which sends the secret as
    Basic auth — a method rejected by TigerGraph Cloud 4.x.
    """

    def __init__(
        self,
        host: str,
        graph_name: str,
        username: str,
        password: str,
        use_ssl: bool = False,
    ) -> None:
        normalized = host.strip()
        if not normalized.startswith("http://") and not normalized.startswith("https://"):
            normalized = ("https://" if use_ssl else "http://") + normalized

        self.host = normalized.rstrip("/")
        self.graphname = graph_name

        self._token = _fetch_token(self.host, password)

        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Bearer {self._token}"})
        self._session.verify = False

    # ── Internal helpers ───────────────────────────────────────────────────

    def _restpp(
        self,
        path: str,
        method: str = "GET",
        _allow_missing: bool = False,
        timeout: int = 60,
        **kwargs: Any,
    ) -> Any:
        url = f"{self.host}/restpp/{path}"
        r = self._session.request(method, url, timeout=timeout, **kwargs)
        if _allow_missing and r.status_code == 404:
            log.warning("Query not found (404): %s — is it installed on TigerGraph?", path)
            return {"results": [], "_missing": True}
        r.raise_for_status()
        return r.json()

    def _gsql(self, path: str, method: str = "GET", **kwargs: Any) -> Any:
        url = f"{self.host}/gsql/v1/{path}"
        r = self._session.request(method, url, timeout=30, **kwargs)
        if not r.ok:
            raise RuntimeError(
                f"GSQL {method} {url} → {r.status_code}: {r.text[:600]}"
            )
        return r.json()

    # ── Public API ─────────────────────────────────────────────────────────

    # Maps (vertex_type, vector_attribute) to the installed query name.
    _VECTOR_QUERY_MAP: dict[tuple[str, str], str] = {
        ("Transaction", "risk_embedding"):  "Vec_search_txn_risk",
        ("Transaction", "behaviour_emb"):   "Vec_search_txn_behaviour",
        ("Merchant",    "embedding"):       "Vec_search_merchant",
        ("User",        "embedding"):       "Vec_search_user",
    }

    def search_top_k(
        self,
        vertex_type: str,
        vector_attribute: str,
        query_vector: list[float],
        top_k: int,
    ) -> list[dict[str, Any]]:
        query_name = self._VECTOR_QUERY_MAP.get((vertex_type, vector_attribute))
        if not query_name:
            raise ValueError(
                f"No installed vector search query for {vertex_type}.{vector_attribute}"
            )
        # Pass the float list as repeated 'qvec' params — the format TG REST++ accepts.
        params: list[tuple[str, str]] = [("topk", str(top_k))] + [
            ("qvec", str(v)) for v in query_vector
        ]
        result = self._restpp(
            f"query/{self.graphname}/{query_name}",
            params=params,
        )
        return result.get("results", []) if isinstance(result, dict) else []

    def ping(self) -> dict[str, Any]:
        """Test connectivity. Returns one sample Merchant vertex with all attributes."""
        try:
            result = self._restpp(
                f"graph/{self.graphname}/vertices/Merchant",
                params={"limit": 1},
                timeout=15,
            )
            results = result.get("results", []) if isinstance(result, dict) else []
            sample = results[0] if results else {}
            attrs = sample.get("attributes", {})
            return {
                "ok": True,
                "vertex_id": sample.get("v_id", "—"),
                "attribute_keys": list(attrs.keys()),
                "has_embedding": "embedding" in attrs,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def extract_ids(self, matches: list[dict[str, Any]]) -> list[str]:
        ids: list[str] = []
        for item in matches:
            if not isinstance(item, dict):
                continue
            for value in item.values():
                if isinstance(value, list):
                    for row in value:
                        if isinstance(row, dict):
                            row_id = row.get("v_id") or row.get("id") or row.get("primary_id")
                            if row_id is not None:
                                ids.append(str(row_id))
        return ids

    def run_context_query(self, query_name: str, ids: list[str], limit: int) -> Any:
        params = self._build_params(query_name, ids, limit)
        return self._restpp(
            f"query/{self.graphname}/{query_name}",
            params=self._flatten_params(params),
            _allow_missing=True,
        )

    def run_summary_query(self, query_name: str, ids: list[str]) -> Any:
        params = self._build_params(query_name, ids, None)
        return self._restpp(
            f"query/{self.graphname}/{query_name}",
            params=self._flatten_params(params),
            _allow_missing=True,
        )

    @staticmethod
    def _flatten_params(params: dict[str, Any]) -> list[tuple[str, str]]:
        """Convert list values into repeated query-string keys for REST++."""
        flat: list[tuple[str, str]] = []
        for k, v in params.items():
            if isinstance(v, list):
                for item in v:
                    flat.append((k, str(item)))
            else:
                flat.append((k, str(v)))
        return flat

    def _build_params(
        self, query_name: str, ids: list[str], limit: int | None
    ) -> dict[str, Any]:
        unique_ids = sorted(set(ids))
        if query_name == "Get_transaction_context":
            return {
                "txn_ids": unique_ids,
                "max_txns": limit or 15,
                "max_users": limit or 15,
                "max_merchants": limit or 15,
                "max_locations": limit or 15,
                "max_datetimes": limit or 15,
                "max_mcc": limit or 15,
            }
        if query_name == "Get_merchant_context":
            return {
                "merchant_ids": unique_ids,
                "max_merchants": limit or 15,
                "max_txns": (limit or 15) * 4,
                "max_users": (limit or 15) * 4,
                "max_locations": limit or 15,
                "max_mcc": limit or 15,
            }
        if query_name == "Get_user_context":
            return {
                "user_ids": unique_ids,
                "max_users": limit or 15,
                "max_txns": (limit or 15) * 4,
                "max_merchants": (limit or 15) * 4,
                "max_locations": (limit or 15) * 2,
                "max_datetimes": (limit or 15) * 2,
                "max_mcc": (limit or 15) * 2,
            }
        if query_name == "Summarize_transaction_patterns":
            return {"txn_ids": unique_ids}
        if query_name == "Summarize_merchant_exposure":
            return {"merchant_ids": unique_ids}
        if query_name == "Summarize_user_behavior":
            return {"user_ids": unique_ids}
        return {}
