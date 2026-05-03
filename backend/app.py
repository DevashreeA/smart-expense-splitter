print(">>> app.py starting")

from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
from datetime import datetime
import hashlib

# use relative imports
from backend.database import create_tables, get_connection
from backend.calculations import get_totals, simplify_debts

app = Flask(__name__, template_folder="templates")
app.secret_key = "supersecretkey"
CORS(app, supports_credentials=True)

ALLOWED_CATEGORIES = {"Food", "Travel", "Shopping", "Bills", "Other"}

# Ensure DB and tables exist
create_tables()

# ---------------- HELPER FUNCTIONS ---------------- #

def add_user_db(name):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO users (name) VALUES (?)", (name,))
    conn.commit()
    uid = c.lastrowid
    conn.close()
    return uid


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def get_current_auth_user():
    auth_user_id = session.get("user_id")
    if not auth_user_id:
        return None
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT auth_user_id, name, username, email, profile_image FROM auth_users WHERE auth_user_id = ?", (auth_user_id,))
    row = c.fetchone()
    conn.close()
    return row


def normalize_category(category):
    value = (category or "Other").strip().title()
    return value if value in ALLOWED_CATEGORIES else None


def get_linked_user_id(auth_user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE auth_user_id = ?", (auth_user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def get_group_user_ids(group_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT u.user_id
        FROM group_members gm
        JOIN users u ON u.auth_user_id = gm.auth_user_id
        WHERE gm.group_id = ?
        ORDER BY u.user_id
    """, (group_id,))
    ids = [r[0] for r in c.fetchall()]
    conn.close()
    return ids


def ensure_group_member(group_id, auth_user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT 1 FROM group_members WHERE group_id = ? AND auth_user_id = ?", (group_id, auth_user_id))
    ok = c.fetchone() is not None
    conn.close()
    return ok


def get_outstanding_settlement_rows(group_id=None):
    conn = get_connection()
    c = conn.cursor()
    query = """
        SELECT
            s.split_id,
            s.expense_id,
            e.group_id,
            g.name,
            e.date,
            s.user_id AS from_user_id,
            debtor.name,
            e.paid_by AS to_user_id,
            creditor.name,
            s.share,
            COALESCE(sa.status, 'pending') AS status
        FROM splits s
        JOIN expenses e ON e.expense_id = s.expense_id
        JOIN users debtor ON debtor.user_id = s.user_id
        JOIN users creditor ON creditor.user_id = e.paid_by
        LEFT JOIN groups g ON g.group_id = e.group_id
        LEFT JOIN settlement_actions sa ON sa.split_id = s.split_id
        WHERE s.user_id != e.paid_by
    """
    params = []
    if group_id is not None:
        query += " AND e.group_id = ?"
        params.append(group_id)
    query += " ORDER BY e.date DESC, s.split_id DESC"
    c.execute(query, tuple(params))
    rows = c.fetchall()
    conn.close()
    return rows


def build_settlement_payload_for_user(auth_user_id, group_id=None):
    linked_user_id = get_linked_user_id(auth_user_id)
    rows = get_outstanding_settlement_rows(group_id)
    owes = []
    owed_to_you = []
    groups = {}

    for row in rows:
        split_id, expense_id, expense_group_id, group_name, expense_date, from_user_id, from_name, to_user_id, to_name, amount, status = row
        if status in {"paid", "received"}:
            continue
        if linked_user_id not in {from_user_id, to_user_id}:
            continue

        item = {
            "split_id": split_id,
            "expense_id": expense_id,
            "group_id": expense_group_id,
            "group_name": group_name or "Personal",
            "date": expense_date,
            "from_user_id": from_user_id,
            "from_name": from_name,
            "to_user_id": to_user_id,
            "to_name": to_name,
            "amount": round(float(amount or 0), 2),
            "status": status,
        }
        groups.setdefault(item["group_name"], []).append(item)

        if linked_user_id == from_user_id:
            owes.append(item)
        elif linked_user_id == to_user_id:
            owed_to_you.append(item)

    return {
        "you_owe": round(sum(item["amount"] for item in owes), 2),
        "you_receive": round(sum(item["amount"] for item in owed_to_you), 2),
        "owes": owes,
        "owed_to_you": owed_to_you,
        "groups": [{"group_name": name, "items": items} for name, items in groups.items()],
    }


def list_users_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT user_id, name FROM users")
    rows = c.fetchall()
    conn.close()
    return [{"user_id": r[0], "name": r[1]} for r in rows]


def add_expense_db(amount, paid_by, description, involved_ids, shares=None):
    conn = get_connection()
    c = conn.cursor()

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    c.execute(
        "INSERT INTO expenses (paid_by, amount, description, date) VALUES (?, ?, ?, ?)",
        (paid_by, amount, description, date_str),
    )

    expense_id = c.lastrowid

    if shares:
        for uid, s in zip(involved_ids, shares):
            c.execute(
                "INSERT INTO splits (expense_id, user_id, share) VALUES (?, ?, ?)",
                (expense_id, uid, s),
            )
    else:
        per = round(amount / len(involved_ids), 2)
        for uid in involved_ids:
            c.execute(
                "INSERT INTO splits (expense_id, user_id, share) VALUES (?, ?, ?)",
                (expense_id, uid, per),
            )

    conn.commit()
    conn.close()
    return expense_id


# ---------------- FRONTEND ROUTE ---------------- #

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- API ROUTES ---------------- #

@app.route("/users", methods=["GET"])
def api_list_users():
    return jsonify(list_users_db())


@app.route("/users", methods=["POST"])
def api_add_user():
    data = request.get_json() or {}
    name = data.get("name")

    if not name:
        return jsonify({"error": "name required"}), 400

    uid = add_user_db(name)
    return jsonify({"user_id": uid, "name": name}), 201


@app.route("/expenses", methods=["POST"])
def api_add_expense():
    data = request.get_json() or {}

    try:
        amount = float(data["amount"])
        paid_by = int(data["paid_by"])
        category = normalize_category(data.get("category", "Other"))
        description = data.get("description", "")
        date = data.get("date")
        group_id = data.get("group_id")
        involved = data.get("involved")
        shares = data.get("shares")

        if shares:
            shares = [float(s) for s in shares]

    except Exception as e:
        return jsonify({"error": f"invalid input: {e}"}), 400

    # Group expense integration: if group selected and involved is missing,
    # split among all linked users in that group.
    if group_id and (not involved or len(involved) == 0):
        involved = get_group_user_ids(int(group_id))
        if not involved:
            return jsonify({"error": "group has no linked members"}), 400

    if not involved:
        return jsonify({"error": "involved required"}), 400
    if not category:
        return jsonify({"error": "category must be one of Food, Travel, Shopping, Bills, Other"}), 400

    expense_id = add_expense_db(amount, paid_by, description, involved, shares)
    conn = get_connection()
    c = conn.cursor()
    if date:
        c.execute("UPDATE expenses SET date = ? WHERE expense_id = ?", (date, expense_id))
    c.execute("UPDATE expenses SET category = ?, group_id = ? WHERE expense_id = ?", (category, group_id, expense_id))
    conn.commit()
    conn.close()
    return jsonify({"expense_id": expense_id}), 201


@app.route("/expenses", methods=["GET"])
def api_list_expenses():
    conn = get_connection()
    c = conn.cursor()

    c.execute(
        "SELECT expense_id, paid_by, amount, category, description, date, group_id FROM expenses ORDER BY expense_id DESC"
    )

    rows = c.fetchall()
    expenses = []

    for r in rows:
        expense_id, paid_by, amount, category, description, date, group_id = r

        c.execute(
            "SELECT user_id, share FROM splits WHERE expense_id = ?",
            (expense_id,),
        )

        splits = [{"user_id": s[0], "share": s[1]} for s in c.fetchall()]

        expenses.append(
            {
                "expense_id": expense_id,
                "paid_by": paid_by,
                "amount": amount,
                "category": category,
                "description": description,
                "date": date,
                "group_id": group_id,
                "splits": splits,
            }
        )

    conn.close()
    return jsonify(expenses)


@app.route("/users/<int:user_id>", methods=["DELETE"])
def api_delete_user(user_id):
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT expense_id FROM expenses WHERE paid_by = ?", (user_id,))
    exp_ids = [r[0] for r in c.fetchall()]

    if exp_ids:
        c.executemany(
            "DELETE FROM splits WHERE expense_id = ?", [(eid,) for eid in exp_ids]
        )

    c.execute("DELETE FROM expenses WHERE paid_by = ?", (user_id,))
    c.execute("DELETE FROM splits WHERE user_id = ?", (user_id,))
    c.execute("DELETE FROM users WHERE user_id = ?", (user_id,))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "deleted_user": user_id})


@app.route("/users/<int:user_id>", methods=["PUT"])
def api_edit_user(user_id):
    data = request.get_json() or {}
    name = data.get("name")

    if not name:
        return jsonify({"error": "name required"}), 400

    conn = get_connection()
    c = conn.cursor()

    c.execute("UPDATE users SET name = ? WHERE user_id = ?", (name, user_id))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "user_id": user_id, "name": name})


@app.route("/expenses/<int:expense_id>", methods=["DELETE"])
def api_delete_expense(expense_id):
    conn = get_connection()
    c = conn.cursor()

    c.execute("DELETE FROM splits WHERE expense_id = ?", (expense_id,))
    c.execute("DELETE FROM expenses WHERE expense_id = ?", (expense_id,))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "deleted_expense": expense_id})


@app.route("/expenses/<int:expense_id>", methods=["PUT"])
def api_edit_expense(expense_id):
    data = request.get_json() or {}

    try:
        amount = float(data["amount"])
        paid_by = int(data["paid_by"])
        category = normalize_category(data.get("category", "Other"))
        description = data.get("description", "")
        date = data.get("date")
        group_id = data.get("group_id")
        involved = data["involved"]
        shares = data.get("shares")

    except Exception as e:
        return jsonify({"error": f"invalid input: {e}"}), 400
    if not category:
        return jsonify({"error": "category must be one of Food, Travel, Shopping, Bills, Other"}), 400

    conn = get_connection()
    c = conn.cursor()

    c.execute(
        "UPDATE expenses SET paid_by = ?, amount = ?, category = ?, description = ?, date = COALESCE(?, date), group_id = ? WHERE expense_id = ?",
        (paid_by, amount, category, description, date, group_id, expense_id),
    )

    c.execute("DELETE FROM splits WHERE expense_id = ?", (expense_id,))

    if shares:
        for uid, s in zip(involved, shares):
            c.execute(
                "INSERT INTO splits (expense_id, user_id, share) VALUES (?, ?, ?)",
                (expense_id, uid, float(s)),
            )
    else:
        per = round(amount / len(involved), 2)
        for uid in involved:
            c.execute(
                "INSERT INTO splits (expense_id, user_id, share) VALUES (?, ?, ?)",
                (expense_id, uid, per),
            )

    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "expense_id": expense_id})


@app.route("/summary", methods=["GET"])
def api_summary():
    totals = get_totals()
    return jsonify(totals)


@app.route("/settle", methods=["GET"])
def api_settle():
    totals = get_totals()
    txns = simplify_debts(totals)

    user_map = {uid: info["name"] for uid, info in totals.items()}

    for t in txns:
        t["from_name"] = user_map.get(t["from"], "")
        t["to_name"] = user_map.get(t["to"], "")

    return jsonify(txns)


# ---------------- AUTH ROUTES (ADDITIVE) ---------------- #
@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    username = (data.get("username") or "").strip().lower()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not name or not username or not email or not password:
        return jsonify({"error": "name, username, email and password required"}), 400

    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            """
            INSERT INTO auth_users (name, username, email, password_hash, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, username, email, hash_password(password), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        auth_user_id = c.lastrowid
        c.execute("INSERT OR IGNORE INTO users (name, auth_user_id) VALUES (?, ?)", (name, auth_user_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": str(e)}), 400

    conn.close()
    return jsonify({"message": "User created", "auth_user_id": auth_user_id}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    identifier = (data.get("identifier") or data.get("username") or data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not identifier or not password:
        return jsonify({"error": "identifier and password required"}), 400

    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT auth_user_id, name, username, email
        FROM auth_users
        WHERE (username = ? OR email = ?) AND password_hash = ?
        """,
        (identifier, identifier, hash_password(password)),
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Invalid credentials"}), 401

    session["user_id"] = row[0]
    return jsonify({"auth_user_id": row[0], "name": row[1], "username": row[2], "email": row[3], "profile_image": row[4] if len(row) > 4 else None})


@app.route("/auth/me", methods=["GET"])
def auth_me():
    row = get_current_auth_user()
    if not row:
        return jsonify({"error": "not logged in"}), 401
    return jsonify({"auth_user_id": row[0], "name": row[1], "username": row[2], "email": row[3], "profile_image": row[4] if len(row) > 4 else None})


@app.route("/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})


# ---------------- FRIEND ROUTES (USERNAME-BASED, ADDITIVE) ---------------- #
@app.route("/friends/requests", methods=["POST"])
def send_friend_request():
    me = get_current_auth_user()
    if not me:
        return jsonify({"error": "login required"}), 401
    data = request.get_json() or {}
    username = (data.get("username") or "").strip().lower()
    if not username:
        return jsonify({"error": "username required"}), 400
    if username == me[2]:
        return jsonify({"error": "Cannot add yourself"}), 400

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT auth_user_id FROM auth_users WHERE username = ?", (username,))
    target = c.fetchone()
    if not target:
        conn.close()
        return jsonify({"error": "User not found"}), 404

    target_id = target[0]
    c.execute(
        """
        SELECT friendship_id, status, auth_user_id, friend_auth_user_id
        FROM friendships
        WHERE (auth_user_id=? AND friend_auth_user_id=?)
           OR (auth_user_id=? AND friend_auth_user_id=?)
        """,
        (me[0], target_id, target_id, me[0]),
    )
    existing = c.fetchone()
    if existing:
        conn.close()
        return jsonify({"error": "Friendship/request already exists"}), 400

    c.execute(
        "INSERT INTO friendships (auth_user_id, friend_auth_user_id, status, created_at) VALUES (?, ?, 'pending', ?)",
        (me[0], target_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    req_id = c.lastrowid
    conn.close()
    return jsonify({"message": "Friend request sent", "request_id": req_id})


@app.route("/friends/request", methods=["POST"])
def send_friend_request_alias():
    return send_friend_request()


@app.route("/friends/requests", methods=["GET"])
def list_friend_requests():
    me = get_current_auth_user()
    if not me:
        return jsonify({"error": "login required"}), 401
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT f.friendship_id, u.auth_user_id, u.name, u.username
        FROM friendships f JOIN auth_users u ON u.auth_user_id = f.auth_user_id
        WHERE f.friend_auth_user_id = ? AND f.status = 'pending'
    """, (me[0],))
    incoming = [{"request_id": r[0], "auth_user_id": r[1], "name": r[2], "username": r[3]} for r in c.fetchall()]
    c.execute("""
        SELECT f.friendship_id, u.auth_user_id, u.name, u.username
        FROM friendships f JOIN auth_users u ON u.auth_user_id = f.friend_auth_user_id
        WHERE f.auth_user_id = ? AND f.status = 'pending'
    """, (me[0],))
    outgoing = [{"request_id": r[0], "auth_user_id": r[1], "name": r[2], "username": r[3]} for r in c.fetchall()]
    conn.close()
    return jsonify({"incoming": incoming, "outgoing": outgoing})


@app.route("/friends/requests/respond", methods=["POST"])
def respond_friend_request():
    me = get_current_auth_user()
    if not me:
        return jsonify({"error": "login required"}), 401
    data = request.get_json() or {}
    request_id = data.get("request_id")
    action = data.get("action")
    if not request_id or action not in {"accept", "reject"}:
        return jsonify({"error": "request_id and valid action required"}), 400
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT friendship_id, friend_auth_user_id, status FROM friendships WHERE friendship_id = ?", (request_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Request not found"}), 404
    if row[1] != me[0]:
        conn.close()
        return jsonify({"error": "Not authorized"}), 403
    if row[2] != "pending":
        conn.close()
        return jsonify({"error": "Request already handled"}), 400
    if action == "accept":
        c.execute("UPDATE friendships SET status='accepted' WHERE friendship_id = ?", (request_id,))
    else:
        c.execute("DELETE FROM friendships WHERE friendship_id = ?", (request_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": f"Request {action}ed"})


@app.route("/friends/accept", methods=["POST"])
def accept_friend_request_alias():
    me = get_current_auth_user()
    if not me:
        return jsonify({"error": "login required"}), 401
    data = request.get_json() or {}
    request_id = data.get("request_id")
    if not request_id:
        return jsonify({"error": "request_id required"}), 400
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT friendship_id, friend_auth_user_id, status FROM friendships WHERE friendship_id = ?", (request_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Request not found"}), 404
    if row[1] != me[0]:
        conn.close()
        return jsonify({"error": "Not authorized"}), 403
    if row[2] != "pending":
        conn.close()
        return jsonify({"error": "Request already handled"}), 400
    c.execute("UPDATE friendships SET status='accepted' WHERE friendship_id = ?", (request_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Request accepted"})


@app.route("/friends/reject", methods=["POST"])
def reject_friend_request_alias():
    me = get_current_auth_user()
    if not me:
        return jsonify({"error": "login required"}), 401
    data = request.get_json() or {}
    request_id = data.get("request_id")
    if not request_id:
        return jsonify({"error": "request_id required"}), 400
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT friendship_id, friend_auth_user_id, status FROM friendships WHERE friendship_id = ?", (request_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Request not found"}), 404
    if row[1] != me[0]:
        conn.close()
        return jsonify({"error": "Not authorized"}), 403
    if row[2] != "pending":
        conn.close()
        return jsonify({"error": "Request already handled"}), 400
    c.execute("DELETE FROM friendships WHERE friendship_id = ?", (request_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Request rejected"})


@app.route("/friends", methods=["GET"])
def list_friends():
    me = get_current_auth_user()
    if not me:
        return jsonify({"error": "login required"}), 401
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT CASE WHEN auth_user_id = ? THEN friend_auth_user_id ELSE auth_user_id END AS fid
        FROM friendships
        WHERE (auth_user_id = ? OR friend_auth_user_id = ?) AND status = 'accepted'
    """, (me[0], me[0], me[0]))
    ids = [r[0] for r in c.fetchall()]
    friends = []
    for fid in ids:
        c.execute("SELECT auth_user_id, name, username, email FROM auth_users WHERE auth_user_id = ?", (fid,))
        u = c.fetchone()
        if u:
            friends.append({"auth_user_id": u[0], "name": u[1], "username": u[2], "email": u[3]})
    conn.close()
    return jsonify({"friends": friends})


# ---------------- GROUP ROUTES (ADDITIVE) ---------------- #
@app.route("/groups", methods=["GET"])
def get_groups():
    me = get_current_auth_user()
    if not me:
        return jsonify({"error": "login required"}), 401
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT g.group_id, g.name, g.created_by, g.created_at
        FROM groups g JOIN group_members gm ON gm.group_id = g.group_id
        WHERE gm.auth_user_id = ?
    """, (me[0],))
    groups = [{"group_id": r[0], "name": r[1], "created_by": r[2], "created_at": r[3]} for r in c.fetchall()]
    conn.close()
    return jsonify({"groups": groups})


@app.route("/groups", methods=["POST"])
def create_group():
    me = get_current_auth_user()
    if not me:
        return jsonify({"error": "login required"}), 401
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    member_usernames = data.get("member_usernames") or []
    if not name:
        return jsonify({"error": "name required"}), 400
    if not isinstance(member_usernames, list):
        return jsonify({"error": "member_usernames must be array"}), 400

    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO groups (name, created_by, created_at) VALUES (?, ?, ?)", (name, me[0], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    gid = c.lastrowid
    c.execute("INSERT INTO group_members (group_id, auth_user_id, joined_at) VALUES (?, ?, ?)", (gid, me[0], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    for uname in member_usernames:
        uname = (uname or "").strip().lower()
        if not uname:
            continue
        c.execute("SELECT auth_user_id FROM auth_users WHERE username = ?", (uname,))
        u = c.fetchone()
        if u:
            c.execute("INSERT OR IGNORE INTO group_members (group_id, auth_user_id, joined_at) VALUES (?, ?, ?)", (gid, u[0], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    return jsonify({"group_id": gid, "name": name}), 201


@app.route("/groups/<int:group_id>/expenses", methods=["GET"])
def get_group_expenses(group_id):
    me = get_current_auth_user()
    if not me:
        return jsonify({"error": "login required"}), 401
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT 1 FROM group_members WHERE group_id = ? AND auth_user_id = ?", (group_id, me[0]))
    if not c.fetchone():
        conn.close()
        return jsonify({"error": "not a member"}), 403
    c.execute("SELECT expense_id, paid_by, amount, category, description, date FROM expenses WHERE group_id = ? ORDER BY expense_id DESC", (group_id,))
    rows = [{"expense_id": r[0], "paid_by": r[1], "amount": r[2], "category": r[3], "description": r[4], "date": r[5]} for r in c.fetchall()]
    conn.close()
    return jsonify({"expenses": rows})


@app.route("/groups/<int:group_id>", methods=["GET"])
def get_group_details(group_id):
    me = get_current_auth_user()
    if not me:
        return jsonify({"error": "login required"}), 401
    if not ensure_group_member(group_id, me[0]):
        return jsonify({"error": "not a member"}), 403

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT group_id, name, created_by, created_at FROM groups WHERE group_id = ?", (group_id,))
    group = c.fetchone()
    if not group:
        conn.close()
        return jsonify({"error": "group not found"}), 404

    c.execute("""
        SELECT au.auth_user_id, au.name, au.username
        FROM group_members gm
        JOIN auth_users au ON au.auth_user_id = gm.auth_user_id
        WHERE gm.group_id = ?
        ORDER BY au.username
    """, (group_id,))
    members = [{"auth_user_id": r[0], "name": r[1], "username": r[2]} for r in c.fetchall()]
    conn.close()
    return jsonify({"group_id": group[0], "name": group[1], "created_by": group[2], "created_at": group[3], "members": members})


@app.route("/groups/<int:group_id>/add-member", methods=["POST"])
def add_group_member(group_id):
    me = get_current_auth_user()
    if not me:
        return jsonify({"error": "login required"}), 401
    if not ensure_group_member(group_id, me[0]):
        return jsonify({"error": "not a member"}), 403

    data = request.get_json() or {}
    username = (data.get("username") or "").strip().lower()
    if not username:
        return jsonify({"error": "username required"}), 400

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT auth_user_id FROM auth_users WHERE username = ?", (username,))
    user = c.fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "user not found"}), 404
    c.execute(
        "INSERT OR IGNORE INTO group_members (group_id, auth_user_id, joined_at) VALUES (?, ?, ?)",
        (group_id, user[0], datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "member added", "group_id": group_id, "username": username})


@app.route("/groups/<int:group_id>/remove-member", methods=["POST"])
def remove_group_member(group_id):
    me = get_current_auth_user()
    if not me:
        return jsonify({"error": "login required"}), 401
    if not ensure_group_member(group_id, me[0]):
        return jsonify({"error": "not a member"}), 403

    data = request.get_json() or {}
    username = (data.get("username") or "").strip().lower()
    if not username:
        return jsonify({"error": "username required"}), 400

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT auth_user_id FROM auth_users WHERE username = ?", (username,))
    user = c.fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "user not found"}), 404
    if user[0] == me[0]:
        conn.close()
        return jsonify({"error": "cannot remove yourself"}), 400
    c.execute("DELETE FROM group_members WHERE group_id = ? AND auth_user_id = ?", (group_id, user[0]))
    conn.commit()
    conn.close()
    return jsonify({"message": "member removed", "group_id": group_id, "username": username})


@app.route("/dashboard", methods=["GET"])
def dashboard():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT IFNULL(SUM(amount), 0) FROM expenses")
    total_spent = c.fetchone()[0]
    c.execute("SELECT category, IFNULL(SUM(amount), 0) FROM expenses GROUP BY category ORDER BY 2 DESC")
    category_breakdown = [{"category": r[0], "total": r[1]} for r in c.fetchall()]
    c.execute("SELECT substr(date,1,7) AS month, IFNULL(SUM(amount),0) FROM expenses GROUP BY substr(date,1,7) ORDER BY month")
    monthly = [{"month": r[0], "total": r[1]} for r in c.fetchall()]
    c.execute("SELECT expense_id, paid_by, amount, category, description, date FROM expenses ORDER BY expense_id DESC LIMIT 10")
    recent = [{"expense_id": r[0], "paid_by": r[1], "amount": r[2], "category": r[3], "description": r[4], "date": r[5]} for r in c.fetchall()]
    conn.close()
    totals = get_totals()
    my_owe = 0.0
    my_receive = 0.0
    me = get_current_auth_user()
    if me:
        linked_user_id = get_linked_user_id(me[0])
        if linked_user_id and linked_user_id in totals:
            bal = float(totals[linked_user_id]["balance"])
            my_receive = round(max(0.0, bal), 2)
            my_owe = round(max(0.0, -bal), 2)

    return jsonify({
        "total_spent": total_spent,
        "category_breakdown": category_breakdown,
        "monthly_summary": monthly,
        "recent_transactions": recent,
        "you_owe": my_owe,
        "you_receive": my_receive
    })


@app.route("/insights", methods=["GET"])
def insights():
    me = get_current_auth_user()
    conn = get_connection()
    c = conn.cursor()
    today = datetime.now()
    current_month = today.strftime("%Y-%m")
    previous_month = f"{today.year - 1}-12" if today.month == 1 else f"{today.year}-{today.month - 1:02d}"

    c.execute(
        """
        SELECT IFNULL(SUM(amount), 0)
        FROM expenses
        WHERE substr(date, 1, 7) = ?
        """,
        (current_month,),
    )
    total_spent = round(float(c.fetchone()[0] or 0), 2)

    c.execute(
        """
        SELECT category, IFNULL(SUM(amount), 0) AS total
        FROM expenses
        WHERE substr(date, 1, 7) = ?
        GROUP BY category
        ORDER BY total DESC, category ASC
        """,
        (current_month,),
    )
    category_rows = c.fetchall()
    category_breakdown = [{"category": row[0] or "Other", "total": round(float(row[1] or 0), 2)} for row in category_rows]
    top = category_breakdown[0] if category_breakdown else None

    c.execute(
        """
        SELECT strftime('%Y-%W', date) AS week_key, IFNULL(SUM(amount), 0) AS total
        FROM expenses
        WHERE date IS NOT NULL AND date != ''
        GROUP BY strftime('%Y-%W', date)
        ORDER BY week_key DESC
        LIMIT 6
        """
    )
    weekly_rows = list(reversed(c.fetchall()))

    c.execute("SELECT IFNULL(SUM(amount), 0) FROM expenses WHERE substr(date, 1, 7) = ?", (previous_month,))
    previous_total = round(float(c.fetchone()[0] or 0), 2)

    c.execute(
        """
        SELECT e.expense_id, e.amount, e.date
        FROM expenses e
        JOIN splits s ON s.expense_id = e.expense_id
        WHERE s.user_id = ? AND e.paid_by != ? AND date(e.date) <= date('now', '-7 day')
        ORDER BY e.date ASC
        """,
        (get_linked_user_id(me[0]) if me else -1, get_linked_user_id(me[0]) if me else -1),
    )
    old_owed_rows = c.fetchall()
    conn.close()

    alerts = []
    if top and total_spent > 0:
        top_share = round((top["total"] / total_spent) * 100, 2)
        if top_share > 40:
            alerts.append({
                "type": "overspending",
                "message": f"{top['category']} accounts for {top_share}% of this month's spending.",
            })

    if old_owed_rows:
        oldest = old_owed_rows[0]
        try:
            oldest_date = datetime.strptime(str(oldest[2])[:10], "%Y-%m-%d")
            overdue_days = (today - oldest_date).days
        except Exception:
            overdue_days = 7
        alerts.append({
            "type": "pending_payment",
            "message": f"You have pending owed payments older than {overdue_days} days.",
        })

    trends = []
    for week_key, total in weekly_rows:
        trends.append({
            "type": "weekly_spending",
            "label": week_key,
            "value": round(float(total or 0), 2),
        })
    trends.append({
        "type": "monthly_comparison",
        "label": f"{current_month} vs {previous_month}",
        "value": round(total_spent - previous_total, 2),
        "current_total": total_spent,
        "previous_total": previous_total,
    })

    return jsonify({
        "total_spent": total_spent,
        "category_breakdown": category_breakdown,
        "top_category": top or {"category": "Other", "total": 0.0},
        "alerts": alerts,
        "trends": trends,
    })


@app.route("/profile", methods=["GET"])
def get_profile():
    me = get_current_auth_user()
    if not me:
        return jsonify({"error": "login required"}), 401
    return jsonify({
        "auth_user_id": me[0],
        "name": me[1],
        "username": me[2],
        "email": me[3],
        "profile_image": me[4] or "https://api.dicebear.com/8.x/bottts/svg?seed=smart-expense"
    })


@app.route("/profile/update", methods=["POST"])
def update_profile():
    me = get_current_auth_user()
    if not me:
        return jsonify({"error": "login required"}), 401
    data = request.get_json() or {}
    name = (data.get("name") or me[1]).strip()
    profile_image = data.get("profile_image") or me[4]
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE auth_users SET name = ?, profile_image = ? WHERE auth_user_id = ?", (name, profile_image, me[0]))
    c.execute("UPDATE users SET name = ? WHERE auth_user_id = ?", (name, me[0]))
    conn.commit()
    conn.close()
    return jsonify({"message": "profile updated"})


@app.route("/balances", methods=["GET"])
def get_balances():
    totals = get_totals()
    me = get_current_auth_user()
    my = {"you_owe": 0.0, "you_receive": 0.0}
    if me:
        my = build_settlement_payload_for_user(me[0])
    return jsonify({"totals": totals, **my})


@app.route("/settlements", methods=["GET"])
def get_settlements():
    me = get_current_auth_user()
    if not me:
        return jsonify({"error": "login required"}), 401
    group_id = request.args.get("group_id", type=int)
    return jsonify(build_settlement_payload_for_user(me[0], group_id=group_id))


@app.route("/groups/<int:group_id>/settlements", methods=["GET"])
def get_group_settlements(group_id):
    me = get_current_auth_user()
    if not me:
        return jsonify({"error": "login required"}), 401
    if not ensure_group_member(group_id, me[0]):
        return jsonify({"error": "not a member"}), 403
    payload = build_settlement_payload_for_user(me[0], group_id=group_id)
    payload["group_id"] = group_id
    return jsonify(payload)


@app.route("/settlements/mark-paid", methods=["POST"])
def mark_paid():
    me = get_current_auth_user()
    if not me:
        return jsonify({"error": "login required"}), 401
    data = request.get_json() or {}
    split_id = data.get("split_id")
    from_user_id = data.get("from_user_id")
    to_user_id = data.get("to_user_id")
    amount = data.get("amount")
    if not split_id:
        return jsonify({"error": "split_id required"}), 400
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT s.split_id, s.expense_id, e.group_id, s.user_id, e.paid_by, s.share
        FROM splits s JOIN expenses e ON e.expense_id = s.expense_id
        WHERE s.split_id = ?
    """, (split_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "split not found"}), 404
    split_id, expense_id, group_id, actual_from_user_id, actual_to_user_id, actual_amount = row
    if get_linked_user_id(me[0]) != actual_from_user_id:
        conn.close()
        return jsonify({"error": "only the owing user can mark paid"}), 403
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""
        INSERT INTO settlement_actions (split_id, expense_id, group_id, from_user_id, to_user_id, amount, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 'paid', ?, ?)
        ON CONFLICT(split_id) DO UPDATE SET
            status='paid',
            updated_at=excluded.updated_at
    """, (split_id, expense_id, group_id, actual_from_user_id, actual_to_user_id, actual_amount, now_ts, now_ts))
    conn.commit()
    conn.close()
    return jsonify({"message": "marked as paid"})


@app.route("/settlements/mark-received", methods=["POST"])
def mark_received():
    me = get_current_auth_user()
    if not me:
        return jsonify({"error": "login required"}), 401
    data = request.get_json() or {}
    split_id = data.get("split_id")
    if not split_id:
        return jsonify({"error": "split_id required"}), 400
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT s.split_id, s.expense_id, e.group_id, s.user_id, e.paid_by, s.share
        FROM splits s JOIN expenses e ON e.expense_id = s.expense_id
        WHERE s.split_id = ?
    """, (split_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "split not found"}), 404
    split_id, expense_id, group_id, actual_from_user_id, actual_to_user_id, actual_amount = row
    if get_linked_user_id(me[0]) != actual_to_user_id:
        conn.close()
        return jsonify({"error": "only the receiving user can mark received"}), 403
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""
        INSERT INTO settlement_actions (split_id, expense_id, group_id, from_user_id, to_user_id, amount, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 'received', ?, ?)
        ON CONFLICT(split_id) DO UPDATE SET
            status='received',
            updated_at=excluded.updated_at
    """, (split_id, expense_id, group_id, actual_from_user_id, actual_to_user_id, actual_amount, now_ts, now_ts))
    conn.commit()
    conn.close()
    return jsonify({"message": "marked as received"})


# ---------------- RUN ---------------- #

import os

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        debug=False
    )
