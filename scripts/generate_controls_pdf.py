"""
generate_controls_pdf.py
Generates a polished reference PDF for all GraphSAGE / Hybrid Search controls.
Uses system Arial fonts for full Unicode support (Greek letters, arrows, etc.)
"""

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from pathlib import Path

FONTS = "/System/Library/Fonts/Supplemental"
OUT   = Path(__file__).resolve().parents[1] / "GRAPHSAGE_CONTROLS_GUIDE.pdf"

BRAND_BLUE   = (23,  83, 164)
BRAND_ORANGE = (220, 90,  20)
DARK_GREY    = (45,  45,  45)
MID_GREY     = (110, 110, 110)
LIGHT_GREY   = (242, 242, 242)
WHITE        = (255, 255, 255)
GREEN        = (30,  130,  70)
PURPLE       = (110,  50, 170)


class PDF(FPDF):

    def setup_fonts(self):
        self.add_font("Arial",  "",  f"{FONTS}/Arial.ttf")
        self.add_font("Arial",  "B", f"{FONTS}/Arial Bold.ttf")
        self.add_font("Arial",  "I", f"{FONTS}/Arial Italic.ttf")
        self.add_font("ArialBI","",  f"{FONTS}/Arial Bold Italic.ttf")

    def header(self):
        self.set_fill_color(*BRAND_BLUE)
        self.rect(0, 0, 210, 14, "F")
        self.set_font("Arial", "B", 8)
        self.set_text_color(*WHITE)
        self.set_xy(10, 3)
        self.cell(130, 8, "TigerGraph Demo  ·  GraphSAGE & Hybrid Search — Controls Reference",
                  new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.cell(60, 8, f"Page {self.page_no()}", align="R",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(6)

    def footer(self):
        self.set_y(-12)
        self.set_font("Arial", "I", 7)
        self.set_text_color(*MID_GREY)
        self.cell(0, 8, "TigerGraph 4.2.2  ·  sentence-transformers all-MiniLM-L6-v2  ·  GraphSAGE-mean  ·  Streamlit", align="C")

    # ── helpers ──────────────────────────────────────────────────────────────

    def section_title(self, text, colour=None):
        if colour is None:
            colour = BRAND_BLUE
        self.ln(4)
        self.set_fill_color(*colour)
        self.set_text_color(*WHITE)
        self.set_font("Arial", "B", 12)
        self.cell(0, 9, f"  {text}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        self.ln(2)
        self.set_text_color(*DARK_GREY)

    def sub_title(self, text):
        self.set_font("Arial", "B", 10)
        self.set_text_color(*BRAND_ORANGE)
        self.cell(0, 7, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(*DARK_GREY)

    def body(self, text):
        self.set_font("Arial", "", 9)
        self.set_text_color(*DARK_GREY)
        self.multi_cell(0, 5, text)
        self.ln(1)

    def key_value(self, key, value):
        KEY_W = 52
        self.set_font("Arial", "B", 9)
        self.set_text_color(*BRAND_BLUE)
        self.cell(KEY_W, 5, key, new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("Arial", "", 9)
        self.set_text_color(*DARK_GREY)
        self.multi_cell(self.epw - KEY_W, 5, value)
        self.set_x(self.l_margin)

    def tip_box(self, text):
        self.set_fill_color(*LIGHT_GREY)
        self.set_draw_color(*BRAND_BLUE)
        self.set_line_width(0.5)
        self.set_font("Arial", "I", 8.5)
        self.set_text_color(60, 60, 80)
        self.multi_cell(0, 5, f"  → {text}", fill=True, border="L")
        self.ln(2)

    def formula_box(self, text):
        self.set_fill_color(225, 225, 248)
        self.set_font("Arial", "B", 9)
        self.set_text_color(*PURPLE)
        self.multi_cell(0, 6, f"  {text}", fill=True)
        self.set_text_color(*DARK_GREY)
        self.ln(2)

    def divider(self):
        self.ln(2)
        self.set_draw_color(*MID_GREY)
        self.set_line_width(0.2)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def table_header(self, headers, widths):
        self.set_fill_color(*BRAND_BLUE)
        self.set_text_color(*WHITE)
        self.set_font("Arial", "B", 8.5)
        for h, w in zip(headers, widths):
            self.cell(w, 7, f"  {h}", border=1, fill=True,
                      new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.ln()

    def table_row(self, cells, widths, shade=False):
        self.set_fill_color(*(LIGHT_GREY if shade else WHITE))
        self.set_text_color(*DARK_GREY)
        for i, (c, w) in enumerate(zip(cells, widths)):
            if i == 1:
                self.set_font("Arial", "B", 8.5)
                self.set_text_color(*BRAND_BLUE)
            else:
                self.set_font("Arial", "", 8.5)
                self.set_text_color(*DARK_GREY)
            self.cell(w, 6, f"  {c}", border=1, fill=True,
                      new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.ln()


# ═════════════════════════════════════════════════════════════════════════════
pdf = PDF()
pdf.setup_fonts()
pdf.set_auto_page_break(auto=True, margin=18)
pdf.add_page()

# ── COVER BLOCK ──────────────────────────────────────────────────────────────
pdf.set_fill_color(*BRAND_BLUE)
pdf.rect(0, 14, 210, 62, "F")

pdf.set_font("Arial", "B", 24)
pdf.set_text_color(*WHITE)
pdf.set_xy(12, 22)
pdf.cell(0, 14, "GraphSAGE & Hybrid Search", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

pdf.set_xy(12, 36)
pdf.set_font("Arial", "", 14)
pdf.cell(0, 9, "Controls & Filters — Reference Guide", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

pdf.set_xy(12, 50)
pdf.set_font("Arial", "I", 10)
pdf.set_text_color(190, 215, 255)
pdf.cell(0, 6, "TigerGraph 4.2.2  |  Global Fintech Vector + Graph Intelligence", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

pdf.set_xy(12, 60)
pdf.set_font("Arial", "", 9)
pdf.set_text_color(170, 200, 245)
pdf.cell(0, 6, "Streamlit App  •  GraphSAGE Explorer  •  Cluster Explorer  •  Hybrid Search",
         new_x=XPos.LMARGIN, new_y=YPos.NEXT)

pdf.ln(52)
pdf.set_text_color(*DARK_GREY)


# ═════════════════════════════════════════════════════════════════════════════
# 1 — WHAT IS UMAP
# ═════════════════════════════════════════════════════════════════════════════
pdf.section_title("1.  What is UMAP?")

pdf.body(
    "UMAP stands for Uniform Manifold Approximation and Projection. It is a dimensionality "
    "reduction algorithm — a mathematical technique for compressing high-dimensional data "
    "into 2 dimensions so humans can see and interpret it.\n\n"
    "In this demo, every transaction, merchant, and user is represented by a 384-number "
    "vector (384 dimensions). That is impossible to visualise directly. UMAP compresses "
    "those 384 numbers down to just 2 (x and y on the scatter plot) while preserving the "
    "most important property: things that were similar in 384-dimensional space end up "
    "close together in the 2D plot."
)

pdf.sub_title("What the UMAP scatter plot tells you:")
pdf.key_value("Close together  =",  "Very similar risk or behaviour profile — the model considers them nearly the same")
pdf.key_value("Far apart  =",       "Very different profiles")
pdf.key_value("Tight cluster  =",   "A natural grouping discovered with no human labels")
pdf.key_value("Isolated dot  =",    "An anomaly — entity with no similar peers in the dataset")
pdf.ln(2)

pdf.tip_box(
    "Management soundbite: 'Each dot is a merchant / transaction / user. Dots that are near "
    "each other behave the same way in the data. We did not tell the model what to group — "
    "it found the clusters itself from the raw transaction patterns.'"
)

pdf.divider()

# ═════════════════════════════════════════════════════════════════════════════
# 2 — UMAP CONTROLS
# ═════════════════════════════════════════════════════════════════════════════
pdf.section_title("2.  UMAP Controls")
pdf.body("These two sliders appear in both the Cluster Explorer and GraphSAGE Explorer sidebars.")

pdf.sub_title("UMAP n_neighbors   (slider: 5 – 30, default 10)")
pdf.body(
    "Controls how many nearby points UMAP considers when deciding where to place each dot. "
    "Think of it as the 'neighbourhood zoom level'."
)
pdf.key_value("Low (5 – 8):",   "Focuses on very local structure. Reveals fine-grained micro-clusters. Layout can look more scattered.")
pdf.key_value("High (20 – 30):","Focuses on global structure. Reveals broad, well-separated macro-clusters. Smoother layout.")
pdf.key_value("Recommended:",   "10 – 15 for this dataset. Good balance between local detail and global structure.")
pdf.ln(2)
pdf.tip_box("Demo tip: keep at 10. If clusters look too scattered, increase to 15. If everything merges, decrease to 7.")

pdf.divider()

pdf.sub_title("UMAP min_dist   (slider: 0.01 – 0.5, default 0.15)")
pdf.body(
    "Controls how tightly dots are packed within a cluster. "
    "It sets the minimum distance allowed between any two points in the 2D output."
)
pdf.key_value("Low (0.01 – 0.05):", "Dots pack very tightly. Clusters look dense and dramatic. Boundaries are sharp.")
pdf.key_value("High (0.3 – 0.5):", "Dots spread out. Clusters overlap and appear more gradual.")
pdf.key_value("Recommended:", "0.10 – 0.20 for presentations. Tight enough to look impressive, not overcrowded.")
pdf.ln(2)
pdf.tip_box("Demo tip: reduce to 0.05 to make clusters look dramatically tighter for a more striking visual.")

pdf.add_page()

# ═════════════════════════════════════════════════════════════════════════════
# 3 — SELF-WEIGHT ALPHA
# ═════════════════════════════════════════════════════════════════════════════
pdf.section_title("3.  Self-weight α  (GraphSAGE aggregation balance)")

pdf.sub_title("Slider: 0.1 – 0.9, default 0.5")
pdf.body(
    "This is the most important GraphSAGE parameter. It controls the balance between a "
    "merchant's OWN text description and the risk signals it absorbs from its connected "
    "transactions and users in the graph.\n\n"
    "The aggregation formula used in this demo:"
)
pdf.formula_box(
    "h_merchant  =  α × own_embedding  +  (1 − α) × mean(neighbour_embeddings)"
)

pdf.key_value("α = 0.9  (high self-weight):",
    "Merchant trusts its own description 90%. Neighbours have only 10% influence. "
    "Embedding barely moves from the text-only position.")
pdf.key_value("α = 0.5  (balanced):",
    "Equal weight to own description and neighbourhood. Recommended default — "
    "good balance of identity and context.")
pdf.key_value("α = 0.1  (low self-weight):",
    "Neighbourhood dominates 90%. The merchant's own description is nearly ignored. "
    "Embedding moves aggressively towards its graph neighbours.")
pdf.ln(2)

pdf.tip_box(
    "Demo script: in 'How It Works' → 'Live Similarity Probe', slide α from 0.9 down "
    "to 0.2 and watch the nearest-neighbour table change in real time. This visually "
    "demonstrates risk propagating through the network."
)

pdf.sub_title("Why does α matter for fraud detection?")
pdf.body(
    "A legitimate merchant that happens to be connected to high-risk transactions may have "
    "a perfectly safe own description. By lowering α, the neighbourhood signal dominates "
    "and the merchant gets pulled towards the risk cluster — even if no analyst has "
    "flagged it yet.\n\n"
    "This is how GraphSAGE catches fraud BEFORE it is confirmed: the network topology "
    "reveals risk signals before any label exists."
)

pdf.divider()

# ═════════════════════════════════════════════════════════════════════════════
# 4 — RISK TRANSACTIONS INJECTED TO NEW MERCHANT
# ═════════════════════════════════════════════════════════════════════════════
pdf.section_title("4.  Risk Transactions Injected to New Merchant  (Cold-Start Demo)")

pdf.sub_title("Slider: 3 – 20, default 8")
pdf.body(
    "This control is exclusive to the Cold-Start Demo tab. It simulates a brand-new merchant "
    "that has ZERO transaction history of its own. The slider sets how many of the highest-risk "
    "transaction embeddings are connected to this synthetic new merchant in the graph.\n\n"
    "The new merchant starts with a random embedding (no data = no signal). GraphSAGE then "
    "aggregates the embeddings of those injected transactions and pulls the new merchant's "
    "position towards whatever cluster those transactions belong to.\n"
)

pdf.formula_box(
    "new_merchant_sage  =  α × random_embedding  +  (1 − α) × mean(risk_transaction_embeddings)"
)

pdf.key_value("3 – 5 transactions:",  "Weak signal. New merchant moves slightly towards risk cluster but stays ambiguous.")
pdf.key_value("8 – 10 transactions:", "Moderate signal. New merchant clearly migrates into the risk zone. Best for demos.")
pdf.key_value("15 – 20 transactions:","Strong signal. New merchant lands deep inside the highest-risk cluster. Maximum visual impact.")
pdf.ln(2)

pdf.tip_box(
    "THE headline demo moment: set to 10, show the LEFT plot (random position = invisible "
    "to any model or rule engine), then reveal the RIGHT plot (lands deep in risk cluster = "
    "immediately flagged). This is the cold-start advantage no rule engine can replicate."
)

pdf.add_page()

# ═════════════════════════════════════════════════════════════════════════════
# 5 — HYBRID SEARCH CONTROLS
# ═════════════════════════════════════════════════════════════════════════════
pdf.section_title("5.  Hybrid Search Controls", colour=BRAND_ORANGE)

pdf.sub_title("Search Mode (dropdown)")
pdf.body("Selects which entity type and embedding to search against in TigerGraph:")
pdf.key_value("Transaction Risk:",      "Searches the risk_embedding on Transaction vertices. Finds transactions matching a risk description (e.g. 'late-night cash withdrawals below reporting threshold').")
pdf.key_value("Transaction Behaviour:", "Searches the behaviour_emb on Transaction vertices. Finds transactions matching a spending behaviour (e.g. 'weekend dining and entertainment').")
pdf.key_value("Merchant Similarity:",   "Searches the embedding on Merchant vertices. Finds merchants with a similar business profile and transaction pattern.")
pdf.key_value("User Similarity:",       "Searches the embedding on USER vertices. Finds users with a similar spending behaviour profile.")
pdf.ln(2)

pdf.sub_title("Natural-language query (text area)")
pdf.body(
    "Plain English description of what you are looking for. This text is embedded by the "
    "same sentence-transformers model (all-MiniLM-L6-v2) that created all the embeddings in "
    "TigerGraph. The system then finds the Top-K entities whose embeddings are most similar "
    "(by cosine similarity) to your query embedding.\n\n"
    "You do not need to know field names, MCC codes, thresholds, or SQL. The model "
    "understands the meaning of your words and matches it to the meaning stored in the data."
)
pdf.tip_box(
    "Example queries:  'Suspicious late-night ATM cash withdrawals just below 5,000'  |  "
    "'Premium international airline and hotel spending on corporate cards'  |  "
    "'Users with sudden high-frequency transactions across multiple countries'"
)

pdf.divider()

pdf.sub_title("Top-K matches   (slider: 3 – 20, default 8)")
pdf.body(
    "How many of the most semantically similar entities to return from TigerGraph's "
    "HNSW vector index. These K entities then become the seed set for the graph traversal."
)
pdf.key_value("Low K (3 – 5):", "Very precise. Only strongest semantic matches. Graph context is focused and specific.")
pdf.key_value("High K (15 – 20):", "Broader net. Captures weaker matches. Graph context is richer but may include noise.")
pdf.ln(2)
pdf.tip_box("Demo sweet spot: K = 8. Enough results to look substantive, focused enough to stay on-topic.")

pdf.divider()

pdf.sub_title("Context depth / per hop   (slider: 5 – 50, default 15)")
pdf.body(
    "After vector search returns K seed entities, the graph traversal expands outward "
    "one hop at a time. This slider limits how many vertices are fetched per hop — "
    "how many connected Merchants, Users, Locations, and DateTimes are returned per seed."
)
pdf.key_value("Low (5 – 10):",  "Tight focus. Only strongest connections. Faster. Cleaner result tables.")
pdf.key_value("High (30 – 50):","Wide context. Many connected entities returned. Richer graph network view. Slower.")
pdf.ln(2)
pdf.tip_box("Increase to 25 when demonstrating the Graph Network tab — denser network = more impressive visualisation.")

pdf.add_page()

# ═════════════════════════════════════════════════════════════════════════════
# 6 — CLUSTER EXPLORER
# ═════════════════════════════════════════════════════════════════════════════
pdf.section_title("6.  Cluster Explorer Controls", colour=GREEN)

pdf.sub_title("Entity selector (radio buttons)")
pdf.key_value("Transaction Risk:",      "UMAP of all 5,000 transaction risk embeddings. Colour = amount band (low / medium / high / very high).")
pdf.key_value("Transaction Behaviour:", "UMAP of all 5,000 transaction behaviour embeddings. Colour = merchant category.")
pdf.key_value("Merchants:",             "UMAP of all 220 merchant embeddings. Colour = merchant category text.")
pdf.key_value("Users:",                 "UMAP of all 848 user embeddings. Colour = dominant region (EMEA / APAC / NA / MEA).")
pdf.ln(2)
pdf.body("The UMAP n_neighbors and min_dist sliders work identically to those described in Section 2.")

pdf.divider()

# ═════════════════════════════════════════════════════════════════════════════
# 7 — GRAPHSAGE EXPLORER TABS
# ═════════════════════════════════════════════════════════════════════════════
pdf.section_title("7.  GraphSAGE Explorer — Tab-by-Tab Guide")

tabs = [
    ("Merchant Clusters",
     "Side-by-side UMAP of 220 merchants: text-only (left) vs 1-hop GraphSAGE (right). "
     "Controlled by alpha, n_neighbors, min_dist. Look for clusters tightening on the right."),
    ("User Clusters",
     "Side-by-side UMAP of 848 users: text-only vs 1-hop GraphSAGE. Users who visit "
     "similar merchants cluster together after graph aggregation."),
    ("Cold-Start Demo",
     "THE headline demo. A brand-new merchant with no transaction history is injected. "
     "Left: random embedding = invisible to every model and rule engine. "
     "Right: GraphSAGE pulls it into the risk cluster based on connected transactions. "
     "Controlled by alpha and the 'Risk transactions' slider."),
    ("2-Hop Aggregation",
     "Three-way UMAP: text-only vs 1-hop vs 2-hop (Merchant <- Transaction <- User). "
     "2-hop means each merchant absorbs User embeddings, which have already absorbed "
     "Transaction embeddings. Fraud rings become visible through shared mule accounts "
     "propagating risk across multiple merchants."),
    ("Fraud Scoring",
     "Supervised GNN simulation. Synthetic fraud labels derived from risk tags. "
     "Logistic Regression trained independently on text-only, 1-hop, and 2-hop embeddings. "
     "ROC curves compare which embedding makes fraud most separable. "
     "Top 20 merchants ranked by 2-hop fraud probability score."),
    ("TG Native GNN",
     "Architecture guide. Shows how this simulation maps to TigerGraph 4.x native ML "
     "Workbench — including the actual pyTigerGraph GDS API code and GSQL inference command."),
    ("How It Works",
     "Conceptual explanation of GraphSAGE, the aggregation formula, fraud scenario table, "
     "and the Live Similarity Probe with real-time nearest-neighbour updates."),
]

for name, desc in tabs:
    pdf.sub_title(f"  {name}")
    pdf.body(desc)
    pdf.ln(1)

pdf.add_page()

# ═════════════════════════════════════════════════════════════════════════════
# 8 — CHEAT SHEET TABLE
# ═════════════════════════════════════════════════════════════════════════════
pdf.section_title("8.  Demo Settings Cheat Sheet")
pdf.body("Recommended settings for the best senior management demo experience:")
pdf.ln(2)

headers = ["Control", "Recommended Value", "Why"]
widths  = [55, 48, 87]
pdf.table_header(headers, widths)

rows = [
    ("Self-weight α",             "0.5",           "Equal own + neighbourhood — balanced and easy to explain"),
    ("UMAP n_neighbors",          "10",             "Clear local clusters without over-fragmenting"),
    ("UMAP min_dist",             "0.15",           "Tight clusters that look visually impressive"),
    ("Risk txns (cold-start)",    "10",             "Strong enough signal to land clearly in risk cluster"),
    ("Top-K matches",             "8",              "Precise but visually rich — enough to fill all tabs"),
    ("Context depth",             "15",             "Fast response with enough context for all tabs"),
    ("Search mode (open with)",   "Transaction Risk","Most dramatic — shows unknown fraud patterns immediately"),
    ("Search mode (follow with)", "Merchant Similarity","Shows network surveillance across multiple merchants"),
]

for i, row in enumerate(rows):
    pdf.table_row(row, widths, shade=(i % 2 == 0))

pdf.ln(6)

# ═════════════════════════════════════════════════════════════════════════════
# 9 — GLOSSARY
# ═════════════════════════════════════════════════════════════════════════════
pdf.section_title("9.  Glossary")

terms = [
    ("Embedding",         "A list of numbers (vector) that encodes the meaning of text or an entity. Similar meanings produce similar numbers."),
    ("Cosine Similarity", "A score from -1 to 1 measuring how similar two embeddings are. 1.0 = identical meaning, 0 = unrelated, -1 = opposite."),
    ("Vector Search",     "Finding the K most similar embeddings to a query. The engine behind all natural-language searches in this demo."),
    ("HNSW",              "Hierarchical Navigable Small World. The index algorithm TigerGraph uses for fast vector search at scale."),
    ("GraphSAGE",         "Graph SAmple and agGrEgate. A Graph Neural Network that updates each node's embedding by aggregating neighbour embeddings."),
    ("1-hop",             "One step in the graph. Example: Merchant <- Transaction. A merchant absorbs signals from transactions directly connected to it."),
    ("2-hop",             "Two steps. Merchant <- Transaction <- User. A merchant absorbs user embeddings that have already absorbed transaction signals."),
    ("Cold-start",        "A new entity with no transaction history. No rule engine can score it. GraphSAGE flags it using graph connections alone."),
    ("AUC",               "Area Under the ROC Curve. Classifier quality from 0.5 (random) to 1.0 (perfect). Higher = better fraud separability."),
    ("ROC Curve",         "Receiver Operating Characteristic. Plots true positive rate vs false positive rate across all decision thresholds."),
    ("RAG",               "Retrieval-Augmented Generation. Using vector search to find relevant graph context, then grounding an LLM response with it."),
    ("Message Passing",   "The core GNN operation: each node receives messages from its neighbours and updates its own representation."),
]

for term, definition in terms:
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(*BRAND_BLUE)
    pdf.cell(42, 5, term, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(*DARK_GREY)
    pdf.multi_cell(0, 5, definition)
    pdf.ln(1)

# ── save ─────────────────────────────────────────────────────────────────────
pdf.output(OUT)
print(f"PDF saved: {OUT}")
