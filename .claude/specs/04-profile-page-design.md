# Spec: Profile Page Design

## Overview
This step implements the `/profile` route so logged-in users can see their account details and a summary of their spending activity. The route currently returns a raw string stub; this step replaces it with a proper template that displays the user's name, email, join date, and a high-level expense summary (total spent, number of expenses, top category). The page is the user's first post-login destination beyond the landing page and sets the visual foundation for the dashboard experience that expense management steps will build on.

## Depends on
- Step 01 — Database Setup (`get_db()`, `users` table, `expenses` table)
- Step 02 — Registration (`create_user()`, `users` schema)
- Step 03 — Login and Logout (`session["user_id"]`, `session["user_name"]`, auth gating pattern)

## Routes
- `GET /profile` — renders the profile page with user info and expense summary — logged-in only (redirect to `/login` if not authenticated)

## Database changes
No new tables or columns. The existing `users` and `expenses` tables are sufficient.

## Templates
- **Create:** `templates/profile.html` — profile page extending `base.html`; displays user name, email, join date, total spent, expense count, and top spending category
- **Modify:** `templates/base.html` — add a "Profile" nav link in the authenticated nav links block (shown only when `session.get("user_id")`)

## Files to change
- `app.py` — replace the stub `profile()` route with a real handler: check session, fetch user data and expense summary, render `profile.html`; import `get_user_by_id` and `get_expense_summary` from `database.db`
- `database/db.py` — add `get_user_by_id(user_id)` and `get_expense_summary(user_id)` helpers
- `templates/base.html` — add Profile nav link for authenticated users
- `templates/profile.html` — create the profile page template

## Files to create
- `templates/profile.html` — the profile page
- `static/css/profile.css` — page-specific styles (imported via `{% block head %}` in `profile.html`)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders) — never f-strings in SQL
- Passwords hashed with werkzeug — never expose `password_hash` to the template
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Unauthenticated access to `/profile` must redirect to `url_for('login')` — use `session.get("user_id")`, not a decorator
- `get_user_by_id(user_id)` — fetches a single user row by primary key; call `abort(404)` in the route if the result is `None`
- `get_expense_summary(user_id)` — returns a dict with keys: `total_spent` (REAL), `expense_count` (INTEGER), `top_category` (TEXT or `None` if no expenses)
- The route must pass only serialisable data to the template — no raw `sqlite3.Row` objects for the summary dict
- Page-specific styles go in `static/css/profile.css`, loaded via `{% block head %}` in `profile.html`
- The profile template must not display the password hash or any internal DB fields other than `id`, `name`, `email`, `created_at`

## Definition of done
- [ ] Visiting `/profile` while logged in renders a page showing the user's name and email
- [ ] The page shows the account creation date from the `created_at` column
- [ ] The page shows total amount spent (sum of all expense amounts for that user)
- [ ] The page shows total number of expenses for that user
- [ ] The page shows the top spending category (category with the highest total amount), or a placeholder if no expenses exist
- [ ] Visiting `/profile` while **not** logged in redirects to `/login`
- [ ] The navbar shows a "Profile" link when logged in
- [ ] The profile page uses CSS variables exclusively — no hardcoded hex values
- [ ] App starts without errors
- [ ] All new DB queries use parameterised SQL
