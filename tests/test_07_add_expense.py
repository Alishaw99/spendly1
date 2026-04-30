# tests/test_07_add_expense.py
#
# Spec behaviors covered (07-add-expense.md):
#
# GET /expenses/add
#   - Logged-in user gets 200 and a rendered form
#   - Form contains amount, category dropdown, date, and description fields
#   - Date field defaults to today's date (IST/local date — verified as YYYY-MM-DD)
#   - Category dropdown contains exactly the seven fixed categories
#   - Unauthenticated request redirects to /login
#
# POST /expenses/add
#   - Valid data inserts a row into expenses and redirects to /profile
#   - Newly inserted expense row is present in DB for the correct user
#   - Description is optional — blank description is stored as NULL/None
#   - Blank amount flashes an error and re-renders the form (no redirect, no DB insert)
#   - Zero amount flashes an error and re-renders the form
#   - Negative amount flashes an error and re-renders the form
#   - Non-numeric amount flashes an error and re-renders the form
#   - Category not in fixed list flashes an error and re-renders the form
#   - Invalid date format flashes an error and re-renders the form
#   - Missing date field flashes an error and re-renders the form
#   - Unauthenticated POST is blocked (redirects to /login or returns 403 per spec)
#
# Nav bar
#   - "Add Expense" link appears in the nav when a user is logged in
#   - "Add Expense" link does NOT appear in the nav when no user is logged in

import pytest
from datetime import date

from app import app
from database.db import init_db, create_user, get_db

FIXED_CATEGORIES = [
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
]


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #

@pytest.fixture
def client(tmp_path):
    """
    Provide a Flask test client backed by a fresh in-memory-style SQLite DB.
    We use a temp-file DB (not ':memory:') so that the same path is seen by
    every connection opened inside app routes, which create their own sqlite3
    connections via get_db().
    """
    db_file = str(tmp_path / "test_spendly.db")

    app.config["TESTING"] = True
    app.config["DATABASE"] = db_file

    # Patch DB_PATH used inside database.db so all helpers hit the temp file.
    import database.db as db_module
    original_path = db_module.DB_PATH
    db_module.DB_PATH = db_file

    with app.test_client() as test_client:
        with app.app_context():
            init_db()
        yield test_client

    # Restore original path after the test.
    db_module.DB_PATH = original_path


@pytest.fixture
def registered_user(client):
    """
    Create a test user and return their credentials.
    Uses create_user() directly so the DB state is deterministic.
    """
    import database.db as db_module
    user_id = create_user("Test User", "testuser@example.com", "password123")
    return {"id": user_id, "email": "testuser@example.com", "password": "password123"}


@pytest.fixture
def auth_client(client, registered_user):
    """
    Return the same test client but with session['user_id'] pre-set so that
    routes see an authenticated user without going through the login flow.
    """
    with client.session_transaction() as sess:
        sess["user_id"] = registered_user["id"]
        sess["user_name"] = "Test User"
    return client


def _get_db_connection():
    """Open a raw connection to whatever DB_PATH is currently set."""
    import database.db as db_module
    return db_module.get_db()


# --------------------------------------------------------------------------- #
# Helper                                                                       #
# --------------------------------------------------------------------------- #

def _expense_count_for_user(user_id):
    """Return the number of expense rows for the given user_id."""
    conn = _get_db_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()
    return count


def _latest_expense_for_user(user_id):
    """Return the most recently inserted expense row for the given user_id."""
    conn = _get_db_connection()
    row = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# --------------------------------------------------------------------------- #
# GET /expenses/add — authenticated                                            #
# --------------------------------------------------------------------------- #

