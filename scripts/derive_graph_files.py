from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MASTER_FILE = DATA_DIR / "synthetic_transactions_5000.csv"
VERTEX_DIR = DATA_DIR / "vertices"
EDGE_DIR = DATA_DIR / "edges"


def location_id(city: str, country_code: str) -> str:
    safe_city = city.upper().replace(" ", "_")
    return f"LOC_{country_code}_{safe_city}"


def datetime_id(date_value: str, time_value: str) -> str:
    return f"DT_{date_value.replace('-', '')}_{time_value.replace(':', '')}"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    with MASTER_FILE.open("r", newline="", encoding="utf-8") as csv_file:
        transactions = list(csv.DictReader(csv_file))

    users: dict[str, dict[str, object]] = {}
    merchants: dict[str, dict[str, object]] = {}
    locations: dict[str, dict[str, object]] = {}
    datetimes: dict[str, dict[str, object]] = {}
    transaction_vertices: list[dict[str, object]] = []

    user_profile_counter: dict[str, Counter[tuple[str, str, str]]] = defaultdict(Counter)
    user_total_spend: dict[str, float] = defaultdict(float)
    user_transaction_count: Counter[str] = Counter()
    user_first_seen: dict[str, str] = {}
    user_last_seen: dict[str, str] = {}

    user_transaction_edges: list[dict[str, str]] = []
    transaction_merchant_edges: list[dict[str, str]] = []
    transaction_location_edges: list[dict[str, str]] = []
    transaction_datetime_edges: list[dict[str, str]] = []
    merchant_location_edges: dict[tuple[str, str], dict[str, str]] = {}

    for row in transactions:
        user_id = row["userid"]
        merchant_id = row["merchant_id"]
        txn_id = row["tran_sequence_number"]
        loc_id = location_id(row["merchant_city"], row["merchant_country_code"])
        dt_id = datetime_id(row["transaction_date"], row["transaction_time"])
        timestamp_str = f"{row['transaction_date']}T{row['transaction_time']}"
        ts = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S")
        amount = float(row["Transaction_Amount"])

        user_profile_counter[user_id][
            (
                row["merchant_country_code"],
                row["merchant_region_code"],
                row["transaction_currency_code"],
            )
        ] += 1
        user_total_spend[user_id] += amount
        user_transaction_count[user_id] += 1
        user_first_seen[user_id] = min(user_first_seen.get(user_id, timestamp_str), timestamp_str)
        user_last_seen[user_id] = max(user_last_seen.get(user_id, timestamp_str), timestamp_str)

        merchants[merchant_id] = {
            "merchant_id": merchant_id,
            "merchant_name": row["merchant_name"],
            "merchant_category_code": row["merchant_category_code"],
            "merchant_city": row["merchant_city"],
            "merchant_country_code": row["merchant_country_code"],
            "merchant_region_code": row["merchant_region_code"],
            "ICA_code": row["ICA_code"],
            "issr_id": row["issr_id"],
            "acquirer_id": row["acquirer_id"],
            "location_id": loc_id,
        }

        locations[loc_id] = {
            "location_id": loc_id,
            "merchant_city": row["merchant_city"],
            "merchant_country_code": row["merchant_country_code"],
            "merchant_region_code": row["merchant_region_code"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
        }

        datetimes[dt_id] = {
            "transaction_datetime_id": dt_id,
            "transaction_date": row["transaction_date"],
            "transaction_time": row["transaction_time"],
            "day_of_week": ts.strftime("%A"),
            "month": ts.strftime("%Y-%m"),
            "hour_of_day": ts.strftime("%H"),
            "is_weekend": "true" if ts.weekday() >= 5 else "false",
        }

        transaction_vertices.append(
            {
                "tran_sequence_number": txn_id,
                "Transaction_Amount": row["Transaction_Amount"],
                "transaction_currency_code": row["transaction_currency_code"],
                "card_type": row["card_type"],
                "ICA_code": row["ICA_code"],
                "issr_id": row["issr_id"],
                "acquirer_id": row["acquirer_id"],
                "transaction_date": row["transaction_date"],
                "transaction_time": row["transaction_time"],
                "transaction_narration": row["transaction_narration"],
            }
        )

        user_transaction_edges.append({"userid": user_id, "tran_sequence_number": txn_id})
        transaction_merchant_edges.append({"tran_sequence_number": txn_id, "merchant_id": merchant_id})
        transaction_location_edges.append({"tran_sequence_number": txn_id, "location_id": loc_id})
        transaction_datetime_edges.append(
            {"tran_sequence_number": txn_id, "transaction_datetime_id": dt_id}
        )
        merchant_location_edges[(merchant_id, loc_id)] = {
            "merchant_id": merchant_id,
            "location_id": loc_id,
        }

    for user_id in sorted(user_transaction_count):
        dominant_country, dominant_region, dominant_currency = user_profile_counter[user_id].most_common(1)[0][0]
        users[user_id] = {
            "userid": user_id,
            "home_country_code": dominant_country,
            "home_region_code": dominant_region,
            "preferred_currency_code": dominant_currency,
            "transaction_count": user_transaction_count[user_id],
            "total_spend": round(user_total_spend[user_id], 2),
            "first_seen_timestamp": user_first_seen[user_id],
            "last_seen_timestamp": user_last_seen[user_id],
        }

    write_csv(
        VERTEX_DIR / "users.csv",
        [
            "userid",
            "home_country_code",
            "home_region_code",
            "preferred_currency_code",
            "transaction_count",
            "total_spend",
            "first_seen_timestamp",
            "last_seen_timestamp",
        ],
        [users[user_id] for user_id in sorted(users)],
    )
    write_csv(
        VERTEX_DIR / "merchants.csv",
        [
            "merchant_id",
            "merchant_name",
            "merchant_category_code",
            "merchant_city",
            "merchant_country_code",
            "merchant_region_code",
            "ICA_code",
            "issr_id",
            "acquirer_id",
            "location_id",
        ],
        [merchants[merchant_id] for merchant_id in sorted(merchants)],
    )
    write_csv(
        VERTEX_DIR / "locations.csv",
        [
            "location_id",
            "merchant_city",
            "merchant_country_code",
            "merchant_region_code",
            "latitude",
            "longitude",
        ],
        [locations[loc] for loc in sorted(locations)],
    )
    write_csv(
        VERTEX_DIR / "transaction_datetimes.csv",
        [
            "transaction_datetime_id",
            "transaction_date",
            "transaction_time",
            "day_of_week",
            "month",
            "hour_of_day",
            "is_weekend",
        ],
        [datetimes[dt] for dt in sorted(datetimes)],
    )
    write_csv(
        VERTEX_DIR / "transactions.csv",
        [
            "tran_sequence_number",
            "Transaction_Amount",
            "transaction_currency_code",
            "card_type",
            "ICA_code",
            "issr_id",
            "acquirer_id",
            "transaction_date",
            "transaction_time",
            "transaction_narration",
        ],
        transaction_vertices,
    )

    write_csv(EDGE_DIR / "user_transaction.csv", ["userid", "tran_sequence_number"], user_transaction_edges)
    write_csv(
        EDGE_DIR / "transaction_merchant.csv",
        ["tran_sequence_number", "merchant_id"],
        transaction_merchant_edges,
    )
    write_csv(
        EDGE_DIR / "transaction_location.csv",
        ["tran_sequence_number", "location_id"],
        transaction_location_edges,
    )
    write_csv(
        EDGE_DIR / "transaction_datetime.csv",
        ["tran_sequence_number", "transaction_datetime_id"],
        transaction_datetime_edges,
    )
    write_csv(
        EDGE_DIR / "merchant_location.csv",
        ["merchant_id", "location_id"],
        [merchant_location_edges[key] for key in sorted(merchant_location_edges)],
    )

    print(f"Wrote {len(users)} users")
    print(f"Wrote {len(merchants)} merchants")
    print(f"Wrote {len(locations)} locations")
    print(f"Wrote {len(datetimes)} transaction datetimes")
    print(f"Wrote {len(transaction_vertices)} transactions")
    print(f"Wrote {len(user_transaction_edges)} user-transaction edges")
    print(f"Wrote {len(transaction_merchant_edges)} transaction-merchant edges")
    print(f"Wrote {len(transaction_location_edges)} transaction-location edges")
    print(f"Wrote {len(transaction_datetime_edges)} transaction-datetime edges")
    print(f"Wrote {len(merchant_location_edges)} merchant-location edges")


if __name__ == "__main__":
    main()
