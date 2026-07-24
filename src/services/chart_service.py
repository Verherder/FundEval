# -*- coding: UTF-8 -*-
"""ChartService — fund chart data: intraday, performance, profit curves."""

import datetime
import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from src.services.metrics import safe_float, safe_int, build_clear_cycles, parse_tx_datetime
from src.services.nav_service import nav_backfill_effective_end_date, _build_backfill_request_segments
from src.services.transaction_service import _extract_net_value_and_date
from src.trading_calendar import is_cn_sse_trading_day, iter_cn_sse_trading_days
from src.config.yaml_config import get_performance_chart_config
from src.services.intraday_chart_service import IntradayChartService

# ── module-level constants (moved from fund_server.py) ────────────────

_perf_config = get_performance_chart_config()
PERFORMANCE_CHART_INTERVAL_LABELS = _perf_config.get('interval_labels', {
    "ONE_MONTH": "近1月",
    "THREE_MONTH": "近3月",
    "SIX_MONTH": "近6月",
    "ONE_YEAR": "近1年",
    "THREE_YEAR": "近3年",
    "FIVE_YEAR": "近5年",
    "SINCE_ESTABLISHMENT": "成立以来",
})

PERFORMANCE_CHART_INTERVAL_DAYS = _perf_config.get('interval_days', {
    "ONE_MONTH": 31,
    "THREE_MONTH": 93,
    "SIX_MONTH": 186,
    "ONE_YEAR": 365,
    "THREE_YEAR": 365 * 3,
    "FIVE_YEAR": 365 * 5,
})

PERFORMANCE_CHART_INTERVAL_ORDER = _perf_config.get('interval_order', [
    "ONE_MONTH",
    "THREE_MONTH",
    "SIX_MONTH",
    "ONE_YEAR",
    "THREE_YEAR",
    "FIVE_YEAR",
    "SINCE_ESTABLISHMENT",
])

PERFORMANCE_CHART_INTERVALS = set(PERFORMANCE_CHART_INTERVAL_ORDER)
DEFAULT_PERFORMANCE_CHART_INTERVAL = _perf_config.get('default_interval', 'SINCE_ESTABLISHMENT')
DEFAULT_PROFIT_CHART_INTERVAL = _perf_config.get('default_profit_interval', 'THREE_MONTH')


# ── helpers ────────────────────────────────────────────────────────────

def resolve_curve_label_dates(labels: List[str]) -> List[Optional[datetime.date]]:
    """将业绩曲线标签解析为日期；兼容 MM-DD（按时间序列回推年份）。"""
    resolved: List[Optional[datetime.date]] = []
    if not labels:
        return resolved

    has_full_date = any(re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(item or '').strip()) for item in labels)
    if has_full_date:
        for label in labels:
            try:
                resolved.append(datetime.date.fromisoformat(str(label).strip()))
            except Exception:
                resolved.append(None)
        return resolved

    current_year = datetime.date.today().year
    reverse_dates: List[Optional[datetime.date]] = []
    prev_date: Optional[datetime.date] = None
    for label in reversed(labels):
        text = str(label or '').strip()
        if not re.fullmatch(r'\d{2}-\d{2}', text):
            reverse_dates.append(None)
            continue
        month = int(text[:2])
        day = int(text[3:5])
        candidate_year = current_year if prev_date is None else prev_date.year
        candidate = None
        for year in range(candidate_year, candidate_year - 6, -1):
            try:
                temp = datetime.date(year, month, day)
            except Exception:
                continue
            if prev_date is None or temp <= prev_date:
                candidate = temp
                break
        reverse_dates.append(candidate)
        if candidate is not None:
            prev_date = candidate

    reverse_dates.reverse()
    return reverse_dates


# ── ChartService ───────────────────────────────────────────────────────

