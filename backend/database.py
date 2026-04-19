import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).parent / "expenses.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def create_tables():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
            paid_by INTEGER,
            amount REAL,
            description TEXT,
            date TEXT,
            FOREIGN KEY (paid_by) REFERENCES users(user_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS splits (
            split_id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_id INTEGER,
            user_id INTEGER,
            share REAL,
            FOREIGN KEY (expense_id) REFERENCES expenses(expense_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    conn.commit()
    conn.close()