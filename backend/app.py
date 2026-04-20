print(">>> app.py starting")

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from datetime import datetime

# use relative imports
from database import create_tables, get_connection
from calculations import get_totals, simplify_debts

app = Flask(__name__, template_folder="templates")
CORS(app)

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
        description = data.get("description", "")
        involved = data["involved"]
        shares = data.get("shares")

        if shares:
            shares = [float(s) for s in shares]

    except Exception as e:
        return jsonify({"error": f"invalid input: {e}"}), 400

    expense_id = add_expense_db(amount, paid_by, description, involved, shares)
    return jsonify({"expense_id": expense_id}), 201


@app.route("/expenses", methods=["GET"])
def api_list_expenses():
    conn = get_connection()
    c = conn.cursor()

    c.execute(
        "SELECT expense_id, paid_by, amount, description, date FROM expenses ORDER BY expense_id DESC"
    )

    rows = c.fetchall()
    expenses = []

    for r in rows:
        expense_id, paid_by, amount, description, date = r

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
                "description": description,
                "date": date,
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
        description = data.get("description", "")
        involved = data["involved"]
        shares = data.get("shares")

    except Exception as e:
        return jsonify({"error": f"invalid input: {e}"}), 400

    conn = get_connection()
    c = conn.cursor()

    c.execute(
        "UPDATE expenses SET paid_by = ?, amount = ?, description = ? WHERE expense_id = ?",
        (paid_by, amount, description, expense_id),
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


# ---------------- RUN ---------------- #

if __name__ == "__main__":
    app.run(debug=True, port=5000)