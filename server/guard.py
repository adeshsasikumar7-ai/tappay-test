import math
import os
from flask import Blueprint, jsonify, request
from guard_shops import SHOPS

guard_bp = Blueprint("guard", __name__)


def guess_typo(amount, low, high):
    """If removing one digit gives a normal amount, return it. Else None."""
    if amount != int(amount):
        return None
    digits = str(int(amount))
    if len(digits) < 2:
        return None
    for i in range(len(digits) - 1, -1, -1):   # last digit first
        candidate = int(digits[:i] + digits[i + 1:])
        if low <= candidate <= high:
            return candidate
    return None


def parse_positive_amount(amount):
    """Return a finite positive amount, or None for invalid input."""
    if isinstance(amount, bool):
        return None
    try:
        parsed = float(amount)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(parsed) or parsed <= 0:
        return None
    return parsed


def run_rules(shop_id, amount):
    """The rules decide everything. can_explain is only used inside our code."""
    if not isinstance(shop_id, str) or shop_id not in SHOPS:
        return {"status": "warning", "message": "Unknown shop. Don't pay.",
                "suggested_amount": None, "can_explain": False}
    shop = SHOPS[shop_id]

    amount = parse_positive_amount(amount)
    if amount is None:
        return {"status": "warning", "message": "Please enter a valid amount.",
                "suggested_amount": None, "can_explain": False}

    low, high = shop["min"], shop["max"]

    if amount > high:
        fix = guess_typo(amount, low, high)
        message = f"This is much higher than usual at this shop (usually {low} to {high})."
        if fix is not None:
            message += f" Did you mean {fix}?"
        return {"status": "warning", "message": message,
                "suggested_amount": fix, "can_explain": True}

    if amount < low:
        return {"status": "warning",
                "message": f"This is lower than usual at this shop (usually {low} to {high}).",
                "suggested_amount": None, "can_explain": True}

    return {"status": "ok", "message": "Looks fine.",
            "suggested_amount": None, "can_explain": False}


def ai_tone(shop_name, amount, low, high, rule_message, suggested):
    """Ask Groq for a safe tone label; callers must render trusted local text."""
    try:
        from groq import Groq
        client = Groq(timeout=5.0, max_retries=0)  # reads GROQ_API_KEY
        prompt = (
            f"Shop: {shop_name}. Usual payments: {low} to {high}. "
            f"Customer typed: {amount:g}. Safety check result: {rule_message} "
            f"Suggested amount: {suggested}.\n"
            "Choose a tone for an existing warning. Output exactly one token: "
            "friendly or direct. Never say the payment is safe, approved, or "
            "okay to make. Do not create or change a suggested amount."
        )
        reply = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
            max_completion_tokens=80,
            reasoning_effort="low",
            messages=[{"role": "user", "content": prompt}],
        )
        tone = (reply.choices[0].message.content or "").strip().lower()
        return tone if tone in {"friendly", "direct"} else None
    except Exception:
        return None


def render_warning(result, shop, amount):
    """Render only rule-backed warning text; Groq can choose a safe tone label."""
    rule_message = result["message"]
    if amount >= shop["min"]:
        return rule_message

    tone = ai_tone(shop["name"], amount, shop["min"], shop["max"],
                   rule_message, result["suggested_amount"])
    if tone != "friendly":
        return rule_message

    return (f"This amount is lower than usual at this shop (usually "
            f"{shop['min']} to {shop['max']}).")


@guard_bp.post("/guard/check")
def check():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    shop_id, amount = data.get("shop_id"), data.get("amount")
    if not isinstance(shop_id, str) or not shop_id:
        return jsonify({"error": "shop_id must be a non-empty string"}), 400

    if shop_id not in SHOPS:
        return jsonify({
            "status": "warning",
            "message": "Unknown shop. Don't pay.",
            "suggested_amount": None,
        }), 404

    if "amount" not in data or parse_positive_amount(amount) is None:
        return jsonify({
            "status": "warning",
            "message": "Please enter a valid amount.",
            "suggested_amount": None,
        }), 400

    result = run_rules(shop_id, amount)

    if result.pop("can_explain"):
        result["message"] = render_warning(result, SHOPS[shop_id],
                                           parse_positive_amount(amount))

    return jsonify(result)
