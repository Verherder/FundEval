# -*- coding: UTF-8 -*-
"""Regression tests for refreshed NAV persistence and daily return calculation."""

import datetime
from unittest.mock import MagicMock

from src.fund import normalize_nav_date_for_storage
from src.fund_table import build_fund_table


def test_normalize_nav_date_for_storage_expands_short_date():
    today = datetime.date(2024, 1, 3)

    assert normalize_nav_date_for_storage("01-02", today=today) == "2024-01-02"
    assert normalize_nav_date_for_storage("12-29", today=today) == "2023-12-29"
    assert normalize_nav_date_for_storage("20240102", today=today) == "2024-01-02"


def test_daily_return_uses_nav_delta_and_shares_when_prev_nav_exists():
    fund_obj = _FakeMiniFund()
    fund_obj.nav_repo.get_fund_nav_by_date.return_value = 1.1

    _titles, rows, _sortable = build_fund_table(fund_obj)

    assert "¥10.00" in rows[0][8]
    fund_obj.nav_repo.get_fund_nav_by_date.assert_any_call("000001", "2024-01-02")
    fund_obj._fetch_prev_nav_from_cloud.assert_not_called()


def test_estimated_return_uses_prev_nav_and_does_not_store_estimated_nav():
    fund_obj = _FakeMiniFund(forecast_growth="2.00%")
    fund_obj.nav_repo.get_fund_nav_by_date.return_value = 1.1

    _titles, rows, _sortable = build_fund_table(fund_obj)

    assert "data-estimate-return='2.200000'" in rows[0][3]
    fund_obj.nav_repo.upsert_fund_nav_history.assert_not_called()


def test_estimated_return_falls_back_to_estimate2_when_estimate1_missing():
    fund_obj = _FakeMiniFund(forecast_growth="N/A", estimate2_growth="2.00%")
    fund_obj.nav_repo.get_fund_nav_by_date.return_value = 1.1

    _titles, rows, _sortable = build_fund_table(fund_obj)

    assert "data-estimate-return=" not in rows[0][3]
    assert "data-estimate2-return='2.400000'" in rows[0][4]


def test_estimate2_return_uses_current_nav_for_overseas_fund_update_time():
    fund_obj = _FakeMiniFund(forecast_growth="N/A", estimate2_growth="2.00%", estimate2_date="2024-01-06")
    fund_obj.nav_repo.get_fund_nav_by_date.return_value = None
    fund_obj.nav_repo.get_prev_fund_nav.return_value = 1.1

    _titles, rows, _sortable = build_fund_table(fund_obj)

    assert "data-estimate2-return='2.400000'" in rows[0][4]
    fund_obj.nav_repo.get_prev_fund_nav.assert_not_called()


def test_daily_return_does_not_use_latest_nav_as_missing_prev_nav():
    fund_obj = _FakeMiniFund()
    fund_obj.nav_repo.get_fund_nav_by_date.return_value = None
    fund_obj.nav_repo.get_prev_fund_nav.return_value = None

    _titles, rows, _sortable = build_fund_table(fund_obj)

    assert rows[0][8] == "--"
    fund_obj._fetch_prev_nav_from_cloud.assert_not_called()


class _FakeMiniFund:
    def __init__(self, forecast_growth="0.00%", estimate2_growth="0.00%", estimate2_date="2024-01-03"):
        self.forecast_growth = forecast_growth
        self.estimate2_growth = estimate2_growth
        self.estimate2_date = estimate2_date
        self.CACHE_MAP = {
            "000001": {
                "fund_name": "测试基金",
                "fund_key": "KEY1",
                "shares": 100,
                "is_hold": False,
            }
        }
        self.db = MagicMock()
        self.db.get_fund_transactions.return_value = []
        self.user_id = 1
        self.nav_repo = MagicMock()
        self.nav_repo.get_prev_fund_nav.return_value = None
        self._fetch_history_nav_map_by_date_range = MagicMock(return_value={})
        self._fetch_prev_nav_from_cloud = MagicMock(return_value=1.2)

    def search_code(self, is_return=False):
        return [[
            "000001",
            "测试基金",
            "15:00",
            "1.2000(2024-01-03)",
            self.forecast_growth,
            "1.00%",
            "2024-01-03",
            "1天 1.00%",
            "1/1 1.00%",
            "2024-01-03",
            self.estimate2_growth,
            "15:00",
            self.estimate2_date,
        ]]


def test_missing_prev_nav_is_backfilled_from_history_api_for_estimated_return():
    fund_obj = _FakeMiniFund(forecast_growth="2.00%")
    fund_obj.nav_repo.get_fund_nav_by_date.side_effect = [None, 1.1, 1.1, 1.1]
    fund_obj._fetch_history_nav_map_by_date_range.return_value = {"2024-01-02": 1.1}

    _titles, rows, _sortable = build_fund_table(fund_obj)

    assert "data-estimate-return='2.200000'" in rows[0][3]
    fund_obj._fetch_history_nav_map_by_date_range.assert_called_with("KEY1", "2024-01-02", "2024-01-03")
    fund_obj.nav_repo.upsert_fund_nav_history.assert_any_call(
        "000001", "2024-01-02", 1.1, "history_api_prev_nav_on_table"
    )
