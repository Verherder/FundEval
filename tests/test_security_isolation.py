import hashlib
import re
from src.database import Database
from src.services import import_service
from src.tab_enhancers import enhance_fund_tab_content


def test_shared_catalog_and_private_watchlist():
    db = Database(":memory:")
    _, _, user_a = db.create_user("alice", "a-password")
    _, _, user_b = db.create_user("bob", "b-password")
    db.add_fund(user_a, "999999", "key", "共享基金")
    db.add_fund(user_b, "999999", "key", "共享基金")

    funds_a = db.get_user_funds(user_a)
    funds_a["999999"]["shares"] = 123.45
    funds_a["999999"]["sectors"] = ["医疗"]
    assert db.save_user_funds(user_a, funds_a)

    assert db.get_user_funds(user_a)["999999"]["shares"] == 123.45
    assert db.get_user_funds(user_b)["999999"]["shares"] == 0
    assert db.get_user_funds(user_b)["999999"]["sectors"] == ["医疗"]


def test_all_users_can_browse_catalog_and_select_without_deleting_shared_fund():
    db = Database(":memory:")
    _, _, admin = db.create_user("jiaming", "administrator-password")
    _, _, user = db.create_user("alice", "alice-password")
    db.add_fund(admin, "999999", "key", "共享基金")

    catalog_item = next(
        item for item in db.get_fund_catalog(user)
        if item["fund_code"] == "999999"
    )
    assert catalog_item["is_selected"] is False

    assert db.add_catalog_funds_to_watchlist(user, ["999999"]) == 1
    assert next(
        item for item in db.get_fund_catalog(user)
        if item["fund_code"] == "999999"
    )["is_selected"] is True
    assert db.delete_fund(user, "999999") is True
    assert next(
        item for item in db.get_fund_catalog(user)
        if item["fund_code"] == "999999"
    )["is_selected"] is False
    assert db.get_user_funds(admin)["999999"]["fund_name"] == "共享基金"


def test_new_user_sees_shared_catalog_with_empty_private_state():
    db = Database(":memory:")
    _, _, admin = db.create_user("jiaming", "administrator-password")
    _, _, user = db.create_user("test", "test-password-123")
    db.add_fund(admin, "999998", "key-a", "公共基金A")
    db.add_fund(admin, "999999", "key-b", "公共基金B")

    assert db.get_user_funds(user) == {}
    visible = db.get_visible_funds(user)
    assert {"999998", "999999"}.issubset(visible)
    assert visible["999998"]["is_hold"] is False
    assert visible["999998"]["shares"] == 0
    assert visible["999998"]["is_selected"] is False

    assert db.save_visible_funds(user, visible)
    assert db.get_user_funds(user) == {}
    assert db.update_fund_shares(user, "999998", 12.34)
    assert len(db.get_user_funds(user)) == 1
    assert db.get_user_funds(user)["999998"]["shares"] == 12.34


def test_order_number_and_pending_buy_are_user_scoped():
    db = Database(":memory:")
    _, _, user_a = db.create_user("alice", "a-password")
    _, _, user_b = db.create_user("bob", "b-password")
    assert db.add_fund_transaction(user_a, "000594", "buy", 10, 10, order_no="same")
    assert db.add_fund_transaction(user_b, "000594", "buy", 10, 10, order_no="same")
    assert db.add_fund_transaction(user_a, "000594", "buy", 10, 10, order_no="same") is None
    pending = db.add_pending_buy(user_a, "000594", 100, "2026-07-23")
    assert not db.mark_pending_buy_settled(user_b, pending, 1, 1.0, 100)
    assert db.mark_pending_buy_settled(user_a, pending, 1, 1.0, 100)


def test_import_progress_is_owned_by_user():
    service = import_service.ImportService(None, None, None, None, None)
    import_service._set_import_job_state("secret-job", user_id=11, done=False)
    assert service.get_import_progress(12, "secret-job")["success"] is False
    assert service.get_import_progress(11, "secret-job")["success"] is True


def test_csrf_and_admin_authorization():
    from src.app import create_app

    db = Database(":memory:")
    _, _, user_id = db.create_user("ordinary", "ordinary-password")
    app = create_app(db=db)
    app.config["TESTING"] = False
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["username"] = "ordinary"
        session["csrf_token"] = "csrf-value"
    assert client.post("/api/fund/delete", json={"code": "000594"}).status_code == 400
    response = client.post(
        "/api/fund/sector",
        json={"codes": "000594", "sectors": ["医疗"]},
        headers={"X-CSRF-Token": "csrf-value"},
    )
    assert response.status_code == 403


