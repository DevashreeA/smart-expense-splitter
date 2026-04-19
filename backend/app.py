# backend/app.py
print(">>> app.py starting")

# use relative imports because this file is part of the backend package
from .database import create_tables, get_connection   # or get_connection if that's your function name
from .calculations import get_totals, simplify_debts

from flask import Flask, request, jsonify
from flask_cors import CORS

from datetime import datetime

from flask import abort

app = Flask(__name__)
CORS(app)

# Ensure DB and tables exist
create_tables()

# --- Helper functions (simple) ---
def add_user_db(name):
    connect = get_connection()
    c = connect.cursor()
    c.execute("INSERT INTO users (name) VALUES (?)", (name,))
    connect.commit()
    uid = c.lastrowid
    connect.close()
    return uid

def list_users_db():
    connect = get_connection()
    c = connect.cursor()
    c.execute("SELECT user_id, name FROM users")
    rows = c.fetchall()
    connect.close()
    return [{"user_id": r[0], "name": r[1]} for r in rows]

def add_expense_db(amount, paid_by, description, involved_ids, shares=None):
    connect = get_connection()
    c = connect.cursor()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO expenses (paid_by, amount, description, date) VALUES (?, ?, ?, ?)",
              (paid_by, amount, description, date_str))
    expense_id = c.lastrowid
    if shares:
        for uid, s in zip(involved_ids, shares):
            c.execute("INSERT INTO splits (expense_id, user_id, share) VALUES (?, ?, ?)",
                      (expense_id, uid, s))
    else:
        per = round(amount / len(involved_ids), 2)
        for uid in involved_ids:
            c.execute("INSERT INTO splits (expense_id, user_id, share) VALUES (?, ?, ?)",
                      (expense_id, uid, per))
    connect.commit()
    connect.close()
    return expense_id

# --- API routes ---
@app.route("/")
def hello():
    return jsonify({"message": "Smart Expense Splitter API is running"})

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
    """
    Expected JSON:
    {
      "amount": 900,
      "paid_by": 1,
      "description": "Dinner",
      "involved": [1,2,3],
      "shares": [300,300,300]   # optional; if absent -> split equally
    }
    """
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
     
    # --- New endpoints for edit/delete and list expenses ---



# Get all expenses with their splits
@app.route("/expenses", methods=["GET"])
def api_list_expenses():
    connect = get_connection()
    c = connect.cursor()
    c.execute("SELECT expense_id, paid_by, amount, description, date FROM expenses ORDER BY expense_id DESC")
    expenses_rows = c.fetchall()

    expenses = []
    for er in expenses_rows:
        expense_id, paid_by, amount, description, date = er
        # get splits
        c.execute("SELECT user_id, share FROM splits WHERE expense_id = ?", (expense_id,))
        splits = [{"user_id": r[0], "share": r[1]} for r in c.fetchall()]
        expenses.append({
            "expense_id": expense_id,
            "paid_by": paid_by,
            "amount": amount,
            "description": description,
            "date": date,
            "splits": splits
        })
    connect.close()
    return jsonify(expenses)

# Delete a user (and related splits/expenses)
@app.route("/users/<int:user_id>", methods=["DELETE"])
def api_delete_user(user_id):
    connect = get_connection()
    c = connect.cursor()
    # find expenses paid by this user
    c.execute("SELECT expense_id FROM expenses WHERE paid_by = ?", (user_id,))
    exp_ids = [r[0] for r in c.fetchall()]

    # delete splits for those expenses (if any)
    if exp_ids:
        c.executemany("DELETE FROM splits WHERE expense_id = ?", [(eid,) for eid in exp_ids])
    # delete those expenses
    c.execute("DELETE FROM expenses WHERE paid_by = ?", (user_id,))

    # delete splits where this user was involved
    c.execute("DELETE FROM splits WHERE user_id = ?", (user_id,))

    # finally delete the user
    c.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    connect.commit()
    connect.close()
    return jsonify({"status": "ok", "deleted_user": user_id})

# Edit (rename) a user
@app.route("/users/<int:user_id>", methods=["PUT"])
def api_edit_user(user_id):
    data = request.get_json() or {}
    name = data.get("name")
    if not name:
        return jsonify({"error":"name required"}), 400
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET name = ? WHERE user_id = ?", (name, user_id))
    conn.commit()
    conn.close()
    return jsonify({"status":"ok", "user_id": user_id, "name": name})

# Delete an expense
@app.route("/expenses/<int:expense_id>", methods=["DELETE"])
def api_delete_expense(expense_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM splits WHERE expense_id = ?", (expense_id,))
    c.execute("DELETE FROM expenses WHERE expense_id = ?", (expense_id,))
    conn.commit()
    conn.close()
    return jsonify({"status":"ok", "deleted_expense": expense_id})

# Edit an expense (replace data and splits)
@app.route("/expenses/<int:expense_id>", methods=["PUT"])
def api_edit_expense(expense_id):
    data = request.get_json() or {}
    try:
        amount = float(data["amount"])
        paid_by = int(data["paid_by"])
        description = data.get("description", "")
        involved = data["involved"]        # list of ids
        shares = data.get("shares")       # optional list
    except Exception as e:
        return jsonify({"error": f"invalid input: {e}"}), 400

    connect = get_connection()
    c = connect.cursor()
    # update expense row
    c.execute("UPDATE expenses SET paid_by = ?, amount = ?, description = ? WHERE expense_id = ?",
              (paid_by, amount, description, expense_id))
    # remove old splits
    c.execute("DELETE FROM splits WHERE expense_id = ?", (expense_id,))
    # insert new splits
    if shares:
        for uid, s in zip(involved, shares):
            c.execute("INSERT INTO splits (expense_id, user_id, share) VALUES (?, ?, ?)",
                      (expense_id, uid, float(s)))
    else:
        per = round(amount / len(involved), 2)
        for uid in involved:
            c.execute("INSERT INTO splits (expense_id, user_id, share) VALUES (?, ?, ?)",
                      (expense_id, uid, per))
    connect.commit()
    connect.close()
    return jsonify({"status":"ok", "expense_id": expense_id})


@app.route("/summary", methods=["GET"])
def api_summary():
    totals = get_totals()
    return jsonify(totals)

@app.route("/settle", methods=["GET"])
def api_settle():
    totals = get_totals()
    txns = simplify_debts(totals)

    # Add names to the transactions (optional but nice)
    user_map = {uid: info["name"] for uid, info in totals.items()}
    for t in txns:
        t["from_name"] = user_map.get(t["from"], "")
        t["to_name"] = user_map.get(t["to"], "")
    return jsonify(txns)



if __name__ == "__main__":
    app.run(debug=True, port=5000)
