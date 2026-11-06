from flask import Flask
from guard import guard_bp

app = Flask(__name__)
app.register_blueprint(guard_bp)
client = app.test_client()


def check(shop, amount):
    return client.post("/guard/check", json={"shop_id": shop, "amount": amount}).get_json()


def test_ok():
    assert check("shop_001", 25)["status"] == "ok"


def test_typo():
    r = check("shop_001", 250)
    assert r["status"] == "warning" and r["suggested_amount"] == 25


def test_zero():
    assert check("shop_001", 0)["status"] == "warning"


def test_unknown_shop():
    r = check("shop_fake", 25)
    assert r["status"] == "warning" and "Unknown shop" in r["message"]
