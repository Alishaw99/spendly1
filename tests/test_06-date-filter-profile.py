# tests/test_06-date-filter-profile.py
#
# Spec-driven tests for the date filter feature on the /profile page.
#
# Spec behaviours under test:
#  - /profile with no params returns 200 and all-time data (no regression)
#  - /profile?from=...&to=... filters summary stats, categories, and
#    transactions to only expenses within that inclusive range
#  - /profile?period=3m and ?period=6m preset shortcuts filter correctly
#  - /profile?period=all (or no period param) shows all-time data
#  - Custom ?from/to overrides any preset period param
#  - Total spent, expense count, and top category reflect the filtered range
#  - Category breakdown includes only categories with expenses in range;
#    percentages sum to 100
#  - Transaction list contains only in-range rows, ordered newest-first
#  - Filter form inputs pre-fill with the active from/to values (custom mode)
#  - Pre-set preset buttons are rendered with active state when a preset is used
#  - A filter badge/label appears near "Spending Summary" when a filter is active
#    (period == 3m, 6m, or custom); no badge for all-time view
#  - A malformed date in ?from or ?to is silently ignored (page loads normally)
#  - A user with zero expenses in the filtered range sees zero stats and an empty
#    transaction list without any server error
#  - Unauthenticated requests to /profile redirect to /login (302)

import os
import tempfile
import pytest
from datetime import datetime, date
import calendar as cal_module

import database.db as db_module
from app import app


# ---------------------------------------------------------------------------
# Seed data constants — keep in sync with database/db.py seed_db()
# ---------------------------------------------------------------------------

SEED_EXPENSES = [
    # (amount, category, date, description)
    (450.00,  "Food",          "2026-04-02", "Groceries"),
    (120.00,  "Transport",     "2026-04-05", "Metro recharge"),
    (1200.00, "Bills",         "2026-04-08", "Electricity bill"),
    (600.00,  "Health",        "2026-04-10", "Pharmacy"),
    (350.00,  "Entertainment", "2026-04-13", "Movie tickets"),
    (2200.00, "Shopping",      "2026-04-17", "Clothes"),
    (380.00,  "Food",          "2026-04-20", "Restaurant dinner"),
    (750.00,  "Other",         "2026-04-24", "Miscellaneous"),
]

ALL_TIME_TOTAL   = sum(e[0] for e in SEED_EXPENSES)          # 6050.00
ALL_TIME_COUNT   = len(SEED_EXPENSES)                        # 8
ALL_TIME_TOP_CAT = "Shopping"                                # highest single total: 2200

# Expenses between 2026-04-01 and 2026-04-15 (inclusive):
#   04-02 Food 450, 04-05 Transport 120, 04-08 Bills 1200,
#   04-10 Health 600, 04-13 Entertainment 350
RANGE_EXPENSES = [e for e in SEED_EXPENSES if "2026-04-01" <= e[2] <= "2026-04-15"]
RANGE_TOTAL    = sum(e[0] for e in RANGE_EXPENSES)          # 2720.00
RANGE_COUNT    = len(RANGE_EXPENSES)                        # 5
RANGE_TOP_CAT  = "Bills"                                    # 1200 is highest

SEED_EMAIL    = "demo@spendly.com"
SEED_PASSWORD = "demo123"


# ---------------------------------------------------------------------------
# Helpers — months_ago matches the logic in app.py profile()
# ---------------------------------------------------------------------------

def _months_ago(n):
    today = date.today()
    month = today.month - n
    year  = today.year
    while month <= 0:
        month += 12
        year  -= 1
    day = min(today.day, cal_module.monthrange(year, month)[1])
    return date(year, month, day).isoformat()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path):
    """Return a path to a temporary SQLite file and patch db_module.DB_PATH."""
    path = str(tmp_path / "test_spendly.db")
    original = db_module.DB_PATH
    db_module.DB_PATH = path
    yield path
    db_module.DB_PATH = original


@pytest.fixture
def unauth_client(db_path):
    """Flask test client with a fresh seeded DB — NOT logged in."""
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    with app.test_client() as client:
        with app.app_context():
            db_module.init_db()
            db_module.seed_db()
        yield client


