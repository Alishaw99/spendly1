import pytest
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)

SEED_USER_ID = 1
NONEXISTENT_ID = 999999


# --- get_user_by_id ---

def test_get_user_by_id_valid():
    user = get_user_by_id(SEED_USER_ID)
    assert user is not None
    assert user["name"] == "Demo User"
    assert user["email"] == "demo@spendly.com"
    parts = user["member_since"].split()
    assert len(parts) == 2
    assert parts[1].isdigit()


def test_get_user_by_id_nonexistent():
    assert get_user_by_id(NONEXISTENT_ID) is None


# --- get_summary_stats ---

def test_get_summary_stats_with_expenses():
    stats = get_summary_stats(SEED_USER_ID)
    assert stats["total_spent"] == pytest.approx(6050.0)
    assert stats["transaction_count"] == 8
    assert stats["top_category"] == "Shopping"


def test_get_summary_stats_no_expenses():
    stats = get_summary_stats(NONEXISTENT_ID)
    assert stats["total_spent"] == 0
    assert stats["transaction_count"] == 0
    assert stats["top_category"] == "—"


# --- get_recent_transactions ---

def test_get_recent_transactions_with_expenses():
    txns = get_recent_transactions(SEED_USER_ID)
    assert len(txns) == 8
    for t in txns:
        assert "date" in t
        assert "description" in t
        assert "category" in t
        assert "amount" in t
    assert txns[0]["date"] == "2026-04-24"


def test_get_recent_transactions_no_expenses():
    assert get_recent_transactions(NONEXISTENT_ID) == []


# --- get_category_breakdown ---

def test_get_category_breakdown_with_expenses():
    cats = get_category_breakdown(SEED_USER_ID)
    assert len(cats) == 7
    assert cats[0]["name"] == "Shopping"
    assert cats[0]["amount"] == pytest.approx(2200.0)
    pcts = [c["pct"] for c in cats]
    assert all(isinstance(p, int) for p in pcts)
    assert sum(pcts) == 100


def test_get_category_breakdown_no_expenses():
    assert get_category_breakdown(NONEXISTENT_ID) == []


# --- Route tests ---

def test_profile_unauthenticated(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_authenticated(client):
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    resp = client.get("/profile")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "Demo User" in body
    assert "demo@spendly.com" in body
    assert "&#8377;" in body
    assert "6050" in body
    assert "Shopping" in body
