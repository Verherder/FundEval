# -*- coding: UTF-8 -*-
"""Transaction service — buy, sell, backfill, CRUD, and net-value resolution."""

import datetime
import re
from decimal import Decimal, ROUND_HALF_UP

from src.services.metrics import safe_float, safe_int, quantize_shares_2, calculate_holding_shares_by_time


def _normalize_nav_date(nav_date_text):
    if not nav_date_text:
        return None
    nav_date_text = str(nav_date_text).strip()
    try:
        if len(nav_date_text) == 5:
            current_year = datetime.date.today().year
            nav_date_text = f"{current_year}-{nav_date_text}"
        return datetime.date.fromisoformat(nav_date_text).isoformat()
    except Exception:
        return None


def _extract_net_value_and_date(net_value_text):
    text = str(net_value_text or '').strip()
    if not text:
        return None, None
    nav_value = None
    nav_date = None
    try:
        nav_value = float(text.split('(')[0])
    except Exception:
        nav_value = None
    if '(' in text and ')' in text:
        try:
            date_text = text.split('(')[1].split(')')[0]
            nav_date = _normalize_nav_date(date_text)
        except Exception:
            nav_date = None
    return nav_value, nav_date


def _get_buy_effective_date(now_time=None):
    now_time = now_time or datetime.datetime.now()
    effective_date = now_time.date()
    if now_time.hour >= 15:
        effective_date = effective_date + datetime.timedelta(days=1)
    return effective_date.isoformat()