def test_signed_csrf_login_logout_and_repeated_logout():
    from src.app import create_app

    db = Database(":memory:")
    _, _, admin = db.create_user("csrfadmin", "ValidPassword12!")
    with db.get_connection() as conn:
        conn.execute("UPDATE users SET is_admin=1 WHERE id=?", (admin,))

    app = create_app(db=db)
    app.config["TESTING"] = False
    client = app.test_client()

    login_html = client.get("/login").get_data(as_text=True)
    login_token = re.search(
        r'name="csrf_token" value="([^"]+)"',
        login_html,
    ).group(1)
    response = client.post(
        "/login",
        data={
            "username": "csrfadmin",
            "password": "ValidPassword12!",
            "csrf_token": login_token,
        },
    )
    assert response.status_code == 302

    settings_html = client.get("/settings").get_data(as_text=True)
    logout_token = re.search(
        r'name="csrf_token" value="([^"]+)"',
        settings_html,
    ).group(1)
    assert client.post("/logout", data={"csrf_token": logout_token}).status_code == 302
    assert client.post("/logout", data={"csrf_token": logout_token}).status_code == 302


def test_signed_csrf_token_survives_app_recreation():
    from flask import session
    from src.app import create_app
    from src.auth import get_csrf_token, validate_csrf_token

    db = Database(":memory:")
    app_one = create_app(db=db)
    app_two = create_app(db=db)

    with app_one.test_request_context("/"):
        session["user_id"] = 42
        token = get_csrf_token()
    with app_two.test_request_context("/"):
        session["user_id"] = 42
        assert validate_csrf_token(token)
        session["user_id"] = 43
        assert not validate_csrf_token(token)


def test_development_secret_key_persists_across_restarts(tmp_path, monkeypatch):
    from src.app import _load_secret_key

    monkeypatch.delenv("FUNDEVAL_SECRET_KEY", raising=False)
    monkeypatch.delenv("FUNDEVAL_ENV", raising=False)
    monkeypatch.setenv("FUNDEVAL_RUNTIME_DIR", str(tmp_path))

    first = _load_secret_key(None)
    second = _load_secret_key(None)

    assert first == second
    assert len(first) >= 48
    assert (tmp_path / "session-secret").stat().st_mode & 0o777 == 0o600


def test_invite_is_single_use():
    from src.app import create_app

    db = Database(":memory:")
    _, _, admin = db.create_user("jiaming", "administrator-password")
    with db.get_connection() as conn:
        conn.execute("UPDATE users SET is_admin=1 WHERE id=?", (admin,))
    token = "one-time-invite"
    db.create_invitation(hashlib.sha256(token.encode()).hexdigest(), admin, "2099-01-01T00:00:00+00:00")
    app = create_app(db=db)
    app.config["TESTING"] = True
    client = app.test_client()
    data = {"username": "newuser", "password": "long-password-123", "confirm_password": "long-password-123", "invite_code": token}
    assert client.post("/register", data=data).status_code == 302
    data["username"] = "newuser2"
    assert client.post("/register", data=data).status_code == 400


def test_admin_ui_and_sensitive_endpoints_are_protected():
    from src.app import create_app

    db = Database(":memory:")
    _, _, admin = db.create_user("jiaming", "administrator-password")
    _, _, ordinary = db.create_user("ordinary", "ordinary-password")
    with db.get_connection() as conn:
        conn.execute("UPDATE users SET is_admin=1 WHERE id=?", (admin,))

    app = create_app(db=db)
    app.config["TESTING"] = True
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = ordinary
        session["username"] = "ordinary"

    portfolio_html = client.get("/portfolio").get_data(as_text=True)
    assert 'href="/settings"' not in portfolio_html
    assert "回填成立日期" not in portfolio_html
    assert "清空交易记录" not in portfolio_html
    assert client.get("/settings").status_code == 403
    assert client.put("/api/config/refresh", json={}).status_code == 403
    assert client.post("/api/admin/invitations", json={"days": 7}).status_code == 403
    assert client.post("/api/fund/backfill-establishment-dates").status_code == 403
    assert client.post("/api/fund/transactions/clear-all", json={}).status_code == 403
    assert client.post("/api/fund/upload").status_code == 403


