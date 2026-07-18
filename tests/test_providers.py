import datetime
from unittest.mock import MagicMock

import pytest

from src.providers import Fund123Client, FundGzClient


URLS = {
    "fund123_origin": "https://fund123.test",
    "fund123_fund_page": "https://fund123.test/fund",
    "fund123_intraday_api": "https://fund123.test/intraday",
    "fundgz_js_tpl": "https://fundgz.test/{fund}.js",
}


def test_fund123_latest_estimate_returns_only_last_point():
    quote_time = datetime.datetime(2026, 7, 18, 14, 30).timestamp() * 1000
    request_json = MagicMock(return_value=(MagicMock(), {
        "success": True,
        "list": [
            {"time": quote_time - 60000, "forecastGrowth": "-0.01", "forecastNetValue": "1.48"},
            {"time": quote_time, "forecastGrowth": "-0.0234", "forecastNetValue": "1.46"},
        ],
    }))
    client = Fund123Client(MagicMock(), request_json, URLS, lambda: "csrf-token")

    assert client.fetch_latest_estimate("KEY260101") == {
        "growth": -2.34,
        "net_value": 1.46,
        "date": "2026-07-18",
        "time": "14:30",
    }
    assert request_json.call_args.kwargs["params"] == {"_csrf": "csrf-token"}


def test_fund123_intraday_curve_preserves_all_points():
    quote_time = datetime.datetime(2026, 7, 18, 14, 30).timestamp() * 1000
    request_json = MagicMock(return_value=(MagicMock(), {
        "success": True,
        "list": [
            {"time": quote_time - 60000, "forecastGrowth": "-0.01", "forecastNetValue": "1.48"},
            {"time": quote_time, "forecastGrowth": "-0.0234", "forecastNetValue": "1.46"},
        ],
    }))
    client = Fund123Client(MagicMock(), request_json, URLS, lambda: "csrf-token")

    points = client.fetch_intraday_curve("KEY260101")

    assert len(points) == 2
    assert points[-1]["growth"] == -2.34
    assert points[-1]["net_value"] == 1.46


def test_fundgz_parses_jsonp_estimate():
    response = MagicMock(
        status_code=200,
        text='jsonpgz({"gszzl":"1.23","gztime":"2026-07-17 15:00"});',
    )
    client = FundGzClient(MagicMock(return_value=response), URLS)

    assert client.fetch_latest_estimate("260101") == {
        "growth": 1.23,
        "date": "2026-07-17",
        "time": "15:00",
        "quote_time": "2026-07-17 15:00",
    }


def test_fundgz_rejects_invalid_jsonp():
    response = MagicMock(status_code=403, text="blocked")
    client = FundGzClient(MagicMock(return_value=response), URLS)

    with pytest.raises(ValueError, match="响应格式异常"):
        client.fetch_latest_estimate("260101")
