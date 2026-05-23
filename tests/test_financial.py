# -*- coding: UTF-8 -*-
"""Tests for financial utilities (XIRR/XNPV).

These tests will be validated against the actual implementation in src/fund.py
(phase 6迁移到 src/utils/financial.py).
"""

from datetime import date

import pytest


class TestXNPV:
    """Test xnpv() function."""

    def test_xnpv_basic(self):
        """Test basic XNPV calculation."""
        from src.fund import xnpv

        rate = 0.05
        cashflows = [
            (date(2024, 1, 1), -1000.0),
            (date(2024, 12, 31), 1050.0),
        ]
        result = xnpv(rate, cashflows)
        assert isinstance(result, float)

    def test_xnpv_negative_rate(self):
        """Test XNPV with negative rate."""
        from src.fund import xnpv

        rate = -0.5
        cashflows = [
            (date(2024, 1, 1), -1000.0),
            (date(2024, 12, 31), 1500.0),
        ]
        result = xnpv(rate, cashflows)
        assert isinstance(result, float)

    def test_xnpv_extreme_negative_rate(self):
        """Test XNPV returns inf when rate <= -0.999999."""
        from src.fund import xnpv

        rate = -0.999999
        cashflows = [
            (date(2024, 1, 1), -1000.0),
            (date(2024, 12, 31), 1500.0),
        ]
        result = xnpv(rate, cashflows)
        assert result == float("inf")

    def test_xnpv_zero_rate(self):
        """Test XNPV with zero rate (simple sum)."""
        from src.fund import xnpv

        rate = 0.0
        cashflows = [
            (date(2024, 1, 1), -1000.0),
            (date(2024, 12, 31), 1000.0),
        ]
        result = xnpv(rate, cashflows)
        assert result == 0.0

    def test_xnpv_empty(self):
        """Test XNPV with empty cashflows (edge case)."""
        from src.fund import xnpv

        rate = 0.05
        cashflows = []
        # May raise or return specific value - behavior depends on implementation
        try:
            result = xnpv(rate, cashflows)
            assert isinstance(result, float)
        except (IndexError, ValueError):
            pass  # Acceptable behavior for empty input


class TestSolveXIRR:
    """Test solve_xirr() function."""

    def test_solve_xirr_basic(self):
        """Test basic XIRR calculation."""
        from src.fund import solve_xirr

        cashflows = [
            (date(2024, 1, 1), -1000.0),
            (date(2024, 12, 31), 1050.0),
        ]
        result = solve_xirr(cashflows)
        assert result is not None
        assert isinstance(result, float)
        # Approximately 5% annual return
        assert 0.04 < result < 0.06

    def test_solve_xirr_single_cashflow(self):
        """Test XIRR returns None with single cashflow."""
        from src.fund import solve_xirr

        cashflows = [(date(2024, 1, 1), -1000.0)]
        result = solve_xirr(cashflows)
        assert result is None

    def test_solve_xirr_no_negative(self):
        """Test XIRR returns None when no negative cashflow (no investment)."""
        from src.fund import solve_xirr

        cashflows = [
            (date(2024, 1, 1), 1000.0),
            (date(2024, 12, 31), 1100.0),
        ]
        result = solve_xirr(cashflows)
        assert result is None

    def test_solve_xirr_no_positive(self):
        """Test XIRR returns None when no positive cashflow (no return)."""
        from src.fund import solve_xirr

        cashflows = [
            (date(2024, 1, 1), -1000.0),
            (date(2024, 12, 31), -500.0),
        ]
        result = solve_xirr(cashflows)
        assert result is None

    def test_solve_xirr_multiple_cashflows(self):
        """Test XIRR with multiple cashflows."""
        from src.fund import solve_xirr

        cashflows = [
            (date(2024, 1, 1), -5000.0),
            (date(2024, 3, 1), -2000.0),
            (date(2024, 9, 1), 3000.0),
            (date(2024, 12, 31), 5000.0),
        ]
        result = solve_xirr(cashflows)
        assert result is not None
        assert isinstance(result, float)
        # Reasonable range for mixed cash flows
        assert -0.5 < result < 10.0

    def test_solve_xirr_zero_amt(self):
        """Test XIRR returns None when all zero amounts."""
        from src.fund import solve_xirr

        cashflows = [
            (date(2024, 1, 1), 0.0),
            (date(2024, 12, 31), 0.0),
        ]
        result = solve_xirr(cashflows)
        assert result is None


class TestXIRRIntegration:
    """Integration tests for XIRR/XNPV pair."""

    def test_xnpv_solve_xirr_roundtrip(self):
        """Test that XIRR produced by solve_xirr produces NPV ≈ 0 via xnpv."""
        from src.fund import solve_xirr, xnpv

        cashflows = [
            (date(2024, 1, 1), -1000.0),
            (date(2024, 6, 30), 300.0),
            (date(2024, 12, 31), 800.0),
        ]

        rate = solve_xirr(cashflows)
        if rate is not None:
            npv = xnpv(rate, cashflows)
            # NPV at IRR should be approximately 0
            assert abs(npv) < 1.0