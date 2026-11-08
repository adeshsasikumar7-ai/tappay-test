from flask import Flask, jsonify, request
from flask_cors import CORS
from requests.exceptions import HTTPError, RequestException
from decimal import Decimal, InvalidOperation
import sqlite3

import re

from paypal import create_order, get_order, capture_order
from merchant import verify_merchant
from webhook import verify_webhook_signature
from database import initialize_database, save_payment, get_shop_payments


app = Flask(__name__)
from guard import guard_bp
app.register_blueprint(guard_bp)

CORS(app, origins=[
    "https://adeshsasikumar7-ai.github.io"
])

initialize_database()


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
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    amount = data.get("amount")
    currency = data.get("currency")
    shop_id = data.get("shop_id")

    if not isinstance(shop_id, str) or not re.fullmatch(r"shop_[a-zA-Z0-9_-]{1,40}", shop_id):
        return jsonify({"error": "Valid shop ID is required"}), 400

    merchant = verify_merchant(shop_id)
    if not merchant["verified"]:
        return jsonify({"error": "Shop is not verified"}), 403

    if not isinstance(amount, (str, int, float)):
        return jsonify({"error": "Valid amount is required"}), 400

    try:
        if not re.fullmatch(r"\d{1,8}(?:\.\d{1,2})?", str(amount)):
            return jsonify({"error": "Invalid amount format"}), 400

        if float(amount) <= 0:
            return jsonify({"error": "Amount must be positive"}), 400

        if currency != "USD":
            return jsonify({"error": "Only USD is supported; specify currency as USD"}), 400

        # Guard range warnings are advisory. This endpoint independently
        # enforces a valid positive USD amount and an active verified merchant.
        order = create_order(str(amount), currency, shop_id)

        return jsonify({
            "order_id": order["id"],
            "status": order["status"],
            "approval_url": next(
                (link["href"] for link in order["links"]
                 if link["rel"] == "approve"),
                None
            )
        }), 201

    except (HTTPError, RequestException):
        app.logger.exception("PayPal order creation failed")
        return jsonify({"error": "PayPal order service is unavailable"}), 502
    except Exception:
        app.logger.exception("Unexpected order creation error")
        return jsonify({"error": "Could not create payment order"}), 500


@app.route("/api/orders/<order_id>", methods=["GET"])
def retrieve_order(order_id):
    try:
        order = get_order(order_id)
        return jsonify(order), 200
    except (HTTPError, RequestException):
        app.logger.exception("PayPal order lookup failed")
        return jsonify({"error": "Could not retrieve payment order"}), 502
    except ValueError:
        return jsonify({"error": "Invalid PayPal order ID"}), 400
    except Exception:
        app.logger.exception("Unexpected order lookup error")
        return jsonify({"error": "Could not retrieve payment order"}), 500




@app.route("/api/orders/<order_id>/capture", methods=["POST"])
def capture_payment(order_id):
    try:
        order = get_order(order_id)

        if order["status"] != "APPROVED":
            return jsonify({
                "error": "Order has not been approved",
                "current_status": order["status"]
            }), 409

        # Retrieve merchant ID before capturing
        shop_id = order["purchase_units"][0].get("custom_id")

        if not shop_id:
            return jsonify({
                "error": "Shop ID missing from order"
            }), 400

        if not verify_merchant(shop_id)["verified"]:
            return jsonify({"error": "Shop is not verified"}), 403

        # Capture exactly once
        result = capture_order(order_id)

        capture = result["purchase_units"][0]["payments"]["captures"][0]

        if capture["status"] != "COMPLETED":
            return jsonify({
                "error": "Payment capture not completed",
                "status": capture["status"]
            }), 409

        amount = capture["amount"]["value"]
        currency = capture["amount"]["currency_code"]
        payment_id = capture["id"]

        try:
            save_payment(payment_id, shop_id, amount, currency)
        except Exception:
            app.logger.exception("PayPal capture completed but local persistence failed")
            return jsonify({
                "success": True,
                "payment_id": payment_id,
                "shop_id": shop_id,
                "amount": amount,
                "currency": currency,
                "status": "COMPLETED",
                "payment_recorded": False,
                "warning": "Payment completed, but local payment history could not be updated."
            }), 200

        return jsonify({
            "success": True,
            "payment_id": payment_id,
            "shop_id": shop_id,
            "amount": amount,
            "currency": currency,
            "status": "COMPLETED",
            "payment_recorded": True
        }), 200

    except (HTTPError, RequestException):
        app.logger.exception("Could not confirm PayPal payment status")
        return jsonify({
            "error": "Could not confirm payment status; check before retrying."
        }), 502
    except ValueError:
        return jsonify({"error": "Invalid PayPal order ID"}), 400
    except Exception:
        app.logger.exception("Unexpected payment capture processing error")
        return jsonify({"error": "Could not process payment capture"}), 500



