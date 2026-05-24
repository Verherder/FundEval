# -*- coding: UTF-8 -*-
"""Financial calculation utilities: XNPV and XIRR."""


def xnpv(rate, cashflows):
    """Calculate Net Present Value for irregular cashflows.

    Args:
        rate: Annual discount rate (0.05 = 5%).
        cashflows: List of (datetime/date, amount) tuples sorted by date.

    Returns:
        Present value (float). Returns inf for rate <= -0.999999.
    """
    if rate <= -0.999999:
        return float("inf")
    t0 = cashflows[0][0]
    total_value = 0.0
    for tx_date, amount in cashflows:
        days = (tx_date - t0).total_seconds() / 86400
        total_value += amount / ((1 + rate) ** (days / 365.0))
    return total_value


def solve_xirr(cashflows):
    """Calculate Internal Rate of Return for irregular cashflows via bisection.

    Args:
        cashflows: List of (datetime/date, amount) tuples sorted by date.

    Returns:
        Annual IRR as float, or None if no valid IRR exists.
    """
    if len(cashflows) < 2:
        return None
    has_positive = any(amount > 0 for _, amount in cashflows)
    has_negative = any(amount < 0 for _, amount in cashflows)
    if not (has_positive and has_negative):
        return None

    low, high = -0.9999, 10.0
    try:
        f_low = xnpv(low, cashflows)
        f_high = xnpv(high, cashflows)
    except Exception:
        return None

    expand_count = 0
    while f_low * f_high > 0 and expand_count < 20:
        high *= 2
        try:
            f_high = xnpv(high, cashflows)
        except Exception:
            return None
        expand_count += 1

    if f_low * f_high > 0:
        return None

    for _ in range(100):
        mid = (low + high) / 2
        f_mid = xnpv(mid, cashflows)
        if abs(f_mid) < 1e-7:
            return mid
        if f_low * f_mid <= 0:
            high = mid
            f_high = f_mid
        else:
            low = mid
            f_low = f_mid
    return (low + high) / 2
