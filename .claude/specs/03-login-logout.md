# Spec: Login and Logout

## Overview
This step wires up the login form and logout route so users can authenticate and end their session. The `GET /login` route already renders `login.html`, but the form does nothing. This step adds `POST /login` to validate credentials against the database, starts a Flask session on success, and implements `GET /logout` to clear the session and redirect home. Together these two routes give Spendly its first real access control boundary — subsequent steps can check `session["user_id"]` to gate protected pages.

## Depends on
- Step 01 — Database Setup (`get_db()`, `users` table)
- Step 02 — Registration (`get_user_by_email()`, hashed passwords with werkzeug)

## Routes
- `POST /login` — handles login form submission, starts session on success — public
- `GET /logout` — clears the session, redirects to `GET /` — public (but only meaningful when logged in)

## Database changes
No database changes. The `users` table (id, name, email, password_hash) from Step 01 is sufficient.

## Templates
- **Modify:** `templates/login.html` — ensure form uses `method="POST"` and `action="{{ url_for('login') }}"`, remove any dead `{% if error %}` block, rely on flash messages from `base.html`
- **Modify:** `templates/base.html` — update nav links to show "Sign out" when a user is logged in (check `session.get("user_id")`), hide "Sign in" / "Get started" when already authenticated

## Files to change
- `app.py` — add `POST /login` handler; implement `GET /logout`; import `session` from Flask; import `check_password_hash` from werkzeug (or use `get_user_by_email` + `check_password_hash`)
- `database/db.py` — no changes needed (`get_user_by_email()` already exists)
- `templates/login.html` — fix form method/action, remove dead error block
- `templates/base.html` — conditional nav links based on session state

## Files to create
- None

## New dependencies
No new dependencies. `werkzeug.security.check_password_hash` is already available via the installed werkzeug package.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders) — never f-strings in SQL
- Passwords verified with `werkzeug.security.check_password_hash` — never compare plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Store only `user_id` and `user_name` in the session — never store the password hash
- On failed login (wrong email or wrong password) show a single generic flash error: "Invalid email or password." — do not reveal which field was wrong
- On successful login redirect to `GET /` (landing) using `url_for('landing')` — a dashboard route does not exist yet
- `GET /logout` must call `session.clear()` then redirect to `url_for('landing')`
- Import `session` from Flask (already imported as part of the flask package)
- Use `abort()` only for genuine HTTP errors — use `flash()` + re-render for credential failures

## Definition of done
- [ ] Submitting valid credentials sets `session["user_id"]` and redirects to `/`
- [ ] Submitting an unknown email shows flash "Invalid email or password." and stays on `/login`
- [ ] Submitting a correct email with wrong password shows flash "Invalid email or password." and stays on `/login`
- [ ] Submitting with empty email or password shows a validation flash error
- [ ] Visiting `/logout` clears the session and redirects to `/`
- [ ] After logout, `session.get("user_id")` is `None`
- [ ] Nav bar shows "Sign out" link when logged in, "Sign in" / "Get started" when logged out
- [ ] App starts without errors
- [ ] No plaintext passwords anywhere in session or logs
