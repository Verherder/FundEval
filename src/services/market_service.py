# -*- coding: UTF-8 -*-
"""Market service — sectors, sector funds, and fund table data."""

import requests

from src.market_data import (
    fetch_bk,
    fetch_select_fund,
)


class MarketService:
    """Service for market data operations.

    Args:
        get_lan_fund_fn: Callable returning a MiniFund instance for the current request.
    """

    def __init__(self, get_lan_fund_fn):
        self._get_lan_fund = get_lan_fund_fn

    # ------------------------------------------------------------------
    # Tab data
    # ------------------------------------------------------------------

    def get_bk_data_raw(self, user_id=None):
        return fetch_bk(is_return=True)

    def build_fund_table(self, user_id, cancel_event=None):
        """Return (titles, rows, sortable_columns) for fund table."""
        return self._get_lan_fund(user_id=user_id).build_fund_table(cancel_event=cancel_event)

    def get_select_fund(self, user_id=None, bk_id=None):
        return fetch_select_fund(bk_id=bk_id, is_return=True)

    def get_major_categories(self, user_id=None):
        from src.data.sectors import MAJOR_CATEGORIES

        return MAJOR_CATEGORIES

    # ------------------------------------------------------------------
    # External API data
    # ------------------------------------------------------------------

    @staticmethod
    def fetch_sectors():
        """Fetch sector/board data from Eastmoney API.

        Returns:
            List of sector dicts sorted by change descending.
        """
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "cb": "",
            "fid": "f62",
            "po": "1",
            "pz": "100",
            "pn": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "ut": "8dec03ba335b81bf4ebdf7b29ec27d15",
            "fs": "m:90 t:2",
            "fields": "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124,f1,f13",
        }
        response = requests.get(url, params=params, timeout=10, verify=False)
        data = response.json().get("data")
        if not data:
            return []

        sectors = []
        for bk in data.get("diff", []):
            sectors.append({
                "code": bk["f12"],
                "name": bk["f14"],
                "change": str(bk["f3"]) + "%",
                "main_inflow": str(round(bk["f62"] / 100000000, 2)) + "亿",
                "main_inflow_pct": str(round(bk["f184"], 2)) + "%",
                "small_inflow": str(round(bk["f84"] / 100000000, 2)) + "亿",
                "small_inflow_pct": str(round(bk["f87"], 2)) + "%",
            })

        sectors.sort(
            key=lambda x: float(x["change"].replace("%", "")) if x["main_inflow_pct"] != "N/A" else -99,
            reverse=True,
        )
        return sectors