def test_admin_can_generate_invitation_without_storing_plaintext():
    from src.app import create_app

    db = Database(":memory:")
    _, _, admin = db.create_user("jiaming", "administrator-password")
    with db.get_connection() as conn:
        conn.execute("UPDATE users SET is_admin=1 WHERE id=?", (admin,))

    app = create_app(db=db)
    app.config["TESTING"] = True
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = admin
        session["username"] = "jiaming"

    settings_html = client.get("/settings").get_data(as_text=True)
    assert "注册邀请码" in settings_html
    response = client.post("/api/admin/invitations", json={"days": 7})
    assert response.status_code == 200
    invite_code = response.get_json()["invite_code"]
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT token_hash,created_by FROM invitations ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert row["created_by"] == admin
    assert row["token_hash"] == hashlib.sha256(invite_code.encode()).hexdigest()
    assert row["token_hash"] != invite_code


def test_registration_validates_username_and_password_patterns():
    from src.app import create_app

    db = Database(":memory:")
    _, _, admin = db.create_user("jiaming", "administrator-password")
    with db.get_connection() as conn:
        conn.execute("UPDATE users SET is_admin=1 WHERE id=?", (admin,))
    token = "validation-invite"
    db.create_invitation(
        hashlib.sha256(token.encode()).hexdigest(),
        admin,
        "2099-01-01T00:00:00+00:00",
    )
    app = create_app(db=db)
    app.config["TESTING"] = True
    client = app.test_client()

    base = {
        "invite_code": token,
        "confirm_password": "ValidPassword12!",
    }
    response = client.post(
        "/register",
        data={**base, "username": "bad'user", "password": "ValidPassword12!"},
    )
    assert response.status_code == 400
    response = client.post(
        "/register",
        data={
            **base,
            "username": "valid_user",
            "password": "123456789012345678901",
            "confirm_password": "123456789012345678901",
        },
    )
    assert response.status_code == 400
    response = client.post(
        "/register",
        data={
            **base,
            "username": "valid_user",
            "password": "bad'password12",
            "confirm_password": "bad'password12",
        },
    )
    assert response.status_code == 400


def test_admin_user_management_and_self_protection():
    from src.app import create_app

    db = Database(":memory:")
    _, _, admin = db.create_user("jiaming", "administrator-password")
    _, _, user = db.create_user("managed_user", "managed-password")
    with db.get_connection() as conn:
        conn.execute("UPDATE users SET is_admin=1 WHERE id=?", (admin,))

    app = create_app(db=db)
    app.config["TESTING"] = True
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = admin
        session["username"] = "jiaming"

    listing = client.get("/api/admin/users").get_json()
    assert listing["current_user_id"] == admin
    assert {item["username"] for item in listing["users"]} == {"jiaming", "managed_user"}
    assert client.patch(
        f"/api/admin/users/{admin}",
        json={"action": "set_locked", "is_locked": True},
    ).status_code == 400
    assert client.patch(
        f"/api/admin/users/{user}",
        json={"action": "set_admin", "is_admin": True},
    ).status_code == 200
    assert db.is_admin(user)
    assert client.patch(
        f"/api/admin/users/{user}",
        json={"action": "set_locked", "is_locked": True},
    ).status_code == 200
    assert db.get_user_by_username("managed_user")["password_reset_required"] == 1
    assert client.patch(
        f"/api/admin/users/{user}",
        json={"action": "reset_password", "password": "NewPassword12!"},
    ).status_code == 200
    assert db.verify_password("managed_user", "NewPassword12!")[0] is True


def test_sensitive_toolbar_controls_only_render_for_admin():
    ordinary_html = enhance_fund_tab_content("<table></table>", {}, is_admin=False)
    admin_html = enhance_fund_tab_content("<table></table>", {}, is_admin=True)

    assert 'id="fundCodesInput"' in ordinary_html
    assert 'onclick="addFunds()"' in ordinary_html
    assert "取消自选" in ordinary_html
    assert "回填成立日期" not in ordinary_html
    assert "清空交易记录" not in ordinary_html
    assert "导入基金列表" not in ordinary_html
    assert "回填成立日期" in admin_html
    assert "清空交易记录" in admin_html
    assert "导入基金列表" in admin_html