@app.route("/api/merchants/<merchant_id>", methods=["GET"])
def check_merchant(merchant_id):
    try:
        result = verify_merchant(merchant_id)
        return jsonify(result), 200 if result["found"] else 404
    except Exception:
        app.logger.exception("Merchant lookup failed")
        return jsonify({"error": "Could not retrieve merchant status"}), 500

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

        # Keep the shopkeeper feed current when PayPal reports a completed
        # capture. The capture ID is the database key, so webhook retries and
        # the synchronous capture route can safely report the same payment.
        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            resource = event.get("resource")
            if not isinstance(resource, dict):
                return jsonify({"error": "Completed capture resource is invalid"}), 400

            capture_id = resource.get("id")
            amount_info = resource.get("amount")
            if not isinstance(amount_info, dict):
                return jsonify({"error": "Completed capture amount is invalid"}), 400

            if not isinstance(capture_id, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,64}", capture_id):
                return jsonify({"error": "Completed capture ID is invalid"}), 400

            if resource.get("status") != "COMPLETED":
                return jsonify({"error": "Capture is not completed"}), 400

            amount_value = amount_info.get("value")
            if isinstance(amount_value, bool) or not isinstance(amount_value, (str, int, float)):
                return jsonify({"error": "Completed capture amount is invalid"}), 400
            try:
                parsed_amount = Decimal(str(amount_value))
            except (InvalidOperation, ValueError):
                return jsonify({"error": "Completed capture amount is invalid"}), 400

            if not parsed_amount.is_finite() or parsed_amount <= 0:
                return jsonify({"error": "Completed capture amount must be positive"}), 400

            currency = amount_info.get("currency_code")
            if currency != "USD":
                return jsonify({"error": "Only USD captures can be recorded"}), 400

            shop_id = resource.get("custom_id")

            if not isinstance(shop_id, str) or not shop_id:
                supplementary_data = resource.get("supplementary_data")
                related_ids = (supplementary_data.get("related_ids") or {}
                               if isinstance(supplementary_data, dict) else {})
                order_id = related_ids.get("order_id")
                if order_id:
                    order = get_order(order_id)
                    purchase_units = order.get("purchase_units") or []
                    if purchase_units:
                        shop_id = purchase_units[0].get("custom_id")

            if not shop_id or not verify_merchant(shop_id)["verified"]:
                return jsonify({"error": "Completed capture is not linked to a verified shop"}), 400

            save_payment(capture_id, shop_id, str(amount_value), currency)

        return jsonify({
            "received": True,
            "verified": True,
            "event_type": event_type
        }), 200

    except ValueError:
        return jsonify({"error": "Invalid PayPal webhook request"}), 400

    except (HTTPError, RequestException):
        app.logger.exception("Webhook verification or PayPal order lookup failed")
        return jsonify({"error": "Could not verify or process PayPal webhook"}), 502
    except sqlite3.Error:
        app.logger.exception("Webhook payment persistence failed")
        return jsonify({"error": "Payment record could not be saved"}), 500
    except Exception:
        app.logger.exception("Unexpected PayPal webhook processing error")
        return jsonify({"error": "Could not process PayPal webhook"}), 500

@app.route("/api/payments/new", methods=["GET"])
def get_new_payments():
    shop_id = request.args.get("shop")

    if not shop_id or not re.fullmatch(
        r"shop_[a-zA-Z0-9_-]{1,40}", shop_id
    ):
        return jsonify({"error": "Valid shop ID is required"}), 400

    try:
        payments = get_shop_payments(shop_id)

        return jsonify({
            "shop_id": shop_id,
            "payments": payments
        }), 200

    except Exception:
        app.logger.exception("Payment history lookup failed")
        return jsonify({"error": "Could not retrieve payment history"}), 500



if __name__ == "__main__":
    app.run(debug=True, port=5000)
