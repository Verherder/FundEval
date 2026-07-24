# -*- coding: UTF-8 -*-
"""Versioned SQLite schema and the explicit legacy migration."""

import json
import sqlite3
from pathlib import Path


SCHEMA_VERSION = 2
EXAMPLE_FUNDS = (
    ("000594", "20150718000230030000000000002794", "大摩进取优选股票"),
    ("000913", "20150718000230030000000000000574", "农银医疗保健股票"),
    ("001208", "20150718000230030000000000000428", "诺安低碳经济股票A"),
)


class MigrationRequired(RuntimeError):
    pass


def _table_exists(conn, name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def get_schema_version(conn):
    if not _table_exists(conn, "schema_meta"):
        return 0
    row = conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
    return int(row[0]) if row else 0


def create_latest_schema(conn):
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            password_reset_required INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS fund_catalog (
            fund_code TEXT PRIMARY KEY,
            fund_key TEXT NOT NULL,
            fund_name TEXT NOT NULL,
            sectors TEXT NOT NULL DEFAULT '[]',
            establishment_date TEXT,
            estimate_history TEXT NOT NULL DEFAULT '{}',
            estimate_history_2 TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS user_watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            fund_code TEXT NOT NULL,
            is_hold INTEGER NOT NULL DEFAULT 0,
            shares REAL NOT NULL DEFAULT 0,
            chart_default INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (fund_code) REFERENCES fund_catalog(fund_code),
            UNIQUE(user_id, fund_code)
        );
        CREATE TABLE IF NOT EXISTS fund_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            fund_code TEXT NOT NULL,
            order_no TEXT,
            tx_type TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            shares REAL NOT NULL DEFAULT 0,
            net_value REAL,
            tx_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fee REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_user_order
            ON fund_transactions(user_id, order_no)
            WHERE order_no IS NOT NULL AND order_no != '';
        CREATE TABLE IF NOT EXISTS fund_pending_buys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            fund_code TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            effective_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            settled_tx_id INTEGER,
            settled_net_value REAL,
            settled_shares REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            settled_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (settled_tx_id) REFERENCES fund_transactions(id)
        );
        CREATE TABLE IF NOT EXISTS fund_nav_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fund_code TEXT NOT NULL,
            nav_date TEXT NOT NULL,
            nav_value REAL NOT NULL,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(fund_code, nav_date)
        );
        CREATE INDEX IF NOT EXISTS idx_fund_nav_history_code_date
            ON fund_nav_history(fund_code, nav_date);
        CREATE INDEX IF NOT EXISTS idx_fund_nav_history_date ON fund_nav_history(nav_date);
        CREATE TABLE IF NOT EXISTS fund_performance_curve_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fund_code TEXT NOT NULL,
            date_interval TEXT NOT NULL,
            curve_date TEXT NOT NULL,
            growth_rate REAL,
            benchmark_growth_rate REAL,
            nav_value REAL,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(fund_code, date_interval, curve_date)
        );
        CREATE INDEX IF NOT EXISTS idx_curve_cache_code_interval_date
            ON fund_performance_curve_cache(fund_code, date_interval, curve_date);
        CREATE INDEX IF NOT EXISTS idx_curve_cache_code_date
            ON fund_performance_curve_cache(fund_code, curve_date);
        CREATE TABLE IF NOT EXISTS index_nav_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            index_code TEXT NOT NULL,
            nav_date TEXT NOT NULL,
            close REAL NOT NULL,
            change_pct REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(index_code, nav_date)
        );
        CREATE INDEX IF NOT EXISTS idx_index_nav_history_code_date
            ON index_nav_history(index_code, nav_date);
        CREATE TABLE IF NOT EXISTS invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_hash TEXT UNIQUE NOT NULL,
            created_by INTEGER NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used_by INTEGER,
            used_at TIMESTAMP,
            revoked_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS remember_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            revoked_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identity_hash TEXT NOT NULL,
            succeeded INTEGER NOT NULL DEFAULT 0,
            attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_login_attempt_identity_time
            ON login_attempts(identity_hash, attempted_at);
        CREATE TABLE IF NOT EXISTS import_jobs (
            job_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            state_json TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )


