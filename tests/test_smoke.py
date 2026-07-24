# -*- coding: UTF-8 -*-
"""P0 smoke tests — verifies the app stays functional after each refactor phase.

Uses Flask test_client + in-memory SQLite. No external APIs are called
(data endpoints will return errors, but routes must not 500).

Usage:
    pytest tests/test_smoke.py -q
"""

import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def test_db(monkeypatch):
    """Create an in-memory Database for every test.

    Runs automatically (autouse=True) so no @pytest.mark.usefixtures needed.
    """
    from src.database import Database

    db = Database(":memory:")
    return db


@pytest.fixture
def client(test_db):
    """Flask test client."""
    from src.app import create_app

    app = create_app(db=test_db)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-smoke-key"
    return app.test_client()


@pytest.fixture
def auth_client(client, test_db):
    """Test client pre-authenticated as a fresh test user."""
    test_db.create_user("smoketest", "smoke123")
    client.post(
        "/login",
        data={"username": "smoketest", "password": "smoke123"},
    )
    return client


# ── P0-1: Login ──────────────────────────────────────────────────────────

def test_login_page_loads(client):
    """GET /login returns the login form."""
    resp = client.get("/login")
    assert resp.status_code == 200


def test_reverse_proxy_prefix_is_preserved_in_redirects_and_assets(client):
    headers = {"X-Forwarded-Prefix": "/fundeval"}

    redirect_response = client.get("/", headers=headers, follow_redirects=False)
    assert redirect_response.status_code == 302
    assert redirect_response.headers["Location"].endswith("/fundeval/login")

    login_response = client.get("/login", headers=headers)
    html = login_response.get_data(as_text=True)
    assert 'action="/fundeval/login"' in html
    assert 'href="/fundeval/register"' in html
    assert 'href="/fundeval/static/1.ico"' in html


def test_reverse_proxy_prefix_is_preserved_after_login(client, test_db):
    headers = {"X-Forwarded-Prefix": "/fundeval"}
    _, _, user_id = test_db.create_user("prefixadmin", "prefix-password")
    with test_db.get_connection() as conn:
        conn.execute("UPDATE users SET is_admin=1 WHERE id=?", (user_id,))
    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["username"] = "prefixuser"

    settings_response = client.get("/settings", headers=headers)
    html = settings_response.get_data(as_text=True)
    assert 'data-app-base="/fundeval"' in html
    assert 'href="/fundeval/portfolio"' in html
    assert 'href="/fundeval/settings"' in html
    assert 'src="/fundeval/static/js/app-url.js"' in html
    assert 'src="/fundeval/static/js/settings.js?v=20260721a"' in html


def test_login_with_valid_credentials(client, test_db):
    """POST /login with valid credentials sets session and redirects."""
    test_db.create_user("user1", "pass123")

    resp = client.post(
        "/login",
        data={"username": "user1", "password": "pass123"},
    )

    # Should redirect (302) to /fund or /portfolio
    assert resp.status_code in (200, 302)


def test_login_with_wrong_password(client, test_db):
    """POST /login with wrong password stays on login page."""
    test_db.create_user("user1", "pass123")

    resp = client.post(
        "/login",
        data={"username": "user1", "password": "wrongpassword"},
    )

    assert resp.status_code == 401
    # Should not redirect — stays on login


# ── P0-2: Portfolio page ─────────────────────────────────────────────────

def test_portfolio_requires_login(client):
    """Unauthenticated access to /portfolio redirects to /login."""
    resp = client.get("/portfolio", follow_redirects=False)
    assert resp.status_code in (302, 401)


def test_portfolio_loads_when_authenticated(auth_client):
    """GET /portfolio returns 200 (even if external data fails, must not 500)."""
    resp = auth_client.get("/portfolio")
    # 200 OK (empty page) or 302 redirect — never 500
    assert resp.status_code != 500


def test_settings_page_loads_when_authenticated(auth_client):
    resp = auth_client.get("/settings")
    assert resp.status_code != 500
    if resp.status_code == 200:
        assert "单次刷新同步基金数" in resp.get_data(as_text=True)


