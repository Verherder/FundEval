# -*- coding: UTF-8 -*-
"""NAV repository — manages fund_nav_history, fund_performance_curve_cache, and index_nav_history tables."""


class NavRepo:
    """Repository for NAV and performance-curve database operations."""

    def __init__(self, db):
        """Initialize with a Database instance.

        Args:
            db: Database instance.
        """
        self._db = db

    def get_fund_nav_by_date(self, fund_code, nav_date):
        return self._db.get_fund_nav_by_date(fund_code, nav_date)

    def get_prev_fund_nav(self, fund_code, before_date):
        return self._db.get_prev_fund_nav(fund_code, before_date)

    def upsert_fund_nav_history(self, fund_code, nav_date, nav_value, source=None):
        return self._db.upsert_fund_nav_history(fund_code, nav_date, nav_value, source)

    def get_fund_nav_history_range(self, fund_code, start_date=None, end_date=None):
        return self._db.get_fund_nav_history_range(fund_code, start_date, end_date)

    def get_fund_performance_curve_cache(self, fund_code, date_interval, start_date=None, end_date=None):
        return self._db.get_fund_performance_curve_cache(fund_code, date_interval, start_date, end_date)

    def bulk_upsert_fund_performance_curve_cache(self, fund_code, date_interval, curve_points, source=None):
        return self._db.bulk_upsert_fund_performance_curve_cache(fund_code, date_interval, curve_points, source)

    def bulk_upsert_index_nav_history(self, index_code, records):
        return self._db.bulk_upsert_index_nav_history(index_code, records)

    def get_index_nav_history_range(self, index_code, start_date=None, end_date=None):
        return self._db.get_index_nav_history_range(index_code, start_date, end_date)