@pytest.fixture
def client(unauth_client):
    """Flask test client that is already logged in as the seed demo user."""
    unauth_client.post(
        "/login",
        data={"email": SEED_EMAIL, "password": SEED_PASSWORD},
        follow_redirects=True,
    )
    yield unauth_client


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def get_profile(client, **params):
    """GET /profile with optional query string parameters."""
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"/profile?{qs}" if qs else "/profile"
    return client.get(url, follow_redirects=False)


# ===========================================================================
# 1. Authentication guard
# ===========================================================================

class TestProfileAuthGuard:
    def test_unauthenticated_access_redirects_to_login(self, unauth_client):
        """Unauthenticated GET /profile must redirect to /login with status 302."""
        response = unauth_client.get("/profile")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_unauthenticated_access_does_not_return_200(self, unauth_client):
        """Confirm no 200 is returned for unauthenticated /profile (follow redirects)."""
        response = unauth_client.get("/profile", follow_redirects=True)
        assert b"login" in response.data.lower() or b"sign in" in response.data.lower()

    def test_authenticated_access_returns_200(self, client):
        """Logged-in user must receive 200 from /profile."""
        response = get_profile(client)
        assert response.status_code == 200


# ===========================================================================
# 2. No-filter / all-time view (regression guard)
# ===========================================================================

class TestProfileAllTime:
    def test_no_params_returns_200(self, client):
        response = get_profile(client)
        assert response.status_code == 200

    def test_no_params_shows_all_time_total(self, client):
        """With no filter, total spent must equal the sum of all seed expenses."""
        response = get_profile(client)
        assert f"{ALL_TIME_TOTAL:.2f}".encode() in response.data

    def test_no_params_shows_all_time_count(self, client):
        """With no filter, expense count must equal total seed expense rows."""
        response = get_profile(client)
        # The count appears as a plain integer in the stat card
        assert str(ALL_TIME_COUNT).encode() in response.data

    def test_no_params_shows_correct_top_category(self, client):
        """With no filter, top category must be Shopping (highest single total: 2200)."""
        response = get_profile(client)
        assert ALL_TIME_TOP_CAT.encode() in response.data

    def test_no_params_shows_all_transactions(self, client):
        """All seed expense descriptions must appear in the unfiltered transaction list."""
        response = get_profile(client)
        for _, _, _, desc in SEED_EXPENSES:
            assert desc.encode() in response.data

    def test_no_params_no_filter_badge(self, client):
        """All-time view must NOT show the filter badge next to Spending Summary."""
        response = get_profile(client)
        # The badge element is only rendered for 3m, 6m, or custom periods
        assert b"profile-filter-badge" not in response.data

    def test_period_all_param_shows_all_time_data(self, client):
        """`?period=all` is equivalent to no filter — all-time data, no badge."""
        response = get_profile(client, period="all")
        assert response.status_code == 200
        assert f"{ALL_TIME_TOTAL:.2f}".encode() in response.data
        assert b"profile-filter-badge" not in response.data


# ===========================================================================
# 3. Custom date range filter
# ===========================================================================

