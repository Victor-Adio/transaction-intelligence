from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class City:
    name: str
    country_code: str
    region_code: str
    currency_code: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class MerchantTemplate:
    prefix: str
    mcc: str
    amount_min: float
    amount_max: float
    amount_shape: float
    card_type_weights: dict[str, int]


@dataclass(frozen=True)
class Merchant:
    merchant_id: str
    merchant_name: str
    city: City
    mcc: str
    ica_code: str
    acquirer_id: str
    issr_id: str


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_FILE = DATA_DIR / "synthetic_transactions_5000.csv"

SEED = 4222
TRANSACTION_COUNT = 5000
USER_COUNT = 850
MERCHANT_COUNT = 220

CITY_POOL = [
    City("New York", "US", "NA", "USD", 40.7128, -74.0060),
    City("San Francisco", "US", "NA", "USD", 37.7749, -122.4194),
    City("Chicago", "US", "NA", "USD", 41.8781, -87.6298),
    City("Toronto", "CA", "NA", "CAD", 43.6532, -79.3832),
    City("Vancouver", "CA", "NA", "CAD", 49.2827, -123.1207),
    City("London", "GB", "EMEA", "GBP", 51.5074, -0.1278),
    City("Manchester", "GB", "EMEA", "GBP", 53.4808, -2.2426),
    City("Paris", "FR", "EMEA", "EUR", 48.8566, 2.3522),
    City("Berlin", "DE", "EMEA", "EUR", 52.5200, 13.4050),
    City("Madrid", "ES", "EMEA", "EUR", 40.4168, -3.7038),
    City("Amsterdam", "NL", "EMEA", "EUR", 52.3676, 4.9041),
    City("Dubai", "AE", "MEA", "AED", 25.2048, 55.2708),
    City("Singapore", "SG", "APAC", "SGD", 1.3521, 103.8198),
    City("Sydney", "AU", "APAC", "AUD", -33.8688, 151.2093),
    City("Melbourne", "AU", "APAC", "AUD", -37.8136, 144.9631),
    City("Tokyo", "JP", "APAC", "JPY", 35.6762, 139.6503),
    City("Osaka", "JP", "APAC", "JPY", 34.6937, 135.5023),
    City("Hong Kong", "HK", "APAC", "HKD", 22.3193, 114.1694),
    City("Mumbai", "IN", "APAC", "INR", 19.0760, 72.8777),
    City("Bengaluru", "IN", "APAC", "INR", 12.9716, 77.5946),
]

MERCHANT_TEMPLATES = [
    MerchantTemplate("FreshMart", "5411", 8.0, 220.0, 2.7, {"DEBIT": 55, "CREDIT": 35, "PREPAID": 10}),
    MerchantTemplate("MetroFuel", "5541", 25.0, 180.0, 2.0, {"DEBIT": 45, "CREDIT": 45, "PREPAID": 10}),
    MerchantTemplate("SkyJet Travel", "4511", 180.0, 2400.0, 1.8, {"DEBIT": 5, "CREDIT": 90, "PREPAID": 5}),
    MerchantTemplate("CloudStay", "7011", 90.0, 1800.0, 1.9, {"DEBIT": 10, "CREDIT": 85, "PREPAID": 5}),
    MerchantTemplate("QuickBite", "5814", 6.0, 55.0, 3.1, {"DEBIT": 40, "CREDIT": 40, "PREPAID": 20}),
    MerchantTemplate("UrbanTable", "5812", 18.0, 220.0, 2.1, {"DEBIT": 25, "CREDIT": 60, "PREPAID": 15}),
    MerchantTemplate("MediCare Plus", "8099", 25.0, 550.0, 2.2, {"DEBIT": 25, "CREDIT": 70, "PREPAID": 5}),
    MerchantTemplate("PharmaDirect", "5912", 12.0, 240.0, 2.4, {"DEBIT": 40, "CREDIT": 50, "PREPAID": 10}),
    MerchantTemplate("Luxura Retail", "5651", 40.0, 1400.0, 1.7, {"DEBIT": 10, "CREDIT": 85, "PREPAID": 5}),
    MerchantTemplate("ElectroHub", "5732", 35.0, 2200.0, 1.6, {"DEBIT": 15, "CREDIT": 80, "PREPAID": 5}),
    MerchantTemplate("RideNow", "4121", 7.0, 95.0, 2.6, {"DEBIT": 35, "CREDIT": 30, "PREPAID": 35}),
    MerchantTemplate("EduPrime", "8220", 70.0, 6500.0, 1.3, {"DEBIT": 5, "CREDIT": 90, "PREPAID": 5}),
    MerchantTemplate("StreamSphere", "4899", 4.0, 35.0, 3.3, {"DEBIT": 20, "CREDIT": 55, "PREPAID": 25}),
    MerchantTemplate("MarketSquare", "5311", 15.0, 450.0, 2.3, {"DEBIT": 40, "CREDIT": 45, "PREPAID": 15}),
    MerchantTemplate("FinServe Online", "6012", 25.0, 5000.0, 1.4, {"DEBIT": 20, "CREDIT": 55, "PREPAID": 25}),
]

