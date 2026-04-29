from datetime import datetime
import math
from database.db import get_db


def get_user_by_id(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT id, name, email, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    member_since = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S").strftime("%B %Y")
    return {"name": row["name"], "email": row["email"], "member_since": member_since}


def get_summary_stats(user_id):
    conn = get_db()
    agg = conn.execute(
        "SELECT COALESCE(SUM(amount), 0.0) AS total_spent, COUNT(*) AS transaction_count "
        "FROM expenses WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    top = conn.execute(
        "SELECT category FROM expenses WHERE user_id = ? "
        "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    conn.close()
    return {
        "total_spent": float(agg["total_spent"]),
        "transaction_count": int(agg["transaction_count"]),
        "top_category": top["category"] if top else "—",
    }


def get_recent_transactions(user_id, limit=10):
    conn = get_db()
    rows = conn.execute(
        "SELECT amount, category, date, description "
        "FROM expenses WHERE user_id = ? ORDER BY date DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [
        {
            "date": r["date"],
            "description": r["description"],
            "category": r["category"],
            "amount": float(r["amount"]),
        }
        for r in rows
    ]


def get_category_breakdown(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT category, SUM(amount) AS total "
        "FROM expenses WHERE user_id = ? "
        "GROUP BY category ORDER BY total DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    if not rows:
        return []
    grand_total = sum(r["total"] for r in rows)
    raw_pcts = [(r["total"] / grand_total) * 100 for r in rows]
    pcts = [math.floor(p) for p in raw_pcts]
    remainder = 100 - sum(pcts)
    fractions = sorted(
        range(len(raw_pcts)),
        key=lambda i: raw_pcts[i] - math.floor(raw_pcts[i]),
        reverse=True,
    )
    for i in range(remainder):
        pcts[fractions[i]] += 1
    return [
        {"name": rows[i]["category"], "amount": float(rows[i]["total"]), "pct": pcts[i]}
        for i in range(len(rows))
    ]
