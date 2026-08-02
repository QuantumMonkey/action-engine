"""Regenerate the committed sample.db fixture (ENT-02). Deterministic."""

import os
import sqlite3
import sys

CUSTOMERS = [
    (1, "Meridian Textiles", "Pune", "priya@meridiantex.example"),
    (2, "BlueFin Logistics", "Mumbai", "ops@bluefin.example"),
    (3, "Karnak Foods", "Nashik", "orders@karnak.example"),
    (4, "Stellar Components", "Bengaluru", "sales@stellarcomp.example"),
    (5, "Harbor & Sons", "Kochi", "info@harborsons.example"),
]

ORDERS = [
    (101, 1, "2026-05-02", 12500.00, "delivered"),
    (102, 1, "2026-06-11", 8400.50, "delivered"),
    (103, 2, "2026-06-15", 22999.99, "shipped"),
    (104, 3, "2026-06-20", 1575.25, "delivered"),
    (105, 3, "2026-07-01", 6320.00, "processing"),
    (106, 4, "2026-07-03", 45100.00, "shipped"),
    (107, 5, "2026-07-08", 990.00, "processing"),
    (108, 2, "2026-07-10", 13750.75, "processing"),
]


def build(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            city TEXT NOT NULL,
            email TEXT NOT NULL
        );
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            order_date TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL
        );
        """
    )
    conn.executemany("INSERT INTO customers VALUES (?,?,?,?)", CUSTOMERS)
    conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", ORDERS)
    conn.commit()
    conn.close()
    print(f"fixture written: {path}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "fixtures", "sample.db",
    )
    os.makedirs(os.path.dirname(out), exist_ok=True)
    build(out)
