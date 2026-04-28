# Spec: Registration

## Overview
This step wires up the registration form so new users can create an account. The `GET /register` route already renders `register.html`, but the form currently does nothing. This step adds the `POST /register` route to validate input, hash the password, insert the new user into the database, and redirect on success. It also adds the `create_user()` and `get_user_by_email()` helper functions to `database/db.py`.

## Depends on
- Step 01 — Database Setup (`get_db()`, `init_db()`, `seed_db()`, `users` table)

## Routes
- `POST /register` — handles registration form submission — public

## Database changes
No new tables or columns. The `users` table from Step 01 is sufficient:
- `id`, `name`, `email` (UNIQUE), `password_hash`, `created_at`

## Templates
- **Modify:** `templates/register.html` — ensure the form uses `method="POST"` and `action="{{ url_for('register') }}"`, add flash message display block for validation errors and success feedback.

## Files to change
- `app.py` — add `POST /register` route handler; import `flash`, `redirect`, `request` from Flask; import `create_user`, `get_user_by_email` from `database.db`; set `app.secret_key`
- `database/db.py` — add `create_user()` and `get_user_by_email()` helpers
- `templates/register.html` — add `method="POST"`, correct `action`, flash message display

## Files to create
- None

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders) — never f-strings in SQL
- Passwords hashed with `werkzeug.security.generate_password_hash` — never store plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `secret_key` must be set on `app` for `flash()` to work — use a hardcoded dev string for now (e.g. `"dev-secret-key"`)
- Duplicate email must show a user-facing flash error, not a 500 — catch the `sqlite3.IntegrityError`
- After successful registration redirect to `GET /login` using `url_for('login')`
- Validate server-side: name, email, and password must all be non-empty; password must be at least 8 characters
- Use `abort()` only for genuine HTTP errors — use `flash()` + re-render for form validation failures

## Definition of done
- [ ] Submitting the registration form with valid data creates a new row in `users` with a hashed password
- [ ] Submitting with a duplicate email shows a flash error and does not crash
- [ ] Submitting with an empty name, email, or password shows a validation error
- [ ] Submitting with a password shorter than 8 characters shows a validation error
- [ ] Successful registration redirects to `/login`
- [ ] App starts without errors
- [ ] All queries in `db.py` use parameterised SQL
