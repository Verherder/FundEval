from src.services.metrics import compute_nav_momentum


def test_nav_momentum_calculates_recent_growth_and_positive_streak():
    result = compute_nav_momentum({
        "2026-07-13": 1.00,
        "2026-07-14": 1.02,
        "2026-07-15": 1.01,
        "2026-07-16": 1.03,
        "2026-07-17": 1.05,
    })

    assert result == {
        "up_days": 3,
        "change_days": 4,
        "period_growth": "5.00%",
        "consecutive_count": 2,
        "consecutive_growth": "3.96%",
    }


def test_nav_momentum_uses_negative_count_for_decline_streak():
    result = compute_nav_momentum({
        "2026-07-14": 1.00,
        "2026-07-15": 1.05,
        "2026-07-16": 1.03,
        "2026-07-17": 1.00,
    })

    assert result["up_days"] == 1
    assert result["change_days"] == 3
    assert result["consecutive_count"] == -2
    assert result["consecutive_growth"] == "-4.76%"


def test_nav_momentum_limits_window_to_thirty_changes():
    nav_map = {
        f"2026-06-{index:02d}": 1 + index / 100
        for index in range(1, 31)
    }
    nav_map["2026-07-01"] = 1.31
    nav_map["2026-07-02"] = 1.32

    result = compute_nav_momentum(nav_map)

    assert result["change_days"] == 30
    assert result["up_days"] == 30


def test_nav_momentum_returns_na_with_insufficient_local_data():
    result = compute_nav_momentum({"2026-07-17": 1.0})

    assert result["consecutive_count"] == "N/A"
    assert result["period_growth"] == "N/A"
