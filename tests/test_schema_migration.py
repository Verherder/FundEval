import sqlite3

from src.schema import get_schema_version, migrate_legacy_database


def test_legacy_migration_builds_shared_pool_and_preserves_private_data(tmp_path):
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE user_funds (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                fund_code TEXT NOT NULL,
                fund_key TEXT NOT NULL,
                fund_name TEXT NOT NULL,
                is_hold INTEGER DEFAULT 0,
                shares REAL DEFAULT 0,
                sectors TEXT,
                establishment_date TEXT,
                estimate_history TEXT DEFAULT '{}',
                estimate_history_2 TEXT DEFAULT '{}',
                chart_default INTEGER DEFAULT 0,
                UNIQUE(user_id, fund_code)
            );
            CREATE TABLE fund_transactions (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                fund_code TEXT NOT NULL,
                tx_type TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                shares REAL NOT NULL DEFAULT 0,
                net_value REAL,
                tx_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE fund_pending_buys (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                fund_code TEXT NOT NULL,
                amount REAL NOT NULL,
                effective_date TEXT NOT NULL,
                status TEXT DEFAULT 'pending'
            );
            INSERT INTO users VALUES (1, 'jiaming', 'hash-a');
            INSERT INTO users VALUES (2, 'alice', 'hash-b');
            INSERT INTO user_funds
                (id,user_id,fund_code,fund_key,fund_name,is_hold,shares,sectors)
                VALUES (1,1,'000001','admin-key','管理员基金',1,12.345,'["管理员"]');
            INSERT INTO user_funds
                (id,user_id,fund_code,fund_key,fund_name,is_hold,shares,sectors)
                VALUES (2,2,'000001','user-key','重复基金',0,3.2,'["用户"]');
            INSERT INTO user_funds
                (id,user_id,fund_code,fund_key,fund_name,is_hold,shares,sectors)
                VALUES (3,2,'000002','second-key','用户新增基金',1,8.8,'[]');
            INSERT INTO fund_transactions
                (id,user_id,fund_code,tx_type,amount,shares)
                VALUES (1,2,'000002','buy',100,8.8);
            INSERT INTO fund_pending_buys
                (id,user_id,fund_code,amount,effective_date)
                VALUES (1,2,'000002',50,'2026-07-25');
            """
        )
        original_users = conn.execute(
            "SELECT id,username,password_hash FROM users ORDER BY id"
        ).fetchall()
        original_transactions = conn.execute(
            "SELECT * FROM fund_transactions ORDER BY id"
        ).fetchall()
        original_pending_buys = conn.execute(
            "SELECT * FROM fund_pending_buys ORDER BY id"
        ).fetchall()

    result = migrate_legacy_database(db_path, apply=True)

    assert result["migrated"] is True
    with sqlite3.connect(db_path) as conn:
        assert get_schema_version(conn) == 2
        assert conn.execute("SELECT COUNT(*) FROM fund_catalog").fetchone()[0] == 2
        assert conn.execute(
            "SELECT fund_name FROM fund_catalog WHERE fund_code='000001'"
        ).fetchone()[0] == "管理员基金"
        assert conn.execute(
            "SELECT COUNT(*) FROM user_watchlist WHERE user_id=1"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM user_watchlist WHERE user_id=2"
        ).fetchone()[0] == 2
        assert conn.execute(
            "SELECT shares FROM user_watchlist WHERE user_id=2 AND fund_code='000001'"
        ).fetchone()[0] == 3.2
        assert conn.execute(
            "SELECT COUNT(*) FROM fund_transactions WHERE user_id=2"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM fund_pending_buys WHERE user_id=2"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT id,username,password_hash FROM users ORDER BY id"
        ).fetchall() == original_users
        assert conn.execute(
            """
            SELECT id,user_id,fund_code,tx_type,amount,shares,net_value,tx_time
            FROM fund_transactions ORDER BY id
            """
        ).fetchall() == original_transactions
        assert conn.execute(
            """
            SELECT id,user_id,fund_code,amount,effective_date,status
            FROM fund_pending_buys ORDER BY id
            """
        ).fetchall() == original_pending_buys
        assert conn.execute(
            "SELECT COUNT(*) FROM users WHERE password_reset_required != 0"
        ).fetchone()[0] == 0
