from src.database import Database


def test_identical_fund_nav_upsert_does_not_touch_timestamp(tmp_path):
    db = Database(str(tmp_path / "fund.db"))
    assert db.upsert_fund_nav_history("000001", "2026-07-17", 1.2345, "test") is True

    conn = db.get_connection()
    conn.execute(
        "UPDATE fund_nav_history SET updated_at = ? WHERE fund_code = ? AND nav_date = ?",
        ("2020-01-01 00:00:00", "000001", "2026-07-17"),
    )
    conn.commit()
    conn.close()

    assert db.upsert_fund_nav_history("000001", "2026-07-17", 1.2345, "test") is False
    conn = db.get_connection()
    row = conn.execute(
        "SELECT updated_at FROM fund_nav_history WHERE fund_code = ? AND nav_date = ?",
        ("000001", "2026-07-17"),
    ).fetchone()
    conn.close()
    assert row["updated_at"] == "2020-01-01 00:00:00"


def test_identical_index_nav_bulk_upsert_does_not_touch_timestamp(tmp_path):
    db = Database(str(tmp_path / "fund.db"))
    records = [{"nav_date": "2026-07-17", "close": 4012.34, "change_pct": 0.25}]
    assert db.bulk_upsert_index_nav_history("000300", records) is True

    conn = db.get_connection()
    conn.execute(
        "UPDATE index_nav_history SET updated_at = ? WHERE index_code = ? AND nav_date = ?",
        ("2020-01-01 00:00:00", "000300", "2026-07-17"),
    )
    conn.commit()
    conn.close()

    assert db.bulk_upsert_index_nav_history("000300", records) is False
    conn = db.get_connection()
    row = conn.execute(
        "SELECT updated_at FROM index_nav_history WHERE index_code = ? AND nav_date = ?",
        ("000300", "2026-07-17"),
    ).fetchone()
    conn.close()
    assert row["updated_at"] == "2020-01-01 00:00:00"
