# -*- coding: UTF-8 -*-
"""Pytest fixtures for FundEval tests."""

import json
import sqlite3
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "docs" / "refactor" / "fixtures"


@pytest.fixture
def test_user_id():
    """Fixed test user ID for regression tests."""
    return 1


@pytest.fixture
def db(tmp_path):
    """In-memory SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    # Create minimal schema matching src/database.py
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_funds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            fund_code TEXT NOT NULL,
            fund_key TEXT NOT NULL,
            fund_name TEXT NOT NULL,
            is_hold INTEGER DEFAULT 0,
            shares REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, fund_code)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            fund_code TEXT NOT NULL,
            tx_type TEXT NOT NULL,
            date TEXT NOT NULL,
            amount REAL,
            shares REAL,
            price REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insert test user
    cursor.execute(
        "INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)",
        (1, "testuser", "$2b$12$test_hash_for_testing_only")
    )

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def api_fund_data():
    """Load api_fund_data.json fixture."""
    fixture_path = FIXTURES_DIR / "api_fund_data.json"
    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def api_performance_chart_data():
    """Load api_performance_chart_data.json fixture."""
    fixture_path = FIXTURES_DIR / "api_performance_chart_data.json"
    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)