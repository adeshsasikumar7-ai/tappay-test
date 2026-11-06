
import json
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "merchants.json"


def load_merchants():
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    return data["merchants"]


def find_merchant(merchant_id):
    merchants = load_merchants()

    for merchant in merchants:
        if merchant["merchant_id"] == merchant_id:
            return merchant

    return None


def verify_merchant(merchant_id):
    merchant = find_merchant(merchant_id)

    if merchant is None:
        return {
            "found": False,
            "verified": False,
            "message": "Merchant not found"
        }

    return {
        "found": True,
        "verified": (
            merchant["verified"]
            and merchant["status"] == "active"
        ),
        "merchant": merchant
    }