ISSUER_BY_COUNTRY = {
    "US": ["ISSR_US_101", "ISSR_US_205", "ISSR_US_319"],
    "CA": ["ISSR_CA_110", "ISSR_CA_214"],
    "GB": ["ISSR_GB_118", "ISSR_GB_224"],
    "FR": ["ISSR_FR_126", "ISSR_FR_229"],
    "DE": ["ISSR_DE_132", "ISSR_DE_238"],
    "ES": ["ISSR_ES_145", "ISSR_ES_241"],
    "NL": ["ISSR_NL_149", "ISSR_NL_255"],
    "AE": ["ISSR_AE_152", "ISSR_AE_266"],
    "SG": ["ISSR_SG_158", "ISSR_SG_271"],
    "AU": ["ISSR_AU_163", "ISSR_AU_276"],
    "JP": ["ISSR_JP_174", "ISSR_JP_287"],
    "HK": ["ISSR_HK_181", "ISSR_HK_294"],
    "IN": ["ISSR_IN_188", "ISSR_IN_302"],
}

ACQUIRER_BY_REGION = {
    "NA": ["ACQ_NA_401", "ACQ_NA_402", "ACQ_NA_403"],
    "EMEA": ["ACQ_EMEA_501", "ACQ_EMEA_502", "ACQ_EMEA_503"],
    "MEA": ["ACQ_MEA_601", "ACQ_MEA_602"],
    "APAC": ["ACQ_APAC_701", "ACQ_APAC_702", "ACQ_APAC_703"],
}

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


def build_merchants(rng: random.Random) -> list[Merchant]:
    merchants: list[Merchant] = []
    for idx in range(1, MERCHANT_COUNT + 1):
        template = rng.choice(MERCHANT_TEMPLATES)
        city = rng.choice(CITY_POOL)
        suffix = f"{city.name} {idx:03d}"
        merchant_name = f"{template.prefix} {suffix}"
        merchant_id = f"M{city.country_code}{idx:05d}"
        ica_code = f"ICA{100000 + idx:06d}"[-6:]
        acquirer_id = rng.choice(ACQUIRER_BY_REGION[city.region_code])
        issuer_choices = ISSUER_BY_COUNTRY.get(city.country_code, ["ISSR_GLOBAL_001"])
        issr_id = rng.choice(issuer_choices)
        merchants.append(
            Merchant(
                merchant_id=merchant_id,
                merchant_name=merchant_name,
                city=city,
                mcc=template.mcc,
                ica_code=ica_code,
                acquirer_id=acquirer_id,
                issr_id=issr_id,
            )
        )
    return merchants


def clamp(value: float, floor: float, ceiling: float) -> float:
    return max(floor, min(ceiling, value))


def merchant_template_for_mcc(mcc: str) -> MerchantTemplate:
    for template in MERCHANT_TEMPLATES:
        if template.mcc == mcc:
            return template
    raise ValueError(f"No template found for MCC {mcc}")


def sample_amount(rng: random.Random, template: MerchantTemplate, currency: str) -> float:
    beta_sample = rng.betavariate(1.6, template.amount_shape)
    amount = template.amount_min + (template.amount_max - template.amount_min) * beta_sample
    if currency in {"JPY"}:
        return round(amount)
    if currency in {"INR"}:
        return round(amount, 0)
    return round(amount, 2)


def sample_card_type(rng: random.Random, template: MerchantTemplate) -> str:
    options = list(template.card_type_weights.keys())
    weights = list(template.card_type_weights.values())
    return rng.choices(options, weights=weights, k=1)[0]


def jitter_coordinate(rng: random.Random, base: float, scale: float = 0.04) -> float:
    return round(base + rng.uniform(-scale, scale), 6)


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


def card_type_text(card_type: str) -> str:
    return {
        "DEBIT": "debit card",
        "CREDIT": "credit card",
        "PREPAID": "prepaid card",
    }[card_type]


def time_phrase(transaction_dt: datetime) -> str:
    hour = transaction_dt.hour
    if 0 <= hour < 6:
        return "late-night"
    if 6 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "late-night"


