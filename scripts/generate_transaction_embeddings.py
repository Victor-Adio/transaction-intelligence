from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from sentence_transformers import SentenceTransformer


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DEFAULT_INPUT = DATA_DIR / "embedding_prep_transactions.csv"
DEFAULT_OUTPUT = DATA_DIR / "transaction_embeddings.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate embeddings for synthetic transactions.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Input CSV containing embedding-ready transaction text.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output CSV path for generated embeddings.",
    )
    parser.add_argument(
        "--text-columns",
        nargs="+",
        default=["transaction_text_risk", "transaction_text_behavior"],
        help="One or more CSV columns to embed.",
    )
    parser.add_argument(
        "--id-column",
        default="tran_sequence_number",
        help="Identifier column to carry into the output file.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=128,
        help="Batch size for local embedding generation.",
    )
    parser.add_argument(
        "--model",
        default="all-MiniLM-L6-v2",
        help="SentenceTransformers model name.",
    )
    parser.add_argument(
        "--normalize",
        action="store_true",
        default=True,
        help="Normalize embeddings for cosine similarity search.",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Optional torch device override, such as cpu, mps, or cuda.",
    )
    return parser.parse_args()


def read_rows(input_path: Path, id_column: str, text_columns: list[str]) -> list[dict[str, str]]:
    with input_path.open("r", newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    if not rows:
        raise ValueError(f"No rows found in {input_path}")
    if id_column not in rows[0]:
        raise ValueError(f"Missing id column '{id_column}' in {input_path}")
    for text_column in text_columns:
        if text_column not in rows[0]:
            raise ValueError(f"Missing text column '{text_column}' in {input_path}")
        if not any(row[text_column].strip() for row in rows):
            raise ValueError(f"No non-empty values found in text column '{text_column}'")
    return rows


def write_embeddings(output_path: Path, records: list[dict[str, str]]) -> None:
    id_column = records[0]["id_column_name"] if records else "entity_id"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                id_column,
                "text_column",
                "embedding_model",
                "embedding_dimension",
                "normalized",
                "embedding_vector",
            ],
        )
        writer.writeheader()
        sanitized_records = []
        for record in records:
            sanitized_record = dict(record)
            sanitized_record.pop("id_column_name", None)
            sanitized_records.append(sanitized_record)
        writer.writerows(sanitized_records)


def main() -> int:
    args = parse_args()
    id_column = args.id_column
    rows = read_rows(args.input, id_column, args.text_columns)
    model = SentenceTransformer(args.model, device=args.device)
    output_records: list[dict[str, str]] = []

    for text_column in args.text_columns:
        eligible_rows = [row for row in rows if row[text_column].strip()]
        texts = [row[text_column] for row in eligible_rows]
        embeddings = model.encode(
            texts,
            batch_size=args.batch_size,
            normalize_embeddings=args.normalize,
            show_progress_bar=True,
        )
        for row, embedding in zip(eligible_rows, embeddings, strict=True):
            output_records.append(
                {
                    id_column: row[id_column],
                    "id_column_name": id_column,
                    "text_column": text_column,
                    "embedding_model": args.model,
                    "normalized": str(args.normalize).lower(),
                    "embedding_dimension": str(len(embedding)),
                    "embedding_vector": json.dumps(embedding.tolist(), separators=(",", ":")),
                }
            )
        print(
            f"Embedded column '{text_column}' "
            f"({len(eligible_rows)} rows, cumulative {len(output_records)})"
        )

    write_embeddings(args.output, output_records)
    print(f"Wrote {len(output_records)} embeddings to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
