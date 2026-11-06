
from webhook import verify_webhook_signature
from merchant import verify_merchant
from flask import Flask, jsonify, request
from paypal import create_order, get_order, capture_order
from requests.exceptions import HTTPError, RequestException
import re

app = Flask(__name__)


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "TapPay backend is running!",
        "status": "success"
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"})


@app.route("/api/orders", methods=["POST"])
def create_payment_order():
    data = request.get_json(silent=True) or {}

    amount = data.get("amount")
    currency = data.get("currency", "USD")

    if not isinstance(amount, (str, int, float)):
        return jsonify({"error": "Valid amount is required"}), 400

    try:
        if not re.fullmatch(r"\d{1,8}(?:\.\d{1,2})?", str(amount)):
            return jsonify({"error": "Invalid amount format"}), 400

        if float(amount) <= 0:
            return jsonify({"error": "Amount must be positive"}), 400

        if currency != "USD":
            return jsonify({"error": "Only USD is currently supported"}), 400

        order = create_order(str(amount), currency)

        return jsonify({
            "order_id": order["id"],
            "status": order["status"],
            "approval_url": next(
                (link["href"] for link in order["links"]
                 if link["rel"] == "approve"),
                None
            )
        }), 201

    except (HTTPError, RequestException) as error:
        return jsonify({"error": str(error)}), 502
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.route("/api/orders/<order_id>", methods=["GET"])
def retrieve_order(order_id):
    try:
        order = get_order(order_id)
        return jsonify(order), 200
    except (HTTPError, RequestException) as error:
        return jsonify({"error": str(error)}), 502
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@app.route("/api/orders/<order_id>/capture", methods=["POST"])
def capture_payment(order_id):
    try:
        order = get_order(order_id)

        if order["status"] != "APPROVED":
            return jsonify({
                "error": "Order has not been approved",
                "current_status": order["status"]
            }), 409

        result = capture_order(order_id)
        return jsonify(result), 200

    except (HTTPError, RequestException) as error:
        return jsonify({"error": str(error)}), 502
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@app.route("/api/merchants/<merchant_id>", methods=["GET"])
def check_merchant(merchant_id):
    result = verify_merchant(merchant_id)
    return jsonify(result), 200 if result["found"] else 404

@app.route("/api/webhooks/paypal", methods=["POST"])
def paypal_webhook():
    event = request.get_json(silent=True)

    if not isinstance(event, dict):
        return jsonify({"error": "Invalid webhook payload"}), 400

    try:
        verification = verify_webhook_signature(
            request.headers,
            event
        )

        if verification.get("verification_status") != "SUCCESS":
            return jsonify({"error": "Webhook verification failed"}), 400

        event_type = event.get("event_type")

        return jsonify({
            "received": True,
            "verified": True,
            "event_type": event_type
        }), 200

    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    except (HTTPError, RequestException) as error:
        return jsonify({"error": str(error)}), 502
if __name__ == "__main__":
    app.run(debug=True, port=5000)
