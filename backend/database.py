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
            name TEXT NOT NULL,
            auth_user_id INTEGER UNIQUE,
            FOREIGN KEY (auth_user_id) REFERENCES auth_users(auth_user_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS auth_users (
            auth_user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
            paid_by INTEGER,
            amount REAL,
            category TEXT DEFAULT 'General',
            description TEXT,
            date TEXT,
            group_id INTEGER,
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

    c.execute("""
        CREATE TABLE IF NOT EXISTS friendships (
            friendship_id INTEGER PRIMARY KEY AUTOINCREMENT,
            auth_user_id INTEGER NOT NULL,
            friend_auth_user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            UNIQUE(auth_user_id, friend_auth_user_id),
            FOREIGN KEY (auth_user_id) REFERENCES auth_users(auth_user_id),
            FOREIGN KEY (friend_auth_user_id) REFERENCES auth_users(auth_user_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (created_by) REFERENCES auth_users(auth_user_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS group_members (
            group_member_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            auth_user_id INTEGER NOT NULL,
            joined_at TEXT NOT NULL,
            UNIQUE(group_id, auth_user_id),
            FOREIGN KEY (group_id) REFERENCES groups(group_id),
            FOREIGN KEY (auth_user_id) REFERENCES auth_users(auth_user_id)
        )
    """)

    # Safe incremental schema updates for existing databases
    cols_users = [r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()]
    if "auth_user_id" not in cols_users:
        c.execute("ALTER TABLE users ADD COLUMN auth_user_id INTEGER")

    cols_expenses = [r[1] for r in c.execute("PRAGMA table_info(expenses)").fetchall()]
    if "category" not in cols_expenses:
        c.execute("ALTER TABLE expenses ADD COLUMN category TEXT DEFAULT 'General'")
    if "group_id" not in cols_expenses:
        c.execute("ALTER TABLE expenses ADD COLUMN group_id INTEGER")

    conn.commit()
    conn.close()