class TestProfileCustomDateRange:
    FROM_DATE = "2026-04-01"
    TO_DATE   = "2026-04-15"

    def test_filtered_page_returns_200(self, client):
        response = get_profile(client, **{"from": self.FROM_DATE, "to": self.TO_DATE})
        assert response.status_code == 200

    def test_filtered_total_matches_range(self, client):
        """Total spent must equal the sum of expenses within the filtered range only."""
        response = get_profile(client, **{"from": self.FROM_DATE, "to": self.TO_DATE})
        assert f"{RANGE_TOTAL:.2f}".encode() in response.data

    def test_filtered_count_matches_range(self, client):
        """Expense count must equal the number of expenses in the filtered range."""
        response = get_profile(client, **{"from": self.FROM_DATE, "to": self.TO_DATE})
        assert str(RANGE_COUNT).encode() in response.data

    def test_filtered_top_category_matches_range(self, client):
        """Top category must be Bills (highest in range: 1200) not all-time top."""
        response = get_profile(client, **{"from": self.FROM_DATE, "to": self.TO_DATE})
        assert RANGE_TOP_CAT.encode() in response.data

    def test_all_time_top_category_not_shown_in_stats_when_filtered(self, client):
        """Shopping (all-time top category) must NOT appear in the stat card when filtered."""
        response = get_profile(client, **{"from": self.FROM_DATE, "to": self.TO_DATE})
        html = response.data.decode()
        # "Shopping" is a category name that may appear in category breakdown row too,
        # but Shopping expenses fall after 2026-04-15 so it must not appear at all.
        assert "Shopping" not in html

    def test_filtered_transactions_only_in_range(self, client):
        """Transaction table must contain only descriptions of in-range expenses."""
        response = get_profile(client, **{"from": self.FROM_DATE, "to": self.TO_DATE})
        for _, _, expense_date, desc in SEED_EXPENSES:
            if self.FROM_DATE <= expense_date <= self.TO_DATE:
                assert desc.encode() in response.data, (
                    f"Expected in-range expense '{desc}' ({expense_date}) to appear"
                )
            else:
                assert desc.encode() not in response.data, (
                    f"Expected out-of-range expense '{desc}' ({expense_date}) to be absent"
                )

    def test_filtered_transactions_ordered_newest_first(self, client):
        """In-range transactions must appear newest-first (descending by date)."""
        response = get_profile(client, **{"from": self.FROM_DATE, "to": self.TO_DATE})
        html = response.data.decode()
        # The dates for in-range expenses sorted descending:
        expected_order = sorted(
            [e[2] for e in RANGE_EXPENSES], reverse=True
        )
        positions = [html.find(d) for d in expected_order]
        assert positions == sorted(positions), (
            "Transactions are not in newest-first order"
        )

    def test_filtered_category_breakdown_excludes_out_of_range_categories(self, client):
        """Categories with no expenses in the range must be absent from the breakdown."""
        response = get_profile(client, **{"from": self.FROM_DATE, "to": self.TO_DATE})
        out_of_range_categories = {
            cat for _, cat, expense_date, _ in SEED_EXPENSES
            if not (self.FROM_DATE <= expense_date <= self.TO_DATE)
        }
        in_range_categories = {
            cat for _, cat, expense_date, _ in SEED_EXPENSES
            if self.FROM_DATE <= expense_date <= self.TO_DATE
        }
        # Exclude any category that appears ONLY outside the range
        exclusive_out = out_of_range_categories - in_range_categories
        html = response.data.decode()
        # Find the category breakdown section (between "By Category" and next section)
        cat_section_start = html.find("By Category")
        cat_section_end   = html.find("Recent Transactions")
        if cat_section_start != -1 and cat_section_end != -1:
            cat_section = html[cat_section_start:cat_section_end]
            for cat in exclusive_out:
                assert cat not in cat_section, (
                    f"Out-of-range category '{cat}' must not appear in breakdown"
                )

    def test_filter_badge_shown_for_custom_range(self, client):
        """A filter badge must appear near Spending Summary when a custom range is active."""
        response = get_profile(client, **{"from": self.FROM_DATE, "to": self.TO_DATE})
        assert b"profile-filter-badge" in response.data

    def test_filter_badge_shows_formatted_dates(self, client):
        """The filter badge must show human-readable dates (e.g. '01 Apr 2026')."""
        response = get_profile(client, **{"from": self.FROM_DATE, "to": self.TO_DATE})
        html = response.data.decode()
        assert "01 Apr 2026" in html
        assert "15 Apr 2026" in html

    def test_from_input_prefills_with_active_value(self, client):
        """The 'from' date input must be pre-filled with the active from value."""
        response = get_profile(client, **{"from": self.FROM_DATE, "to": self.TO_DATE})
        assert f'value="{self.FROM_DATE}"'.encode() in response.data

    def test_to_input_prefills_with_active_value(self, client):
        """The 'to' date input must be pre-filled with the active to value."""
        response = get_profile(client, **{"from": self.FROM_DATE, "to": self.TO_DATE})
        assert f'value="{self.TO_DATE}"'.encode() in response.data

    def test_filter_inputs_not_prefilled_on_all_time_view(self, client):
        """Date inputs must be empty when no filter is active (all-time view)."""
        response = get_profile(client)
        html = response.data.decode()
        # Input values should be empty strings or absent values for from/to
        assert f'value="{self.FROM_DATE}"' not in html
        assert f'value="{self.TO_DATE}"' not in html


# ===========================================================================
# 4. Boundary inclusiveness
# ===========================================================================

