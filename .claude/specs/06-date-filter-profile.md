# Spec: Date Filter for Profile Page

## Overview
This step adds a date range filter to the `/profile` page so users can narrow
their spending view to a specific period. Currently the profile page always
displays all-time stats, all transactions, and the full category breakdown.
After this step, two optional query-string parameters (`from` and `to`) let
users filter by date range; the summary stats, transaction list, and category
breakdown all update to reflect only expenses that fall within the chosen
window. The filter form sits above the spending data and pre-fills with the
active range on every load.

## Depends on
- Step 01 — Database Setup (`get_db()`, `expenses` table with `date` column)
- Step 02 — Registration (users in the database)
- Step 03 — Login and Logout (`session["user_id"]` set on login)
- Step 04 — Profile Page Design (`profile.html` template structure)
- Step 05 — Backend Routes (`database/queries.py`, live query helpers)

## Routes
No new routes. The existing `GET /profile` route is modified to accept
optional query-string parameters:
- `GET /profile?from=YYYY-MM-DD&to=YYYY-MM-DD` — filters all profile data
  to the given date range — logged-in only

## Database changes
No database changes. The `expenses.date` column (`TEXT`, `YYYY-MM-DD`) is
already present and sufficient for range filtering.

## Templates
- **Modify:** `templates/profile.html`
  - Add a filter form above the Spending Summary section
  - Form uses `method="GET"` and `action="{{ url_for('profile') }}"`
  - Two `<input type="date">` fields: `name="from"` and `name="to"`
  - A submit button labelled "Apply"
  - A "Clear" link that points to `url_for('profile')` (no query params)
  - Both inputs pre-fill with the currently active `date_from` / `date_to`
    values passed from the route
  - All four data sections (summary stats, category breakdown, transaction
    list, empty states) must reflect the filtered data, not all-time data

## Files to change
- `app.py` — update `profile()` route: read `from` and `to` from
  `request.args`, validate they are valid `YYYY-MM-DD` strings (ignore
  malformed values silently), pass them as `date_from` / `date_to` to every
  query helper and to the template
- `database/queries.py` — add optional `date_from` and `date_to` parameters
  to `get_summary_stats()`, `get_recent_transactions()`, and
  `get_category_breakdown()`; when provided, append
  `AND date >= ? AND date <= ?` to the WHERE clause
- `templates/profile.html` — add the filter form as described above

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never f-strings or string concatenation in SQL
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Validate `from` / `to` params in the route using `datetime.strptime` with
  `"%Y-%m-%d"` — silently set to `None` on any parse error (do not flash or
  abort)
- When `date_from` is `None` and `date_to` is `None`, behaviour must be
  identical to the unfiltered profile page (no regression)
- When only one bound is provided, apply only that bound (open-ended range)
- Query helpers must not import Flask — keep them pure Python with `get_db()`
- The filter form input names must be exactly `from` and `to` (matching
  `request.args`)
- Do not change the `get_user_by_id()` helper — user info is never filtered
- Summary stats shown when a filter is active must clearly indicate they
  reflect the filtered period, not all time — pass `date_from` and `date_to`
  to the template and conditionally show a label such as
  "Filtered: DD Mon YYYY – DD Mon YYYY" next to the section heading

## Definition of done
- [ ] Visiting `/profile` with no query params shows all-time data
  (no regression from Step 05)
- [ ] Visiting `/profile?from=2026-04-01&to=2026-04-15` shows only expenses
  with date between 2026-04-01 and 2026-04-15 (inclusive)
- [ ] Total spent, expense count, and top category all reflect the filtered
  range, not all-time totals
- [ ] Category breakdown shows only categories that have expenses in the
  filtered range; percentages still sum to 100
- [ ] Transaction list shows only transactions within the filtered range,
  ordered newest-first
- [ ] Filter form inputs pre-fill with the active `from` / `to` values after
  applying a filter
- [ ] Clicking "Clear" returns to the unfiltered profile page
- [ ] A malformed date in `from` or `to` (e.g. `?from=abc`) is silently
  ignored — the page loads as if that param were absent
- [ ] When a filter is active, a label near the summary heading shows the
  active date range
- [ ] A user with no expenses in the filtered range sees zero stats and empty
  lists without errors
- [ ] All new SQL uses parameterised queries — no f-strings in SQL
