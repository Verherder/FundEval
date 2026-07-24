# -*- coding: UTF-8 -*-
"""Regression tests for fund chart transaction markers."""

import datetime
from unittest.mock import MagicMock

from src.services.chart_service import ChartService


def test_performance_chart_uses_transaction_nav_to_render_missing_trade_date_marker():
    nav_repo = _FakeNavRepo({
        "2026-05-14": 1.6919,
        "2026-05-25": 1.6457,
    })
    transaction_repo = MagicMock()
    transaction_repo.get_fund_transactions.return_value = [{
        "id": 3510,
        "tx_type": "buy",
        "amount": 1000.0,
        "shares": 604.34,
        "net_value": 1.6547,
        "tx_time": "2026-05-15 15:00:00",
    }]

    fund_repo = MagicMock()
    fund_repo.get_visible_funds.return_value = {
        "012842": {
            "fund_key": "KEY012842",
            "fund_name": "易方达中证军工指数(LOF)C",
            "establishment_date": "2026-05-14",
        }
    }

    nav_service = MagicMock()
    nav_service.parse_iso_date.side_effect = lambda text: datetime.date.fromisoformat(text) if text else None
    nav_service.get_local_fund_establishment_date.return_value = datetime.date(2026, 5, 14)
    nav_service.ensure_nav_history_from_establishment.side_effect = lambda *_args, **_kwargs: dict(nav_repo.nav_map)
    nav_service.ensure_index_nav_history.return_value = {}
    nav_service.ensure_fund_nav_by_date.side_effect = lambda _user_id, _fund_code, nav_date, fallback_nav=None, fallback_source='fallback': nav_repo.ensure_nav_by_date(nav_date, fallback_nav, fallback_source)

    service = ChartService(
        db=None,
        fund_repo=fund_repo,
        nav_repo=nav_repo,
        transaction_repo=transaction_repo,
        nav_service=nav_service,
        get_lan_fund_fn=lambda **_kwargs: None,
    )

    result = service.get_fund_performance_chart_data(1, "012842", "SINCE_ESTABLISHMENT")
    chart_data = result["chart_data"]

    assert "2026-05-15" in chart_data["labels"]
    assert nav_repo.nav_map["2026-05-15"] == 1.6547
    assert chart_data["trade_markers"] == [{
        "type": "buy",
        "marker_type": "buy",
        "x": "2026-05-15",
        "y": chart_data["growth"][chart_data["labels"].index("2026-05-15")],
        "amount": 1000.0,
        "shares": 604.34,
        "net_value": 1.6547,
        "tx_time": "2026-05-15 15:00:00",
    }]


class _FakeNavRepo:
    def __init__(self, nav_map):
        self.nav_map = dict(nav_map)

    def get_fund_nav_by_date(self, _fund_code, nav_date):
        return self.nav_map.get(nav_date)

    def upsert_fund_nav_history(self, _fund_code, nav_date, nav_value, source=None):
        assert source == "transaction_nav"
        self.nav_map[nav_date] = nav_value
        return True

    def ensure_nav_by_date(self, nav_date, fallback_nav=None, fallback_source='fallback'):
        if nav_date in self.nav_map:
            return self.nav_map[nav_date]
        assert fallback_source == "transaction_nav"
        if fallback_nav is None:
            return None
        self.nav_map[nav_date] = fallback_nav
        return fallback_nav

    def get_fund_nav_history_range(self, _fund_code, start_date=None, end_date=None):
        result = {}
        for nav_date, nav_value in self.nav_map.items():
            if start_date and nav_date < start_date:
                continue
            if end_date and nav_date > end_date:
                continue
            result[nav_date] = nav_value
        return result
