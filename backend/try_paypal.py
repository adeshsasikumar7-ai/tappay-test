import requests

BASE = "http://localhost:5001"
SHOP = "shop_001"

# 1. Create an order
r = requests.post(f"{BASE}/api/orders", json={"shop_id": SHOP, "amount": 25})
order = r.json()
print("Create order:", r.status_code, order.get("status"))
if r.status_code >= 400:
    print(order)
    raise SystemExit

print("\nOpen this link in a PRIVATE browser window, log in with your")
print("sandbox PERSONAL account, and click Pay/Continue:\n")
print(order["approve_url"])
input("\nPress Enter here AFTER you approved it... ")

# 2. Capture
r = requests.post(f"{BASE}/api/orders/{order['id']}/capture")
print("Capture:", r.status_code, r.json().get("status"))

# 3. Check the received signal
r = requests.get(f"{BASE}/api/received/{SHOP}")
print("Received signal:", r.json())
