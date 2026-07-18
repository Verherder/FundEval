# -*- coding: UTF-8 -*-
"""Regression tests for refreshed NAV persistence and daily return calculation."""

import datetime
import threading
from unittest.mock import MagicMock

import pytest

from src.fund import Fund123EndpointBlockedError, MiniFund, normalize_nav_date_for_storage
from src.fund_table import build_fund_table, calculate_position_summary
from src.providers import FundHttpTransport


def test_normalize_nav_date_for_storage_expands_short_date():
    today = datetime.date(2024, 1, 3)

    assert normalize_nav_date_for_storage("01-02", today=today) == "2024-01-02"
    assert normalize_nav_date_for_storage("12-29", today=today) == "2023-12-29"
    assert normalize_nav_date_for_storage("20240102", today=today) == "2024-01-02"


def test_json_request_retries_empty_response(monkeypatch):
    empty_response = MagicMock(content=b"", text="", status_code=200, headers={})
    valid_response = MagicMock(content=b'{"success": true}', text='{"success": true}', status_code=200, headers={})
    valid_response.json.return_value = {"success": True}
    transport = FundHttpTransport(sleep_fn=lambda _seconds: None)
    transport.request = MagicMock(side_effect=[empty_response, valid_response])

    response, payload = transport.request_json("POST", "https://example.test/api")

    assert response is valid_response
    assert payload == {"success": True}
    assert transport.request.call_count == 2


def test_forbidden_endpoint_is_circuit_broken(monkeypatch):
    FundHttpTransport.clear_circuit_breakers()
    response = MagicMock(status_code=403, headers={})
    session = MagicMock()
    session.request.return_value = response
    transport = FundHttpTransport(session=session, sleep_fn=lambda _seconds: None)
    transport._thread_local.session = session

    try:
        with pytest.raises(Fund123EndpointBlockedError):
            transport.request("POST", "https://example.test/blocked")
        with pytest.raises(Fund123EndpointBlockedError):
            transport.request("POST", "https://example.test/blocked")
        assert session.request.call_count == 1
    finally:
        FundHttpTransport.clear_circuit_breakers()


def test_fund_refresh_only_requests_latest_estimate_not_trend_data(monkeypatch):
    fund_obj = MiniFund.__new__(MiniFund)
    fund_obj._refresh_semaphore = threading.Semaphore(1)
    fund_obj._csrf = "csrf"
    fund_obj.db = None
    fund_obj.user_id = None
    fund_obj.nav_repo = None
    fund_obj._cache_dirty = False
    fund_obj.result = []
    fund_obj.CACHE_MAP = {
        "260101": {
            "fund_key": "KEY260101",
            "fund_name": "测试基金",
            "is_hold": False,
            "sectors": [],
        }
    }
    detail_response = MagicMock(
        text='"dayOfGrowth":"1.2","netValue":"1.5","netValueDate":"2026-07-17"'
    )
    fallback_response = MagicMock(
        text='jsonpgz({"gszzl":"1.23","gztime":"2026-07-17 15:00"});',
        status_code=200,
    )
    fund_obj._request_with_retries = MagicMock(side_effect=[detail_response, fallback_response])
    fund_obj._request_json_with_retries = MagicMock()
    fund_obj.fetch_latest_intraday_estimate = MagicMock(return_value={
        "growth": -2.34,
        "net_value": 1.46,
        "date": "2026-07-18",
        "time": "14:30",
    })

    fund_obj.search_one_code("260101", fund_obj.CACHE_MAP["260101"], True)

    requested_urls = [call.args[1] for call in fund_obj._request_with_retries.call_args_list]
    requested_urls += [call.args[1] for call in fund_obj._request_json_with_retries.call_args_list]
    from src.fund import DATA_SOURCE_URLS
    assert DATA_SOURCE_URLS["fund123_curves_api"] not in requested_urls
    assert DATA_SOURCE_URLS["fund123_intraday_api"] not in requested_urls
    assert DATA_SOURCE_URLS["fundgz_js_tpl"].format(fund="260101") in requested_urls
    fund_obj._request_json_with_retries.assert_not_called()
    fund_obj.fetch_latest_intraday_estimate.assert_called_once_with("KEY260101", cancel_event=None)
    assert len(fund_obj.result) == 1
    assert fund_obj.result[0][4] == "-2.34%"
    assert fund_obj.result[0][9] == "2026-07-18"
    assert fund_obj.result[0][10] == "1.23%"
    assert fund_obj.result[0][12] == "2026-07-17"


def test_latest_estimate_interface_returns_only_last_point():
    fund_obj = MiniFund.__new__(MiniFund)
    fund_obj._csrf = "csrf"
    quote_time = datetime.datetime(2026, 7, 18, 14, 30).timestamp() * 1000
    fund_obj._request_json_with_retries = MagicMock(return_value=(MagicMock(), {
        "success": True,
        "list": [
            {"time": quote_time - 60000, "forecastGrowth": "-0.01", "forecastNetValue": "1.48"},
            {"time": quote_time, "forecastGrowth": "-0.0234", "forecastNetValue": "1.46"},
        ],
    }))

    result = fund_obj.fetch_latest_intraday_estimate("KEY260101")

    assert result == {
        "growth": -2.34,
        "net_value": 1.46,
        "date": "2026-07-18",
        "time": "14:30",
    }