def inspect_legacy(conn):
    def count(table, where="", args=()):
        if not _table_exists(conn, table):
            return 0
        return conn.execute(f"SELECT COUNT(*) FROM {table} {where}", args).fetchone()[0]

    return {
        "schema_version": get_schema_version(conn),
        "users": count("users"),
        "funds": count("user_funds"),
        "transactions": count("fund_transactions"),
        "pending_buys": count("fund_pending_buys"),
        "jiaming_funds": count(
            "user_funds",
            "WHERE user_id=(SELECT id FROM users WHERE username='jiaming')",
        ),
    }


def migrate_legacy_database(db_path, apply=False):
    path = Path(db_path)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    summary = inspect_legacy(conn)
    if not apply or summary["schema_version"] == SCHEMA_VERSION:
        conn.close()
        return summary
    if summary["schema_version"] not in (0, 1):
        conn.close()
        raise MigrationRequired(f"不支持的数据库版本: {summary['schema_version']}")

    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("ALTER TABLE user_funds RENAME TO legacy_user_funds")
        conn.execute("DROP INDEX IF EXISTS idx_fund_transactions_order_no_unique")
        user_columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        if "is_admin" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
        if "password_reset_required" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN password_reset_required INTEGER NOT NULL DEFAULT 0")
        tx_columns = {row[1] for row in conn.execute("PRAGMA table_info(fund_transactions)")}
        if "order_no" not in tx_columns:
            conn.execute("ALTER TABLE fund_transactions ADD COLUMN order_no TEXT")
        if "fee" not in tx_columns:
            conn.execute("ALTER TABLE fund_transactions ADD COLUMN fee REAL NOT NULL DEFAULT 0")
        create_latest_schema(conn)
        admin = conn.execute("SELECT id FROM users WHERE username='jiaming'").fetchone()
        admin_id = admin[0] if admin else None
        conn.execute("UPDATE users SET is_admin=CASE WHEN username='jiaming' THEN 1 ELSE 0 END")

        rows = conn.execute(
            """
            SELECT *
            FROM legacy_user_funds
            ORDER BY CASE WHEN user_id=? THEN 0 ELSE 1 END, id
            """,
            (admin_id,),
        ).fetchall()
        for row in rows:
            keys = set(row.keys())
            conn.execute(
                """INSERT OR IGNORE INTO fund_catalog
                   (fund_code,fund_key,fund_name,sectors,establishment_date,
                    estimate_history,estimate_history_2)
                   VALUES(?,?,?,?,?,?,?)""",
                (
                    row["fund_code"], row["fund_key"], row["fund_name"],
                    row["sectors"] if "sectors" in keys and row["sectors"] else "[]",
                    row["establishment_date"] if "establishment_date" in keys else None,
                    row["estimate_history"] if "estimate_history" in keys and row["estimate_history"] else "{}",
                    row["estimate_history_2"] if "estimate_history_2" in keys and row["estimate_history_2"] else "{}",
                ),
            )
            conn.execute(
                """INSERT OR IGNORE INTO user_watchlist
                   (id,user_id,fund_code,is_hold,shares,chart_default)
                   VALUES(?,?,?,?,?,?)""",
                (
                    row["id"], row["user_id"], row["fund_code"], int(row["is_hold"] or 0),
                    row["shares"] if row["shares"] is not None else 0,
                    int(row["chart_default"] or 0) if "chart_default" in keys else 0,
                ),
            )

        expected_watchlists = {
            (
                row["user_id"],
                row["fund_code"],
                int(row["is_hold"] or 0),
                row["shares"] if row["shares"] is not None else 0,
                int(row["chart_default"] or 0) if "chart_default" in row.keys() else 0,
            )
            for row in rows
        }
        actual_watchlists = {
            tuple(row)
            for row in conn.execute(
                """
                SELECT user_id, fund_code, is_hold, shares, chart_default
                FROM user_watchlist
                """
            )
        }
        if actual_watchlists != expected_watchlists:
            raise RuntimeError("迁移前后用户自选、持有状态、份额或默认图表不一致")

        conn.execute("DROP TABLE legacy_user_funds")
        conn.commit()
        return {**summary, "migrated": True, "target_version": SCHEMA_VERSION}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
