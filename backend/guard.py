
import math
import os
import requests

from flask import Blueprint, jsonify, request
from shops import SHOPS

guard_bp = Blueprint("guard", __name__)


def guess_typo(amount, low, high):
    """If removing one digit gives a normal amount, return it. Else None."""

    if amount != int(amount):
        return None

    digits = str(int(amount))

    if len(digits) < 2:
        return None

    for i in range(len(digits) - 1, -1, -1):
        candidate = int(digits[:i] + digits[i + 1:])

        if low <= candidate <= high:
            return candidate

    return None


def run_rules(shop_id, amount):
    """Python rules determine the payment safety result."""

    if not isinstance(shop_id, str) or shop_id not in SHOPS:
        return {
            "status": "warning",
            "message": "Unknown shop. Don't pay.",
            "suggested_amount": None,
            "can_explain": False
        }

    shop = SHOPS[shop_id]

    try:
        if isinstance(amount, bool):
            raise ValueError

        amount = float(amount)

        if not math.isfinite(amount):
            raise ValueError

    except (TypeError, ValueError):
        return {
            "status": "warning",
            "message": "Please enter a valid amount.",
            "suggested_amount": None,
            "can_explain": False
        }

    if amount <= 0:
        return {
            "status": "warning",
            "message": "The amount must be more than 0.",
            "suggested_amount": None,
            "can_explain": False
        }

    low, high = shop["min"], shop["max"]

    if amount > high:
        fix = guess_typo(amount, low, high)

        message = (
            f"This is much higher than usual at this shop "
            f"(usually {low} to {high})."
        )

        if fix is not None:
            message += f" Did you mean {fix}?"

        return {
            "status": "warning",
            "message": message,
            "suggested_amount": fix,
            "can_explain": True
        }

    if amount < low:
        return {
            "status": "warning",
            "message": (
                f"This is lower than usual at this shop "
                f"(usually {low} to {high})."
            ),
            "suggested_amount": None,
            "can_explain": True
        }

    return {
        "status": "ok",
        "message": "Looks fine.",
        "suggested_amount": None,
        "can_explain": False
    }


def ai_sentence(shop_name, amount, low, high, rule_message, suggested):
    """Use Groq to generate a friendly payment warning."""

    try:
        key = os.environ.get("GROQ_API_KEY")

        if not key:
            return None

        prompt = (
            f"Shop: {shop_name}. "
            f"Usual payments: {low} to {high}. "
            f"Customer typed: {amount:g}. "
            f"Safety check result: {rule_message} "
            f"Suggested amount: {suggested}.\n"
            "Write ONE short, friendly sentence in plain English "
            "that warns the customer. "
            "Mention the suggested amount if there is one. "
            "Output only the sentence."
        )

                r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openai/gpt-oss-20b",
                "max_completion_tokens": 80,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=30
        )
        response.raise_for_status()

        ai_text = (
            response.json()["choices"][0]["message"]["content"].strip()
        )

        return ai_text or None

    except Exception as e:
        print("Groq AI error:", str(e))
        return None


@guard_bp.post("/guard/check")
def check():

    data = request.get_json(silent=True) or {}

    shop_id = data.get("shop_id")
    amount = data.get("amount")

    result = run_rules(shop_id, amount)

    if result.pop("can_explain"):

        shop = SHOPS[shop_id]

        sentence = ai_sentence(
            shop["name"],
            float(amount),
            shop["min"],
            shop["max"],
            result["message"],
            result["suggested_amount"]
        )

        if sentence:
            result["message"] = sentence

    return jsonify(result)

