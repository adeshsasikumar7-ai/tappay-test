import os
from paypal import paypal_request


def verify_webhook_signature(headers, event):
    webhook_id = os.getenv("PAYPAL_WEBHOOK_ID")

    if not webhook_id:
        raise ValueError("PayPal webhook ID is missing")

    required_headers = {
        "auth_algo": headers.get("PAYPAL-AUTH-ALGO"),
        "cert_url": headers.get("PAYPAL-CERT-URL"),
        "transmission_id": headers.get("PAYPAL-TRANSMISSION-ID"),
        "transmission_sig": headers.get("PAYPAL-TRANSMISSION-SIG"),
        "transmission_time": headers.get("PAYPAL-TRANSMISSION-TIME"),
    }

    if not all(required_headers.values()):
        raise ValueError("Required PayPal webhook headers are missing")

    payload = {
        **required_headers,
        "webhook_id": webhook_id,
        "webhook_event": event,
    }

    return paypal_request(
        "POST",
        "/v1/notifications/verify-webhook-signature",
        payload
    )
