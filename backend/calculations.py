# backend/calculations.py
from backend.database import get_connection
from collections import defaultdict

def get_totals():
    """
    Returns a dict keyed by user_id:
    { user_id: { 'name': ..., 'paid': X, 'share': Y, 'balance': paid-share } }
    """
    connect = get_connection()
    c = connect.cursor()

    # total paid by each user
    c.execute("""
        SELECT u.user_id, u.name, IFNULL(SUM(e.amount), 0) as total_paid
        FROM users u
        LEFT JOIN expenses e ON u.user_id = e.paid_by
        GROUP BY u.user_id
    """)
    paid_rows = c.fetchall()
    paid = {r[0]: {"name": r[1], "paid": float(r[2] or 0)} for r in paid_rows}

    # total share for each user
    c.execute("""
        SELECT u.user_id, u.name, IFNULL(SUM(s.share), 0) as total_share
        FROM users u
        LEFT JOIN splits s ON u.user_id = s.user_id
        GROUP BY u.user_id
    """)
    share_rows = c.fetchall()
    share = {r[0]: {"name": r[1], "share": float(r[2] or 0)} for r in share_rows}

    # combine
    users = set(list(paid.keys()) + list(share.keys()))
    totals = {}
    for uid in users:
        name = paid.get(uid, {}).get("name") or share.get(uid, {}).get("name") or "Unknown"
        p = paid.get(uid, {}).get("paid", 0.0)
        s = share.get(uid, {}).get("share", 0.0)
        balance = round(p - s, 2)
        totals[uid] = {"user_id": uid, "name": name, "paid": round(p,2), "share": round(s,2), "balance": balance}

    connect.close()
    return totals

def simplify_debts(totals):
    """
    totals: output of get_totals()
    Return a list of transactions (debtor_id, creditor_id, amount)
    so that debts are settled with minimal number of transfers.
    """
    creditors = []
    debtors = []
    for uid, info in totals.items():
        bal = round(info["balance"], 2)
        if bal > 0:
            creditors.append([uid, bal])
        elif bal < 0:
            debtors.append([uid, -bal])  # positive amount they owe

    # sort not strictly required, but predictable
    creditors.sort(key=lambda x: x[0])
    debtors.sort(key=lambda x: x[0])

    transactions = []
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        debtor_id, owe_amt = debtors[i]
        creditor_id, cred_amt = creditors[j]
        pay = round(min(owe_amt, cred_amt), 2)
        if pay > 0:
            transactions.append({"from": debtor_id, "to": creditor_id, "amount": pay})
        debtors[i][1] -= pay
        creditors[j][1] -= pay
        if abs(debtors[i][1]) < 0.001:
            i += 1
        if abs(creditors[j][1]) < 0.001:
            j += 1

    return transactions
