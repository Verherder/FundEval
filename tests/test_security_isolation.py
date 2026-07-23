import hashlib
import re
from src.database import Database
from src.services import import_service


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

