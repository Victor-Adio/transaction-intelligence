from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SOURCE_FILE = DATA_DIR / "embedding_prep_transactions.csv"
MERCHANT_OUTPUT = DATA_DIR / "embedding_prep_merchants.csv"
USER_OUTPUT = DATA_DIR / "embedding_prep_users.csv"


def safe_mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def amount_profile(avg_amount: float) -> str:
    if avg_amount < 20:
        return "micro-ticket"
    if avg_amount < 100:
        return "small-ticket"
    if avg_amount < 500:
        return "mid-value"
    if avg_amount < 2000:
        return "high-value"
    return "very high-value"


def build_merchant_text(summary: dict[str, object]) -> str:
    return (
        f"{summary['merchant_name']} is a {summary['merchant_category_text']} merchant in "
        f"{summary['merchant_city']}, {summary['merchant_country_code']}, within the "
        f"{summary['merchant_region_code']} region. Across {summary['transaction_count']} transactions, "
        f"it shows {summary['amount_profile']} spend with an average transaction value of "
        f"{summary['average_amount']} {summary['preferred_currency_code']}. The merchant most often sees "
        f"{summary['dominant_card_type']} usage and is commonly associated with {summary['top_risk_tags']}."
    )


def build_user_text(summary: dict[str, object]) -> str:
    return (
        f"User {summary['userid']} shows a {summary['spend_profile']} spending profile across "
        f"{summary['transaction_count']} transactions totaling {summary['total_spend']} "
        f"{summary['preferred_currency_code']}. The user most often transacts in "
        f"{summary['dominant_region']} with {summary['dominant_card_type']} payments, favors "
        f"{summary['favorite_category_text']}, and is most active during {summary['dominant_time_of_day']} "
        f"{summary['dominant_day_type']} periods. Common patterns include {summary['top_risk_tags']}."
    )


def main() -> None:
    with SOURCE_FILE.open("r", newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    merchant_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    user_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        merchant_rows[row["merchant_id"]].append(row)
        user_rows[row["userid"]].append(row)

    merchant_output_rows: list[dict[str, object]] = []
    for merchant_id, merchant_txns in sorted(merchant_rows.items()):
        first = merchant_txns[0]
        amounts = [float(row["transaction_amount"]) for row in merchant_txns]
        card_counter = Counter(row["card_type_text"] for row in merchant_txns)
        risk_counter = Counter(
            tag
            for row in merchant_txns
            for tag in row["risk_tags"].split("|")
            if tag
        )
        summary = {
            "merchant_id": merchant_id,
            "merchant_name": first["merchant_name"],
            "merchant_category_text": first["merchant_category_text"],
            "merchant_city": first["merchant_city"],
            "merchant_country_code": first["merchant_country_code"],
            "merchant_region_code": first["merchant_region_code"],
            "transaction_count": len(merchant_txns),
            "average_amount": safe_mean(amounts),
            "preferred_currency_code": first["transaction_currency_code"],
            "dominant_card_type": card_counter.most_common(1)[0][0],
            "amount_profile": amount_profile(safe_mean(amounts)),
            "top_risk_tags": ", ".join(tag for tag, _ in risk_counter.most_common(3)),
        }
        merchant_output_rows.append(
            {
                **summary,
                "merchant_text_summary": build_merchant_text(summary),
            }
        )

    user_output_rows: list[dict[str, object]] = []
    for user_id, user_txns in sorted(user_rows.items()):
        amounts = [float(row["transaction_amount"]) for row in user_txns]
        card_counter = Counter(row["card_type_text"] for row in user_txns)
        region_counter = Counter(row["merchant_region_code"] for row in user_txns)
        category_counter = Counter(row["merchant_category_text"] for row in user_txns)
        time_counter = Counter(row["time_of_day"] for row in user_txns)
        day_type_counter = Counter(row["day_type"] for row in user_txns)
        currency_counter = Counter(row["transaction_currency_code"] for row in user_txns)
        risk_counter = Counter(
            tag
            for row in user_txns
            for tag in row["risk_tags"].split("|")
            if tag
        )
        total_spend = round(sum(amounts), 2)
        summary = {
            "userid": user_id,
            "transaction_count": len(user_txns),
            "total_spend": total_spend,
            "preferred_currency_code": currency_counter.most_common(1)[0][0],
            "dominant_region": region_counter.most_common(1)[0][0],
            "dominant_card_type": card_counter.most_common(1)[0][0],
            "favorite_category_text": category_counter.most_common(1)[0][0],
            "dominant_time_of_day": time_counter.most_common(1)[0][0],
            "dominant_day_type": day_type_counter.most_common(1)[0][0],
            "spend_profile": amount_profile(safe_mean(amounts)),
            "top_risk_tags": ", ".join(tag for tag, _ in risk_counter.most_common(3)),
        }
        user_output_rows.append(
            {
                **summary,
                "user_text_summary": build_user_text(summary),
            }
        )

    with MERCHANT_OUTPUT.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "merchant_id",
                "merchant_name",
                "merchant_category_text",
                "merchant_city",
                "merchant_country_code",
                "merchant_region_code",
                "transaction_count",
                "average_amount",
                "preferred_currency_code",
                "dominant_card_type",
                "amount_profile",
                "top_risk_tags",
                "merchant_text_summary",
            ],
        )
        writer.writeheader()
        writer.writerows(merchant_output_rows)

    with USER_OUTPUT.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "userid",
                "transaction_count",
                "total_spend",
                "preferred_currency_code",
                "dominant_region",
                "dominant_card_type",
                "favorite_category_text",
                "dominant_time_of_day",
                "dominant_day_type",
                "spend_profile",
                "top_risk_tags",
                "user_text_summary",
            ],
        )
        writer.writeheader()
        writer.writerows(user_output_rows)

    print(f"Wrote {len(merchant_output_rows)} merchant summaries to {MERCHANT_OUTPUT}")
    print(f"Wrote {len(user_output_rows)} user summaries to {USER_OUTPUT}")


if __name__ == "__main__":
    main()
