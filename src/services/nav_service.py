# -*- coding: UTF-8 -*-
"""NavService — NAV data management, establishment dates, index sync, and backfill."""

import calendar
import datetime
import re
import time
from typing import Dict, List, Optional, Tuple

import requests as _requests
from loguru import logger

import src.fund as fund
from src.services.metrics import safe_float
from src.services.transaction_service import _normalize_nav_date, _extract_net_value_and_date
from src.trading_calendar import is_cn_sse_trading_day, iter_cn_sse_trading_days
from src.config.yaml_config import get_nav_sync_config

# ── module-level config & helpers (moved from fund_server.py) ──────────

_nav_config = get_nav_sync_config()
HISTORY_NAV_REQUEST_PAGE_SIZE = _nav_config.get('request_page_size', 300)
NAV_BACKFILL_REQUEST_MONTHS = _nav_config.get('backfill_months', 12)

_include_today_after_str = _nav_config.get('include_today_after', '20:00')
_nav_include_hour, _nav_include_min = map(int, _include_today_after_str.split(':'))
_NAV_BACKFILL_INCLUDE_TODAY_AFTER = datetime.time(_nav_include_hour, _nav_include_min)


def nav_backfill_effective_end_date(now: Optional[datetime.datetime] = None) -> datetime.date:
    """历史净值自动补齐所覆盖的最后一日（不含「今天」直至 20:00）。"""
    now = now or datetime.datetime.now()
    today = now.date()
    if now.time() < _NAV_BACKFILL_INCLUDE_TODAY_AFTER:
        return today - datetime.timedelta(days=1)
    return today


def _add_months_keep_day(base_date: datetime.date, months: int) -> datetime.date:
    """为日期加减月份，并尽量保持日数不变。"""
    total_months = (base_date.year * 12 + (base_date.month - 1)) + int(months)
    year = total_months // 12
    month = total_months % 12 + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


def _build_backfill_request_segments(
    missing_dates: List[datetime.date],
    max_end_date: datetime.date,
    months: int = NAV_BACKFILL_REQUEST_MONTHS,
) -> List[Tuple[datetime.date, datetime.date]]:
    """按固定月数窗口构造补齐请求片段，窗口长度不受假期缺口影响。"""
    normalized_dates = sorted({
        item for item in missing_dates
        if isinstance(item, datetime.date) and item <= max_end_date
    })
    if not normalized_dates:
        return []

    segments: List[Tuple[datetime.date, datetime.date]] = []
    covered_until: Optional[datetime.date] = None
    for missing_day in normalized_dates:
        if covered_until is not None and missing_day <= covered_until:
            continue
        seg_start = missing_day
        seg_end = min(_add_months_keep_day(seg_start, months) - datetime.timedelta(days=1), max_end_date)
        segments.append((seg_start, seg_end))
        covered_until = seg_end
    return segments


# ── NavService ─────────────────────────────────────────────────────────

