from paypal import get_order

order_id = input("Enter the NEW order ID: ").strip()

try:
    order = get_order(order_id)

    print("Order status:", order["status"])
    print("Full response:", order)

except Exception as error:
    print("Error:", error)