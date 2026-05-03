import sqlite3
from pathlib import Path
# flask import to be able to use app.route
from flask import Flask, request, jsonify

app = Flask(__name__)

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
            created_at TEXT NOT NULL,
            profile_image TEXT
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
            membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            auth_user_id INTEGER NOT NULL,
            joined_at TEXT NOT NULL,
            UNIQUE(group_id, auth_user_id),
            FOREIGN KEY (group_id) REFERENCES groups(group_id),
            FOREIGN KEY (auth_user_id) REFERENCES auth_users(auth_user_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS settlement_actions (
            settlement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            split_id INTEGER,
            expense_id INTEGER,
            group_id INTEGER,
            from_user_id INTEGER NOT NULL,
            to_user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            updated_at TEXT,
            UNIQUE(from_user_id, to_user_id, amount, created_at),
            FOREIGN KEY (split_id) REFERENCES splits(split_id),
            FOREIGN KEY (expense_id) REFERENCES expenses(expense_id),
            FOREIGN KEY (from_user_id) REFERENCES users(user_id),
            FOREIGN KEY (to_user_id) REFERENCES users(user_id)
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

    cols_auth_users = [r[1] for r in c.execute("PRAGMA table_info(auth_users)").fetchall()]
    if "profile_image" not in cols_auth_users:
        c.execute("ALTER TABLE auth_users ADD COLUMN profile_image TEXT")

    cols_settlements = [r[1] for r in c.execute("PRAGMA table_info(settlement_actions)").fetchall()]
    if "split_id" not in cols_settlements:
        c.execute("ALTER TABLE settlement_actions ADD COLUMN split_id INTEGER")
    if "expense_id" not in cols_settlements:
        c.execute("ALTER TABLE settlement_actions ADD COLUMN expense_id INTEGER")
    if "group_id" not in cols_settlements:
        c.execute("ALTER TABLE settlement_actions ADD COLUMN group_id INTEGER")

    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_settlement_split_unique ON settlement_actions(split_id) WHERE split_id IS NOT NULL")

    # Create group messages table
    c.execute("""
        CREATE TABLE IF NOT EXISTS group_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            message_type TEXT NOT NULL DEFAULT 'payment',
            amount REAL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (group_id) REFERENCES groups(group_id),
            FOREIGN KEY (user_id) REFERENCES auth_users(auth_user_id)
        )
    """)

    # Create blocked users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS blocked_users (
            block_id INTEGER PRIMARY KEY AUTOINCREMENT,
            blocker_auth_user_id INTEGER NOT NULL,
            blocked_auth_user_id INTEGER NOT NULL,
            blocked_at TEXT NOT NULL,
            UNIQUE(blocker_auth_user_id, blocked_auth_user_id),
            FOREIGN KEY (blocker_auth_user_id) REFERENCES auth_users(auth_user_id),
            FOREIGN KEY (blocked_auth_user_id) REFERENCES auth_users(auth_user_id)
        )
    """)

    # Safe incremental schema updates for new features
    cols_auth_users = [r[1] for r in c.execute("PRAGMA table_info(auth_users)").fetchall()]
    if "bio" not in cols_auth_users:
        c.execute("ALTER TABLE auth_users ADD COLUMN bio TEXT")

    conn.commit()
    conn.close()

# Placeholder for get_current_auth_user, replace with your actual implementation
def get_current_auth_user():
    # This is a dummy function. In a real application, you would get the authenticated user
    # based on the request context (e.g., from a JWT token or session).
    # For demonstration purposes, we'll assume a user with auth_user_id = 1 exists.
    return {'auth_user_id': 1, 'name': 'Test User'}

@app.route("/friends/requests", methods=["POST"])
def send_friend_request():
    me = get_current_auth_user()
    data = request.get_json()

    friend_username = data.get("friend_username")
    if not friend_username:
        return jsonify({"error": "Friend username is required"}), 400

    conn = get_connection()
    c = conn.cursor()

    # Get the friend's auth_user_id
    c.execute("SELECT auth_user_id FROM auth_users WHERE username = ?", (friend_username,))
    friend_result = c.fetchone()

    if not friend_result:
        conn.close()
        return jsonify({"error": f"User '{friend_username}' not found"}), 404

    friend_auth_user_id = friend_result[0]

    if me['auth_user_id'] == friend_auth_user_id:
        conn.close()
        return jsonify({"error": "You cannot send a friend request to yourself"}), 400

    # Check if a request already exists or if they are already friends
    c.execute("""
        SELECT status FROM friendships
        WHERE (auth_user_id = ? AND friend_auth_user_id = ?)
        OR (auth_user_id = ? AND friend_auth_user_id = ?)
    """, (me['auth_user_id'], friend_auth_user_id, friend_auth_user_id, me['auth_user_id']))
    existing_friendship = c.fetchone()

    if existing_friendship:
        if existing_friendship[0] == 'pending':
            conn.close()
            return jsonify({"message": "Friend request already sent or pending"}), 409
        elif existing_friendship[0] == 'accepted':
            conn.close()
            return jsonify({"message": "You are already friends"}), 409

    # Insert the new friend request
    from datetime import datetime
    created_at = datetime.utcnow().isoformat()
    try:
        c.execute("""
            INSERT INTO friendships (auth_user_id, friend_auth_user_id, status, created_at)
            VALUES (?, ?, 'pending', ?)
        """, (me['auth_user_id'], friend_auth_user_id, created_at))
        conn.commit()
        conn.close()
        return jsonify({"message": "Friend request sent successfully"}), 201
    except sqlite3.IntegrityError:
        conn.rollback()
        conn.close()
        return jsonify({"error": "Could not send friend request. Please try again."}), 500

# If you want to run this as a standalone Flask app, uncomment the following lines:
# if __name__ == "__main__":
#     create_tables()
#     app.run(debug=True)

