from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SOURCE_FILE = DATA_DIR / "synthetic_transactions_5000_new.csv"
OUTPUT_FILE = DATA_DIR / "embedding_prep_transactions.csv"

MCC_DESCRIPTIONS = {
    "5411": "grocery retail",
    "5541": "fuel and convenience",
    "4511": "air travel",
    "7011": "lodging and hospitality",
    "5814": "quick service dining",
    "5812": "restaurant dining",
    "8099": "healthcare services",
    "5912": "pharmacy and wellness",
    "5651": "fashion retail",
    "5732": "consumer electronics",
    "4121": "ride-hailing and local transport",
    "8220": "education services",
    "4899": "digital subscription services",
    "5311": "general retail",
    "6012": "financial services",
}


def amount_band(amount: float) -> str:
    if amount < 20:
        return "micro"
    if amount < 100:
        return "small-ticket"
    if amount < 500:
        return "mid-value"
    if amount < 2000:
        return "high-value"
    return "very high-value"


def amount_band_score(label: str) -> int:
    return {
        "micro": 1,
        "small-ticket": 2,
        "mid-value": 3,
        "high-value": 4,
        "very high-value": 5,
    }[label]


def card_type_text(card_type: str) -> str:
    return {
        "DEBIT": "debit card",
        "CREDIT": "credit card",
        "PREPAID": "prepaid card",
    }[card_type]


def time_of_day(hour: int) -> str:
    if 0 <= hour < 6:
        return "late-night"
    if 6 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "late-night"


def weekend_flag(dt: datetime) -> str:
    return "weekend" if dt.weekday() >= 5 else "weekday"


def risk_tags(row: dict[str, str], amount: float, dt: datetime) -> list[str]:
    tags: list[str] = []
    mcc = row["merchant_category_code"]
    if amount >= 2000:
        tags.append("very high-value")
    elif amount >= 500:
        tags.append("high-value")
    if mcc in {"4511", "7011"}:
        tags.append("travel-related")
    if mcc == "6012":
        tags.append("cash-like financial services")
    if mcc == "5732":
        tags.append("premium electronics")
    if mcc == "4899":
        tags.append("digital recurring")
    if row["card_type"] == "PREPAID":
        tags.append("prepaid instrument")
    if dt.hour < 6:
        tags.append("late-night activity")
    if dt.weekday() >= 5:
        tags.append("weekend spend")
    return tags or ["everyday consumer spend"]


def build_behavior_text(row: dict[str, str], amount: float, dt: datetime) -> str:
    category_text = MCC_DESCRIPTIONS[row["merchant_category_code"]]
    return (
        f"This transaction was a {amount_band(amount)} {card_type_text(row['card_type'])} payment of "
        f"{row['Transaction_Amount']} {row['transaction_currency_code']} at {row['merchant_name']}, "
        f"a {category_text} merchant in {row['merchant_city']}, {row['merchant_country_code']}, "
        f"within the {row['merchant_region_code']} region. It took place on {row['transaction_date']} "
        f"during {time_of_day(dt.hour)} {weekend_flag(dt)} hours."
    )


def build_risk_text(row: dict[str, str], amount: float, dt: datetime) -> str:
    category_text = MCC_DESCRIPTIONS[row["merchant_category_code"]]
    tags_text = ", ".join(risk_tags(row, amount, dt))
    return (
        f"This transaction appears to be a {amount_band(amount)} {category_text} payment using a "
        f"{card_type_text(row['card_type'])}. It occurred at {row['merchant_name']} in "
        f"{row['merchant_city']}, {row['merchant_country_code']}, within the "
        f"{row['merchant_region_code']} region, on {row['transaction_date']} during "
        f"{time_of_day(dt.hour)} {weekend_flag(dt)} hours. The transaction was processed in "
        f"{row['transaction_currency_code']} through issuer {row['issr_id']} and acquirer "
        f"{row['acquirer_id']}, and can be described as {tags_text}."
    )


def main() -> None:
    with SOURCE_FILE.open("r", newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    output_rows: list[dict[str, str | int | float]] = []
    for row in rows:
        dt = datetime.strptime(
            f"{row['transaction_date']}T{row['transaction_time']}",
            "%Y-%m-%dT%H:%M:%S",
        )
        amount = float(row["Transaction_Amount"])
        band = amount_band(amount)
        tags = risk_tags(row, amount, dt)
        output_rows.append(
            {
                "tran_sequence_number": row["tran_sequence_number"],
                "userid": row["userid"],
                "merchant_id": row["merchant_id"],
                "merchant_name": row["merchant_name"],
                "merchant_category_code": row["merchant_category_code"],
                "merchant_category_text": MCC_DESCRIPTIONS[row["merchant_category_code"]],
                "merchant_city": row["merchant_city"],
                "merchant_country_code": row["merchant_country_code"],
                "merchant_region_code": row["merchant_region_code"],
                "transaction_date": row["transaction_date"],
                "transaction_time": row["transaction_time"],
                "transaction_currency_code": row["transaction_currency_code"],
                "transaction_amount": row["Transaction_Amount"],
                "amount_band": band,
                "amount_band_score": amount_band_score(band),
                "card_type": row["card_type"],
                "card_type_text": card_type_text(row["card_type"]),
                "time_of_day": time_of_day(dt.hour),
                "day_type": weekend_flag(dt),
                "hour_of_day": dt.hour,
                "risk_tags": "|".join(tags),
                "transaction_narration": row["transaction_narration"],
                "transaction_text_behavior": build_behavior_text(row, amount, dt),
                "transaction_text_risk": build_risk_text(row, amount, dt),
            }
        )

    fieldnames = [
        "tran_sequence_number",
        "userid",
        "merchant_id",
        "merchant_name",
        "merchant_category_code",
        "merchant_category_text",
        "merchant_city",
        "merchant_country_code",
        "merchant_region_code",
        "transaction_date",
        "transaction_time",
        "transaction_currency_code",
        "transaction_amount",
        "amount_band",
        "amount_band_score",
        "card_type",
        "card_type_text",
        "time_of_day",
        "day_type",
        "hour_of_day",
        "risk_tags",
        "transaction_narration",
        "transaction_text_behavior",
        "transaction_text_risk",
    ]

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Wrote {len(output_rows)} embedding-ready rows to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
