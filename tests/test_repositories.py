# -*- coding: UTF-8 -*-
"""Tests for repository layer — verifies delegation to Database methods."""

from unittest.mock import MagicMock

import pytest

from src.repositories.user_repo import UserRepo
from src.repositories.fund_repo import FundRepo
from src.repositories.transaction_repo import TransactionRepo
from src.repositories.nav_repo import NavRepo


# ── helpers ──────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    return MagicMock()


# ── UserRepo ─────────────────────────────────────────────────────────

class TestUserRepo:
    def test_create_user_delegates(self, mock_db):
        mock_db.create_user.return_value = (True, "ok", 1)
        repo = UserRepo(mock_db)
        result = repo.create_user("alice", "secret")
        mock_db.create_user.assert_called_once_with("alice", "secret")
        assert result == (True, "ok", 1)

    def test_get_user_by_username_delegates(self, mock_db):
        mock_db.get_user_by_username.return_value = {"id": 1, "username": "alice"}
        repo = UserRepo(mock_db)
        result = repo.get_user_by_username("alice")
        mock_db.get_user_by_username.assert_called_once_with("alice")
        assert result == {"id": 1, "username": "alice"}

    def test_get_user_by_username_none(self, mock_db):
        mock_db.get_user_by_username.return_value = None
        repo = UserRepo(mock_db)
        result = repo.get_user_by_username("nobody")
        assert result is None

    def test_verify_password_delegates(self, mock_db):
        mock_db.verify_password.return_value = (True, 1)
        repo = UserRepo(mock_db)
        result = repo.verify_password("alice", "secret")
        mock_db.verify_password.assert_called_once_with("alice", "secret")
        assert result == (True, 1)


# ── FundRepo ─────────────────────────────────────────────────────────

class TestFundRepo:
    def test_get_user_funds_delegates(self, mock_db):
        mock_db.get_user_funds.return_value = {"000001": {"name": "Test Fund"}}
        repo = FundRepo(mock_db)
        result = repo.get_user_funds(1)
        mock_db.get_user_funds.assert_called_once_with(1)
        assert result == {"000001": {"name": "Test Fund"}}

    def test_save_user_funds_delegates(self, mock_db):
        repo = FundRepo(mock_db)
        fund_map = {"000001": {"name": "Test"}}
        repo.save_user_funds(1, fund_map)
        mock_db.save_user_funds.assert_called_once_with(1, fund_map)

    def test_update_fund_shares_delegates(self, mock_db):
        repo = FundRepo(mock_db)
        repo.update_fund_shares(1, "000001", 100.0)
        mock_db.update_fund_shares.assert_called_once_with(1, "000001", 100.0)

    def test_add_fund_delegates(self, mock_db):
        repo = FundRepo(mock_db)
        repo.add_fund(1, "000001", "key", "Test Fund")
        mock_db.add_fund.assert_called_once_with(1, "000001", "key", "Test Fund")

    def test_delete_fund_delegates(self, mock_db):
        repo = FundRepo(mock_db)
        repo.delete_fund(1, "000001")
        mock_db.delete_fund.assert_called_once_with(1, "000001")

    def test_update_chart_default_delegates(self, mock_db):
        repo = FundRepo(mock_db)
        repo.update_chart_default(1, "000001")
        mock_db.update_chart_default.assert_called_once_with(1, "000001")

    def test_update_fund_shares_delta_delegates(self, mock_db):
        repo = FundRepo(mock_db)
        repo.update_fund_shares_delta(1, "000001", 50.0)
        mock_db.update_fund_shares_delta.assert_called_once_with(1, "000001", 50.0)

    def test_update_fund_establishment_date_delegates(self, mock_db):
        repo = FundRepo(mock_db)
        repo.update_fund_establishment_date(1, "000001", "2020-01-01")
        mock_db.update_fund_establishment_date.assert_called_once_with(1, "000001", "2020-01-01")

    def test_recalculate_fund_shares_from_transactions_delegates(self, mock_db):
        repo = FundRepo(mock_db)
        repo.recalculate_fund_shares_from_transactions(1, "000001")
        mock_db.recalculate_fund_shares_from_transactions.assert_called_once_with(1, "000001")

    def test_get_chart_default_fund_delegates(self, mock_db):
        mock_db.get_chart_default_fund.return_value = "000001"
        repo = FundRepo(mock_db)
        result = repo.get_chart_default_fund(1)
        mock_db.get_chart_default_fund.assert_called_once_with(1)
        assert result == "000001"


