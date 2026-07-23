# -*- coding: UTF-8 -*-
"""Transaction repository — manages fund_transactions and fund_pending_buys tables."""


class TransactionRepo:
    """Repository for transaction-related database operations."""

    def __init__(self, db):
        """Initialize with a Database instance.

        Args:
            db: Database instance.
        """
        self._db = db

    def add_fund_transaction(self, user_id, fund_code, tx_type, amount, shares,
                             net_value=None, tx_time=None, fee=0.0, order_no=None):
        return self._db.add_fund_transaction(
            user_id, fund_code, tx_type, amount, shares, net_value, tx_time, fee, order_no)

    def add_pending_buy(self, user_id, fund_code, amount, effective_date):
        return self._db.add_pending_buy(user_id, fund_code, amount, effective_date)

    def get_pending_buys(self, user_id, fund_code=None):
        return self._db.get_pending_buys(user_id, fund_code)

    def mark_pending_buy_settled(self, user_id, pending_id, settled_tx_id, settled_net_value, settled_shares):
        return self._db.mark_pending_buy_settled(user_id, pending_id, settled_tx_id, settled_net_value, settled_shares)

    def get_fund_transactions(self, user_id, fund_code):
        return self._db.get_fund_transactions(user_id, fund_code)

    def get_all_fund_transactions(self, user_id):
        return self._db.get_all_fund_transactions(user_id)

    def exists_transaction_order_no(self, user_id, order_no):
        return self._db.exists_transaction_order_no(user_id, order_no)

    def update_fund_transaction_and_recalculate(self, user_id, fund_code, tx_id, tx_type,
                                                  amount, shares, net_value, tx_time, fee=0.0):
        return self._db.update_fund_transaction_and_recalculate(
            user_id, fund_code, tx_id, tx_type, amount, shares, net_value, tx_time, fee)

    def delete_fund_transaction_and_recalculate(self, user_id, fund_code, tx_id):
        return self._db.delete_fund_transaction_and_recalculate(user_id, fund_code, tx_id)

    def clear_fund_transactions_and_recalculate(self, user_id, fund_code):
        return self._db.clear_fund_transactions_and_recalculate(user_id, fund_code)

    def clear_all_fund_transactions_and_recalculate(self, user_id):
        return self._db.clear_all_fund_transactions_and_recalculate(user_id)
