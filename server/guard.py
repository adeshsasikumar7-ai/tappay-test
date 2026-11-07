import math
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


def run_rules(shop_id, amount):
    """The rules decide everything. can_explain is only used inside our code."""
    if not isinstance(shop_id, str) or shop_id not in SHOPS:
        return {"status": "warning", "message": "Unknown shop. Don't pay.",
                "suggested_amount": None, "can_explain": False}
    shop = SHOPS[shop_id]

    try:
        if isinstance(amount, bool):
            raise ValueError
        amount = float(amount)
        if not math.isfinite(amount):
            raise ValueError
    except (TypeError, ValueError):
        return {"status": "warning", "message": "Please enter a valid amount.",
                "suggested_amount": None, "can_explain": False}

    if amount <= 0:
        return {"status": "warning", "message": "The amount must be more than 0.",
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


def ai_sentence(shop_name, amount, low, high, rule_message, suggested):
    """Ask the AI for one friendly sentence. Returns None if anything fails."""
    try:
        from anthropic import Anthropic
        client = Anthropic(timeout=5.0, max_retries=0)  # reads ANTHROPIC_API_KEY
        prompt = (
            f"Shop: {shop_name}. Usual payments: {low} to {high}. "
            f"Customer typed: {amount:g}. Safety check result: {rule_message} "
            f"Suggested amount: {suggested}.\n"
            "Write ONE short, friendly sentence in plain English that warns the "
            "customer. Mention the suggested amount if there is one. "
            "Output only the sentence."
        )
        reply = client.messages.create(
            model="claude-haiku-5-5",
            max_tokens=80,
            messages=[{"role": "user", "content": prompt}],
        )
        text = reply.content[0].text.strip()
        return text or None
    except Exception:
        return None   # any problem: the fixed rule sentence is used instead


@guard_bp.post("/guard/check")
def check():
    data = request.get_json(silent=True) or {}
    shop_id, amount = data.get("shop_id"), data.get("amount")
    result = run_rules(shop_id, amount)

    if result.pop("can_explain"):
        shop = SHOPS[shop_id]
        sentence = ai_sentence(shop["name"], float(amount), shop["min"],
                               shop["max"], result["message"],
                               result["suggested_amount"])
        if sentence:
            result["message"] = sentence   # only the wording changes

    return jsonify(result)
