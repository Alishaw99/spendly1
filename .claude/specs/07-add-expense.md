# Spec: Add Expense

## Overview
This step implements the `/expenses/add` route so logged-in users can record a
new expense. The route currently returns a raw string stub. After this step,
a form-based page lets the user enter an amount, category, date, and optional
description. On valid submission the expense is inserted into the `expenses`
table and the user is redirected to their profile page. This is the first
write operation in Spendly and is the foundation for the edit and delete steps
that follow.

## Depends on
- Step 01 — Database Setup (`get_db()`, `expenses` table)
- Step 02 — Registration (`users` table, `user_id` foreign key)
- Step 03 — Login and Logout (`session["user_id"]` set on login)
- Step 04 — Profile Page Design (`profile.html` already renders expense list)
- Step 05 — Backend Routes (`database/queries.py`, live query helpers)

## Routes
- `GET /expenses/add` — renders the add-expense form — logged-in only
- `POST /expenses/add` — handles form submission, inserts expense, redirects — logged-in only

## Database changes
No new tables or columns. The `expenses` table from Step 01 is sufficient:
- `id`, `user_id`, `amount`, `category`, `date`, `description`, `created_at`

## Templates
- **Create:** `templates/add_expense.html` — form page extending `base.html`
  with fields for amount, category (dropdown), date, and description
- **Modify:** `templates/base.html` — add an "Add Expense" nav link for
  authenticated users pointing to `url_for('add_expense')`

## Files to change
- `app.py` — replace the stub `add_expense()` route with a real GET+POST
  handler; import `add_expense_to_db` from `database.db`
- `database/db.py` — add `add_expense_to_db(user_id, amount, category, date, description)` helper
- `templates/base.html` — add "Add Expense" nav link for logged-in users

## Files to create
- `templates/add_expense.html` — the add-expense form template
- `static/css/add_expense.css` — page-specific styles loaded via `{% block head %}`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders) — never f-strings in SQL
- Passwords hashed with werkzeug (not relevant here but keep existing pattern)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Unauthenticated access to `GET /expenses/add` must redirect to
  `url_for('login')` — check `session.get("user_id")`
- `amount` must be validated server-side: must be a positive number greater
  than zero; reject non-numeric input with a flash error
- `category` must be one of the fixed list: Food, Transport, Bills, Health,
  Entertainment, Shopping, Other — validate server-side
- `date` must be a valid `YYYY-MM-DD` string — validate with
  `datetime.strptime`; default to today's date on `GET`
- `description` is optional — store `None` if blank
- On validation failure: flash an error and re-render the form with the
  user's previously entered values preserved
- On success: flash a success message and redirect to `url_for('profile')`
  using `redirect()`
- `add_expense_to_db()` belongs in `database/db.py` — never inline SQL in
  the route
- The category dropdown must use the exact same fixed list as used in
  `seed_db()`: Food, Transport, Bills, Health, Entertainment, Shopping, Other
- Use `abort(403)` if a logged-out user somehow reaches the POST handler

## Definition of done
- [ ] Visiting `/expenses/add` while logged in renders a form with amount,
  category dropdown, date, and description fields
- [ ] The date field defaults to today's date on GET
- [ ] Submitting the form with valid data inserts a row into `expenses` and
  redirects to `/profile`
- [ ] The newly added expense appears in the transaction list on `/profile`
- [ ] Submitting with a blank or zero amount shows a flash error and
  re-renders the form
- [ ] Submitting with an invalid category shows a flash error
- [ ] Submitting with an invalid date shows a flash error
- [ ] Visiting `/expenses/add` while **not** logged in redirects to `/login`
- [ ] The navbar shows an "Add Expense" link when logged in
- [ ] All SQL in `db.py` uses parameterised queries — no f-strings
- [ ] App starts without errors