class NavService:
    """NAV data management: establishment dates, index sync, history backfill."""

    def __init__(self, db, fund_repo, nav_repo, get_lan_fund_fn):
        self._db = db
        self._fund_repo = fund_repo
        self._nav_repo = nav_repo
        self._get_lan_fund = get_lan_fund_fn

    # ── static helpers ─────────────────────────────────────────────────

    @staticmethod
    def parse_iso_date(date_text):
        try:
            text = str(date_text or '').strip()
            if not text:
                return None
            return datetime.date.fromisoformat(text)
        except Exception:
            return None

    @staticmethod
    def build_missing_nav_segments(
        expected_dates: List[datetime.date],
        existing_nav_map: dict,
    ) -> List[Tuple[datetime.date, datetime.date]]:
        """按缺失交易日构建固定月数补齐片段。"""
        if not expected_dates:
            return []
        existing_dates = {datetime.date.fromisoformat(str(day)) for day in existing_nav_map.keys()}
        missing_dates = sorted([day for day in expected_dates if day not in existing_dates])
        if not missing_dates:
            return []
        return _build_backfill_request_segments(missing_dates, missing_dates[-1])

    # ── establishment date ─────────────────────────────────────────────

    def get_fund_establishment_date(self, user_id, fund_code):
        """从 fund123_matiaria 接口读取基金成立日期。"""
        try:
            api_tpl = fund.DATA_SOURCE_URLS.get('fund123_matiaria_tpl')
            if not api_tpl:
                return None

            my_fund = self._get_lan_fund(user_id=user_id)
            api_url = api_tpl.format(fund=fund_code)
            response = my_fund.session.get(api_url, timeout=10, verify=False)

            date_text = None
            try:
                payload = response.json()
                date_text = (
                    payload.get('titleInfo', {})
                    .get('establishmentDate')
                )
            except Exception:
                pass

            if not date_text:
                match = re.search(r'"establishmentDate"\s*:\s*"(\d{4}-\d{2}-\d{2}|\d{8})"', response.text)
                if match:
                    date_text = match.group(1)

            if not date_text:
                return None

            date_text = str(date_text).strip()
            if re.fullmatch(r'\d{8}', date_text):
                return datetime.datetime.strptime(date_text, '%Y%m%d').date()
            return datetime.date.fromisoformat(date_text)
        except Exception:
            return None

    def get_local_fund_establishment_date(self, user_id, fund_code, user_funds=None):
        """优先从 user_funds 读取成立日，其次用本地净值最早日期推导。"""
        if user_funds is None:
            user_funds = self._fund_repo.get_user_funds(user_id)

        fund_data = user_funds.get(fund_code, {}) if isinstance(user_funds, dict) else {}
        established = self.parse_iso_date(fund_data.get('establishment_date'))
        if established:
            return established

        remote_established = self.get_fund_establishment_date(user_id, fund_code)
        if isinstance(remote_established, datetime.date):
            try:
                self._fund_repo.update_fund_establishment_date(user_id, fund_code, remote_established.isoformat())
            except Exception:
                pass
            return remote_established

        nav_map = self._nav_repo.get_fund_nav_history_range(fund_code) or {}
        first_nav_date = None
        for day in sorted(nav_map.keys()):
            day_obj = self.parse_iso_date(day)
            if day_obj is not None:
                first_nav_date = day_obj
                break

        return first_nav_date

    def backfill_all_establishment_dates(self, user_id):
        """批量补齐当前用户基金成立日期（仅处理 establishment_date 缺失的数据）。"""
        my_fund = self._get_lan_fund(user_id=user_id)

        fund_map = my_fund.CACHE_MAP if isinstance(my_fund.CACHE_MAP, dict) else {}
        if not fund_map:
            return {
                'success': True,
                'message': '暂无基金可回填',
                'total': 0,
                'missing': 0,
                'updated': 0,
                'failed': 0,
                'failed_codes': [],
            }

        total_count = len(fund_map)
        missing_codes = []
        updated_count = 0
        failed_codes = []

        for fund_code, fund_data in fund_map.items():
            existing_text = my_fund._normalize_establishment_date_text(
                (fund_data or {}).get('establishment_date') if isinstance(fund_data, dict) else ''
            )
            if existing_text:
                continue

            missing_codes.append(fund_code)
            established = my_fund._ensure_fund_establishment_date(fund_code)
            if isinstance(established, datetime.date):
                updated_count += 1
            else:
                failed_codes.append(fund_code)

        missing_count = len(missing_codes)
        failed_count = len(failed_codes)
        return {
            'success': True,
            'message': f'成立日回填完成：缺失{missing_count}，补齐{updated_count}，失败{failed_count}',
            'total': total_count,
            'missing': missing_count,
            'updated': updated_count,
            'failed': failed_count,
            'failed_codes': failed_codes,
        }

    # ── index NAV ──────────────────────────────────────────────────────

    def ensure_index_nav_history(self, index_code, start_date, end_date):
        """确保本地指数净值覆盖 [start_date, end_date] 区间，缺失则从云端补齐。"""
        start_obj = self.parse_iso_date(str(start_date))
        end_obj = self.parse_iso_date(str(end_date))
        if start_obj is None or end_obj is None:
            return self._nav_repo.get_index_nav_history_range(index_code, start_date, end_date)

        local_map = self._nav_repo.get_index_nav_history_range(index_code, start_obj.isoformat(), end_obj.isoformat())

        all_trading_days = iter_cn_sse_trading_days(start_obj, end_obj)
        missing = [d for d in all_trading_days if d.isoformat() not in local_map]

        if not missing:
            return local_map

        fetch_start = missing[0].strftime('%Y%m%d')
        fetch_end = missing[-1].strftime('%Y%m%d')
        url = f'https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode={index_code}&startDate={fetch_start}&endDate={fetch_end}'
        try:
            resp = _requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'}, verify=False)
            resp.raise_for_status()
            data = resp.json().get('data') or []
        except Exception as e:
            logger.warning(f"沪深300数据补齐失败【{index_code}】: {e}")
            return local_map

        records = []
        for item in data:
            td = str(item.get('tradeDate', ''))
            if len(td) == 8:
                td = f'{td[:4]}-{td[4:6]}-{td[6:]}'
            close = item.get('close')
            if td and close is not None:
                records.append({'nav_date': td, 'close': float(close), 'change_pct': item.get('changePct')})

        if records:
            self._nav_repo.bulk_upsert_index_nav_history(index_code, records)
            for r in records:
                local_map[r['nav_date']] = r['close']

        logger.info(f"沪深300数据补齐【{index_code}】: 缺失 {len(missing)} 天，从云端补入 {len(records)} 条")
        return local_map

    def sync_index_nav(self, index_code, start_date, end_date):
        """从中证指数官网拉取指定指数历史净值并存库。"""
        if not start_date or not end_date:
            today = datetime.date.today()
            end_date = today.strftime('%Y%m%d')
            start_date = (today - datetime.timedelta(days=365)).strftime('%Y%m%d')

        url = f'https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode={index_code}&startDate={start_date}&endDate={end_date}'
        resp = _requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'}, verify=False)
        resp.raise_for_status()
        payload = resp.json()

        data = payload.get('data') or []
        if not data:
            return {'synced': 0, 'message': 'no data returned'}

        records = []
        for item in data:
            trade_date = str(item.get('tradeDate', '')).strip()
            close = item.get('close')
            if not trade_date or close is None:
                continue
            if len(trade_date) == 8:
                trade_date = f'{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}'
            records.append({
                'nav_date': trade_date,
                'close': float(close),
                'change_pct': item.get('changePct'),
            })

        self._nav_repo.bulk_upsert_index_nav_history(index_code, records)
        return {'synced': len(records)}

    # ── fund NAV history ───────────────────────────────────────────────

    def ensure_nav_history_from_establishment(self, user_id, fund_code, establishment_date):
        """确保本地净值覆盖「成立日 -> 有效截止日」区间（增量补齐）；当日 20:00 前不补今天。"""
        if not isinstance(establishment_date, datetime.date):
            return self._nav_repo.get_fund_nav_history_range(fund_code) or {}

        today = datetime.date.today()
        if establishment_date > today:
            return self._nav_repo.get_fund_nav_history_range(fund_code) or {}

        backfill_end = nav_backfill_effective_end_date()
        if establishment_date > backfill_end:
            return self._nav_repo.get_fund_nav_history_range(
                fund_code,
                establishment_date.isoformat(),
                today.isoformat(),
            ) or {}

        local_nav_map = self._nav_repo.get_fund_nav_history_range(
            fund_code,
            establishment_date.isoformat(),
            today.isoformat(),
        ) or {}

        sorted_dates = sorted(local_nav_map.keys())
        local_max_date = sorted_dates[-1] if sorted_dates else None

        establishment_to_end_days = len(iter_cn_sse_trading_days(establishment_date, backfill_end))
        local_data_days = len(sorted_dates)

        need_full_backfill = not local_max_date or local_data_days < establishment_to_end_days * 0.8

        logger.info(
            f"净值补齐检查【{fund_code}】: establishment_date={establishment_date}, backfill_end={backfill_end}, "
            f"establishment_to_end_days={establishment_to_end_days}, local_data_days={local_data_days}, "
            f"local_max_date={local_max_date}, threshold_80%={int(establishment_to_end_days * 0.8)}, "
            f"need_full_backfill={need_full_backfill}"
        )

        if need_full_backfill:
            check_start = establishment_date
            all_days = iter_cn_sse_trading_days(establishment_date, backfill_end)
            missing_days = [d for d in all_days if d.isoformat() not in local_nav_map]
        else:
            local_max_date_obj = datetime.date.fromisoformat(local_max_date)
            check_start = local_max_date_obj + datetime.timedelta(days=1)
            all_days = iter_cn_sse_trading_days(check_start, backfill_end)
            missing_days = [d for d in all_days if d.isoformat() not in local_nav_map]

        if not missing_days:
            logger.debug(f"净值补齐跳过【{fund_code}】: 本地已有 {len(sorted_dates)} 天数据，从 {local_max_date or establishment_date} 起无缺失交易日")
            return local_nav_map

        request_segments = _build_backfill_request_segments(missing_days, backfill_end)
        segment_count = len(request_segments)

        if segment_count == 0:
            return local_nav_map

        logger.info(
            f"净值补齐【{fund_code}】: start={establishment_date}, backfill_end={backfill_end}, today={today}, "
            f"local_max_date={local_max_date}, missing_days={len(missing_days)}, segments={segment_count}"
        )

        started_at = time.perf_counter()
        wrote_count = 0
        fetched_count = 0
        for seg_start, seg_end in request_segments:
            if seg_start > seg_end:
                continue
            remote_nav_map = self.fetch_history_nav_map_by_date_range(
                user_id,
                fund_code,
                seg_start.isoformat(),
                seg_end.isoformat(),
            )
            if not remote_nav_map:
                continue
            fetched_count += len(remote_nav_map)
            for nav_date, nav_value in remote_nav_map.items():
                if self._nav_repo.upsert_fund_nav_history(fund_code, nav_date, nav_value, source='history_api_establishment_sync'):
                    wrote_count += 1

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info(
            f"净值补齐【{fund_code}】: start={establishment_date}, backfill_end={backfill_end}, today={today}, segments={segment_count}, fetched={fetched_count}, wrote={wrote_count}, elapsed_ms={elapsed_ms}"
        )

        return self._nav_repo.get_fund_nav_history_range(
            fund_code,
            establishment_date.isoformat(),
            today.isoformat(),
        ) or local_nav_map

    def fetch_history_nav_map_by_date_range(self, user_id, fund_code, start_date, end_date):
        """通过历史净值接口批量获取区间净值，返回 {YYYY-MM-DD: nav}。"""
        result = {}
        try:
            start_obj = datetime.date.fromisoformat(str(start_date))
            end_obj = datetime.date.fromisoformat(str(end_date))
        except Exception:
            return result

        if start_obj > end_obj:
            return result

        user_funds = self._fund_repo.get_user_funds(user_id)
        fund_data = user_funds.get(fund_code)
        if not fund_data:
            return result

        fund_key = fund_data.get('fund_key')
        if not fund_key:
            return result

        api_url = fund.DATA_SOURCE_URLS.get('fund123_history_net_value_api')
        if not api_url:
            return result

        my_fund = fund.LanFund(user_id=user_id, db=self._db)

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

        page_size = HISTORY_NAV_REQUEST_PAGE_SIZE
        max_pages = 200

        request_started_at = time.perf_counter()
        segment_total = 0
        page_total = 0

        segment_start = start_obj
        while segment_start <= end_obj:
            segment_total += 1
            segment_end = min(segment_start + datetime.timedelta(days=599), end_obj)
            page_num = 1
            while page_num <= max_pages:
                page_total += 1
                payload = {
                    "productId": fund_key,
                    "startDate": segment_start.strftime('%Y%m%d'),
                    "endDate": segment_end.strftime('%Y%m%d'),
                    "pageNum": page_num,
                    "pageSize": page_size,
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
                except Exception as e:
                    logger.warning(f"区间历史净值接口请求失败【{fund_code} {segment_start}~{segment_end} page={page_num}】: {e}")
                    break

                if not response_json.get("success"):
                    break

                value_list = response_json.get("list", []) or []
                if not value_list:
                    break

                for item in value_list:
                    nav_date = str(item.get("netValueDate", "")).strip()
                    if not nav_date:
                        continue
                    try:
                        nav_value = float(item.get("netValue"))
                    except (TypeError, ValueError):
                        continue
                    if nav_value <= 0:
                        continue
                    result[nav_date] = round(nav_value, 4)

                if len(value_list) < page_size:
                    break
                page_num += 1

            segment_start = segment_end + datetime.timedelta(days=1)

        elapsed_ms = int((time.perf_counter() - request_started_at) * 1000)
        logger.info(
            f"历史净值请求完成【{fund_code}】: start={start_obj}, end={end_obj}, segments={segment_total}, pages={page_total}, records={len(result)}, page_size={page_size}, elapsed_ms={elapsed_ms}"
        )

        return result

    def sync_nav_history_for_curve(self, user_id, fund_code, expected_dates: List[datetime.date]):
        """根据业绩/收益曲线需求补齐本地净值（含新鲜度与缺口段判断）。"""
        if not expected_dates:
            return {}

        expected_dates = sorted({item for item in expected_dates if isinstance(item, datetime.date)})
        if not expected_dates:
            return {}

        start_date = expected_dates[0]
        end_date = expected_dates[-1]

        establishment_date = self.get_fund_establishment_date(user_id, fund_code)
        if establishment_date and establishment_date > start_date:
            expected_dates = [day for day in expected_dates if day >= establishment_date]
            if not expected_dates:
                return {}
            start_date = expected_dates[0]
            end_date = expected_dates[-1]

        sync_end = min(end_date, nav_backfill_effective_end_date())
        if sync_end < start_date:
            return self._nav_repo.get_fund_nav_history_range(fund_code, start_date.isoformat(), end_date.isoformat()) or {}

        expected_dates_sync = [d for d in expected_dates if d <= sync_end]
        if not expected_dates_sync:
            return self._nav_repo.get_fund_nav_history_range(fund_code, start_date.isoformat(), end_date.isoformat()) or {}

        local_nav_map = self._nav_repo.get_fund_nav_history_range(fund_code, start_date.isoformat(), end_date.isoformat()) or {}

        local_max_date = None
        if local_nav_map:
            try:
                local_max_date = max(datetime.date.fromisoformat(day) for day in local_nav_map.keys())
            except Exception:
                local_max_date = None

        need_fresh_backfill = local_max_date is None or local_max_date < sync_end
        missing_segments = self.build_missing_nav_segments(expected_dates_sync, local_nav_map)

        if not need_fresh_backfill and not missing_segments:
            return local_nav_map

        request_segments = missing_segments[:]
        if need_fresh_backfill:
            fresh_start = (local_max_date + datetime.timedelta(days=1)) if local_max_date else start_date
            if fresh_start <= sync_end:
                request_segments.append((fresh_start, sync_end))

        request_segments = sorted(request_segments, key=lambda item: item[0])
        merged_segments: List[Tuple[datetime.date, datetime.date]] = []
        for seg_start, seg_end in request_segments:
            if not merged_segments:
                merged_segments.append((seg_start, seg_end))
                continue
            last_start, last_end = merged_segments[-1]
            if seg_start <= (last_end + datetime.timedelta(days=1)):
                merged_segments[-1] = (last_start, max(last_end, seg_end))
            else:
                merged_segments.append((seg_start, seg_end))

        wrote_count = 0
        for seg_start, seg_end in merged_segments:
            remote_nav_map = self.fetch_history_nav_map_by_date_range(user_id, fund_code, seg_start.isoformat(), seg_end.isoformat())
            if not remote_nav_map:
                continue
            for nav_date, nav_value in remote_nav_map.items():
                if self._nav_repo.upsert_fund_nav_history(fund_code, nav_date, nav_value, source='history_api_bulk'):
                    wrote_count += 1

        if wrote_count > 0:
            logger.info(
                f"净值补齐完成【{fund_code}】: range={start_date}~{end_date}, wrote={wrote_count}, segments={len(merged_segments)}"
            )

        return self._nav_repo.get_fund_nav_history_range(fund_code, start_date.isoformat(), end_date.isoformat()) or local_nav_map
