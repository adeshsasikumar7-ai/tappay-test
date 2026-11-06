
import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).parent / "data" / "payments.db"


def get_connection():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id TEXT PRIMARY KEY,
                shop_id TEXT NOT NULL,
                amount TEXT NOT NULL,
                currency TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def save_payment(payment_id, shop_id, amount, currency):
    with get_connection() as connection:
        connection.execute("""
            INSERT OR IGNORE INTO payments
            (id, shop_id, amount, currency, status)
            VALUES (?, ?, ?, ?, 'COMPLETED')
        """, (payment_id, shop_id, amount, currency))


def get_shop_payments(shop_id):
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT id, amount
            FROM payments
            WHERE shop_id = ? AND status = 'COMPLETED'
            ORDER BY created_at DESC
        """, (shop_id,)).fetchall()

    return [dict(row) for row in rows]