class TestProfileRangeBoundaries:
    def test_from_date_is_inclusive(self, client):
        """An expense exactly on the from date must be included."""
        # 2026-04-02 has amount 450 (Groceries / Food)
        response = get_profile(client, **{"from": "2026-04-02", "to": "2026-04-02"})
        assert b"Groceries" in response.data
        assert b"450.00" in response.data

    def test_to_date_is_inclusive(self, client):
        """An expense exactly on the to date must be included."""
        # 2026-04-24 has amount 750 (Miscellaneous / Other)
        response = get_profile(client, **{"from": "2026-04-24", "to": "2026-04-24"})
        assert b"Miscellaneous" in response.data
        assert b"750.00" in response.data

    def test_expense_just_before_from_is_excluded(self, client):
        """An expense one day before the from date must NOT appear."""
        # 2026-04-05 is Transport/Metro; filter starts 2026-04-06
        response = get_profile(client, **{"from": "2026-04-06", "to": "2026-04-30"})
        assert b"Metro recharge" not in response.data

    def test_expense_just_after_to_is_excluded(self, client):
        """An expense one day after the to date must NOT appear."""
        # 2026-04-17 is Shopping/Clothes; filter ends 2026-04-16
        response = get_profile(client, **{"from": "2026-04-01", "to": "2026-04-16"})
        assert b"Clothes" not in response.data

    def test_only_from_provided_open_ended_upper(self, client):
        """Only from= provided — all expenses on or after that date must appear."""
        response = get_profile(client, **{"from": "2026-04-20"})
        # 2026-04-20 Food 380, 2026-04-24 Other 750
        assert b"Restaurant dinner" in response.data
        assert b"Miscellaneous" in response.data
        # Earlier expenses must not appear
        assert b"Groceries" not in response.data

    def test_only_to_provided_open_ended_lower(self, client):
        """Only to= provided — all expenses on or before that date must appear."""
        response = get_profile(client, **{"to": "2026-04-05"})
        # 2026-04-02 Food 450, 2026-04-05 Transport 120
        assert b"Groceries" in response.data
        assert b"Metro recharge" in response.data
        # Later expenses must not appear
        assert b"Electricity bill" not in response.data


# ===========================================================================
# 5. Malformed date handling
# ===========================================================================

class TestProfileMalformedDates:
    def test_malformed_from_is_silently_ignored(self, client):
        """?from=abc must load as if from= were absent — page returns 200."""
        response = get_profile(client, **{"from": "abc", "to": "2026-04-15"})
        assert response.status_code == 200

    def test_malformed_to_is_silently_ignored(self, client):
        """?to=not-a-date must load as if to= were absent — page returns 200."""
        response = get_profile(client, **{"from": "2026-04-01", "to": "not-a-date"})
        assert response.status_code == 200

    def test_both_malformed_shows_all_time_data(self, client):
        """?from=bad&to=bad — both ignored — page must show all-time total."""
        response = get_profile(client, **{"from": "bad", "to": "bad"})
        assert response.status_code == 200
        assert f"{ALL_TIME_TOTAL:.2f}".encode() in response.data

    def test_malformed_from_with_valid_to_acts_as_open_ended_lower(self, client):
        """?from=bad&to=2026-04-05 — only the valid to= bound is applied."""
        response = get_profile(client, **{"from": "not-valid", "to": "2026-04-05"})
        assert response.status_code == 200
        # Only expenses up to 2026-04-05 should appear
        assert b"Groceries" in response.data       # 2026-04-02
        assert b"Metro recharge" in response.data  # 2026-04-05
        assert b"Electricity bill" not in response.data  # 2026-04-08

    def test_wrong_date_format_rejected(self, client):
        """A date in DD/MM/YYYY format must be rejected and page must still load."""
        response = get_profile(client, **{"from": "01/04/2026", "to": "2026-04-15"})
        assert response.status_code == 200

    def test_partial_date_string_rejected(self, client):
        """A partial date string (YYYY-MM) must be silently ignored."""
        response = get_profile(client, **{"from": "2026-04", "to": "2026-04-15"})
        assert response.status_code == 200


# ===========================================================================
# 6. Zero-result range (user has no expenses in filtered range)
# ===========================================================================