# ── TransactionRepo ──────────────────────────────────────────────────

class TestTransactionRepo:
    def test_add_fund_transaction_delegates(self, mock_db):
        mock_db.add_fund_transaction.return_value = 1
        repo = TransactionRepo(mock_db)
        result = repo.add_fund_transaction(
            1, "000001", "buy", 1000.0, 500.0,
            net_value=2.0, tx_time="2024-01-01", fee=1.5, order_no="ON123"
        )
        mock_db.add_fund_transaction.assert_called_once_with(
            1, "000001", "buy", 1000.0, 500.0, 2.0, "2024-01-01", 1.5, "ON123"
        )
        assert result == 1

    def test_add_pending_buy_delegates(self, mock_db):
        repo = TransactionRepo(mock_db)
        repo.add_pending_buy(1, "000001", 1000.0, "2024-01-15")
        mock_db.add_pending_buy.assert_called_once_with(1, "000001", 1000.0, "2024-01-15")

    def test_get_pending_buys_delegates(self, mock_db):
        mock_db.get_pending_buys.return_value = [{"id": 1, "amount": 1000}]
        repo = TransactionRepo(mock_db)
        result = repo.get_pending_buys(1, fund_code="000001")
        mock_db.get_pending_buys.assert_called_once_with(1, "000001")
        assert result == [{"id": 1, "amount": 1000}]

    def test_get_pending_buys_no_fund_code(self, mock_db):
        mock_db.get_pending_buys.return_value = []
        repo = TransactionRepo(mock_db)
        result = repo.get_pending_buys(1)
        mock_db.get_pending_buys.assert_called_once_with(1, None)
        assert result == []

    def test_mark_pending_buy_settled_delegates(self, mock_db):
        repo = TransactionRepo(mock_db)
        repo.mark_pending_buy_settled(1, 100, 2.5, 400.0)
        mock_db.mark_pending_buy_settled.assert_called_once_with(1, 100, 2.5, 400.0)

    def test_get_fund_transactions_delegates(self, mock_db):
        mock_db.get_fund_transactions.return_value = [{"id": 1, "tx_type": "buy"}]
        repo = TransactionRepo(mock_db)
        result = repo.get_fund_transactions(1, "000001")
        mock_db.get_fund_transactions.assert_called_once_with(1, "000001")
        assert result == [{"id": 1, "tx_type": "buy"}]

    def test_get_all_fund_transactions_delegates(self, mock_db):
        mock_db.get_all_fund_transactions.return_value = [{"id": 1}]
        repo = TransactionRepo(mock_db)
        result = repo.get_all_fund_transactions(1)
        mock_db.get_all_fund_transactions.assert_called_once_with(1)
        assert result == [{"id": 1}]

    def test_exists_transaction_order_no_delegates(self, mock_db):
        mock_db.exists_transaction_order_no.return_value = True
        repo = TransactionRepo(mock_db)
        result = repo.exists_transaction_order_no("ON123")
        mock_db.exists_transaction_order_no.assert_called_once_with("ON123")
        assert result is True

    def test_update_fund_transaction_and_recalculate_delegates(self, mock_db):
        repo = TransactionRepo(mock_db)
        repo.update_fund_transaction_and_recalculate(
            1, "000001", 10, "buy", 500.0, 250.0, 2.0, "2024-01-01", fee=1.0
        )
        mock_db.update_fund_transaction_and_recalculate.assert_called_once_with(
            1, "000001", 10, "buy", 500.0, 250.0, 2.0, "2024-01-01", 1.0
        )

    def test_delete_fund_transaction_and_recalculate_delegates(self, mock_db):
        repo = TransactionRepo(mock_db)
        repo.delete_fund_transaction_and_recalculate(1, "000001", 10)
        mock_db.delete_fund_transaction_and_recalculate.assert_called_once_with(1, "000001", 10)

    def test_clear_fund_transactions_and_recalculate_delegates(self, mock_db):
        repo = TransactionRepo(mock_db)
        repo.clear_fund_transactions_and_recalculate(1, "000001")
        mock_db.clear_fund_transactions_and_recalculate.assert_called_once_with(1, "000001")

    def test_clear_all_fund_transactions_and_recalculate_delegates(self, mock_db):
        repo = TransactionRepo(mock_db)
        repo.clear_all_fund_transactions_and_recalculate(1)
        mock_db.clear_all_fund_transactions_and_recalculate.assert_called_once_with(1)


