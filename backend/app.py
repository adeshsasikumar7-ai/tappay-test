from dotenv import load_dotenv
load_dotenv()

import os, time, uuid, requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from shops import SHOPS
from guard import guard_bp

app = Flask(__name__)
CORS(app, origins=[
    "https://adeshsasikumar7-ai.github.io",
    "http://localhost:3000",
    "http://127.0.0.1:5500",
])
app.register_blueprint(guard_bp)

PAYPAL = "https://api-m.sandbox.paypal.com"
CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID")
SECRET = os.environ.get("PAYPAL_SECRET")

# DEMO_MODE=true  -> capture is SIMULATED
# DEMO_MODE=false -> capture goes to the real PayPal sandbox
DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() == "true"

RECEIVED = []
ORDERS = {}


def paypal_headers():
    if not CLIENT_ID or not SECRET:
        raise RuntimeError("PayPal keys are missing. Check your .env file.")
    r = requests.post(f"{PAYPAL}/v1/oauth2/token",
                      auth=(CLIENT_ID, SECRET),
                      data={"grant_type": "client_credentials"},
                      timeout=15)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}",
            "Content-Type": "application/json"}


@app.errorhandler(Exception)
def handle_error(e):
    return jsonify(error=str(e)), 500


@app.get("/")
def home():
    return jsonify(message="TapPay backend is running", demo_mode=DEMO_MODE)


@app.get("/api/shop/<shop_id>")
def shop(shop_id):
    s = SHOPS.get(shop_id)
    if not s:
        return jsonify(error="Unknown shop"), 404
    return jsonify(id=shop_id, name=s["name"], verified=True)


@app.post("/api/orders")
def create_order():
    d = request.get_json(silent=True) or {}
    s = SHOPS.get(d.get("shop_id"))
    if not s:
        return jsonify(error="Unknown shop"), 404
    try:
        amount = float(d.get("amount"))
    except (TypeError, ValueError):
        return jsonify(error="Invalid amount"), 400
    if amount <= 0:
        return jsonify(error="Amount must be more than 0"), 400

    body = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {"currency_code": "USD", "value": f"{amount:.2f}"},
            "custom_id": d["shop_id"],
        }],
    }
    r = requests.post(f"{PAYPAL}/v2/checkout/orders", json=body,
                      headers=paypal_headers(), timeout=15)
    data = r.json()
    if "id" in data:
        ORDERS[data["id"]] = {"shop_id": d["shop_id"], "amount": f"{amount:.2f}"}
    data["approve_url"] = next(
        (l["href"] for l in data.get("links", [])
         if l.get("rel") in ("approve", "payer-action")), None)
    return jsonify(data), r.status_code


def record_received(capture_id, shop_id, amount):
    if not any(p["id"] == capture_id for p in RECEIVED):
        RECEIVED.append({
            "id": capture_id,
            "shop_id": shop_id,
            "amount": amount,
            "ts": time.time(),
            "announced": False,
        })


@app.post("/api/orders/<order_id>/capture")
def capture(order_id):
    if DEMO_MODE:
        info = ORDERS.get(order_id)
        if not info:
            return jsonify(error="Unknown order. Create an order first."), 404
        fake_id = "DEMO-" + uuid.uuid4().hex[:12].upper()
        record_received(fake_id, info["shop_id"], info["amount"])
        return jsonify(status="COMPLETED", demo=True, id=order_id,
                       capture_id=fake_id, shop_id=info["shop_id"],
                       amount=info["amount"]), 201

    r = requests.post(f"{PAYPAL}/v2/checkout/orders/{order_id}/capture",
                      headers=paypal_headers(), timeout=15)
    data = r.json()
    if data.get("status") == "COMPLETED":
        pu = data["purchase_units"][0]
        cap = pu["payments"]["captures"][0]
        record_received(cap["id"],
                        pu.get("custom_id") or cap.get("custom_id"),
                        cap["amount"]["value"])
    return jsonify(data), r.status_code


@app.get("/api/received/<shop_id>")
def received(shop_id):
    new = [p for p in RECEIVED if p["shop_id"] == shop_id and not p["announced"]]
    for p in new:
        p["announced"] = True
    return jsonify(payments=new)