class TransactionService:
    """Service for fund transaction operations: buy, sell, backfill, CRUD."""

    def __init__(self, fund_repo, transaction_repo, nav_repo, get_lan_fund_func):
        self._fund_repo = fund_repo
        self._transaction_repo = transaction_repo
        self._nav_repo = nav_repo
        self._get_lan_fund = get_lan_fund_func

    # ── net-value helpers ──────────────────────────────────────────────

    def _get_latest_fund_quote(self, user_id, fund_code):
        user_funds = self._fund_repo.get_user_funds(user_id)
        if fund_code not in user_funds:
            return None, None, None

        my_fund = self._get_lan_fund(user_id=user_id)
        rows = my_fund.search_code(True) or []
        for row in rows:
            if row[0] == fund_code:
                net_value, nav_date = _extract_net_value_and_date(row[3])
                return net_value, nav_date, user_funds[fund_code]
        return None, None, user_funds[fund_code]

    def _get_latest_fund_net_value(self, user_id, fund_code):
        net_value, _nav_date, fund_data = self._get_latest_fund_quote(user_id, fund_code)
        return net_value, fund_data

    def _find_net_value_by_date_from_trend(self, user_id, fund_code, target_date):
        nav_map = self._nav_repo.get_fund_nav_history_range(fund_code) or {}
        if not nav_map:
            return None

        # Match target_date exactly, or try MM-DD short form
        short_date = target_date[5:] if isinstance(target_date, str) and len(target_date) == 10 else target_date
        for nav_date, nav_value in nav_map.items():
            if nav_date != target_date and nav_date != short_date:
                continue
            try:
                nav = float(nav_value)
                if nav > 0:
                    return round(nav, 4)
            except (TypeError, ValueError):
                continue
        return None

    def _find_net_value_by_date_from_history_api(self, user_id, fund_code, target_date):
        user_funds = self._fund_repo.get_user_funds(user_id)
        fund_data = user_funds.get(fund_code)
        if not fund_data:
            return None

        fund_key = fund_data.get('fund_key')
        if not fund_key:
            return None

        try:
            normalized_date = datetime.date.fromisoformat(str(target_date)).strftime("%Y%m%d")
        except Exception:
            return None

        my_fund = self._get_lan_fund(user_id=user_id)
        import src.fund as fund

        api_url = fund.DATA_SOURCE_URLS.get('fund123_history_net_value_api')
        if not api_url:
            return None

        headers = {
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "Origin": fund.DATA_SOURCE_URLS['fund123_origin'],
            "Referer": fund.DATA_SOURCE_URLS['fund123_fund_page'],
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "X-API-Key": "foobar",
            "accept": "json"
        }

        payload = {
            "productId": fund_key,
            "startDate": normalized_date,
            "endDate": normalized_date,
            "pageNum": 1,
            "pageSize": 10,
        }

        try:
            response = my_fund.session.post(
                api_url,
                params={"_csrf": my_fund._csrf},
                json=payload,
                headers=headers,
                timeout=10,
                verify=False,
            )
            response_json = response.json()
        except Exception:
            return None

        if not response_json.get("success"):
            return None

        value_list = response_json.get("list", []) or []
        if not value_list:
            return None

        for item in value_list:
            item_date = str(item.get("netValueDate", "")).strip()
            if item_date and item_date != str(target_date):
                continue
            try:
                net_value = float(item.get("netValue"))
                if net_value > 0:
                    return round(net_value, 4)
            except (TypeError, ValueError):
                continue
        return None

    def _resolve_net_value_for_trade_datetime(self, user_id, fund_code, trade_dt):
        if not isinstance(trade_dt, datetime.datetime):
            return None, None

        base_date = trade_dt.date()
        if trade_dt.time() >= datetime.time(15, 0, 0):
            candidate_date = base_date + datetime.timedelta(days=1)
        else:
            candidate_date = base_date

        for _ in range(15):
            target_date = candidate_date.isoformat()
            net_value = self._nav_repo.get_fund_nav_by_date(fund_code, target_date)
            if net_value is None:
                net_value = self._find_net_value_by_date_from_history_api(user_id, fund_code, target_date)
                if net_value is not None and net_value > 0:
                    self._nav_repo.upsert_fund_nav_history(fund_code, target_date, net_value, source='history_api')

            if net_value is None:
                net_value = self._find_net_value_by_date_from_trend(user_id, fund_code, target_date)
                if net_value is not None and net_value > 0:
                    self._nav_repo.upsert_fund_nav_history(fund_code, target_date, net_value, source='trend')

            if net_value is not None and net_value > 0:
                return float(net_value), target_date
            candidate_date = candidate_date + datetime.timedelta(days=1)

        return None, None

    # ── pending-buy settlement ─────────────────────────────────────────

    def _settle_pending_buys(self, user_id):
        pending_orders = self._transaction_repo.get_pending_buys(user_id)
        if not pending_orders:
            return 0

        settled_count = 0
        quote_cache = {}

        for order in pending_orders:
            fund_code = str(order.get('fund_code', '')).strip()
            if not fund_code:
                continue

            effective_date_text = str(order.get('effective_date', '')).strip()
            try:
                effective_date = datetime.date.fromisoformat(effective_date_text)
            except Exception:
                continue

            if fund_code not in quote_cache:
                quote_cache[fund_code] = self._get_latest_fund_quote(user_id, fund_code)
            latest_net_value, latest_nav_date_text, _fund_data = quote_cache[fund_code]

            if not latest_net_value or latest_net_value <= 0 or not latest_nav_date_text:
                continue

            try:
                latest_nav_date = datetime.date.fromisoformat(latest_nav_date_text)
            except Exception:
                continue

            if latest_nav_date < effective_date:
                continue

            amount = float(order.get('amount', 0) or 0)
            shares = float((Decimal(str(amount)) / Decimal(str(latest_net_value))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
            if amount <= 0 or shares <= 0:
                continue

            current_shares = self._fund_repo.update_fund_shares_delta(user_id, fund_code, shares)
            if current_shares is None:
                continue

            tx_time = f"{effective_date.isoformat()} 15:00:00"
            tx_id = self._transaction_repo.add_fund_transaction(
                user_id=user_id,
                fund_code=fund_code,
                tx_type='buy',
                amount=amount,
                shares=shares,
                net_value=latest_net_value,
                tx_time=tx_time,
                fee=0,
            )

            if tx_id is None:
                self._fund_repo.update_fund_shares_delta(user_id, fund_code, -shares)
                continue

            marked = self._transaction_repo.mark_pending_buy_settled(
                pending_id=order['id'],
                settled_tx_id=tx_id,
                settled_net_value=latest_net_value,
                settled_shares=shares,
            )
            if marked:
                settled_count += 1

        return settled_count

    # ── route-level methods ────────────────────────────────────────────

    def update_fund_shares(self, user_id, code, shares):
        success = self._fund_repo.update_fund_shares(user_id, code, shares)
        if success:
            fund_map = self._fund_repo.get_user_funds(user_id)
            latest = fund_map.get(code, {})
            latest_shares = float(latest.get('shares', shares) or 0)
            latest_is_hold = bool(latest.get('is_hold', latest_shares > 0))
            return {
                'success': True,
                'message': f'已更新份额: {latest_shares:.2f}',
                'current_shares': latest_shares,
                'current_is_hold': latest_is_hold,
            }
        else:
            return {'success': False, 'message': '更新失败，基金不存在'}

    def buy_fund(self, user_id, code, amount):
        user_funds = self._fund_repo.get_user_funds(user_id)
        if code not in user_funds:
            return {'success': False, 'message': '基金不存在'}

        effective_date = _get_buy_effective_date()
        pending_id = self._transaction_repo.add_pending_buy(
            user_id=user_id,
            fund_code=code,
            amount=amount,
            effective_date=effective_date,
        )
        if not pending_id:
            return {'success': False, 'message': '买入失败，待确认记录写入失败'}

        self._settle_pending_buys(user_id)

        pending_list = self._transaction_repo.get_pending_buys(user_id, code)
        is_pending = any(int(item.get('id', -1)) == int(pending_id) for item in pending_list)
        latest_funds = self._fund_repo.get_user_funds(user_id)
        current_shares = float(latest_funds.get(code, {}).get('shares', 0) or 0)

        today_text = datetime.date.today().isoformat()
        if is_pending:
            if effective_date == today_text:
                message = f'买入已提交：¥{amount:,.2f}，将按{effective_date}净值确认份额（15:00后）'
            else:
                message = f'买入已提交：¥{amount:,.2f}，将按{effective_date}及之后首个净值日确认份额'
        else:
            message = f'买入已确认：¥{amount:,.2f}，份额已按净值入账'

        return {
            'success': True,
            'message': message,
            'current_shares': current_shares,
            'pending': is_pending,
            'effective_date': effective_date,
        }

    def buy_backfill(self, user_id, code, amount, fee, net_value, trade_date):
        try:
            normalized_date = datetime.date.fromisoformat(trade_date).isoformat()
        except Exception:
            return {'success': False, 'message': '交易日期格式错误，请使用YYYY-MM-DD'}

        net_value_missing = (net_value is None) or (str(net_value).strip() == "")
        if net_value_missing:
            net_value = self._find_net_value_by_date_from_history_api(user_id, code, normalized_date)
            if net_value is None:
                return {'success': False, 'message': '未查询到该日期净值，请手动输入净值后重试'}
        else:
            try:
                net_value = float(str(net_value).strip())
            except (TypeError, ValueError):
                return {'success': False, 'message': '净值格式错误'}
            if net_value <= 0:
                return {'success': False, 'message': '净值必须大于0'}

        net_buy_amount = float((Decimal(str(amount)) - Decimal(str(fee))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        buy_shares = float((Decimal(str(net_buy_amount)) / Decimal(str(net_value))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        if buy_shares <= 0:
            return {'success': False, 'message': '买入金额过小，折算份额为0'}

        user_funds = self._fund_repo.get_user_funds(user_id)
        if code not in user_funds:
            return {'success': False, 'message': '基金不存在'}

        new_shares = self._fund_repo.update_fund_shares_delta(user_id, code, buy_shares)
        if new_shares is None:
            return {'success': False, 'message': '补录失败，份额更新异常'}

        tx_time = f"{normalized_date} 15:00:00"
        tx_id = self._transaction_repo.add_fund_transaction(
            user_id=user_id,
            fund_code=code,
            tx_type='buy',
            amount=amount,
            shares=buy_shares,
            net_value=net_value,
            tx_time=tx_time,
            fee=fee,
        )
        if tx_id is None:
            self._fund_repo.update_fund_shares_delta(user_id, code, -buy_shares)
            return {'success': False, 'message': '补录失败，交易记录写入异常'}

        return {
            'success': True,
            'message': f'补录成功：{normalized_date} 按净值 {net_value:.4f} 买入 ¥{amount:,.2f}（手续费¥{fee:,.2f}，{buy_shares:.2f}份）',
            'current_shares': new_shares,
            'trade_date': normalized_date,
            'shares': buy_shares,
            'fee': fee,
        }

    def sell_backfill(self, user_id, code, shares, fee, net_value, trade_date):
        try:
            normalized_date = datetime.date.fromisoformat(trade_date).isoformat()
        except Exception:
            return {'success': False, 'message': '交易日期格式错误，请使用YYYY-MM-DD'}

        user_funds = self._fund_repo.get_user_funds(user_id)
        if code not in user_funds:
            return {'success': False, 'message': '基金不存在'}

        trade_dt = datetime.datetime.combine(
            datetime.date.fromisoformat(normalized_date),
            datetime.time(15, 0, 0),
        )
        current_holding = calculate_holding_shares_by_time(self._transaction_repo, user_id, code, up_to_dt=trade_dt)

        net_value_missing = (net_value is None) or (str(net_value).strip() == "")
        if net_value_missing:
            net_value = self._find_net_value_by_date_from_history_api(user_id, code, normalized_date)
            if net_value is None:
                return {'success': False, 'message': '未查询到该日期净值，请手动输入净值后重试'}
        else:
            try:
                net_value = float(str(net_value).strip())
            except (TypeError, ValueError):
                return {'success': False, 'message': '净值格式错误'}
            if net_value <= 0:
                return {'success': False, 'message': '净值必须大于0'}

        if shares is None:
            return {'success': False, 'message': '请提供卖出份额'}

        gross_sell_amount = float((Decimal(str(shares)) * Decimal(str(net_value))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        if fee > gross_sell_amount:
            return {'success': False, 'message': '手续费不能大于卖出总额'}
        sell_amount = float((Decimal(str(gross_sell_amount)) - Decimal(str(fee))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

        if shares <= 0:
            return {'success': False, 'message': '卖出金额过小，折算份额为0'}
        if sell_amount <= 0:
            return {'success': False, 'message': '到账金额必须大于0，请检查份额和手续费'}

        request_shares_2 = quantize_shares_2(shares)
        available_shares_2 = quantize_shares_2(current_holding)
        if request_shares_2 > available_shares_2:
            return {
                'success': False,
                'message': (
                    f'卖出份额超过交易时点可用持仓（可用{available_shares_2:.2f}份，'
                    f'本次{request_shares_2:.2f}份；精确可用{current_holding:.4f}，精确本次{shares:.4f}）'
                )
            }

        shares = request_shares_2
        recalculated = self._fund_repo.recalculate_fund_shares_from_transactions(user_id, code)
        summary_shares = float((recalculated or {}).get('current_shares', user_funds.get(code, {}).get('shares', 0)) or 0)
        if shares > quantize_shares_2(summary_shares):
            return {
                'success': False,
                'message': (
                    f'卖出份额超过当前总持仓（当前{summary_shares:.2f}份，'
                    f'本次{shares:.2f}份）'
                )
            }
        if code not in user_funds:
            user_funds[code] = {}
        user_funds[code]['shares'] = summary_shares

        new_shares = self._fund_repo.update_fund_shares_delta(user_id, code, -shares)
        if new_shares is None:
            return {'success': False, 'message': '补录卖出失败，份额更新异常'}

        tx_time = f"{normalized_date} 15:00:00"
        tx_id = self._transaction_repo.add_fund_transaction(
            user_id=user_id,
            fund_code=code,
            tx_type='sell',
            amount=sell_amount,
            shares=shares,
            net_value=net_value,
            tx_time=tx_time,
            fee=fee,
        )
        if tx_id is None:
            self._fund_repo.update_fund_shares_delta(user_id, code, shares)
            return {'success': False, 'message': '补录卖出失败，交易记录写入异常'}

        return {
            'success': True,
            'message': f'补录卖出成功：{normalized_date} 按净值 {net_value:.4f} 卖出 {shares:.2f}份（到账¥{sell_amount:,.2f}，手续费¥{fee:,.2f}）',
            'current_shares': new_shares,
            'trade_date': normalized_date,
            'shares': shares,
            'amount': sell_amount,
            'fee': fee,
        }

    def dividend_backfill(self, user_id, code, amount, net_value, trade_date):
        try:
            normalized_date = datetime.date.fromisoformat(trade_date).isoformat()
        except Exception:
            return {'success': False, 'message': '交易日期格式错误，请使用YYYY-MM-DD'}

        normalized_net_value = None
        if net_value is not None and str(net_value).strip() != '':
            try:
                normalized_net_value = float(str(net_value).strip())
            except (TypeError, ValueError):
                return {'success': False, 'message': '净值格式错误'}
            if normalized_net_value <= 0:
                return {'success': False, 'message': '净值必须大于0'}

        user_funds = self._fund_repo.get_user_funds(user_id)
        if code not in user_funds:
            return {'success': False, 'message': '基金不存在'}

        current_shares = float(user_funds.get(code, {}).get('shares', 0) or 0)
        tx_time = f"{normalized_date} 15:00:00"
        tx_id = self._transaction_repo.add_fund_transaction(
            user_id=user_id,
            fund_code=code,
            tx_type='dividend',
            amount=amount,
            shares=0,
            net_value=normalized_net_value,
            tx_time=tx_time,
            fee=0,
        )
        if tx_id is None:
            return {'success': False, 'message': '补录分红失败，交易记录写入异常'}

        net_value_desc = f'（参考净值 {normalized_net_value:.4f}）' if normalized_net_value is not None else ''
        return {
            'success': True,
            'message': f'补录分红成功：{normalized_date} 记录现金分红 ¥{amount:,.2f}{net_value_desc}',
            'current_shares': current_shares,
            'trade_date': normalized_date,
            'amount': amount,
            'net_value': normalized_net_value,
        }

    def sell_fund(self, user_id, code, shares):
        self._settle_pending_buys(user_id)
        user_funds = self._fund_repo.get_user_funds(user_id)
        if code not in user_funds:
            return {'success': False, 'message': '基金不存在'}

        current_holding = calculate_holding_shares_by_time(
            self._transaction_repo,
            user_id,
            code,
            up_to_dt=None,
            fallback_shares=float(user_funds[code].get('shares', 0) or 0),
        )
        request_shares_2 = quantize_shares_2(shares)
        available_shares_2 = quantize_shares_2(current_holding)
        if request_shares_2 > available_shares_2:
            return {
                'success': False,
                'message': (
                    f'卖出份额超过当前持仓（可用{available_shares_2:.2f}份，'
                    f'本次{request_shares_2:.2f}份；精确可用{current_holding:.4f}，精确本次{shares:.4f}）'
                )
            }

        shares = request_shares_2
        summary_shares = float(user_funds.get(code, {}).get('shares', 0) or 0)
        if abs(summary_shares - available_shares_2) > 1e-8:
            self._fund_repo.update_fund_shares(user_id, code, available_shares_2)
            if code not in user_funds:
                user_funds[code] = {}
            user_funds[code]['shares'] = available_shares_2

        net_value, _fund_data = self._get_latest_fund_net_value(user_id, code)
        if not net_value or net_value <= 0:
            return {'success': False, 'message': '无法获取基金净值，暂无法卖出'}

        sell_amount = shares * net_value
        new_shares = self._fund_repo.update_fund_shares_delta(user_id, code, -shares)
        if new_shares is None:
            return {'success': False, 'message': '卖出失败，份额更新异常'}

        self._transaction_repo.add_fund_transaction(
            user_id=user_id,
            fund_code=code,
            tx_type='sell',
            amount=sell_amount,
            shares=shares,
            net_value=net_value,
            fee=0,
        )

        return {
            'success': True,
            'message': f'卖出成功：{shares:.2f} 份，约 ¥{sell_amount:,.2f}',
            'current_shares': new_shares,
            'net_value': net_value,
        }

    def get_net_value_by_date(self, user_id, code, trade_date):
        try:
            normalized_date = datetime.date.fromisoformat(trade_date).isoformat()
        except Exception:
            return {'success': False, 'message': '日期格式错误，请使用YYYY-MM-DD'}

        net_value = self._find_net_value_by_date_from_history_api(user_id, code, normalized_date)
        if net_value is None:
            net_value = self._find_net_value_by_date_from_trend(user_id, code, normalized_date)

        if net_value is None:
            return {
                'success': True,
                'found': False,
                'message': '未找到该日期净值，请手动输入',
                'trade_date': normalized_date,
            }

        return {
            'success': True,
            'found': True,
            'trade_date': normalized_date,
            'net_value': net_value,
        }

    def get_transactions(self, user_id, code):
        user_funds = self._fund_repo.get_user_funds(user_id)
        if code not in user_funds:
            return {'success': False, 'message': '基金不存在'}

        from src.services.metrics import parse_tx_datetime

        rows = self._transaction_repo.get_fund_transactions(user_id, code)
        share_eps = 1e-6
        running_shares = 0.0
        running_cost = 0.0
        cycle_start_dt = None
        cycle_total_buy = 0.0
        cycle_total_sell = 0.0
        cycle_total_dividend = 0.0
        transactions = []

        for row in rows:
            tx_type = str(row.get('tx_type', '') or '').lower()
            tx_amount = float(row.get('amount', 0) or 0)
            tx_shares = float(row.get('shares', 0) or 0)
            tx_net_value = float(row.get('net_value', 0) or 0) if row.get('net_value') is not None else 0.0
            tx_time_text = str(row.get('tx_time', '') or '')
            tx_dt = parse_tx_datetime(tx_time_text)
            liquidation_gain = None
            liquidation_return = None
            holding_days = None

            if tx_type == 'buy' and tx_shares > 0:
                if running_shares <= share_eps:
                    cycle_start_dt = tx_dt
                    cycle_total_buy = 0.0
                    cycle_total_sell = 0.0
                    cycle_total_dividend = 0.0
                buy_cost = tx_amount if tx_amount > 0 else tx_shares * tx_net_value
                running_shares += tx_shares
                running_cost += buy_cost
                cycle_total_buy += buy_cost
            elif tx_type == 'sell' and tx_shares > 0 and running_shares > share_eps:
                avg_cost_before = (running_cost / running_shares) if running_shares > share_eps else 0.0
                sell_shares = min(tx_shares, running_shares)
                running_cost -= sell_shares * avg_cost_before
                running_shares -= sell_shares
                cycle_total_sell += tx_amount
                if running_shares <= share_eps:
                    liquidation_gain = cycle_total_sell + cycle_total_dividend - cycle_total_buy
                    liquidation_return = (liquidation_gain / cycle_total_buy * 100) if cycle_total_buy > share_eps else None
                    if cycle_start_dt and tx_dt:
                        holding_days = max((tx_dt.date() - cycle_start_dt.date()).days, 0)
            elif tx_type == 'dividend' and tx_amount > 0 and running_shares > share_eps:
                cycle_total_dividend += tx_amount

            if running_shares <= share_eps:
                running_shares = 0.0
                running_cost = 0.0
                if tx_type == 'sell':
                    cycle_start_dt = None
                    cycle_total_buy = 0.0
                    cycle_total_sell = 0.0
                    cycle_total_dividend = 0.0

            avg_cost_after = (running_cost / running_shares) if running_shares > share_eps else None

            transactions.append({
                'id': int(row.get('id', 0) or 0),
                'order_no': str(row.get('order_no', '') or ''),
                'fund_code': code,
                'tx_type': tx_type,
                'amount': tx_amount,
                'shares': tx_shares,
                'net_value': float(row.get('net_value', 0) or 0) if row.get('net_value') is not None else None,
                'fee': float(row.get('fee', 0) or 0),
                'tx_time': tx_time_text,
                'avg_cost_after': avg_cost_after,
                'holding_shares_after': running_shares,
                'liquidation_gain': liquidation_gain,
                'liquidation_return': liquidation_return,
                'holding_days': holding_days,
            })

        transactions = transactions[::-1]

        return {
            'success': True,
            'fund_code': code,
            'transactions': transactions,
        }

    def update_transaction(self, user_id, code, tx_id, tx_type, amount, shares, net_value, fee, tx_time_raw):
        user_funds = self._fund_repo.get_user_funds(user_id)
        if code not in user_funds:
            return {'success': False, 'message': '基金不存在'}

        parsed_dt = None
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S'):
            try:
                parsed_dt = datetime.datetime.strptime(tx_time_raw, fmt)
                break
            except Exception:
                continue
        if parsed_dt is None:
            return {'success': False, 'message': '交易时间格式错误'}
        tx_time = parsed_dt.strftime('%Y-%m-%d %H:%M:%S')

        result = self._transaction_repo.update_fund_transaction_and_recalculate(
            user_id=user_id,
            fund_code=code,
            tx_id=tx_id,
            tx_type=tx_type,
            amount=amount,
            shares=shares,
            net_value=net_value,
            tx_time=tx_time,
            fee=fee,
        )
        if not result:
            return {'success': False, 'message': '更新失败，交易不存在或处理异常'}

        return {
            'success': True,
            'message': '交易记录已更新',
            'current_shares': float(result.get('current_shares', 0) or 0),
            'current_is_hold': bool(result.get('current_is_hold', False)),
        }

    def delete_transaction(self, user_id, code, tx_id):
        result = self._transaction_repo.delete_fund_transaction_and_recalculate(user_id, code, tx_id)
        if not result:
            return {'success': False, 'message': '删除失败，交易不存在或处理异常'}

        deleted_tx = result.get('deleted', {})
        deleted_type_map = {
            'buy': '买入',
            'sell': '卖出',
            'dividend': '分红',
        }
        deleted_type = deleted_type_map.get(str(deleted_tx.get('tx_type', '')).lower(), '交易')
        deleted_shares = float(deleted_tx.get('shares', 0) or 0)

        return {
            'success': True,
            'message': f'已删除{deleted_type}记录（{deleted_shares:.2f}份）',
            'current_shares': float(result.get('current_shares', 0) or 0),
            'current_is_hold': bool(result.get('current_is_hold', False)),
            'deleted_id': int(deleted_tx.get('id', 0) or 0),
        }

    def clear_fund_transactions(self, user_id, code, confirm_text):
        expected_confirm = f'清空 {code}'
        if confirm_text != expected_confirm:
            return {'success': False, 'message': f'确认文本不匹配，请输入"{expected_confirm}"'}

        user_funds = self._fund_repo.get_user_funds(user_id)
        if code not in user_funds:
            return {'success': False, 'message': '基金不存在'}

        result = self._transaction_repo.clear_fund_transactions_and_recalculate(user_id, code)
        if not result:
            return {'success': False, 'message': '清空失败，处理异常'}

        deleted_count = int(result.get('deleted_count', 0) or 0)
        return {
            'success': True,
            'message': f'已清空 {code} 的交易记录，共删除 {deleted_count} 条',
            'deleted_count': deleted_count,
            'current_shares': float(result.get('current_shares', 0) or 0),
            'current_is_hold': bool(result.get('current_is_hold', False)),
        }

    def clear_all_transactions(self, user_id, confirm_text):
        expected_confirm = '清空全部交易'
        if confirm_text != expected_confirm:
            return {'success': False, 'message': f'确认文本不匹配，请输入"{expected_confirm}"'}

        result = self._transaction_repo.clear_all_fund_transactions_and_recalculate(user_id)
        if not result:
            return {'success': False, 'message': '清空失败，处理异常'}

        deleted_count = int(result.get('deleted_count', 0) or 0)
        affected_funds = int(result.get('affected_funds', 0) or 0)
        return {
            'success': True,
            'message': f'已清空全部交易记录，共删除 {deleted_count} 条，影响 {affected_funds} 只基金',
            'deleted_count': deleted_count,
            'affected_funds': affected_funds,
        }