def weekend_phrase(transaction_dt: datetime) -> str:
    return "weekend" if transaction_dt.weekday() >= 5 else "weekday"


def risk_tags(mcc: str, amount: float, card_type: str, transaction_dt: datetime) -> list[str]:
    tags: list[str] = []
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
    if card_type == "PREPAID":
        tags.append("prepaid instrument")
    if transaction_dt.hour < 6:
        tags.append("late-night activity")
    if transaction_dt.weekday() >= 5:
        tags.append("weekend spend")
    return tags or ["everyday consumer spend"]


def build_transaction_narration(
    amount: float,
    currency_code: str,
    card_type: str,
    merchant: Merchant,
    transaction_dt: datetime,
) -> str:
    category_text = MCC_DESCRIPTIONS[merchant.mcc]
    tags_text = ", ".join(risk_tags(merchant.mcc, amount, card_type, transaction_dt))
    return (
        f"This transaction was a {amount_band(amount)} {card_type_text(card_type)} payment of "
        f"{amount} {currency_code} at {merchant.merchant_name}, a {category_text} merchant in "
        f"{merchant.city.name}, {merchant.city.country_code}, within the {merchant.city.region_code} region. "
        f"It took place on {transaction_dt:%Y-%m-%d} during {time_phrase(transaction_dt)} "
        f"{weekend_phrase(transaction_dt)} hours and can be described as {tags_text}."
    )


def main() -> None:
    rng = random.Random(SEED)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    merchants = build_merchants(rng)
    user_ids = [f"U{idx:06d}" for idx in range(1, USER_COUNT + 1)]

    start_dt = datetime(2025, 1, 1, 0, 0, 0)
    end_dt = datetime(2025, 3, 31, 23, 59, 59)
    total_seconds = int((end_dt - start_dt).total_seconds())

    fieldnames = [
        "tran_sequence_number",
        "Transaction_Amount",
        "userid",
        "transaction_time",
        "transaction_date",
        "transaction_currency_code",
        "merchant_name",
        "merchant_city",
        "merchant_id",
        "card_type",
        "latitude",
        "longitude",
        "merchant_category_code",
        "merchant_country_code",
        "merchant_region_code",
        "ICA_code",
        "issr_id",
        "acquirer_id",
        "transaction_narration",
    ]

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()

        for sequence in range(1, TRANSACTION_COUNT + 1):
            merchant = rng.choices(
                merchants,
                weights=[
                    8 if m.city.region_code in {"NA", "EMEA"} else 5
                    for m in merchants
                ],
                k=1,
            )[0]
            template = merchant_template_for_mcc(merchant.mcc)
            user_id = rng.choice(user_ids)
            txn_dt = start_dt + timedelta(seconds=rng.randint(0, total_seconds))
            amount = sample_amount(rng, template, merchant.city.currency_code)
            card_type = sample_card_type(rng, template)

            # Apply small realism adjustments for card type and merchant profile.
            if merchant.mcc in {"4511", "7011", "8220"} and card_type == "DEBIT":
                card_type = "CREDIT"
            if merchant.mcc == "6012" and amount < 100:
                amount = round(clamp(amount + rng.uniform(70, 130), 100, template.amount_max), 2)
            narration = build_transaction_narration(
                amount=amount,
                currency_code=merchant.city.currency_code,
                card_type=card_type,
                merchant=merchant,
                transaction_dt=txn_dt,
            )

            writer.writerow(
                {
                    "tran_sequence_number": f"TXN{txn_dt:%Y%m%d}{sequence:06d}",
                    "Transaction_Amount": amount,
                    "userid": user_id,
                    "transaction_time": txn_dt.strftime("%H:%M:%S"),
                    "transaction_date": txn_dt.strftime("%Y-%m-%d"),
                    "transaction_currency_code": merchant.city.currency_code,
                    "merchant_name": merchant.merchant_name,
                    "merchant_city": merchant.city.name,
                    "merchant_id": merchant.merchant_id,
                    "card_type": card_type,
                    "latitude": jitter_coordinate(rng, merchant.city.latitude),
                    "longitude": jitter_coordinate(rng, merchant.city.longitude),
                    "merchant_category_code": merchant.mcc,
                    "merchant_country_code": merchant.city.country_code,
                    "merchant_region_code": merchant.city.region_code,
                    "ICA_code": merchant.ica_code,
                    "issr_id": merchant.issr_id,
                    "acquirer_id": merchant.acquirer_id,
                    "transaction_narration": narration,
                }
            )

    print(f"Wrote {TRANSACTION_COUNT} transactions to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
