# -*- coding: UTF-8 -*-
"""Standalone fund table and position summary builders extracted from MiniFund."""

import datetime
import re

from src.services.metrics import (
    compute_holding_metrics,
    format_diff_value,
    format_money_value,
    format_pct_value,
    parse_growth_percent,
    safe_float,
)


def _parse_date_text(date_text):
    text = str(date_text or '').strip()
    if not text:
        return None
    try:
        if re.match(r"^\d{2}-\d{2}$", text):
            text = f"{datetime.datetime.now().year}-{text}"
        if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
            return datetime.datetime.strptime(text, "%Y-%m-%d").date()
    except Exception:
        return None
    return None


def _get_prev_trading_nav(lan_fund, fund_code, target_date):
    if not target_date or not lan_fund.db or not lan_fund.user_id:
        return None
    try:
        from src.trading_calendar import iter_cn_sse_trading_days
        trading_days = iter_cn_sse_trading_days(target_date - datetime.timedelta(days=7), target_date)
    except Exception:
        return None
    previous_days = [day for day in trading_days if day < target_date]
    if not previous_days:
        return None
    prev_date = previous_days[-1].strftime("%Y-%m-%d")
    prev_nav = lan_fund.nav_repo.get_fund_nav_by_date(fund_code, prev_date)
    if prev_nav is not None:
        return prev_nav

    fetch_history = getattr(lan_fund, '_fetch_history_nav_map_by_date_range', None)
    if not callable(fetch_history):
        return None

    fund_data = lan_fund.CACHE_MAP.get(fund_code, {}) if isinstance(lan_fund.CACHE_MAP, dict) else {}
    fund_key = fund_data.get('fund_key') if isinstance(fund_data, dict) else None
    if not fund_key:
        return None

    target_date_text = target_date.strftime("%Y-%m-%d")
    remote_nav_map = fetch_history(fund_key, prev_date, target_date_text) or {}
    for nav_date, nav_value in remote_nav_map.items():
        lan_fund.nav_repo.upsert_fund_nav_history(
            fund_code, nav_date, nav_value, "history_api_prev_nav_on_table"
        )

    return lan_fund.nav_repo.get_fund_nav_by_date(fund_code, prev_date)


def _split_two_part_display(value):
    text = str(value or '').strip()
    if not text:
        return text, ''
    if ' ' in text:
        first, second = text.split(' ', 1)
        return first.strip(), second.strip()
    return text, ''


def _growth_color(value):
    growth = parse_growth_percent(value)
    if growth is None:
        return "var(--text-main)"
    if growth < 0:
        return "var(--down-color)"
    if growth > 0:
        return "var(--up-color)"
    return "var(--text-main)"


