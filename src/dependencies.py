# -*- coding: UTF-8 -*-
"""Dependency injection container for FundEval services.

Module-level singletons initialized once by create_app(), consumed by blueprints.
Each blueprint imports accessor functions at module level; the actual service
instances are set by init_dependencies() before the first request.
"""

from flask import g


_db = None
_user_repo = None
_fund_repo = None
_transaction_repo = None
_nav_repo = None
_tx_service = None
_import_service = None
_nav_service = None
_chart_service = None
_fund_service = None
_market_service = None


def get_lan_fund(user_id=None):
    """Return per-request MiniFund singleton stored on Flask g."""
    if not hasattr(g, "_lan_fund"):
        import src.fund as fund
        g._lan_fund = fund.MiniFund(user_id=user_id, db=_db)
    return g._lan_fund


def init_dependencies(db):
    """Initialize all repos and services once at app startup."""
    global _db, _user_repo, _fund_repo, _transaction_repo, _nav_repo
    global _tx_service, _import_service, _nav_service, _chart_service, _fund_service, _market_service

    from src.repositories.user_repo import UserRepo
    from src.repositories.fund_repo import FundRepo
    from src.repositories.transaction_repo import TransactionRepo
    from src.repositories.nav_repo import NavRepo
    from src.services.transaction_service import TransactionService
    from src.services.import_service import ImportService
    from src.services.nav_service import NavService
    from src.services.chart_service import ChartService
    from src.services.fund_service import FundService
    from src.services.market_service import MarketService

    _db = db
    _user_repo = UserRepo(db)
    _fund_repo = FundRepo(db)
    _transaction_repo = TransactionRepo(db)
    _nav_repo = NavRepo(db)

    _nav_service = NavService(db, _fund_repo, _nav_repo, get_lan_fund)
    _tx_service = TransactionService(_fund_repo, _transaction_repo, _nav_repo, get_lan_fund, _nav_service)
    _import_service = ImportService(_fund_repo, _transaction_repo, _nav_repo, get_lan_fund, _tx_service)
    _chart_service = ChartService(db, _fund_repo, _nav_repo, _transaction_repo, _nav_service, get_lan_fund)
    _fund_service = FundService(db, _fund_repo, _transaction_repo, get_lan_fund, _chart_service)
    _market_service = MarketService(get_lan_fund)


# ------------------------------------------------------------------
# Accessor functions — call these inside route handlers (request time).
# ------------------------------------------------------------------

def get_db():
    return _db


def get_user_repo():
    return _user_repo


def get_fund_repo():
    return _fund_repo


def get_transaction_repo():
    return _transaction_repo


def get_nav_repo():
    return _nav_repo


def get_tx_service():
    return _tx_service


def get_import_service():
    return _import_service


def get_nav_service():
    return _nav_service


def get_chart_service():
    return _chart_service


def get_fund_service():
    return _fund_service


def get_market_service():
    return _market_service
