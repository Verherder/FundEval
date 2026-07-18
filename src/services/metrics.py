# -*- coding: UTF-8 -*-
"""Holding metrics calculation for fund positions."""

import datetime
import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from src.utils.financial import solve_xirr


def parse_growth_percent(value):
    """Extract numeric percentage from a display string like '+2.35%'."""
    if value in (None, "", "N/A", "--", "---"):
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?", str(value))
    return float(match.group()) if match else None


def format_diff_value(value):
    """Format a diff value, stripping trailing zeros. Returns '0' for zero."""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0", "+0") else text


def safe_float(value, default=0.0):
    """Convert value to float, returning default on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    """Convert value to int, returning default on failure."""
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(default)
        except (TypeError, ValueError):
            return None


def compute_nav_momentum(nav_map, max_changes=30):
    """Compute recent up-day ratio and the latest consecutive NAV direction."""
    valid_points = []
    for nav_date, nav_value in sorted((nav_map or {}).items()):
        value = safe_float(nav_value, None)
        if value is not None and value > 0:
            valid_points.append((str(nav_date), value))

    points = valid_points[-(max_changes + 1):]
    if len(points) < 2:
        return {
            "up_days": "N/A",
            "change_days": 0,
            "period_growth": "N/A",
            "consecutive_count": "N/A",
            "consecutive_growth": "N/A",
        }

    changes = []
    for index in range(1, len(points)):
        previous = points[index - 1][1]
        current = points[index][1]
        direction = 1 if current > previous else (-1 if current < previous else 0)
        changes.append(direction)

    up_days = sum(1 for direction in changes if direction > 0)
    period_growth = (points[-1][1] / points[0][1] - 1.0) * 100.0

    latest_direction = changes[-1]
    if latest_direction == 0:
        consecutive_count = 0
        consecutive_growth = 0.0
    else:
        streak_length = 1
        for direction in reversed(changes[:-1]):
            if direction != latest_direction:
                break
            streak_length += 1
        streak_start_index = len(points) - streak_length - 1
        consecutive_growth = (
            points[-1][1] / points[streak_start_index][1] - 1.0
        ) * 100.0
        consecutive_count = streak_length if latest_direction > 0 else -streak_length

    return {
        "up_days": up_days,
        "change_days": len(changes),
        "period_growth": f"{period_growth:.2f}%",
        "consecutive_count": consecutive_count,
        "consecutive_growth": f"{consecutive_growth:.2f}%",
    }


def quantize_shares_2(value):
    """Round shares to 2 decimal places."""
    try:
        return float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    except Exception:
        return 0.0


def parse_tx_datetime(tx_time):
    """Parse a transaction timestamp string into a datetime object."""
    text = str(tx_time or '').strip()
    if not text:
        return None
    try:
        return datetime.datetime.fromisoformat(text.replace(' ', 'T'))
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(text, fmt)
        except Exception:
            continue
    return None


def format_pct_value(value):
    """Format a percentage value with colored HTML span."""
    if value is None:
        return "--"
    rounded_value = round(float(value), 2)
    if abs(rounded_value) < 1e-10:
        color = "var(--text-main)"
        text = "0.00%"
    elif rounded_value > 0:
        color = "var(--up-color)"
        text = f"{rounded_value:.2f}%"
    else:
        color = "var(--down-color)"
        text = f"{rounded_value:.2f}%"
    return f"<span style='color:{color} !important;font-weight:600;'>{text}</span>"


def format_money_value(value):
    """Format a monetary value with colored HTML span."""
    if value is None:
        return "--"
    rounded_value = round(float(value), 2)
    if abs(rounded_value) < 1e-10:
        color = "var(--text-main)"
    elif rounded_value > 0:
        color = "var(--up-color)"
    else:
        color = "var(--down-color)"
    return f"<span style='color:{color} !important;font-weight:600;'>¥{rounded_value:,.2f}</span>"


def compute_holding_metrics(db, user_id, cache_map, fund_code, current_shares, current_net_value):
    """Compute holding return, annual return, holding gain, and effective shares.

    Args:
        db: Database connection with get_fund_transactions() method.
        user_id: Current user ID.
        cache_map: Fund cache dict (code -> {shares, ...}).
        fund_code: Fund code to compute metrics for.
        current_shares: Current number of shares held.
        current_net_value: Current unit net value.

    Returns:
        Tuple of (holding_return_pct, annual_return_pct, holding_gain, effective_shares),
        all None/0 if metrics can't be computed.
    """
    share_eps = 1e-4
    if not db or user_id is None or current_shares <= 0 or current_net_value <= 0:
        return None, None, None, current_shares

    transactions = db.get_fund_transactions(user_id, fund_code)
    if not transactions:
        return None, None, None, current_shares

    running_shares = 0.0
    cycle_start = 0
    for index, tx in enumerate(transactions):
        tx_shares = safe_float(tx.get('shares'), 0.0)
        tx_type = str(tx.get('tx_type', '')).lower()
        if tx_type == 'buy':
            running_shares += tx_shares
        elif tx_type == 'sell':
            running_shares -= tx_shares

        if abs(running_shares) <= share_eps:
            running_shares = 0.0
            cycle_start = index + 1

    cycle_transactions = transactions[cycle_start:]
    if not cycle_transactions:
        return None, None, None, current_shares

    tx_remaining_shares = 0.0
    tx_remaining_cost = 0.0
    cumulative_dividend = 0.0
    cashflows = []

    for tx in cycle_transactions:
        tx_type = str(tx.get('tx_type', '')).lower()
        tx_shares = safe_float(tx.get('shares'), 0.0)
        tx_amount = safe_float(tx.get('amount'), 0.0)
        tx_net_value = safe_float(tx.get('net_value'), 0.0)
        try:
            tx_date = datetime.datetime.fromisoformat(str(tx.get('tx_time')).replace(' ', 'T'))
        except Exception:
            try:
                tx_date = datetime.datetime.strptime(str(tx.get('tx_time')), "%Y-%m-%d %H:%M:%S")
            except Exception:
                tx_date = datetime.datetime.now()

        if tx_type == 'buy' and tx_shares > 0:
            buy_cost = tx_amount if tx_amount > 0 else tx_shares * tx_net_value
            tx_remaining_shares += tx_shares
            tx_remaining_cost += buy_cost
            cashflows.append((tx_date, -buy_cost))
        elif tx_type == 'sell' and tx_shares > 0 and tx_remaining_shares > share_eps:
            avg_cost_before = (tx_remaining_cost / tx_remaining_shares) if tx_remaining_shares > share_eps else 0.0
            sell_shares = min(tx_shares, tx_remaining_shares)
            tx_remaining_cost -= sell_shares * avg_cost_before
            tx_remaining_shares -= sell_shares
            if tx_remaining_shares <= share_eps:
                tx_remaining_shares = 0.0
                tx_remaining_cost = 0.0
            proceeds = tx_amount if tx_amount > 0 else tx_shares * tx_net_value
            cashflows.append((tx_date, proceeds))
        elif tx_type == 'dividend' and tx_amount > 0:
            cumulative_dividend += tx_amount
            cashflows.append((tx_date, tx_amount))

    if tx_remaining_shares <= share_eps:
        return None, None, None, current_shares

    tx_remaining_shares = float(Decimal(str(tx_remaining_shares)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    effective_shares = current_shares
    if abs(tx_remaining_shares - current_shares) > share_eps:
        effective_shares = tx_remaining_shares

    avg_unit_cost = (tx_remaining_cost / tx_remaining_shares) if tx_remaining_shares > share_eps else 0.0
    holding_cost = effective_shares * avg_unit_cost
    current_value = effective_shares * current_net_value
    holding_gain = (current_value - holding_cost) + cumulative_dividend
    holding_return = (holding_gain / holding_cost * 100) if holding_cost > 0 else None

    cashflows.append((datetime.datetime.now(), current_value))
    annual_rate = solve_xirr(cashflows)
    annual_return = annual_rate * 100 if annual_rate is not None else None
    return holding_return, annual_return, holding_gain, effective_shares


def build_clear_cycles(transactions):
    """Build clear-cycle summaries from a fund's transaction history.

    Each clear cycle represents a full buy-then-sell round trip. Returns a list
    of dicts with period_start, period_end, cycle_profit, cycle_return_pct,
    and annual_return_pct keys.
    """
    share_eps = 1e-4
    running_shares = 0.0
    cycle_start_dt = None
    cycle_total_buy = 0.0
    cycle_total_sell = 0.0
    cycle_cashflows = []
    clear_cycles = []

    for tx in transactions:
        tx_type = str(tx.get('tx_type', '')).strip().lower()
        tx_shares = safe_float(tx.get('shares', 0), 0.0) or 0.0
        tx_amount = safe_float(tx.get('amount', 0), 0.0) or 0.0
        tx_net_value = safe_float(tx.get('net_value', 0), 0.0) or 0.0
        tx_fee = safe_float(tx.get('fee', 0), 0.0) or 0.0
        tx_dt = parse_tx_datetime(tx.get('tx_time'))
        if tx_dt is None:
            continue

        gross_amount = tx_amount if tx_amount > 0 else (tx_shares * tx_net_value)
        if tx_type == 'sell' and tx_fee > 0:
            gross_amount += tx_fee
        effective_amount = gross_amount

        if tx_type == 'buy' and tx_shares > 0:
            if running_shares <= share_eps and cycle_start_dt is None:
                cycle_start_dt = tx_dt
                cycle_total_buy = 0.0
                cycle_total_sell = 0.0
                cycle_cashflows = []
            running_shares += tx_shares
            cycle_total_buy += effective_amount
            cycle_cashflows.append((tx_dt, -effective_amount))
        elif tx_type == 'sell' and tx_shares > 0:
            if running_shares <= share_eps:
                continue
            sell_shares = min(tx_shares, running_shares)
            if sell_shares <= 0:
                continue
            running_shares -= sell_shares
            scale = (sell_shares / tx_shares) if tx_shares > 0 else 0.0
            proceeds = effective_amount * scale
            cycle_total_sell += proceeds
            cycle_cashflows.append((tx_dt, proceeds))

            if running_shares <= share_eps:
                running_shares = 0.0
                period_start = cycle_start_dt or tx_dt
                period_end = tx_dt
                cycle_profit = cycle_total_sell - cycle_total_buy
                cycle_return_pct = (cycle_profit / cycle_total_buy * 100.0) if cycle_total_buy > 0 else None
                annual_rate = solve_xirr(cycle_cashflows)
                annual_return_pct = (annual_rate * 100.0) if annual_rate is not None else None
                clear_cycles.append({
                    'clear_tx_id': safe_int(tx.get('id', 0), 0),
                    'period_start': period_start.strftime('%Y-%m-%d'),
                    'period_end': period_end.strftime('%Y-%m-%d'),
                    'cycle_profit': round(cycle_profit, 2),
                    'cycle_return_pct': round(cycle_return_pct, 2) if cycle_return_pct is not None else None,
                    'annual_return_pct': round(annual_return_pct, 2) if annual_return_pct is not None else None,
                })
                cycle_start_dt = None
                cycle_total_buy = 0.0
                cycle_total_sell = 0.0
                cycle_cashflows = []
        elif tx_type == 'dividend' and tx_amount > 0 and running_shares > share_eps:
            cycle_total_sell += tx_amount
            cycle_cashflows.append((tx_dt, tx_amount))

    return clear_cycles


def calculate_holding_shares_by_time(transaction_repo, user_id, fund_code, up_to_dt=None, fallback_shares=0.0):
    """Recalculate available shares from transaction history up to a given datetime.

    When up_to_dt is provided, only transactions at or before that time are counted,
    so sell validation doesn't include "future" buys.
    """
    transactions = transaction_repo.get_fund_transactions(user_id, fund_code)
    if not transactions:
        return float(fallback_shares or 0.0) if up_to_dt is None else 0.0

    holding = 0.0
    share_eps = 1e-8

    for tx in transactions:
        tx_dt = parse_tx_datetime(tx.get('tx_time'))
        if up_to_dt is not None:
            if tx_dt is None or tx_dt > up_to_dt:
                continue

        tx_type = str(tx.get('tx_type', '')).strip().lower()
        tx_shares = safe_float(tx.get('shares', 0), 0.0) or 0.0
        if tx_shares <= 0:
            continue

        if tx_type == 'buy':
            holding += tx_shares
        elif tx_type == 'sell':
            holding -= tx_shares

        if holding < share_eps:
            holding = 0.0

    return holding
