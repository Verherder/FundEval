# -*- coding: UTF-8 -*-
"""Fund service — fund CRUD, hold/sector management, file upload/download, and settlement."""

import datetime
import json
import tempfile
from decimal import Decimal, ROUND_HALF_UP


class FundService:
    """Service for fund management operations.

    Args:
        db: Database connection.
        fund_repo: FundRepo instance.
        transaction_repo: TransactionRepo instance.
        get_lan_fund_fn: Callable returning a MiniFund instance for the current request.
        chart_service: ChartService instance (for quote lookups during settlement).
    """

    def __init__(self, db, fund_repo, transaction_repo, get_lan_fund_fn, chart_service):
        self._db = db
        self._fund_repo = fund_repo
        self._transaction_repo = transaction_repo
        self._get_lan_fund = get_lan_fund_fn
        self._chart_service = chart_service

    # ------------------------------------------------------------------
    # Fund CRUD
    # ------------------------------------------------------------------

    def add_fund(self, user_id, codes):
        """Add fund codes to the user's watchlist."""
        my_fund = self._get_lan_fund(user_id=user_id)
        my_fund.add_code(codes)
        return {'success': True, 'message': f'已添加基金: {codes}'}

    def add_catalog_funds(self, user_id, codes):
        """Select funds that already exist in the shared catalog."""
        parsed_codes = self._parse_codes(codes)
        existing = {
            item["fund_code"]
            for item in self._fund_repo.get_fund_catalog(user_id)
        }
        missing = [code for code in parsed_codes if code not in existing]
        if missing:
            return {
                "success": False,
                "message": f"公共基金池中不存在: {', '.join(missing)}",
            }
        added = self._fund_repo.add_catalog_funds_to_watchlist(user_id, parsed_codes)
        return {"success": True, "message": f"已加入自选: {added} 只基金"}

    def delete_fund(self, user_id, codes):
        """Delete fund codes from the user's watchlist."""
        fund_map = self._fund_repo.get_user_funds(user_id) or {}
        for code in self._parse_codes(codes):
            fund_map.pop(code, None)
        self._fund_repo.save_user_funds(user_id, fund_map)
        return {'success': True, 'message': f'已删除基金: {codes}'}

    # ------------------------------------------------------------------
    # Hold / Sector
    # ------------------------------------------------------------------

    def set_hold(self, user_id, codes, hold):
        """Set or clear the hold flag on one or more funds."""
        fund_map = self._fund_repo.get_user_funds(user_id) or {}
        for code in self._parse_codes(codes):
            if code in fund_map:
                fund_map[code]['is_hold'] = bool(hold)
        self._fund_repo.save_user_funds(user_id, fund_map)
        action = '标记持有' if hold else '取消持有'
        return {'success': True, 'message': f'已{action}: {codes}'}

    def set_sector(self, user_id, codes, sectors):
        """Assign sector tags to one or more funds."""
        fund_map = self._fund_repo.get_user_funds(user_id) or {}
        for code in self._parse_codes(codes):
            if code in fund_map:
                fund_map[code]['sectors'] = list(sectors)
        self._fund_repo.save_user_funds(user_id, fund_map)
        sectors_str = ", ".join(sectors)
        return {'success': True, 'message': f'已标注板块: {codes} -> {sectors_str}'}

    def remove_sector(self, user_id, codes):
        """Remove sector tags from one or more funds."""
        fund_map = self._fund_repo.get_user_funds(user_id) or {}
        for code in self._parse_codes(codes):
            if code in fund_map:
                fund_map[code]['sectors'] = []
        self._fund_repo.save_user_funds(user_id, fund_map)
        return {'success': True, 'message': f'已删除板块标记: {codes}'}

    @staticmethod
    def _parse_codes(codes):
        return [code.strip() for code in str(codes or '').split(',') if code.strip()]

    # ------------------------------------------------------------------
    # Upload / Download
    # ------------------------------------------------------------------

    def upload_funds(self, user_id, file_bytes, filename):
        """Parse and save an uploaded fund_map.json file.

        Returns:
            dict with success/error info.
        """
        filename = str(filename or '').strip()
        if not filename:
            return {'success': False, 'message': '未选择文件'}
        if not filename.endswith('.json'):
            return {'success': False, 'message': '只支持JSON文件'}

        try:
            content = file_bytes.decode('gbk')
            fund_map = json.loads(content)
        except json.JSONDecodeError:
            return {'success': False, 'message': 'JSON格式错误'}

        if not isinstance(fund_map, dict):
            return {'success': False, 'message': '文件格式错误：应为JSON对象'}

        for code, fund_data in fund_map.items():
            if not isinstance(fund_data, dict):
                return {'success': False, 'message': f'基金{code}数据格式错误'}
            if 'fund_key' not in fund_data or 'fund_name' not in fund_data:
                return {'success': False, 'message': f'基金{code}缺少必要字段'}

        success = self._fund_repo.save_user_funds(user_id, fund_map)
        if success:
            return {'success': True, 'message': f'成功导入{len(fund_map)}个基金'}
        return {'success': False, 'message': '保存失败'}

    def download_funds(self, user_id):
        """Generate a temp file with the user's fund_map and return send_file args.

        Returns:
            Tuple of (temp_path, download_name, mimetype) for send_file.
        """
        fund_map = self._fund_repo.get_user_funds(user_id)
        with tempfile.NamedTemporaryFile(mode='w', encoding='gbk', suffix='.json', delete=False) as f:
            json.dump(fund_map, f, ensure_ascii=False, indent=4)
            temp_path = f.name
        return temp_path, 'fund_map.json', 'application/json'

    def download_all_transactions(self, user_id):
        """Generate a temp file with a full transaction backup and return send_file args.

        Returns:
            Tuple of (temp_path, download_name, mimetype) for send_file.
        """
        user_funds = self._fund_repo.get_user_funds(user_id)
        transactions = self._transaction_repo.get_all_fund_transactions(user_id)

        backup_payload = {
            'exported_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'user_id': user_id,
            'fund_count': len(user_funds),
            'transaction_count': len(transactions),
            'funds': user_funds,
            'transactions': transactions,
        }

        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', delete=False) as f:
            json.dump(backup_payload, f, ensure_ascii=False, indent=2)
            temp_path = f.name

        download_name = f'fund_transactions_backup_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        return temp_path, download_name, 'application/json'

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_fund_data(self, user_id):
        """Return the user's fund_map dict after settling pending buys."""
        self.settle_pending_buys(user_id)
        return self._fund_repo.get_user_funds(user_id)

    def get_fund_list(self, user_id):
        """Return a list of fund dicts with shares, hold, sector, and quote info."""
        fund_map = self._fund_repo.get_user_funds(user_id)

        funds = []
        for code, data in fund_map.items():
            funds.append({
                'code': code,
                'name': data.get('fund_name', ''),
                'shares': data.get('shares', 0),
                'is_hold': data.get('is_hold', False),
                'sectors': data.get('sectors', []),
                'net_value': data.get('net_value', 0),
                'day_growth': data.get('day_growth', 0),
                'estimated_growth': data.get('estimated_growth', 0),
            })

        return {'success': True, 'data': funds}

    # ------------------------------------------------------------------
    # Settlement
    # ------------------------------------------------------------------

    def settle_pending_buys(self, user_id):
        """Settle pending buy orders whose effective date has been reached.

        Returns:
            Number of orders settled.
        """
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
                quote_cache[fund_code] = self._chart_service.get_latest_fund_quote(user_id, fund_code)
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
            shares = float((Decimal(str(amount)) / Decimal(str(latest_net_value))).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP))
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
                user_id=user_id,
                pending_id=order['id'],
                settled_tx_id=tx_id,
                settled_net_value=latest_net_value,
                settled_shares=shares,
            )
            if marked:
                settled_count += 1

        return settled_count
