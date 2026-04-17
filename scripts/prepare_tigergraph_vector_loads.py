from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
INPUT_FILE = DATA_DIR / "transaction_embeddings.csv"
OUTPUT_DIR = DATA_DIR / "vector_loads"

TEXT_COLUMN_TO_ATTRIBUTE = {
    "transaction_text_risk": "risk_emb",
    "transaction_text_behavior": "behavior_emb",
}


def vector_to_pipe_string(vector_json: str) -> str:
    vector = json.loads(vector_json)
    return "|".join(str(value) for value in vector)


def main() -> None:
    with INPUT_FILE.open("r", newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    grouped_rows: dict[str, list[dict[str, str]]] = {
        text_column: [] for text_column in TEXT_COLUMN_TO_ATTRIBUTE
    }
    for row in rows:
        text_column = row["text_column"]
        if text_column in grouped_rows:
            grouped_rows[text_column].append(row)

    for text_column, rows_for_column in grouped_rows.items():
        attribute_name = TEXT_COLUMN_TO_ATTRIBUTE[text_column]
        output_path = OUTPUT_DIR / f"transactions_{attribute_name}.csv"
        with output_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=[
                    "tran_sequence_number",
                    attribute_name,
                    "embedding_model",
                    "embedding_dimension",
                    "normalized",
                ],
            )
            writer.writeheader()
            for row in rows_for_column:
                writer.writerow(
                    {
                        "tran_sequence_number": row["tran_sequence_number"],
                        attribute_name: vector_to_pipe_string(row["embedding_vector"]),
                        "embedding_model": row["embedding_model"],
                        "embedding_dimension": row["embedding_dimension"],
                        "normalized": row["normalized"],
                    }
                )
        print(f"Wrote {len(rows_for_column)} rows to {output_path}")


if __name__ == "__main__":
    main()
