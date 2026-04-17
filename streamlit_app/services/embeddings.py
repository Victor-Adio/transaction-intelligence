from __future__ import annotations

class QueryEmbedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: str | None = None) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name, device=device)

    def encode_query(self, text: str) -> list[float]:
        vector = self.model.encode(
            text,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vector.tolist()
