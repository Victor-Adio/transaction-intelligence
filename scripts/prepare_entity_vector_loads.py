from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DEFAULT_OUTPUT_DIR = DATA_DIR / "vector_loads"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Format embedding CSVs for TigerGraph vector loading.",
    )
    parser.add_argument("--input", type=Path, required=True, help="Embedding CSV input path.")
    parser.add_argument("--id-column", required=True, help="Identifier column in the embedding CSV.")
    parser.add_argument(
        "--mapping",
        nargs="+",
        required=True,
        help="Mappings of text_column=vector_attribute, e.g. transaction_text_risk=risk_emb",
    )
    parser.add_argument(
        "--prefix",
        required=True,
        help="Output filename prefix, e.g. transactions, merchants, or users.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for TigerGraph-ready vector load files.",
    )
    return parser.parse_args()


def parse_mapping(pairs: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Invalid mapping '{pair}'. Expected text_column=attribute_name")
        text_column, attribute_name = pair.split("=", 1)
        mapping[text_column] = attribute_name
    return mapping


def vector_to_pipe_string(vector_json: str) -> str:
    vector = json.loads(vector_json)
    return "|".join(str(value) for value in vector)


def main() -> None:
    args = parse_args()
    mapping = parse_mapping(args.mapping)

    with args.input.open("r", newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    args.output_dir.mkdir(parents=True, exist_ok=True)

    grouped_rows: dict[str, list[dict[str, str]]] = {text_column: [] for text_column in mapping}
    for row in rows:
        text_column = row["text_column"]
        if text_column in grouped_rows:
            grouped_rows[text_column].append(row)

    for text_column, rows_for_column in grouped_rows.items():
        attribute_name = mapping[text_column]
        output_path = args.output_dir / f"{args.prefix}_{attribute_name}.csv"
        with output_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=[
                    args.id_column,
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
                        args.id_column: row[args.id_column],
                        attribute_name: vector_to_pipe_string(row["embedding_vector"]),
                        "embedding_model": row["embedding_model"],
                        "embedding_dimension": row["embedding_dimension"],
                        "normalized": row["normalized"],
                    }
                )
        print(f"Wrote {len(rows_for_column)} rows to {output_path}")


if __name__ == "__main__":
    main()
