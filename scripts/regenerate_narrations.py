"""
Regenerate the transaction_narration column in synthetic_transactions_5000_new.csv
with realistic, varied, category-specific narrations that read like actual
bank-app transaction descriptions.

Run: python scripts/regenerate_narrations.py
"""
from __future__ import annotations

import csv
import random
import string
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "synthetic_transactions_5000_new.csv"
OUTPUT = ROOT / "data" / "synthetic_transactions_5000_new.csv"   # overwrite in-place

random.seed(42)

# ── Reference data ──────────────────────────────────────────────────────────

MCC_CATEGORY = {
    "5411": "grocery",
    "5541": "fuel",
    "4511": "airline",
    "7011": "hotel",
    "5814": "dining",
    "5812": "restaurant",
    "8099": "healthcare",
    "5912": "pharmacy",
    "5651": "fashion",
    "5732": "electronics",
    "4121": "transport",
    "8220": "education",
    "4899": "subscription",
    "5311": "retail",
    "6012": "financial",
}

CURRENCY_SYMBOL = {
    "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "SGD": "S$",
    "AED": "AED", "SAR": "SAR", "NGN": "₦", "ZAR": "R",
    "AUD": "A$", "CAD": "CA$", "CHF": "CHF",
}

CARD_ABBREV = {
    "CREDIT": "Visa Credit",
    "DEBIT":  "Mastercard Debit",
    "PREPAID": "Prepaid Card",
}

CARD_SHORT = {
    "CREDIT": "Credit",
    "DEBIT":  "Debit",
    "PREPAID": "Prepaid",
}

CARD_CHANNEL = {
    "CREDIT":  ["contactless", "chip & PIN", "online", "tap-to-pay", "swipe"],
    "DEBIT":   ["contactless", "chip & PIN", "ATM withdrawal", "tap-to-pay", "direct debit"],
    "PREPAID": ["contactless", "online", "tap-to-pay"],
}


def _ref(n: int = 8) -> str:
    """Generate a random alphanumeric reference."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


def _fmt_date(date_str: str) -> str:
    """'2025-02-13' → '13 Feb 2025'"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%-d %b %Y")
    except Exception:
        return date_str


def _fmt_amount(amount: str, currency: str) -> str:
    try:
        val = float(amount)
        sym = CURRENCY_SYMBOL.get(currency, currency)
        if val == int(val):
            return f"{sym}{int(val):,}"
        return f"{sym}{val:,.2f}"
    except Exception:
        return f"{currency} {amount}"


def _channel(card_type: str) -> str:
    return random.choice(CARD_CHANNEL.get(card_type, ["chip & PIN"]))


def _clean_name(name: str) -> str:
    """Strip trailing ID suffix like 'ElectroHub Madrid 100' → 'ElectroHub Madrid'."""
    parts = name.rsplit(" ", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0]
    return name


# ── Template builders by category ──────────────────────────────────────────

def _grocery(row: dict, amt: str, date: str, currency: str) -> str:
    name = _clean_name(row["merchant_name"])
    city = row["merchant_city"]
    channel = _channel(row["card_type"])
    templates = [
        f"Grocery purchase at {name}, {city} — {_fmt_amount(amt, currency)} via {channel} on {_fmt_date(date)}.",
        f"{_fmt_amount(amt, currency)} charged to your {CARD_SHORT[row['card_type']]} card at {name} ({city}) on {_fmt_date(date)}. Ref: {_ref()}.",
        f"Supermarket spend: {name} · {city} · {_fmt_amount(amt, currency)} · {_fmt_date(date)} · {channel.capitalize()}.",
        f"In-store grocery payment to {name} in {city} for {_fmt_amount(amt, currency)} on {_fmt_date(date)}.",
    ]
    return random.choice(templates)


def _fuel(row: dict, amt: str, date: str, currency: str) -> str:
    name = _clean_name(row["merchant_name"])
    city = row["merchant_city"]
    templates = [
        f"Fuel & convenience purchase at {name}, {city} — {_fmt_amount(amt, currency)} on {_fmt_date(date)}. Ref: {_ref(6)}.",
        f"Petrol station charge: {name} · {city} · {_fmt_amount(amt, currency)} · {_fmt_date(date)}.",
        f"{_fmt_amount(amt, currency)} {CARD_SHORT[row['card_type']]} payment at {name} ({city}) fuel station.",
        f"Forecourt transaction at {name}, {city} — {_fmt_amount(amt, currency)} — {_fmt_date(date)}.",
    ]
    return random.choice(templates)


def _airline(row: dict, amt: str, date: str, currency: str) -> str:
    name = _clean_name(row["merchant_name"])
    city = row["merchant_city"]
    pnr = _ref(6)
    templates = [
        f"Flight booking at {name} ({city}) — {_fmt_amount(amt, currency)} charged on {_fmt_date(date)}. PNR: {pnr}.",
        f"Airline ticket: {name} · {_fmt_amount(amt, currency)} · {_fmt_date(date)} · Booking ref {pnr}.",
        f"{_fmt_amount(amt, currency)} deducted for air travel via {name}, {city}, on {_fmt_date(date)}.",
        f"Travel purchase — {name} ({city}): {_fmt_amount(amt, currency)} on {_fmt_date(date)} using {CARD_ABBREV[row['card_type']]}. Ref: {pnr}.",
    ]
    return random.choice(templates)


