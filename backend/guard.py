import os
import math
import requests

from flask import Blueprint, request, jsonify

guard_bp = Blueprint("guard", __name__)


def guess_typo(amount, low, high):
    """Check whether removing an extra digit gives a valid amount."""

    if not amount.is_integer():
        return None

    digits = str(int(amount))

    if len(digits) < 2:
        return None

    for i in range(len(digits) - 1, 0, -1):
        candidate = int(digits[:i] + digits[i + 1:])

        if low <= candidate <= high:
            return candidate

    return None


def run_rules(shop_id, amount):
    """Run deterministic payment safety checks."""

    from shops import SHOPS

    shop = SHOPS.get(shop_id)

    if not shop:
        return {
            "status": "warning",
            "message": "Unknown shop. Please verify the shop details.",
            "suggested_amount": None,
            "can_explain": False
        }

    low = shop["min"]
    high = shop["max"]

    if isinstance(amount, bool):
        return {
            "status": "warning",
            "message": "Invalid payment amount.",
            "suggested_amount": None,
            "can_explain": False
        }

    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return {
            "status": "warning",
            "message": "Invalid payment amount.",
            "suggested_amount": None,
            "can_explain": False
        }

    if not math.isfinite(amount):
        return {
            "status": "warning",
            "message": "Invalid payment amount.",
            "suggested_amount": None,
            "can_explain": False
        }

    if amount <= 0:
        return {
            "status": "warning",
            "message": "Payment amount must be greater than zero.",
            "suggested_amount": None,
            "can_explain": False
        }

    if amount > high:
        suggested = guess_typo(amount, low, high)

        message = "This amount is higher than the shop's usual payment range."

        if suggested is not None:
            message += f" Did you mean {suggested}?"

        return {
            "status": "warning",
            "message": message,
            "suggested_amount": suggested,
            "can_explain": True
        }

    if amount < low:
        return {
            "status": "warning",
            "message": "This amount is lower than the shop's usual payment range.",
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
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            },
            timeout=30
        )

        r.raise_for_status()

        ai_text = (
            r.json()["choices"][0]["message"]["content"].strip()
        )

        return ai_text or None

    except Exception as e:
        print("Groq AI error:", str(e))
        return None


@guard_bp.route("/guard/check", methods=["POST"])
def check():
    """API endpoint to check a payment."""

    data = request.get_json(silent=True) or {}

    shop_id = data.get("shop_id")
    amount = data.get("amount")

    result = run_rules(shop_id, amount)

    if result["can_explain"]:
        from shops import SHOPS

        shop = SHOPS.get(shop_id)

        if shop:
            ai_message = ai_sentence(
                shop_name=shop["name"],
                amount=float(amount),
                low=shop["min"],
                high=shop["max"],
                rule_message=result["message"],
                suggested=result["suggested_amount"]
            )

            if ai_message:
                result["message"] = ai_message

    result.pop("can_explain", None)

    return jsonify(result)