class ChartService:
    """Fund chart data: intraday valuation, performance curves, profit curves."""

    def __init__(self, db, fund_repo, nav_repo, transaction_repo, nav_service, get_lan_fund_fn):
        self._db = db
        self._fund_repo = fund_repo
        self._nav_repo = nav_repo
        self._transaction_repo = transaction_repo
        self._nav_service = nav_service
        self._get_lan_fund = get_lan_fund_fn
        self._intraday_service = IntradayChartService(fund_repo, get_lan_fund_fn)

    # ── helpers ────────────────────────────────────────────────────────

    def get_latest_fund_quote(self, user_id, fund_code):
        """获取基金最新净值与净值日期。"""
        user_funds = self._fund_repo.get_visible_funds(user_id)
        if fund_code not in user_funds:
            return None, None, None

        my_fund = self._get_lan_fund(user_id=user_id)
        rows = my_fund.search_code(True) or []
        for row in rows:
            if row[0] == fund_code:
                net_value, nav_date = _extract_net_value_and_date(row[3])
                return net_value, nav_date, user_funds[fund_code]
        return None, None, user_funds[fund_code]

    def _get_available_performance_intervals(self, establishment_date, end_date):
        available_keys = []
        if not isinstance(end_date, datetime.date):
            end_date = datetime.date.today()

        if isinstance(establishment_date, datetime.date):
            age_days = max((end_date - establishment_date).days, 0)
            for interval_key in PERFORMANCE_CHART_INTERVAL_ORDER:
                if interval_key == 'SINCE_ESTABLISHMENT':
                    available_keys.append(interval_key)
                    continue
                threshold = PERFORMANCE_CHART_INTERVAL_DAYS.get(interval_key)
                if threshold is not None and age_days >= threshold:
                    available_keys.append(interval_key)
            if not available_keys:
                available_keys = ['SINCE_ESTABLISHMENT']
        else:
            available_keys = [
                key for key in PERFORMANCE_CHART_INTERVAL_ORDER
                if key != 'SINCE_ESTABLISHMENT'
            ]

        if 'SINCE_ESTABLISHMENT' not in available_keys:
            available_keys.append('SINCE_ESTABLISHMENT')

        return [[key, PERFORMANCE_CHART_INTERVAL_LABELS.get(key, key)] for key in available_keys]

    def _get_interval_start_date(self, interval_key, end_date, establishment_date=None, fallback_start=None):
        if not isinstance(end_date, datetime.date):
            return fallback_start

        if interval_key == 'SINCE_ESTABLISHMENT':
            return establishment_date or fallback_start

        interval_days = PERFORMANCE_CHART_INTERVAL_DAYS.get(interval_key)
        if interval_days is None:
            return fallback_start

        start_date = end_date - datetime.timedelta(days=max(interval_days - 1, 0))
        if isinstance(establishment_date, datetime.date) and start_date < establishment_date:
            start_date = establishment_date
        return start_date

    def _sync_transaction_nav_points(self, user_id, fund_code):
        """Use confirmed transaction NAVs to fill chart-date gaps before rendering markers."""
        transactions = self._transaction_repo.get_fund_transactions(user_id, fund_code) or []
        wrote_count = 0

        for tx in transactions:
            tx_type = str(tx.get('tx_type', '')).strip().lower()
            if tx_type not in ('buy', 'sell'):
                continue

            tx_dt = parse_tx_datetime(tx.get('tx_time'))
            if tx_dt is None:
                continue

            nav_value = safe_float(tx.get('net_value'), None)
            tx_date = tx_dt.date().isoformat()
            existing_nav = safe_float(self._nav_repo.get_fund_nav_by_date(fund_code, tx_date), None)
            ensured_nav = self._nav_service.ensure_fund_nav_by_date(
                user_id,
                fund_code,
                tx_date,
                fallback_nav=nav_value,
                fallback_source='transaction_nav',
            )
            if (existing_nav is None or existing_nav <= 0) and ensured_nav is not None and ensured_nav > 0:
                wrote_count += 1

        if wrote_count > 0:
            logger.info(f"交易净值补齐业绩曲线【{fund_code}】: wrote={wrote_count}")
        return wrote_count

    def build_local_performance_chart_data(self, user_id, fund_code, fund_name,
                                            date_interval=DEFAULT_PERFORMANCE_CHART_INTERVAL,
                                            user_funds=None):
        """基于本地 fund_nav_history 构建业绩曲线，不依赖远端业绩曲线接口。"""
        if user_funds is None:
            user_funds = self._fund_repo.get_visible_funds(user_id)

        establishment_date = self._nav_service.get_local_fund_establishment_date(
            user_id, fund_code, user_funds=user_funds)
        if isinstance(establishment_date, datetime.date):
            nav_map = self._nav_service.ensure_nav_history_from_establishment(
                user_id, fund_code, establishment_date)
        else:
            nav_map = self._nav_repo.get_fund_nav_history_range(fund_code) or {}

        nav_points = []
        for day in sorted(nav_map.keys()):
            day_obj = self._nav_service.parse_iso_date(day)
            nav_value = safe_float(nav_map.get(day), None)
            if day_obj is None or nav_value is None or nav_value <= 0:
                continue
            nav_points.append((day_obj, round(nav_value, 4)))

        end_date = nav_points[-1][0] if nav_points else datetime.date.today()
        available_intervals = self._get_available_performance_intervals(establishment_date, end_date)
        available_keys = [item[0] for item in available_intervals]

        selected_interval = str(date_interval or DEFAULT_PERFORMANCE_CHART_INTERVAL).strip().upper()
        if selected_interval not in available_keys:
            if DEFAULT_PERFORMANCE_CHART_INTERVAL in available_keys:
                selected_interval = DEFAULT_PERFORMANCE_CHART_INTERVAL
            elif 'SINCE_ESTABLISHMENT' in available_keys:
                selected_interval = 'SINCE_ESTABLISHMENT'
            elif available_keys:
                selected_interval = available_keys[0]
            else:
                selected_interval = DEFAULT_PERFORMANCE_CHART_INTERVAL

        if nav_points:
            fallback_start = nav_points[0][0]
            start_date = self._get_interval_start_date(
                selected_interval, end_date,
                establishment_date=establishment_date,
                fallback_start=fallback_start,
            )
            filtered_points = [item for item in nav_points if (start_date is None or item[0] >= start_date)]
            if not filtered_points:
                filtered_points = nav_points
        else:
            filtered_points = []

        labels = [item[0].isoformat() for item in filtered_points]
        net_values = [item[1] for item in filtered_points]

        growth = []
        base_nav = net_values[0] if net_values else None
        for nav in net_values:
            if base_nav is None or base_nav <= 0:
                growth.append(None)
            else:
                growth.append(round((nav / base_nav - 1.0) * 100.0, 2))

        latest_net_value = net_values[-1] if net_values else None
        latest_net_value_date = labels[-1] if labels else None

        benchmark_growth = []
        if labels:
            hs300_map = self._nav_service.ensure_index_nav_history('000300', labels[0], labels[-1])
            base_close = None
            for label in labels:
                close = hs300_map.get(label)
                if close is not None and base_close is None:
                    base_close = close
                if base_close and close is not None:
                    benchmark_growth.append(round((close / base_close - 1.0) * 100.0, 2))
                else:
                    benchmark_growth.append(None)

        return {
            'labels': labels,
            'growth': growth,
            'net_values': net_values,
            'benchmark_label': '沪深300',
            'benchmark_growth': benchmark_growth,
            'latest_net_value': latest_net_value,
            'latest_net_value_date': latest_net_value_date,
            'from_cache': True,
            'date_interval': selected_interval,
            'interval_label': PERFORMANCE_CHART_INTERVAL_LABELS.get(selected_interval, selected_interval),
            'available_intervals': available_intervals,
            'establishment_date': establishment_date.isoformat() if isinstance(establishment_date, datetime.date) else None,
            'growth_source': 'local_nav',
        }

    # ── route body methods ─────────────────────────────────────────────

    def get_latest_fund_estimate(self, user_id, fund_code):
        """Return one latest estimate point without exposing trend data."""
        return self._intraday_service.get_latest_estimate(user_id, fund_code)

    def get_fund_chart_data(self, user_id, fund_code):
        """获取基金估值趋势图数据。"""
        return self._intraday_service.get_curve(user_id, fund_code)

    def get_fund_performance_chart_data(self, user_id, fund_code, date_interval):
        """获取基金业绩曲线数据。"""
        user_funds = self._fund_repo.get_visible_funds(user_id)

        if fund_code not in user_funds:
            return None

        fund_data = {
            'fund_key': user_funds[fund_code]['fund_key'],
            'fund_name': user_funds[fund_code]['fund_name']
        }

        self._sync_transaction_nav_points(user_id, fund_code)

        chart_data = self.build_local_performance_chart_data(
            user_id=user_id,
            fund_code=fund_code,
            fund_name=fund_data['fund_name'],
            date_interval=date_interval,
            user_funds=user_funds,
        )

        chart_labels = chart_data.get('labels', []) or []
        resolved_label_dates = resolve_curve_label_dates(chart_labels)
        chart_net_values = chart_data.get('net_values', []) or []

        transactions = self._transaction_repo.get_fund_transactions(user_id, fund_code)
        chart_growth = chart_data.get('growth', []) or []
        growth_by_label = {}
        for index, label in enumerate(chart_labels):
            if index >= len(chart_growth):
                continue
            point_date = resolved_label_dates[index] if index < len(resolved_label_dates) else None
            if point_date is not None:
                growth_by_label[point_date.isoformat()] = chart_growth[index]
            else:
                growth_by_label[str(label)] = chart_growth[index]

        clear_cycles = build_clear_cycles(transactions)
        clear_cycle_map = {item['clear_tx_id']: item for item in clear_cycles}

        trade_markers = []
        for tx in transactions:
            tx_time = str(tx.get('tx_time', '')).strip()
            if not tx_time:
                continue
            tx_date = tx_time.split(' ')[0]
            point_value = growth_by_label.get(tx_date)
            if point_value is None:
                continue
            tx_type = str(tx.get('tx_type', '')).strip().lower()
            tx_id = safe_int(tx.get('id', 0), 0)
            cycle_info = clear_cycle_map.get(tx_id)
            marker_type = 'clear' if cycle_info else tx_type
            marker_item = {
                'type': tx_type,
                'marker_type': marker_type,
                'x': tx_date,
                'y': point_value,
                'amount': safe_float(tx.get('amount', 0), 0.0),
                'shares': safe_float(tx.get('shares', 0), 0.0),
                'net_value': safe_float(tx.get('net_value', 0), 0.0),
                'tx_time': tx_time,
            }
            if cycle_info:
                marker_item.update(cycle_info)
            trade_markers.append(marker_item)

        chart_data['trade_markers'] = trade_markers

        net_values = chart_data.get('net_values', []) or []
        parsed_labels = resolved_label_dates

        tx_points = []
        for tx in transactions:
            tx_time = str(tx.get('tx_time', '')).strip()
            if not tx_time:
                continue
            tx_date_text = tx_time.split(' ')[0]
            try:
                tx_date = datetime.date.fromisoformat(tx_date_text)
            except Exception:
                continue
            tx_points.append({
                'date': tx_date,
                'tx_type': str(tx.get('tx_type', '')).strip().lower(),
                'shares': safe_float(tx.get('shares', 0), 0.0),
                'amount': safe_float(tx.get('amount', 0), 0.0),
            })

        tx_points.sort(key=lambda item: item['date'])
        tx_cursor = 0
        holding_shares = 0.0
        cumulative_buy = 0.0
        cumulative_sell = 0.0
        holding_return_pct = []

        for idx, label_date in enumerate(parsed_labels):
            if label_date is None:
                holding_return_pct.append(None)
                continue

            while tx_cursor < len(tx_points) and tx_points[tx_cursor]['date'] <= label_date:
                current_tx = tx_points[tx_cursor]
                tx_type = current_tx['tx_type']
                tx_shares = current_tx['shares']
                tx_amount = current_tx['amount']
                if tx_type == 'buy':
                    holding_shares += tx_shares
                    cumulative_buy += tx_amount
                elif tx_type == 'sell':
                    holding_shares -= tx_shares
                    cumulative_sell += tx_amount
                elif tx_type == 'dividend':
                    cumulative_sell += tx_amount
                tx_cursor += 1

            if holding_shares < 0:
                holding_shares = 0.0

            if cumulative_buy <= 0:
                holding_return_pct.append(None)
                continue

            nav = safe_float(net_values[idx] if idx < len(net_values) else None, None)
            if nav is None:
                holding_return_pct.append(None)
                continue

            total_value = cumulative_sell + holding_shares * nav
            total_return = total_value - cumulative_buy
            holding_return_pct.append(round(total_return / cumulative_buy * 100.0, 2))

        chart_data['holding_return_pct'] = holding_return_pct

        return {
            'chart_data': chart_data,
            'fund_info': {
                'code': fund_code,
                'name': fund_data['fund_name']
            }
        }

    def get_fund_profit_chart_data(self, user_id, fund_code, date_interval):
        """获取基金累计收益曲线数据。"""
        user_funds = self._fund_repo.get_visible_funds(user_id)
        if fund_code not in user_funds:
            return None

        fund_data = {
            'fund_key': user_funds[fund_code]['fund_key'],
            'fund_name': user_funds[fund_code]['fund_name']
        }

        self._sync_transaction_nav_points(user_id, fund_code)

        perf_data = self.build_local_performance_chart_data(
            user_id=user_id,
            fund_code=fund_code,
            fund_name=fund_data['fund_name'],
            date_interval=date_interval,
            user_funds=user_funds,
        )

        labels = perf_data.get('labels', []) or []
        net_values = perf_data.get('net_values', []) or []
        growth_values = perf_data.get('growth', []) or []

        if len(net_values) < len(labels):
            net_values = net_values + [None] * (len(labels) - len(net_values))

        interval_start_date = None
        establishment_date = self._nav_service.parse_iso_date(perf_data.get('establishment_date'))
        if date_interval == 'SINCE_ESTABLISHMENT' and isinstance(establishment_date, datetime.date):
            interval_start_date = establishment_date
        elif labels:
            interval_start_date = self._nav_service.parse_iso_date(labels[0])

        if isinstance(interval_start_date, datetime.date):
            interval_end_date = nav_backfill_effective_end_date()
            interval_nav_map = self._nav_repo.get_fund_nav_history_range(
                fund_code,
                interval_start_date.isoformat(),
                interval_end_date.isoformat(),
            ) or {}

            interval_nav_dates = []
            for day in interval_nav_map.keys():
                day_obj = self._nav_service.parse_iso_date(day)
                if isinstance(day_obj, datetime.date):
                    interval_nav_dates.append(day_obj)

            expected_interval_days = iter_cn_sse_trading_days(interval_start_date, interval_end_date)
            existing_interval_days = {
                day_obj for day_obj in interval_nav_dates
                if is_cn_sse_trading_day(day_obj)
            }
            missing_interval_days = [day for day in expected_interval_days if day not in existing_interval_days]
            request_segments = _build_backfill_request_segments(missing_interval_days, interval_end_date)

            if request_segments:
                wrote_count = 0
                for seg_start, seg_end in request_segments:
                    if seg_start > seg_end:
                        continue
                    remote_nav_map = self._nav_service.fetch_history_nav_map_by_date_range(
                        user_id,
                        fund_code,
                        seg_start.isoformat(),
                        seg_end.isoformat(),
                    )
                    if not remote_nav_map:
                        continue
                    for nav_date, nav_value in remote_nav_map.items():
                        if self._nav_repo.upsert_fund_nav_history(fund_code, nav_date, nav_value, source='history_api_profit_interval_sync'):
                            wrote_count += 1

                if wrote_count > 0:
                    logger.info(
                        f"收益曲线净值补齐完成【{fund_code}】: start={interval_start_date}, end={interval_end_date}, wrote={wrote_count}"
                    )
                    perf_data = self.build_local_performance_chart_data(
                        user_id=user_id,
                        fund_code=fund_code,
                        fund_name=fund_data['fund_name'],
                        date_interval=date_interval,
                        user_funds=user_funds,
                    )
                    labels = perf_data.get('labels', []) or []
                    net_values = perf_data.get('net_values', []) or []
                    growth_values = perf_data.get('growth', []) or []
                    if len(net_values) < len(labels):
                        net_values = net_values + [None] * (len(labels) - len(net_values))

        transactions = self._transaction_repo.get_fund_transactions(user_id, fund_code)
        sorted_txs = []
        for tx in transactions:
            tx_time = str(tx.get('tx_time', '') or '').strip()
            if not tx_time:
                continue

            tx_dt = None
            try:
                tx_dt = datetime.datetime.fromisoformat(tx_time.replace(' ', 'T'))
            except Exception:
                try:
                    tx_dt = datetime.datetime.strptime(tx_time, '%Y-%m-%d %H:%M:%S')
                except Exception:
                    pass
            if tx_dt is None:
                continue

            tx_type = str(tx.get('tx_type', '') or '').strip().lower()
            if tx_type not in ('buy', 'sell', 'dividend'):
                continue

            tx_amount = safe_float(tx.get('amount'))
            tx_shares = safe_float(tx.get('shares'))
            tx_fee = safe_float(tx.get('fee'))
            tx_nav = safe_float(tx.get('net_value'))

            sorted_txs.append({
                'datetime': tx_dt,
                'date': tx_dt.date(),
                'type': tx_type,
                'amount': max(tx_amount or 0.0, 0.0),
                'shares': max(tx_shares or 0.0, 0.0),
                'fee': max(tx_fee or 0.0, 0.0),
                'net_value': tx_nav if tx_nav and tx_nav > 0 else None,
            })

        sorted_txs.sort(key=lambda item: item['datetime'])

        resolved_label_dates = resolve_curve_label_dates(labels)
        expected_dates = [item for item in resolved_label_dates if isinstance(item, datetime.date)]
        local_nav_map = self._nav_repo.get_fund_nav_history_range(fund_code) or {}

        has_valid_nav = any(safe_float(value) not in (None, 0.0) for value in net_values)
        if labels:
            anchor_nav = None
            anchor_date = None

            for idx in range(len(labels) - 1, -1, -1):
                nav_num = safe_float(net_values[idx]) if idx < len(net_values) else None
                if nav_num is not None and nav_num > 0:
                    anchor_nav = nav_num
                    anchor_date = labels[idx]
                    break

            if anchor_nav is None or anchor_nav <= 0:
                for tx_item in reversed(sorted_txs):
                    if tx_item['net_value'] is not None:
                        anchor_nav = tx_item['net_value']
                        anchor_date = tx_item['date'].isoformat()
                        break

            if (anchor_nav is None or anchor_nav <= 0) and local_nav_map:
                last_date = sorted(local_nav_map.keys())[-1]
                local_anchor = safe_float(local_nav_map.get(last_date))
                if local_anchor is not None and local_anchor > 0:
                    anchor_nav = local_anchor
                    anchor_date = last_date

            if anchor_nav is None or anchor_nav <= 0:
                latest_nav, latest_nav_date, _ = self.get_latest_fund_quote(user_id, fund_code)
                latest_nav_num = safe_float(latest_nav)
                if latest_nav_num is not None and latest_nav_num > 0:
                    anchor_nav = latest_nav_num
                    anchor_date = latest_nav_date

            reference_index = None
            if anchor_date:
                try:
                    anchor_date_obj = datetime.date.fromisoformat(str(anchor_date))
                except Exception:
                    anchor_date_obj = None
                if anchor_date_obj is not None:
                    for idx, point_date in enumerate(resolved_label_dates):
                        if point_date == anchor_date_obj:
                            reference_index = idx
                            break

                if reference_index is None:
                    anchor_date_text = str(anchor_date)
                    anchor_suffix = anchor_date_text[5:] if len(anchor_date_text) >= 10 else anchor_date_text
                    for idx, label in enumerate(labels):
                        label_text = str(label)
                        if label_text == anchor_date_text or label_text.endswith(anchor_suffix):
                            reference_index = idx
                            break

            if reference_index is None:
                for idx in range(len(growth_values) - 1, -1, -1):
                    if safe_float(growth_values[idx], None) is not None:
                        reference_index = idx
                        break

            if anchor_nav and anchor_nav > 0 and reference_index is not None:
                reference_growth = safe_float(growth_values[reference_index]) or 0.0
                denominator = 1 + reference_growth / 100.0
                if abs(denominator) > 1e-8:
                    base_nav = anchor_nav / denominator
                    rebuilt_nav_values = []
                    for idx, growth in enumerate(growth_values):
                        growth_num = safe_float(growth)
                        if growth_num is None:
                            rebuilt_nav_values.append(None)
                        else:
                            rebuilt_nav_values.append(round(base_nav * (1 + growth_num / 100.0), 4))

                    max_len = max(len(net_values), len(rebuilt_nav_values))
                    merged_nav_values = []
                    for idx in range(max_len):
                        real_nav = safe_float(net_values[idx]) if idx < len(net_values) else None
                        rebuilt_nav = safe_float(rebuilt_nav_values[idx]) if idx < len(rebuilt_nav_values) else None
                        if real_nav is not None and real_nav > 0:
                            merged_nav_values.append(round(real_nav, 4))
                        elif rebuilt_nav is not None and rebuilt_nav > 0:
                            merged_nav_values.append(round(rebuilt_nav, 4))
                        else:
                            merged_nav_values.append(None)
                    net_values = merged_nav_values

        nav_by_date = {}
        for idx, point_date in enumerate(resolved_label_dates):
            if point_date is None:
                continue
            nav_value = safe_float(net_values[idx]) if idx < len(net_values) else None
            if nav_value is not None and nav_value > 0:
                nav_by_date[point_date] = round(nav_value, 4)

        if not nav_by_date and sorted_txs:
            for tx in sorted_txs:
                if tx['net_value'] is not None:
                    nav_by_date[tx['date']] = round(tx['net_value'], 4)

        expanded_dates = sorted(nav_by_date.keys()) if nav_by_date else sorted(expected_dates)
        expanded_labels = [item.isoformat() for item in expanded_dates]
        expanded_net_values = [nav_by_date.get(item) for item in expanded_dates]

        tx_index = 0
        cumulative_buy = 0.0
        cumulative_sell = 0.0
        cumulative_dividend = 0.0
        realized_gain = 0.0
        holding_shares = 0.0
        remaining_cost = 0.0

        profit_values = []
        holding_gain_values = []
        realized_gain_values = []
        position_value_values = []
        remaining_cost_values = []
        cumulative_buy_values = []
        cumulative_sell_values = []
        cumulative_dividend_values = []
        profit_rate_values = []

        for idx, point_date in enumerate(expanded_dates):

            while tx_index < len(sorted_txs) and point_date and sorted_txs[tx_index]['date'] <= point_date:
                tx = sorted_txs[tx_index]
                tx_type = tx['type']
                tx_amount = tx['amount']
                tx_shares = tx['shares']
                tx_fee = tx['fee']

                if tx_type == 'buy' and tx_shares > 0:
                    total_cost = tx_amount
                    cumulative_buy += total_cost
                    holding_shares += tx_shares
                    remaining_cost += total_cost
                elif tx_type == 'sell' and tx_shares > 0 and holding_shares > 1e-8:
                    sold_shares = min(tx_shares, holding_shares)
                    avg_cost = (remaining_cost / holding_shares) if holding_shares > 1e-8 else 0.0
                    sold_cost = sold_shares * avg_cost
                    proceeds = tx_amount

                    if tx_shares > sold_shares and tx_shares > 0:
                        proceeds *= (sold_shares / tx_shares)

                    cumulative_sell += proceeds
                    realized_gain += (proceeds - sold_cost)
                    remaining_cost = max(remaining_cost - sold_cost, 0.0)
                    holding_shares = max(holding_shares - sold_shares, 0.0)
                elif tx_type == 'dividend':
                    cumulative_dividend += tx_amount
                    cumulative_sell += tx_amount
                    realized_gain += tx_amount

                tx_index += 1

            net_value = expanded_net_values[idx] if idx < len(expanded_net_values) else None
            net_value_num = safe_float(net_value)

            if net_value_num is None and holding_shares > 1e-8:
                position_value = None
                holding_gain = None
                total_profit = None
            else:
                position_value = (holding_shares * (net_value_num or 0.0))
                holding_gain = position_value - remaining_cost
                total_profit = realized_gain + holding_gain

            invested_base = cumulative_buy if cumulative_buy > 1e-8 else 0.0
            if total_profit is None or invested_base <= 0:
                profit_rate = None
            else:
                profit_rate = total_profit / invested_base * 100.0

            profit_values.append(round(total_profit, 2) if total_profit is not None else None)
            holding_gain_values.append(round(holding_gain, 2) if holding_gain is not None else None)
            realized_gain_values.append(round(realized_gain, 2))
            position_value_values.append(round(position_value, 2) if position_value is not None else None)
            remaining_cost_values.append(round(remaining_cost, 2))
            cumulative_buy_values.append(round(cumulative_buy, 2))
            cumulative_sell_values.append(round(cumulative_sell, 2))
            cumulative_dividend_values.append(round(cumulative_dividend, 2))
            profit_rate_values.append(round(profit_rate, 4) if profit_rate is not None else None)

        latest_profit = next((value for value in reversed(profit_values) if value is not None), None)
        latest_profit_rate = next((value for value in reversed(profit_rate_values) if value is not None), None)

        chart_data = {
            'labels': expanded_labels,
            'profit_values': profit_values,
            'holding_gain_values': holding_gain_values,
            'realized_gain_values': realized_gain_values,
            'position_value_values': position_value_values,
            'remaining_cost_values': remaining_cost_values,
            'cumulative_buy_values': cumulative_buy_values,
            'cumulative_sell_values': cumulative_sell_values,
            'cumulative_dividend_values': cumulative_dividend_values,
            'profit_rate_values': profit_rate_values,
            'date_interval': perf_data.get('date_interval', date_interval),
            'interval_label': perf_data.get('interval_label', date_interval),
            'available_intervals': perf_data.get('available_intervals', []),
            'establishment_date': perf_data.get('establishment_date'),
            'latest_profit': latest_profit,
            'latest_profit_rate': latest_profit_rate,
        }

        return {
            'chart_data': chart_data,
            'fund_info': {
                'code': fund_code,
                'name': fund_data['fund_name']
            }
        }

    def set_chart_default(self, user_id, fund_code):
        """设置估值趋势图默认基金。"""
        user_funds = self._fund_repo.get_visible_funds(user_id)
        if fund_code not in user_funds:
            return False
        self._fund_repo.update_chart_default(user_id, fund_code)
        return True