def _hotel(row: dict, amt: str, date: str, currency: str) -> str:
    name = _clean_name(row["merchant_name"])
    city = row["merchant_city"]
    conf = _ref(7)
    templates = [
        f"Hotel charge at {name}, {city} — {_fmt_amount(amt, currency)} on {_fmt_date(date)}. Confirmation: {conf}.",
        f"Accommodation: {name} · {city} · {_fmt_amount(amt, currency)} · {_fmt_date(date)}.",
        f"Lodging payment to {name} ({city}) of {_fmt_amount(amt, currency)} on {_fmt_date(date)} — Ref: {conf}.",
        f"{_fmt_amount(amt, currency)} charged by {name} hotel, {city}, for stay on {_fmt_date(date)}.",
    ]
    return random.choice(templates)


def _dining(row: dict, amt: str, date: str, currency: str) -> str:
    name = _clean_name(row["merchant_name"])
    city = row["merchant_city"]
    channel = _channel(row["card_type"])
    templates = [
        f"Dining at {name}, {city} — {_fmt_amount(amt, currency)} via {channel} on {_fmt_date(date)}.",
        f"Restaurant bill: {name} · {city} · {_fmt_amount(amt, currency)} · {_fmt_date(date)}.",
        f"{_fmt_amount(amt, currency)} food & beverage charge at {name} ({city}) on {_fmt_date(date)}.",
        f"Food & drink purchase at {name}, {city} — {_fmt_amount(amt, currency)} — {_fmt_date(date)}. Ref: {_ref(6)}.",
    ]
    return random.choice(templates)


def _healthcare(row: dict, amt: str, date: str, currency: str) -> str:
    name = _clean_name(row["merchant_name"])
    city = row["merchant_city"]
    templates = [
        f"Medical services at {name}, {city} — {_fmt_amount(amt, currency)} on {_fmt_date(date)}.",
        f"Healthcare payment: {name} · {city} · {_fmt_amount(amt, currency)} · {_fmt_date(date)}. Ref: {_ref(7)}.",
        f"{_fmt_amount(amt, currency)} charged for health & medical services at {name} ({city}) on {_fmt_date(date)}.",
        f"Clinic/hospital charge from {name}, {city} — {_fmt_amount(amt, currency)} — {_fmt_date(date)}.",
    ]
    return random.choice(templates)


def _pharmacy(row: dict, amt: str, date: str, currency: str) -> str:
    name = _clean_name(row["merchant_name"])
    city = row["merchant_city"]
    templates = [
        f"Pharmacy purchase at {name}, {city} — {_fmt_amount(amt, currency)} on {_fmt_date(date)}.",
        f"Wellness & pharmacy: {name} · {city} · {_fmt_amount(amt, currency)} · {_fmt_date(date)}.",
        f"{_fmt_amount(amt, currency)} {CARD_SHORT[row['card_type']]} payment at {name} pharmacy, {city}.",
        f"Over-the-counter purchase at {name} ({city}) — {_fmt_amount(amt, currency)} — {_fmt_date(date)}.",
    ]
    return random.choice(templates)


def _fashion(row: dict, amt: str, date: str, currency: str) -> str:
    name = _clean_name(row["merchant_name"])
    city = row["merchant_city"]
    channel = _channel(row["card_type"])
    templates = [
        f"Fashion & apparel purchase at {name}, {city} — {_fmt_amount(amt, currency)} via {channel} on {_fmt_date(date)}.",
        f"Retail clothing: {name} · {city} · {_fmt_amount(amt, currency)} · {_fmt_date(date)}. Ref: {_ref(6)}.",
        f"{_fmt_amount(amt, currency)} charged to your {CARD_SHORT[row['card_type']]} card at {name} ({city}).",
        f"In-store fashion purchase at {name}, {city} — {_fmt_amount(amt, currency)} on {_fmt_date(date)}.",
    ]
    return random.choice(templates)


def _electronics(row: dict, amt: str, date: str, currency: str) -> str:
    name = _clean_name(row["merchant_name"])
    city = row["merchant_city"]
    channel = _channel(row["card_type"])
    templates = [
        f"Electronics purchase at {name}, {city} — {_fmt_amount(amt, currency)} via {channel} on {_fmt_date(date)}.",
        f"Consumer electronics: {name} · {city} · {_fmt_amount(amt, currency)} · {_fmt_date(date)}. Ref: {_ref()}.",
        f"{_fmt_amount(amt, currency)} {CARD_SHORT[row['card_type']]} payment at {name} electronics store, {city}.",
        f"High-value electronics charge at {name} ({city}) — {_fmt_amount(amt, currency)} — {_fmt_date(date)}.",
    ]
    return random.choice(templates)


