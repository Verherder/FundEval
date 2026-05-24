# -*- coding: UTF-8 -*-
"""Tests for trading calendar utilities."""

import datetime

import pytest


class TestIsCnSseTradingDay:
    """Test is_cn_sse_trading_day() function."""

    def test_weekday_is_trading_day(self):
        """Test that weekdays are trading days."""
        from src.trading_calendar import is_cn_sse_trading_day

        # Monday (weekday 0)
        monday = datetime.date(2024, 1, 8)
        assert is_cn_sse_trading_day(monday) is True

    def test_friday_is_trading_day(self):
        """Test that Friday is a trading day."""
        from src.trading_calendar import is_cn_sse_trading_day

        # Friday (weekday 4)
        friday = datetime.date(2024, 1, 12)
        assert is_cn_sse_trading_day(friday) is True

    def test_saturday_is_not_trading_day(self):
        """Test that Saturday is not a trading day."""
        from src.trading_calendar import is_cn_sse_trading_day

        saturday = datetime.date(2024, 1, 13)
        assert is_cn_sse_trading_day(saturday) is False

    def test_sunday_is_not_trading_day(self):
        """Test that Sunday is not a trading day."""
        from src.trading_calendar import is_cn_sse_trading_day

        sunday = datetime.date(2024, 1, 14)
        assert is_cn_sse_trading_day(sunday) is False

    def test_boundary_cases(self):
        """Test boundary weekdays."""
        from src.trading_calendar import is_cn_sse_trading_day

        # Thursday Jan 11, 2024
        thursday = datetime.date(2024, 1, 11)
        assert is_cn_sse_trading_day(thursday) is True

        # Wednesday Jan 10, 2024
        wednesday = datetime.date(2024, 1, 10)
        assert is_cn_sse_trading_day(wednesday) is True


class TestIterCnSseTradingDays:
    """Test iter_cn_sse_trading_days() function."""

    def test_single_day_weekday(self):
        """Test iteration over a single weekday."""
        from src.trading_calendar import iter_cn_sse_trading_days

        # Wednesday Jan 10, 2024
        days = iter_cn_sse_trading_days(
            datetime.date(2024, 1, 10), datetime.date(2024, 1, 10)
        )
        assert len(days) == 1
        assert days[0] == datetime.date(2024, 1, 10)

    def test_single_day_weekend(self):
        """Test iteration over a single weekend day returns empty."""
        from src.trading_calendar import iter_cn_sse_trading_days

        saturday = datetime.date(2024, 1, 13)
        days = iter_cn_sse_trading_days(saturday, saturday)
        assert len(days) == 0

    def test_week_range(self):
        """Test iteration over a week (Mon-Sun)."""
        from src.trading_calendar import iter_cn_sse_trading_days

        # Jan 8 (Mon) to Jan 14 (Sun), 2024
        days = iter_cn_sse_trading_days(
            datetime.date(2024, 1, 8), datetime.date(2024, 1, 14)
        )
        # Should contain 5 weekdays
        assert len(days) == 5
        assert datetime.date(2024, 1, 8) in days  # Monday
        assert datetime.date(2024, 1, 12) in days  # Friday
        assert datetime.date(2024, 1, 13) not in days  # Saturday
        assert datetime.date(2024, 1, 14) not in days  # Sunday

    def test_invalid_range(self):
        """Test that invalid date range returns empty list."""
        from src.trading_calendar import iter_cn_sse_trading_days

        # Start > End
        days = iter_cn_sse_trading_days(
            datetime.date(2024, 1, 15), datetime.date(2024, 1, 10)
        )
        assert days == []

    def test_same_day_type_mismatch(self):
        """Test same date passed as start and end of different types."""
        from src.trading_calendar import iter_cn_sse_trading_days

        # Both start and end same weekday
        days = iter_cn_sse_trading_days(
            datetime.date(2024, 1, 10), datetime.date(2024, 1, 10)
        )
        assert len(days) == 1


class TestCnSseRangeHasTradingDay:
    """Test cn_sse_range_has_trading_day() function."""

    def test_range_with_trading_day(self):
        """Test that range containing weekdays returns True."""
        from src.trading_calendar import cn_sse_range_has_trading_day

        # Jan 8 (Mon) to Jan 14 (Sun)
        result = cn_sse_range_has_trading_day(
            datetime.date(2024, 1, 8), datetime.date(2024, 1, 14)
        )
        assert result is True

    def test_range_without_trading_day(self):
        """Test that range with only weekends returns False."""
        from src.trading_calendar import cn_sse_range_has_trading_day

        # Jan 13 (Sat) to Jan 14 (Sun)
        result = cn_sse_range_has_trading_day(
            datetime.date(2024, 1, 13), datetime.date(2024, 1, 14)
        )
        assert result is False

    def test_invalid_range(self):
        """Test that invalid range returns False."""
        from src.trading_calendar import cn_sse_range_has_trading_day

        result = cn_sse_range_has_trading_day(
            datetime.date(2024, 1, 15), datetime.date(2024, 1, 10)
        )
        assert result is False