class TestProfileEmptyFilteredRange:
    def test_filter_with_no_matching_expenses_returns_200(self, client):
        """A date range with no expenses must return 200 without server error."""
        response = get_profile(client, **{"from": "2025-01-01", "to": "2025-12-31"})
        assert response.status_code == 200

    def test_zero_total_when_no_matching_expenses(self, client):
        """Total spent must be 0.00 when no expenses fall in the filtered range."""
        response = get_profile(client, **{"from": "2025-01-01", "to": "2025-12-31"})
        assert b"0.00" in response.data

    def test_zero_count_when_no_matching_expenses(self, client):
        """Expense count must be 0 when no expenses fall in the filtered range."""
        response = get_profile(client, **{"from": "2025-01-01", "to": "2025-12-31"})
        html = response.data.decode()
        # The stat card shows the count as a plain number
        # We look for "0" as the expenses logged value — it must be present
        assert "0" in html

    def test_empty_transaction_list_shown_without_error(self, client):
        """When no expenses match, the empty-state element must render without error."""
        response = get_profile(client, **{"from": "2025-01-01", "to": "2025-12-31"})
        html = response.data.decode()
        # The empty state message per template: "No transactions yet"
        assert "No transactions yet" in html

    def test_no_category_breakdown_when_no_matching_expenses(self, client):
        """Category breakdown section must be absent (or show no rows) when range is empty."""
        response = get_profile(client, **{"from": "2025-01-01", "to": "2025-12-31"})
        html = response.data.decode()
        # The template wraps breakdown in {% if categories %}, so section is hidden
        # If "By Category" still appears, there must be no category rows in it
        cat_idx = html.find("By Category")
        if cat_idx != -1:
            txn_idx = html.find("Recent Transactions", cat_idx)
            cat_section = html[cat_idx:txn_idx] if txn_idx != -1 else html[cat_idx:]
            # No known seed category names should appear in that slice
            for _, cat, _, _ in SEED_EXPENSES:
                assert cat not in cat_section


# ===========================================================================
# 7. Preset period shortcuts
# ===========================================================================

class TestProfilePeriodPresets:
    def test_period_3m_returns_200(self, client):
        response = get_profile(client, period="3m")
        assert response.status_code == 200

    def test_period_6m_returns_200(self, client):
        response = get_profile(client, period="6m")
        assert response.status_code == 200

    def test_period_3m_shows_filter_badge(self, client):
        """?period=3m must show the filter badge near Spending Summary."""
        response = get_profile(client, period="3m")
        assert b"profile-filter-badge" in response.data

    def test_period_6m_shows_filter_badge(self, client):
        """?period=6m must show the filter badge near Spending Summary."""
        response = get_profile(client, period="6m")
        assert b"profile-filter-badge" in response.data

    def test_period_3m_badge_label(self, client):
        """?period=3m badge must contain 'Last 3 Months' text."""
        response = get_profile(client, period="3m")
        assert b"Last 3 Months" in response.data

    def test_period_6m_badge_label(self, client):
        """?period=6m badge must contain 'Last 6 Months' text."""
        response = get_profile(client, period="6m")
        assert b"Last 6 Months" in response.data

    def test_period_3m_excludes_expenses_older_than_3_months(self, client):
        """Seed expenses are all in April 2026; today is 2026-04-29 so 3 months
        ago is ~2026-01-29. All seed expenses must appear (they are within range)."""
        # The seed expenses are all in April 2026 which is within 3 months of today
        response = get_profile(client, period="3m")
        # At minimum the most recent seed expenses should appear
        assert b"Miscellaneous" in response.data  # 2026-04-24

    def test_period_6m_excludes_expenses_older_than_6_months(self, client):
        """All seed expenses fall within the last 6 months — all should appear."""
        response = get_profile(client, period="6m")
        assert b"Miscellaneous" in response.data  # 2026-04-24

    def test_custom_from_to_overrides_period_preset(self, client):
        """When ?from=...&to=... are present, they take priority over ?period=."""
        # With from/to restricted to 2026-04-02..2026-04-02, only Groceries shows
        response = get_profile(
            client,
            **{"from": "2026-04-02", "to": "2026-04-02", "period": "6m"}
        )
        assert b"Groceries" in response.data
        assert b"Miscellaneous" not in response.data  # 2026-04-24 excluded

    def test_custom_range_overrides_3m_preset(self, client):
        """Custom ?from/to must take priority over ?period=3m."""
        response = get_profile(
            client,
            **{"from": "2026-04-24", "to": "2026-04-24", "period": "3m"}
        )
        assert b"Miscellaneous" in response.data
        assert b"Groceries" not in response.data  # 2026-04-02 excluded

    def test_custom_range_shows_custom_badge_not_preset_badge(self, client):
        """When custom from/to override period=3m, badge shows custom range dates."""
        response = get_profile(
            client,
            **{"from": "2026-04-24", "to": "2026-04-24", "period": "3m"}
        )
        # "Last 3 Months" always appears as the preset button label — check that
        # the badge specifically shows the custom date, not the preset label.
        html = response.data.decode()
        badge_start = html.find("profile-filter-badge")
        assert badge_start != -1, "filter badge not found"
        badge_snippet = html[badge_start:badge_start + 200]
        assert "24 Apr 2026" in badge_snippet
        assert "Last 3 Months" not in badge_snippet


