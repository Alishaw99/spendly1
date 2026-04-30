import os
import sqlite3
import calendar
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email, add_expense_to_db
import database.queries as queries
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = "dev-secret-key"

CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Date filter helpers                                                 #
# ------------------------------------------------------------------ #

def months_ago(n):
    today = datetime.today().date()
    month = today.month - n
    year  = today.year + (month - 1) // 12
    month = ((month - 1) % 12) + 1
    day   = min(today.day, calendar.monthrange(year, month)[1])
    return datetime(year, month, day).date().isoformat()


def parse_date(val):
    if not val:
        return None
    try:
        datetime.strptime(val, "%Y-%m-%d")
        return val
    except ValueError:
        return None


def fmt_display(val):
    if val is None:
        return None
    return datetime.strptime(val, "%Y-%m-%d").strftime("%d %b %Y")


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "POST":
        name     = request.form.get("name", "").strip()
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if not name:
            flash("Full name is required.", "error")
        elif not email:
            flash("Email address is required.", "error")
        elif not password:
            flash("Password is required.", "error")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        else:
            try:
                create_user(name, email, password)
                flash("Account created! Please sign in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("An account with that email already exists.", "error")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if not email or not password:
            flash("Email and password are required.", "error")
            return render_template("login.html")

        user = get_user_by_email(email)

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
            return render_template("login.html")

        session["user_id"]   = user["id"]
        session["user_name"] = user["name"]
        return redirect(url_for("profile"))

    return render_template("login.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = queries.get_user_by_id(session["user_id"])
    if user is None:
        abort(404)

    today     = datetime.today().date()
    today_str = today.isoformat()
    presets   = {"3m": months_ago(3), "6m": months_ago(6)}

    # Custom date range takes priority over preset buttons
    custom_from = parse_date(request.args.get("from", "").strip())
    custom_to   = parse_date(request.args.get("to",   "").strip())

    if custom_from or custom_to:
        period    = "custom"
        date_from = custom_from
        date_to   = custom_to
    else:
        period = request.args.get("period", "all")
        if period in presets:
            date_from = presets[period]
            date_to   = today_str
        else:
            period    = "all"
            date_from = None
            date_to   = None

    summary  = queries.get_summary_stats(session["user_id"], date_from=date_from, date_to=date_to)
    expenses = queries.get_recent_transactions(session["user_id"], date_from=date_from, date_to=date_to)
    raw_cats = queries.get_category_breakdown(session["user_id"], date_from=date_from, date_to=date_to)
    categories = [{"category": c["name"], "total": c["amount"]} for c in raw_cats]

    return render_template(
        "profile.html",
        user_name=user["name"],
        user_email=user["email"],
        user_joined=user["member_since"],
        total_spent=summary["total_spent"],
        expense_count=summary["transaction_count"],
        top_category=summary["top_category"],
        expenses=expenses,
        categories=categories,
        period=period,
        date_from=date_from,
        date_to=date_to,
        date_from_display=fmt_display(date_from),
        date_to_display=fmt_display(date_to),
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if not session.get("user_id"):
        if request.method == "POST":
            abort(403)
        return redirect(url_for("login"))

    if request.method == "POST":
        amount_raw   = request.form.get("amount", "").strip()
        category     = request.form.get("category", "")
        expense_date = request.form.get("date", "").strip()
        description  = request.form.get("description", "").strip()

        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except ValueError:
            flash("Amount must be a positive number.", "error")
            return render_template("add_expense.html", categories=CATEGORIES, form=request.form)

        if category not in CATEGORIES:
            flash("Please select a valid category.", "error")
            return render_template("add_expense.html", categories=CATEGORIES, form=request.form)

        try:
            datetime.strptime(expense_date, "%Y-%m-%d")
        except ValueError:
            flash("Please enter a valid date.", "error")
            return render_template("add_expense.html", categories=CATEGORIES, form=request.form)

        add_expense_to_db(session["user_id"], amount, category, expense_date, description or None)
        flash("Expense added successfully.", "success")
        return redirect(url_for("profile"))

    today = datetime.today().date().isoformat()
    return render_template("add_expense.html", categories=CATEGORIES, form={"date": today})


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1", port=5001)