class TestGetAddExpenseAuthenticated:

    def test_get_returns_200_for_logged_in_user(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert response.status_code == 200

    def test_get_renders_amount_field(self, auth_client):
        response = auth_client.get("/expenses/add")
        body = response.data.decode()
        # The form must contain an input field named "amount"
        assert 'name="amount"' in body

    def test_get_renders_category_dropdown(self, auth_client):
        response = auth_client.get("/expenses/add")
        body = response.data.decode()
        # A <select> named "category" must be present
        assert 'name="category"' in body
        assert "<select" in body

    def test_get_renders_date_field(self, auth_client):
        response = auth_client.get("/expenses/add")
        body = response.data.decode()
        assert 'name="date"' in body

    def test_get_renders_description_field(self, auth_client):
        response = auth_client.get("/expenses/add")
        body = response.data.decode()
        assert 'name="description"' in body

    def test_get_date_field_defaults_to_today(self, auth_client):
        today_iso = date.today().isoformat()  # YYYY-MM-DD
        response = auth_client.get("/expenses/add")
        body = response.data.decode()
        # The rendered form must pre-populate the date input with today's date
        assert today_iso in body

    def test_get_category_dropdown_contains_all_fixed_categories(self, auth_client):
        response = auth_client.get("/expenses/add")
        body = response.data.decode()
        for cat in FIXED_CATEGORIES:
            assert cat in body, f"Category '{cat}' not found in the form response"

    def test_get_category_dropdown_does_not_contain_unknown_category(self, auth_client):
        response = auth_client.get("/expenses/add")
        body = response.data.decode()
        # Sanity-check: an invented category must not appear
        assert "Gambling" not in body

    def test_get_renders_form_with_post_action(self, auth_client):
        response = auth_client.get("/expenses/add")
        body = response.data.decode()
        # The form must submit to /expenses/add via POST
        assert 'method="POST"' in body or 'method="post"' in body


# --------------------------------------------------------------------------- #
# GET /expenses/add — unauthenticated                                          #
# --------------------------------------------------------------------------- #

class TestGetAddExpenseUnauthenticated:

    def test_get_redirects_to_login_when_not_logged_in(self, client):
        response = client.get("/expenses/add")
        assert response.status_code in (301, 302)

    def test_get_redirect_points_to_login(self, client):
        response = client.get("/expenses/add", follow_redirects=False)
        location = response.headers.get("Location", "")
        assert "/login" in location

    def test_get_redirect_lands_on_login_page(self, client):
        response = client.get("/expenses/add", follow_redirects=True)
        body = response.data.decode()
        # After following the redirect the user should see the login page
        assert response.status_code == 200
        assert "login" in body.lower() or "sign in" in body.lower()


# --------------------------------------------------------------------------- #
# POST /expenses/add — happy path                                              #
# --------------------------------------------------------------------------- #

class TestPostAddExpenseHappyPath:

    def test_valid_post_redirects_to_profile(self, auth_client):
        response = auth_client.post(
            "/expenses/add",
            data={
                "amount": "250.00",
                "category": "Food",
                "date": "2026-04-15",
                "description": "Lunch at office",
            },
            follow_redirects=False,
        )
        assert response.status_code in (301, 302)
        location = response.headers.get("Location", "")
        assert "/profile" in location

    def test_valid_post_inserts_expense_into_db(self, auth_client, registered_user):
        before_count = _expense_count_for_user(registered_user["id"])
        auth_client.post(
            "/expenses/add",
            data={
                "amount": "500.00",
                "category": "Bills",
                "date": "2026-04-20",
                "description": "Internet bill",
            },
        )
        after_count = _expense_count_for_user(registered_user["id"])
        assert after_count == before_count + 1

    def test_valid_post_stores_correct_amount(self, auth_client, registered_user):
        auth_client.post(
            "/expenses/add",
            data={
                "amount": "750.50",
                "category": "Shopping",
                "date": "2026-04-10",
                "description": "Shoes",
            },
        )
        row = _latest_expense_for_user(registered_user["id"])
        assert row is not None
        assert abs(row["amount"] - 750.50) < 0.001

    def test_valid_post_stores_correct_category(self, auth_client, registered_user):
        auth_client.post(
            "/expenses/add",
            data={
                "amount": "100",
                "category": "Transport",
                "date": "2026-04-12",
                "description": "Bus pass",
            },
        )
        row = _latest_expense_for_user(registered_user["id"])
        assert row is not None
        assert row["category"] == "Transport"

    def test_valid_post_stores_correct_date(self, auth_client, registered_user):
        auth_client.post(
            "/expenses/add",
            data={
                "amount": "300",
                "category": "Health",
                "date": "2026-03-01",
                "description": "Doctor visit",
            },
        )
        row = _latest_expense_for_user(registered_user["id"])
        assert row is not None
        assert row["date"] == "2026-03-01"

    def test_valid_post_stores_correct_user_id(self, auth_client, registered_user):
        auth_client.post(
            "/expenses/add",
            data={
                "amount": "200",
                "category": "Entertainment",
                "date": "2026-04-18",
                "description": "Cinema",
            },
        )
        row = _latest_expense_for_user(registered_user["id"])
        assert row is not None
        assert row["user_id"] == registered_user["id"]

    def test_valid_post_flashes_success_message(self, auth_client):
        response = auth_client.post(
            "/expenses/add",
            data={
                "amount": "150",
                "category": "Other",
                "date": "2026-04-05",
                "description": "Stationery",
            },
            follow_redirects=True,
        )
        body = response.data.decode()
        # A success flash should be present on the redirected page
        assert "success" in body.lower() or "added" in body.lower()


# --------------------------------------------------------------------------- #
# POST /expenses/add — optional description                                   #
# --------------------------------------------------------------------------- #

class TestPostAddExpenseOptionalDescription:

    def test_blank_description_is_accepted_and_stored_as_null(self, auth_client, registered_user):
        """Spec says description is optional — blank input must succeed and store None."""
        before_count = _expense_count_for_user(registered_user["id"])
        response = auth_client.post(
            "/expenses/add",
            data={
                "amount": "99",
                "category": "Food",
                "date": "2026-04-22",
                "description": "",   # intentionally blank
            },
            follow_redirects=False,
        )
        # Must redirect (not re-render the form)
        assert response.status_code in (301, 302)
        after_count = _expense_count_for_user(registered_user["id"])
        assert after_count == before_count + 1

    def test_blank_description_stored_as_none_in_db(self, auth_client, registered_user):
        auth_client.post(
            "/expenses/add",
            data={
                "amount": "99",
                "category": "Food",
                "date": "2026-04-22",
                "description": "",
            },
        )
        row = _latest_expense_for_user(registered_user["id"])
        assert row is not None
        assert row["description"] is None

    def test_whitespace_only_description_stored_as_none(self, auth_client, registered_user):
        """Whitespace-only description should also be treated as empty/None."""
        auth_client.post(
            "/expenses/add",
            data={
                "amount": "55",
                "category": "Other",
                "date": "2026-04-23",
                "description": "   ",  # only whitespace
            },
        )
        row = _latest_expense_for_user(registered_user["id"])
        assert row is not None
        assert row["description"] is None


# --------------------------------------------------------------------------- #
# POST /expenses/add — amount validation                                       #
# --------------------------------------------------------------------------- #

class TestPostAddExpenseAmountValidation:

    def _post_bad_amount(self, auth_client, amount_value):
        return auth_client.post(
            "/expenses/add",
            data={
                "amount": amount_value,
                "category": "Food",
                "date": "2026-04-15",
                "description": "test",
            },
            follow_redirects=False,
        )

    def test_blank_amount_does_not_redirect(self, auth_client):
        response = self._post_bad_amount(auth_client, "")
        assert response.status_code == 200  # form is re-rendered, not a redirect

    def test_blank_amount_flashes_error(self, auth_client):
        response = self._post_bad_amount(auth_client, "")
        body = response.data.decode()
        assert "error" in body.lower() or "amount" in body.lower()

    def test_blank_amount_does_not_insert_row(self, auth_client, registered_user):
        before_count = _expense_count_for_user(registered_user["id"])
        self._post_bad_amount(auth_client, "")
        assert _expense_count_for_user(registered_user["id"]) == before_count

    def test_zero_amount_does_not_redirect(self, auth_client):
        response = self._post_bad_amount(auth_client, "0")
        assert response.status_code == 200

    def test_zero_amount_flashes_error(self, auth_client):
        response = self._post_bad_amount(auth_client, "0")
        body = response.data.decode()
        assert "error" in body.lower() or "amount" in body.lower()

    def test_zero_amount_does_not_insert_row(self, auth_client, registered_user):
        before_count = _expense_count_for_user(registered_user["id"])
        self._post_bad_amount(auth_client, "0")
        assert _expense_count_for_user(registered_user["id"]) == before_count

    def test_zero_float_amount_does_not_redirect(self, auth_client):
        response = self._post_bad_amount(auth_client, "0.00")
        assert response.status_code == 200

    def test_negative_amount_does_not_redirect(self, auth_client):
        response = self._post_bad_amount(auth_client, "-50")
        assert response.status_code == 200

    def test_negative_amount_flashes_error(self, auth_client):
        response = self._post_bad_amount(auth_client, "-50")
        body = response.data.decode()
        assert "error" in body.lower() or "amount" in body.lower()

    def test_negative_amount_does_not_insert_row(self, auth_client, registered_user):
        before_count = _expense_count_for_user(registered_user["id"])
        self._post_bad_amount(auth_client, "-100")
        assert _expense_count_for_user(registered_user["id"]) == before_count

    def test_non_numeric_amount_does_not_redirect(self, auth_client):
        response = self._post_bad_amount(auth_client, "abc")
        assert response.status_code == 200

    def test_non_numeric_amount_flashes_error(self, auth_client):
        response = self._post_bad_amount(auth_client, "abc")
        body = response.data.decode()
        assert "error" in body.lower() or "amount" in body.lower()

    def test_non_numeric_amount_does_not_insert_row(self, auth_client, registered_user):
        before_count = _expense_count_for_user(registered_user["id"])
        self._post_bad_amount(auth_client, "not-a-number")
        assert _expense_count_for_user(registered_user["id"]) == before_count

    def test_amount_with_currency_symbol_is_rejected(self, auth_client):
        """'₹250' is not a pure numeric string and must be rejected."""
        response = self._post_bad_amount(auth_client, "₹250")
        assert response.status_code == 200

    @pytest.mark.parametrize("bad_amount", ["", "0", "0.00", "-1", "-0.01", "abc", "1e", "--5", "1,200"])
    def test_invalid_amounts_are_all_rejected(self, auth_client, bad_amount):
        response = self._post_bad_amount(auth_client, bad_amount)
        assert response.status_code == 200, (
            f"Expected form re-render (200) for amount='{bad_amount}', got {response.status_code}"
        )


# --------------------------------------------------------------------------- #
# POST /expenses/add — category validation                                     #
# --------------------------------------------------------------------------- #

class TestPostAddExpenseCategoryValidation:

    def _post_bad_category(self, auth_client, category_value):
        return auth_client.post(
            "/expenses/add",
            data={
                "amount": "100",
                "category": category_value,
                "date": "2026-04-15",
                "description": "test",
            },
            follow_redirects=False,
        )

    def test_invalid_category_does_not_redirect(self, auth_client):
        response = self._post_bad_category(auth_client, "Gambling")
        assert response.status_code == 200

    def test_invalid_category_flashes_error(self, auth_client):
        response = self._post_bad_category(auth_client, "Gambling")
        body = response.data.decode()
        assert "error" in body.lower() or "category" in body.lower()

    def test_invalid_category_does_not_insert_row(self, auth_client, registered_user):
        before_count = _expense_count_for_user(registered_user["id"])
        self._post_bad_category(auth_client, "Luxury")
        assert _expense_count_for_user(registered_user["id"]) == before_count

    def test_blank_category_is_rejected(self, auth_client):
        response = self._post_bad_category(auth_client, "")
        assert response.status_code == 200

    def test_case_sensitive_category_is_rejected(self, auth_client):
        """'food' (lowercase) is not in the fixed list; only 'Food' is valid."""
        response = self._post_bad_category(auth_client, "food")
        assert response.status_code == 200

    def test_category_with_extra_spaces_is_rejected(self, auth_client):
        """' Food ' with surrounding whitespace is not in the fixed list."""
        response = self._post_bad_category(auth_client, " Food ")
        assert response.status_code == 200

    @pytest.mark.parametrize("valid_cat", FIXED_CATEGORIES)
    def test_each_fixed_category_is_accepted(self, auth_client, registered_user, valid_cat):
        before_count = _expense_count_for_user(registered_user["id"])
        response = auth_client.post(
            "/expenses/add",
            data={
                "amount": "10",
                "category": valid_cat,
                "date": "2026-01-01",
                "description": "",
            },
            follow_redirects=False,
        )
        assert response.status_code in (301, 302), (
            f"Expected redirect for valid category '{valid_cat}', got {response.status_code}"
        )
        assert _expense_count_for_user(registered_user["id"]) == before_count + 1


# --------------------------------------------------------------------------- #
# POST /expenses/add — date validation                                         #
# --------------------------------------------------------------------------- #

class TestPostAddExpenseDateValidation:

    def _post_bad_date(self, auth_client, date_value):
        return auth_client.post(
            "/expenses/add",
            data={
                "amount": "100",
                "category": "Food",
                "date": date_value,
                "description": "test",
            },
            follow_redirects=False,
        )

    def test_missing_date_does_not_redirect(self, auth_client):
        response = self._post_bad_date(auth_client, "")
        assert response.status_code == 200

    def test_missing_date_flashes_error(self, auth_client):
        response = self._post_bad_date(auth_client, "")
        body = response.data.decode()
        assert "error" in body.lower() or "date" in body.lower()

    def test_missing_date_does_not_insert_row(self, auth_client, registered_user):
        before_count = _expense_count_for_user(registered_user["id"])
        self._post_bad_date(auth_client, "")
        assert _expense_count_for_user(registered_user["id"]) == before_count

    def test_dd_mm_yyyy_format_is_rejected(self, auth_client):
        """Date must be YYYY-MM-DD per spec; DD/MM/YYYY is invalid."""
        response = self._post_bad_date(auth_client, "15/04/2026")
        assert response.status_code == 200

    def test_mm_dd_yyyy_format_is_rejected(self, auth_client):
        response = self._post_bad_date(auth_client, "04-15-2026")
        assert response.status_code == 200

    def test_plain_text_date_is_rejected(self, auth_client):
        response = self._post_bad_date(auth_client, "yesterday")
        assert response.status_code == 200

    def test_partial_date_is_rejected(self, auth_client):
        response = self._post_bad_date(auth_client, "2026-04")
        assert response.status_code == 200

    def test_invalid_month_is_rejected(self, auth_client):
        """Month 13 does not exist."""
        response = self._post_bad_date(auth_client, "2026-13-01")
        assert response.status_code == 200

    def test_invalid_day_is_rejected(self, auth_client):
        """Day 32 does not exist."""
        response = self._post_bad_date(auth_client, "2026-04-32")
        assert response.status_code == 200

    def test_valid_yyyy_mm_dd_is_accepted(self, auth_client, registered_user):
        before_count = _expense_count_for_user(registered_user["id"])
        response = self._post_bad_date(auth_client, "2026-01-31")
        assert response.status_code in (301, 302)
        assert _expense_count_for_user(registered_user["id"]) == before_count + 1

    @pytest.mark.parametrize("bad_date", [
        "", "15/04/2026", "04-15-2026", "yesterday", "2026-04", "2026-13-01", "2026-04-32",
    ])
    def test_invalid_date_formats_are_all_rejected(self, auth_client, bad_date):
        response = self._post_bad_date(auth_client, bad_date)
        assert response.status_code == 200, (
            f"Expected form re-render (200) for date='{bad_date}', got {response.status_code}"
        )


# --------------------------------------------------------------------------- #
# POST /expenses/add — unauthenticated                                         #
# --------------------------------------------------------------------------- #

class TestPostAddExpenseUnauthenticated:

    def test_post_without_session_is_blocked(self, client):
        """Unauthenticated POST must not insert a row and must be rejected."""
        response = client.post(
            "/expenses/add",
            data={
                "amount": "100",
                "category": "Food",
                "date": "2026-04-15",
                "description": "test",
            },
            follow_redirects=False,
        )
        # Spec says redirect to /login; abort(403) is also mentioned as a fallback.
        assert response.status_code in (301, 302, 403)

    def test_post_without_session_redirects_to_login_or_returns_403(self, client):
        response = client.post(
            "/expenses/add",
            data={
                "amount": "100",
                "category": "Food",
                "date": "2026-04-15",
                "description": "test",
            },
            follow_redirects=False,
        )
        if response.status_code in (301, 302):
            location = response.headers.get("Location", "")
            assert "/login" in location, (
                f"Redirect should point to /login, got: {location}"
            )
        else:
            assert response.status_code == 403


# --------------------------------------------------------------------------- #
# Form re-render preserves entered values on validation failure                #
# --------------------------------------------------------------------------- #

class TestFormValuePreservationOnError:

    def test_amount_value_preserved_after_invalid_category(self, auth_client):
        """When category is invalid, the amount the user entered should be echoed back."""
        response = auth_client.post(
            "/expenses/add",
            data={
                "amount": "999",
                "category": "InvalidCat",
                "date": "2026-04-15",
                "description": "Some note",
            },
        )
        body = response.data.decode()
        assert "999" in body

    def test_description_preserved_after_invalid_date(self, auth_client):
        """When date is invalid, the description the user entered should be echoed back."""
        response = auth_client.post(
            "/expenses/add",
            data={
                "amount": "50",
                "category": "Food",
                "date": "bad-date",
                "description": "My unique description text",
            },
        )
        body = response.data.decode()
        assert "My unique description text" in body


# --------------------------------------------------------------------------- #
# Nav bar — "Add Expense" link                                                 #
# --------------------------------------------------------------------------- #

class TestNavBarAddExpenseLink:

    def test_add_expense_link_present_when_logged_in(self, auth_client):
        """Logged-in users must see an 'Add Expense' link in the nav bar."""
        response = auth_client.get("/profile", follow_redirects=True)
        body = response.data.decode()
        assert "Add Expense" in body

    def test_add_expense_link_absent_when_logged_out(self, client):
        """Anonymous visitors must NOT see an 'Add Expense' nav link."""
        response = client.get("/", follow_redirects=True)
        body = response.data.decode()
        assert "Add Expense" not in body

    def test_add_expense_nav_link_points_to_correct_path(self, auth_client):
        """The 'Add Expense' nav link must href to /expenses/add."""
        response = auth_client.get("/profile", follow_redirects=True)
        body = response.data.decode()
        assert "/expenses/add" in body

    def test_add_expense_link_appears_on_add_expense_page_itself(self, auth_client):
        """Even on the add-expense page the nav link must still be rendered."""
        response = auth_client.get("/expenses/add")
        body = response.data.decode()
        assert "Add Expense" in body
