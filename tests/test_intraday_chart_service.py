from unittest.mock import MagicMock

from src.services.intraday_chart_service import IntradayChartService


def test_latest_estimate_and_curve_use_separate_provider_methods():
    fund_repo = MagicMock()
    fund_repo.get_user_funds.return_value = {
        "260101": {"fund_key": "KEY260101", "fund_name": "测试基金"}
    }
    provider = MagicMock()
    provider.fetch_latest_intraday_estimate.return_value = {
        "growth": 1.2, "net_value": 1.5, "date": "2026-07-18", "time": "14:30"
    }
    provider.fetch_intraday_curve.return_value = [
        {"growth": 1.0, "net_value": 1.49, "date": "2026-07-18", "time": "14:29"},
        {"growth": 1.2, "net_value": 1.5, "date": "2026-07-18", "time": "14:30"},
    ]
    service = IntradayChartService(fund_repo, lambda **_kwargs: provider)

    latest = service.get_latest_estimate(1, "260101")
    provider.fetch_intraday_curve.assert_not_called()
    curve = service.get_curve(1, "260101")

    assert latest["estimate"]["growth"] == 1.2
    assert curve["chart_data"]["labels"] == ["14:29", "14:30"]
    provider.fetch_latest_intraday_estimate.assert_called_once_with("KEY260101")
    provider.fetch_intraday_curve.assert_called_once_with("KEY260101")


def test_unknown_fund_returns_none_without_provider_request():
    fund_repo = MagicMock()
    fund_repo.get_user_funds.return_value = {}
    provider_factory = MagicMock()
    service = IntradayChartService(fund_repo, provider_factory)

    assert service.get_latest_estimate(1, "000000") is None
    assert service.get_curve(1, "000000") is None
    provider_factory.assert_not_called()
