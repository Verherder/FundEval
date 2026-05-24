# -*- coding: UTF-8 -*-
"""Fund repository — manages user_funds table operations."""


class FundRepo:
    """Repository for fund-related database operations."""

    def __init__(self, db):
        """Initialize with a Database instance.

        Args:
            db: Database instance.
        """
        self._db = db

    def get_user_funds(self, user_id):
        return self._db.get_user_funds(user_id)

    def save_user_funds(self, user_id, fund_map):
        return self._db.save_user_funds(user_id, fund_map)

    def update_fund_shares(self, user_id, fund_code, shares):
        return self._db.update_fund_shares(user_id, fund_code, shares)

    def add_fund(self, user_id, fund_code, fund_key, fund_name):
        return self._db.add_fund(user_id, fund_code, fund_key, fund_name)

    def delete_fund(self, user_id, fund_code):
        return self._db.delete_fund(user_id, fund_code)

    def update_chart_default(self, user_id, fund_code):
        return self._db.update_chart_default(user_id, fund_code)

    def update_fund_shares_delta(self, user_id, fund_code, shares_delta):
        return self._db.update_fund_shares_delta(user_id, fund_code, shares_delta)

    def update_fund_establishment_date(self, user_id, fund_code, establishment_date):
        return self._db.update_fund_establishment_date(user_id, fund_code, establishment_date)

    def recalculate_fund_shares_from_transactions(self, user_id, fund_code):
        return self._db.recalculate_fund_shares_from_transactions(user_id, fund_code)

    def get_chart_default_fund(self, user_id):
        return self._db.get_chart_default_fund(user_id)