# ── NavRepo ──────────────────────────────────────────────────────────

class TestNavRepo:
    def test_get_fund_nav_by_date_delegates(self, mock_db):
        mock_db.get_fund_nav_by_date.return_value = {"nav": 1.5}
        repo = NavRepo(mock_db)
        result = repo.get_fund_nav_by_date("000001", "2024-01-01")
        mock_db.get_fund_nav_by_date.assert_called_once_with("000001", "2024-01-01")
        assert result == {"nav": 1.5}

    def test_get_prev_fund_nav_delegates(self, mock_db):
        mock_db.get_prev_fund_nav.return_value = {"nav": 1.4}
        repo = NavRepo(mock_db)
        result = repo.get_prev_fund_nav("000001", "2024-01-02")
        mock_db.get_prev_fund_nav.assert_called_once_with("000001", "2024-01-02")
        assert result == {"nav": 1.4}

    def test_upsert_fund_nav_history_delegates(self, mock_db):
        repo = NavRepo(mock_db)
        repo.upsert_fund_nav_history("000001", "2024-01-01", 1.5, source="test")
        mock_db.upsert_fund_nav_history.assert_called_once_with(
            "000001", "2024-01-01", 1.5, "test"
        )

    def test_get_fund_nav_history_range_delegates(self, mock_db):
        mock_db.get_fund_nav_history_range.return_value = [{"nav": 1.5}]
        repo = NavRepo(mock_db)
        result = repo.get_fund_nav_history_range("000001", "2024-01-01", "2024-12-31")
        mock_db.get_fund_nav_history_range.assert_called_once_with(
            "000001", "2024-01-01", "2024-12-31"
        )
        assert result == [{"nav": 1.5}]

    def test_get_fund_performance_curve_cache_delegates(self, mock_db):
        mock_db.get_fund_performance_curve_cache.return_value = [{"date": "2024-01-01"}]
        repo = NavRepo(mock_db)
        result = repo.get_fund_performance_curve_cache(
            "000001", "1y", "2024-01-01", "2024-12-31"
        )
        mock_db.get_fund_performance_curve_cache.assert_called_once_with(
            "000001", "1y", "2024-01-01", "2024-12-31"
        )
        assert result == [{"date": "2024-01-01"}]

    def test_bulk_upsert_fund_performance_curve_cache_delegates(self, mock_db):
        repo = NavRepo(mock_db)
        points = [{"date": "2024-01-01", "nav": 1.5}]
        repo.bulk_upsert_fund_performance_curve_cache("000001", "1y", points, source="test")
        mock_db.bulk_upsert_fund_performance_curve_cache.assert_called_once_with(
            "000001", "1y", points, "test"
        )

    def test_bulk_upsert_index_nav_history_delegates(self, mock_db):
        repo = NavRepo(mock_db)
        records = [{"date": "2024-01-01", "value": 3000.0}]
        repo.bulk_upsert_index_nav_history("000001", records)
        mock_db.bulk_upsert_index_nav_history.assert_called_once_with("000001", records)

    def test_get_index_nav_history_range_delegates(self, mock_db):
        mock_db.get_index_nav_history_range.return_value = [{"date": "2024-01-01"}]
        repo = NavRepo(mock_db)
        result = repo.get_index_nav_history_range("000001", "2024-01-01", "2024-12-31")
        mock_db.get_index_nav_history_range.assert_called_once_with(
            "000001", "2024-01-01", "2024-12-31"
        )
        assert result == [{"date": "2024-01-01"}]