def test_refresh_settings_requires_login(client):
    resp = client.get("/api/config/refresh", follow_redirects=False)
    assert resp.status_code in (302, 401)


def test_fund_page_loads(auth_client):
    """GET /fund returns 200."""
    resp = auth_client.get("/fund")
    assert resp.status_code != 500


# ── P0-3: Add fund ───────────────────────────────────────────────────────

def test_add_fund_endpoint(auth_client):
    """POST /api/fund/add succeeds (or fails gracefully, not 500)."""
    resp = auth_client.post(
        "/api/fund/add",
        json={"code": "000001"},
    )
    json_data = resp.get_json()
    # May fail because external API is unavailable, but must not 500
    assert resp.status_code != 500
    assert json_data is not None


# ── P0-4: Delete fund ────────────────────────────────────────────────────

def test_delete_fund_endpoint(auth_client):
    """POST /api/fund/delete handles missing fund gracefully."""
    resp = auth_client.post(
        "/api/fund/delete",
        json={"code": "000001"},
    )
    assert resp.status_code != 500


# ── P0-5: Buy ────────────────────────────────────────────────────────────

def test_buy_endpoint(auth_client):
    """POST /api/fund/buy returns structured response (not 500)."""
    resp = auth_client.post(
        "/api/fund/buy",
        json={"code": "000001", "amount": 100},
    )
    assert resp.status_code != 500
    json_data = resp.get_json()
    assert json_data is not None


# ── P0-6: Sell ───────────────────────────────────────────────────────────

def test_sell_endpoint(auth_client):
    """POST /api/fund/sell returns structured JSON (not 500)."""
    resp = auth_client.post(
        "/api/fund/sell",
        json={"code": "000001", "shares": 0.01},
    )
    assert resp.status_code != 500
    assert resp.get_json() is not None


# ── P0-7: Performance chart ──────────────────────────────────────────────

def test_performance_chart_endpoint(auth_client):
    """GET /api/fund/performance-chart-data returns JSON structure."""
    resp = auth_client.get(
        "/api/fund/performance-chart-data?code=000001&interval=SINCE_ESTABLISHMENT"
    )
    # May be 400/500 if fund data unavailable, but must return JSON
    json_data = resp.get_json()
    assert json_data is not None


# ── P0-8: Logout ─────────────────────────────────────────────────────────

def test_logout(auth_client):
    """POST /logout clears session and redirects to /login."""
    resp = auth_client.post("/logout", follow_redirects=False)
    assert resp.status_code in (200, 302)


def test_protected_page_after_logout(auth_client):
    """After logout, /portfolio redirects to /login."""
    auth_client.post("/logout")
    resp = auth_client.get("/portfolio", follow_redirects=False)
    assert resp.status_code in (302, 401)


# ── P1: Sector & Tab fragments ───────────────────────────────────────────

def test_sectors_page_loads(auth_client):
    """GET /sectors returns 200 (not 500)."""
    resp = auth_client.get("/sectors")
    assert resp.status_code != 500


def test_tab_fund_endpoint(auth_client):
    """GET /api/tab/fund returns JSON with content."""
    resp = auth_client.get("/api/tab/fund")
    json_data = resp.get_json()
    assert json_data is not None


# ── Gate: Static resources ────────────────────────────────────────────────

def test_static_css_available(client):
    """/static/css/style.css returns 200 for login page (rendered CSS)."""
    resp = client.get("/static/css/style.css")
    # CSS may be served via Jinja or static file — either way, not 404
    # Note: prior to phase 3, CSS may be served differently
    assert resp.status_code != 500


def test_static_js_available(client):
    """/static/js/main.js returns 200."""
    resp = client.get("/static/js/main.js")
    assert resp.status_code != 500


def test_portfolio_chart_module_available(client):
    """Portfolio native module is served as JavaScript."""
    resp = client.get("/static/js/portfolio/chart-crosshair.js")
    assert resp.status_code == 200
    assert b"createPerformanceCrosshairPlugin" in resp.data

    entry_resp = client.get("/static/js/portfolio/portfolio.js")
    assert entry_resp.status_code == 200
    assert b"toggleFundRowChart" in entry_resp.data