def _transport(row: dict, amt: str, date: str, currency: str) -> str:
    name = _clean_name(row["merchant_name"])
    city = row["merchant_city"]
    templates = [
        f"Ride & transport: {name} ({city}) — {_fmt_amount(amt, currency)} on {_fmt_date(date)}.",
        f"Taxi/ride-hailing charge from {name}, {city} — {_fmt_amount(amt, currency)} — {_fmt_date(date)}.",
        f"{_fmt_amount(amt, currency)} transport payment via {name}, {city}, on {_fmt_date(date)}.",
        f"Local transport: {name} · {city} · {_fmt_amount(amt, currency)} · {_fmt_date(date)}. Ref: {_ref(6)}.",
    ]
    return random.choice(templates)


def _education(row: dict, amt: str, date: str, currency: str) -> str:
    name = _clean_name(row["merchant_name"])
    city = row["merchant_city"]
    ref = _ref(8)
    templates = [
        f"Education payment to {name}, {city} — {_fmt_amount(amt, currency)} on {_fmt_date(date)}. Invoice: {ref}.",
        f"Tuition/course fee: {name} · {city} · {_fmt_amount(amt, currency)} · {_fmt_date(date)}.",
        f"{_fmt_amount(amt, currency)} charged by {name} ({city}) for educational services on {_fmt_date(date)}.",
        f"Academic services at {name}, {city} — {_fmt_amount(amt, currency)} — {_fmt_date(date)}. Ref: {ref}.",
    ]
    return random.choice(templates)


def _subscription(row: dict, amt: str, date: str, currency: str) -> str:
    name = _clean_name(row["merchant_name"])
    city = row["merchant_city"]
    templates = [
        f"Recurring subscription: {name} — {_fmt_amount(amt, currency)} auto-debited on {_fmt_date(date)}.",
        f"Digital subscription charge from {name} ({city}) — {_fmt_amount(amt, currency)} on {_fmt_date(date)}.",
        f"Monthly plan renewal: {name} · {_fmt_amount(amt, currency)} · {_fmt_date(date)}. Sub ref: {_ref(6)}.",
        f"{_fmt_amount(amt, currency)} deducted for {name} digital subscription on {_fmt_date(date)}.",
    ]
    return random.choice(templates)


def _retail(row: dict, amt: str, date: str, currency: str) -> str:
    name = _clean_name(row["merchant_name"])
    city = row["merchant_city"]
    channel = _channel(row["card_type"])
    templates = [
        f"Retail purchase at {name}, {city} — {_fmt_amount(amt, currency)} via {channel} on {_fmt_date(date)}.",
        f"General retail: {name} · {city} · {_fmt_amount(amt, currency)} · {_fmt_date(date)}. Ref: {_ref(6)}.",
        f"{_fmt_amount(amt, currency)} {CARD_SHORT[row['card_type']]} payment at {name}, {city}.",
        f"In-store purchase at {name} ({city}) — {_fmt_amount(amt, currency)} — {_fmt_date(date)}.",
    ]
    return random.choice(templates)


def _financial(row: dict, amt: str, date: str, currency: str) -> str:
    name = _clean_name(row["merchant_name"])
    city = row["merchant_city"]
    ref  = _ref(10)
    templates = [
        f"Financial services payment to {name} ({city}) — {_fmt_amount(amt, currency)} on {_fmt_date(date)}. Ref: {ref}.",
        f"Fund transfer / payment: {name} · {city} · {_fmt_amount(amt, currency)} · {_fmt_date(date)}.",
        f"{_fmt_amount(amt, currency)} cash-equivalent transaction via {name}, {city}, on {_fmt_date(date)}. Ref: {ref}.",
        f"Financial transaction at {name} ({city}) — {_fmt_amount(amt, currency)} — {_fmt_date(date)}. Auth: {ref[:6]}.",
    ]
    return random.choice(templates)


# ── Dispatch ────────────────────────────────────────────────────────────────

_BUILDERS = {
    "grocery":      _grocery,
    "fuel":         _fuel,
    "airline":      _airline,
    "hotel":        _hotel,
    "dining":       _dining,
    "restaurant":   _dining,
    "healthcare":   _healthcare,
    "pharmacy":     _pharmacy,
    "fashion":      _fashion,
    "electronics":  _electronics,
    "transport":    _transport,
    "education":    _education,
    "subscription": _subscription,
    "retail":       _retail,
    "financial":    _financial,
}


def build_narration(row: dict) -> str:
    cat = MCC_CATEGORY.get(row["merchant_category_code"], "retail")
    builder = _BUILDERS.get(cat, _retail)
    return builder(row, row["Transaction_Amount"], row["transaction_date"], row["transaction_currency_code"])


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    with open(SOURCE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    fieldnames = list(rows[0].keys())

    updated = 0
    for row in rows:
        new_narration = build_narration(row)
        row["transaction_narration"] = new_narration
        updated += 1

    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Updated {updated:,} narrations in {OUTPUT}")
    print("\nSample narrations:")
    for row in random.sample(rows, min(10, len(rows))):
        cat = MCC_CATEGORY.get(row["merchant_category_code"], "?")
        print(f"  [{cat:12s}] {row['transaction_narration']}")


if __name__ == "__main__":
    main()
