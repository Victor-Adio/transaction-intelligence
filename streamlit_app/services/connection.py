"""
Shared TigerGraph connection helper.

Imported by app.py and all page files so they never need to import each other.
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from services.tigergraph_client import TigerGraphDemoClient

ROOT = Path(__file__).resolve().parents[2]
CONNECTION_STATE_FILE = ROOT / ".streamlit_connection.json"


def load_saved_connection() -> dict:
    """Return connection config from local JSON file or st.secrets."""
    if CONNECTION_STATE_FILE.exists():
        try:
            return json.loads(CONNECTION_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    try:
        tg = st.secrets.get("tigergraph", {})
        if tg:
            return {
                "host":          str(tg.get("host",       "")),
                "graph_name":    str(tg.get("graph_name", "Tran_graph")),
                "username":      str(tg.get("username",   "")),
                "use_ssl":       bool(tg.get("use_ssl",   True)),
                "save_password": False,
                "password":      str(tg.get("secret",     "")),
            }
    except Exception:
        pass

    return {}


def get_tg_client() -> TigerGraphDemoClient | None:
    """Build and return an authenticated TigerGraphDemoClient, or None."""
    cfg = load_saved_connection()
    if not cfg.get("password") or not cfg.get("host"):
        return None
    try:
        return TigerGraphDemoClient(
            host=cfg["host"],
            graph_name=cfg.get("graph_name", "Tran_graph"),
            username=cfg.get("username", ""),
            password=cfg["password"],
            use_ssl=bool(cfg.get("use_ssl", True)),
        )
    except Exception:
        return None