def build_fund_table(lan_fund):
    """Build fund table rows for web display.

    Returns (titles, rows, sortable_columns).
    """
    result = lan_fund.search_code(True) or []

    def has_active_position(fund_code):
        return safe_float(lan_fund.CACHE_MAP.get(fund_code, {}).get('shares', 0), 0.0) > 0

    def est1_value(row):
        try:
            raw = str(row[4]).replace('%', '')
            for prefix in ('\033[1;31m', '\033[1;32m', '\033[0m'):
                raw = raw.replace(prefix, '')
            return -float(raw)
        except (ValueError, TypeError):
            return 99

    result = sorted(result, key=lambda row: (0 if has_active_position(row[0]) else 1, est1_value(row)))

    total = len(result)
    hold_count = sum(1 for r in result if lan_fund.CACHE_MAP.get(r[0], {}).get("is_hold", False))
    titles = ["标记", "基金代码", f"基金名称 (共{total}个持有{hold_count}个)", "估值1", "估值2", "日涨幅", "连涨/跌", "近30天", "日收益", "持仓/收益", "持有/年化"]
    rows = []
    for row in result:
        code = row[0]
        is_hold = lan_fund.CACHE_MAP.get(code, {}).get("is_hold", False)
        code_cell = f'{code}'
        star_char = "⭐" if is_hold else "☆"
        star_html = (
            f'<span class="fund-hold-star" data-code="{code}" data-hold="{1 if is_hold else 0}" '
            f'title="点击切换持有" style="cursor:pointer;user-select:none;">{star_char}</span>'
        )
        name = row[1]
        if name.startswith("⭐ "):
            name = name[2:]
        if "🏷️" in name and "<span" in name:
            name = name.replace(" <span", "<br><span", 1)
        name_cell = (
            f'<span class="fund-name-cell" data-code="{code}" '
            f'style="cursor:pointer;text-decoration:underline;text-decoration-style:dotted;">{name}</span>'
        )
        now_time = row[2]
        net_value_text = row[3]
        net_value_display = net_value_text.split('(')[0] if isinstance(net_value_text, str) else net_value_text
        shares = safe_float(lan_fund.CACHE_MAP.get(code, {}).get('shares', 0), 0.0)
        net_value_num = safe_float(net_value_display, 0.0)
        holding_return, annual_return, holding_gain, effective_shares = compute_holding_metrics(
            lan_fund.db, lan_fund.user_id, lan_fund.CACHE_MAP, code, shares, net_value_num)
        calc_shares = effective_shares if effective_shares is not None else shares
        position_amount = net_value_num * calc_shares
        position_amount_display = (
            f"<span class='fund-position-amount-cell' data-code='{code}' "
            f"style='cursor:pointer;text-decoration:underline;text-decoration-style:dotted;' title='点击查看交易记录'>"
            f"¥{position_amount:,.2f}</span>"
            f"<br><span class='fund-position-gain-cell' data-code='{code}' "
            f"style='font-size:11px;color:var(--text-dim);font-weight:400;cursor:pointer;text-decoration:underline;text-decoration-style:dotted;' title='点击查看累计收益曲线'>{format_money_value(holding_gain)}</span>"
        )
        performance_display = (
            f"{format_pct_value(holding_return)}"
            f"<br>{format_pct_value(annual_return)}"
        )
        forecast_growth = row[4]
        day_growth = row[5]
        net_value_date = row[6]
        consecutive_info = row[7]
        monthly_info = row[8]
        estimate_date = row[9] if len(row) > 9 else ""
        estimate2_growth = row[10] if len(row) > 10 else "N/A"
        estimate2_time = row[11] if len(row) > 11 else "N/A"
        estimate2_date = row[12] if len(row) > 12 else ""

        consecutive_days_text, consecutive_rate_text = _split_two_part_display(consecutive_info)
        consecutive_rate_color = _growth_color(consecutive_rate_text)
        consecutive_cell = (
            f"{consecutive_days_text}"
            f"<br><span style='font-size:11px;color:{consecutive_rate_color};font-weight:600;'>{consecutive_rate_text}</span>"
        ) if consecutive_rate_text else consecutive_days_text

        monthly_days_text, monthly_rate_text = _split_two_part_display(monthly_info)
        monthly_rate_color = _growth_color(monthly_rate_text)
        monthly_cell = (
            f"{monthly_days_text}"
            f"<br><span style='font-size:11px;color:{monthly_rate_color};font-weight:600;'>{monthly_rate_text}</span>"
        ) if monthly_rate_text else monthly_days_text

        day_growth_val = parse_growth_percent(day_growth)

        display_net_value_date = net_value_date
        if isinstance(net_value_date, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", net_value_date):
            display_net_value_date = net_value_date[5:]

        fund_cache = lan_fund.CACHE_MAP.get(code, {})
        estimate_history = fund_cache.get("estimate_history", {}) if isinstance(fund_cache, dict) else {}
        history_estimate_val = None
        if isinstance(net_value_date, str):
            lookup_keys = [net_value_date]
            if re.match(r"^\d{4}-\d{2}-\d{2}$", net_value_date):
                lookup_keys.append(net_value_date[5:])
            elif re.match(r"^\d{2}-\d{2}$", net_value_date):
                current_year = datetime.datetime.now().year
                lookup_keys.append(f"{current_year}-{net_value_date}")

            for key in lookup_keys:
                if key in estimate_history:
                    history_estimate_val = estimate_history.get(key)
                    break

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        estimate1_diff_str = ""
        if history_estimate_val is not None and day_growth_val is not None and net_value_date != today:
            diff1 = float(history_estimate_val) - day_growth_val
            estimate1_diff_str = f" {format_diff_value(diff1)}"

        estimate2_diff_str = ""
        estimate2_history = fund_cache.get("estimate_history_2", {}) if isinstance(fund_cache, dict) else {}
        history_estimate2_val = None
        if isinstance(net_value_date, str):
            lookup_keys2 = [net_value_date]
            if re.match(r"^\d{4}-\d{2}-\d{2}$", net_value_date):
                lookup_keys2.append(net_value_date[5:])
            elif re.match(r"^\d{2}-\d{2}$", net_value_date):
                lookup_keys2.append(f"{datetime.datetime.now().year}-{net_value_date}")

            for key in lookup_keys2:
                if key in estimate2_history:
                    history_estimate2_val = estimate2_history.get(key)
                    break

        if history_estimate2_val is not None and day_growth_val is not None and net_value_date != today:
            diff2 = float(history_estimate2_val) - day_growth_val
            estimate2_diff_str = f" {format_diff_value(diff2)}"

        estimate_growth_val = parse_growth_percent(forecast_growth)
        estimate_return = None
        if estimate_growth_val is not None and shares > 0:
            estimate_target_date = _parse_date_text(estimate_date) or datetime.datetime.now().date()
            estimate_prev_nav = _get_prev_trading_nav(lan_fund, code, estimate_target_date)
            if estimate_prev_nav is not None and estimate_prev_nav > 0:
                estimate_nav = float(estimate_prev_nav) * (1.0 + estimate_growth_val / 100.0)
                estimate_return = shares * (estimate_nav - float(estimate_prev_nav))

        estimate_return_attr = ""
        if estimate_return is not None:
            estimate_return_attr = f" data-estimate-return='{estimate_return:.6f}'"

        estimate1_cell = (
            f"<span class='fund-estimate-cell' data-code='{code}' data-estimate-date='{estimate_date}'{estimate_return_attr} "
            f"style='cursor:pointer;text-decoration:underline;text-decoration-style:dotted;' title='点击查看估值曲线'>{forecast_growth}</span>"
            f"<br><span style='font-size:11px;color:var(--text-dim);font-weight:400;'>{now_time}{estimate1_diff_str}</span>"
        )
        estimate2_cell = (
            f"<span class='fund-estimate2-cell' data-code='{code}' data-estimate2-date='{estimate2_date}' "
            f"style='font-weight:500;'>{estimate2_growth}</span>"
            f"<br><span style='font-size:11px;color:var(--text-dim);font-weight:400;'>{estimate2_time}{estimate2_diff_str}</span>"
        )

        daygrowth_cell = (
            f"<span class='fund-daygrowth-cell' data-code='{code}'>{day_growth}</span>"
            f"<br><span style='font-size:11px;color:var(--text-dim);font-weight:400;'>{display_net_value_date}</span>"
        )
        day_growth_val = parse_growth_percent(day_growth)
        current_nav = None
        prev_nav = None
        if net_value_date and lan_fund.db and lan_fund.user_id:
            today_date = datetime.datetime.now().date()
            today_str = today_date.strftime("%Y-%m-%d")

            if net_value_date == today_str:
                current_nav = net_value_num
                prev_nav = _get_prev_trading_nav(lan_fund, code, today_date)
            else:
                net_value_date_obj = _parse_date_text(net_value_date)
                if net_value_date_obj:
                    current_nav = net_value_num
                    prev_nav = _get_prev_trading_nav(lan_fund, code, net_value_date_obj)

        if current_nav is not None and prev_nav is not None and shares > 0:
            day_return = shares * (current_nav - prev_nav)
        else:
            day_return = None
        day_return_display = format_money_value(day_return) if day_return is not None else "--"
        rows.append([
            star_html,
            code_cell,
            name_cell,
            estimate1_cell,
            estimate2_cell,
            daygrowth_cell,
            consecutive_cell,
            monthly_cell,
            day_return_display,
            position_amount_display,
            performance_display
        ])
    return titles, rows, [3, 4, 5, 6, 7, 8, 9]


def calculate_position_summary(result, cache_map):
    """Calculate position summary from fund search results.

    Args:
        result: list of fund data rows from search_code
        cache_map: fund cache map (CACHE_MAP)

    Returns:
        dict or None if no positions
    """
    total_value = 0
    estimated_gain = 0
    actual_gain = 0
    settled_value = 0
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    before_market_open = False
    now = datetime.datetime.now()
    current_hour = now.hour
    current_minute = now.minute
    before_market_open = current_hour < 9 or (current_hour == 9 and current_minute < 30)

    fund_details = []

    for fund_data in result:
        shares = cache_map.get(fund_data[0], {}).get('shares', 0)
        if shares <= 0:
            continue

        try:
            fund_code = fund_data[0]
            fund_name = fund_data[1]

            net_value_str = fund_data[3]
            net_value = float(net_value_str.split('(')[0])
            net_value_date = net_value_str.split('(')[1].replace(')', '')

            if len(net_value_date) == 5:
                current_year = datetime.datetime.now().year
                net_value_date = f"{current_year}-{net_value_date}"

            estimated_growth_str = fund_data[4]
            if estimated_growth_str != "N/A":
                estimated_growth_str = estimated_growth_str.replace('\033[1;31m', '').replace('\033[1;32m',
                                                                                              '').replace('%', '')
                estimated_growth = float(estimated_growth_str)
            else:
                estimated_growth = 0

            day_growth_str = fund_data[5]
            if day_growth_str != "N/A":
                day_growth_str = day_growth_str.replace('\033[1;31m', '').replace('\033[1;32m', '').replace('%', '')
                day_growth = float(day_growth_str)
            else:
                day_growth = 0

            position_value = shares * net_value
            total_value += position_value

            fund_est_gain = position_value * estimated_growth / 100
            estimated_gain += fund_est_gain

            fund_act_gain = 0
            if net_value_date == today:
                fund_act_gain = position_value * day_growth / 100
                actual_gain += fund_act_gain
                settled_value += position_value

            fund_details.append({
                'code': fund_code,
                'name': fund_name,
                'shares': shares,
                'position_value': position_value,
                'estimated_gain': fund_est_gain,
                'estimated_gain_pct': (fund_est_gain / position_value * 100) if position_value > 0 else 0,
                'actual_gain': fund_act_gain,
                'actual_gain_pct': (fund_act_gain / position_value * 100) if position_value > 0 else 0,
            })

        except (ValueError, IndexError, AttributeError) as e:
            import logging
            logging.getLogger(__name__).warning(f"解析基金数据失败: {fund_data[0]}, {e}")
            continue

    if total_value == 0:
        return None

    return {
        'total_value': total_value,
        'estimated_gain': estimated_gain,
        'estimated_gain_pct': (estimated_gain / total_value * 100) if total_value > 0 else 0,
        'actual_gain': actual_gain,
        'actual_gain_pct': (actual_gain / settled_value * 100) if settled_value > 0 else 0,
        'settled_value': settled_value,
        'fund_details': fund_details
    }
