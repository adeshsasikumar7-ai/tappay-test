
import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
BASE_URL = "https://api-m.sandbox.paypal.com"


def get_access_token():
    if not CLIENT_ID or not CLIENT_SECRET:
        raise ValueError("PayPal credentials are missing")

    response = requests.post(
        f"{BASE_URL}/v1/oauth2/token",
        auth=(CLIENT_ID, CLIENT_SECRET),
        data={"grant_type": "client_credentials"},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def paypal_request(method, path, payload=None):
    token = get_access_token()

    response = requests.request(
        method,
        f"{BASE_URL}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=20,
    )

    response.raise_for_status()
    return response.json()



def create_order(amount, currency="USD", shop_id=None):
    payload = {
        "intent": "CAPTURE",
        "payment_source": {
            "paypal": {
                "experience_context": {
                    "return_url": "https://adeshsasikumar7-ai.github.io/tappay-test/",
                    "cancel_url": "https://adeshsasikumar7-ai.github.io/tappay-test/?payment=cancelled",
                    "user_action": "PAY_NOW",
                    "shipping_preference": "NO_SHIPPING"
                }
            }
        },
        "purchase_units": [
            {
                "custom_id": shop_id,
                "amount": {
                    "currency_code": currency,
                    "value": amount,
                }
            }
        ],
    }

    return paypal_request("POST", "/v2/checkout/orders", payload)



def get_order(order_id):
    validate_order_id(order_id)
    return paypal_request(
        "GET",
        f"/v2/checkout/orders/{order_id}",
    )


def capture_order(order_id):
    validate_order_id(order_id)
    return paypal_request(
        "POST",
        f"/v2/checkout/orders/{order_id}/capture",
        {},
    )


def validate_order_id(order_id):
    if not isinstance(order_id, str) or not re.fullmatch(
        r"[A-Za-z0-9-]{1,64}", order_id
    ):
        raise ValueError("Invalid PayPal order ID")
