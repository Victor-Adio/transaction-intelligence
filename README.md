# ⚡ Transaction Intelligence

> Vector Search · Graph Traversal · Neighbourhood Embeddings — powered by **TigerGraph 4.2**

A unified intelligence platform for transaction analysis combining TigerGraph's native vector index (HNSW/COSINE) with graph traversal to deliver semantic hybrid search across 5,000 transactions, 220 merchants, and 848 users.

---

## Pages

| Page | What it does |
|---|---|
| **🏠 Home** | Overview, architecture, and navigation |
| **🔍 Hybrid Search** | Natural-language query → vector Top-K → GSQL graph expansion |
| **🔬 Cluster Explorer** | UMAP 2D projections of 384-dim embeddings (transactions, merchants, users) |
| **🧠 GraphSAGE Explorer** | 1-hop / 2-hop neighbourhood aggregation and cold-start detection |

---

## Local setup

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure TigerGraph credentials

Copy the secrets template and fill in your values:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# then edit .streamlit/secrets.toml with your TigerGraph host, username, and API secret
```

> **API secret** is found in GraphStudio → Admin Portal → Users → Secrets → Create Secret

Alternatively, enter credentials directly in the app sidebar — click **💾 Save** to persist locally.

### 3. (Optional) Regenerate large embedding files

The transaction embedding files (`data/transaction_embeddings.csv`, `data/vector_loads/transactions_*.csv`) are excluded from the repo due to size. Regenerate them with:

```bash
python scripts/preprocess_transactions_for_embeddings.py
python scripts/generate_transaction_embeddings.py
python scripts/prepare_tigergraph_vector_loads.py
```

### 4. Run the app

```bash
cd streamlit_app
streamlit run app.py
```

---

## Deploy on Streamlit Cloud

### 1. Push to GitHub (see below for what to commit)

### 2. Connect on [share.streamlit.io](https://share.streamlit.io)

- **Repository:** your GitHub repo
- **Branch:** `main`
- **Main file path:** `streamlit_app/app.py`

### 3. Add secrets

In **App Settings → Secrets**, paste:

```toml
[tigergraph]
host       = "https://your-instance.tgcloud.io"
graph_name = "Tran_graph"
username   = "your@email.com"
secret     = "your_api_secret_here"
use_ssl    = true
```

> The app reads from `st.secrets["tigergraph"]` automatically when no local `.streamlit_connection.json` exists.

---

## Project structure

```
├── streamlit_app/
│   ├── app.py                        # Main app + Home page
│   ├── pages/
│   │   ├── 1_Hybrid_Search.py
│   │   ├── 2_Cluster_Explorer.py
│   │   └── 3_GraphSAGE_Explorer.py
│   └── services/
│       ├── tigergraph_client.py      # TigerGraph REST client (JWT auth)
│       ├── cluster_viz.py            # UMAP cluster visualisations
│       ├── graphsage_sim.py          # GraphSAGE neighbourhood aggregation
│       └── embeddings.py             # Query embedding (sentence-transformers)
├── gsql/
│   └── query_pack.gsql               # All GSQL context + summary queries
├── data/
│   ├── synthetic_transactions_5000_new.csv
│   ├── vertices/                     # TigerGraph bulk-load vertex files
│   ├── edges/                        # TigerGraph bulk-load edge files
│   ├── merchant_embeddings.csv       # Pre-computed 384-dim merchant vectors
│   ├── user_embeddings.csv           # Pre-computed 384-dim user vectors
│   └── embedding_prep_*.csv          # Feature-engineered text for embeddings
├── scripts/
│   ├── generate_synthetic_transactions.py
│   ├── preprocess_transactions_for_embeddings.py
│   ├── generate_transaction_embeddings.py
│   ├── preprocess_entity_embeddings.py
│   ├── prepare_tigergraph_vector_loads.py
│   └── install_queries.py            # Uploads GSQL queries to TigerGraph
├── requirements.txt
└── .streamlit/
    └── secrets.toml.example          # Credentials template (copy → secrets.toml)
```

---

## TigerGraph schema

| Vertex | Key attributes | Embeddings |
|---|---|---|
| `Transaction` | Transaction_id, Amount, Channel_type, Currency_code | `risk_embedding` + `behaviour_emb` (384-dim) |
| `Merchant` | merchantid, merch_name, merch_type | `embedding` (384-dim) |
| `User` | userid, dw_issuer_id, dw_product_cd | `embedding` (384-dim) |
| `Location` | merch_city, merch_region_code, merchant_country_code, country | — |
| `Transaction_DateTime` | TransactionDate, TransactionTime | — |
| `MCC_Code` | mcc_code | — |

**Edges:** `Initiate` (User→Transaction) · `Occurs` (Transaction→Merchant) · `Has` (Merchant→Location) · `Happens_at` (Transaction→Transaction_DateTime) · `Categorized_by` (Merchant→MCC_Code)

**Vector config:** FLOAT · 384 dimensions · COSINE similarity · HNSW index