def test_daily_return_uses_nav_delta_and_shares_when_prev_nav_exists():
    fund_obj = _FakeMiniFund()
    fund_obj.nav_repo.get_fund_nav_by_date.return_value = 1.1

    _titles, rows, _sortable = build_fund_table(fund_obj)

    assert "¥10.00" in rows[0][8]
    fund_obj.nav_repo.get_fund_nav_by_date.assert_any_call("000001", "2024-01-02")
    fund_obj._fetch_prev_nav_from_cloud.assert_not_called()


def test_daily_return_uses_shares_before_nav_date():
    fund_obj = _FakeMiniFund()
    fund_obj.CACHE_MAP["000001"]["shares"] = 150
    fund_obj.db.get_fund_transactions.return_value = [
        {
            "tx_type": "buy",
            "shares": 100,
            "tx_time": "2024-01-01 15:00:00",
        },
        {
            "tx_type": "buy",
            "shares": 50,
            "tx_time": "2024-01-03 15:00:00",
        },
    ]
    fund_obj.nav_repo.get_fund_nav_by_date.return_value = 1.1

    _titles, rows, _sortable = build_fund_table(fund_obj)

    assert "¥10.00" in rows[0][8]
    assert "¥15.00" not in rows[0][8]


def test_position_summary_actual_gain_uses_shares_before_nav_date():
    today = datetime.date.today()
    prior_day = today - datetime.timedelta(days=2)
    result = [[
        "000001",
        "测试基金",
        "15:00",
        f"1.2000({today.isoformat()})",
        "0.00%",
        "10.00%",
        today.isoformat(),
        "1天 10.00%",
        "1/1 10.00%",
    ]]
    cache_map = {"000001": {"shares": 150}}
    db = MagicMock()
    db.get_fund_transactions.return_value = [
        {
            "tx_type": "buy",
            "shares": 100,
            "tx_time": f"{prior_day.isoformat()} 15:00:00",
        },
        {
            "tx_type": "buy",
            "shares": 50,
            "tx_time": f"{today.isoformat()} 15:00:00",
        },
    ]

    summary = calculate_position_summary(result, cache_map, db=db, user_id=1)

    assert summary["actual_gain"] == 12.0
    assert summary["settled_value"] == 120.0


def test_estimated_return_uses_prev_nav_and_does_not_store_estimated_nav():
    fund_obj = _FakeMiniFund(forecast_growth="2.00%")
    fund_obj.nav_repo.get_fund_nav_by_date.return_value = 1.1

    _titles, rows, _sortable = build_fund_table(fund_obj)

    assert "data-estimate-return='2.200000'" in rows[0][3]
    fund_obj.nav_repo.upsert_fund_nav_history.assert_not_called()


def test_estimated_return_falls_back_to_estimate2_when_estimate1_missing():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    fund_obj = _FakeMiniFund(forecast_growth="N/A", estimate2_growth="2.00%", estimate2_date=today)
    fund_obj.nav_repo.get_fund_nav_by_date.return_value = 1.1

    _titles, rows, _sortable = build_fund_table(fund_obj)

    assert "data-estimate-return=" not in rows[0][3]
    assert "data-estimate2-return='2.400000'" in rows[0][4]


def test_estimate2_return_uses_current_nav_for_overseas_fund_update_time():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    fund_obj = _FakeMiniFund(forecast_growth="N/A", estimate2_growth="2.00%", estimate2_date=today)
    fund_obj.nav_repo.get_fund_nav_by_date.return_value = None
    fund_obj.nav_repo.get_prev_fund_nav.return_value = 1.1

    _titles, rows, _sortable = build_fund_table(fund_obj)

    assert "data-estimate2-return='2.400000'" in rows[0][4]
    fund_obj.nav_repo.get_prev_fund_nav.assert_not_called()


def test_stale_estimate2_date_does_not_produce_summary_return():
    fund_obj = _FakeMiniFund(forecast_growth="N/A", estimate2_growth="2.00%", estimate2_date="2024-01-06")

    _titles, rows, _sortable = build_fund_table(fund_obj)

    assert "data-estimate-return=" not in rows[0][3]
    assert "data-estimate2-return=" not in rows[0][4]


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

    def search_code(self, is_return=False, cancel_event=None):
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


def test_build_fund_table_passes_cancel_event_to_search_code():
    cancel_event = MagicMock()
    fund_obj = _FakeMiniFund()
    fund_obj.search_code = MagicMock(return_value=[])

    build_fund_table(fund_obj, cancel_event=cancel_event)

    fund_obj.search_code.assert_called_once_with(True, cancel_event=cancel_event)