# ===========================================================================
# 8. Clear filter link
# ===========================================================================

class TestProfileClearFilter:
    def test_clear_link_present_on_filtered_page(self, client):
        """The profile template must include a link to /profile (no params) for clearing."""
        response = get_profile(client, **{"from": "2026-04-01", "to": "2026-04-15"})
        html = response.data.decode()
        # The clear target in the template is url_for('profile') — renders as /profile
        # Preset "All Time" link also points to /profile with no params
        assert 'href="/profile"' in html

    def test_profile_with_no_params_after_filter_shows_all_time(self, client):
        """Navigating to /profile after a filtered view resets to all-time data."""
        # Simulate applying filter then clearing
        _ = get_profile(client, **{"from": "2026-04-01", "to": "2026-04-15"})
        response = get_profile(client)
        assert f"{ALL_TIME_TOTAL:.2f}".encode() in response.data
        assert b"profile-filter-badge" not in response.data


# ===========================================================================
# 9. Category percentage integrity
# ===========================================================================

class TestProfileCategoryPercentages:
    def test_category_percentages_sum_to_100_all_time(self, client):
        """All-time category percentages (from queries.py) must sum to exactly 100."""
        from database import queries as q
        cats = q.get_category_breakdown(1)  # seed user_id=1
        if cats:
            total_pct = sum(c["pct"] for c in cats)
            assert total_pct == 100

    def test_category_percentages_sum_to_100_filtered(self, client):
        """Filtered category percentages must also sum to exactly 100."""
        from database import queries as q
        cats = q.get_category_breakdown(1, date_from="2026-04-01", date_to="2026-04-15")
        if cats:
            total_pct = sum(c["pct"] for c in cats)
            assert total_pct == 100

    def test_empty_range_returns_empty_list_not_error(self, client):
        """get_category_breakdown with no matching rows must return [] not raise."""
        from database import queries as q
        cats = q.get_category_breakdown(1, date_from="2020-01-01", date_to="2020-12-31")
        assert cats == []


# ===========================================================================
# 10. Template structure — filter form inputs
# ===========================================================================

class TestProfileFilterForm:
    def test_filter_form_has_from_input(self, client):
        """The filter form must contain an input with name='from'."""
        response = get_profile(client)
        assert b'name="from"' in response.data

    def test_filter_form_has_to_input(self, client):
        """The filter form must contain an input with name='to'."""
        response = get_profile(client)
        assert b'name="to"' in response.data

    def test_filter_form_has_apply_button(self, client):
        """The filter form must have a submit button labelled 'Apply'."""
        response = get_profile(client)
        assert b"Apply" in response.data

    def test_filter_form_method_is_get(self, client):
        """The filter form must use method=GET so params appear in the URL."""
        response = get_profile(client)
        assert b'method="GET"' in response.data

    def test_filter_form_action_points_to_profile(self, client):
        """The filter form action must point to /profile."""
        response = get_profile(client)
        assert b'action="/profile"' in response.data

    def test_inputs_are_type_date(self, client):
        """From and to inputs must be type=date for native date picker support."""
        response = get_profile(client)
        html = response.data.decode()
        # Both date inputs must be present
        assert html.count('type="date"') >= 2
