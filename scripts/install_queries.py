"""
install_queries.py
------------------
Reads connection settings from .streamlit_connection.json, authenticates
to TigerGraph Cloud, uploads all queries from gsql/query_pack.gsql via
the GSQL REST endpoint, then issues INSTALL QUERY ALL.

Usage:
    python scripts/install_queries.py
"""

from __future__ import annotations

import json
import pathlib
import sys

import requests

requests.packages.urllib3.disable_warnings()

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONN_FILE = ROOT / ".streamlit_connection.json"
QUERY_FILE = ROOT / "gsql" / "query_pack.gsql"


def load_connection() -> dict:
    if not CONN_FILE.exists():
        sys.exit(f"[ERROR] Connection file not found: {CONN_FILE}")
    with open(CONN_FILE) as f:
        return json.load(f)


def fetch_token(host: str, secret: str) -> str:
    url = f"{host}/gsql/v1/tokens"
    resp = requests.post(url, json={"secret": secret}, verify=False, timeout=15)
    data = resp.json()
    if data.get("error") or not data.get("token"):
        sys.exit(f"[ERROR] Token fetch failed: {data.get('message', data)}")
    return data["token"]


def run_gsql(session: requests.Session, host: str, gsql: str) -> dict:
    url = f"{host}/gsql/v1/statements"
    resp = session.post(
        url,
        data=gsql.encode("utf-8"),
        headers={"Content-Type": "text/plain"},
        timeout=120,
        verify=False,
    )
    try:
        return resp.json()
    except Exception:
        return {"status": resp.status_code, "text": resp.text}


def main() -> None:
    conn = load_connection()

    host: str = conn.get("host", "").strip()
    secret: str = conn.get("password", "")  # field is labelled 'password', stores secret
    graph: str = conn.get("graph_name", "Tran_graph")

    if not host.startswith("http"):
        host = "https://" + host
    host = host.rstrip("/")

    print(f"[1/4] Connecting to: {host}  graph: {graph}")

    token = fetch_token(host, secret)
    print("[2/4] Token acquired successfully.")

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}"})
    session.verify = False

    gsql_body = QUERY_FILE.read_text()
    print(f"[3/4] Uploading queries from {QUERY_FILE.name} …")

    result = run_gsql(session, host, gsql_body)
    print("      Response:")
    print(json.dumps(result, indent=2))

    print("[4/4] Installing all queries (INSTALL QUERY ALL) …")
    install_result = run_gsql(session, host, f"USE GRAPH {graph}\nINSTALL QUERY ALL")
    print("      Response:")
    print(json.dumps(install_result, indent=2))

    print("\n✅ Done. Refresh your Streamlit app — all context tabs should now be active.")


if __name__ == "__main__":
    main()
