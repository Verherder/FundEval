# -*- coding: UTF-8 -*-

import datetime
import json
import os
import re
import threading
from pathlib import Path

import urllib3
from dotenv import load_dotenv
from loguru import logger

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

from src.services.metrics import (
    compute_holding_metrics,
    format_diff_value,
    format_money_value,
    format_pct_value,
    parse_growth_percent,
    safe_float,
)
from src.services.fund_refresh_service import FundRefreshService
from src.services.fund_quote_worker import FundQuoteWorker
from src.repositories.fund_repo import FundRepo
from src.repositories.nav_repo import NavRepo
from src.config.yaml_config import get_data_source_urls, get_fund_refresh_config
from src.trading_calendar import iter_cn_sse_trading_days
from src.providers import (
    Fund123Client,
    Fund123EndpointBlockedError,
    FundGzClient,
    FundHttpTransport,
)

# 加载环境变量
load_dotenv()

DATA_SOURCE_URLS = get_data_source_urls()

PERFORMANCE_CHART_INTERVALS = {
    "ONE_MONTH": "近1月",
    "THREE_MONTH": "近3月",
    "SIX_MONTH": "近6月",
    "ONE_YEAR": "近1年",
    "THREE_YEAR": "近3年",
    "FIVE_YEAR": "近5年",
    "SINCE_ESTABLISHMENT": "成立以来",
}

urllib3.disable_warnings()
try:
    _ssl_module = getattr(getattr(urllib3, "util", None), "ssl_", None)
    if _ssl_module is not None and hasattr(_ssl_module, "DEFAULT_CIPHERS"):
        _ssl_module.DEFAULT_CIPHERS = ":".join(
            [
                "ECDHE+AESGCM",
                "ECDHE+CHACHA20",
                'ECDHE-RSA-AES128-SHA',
                'ECDHE-RSA-AES256-SHA',
                "RSA+AESGCM",
                'AES128-SHA',
                'AES256-SHA',
            ]
        )
except Exception:
    pass

def normalize_nav_date_for_storage(nav_date_text, today=None):
    """Normalize NAV date text to YYYY-MM-DD for fund_nav_history keys."""
    text = str(nav_date_text or "").strip()
    if not text:
        return None

    today = today or datetime.date.today()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return datetime.date.fromisoformat(text).isoformat()
        if re.fullmatch(r"\d{2}-\d{2}", text):
            candidate = datetime.date.fromisoformat(f"{today.year}-{text}")
            if candidate > today + datetime.timedelta(days=7):
                candidate = datetime.date.fromisoformat(f"{today.year - 1}-{text}")
            return candidate.isoformat()
        if re.fullmatch(r"\d{8}", text):
            return datetime.datetime.strptime(text, "%Y%m%d").date().isoformat()
    except Exception:
        return None
    return None


def previous_nav_trading_date(nav_date_text):
    """Return the trading day immediately before a NAV date."""
    nav_date = normalize_nav_date_for_storage(nav_date_text)
    if not nav_date:
        return None
    try:
        nav_date_obj = datetime.date.fromisoformat(nav_date)
    except Exception:
        return None

    trading_days = iter_cn_sse_trading_days(nav_date_obj - datetime.timedelta(days=10), nav_date_obj)
    previous_days = [day for day in trading_days if day < nav_date_obj]
    if not previous_days:
        return None
    return previous_days[-1].isoformat()


class MiniFund:
    CACHE_MAP = {}

    def __init__(self, user_id=None, db=None, initialize_remote=True):
        self.user_id = user_id  # 用户ID，如果为None则使用文件模式
        self.db = db  # 数据库实例，从外部传入
        self.fund_repo = FundRepo(db) if db else None
        self.nav_repo = NavRepo(db) if db else None

        self._transport = FundHttpTransport()
        self.session = self._transport.session
        self._csrf = ""
        self._fund123_client = Fund123Client(
            self._request_with_retries,
            self._request_json_with_retries,
            DATA_SOURCE_URLS,
            lambda: self._csrf,
        )
        self._fundgz_client = FundGzClient(self._request_with_retries, DATA_SOURCE_URLS)
        self._refresh_service = FundRefreshService()
        self._quote_worker = FundQuoteWorker(DATA_SOURCE_URLS, normalize_nav_date_for_storage)
        self.result = []
        self._cache_dirty = False
        self._remote_initialized = False

        # 加载缓存数据，外部接口失败时不影响基础功能
        self.load_cache()
        if initialize_remote:
            try:
                self.init()
                self._remote_initialized = True
            except Exception as e:
                logger.error(f"初始化失败(网络或接口问题，不影响登录等基础功能): {e}")

    def _request_with_retries(self, method, url, **kwargs):
        """Compatibility delegate while callers migrate to provider clients."""
        return self._transport.request(method, url, **kwargs)

    def _request_json_with_retries(self, method, url, *, json_retries=3, **kwargs):
        """Compatibility delegate while callers migrate to provider clients."""
        return self._transport.request_json(method, url, json_retries=json_retries, **kwargs)

    def fetch_latest_intraday_estimate(self, fund_key, cancel_event=None):
        """Fetch only the latest estimate point for portfolio refresh consumers."""
        if cancel_event is not None and cancel_event.is_set():
            return None
        client = getattr(self, "_fund123_client", None)
        if client is None:
            client = Fund123Client(
                self._request_with_retries,
                self._request_json_with_retries,
                DATA_SOURCE_URLS,
                lambda: getattr(self, "_csrf", ""),
            )
        return client.fetch_latest_estimate(fund_key)

    def fetch_intraday_curve(self, fund_key):
        """Fetch the full intraday curve only for the chart endpoint."""
        return self._fund123_client.fetch_intraday_curve(fund_key)

    def load_cache(self):
        """加载缓存数据，优先数据库；数据库为空时从 fund_map.json 迁移。"""
        if self.user_id is not None and self.db is not None:
            self.CACHE_MAP = self.fund_repo.get_user_funds(self.user_id)
            if not self.CACHE_MAP:
                _migrated = self._try_migrate_from_file()
                if _migrated is not None:
                    self.CACHE_MAP = _migrated
        else:
            fund_map_path = _PROJECT_ROOT / "cache" / "fund_map.json"
            if fund_map_path.exists():
                with open(str(fund_map_path), "r", encoding="gbk") as f:
                    self.CACHE_MAP = json.load(f)

    def _try_migrate_from_file(self):
        """如果 fund_map.json 存在，将其内容迁移到数据库并返回 CACHE_MAP。"""
        fund_map_path = _PROJECT_ROOT / "cache" / "fund_map.json"
        if not fund_map_path.exists():
            return None
        try:
            with open(str(fund_map_path), "r", encoding="gbk") as f:
                data = json.load(f)
            if not data:
                return None
            self.fund_repo.save_user_funds(self.user_id, data)
            logger.info(f"从 fund_map.json 迁移 {len(data)} 个基金到数据库 (user_id={self.user_id})")
            return data
        except Exception as e:
            logger.warning(f"从 fund_map.json 迁移数据失败: {e}")
            return None

    @staticmethod
    def _normalize_establishment_date_text(raw_value):
        """将成立日期规范为 YYYY-MM-DD 文本，失败返回空字符串。"""
        text = str(raw_value or '').strip()
        if not text:
            return ''
        try:
            if re.fullmatch(r"\d{8}", text):
                return datetime.datetime.strptime(text, "%Y%m%d").strftime("%Y-%m-%d")
            return datetime.date.fromisoformat(text).isoformat()
        except Exception:
            return ''

    def _fetch_fund_establishment_date(self, fund_code):
        """从基金详情接口获取成立日期，返回 YYYY-MM-DD 或 None。"""
        try:
            api_tpl = DATA_SOURCE_URLS.get('fund123_matiaria_tpl')
            if not api_tpl:
                return None

            url = api_tpl.format(fund=fund_code)
            response = self._request_with_retries(
                "GET",
                url,
                headers={
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Connection": "close",
                    "Referer": DATA_SOURCE_URLS['fund123_fund_page'],
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
                    "accept": "application/json,text/plain,*/*"
                },
                verify=False,
            )

            date_text = None
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    date_text = payload.get('titleInfo', {}).get('establishmentDate')
            except Exception:
                pass

            if not date_text:
                match = re.search(r'"establishmentDate"\s*:\s*"(\d{4}-\d{2}-\d{2}|\d{8})"', response.text)
                if match:
                    date_text = match.group(1)

            normalized = self._normalize_establishment_date_text(date_text)
            return normalized or None
        except Exception:
            return None

    def _ensure_fund_establishment_date(self, fund_code):
        """确保缓存/数据库存在成立日期；缺失时远端补齐并返回 date 对象。"""
        fund_cache_data = self.CACHE_MAP.get(fund_code, {}) if isinstance(self.CACHE_MAP, dict) else {}
        existing_text = self._normalize_establishment_date_text(fund_cache_data.get('establishment_date'))
        if existing_text:
            try:
                return datetime.date.fromisoformat(existing_text)
            except Exception:
                pass

        fetched_text = self._fetch_fund_establishment_date(fund_code)
        if not fetched_text:
            return None

        try:
            if isinstance(fund_cache_data, dict):
                fund_cache_data['establishment_date'] = fetched_text
                self.CACHE_MAP[fund_code] = fund_cache_data

            if self.user_id is not None and self.db is not None:
                self.fund_repo.update_fund_establishment_date(self.user_id, fund_code, fetched_text)
            else:
                self.save_cache()

            return datetime.date.fromisoformat(fetched_text)
        except Exception:
            return None

    def _fetch_prev_nav_from_cloud(self, fund_code):
        """
        从 fund123 云端获取基金最新净值，用于日收益计算中前一交易日净值缺失时补全。
        返回净值浮点数，计算后同步落库 fund_nav_history。
        """
        try:
            url = DATA_SOURCE_URLS['fund123_matiaria_tpl'].format(fund=fund_code)
            response = self._request_with_retries(
                "GET",
                url,
                headers={
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Connection": "close",
                    "Origin": DATA_SOURCE_URLS['fund123_origin'],
                    "Referer": DATA_SOURCE_URLS['fund123_fund_page'],
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                    "X-API-Key": "foobar",
                    "accept": "json"
                },
                verify=False,
            )
            net_value = re.findall(r'"netValue":"(.*?)"', response.text)
            net_value_date = re.findall(r'"netValueDate":"(.*?)"', response.text)
            if not net_value or not net_value_date:
                logger.warning(f"获取基金【{fund_code}】云端净值失败：响应格式异常")
                return None
            nav_float = float(net_value[0])
            nav_date = normalize_nav_date_for_storage(net_value_date[0])
            if not nav_date:
                logger.warning(f"获取基金【{fund_code}】云端净值失败：净值日期异常")
                return None
            # 落库
            if self.db is not None and self.user_id is not None and self.nav_repo is not None:
                self.nav_repo.upsert_fund_nav_history(fund_code, nav_date, nav_float, "fund123")
            logger.info(f"云端获取基金【{fund_code}】净值成功: {nav_float}({nav_date})")
            return nav_float
        except Exception as e:
            logger.error(f"云端获取基金【{fund_code}】净值异常: {e}")
            return None

    def _fetch_history_nav_map_by_date_range(self, fund_key, start_date, end_date):
        """Fetch real NAV history from fund123 for a date range."""
        result = {}
        try:
            start_obj = datetime.date.fromisoformat(str(start_date))
            end_obj = datetime.date.fromisoformat(str(end_date))
        except Exception:
            return result
        if start_obj > end_obj:
            return result

        api_url = DATA_SOURCE_URLS.get('fund123_history_net_value_api')
        if not api_url or not fund_key:
            return result

        headers = {
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "close",
            "Content-Type": "application/json",
            "Origin": DATA_SOURCE_URLS['fund123_origin'],
            "Referer": DATA_SOURCE_URLS['fund123_fund_page'],
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "X-API-Key": "foobar",
            "accept": "json"
        }
        payload = {
            "productId": fund_key,
            "startDate": start_obj.strftime("%Y%m%d"),
            "endDate": end_obj.strftime("%Y%m%d"),
            "pageNum": 1,
            "pageSize": 50,
        }

        try:
            response = self._request_with_retries(
                "POST",
                api_url,
                params={"_csrf": self._csrf},
                json=payload,
                headers=headers,
                verify=False,
            )
            response_json = response.json()
        except Exception as e:
            logger.warning(f"刷新补齐历史净值请求失败【{fund_key} {start_date}~{end_date}】: {e}")
            return result

        if not response_json.get("success"):
            return result

        for item in response_json.get("list", []) or []:
            nav_date = normalize_nav_date_for_storage(item.get("netValueDate"))
            if not nav_date:
                continue
            try:
                nav_value = float(item.get("netValue"))
            except (TypeError, ValueError):
                continue
            if nav_value > 0:
                result[nav_date] = round(nav_value, 4)
        return result

    def _ensure_recent_nav_history_on_refresh(self, fund_code, fund_key, latest_nav_date):
        """Refresh missing real NAVs around the latest NAV date."""
        if self.nav_repo is None:
            return 0

        latest_date = normalize_nav_date_for_storage(latest_nav_date)
        prev_date = previous_nav_trading_date(latest_date)
        if not latest_date or not prev_date:
            return 0

        latest_exists = self.nav_repo.get_fund_nav_by_date(fund_code, latest_date) is not None
        prev_exists = self.nav_repo.get_fund_nav_by_date(fund_code, prev_date) is not None
        if latest_exists and prev_exists:
            return 0

        nav_map = self._fetch_history_nav_map_by_date_range(fund_key, prev_date, latest_date)
        wrote = 0
        for nav_date, nav_value in nav_map.items():
            if self.nav_repo.upsert_fund_nav_history(fund_code, nav_date, nav_value, "history_api_recent_refresh"):
                wrote += 1
        return wrote

    def save_cache(self):
        """
        保存缓存数据，优先保存到数据库（如果有user_id），否则保存到json文件。
        """
        if self.user_id is not None and self.db is not None:
            # 保存到数据库
            self.fund_repo.save_user_funds(self.user_id, self.CACHE_MAP)
        else:
            # 保存到文件（CLI模式）
            with open(str(_PROJECT_ROOT / "cache" / "fund_map.json"), "w", encoding="gbk") as f:
                json.dump(self.CACHE_MAP, f, ensure_ascii=False, indent=4)

    def init(self):
        """
        初始化外部网站所需的 csrf / cookie 等。
        任何网络超时、DNS 解析失败等异常都只记录日志，不向外抛出。
        """
        # fund123: 获取 csrf
        try:
            res = self._request_with_retries(
                "GET",
                DATA_SOURCE_URLS['fund123_fund_page'],
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Connection": "close",
                    "Upgrade-Insecure-Requests": "1",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
                },
                verify=False,
            )
            csrf_matches = re.findall('\"csrf\":\"(.*?)\"', res.text)
            if csrf_matches:
                self._csrf = csrf_matches[0]
            else:
                logger.warning("未能在 fund123 页面中解析到 csrf，部分功能可能不可用")
        except Exception as e:
            logger.error(f"获取 fund123 csrf 失败（网络或接口问题）: {e}")

    def add_code(self, codes):
        """
        添加基金代码到缓存，并同步到数据库或文件。
        codes: str, 多个基金代码以逗号分隔。
        """
        codes = codes.split(",")
        codes = [code.strip() for code in codes if code.strip()]
        for code in codes:
            try:
                headers = {
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Connection": "close",
                    "Content-Type": "application/json",
                    "Origin": DATA_SOURCE_URLS['fund123_origin'],
                    "Referer": DATA_SOURCE_URLS['fund123_fund_page'],
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                    "X-API-Key": "foobar",
                    "accept": "json"
                }
                url = DATA_SOURCE_URLS['fund123_search_api']
                params = {
                    "_csrf": self._csrf
                }
                data = {
                    "fundCode": code
                }
                response, search_json = self._request_json_with_retries(
                    "POST",
                    url,
                    headers=headers,
                    params=params,
                    json=data,
                    verify=False,
                )
                if search_json["success"]:
                    fund_key = search_json["fundInfo"]["key"]
                    fund_name = search_json["fundInfo"]["fundName"]
                    establishment_date = self._fetch_fund_establishment_date(code)
                    self.CACHE_MAP[code] = {
                        "fund_key": fund_key,
                        "fund_name": fund_name,
                        "is_hold": False,
                        "shares": 0,
                        "establishment_date": establishment_date,
                    }
                    logger.info(f"添加基金代码【{code}】成功")
                else:
                    logger.error(f"添加基金代码【{code}】失败: {response.text.strip()}")
            except Exception as e:
                logger.error(f"添加基金代码【{code}】失败: {e}")
        self.save_cache()

    def delete_code(self, codes):
        """
        删除基金代码。
        codes: str, 多个基金代码以逗号分隔。
        """
        codes = codes.split(",")
        codes = [code.strip() for code in codes if code.strip()]
        for code in codes:
            try:
                if code in self.CACHE_MAP:
                    del self.CACHE_MAP[code]
                    logger.info(f"删除基金代码【{code}】成功")
                else:
                    logger.warning(f"删除基金代码【{code}】失败: 不存在该基金代码")
            except Exception as e:
                logger.error(f"删除基金代码【{code}】失败: {e}")
        self.save_cache()

    def mark_fund_sector_web(self, codes, sectors):
        """标记基金板块（Web API使用）

        Args:
            codes: list[str], 基金代码列表
            sectors: list[str], 板块名称列表
        """
        for code in codes:
            if code in self.CACHE_MAP:
                self.CACHE_MAP[code]["sectors"] = sectors
                logger.info(f"✓ 已为基金 {code} 绑定板块: {', '.join(sectors)}")
            else:
                logger.warning(f"基金代码 {code} 不存在")
        self.save_cache()

    def unmark_fund_sector_web(self, codes):
        """删除基金板块标记（Web API使用）

        Args:
            codes: list[str], 基金代码列表
        """
        for code in codes:
            if code in self.CACHE_MAP:
                self.CACHE_MAP[code]["sectors"] = []
                logger.info(f"✓ 已删除基金 {code} 的板块标记")
            else:
                logger.warning(f"基金代码 {code} 不存在")
        self.save_cache()

    def search_one_code(self, fund, fund_data, is_return, cancel_event=None):
        quote_worker = getattr(self, "_quote_worker", None)
        if quote_worker is None:
            quote_worker = FundQuoteWorker(DATA_SOURCE_URLS, normalize_nav_date_for_storage)
        return quote_worker.refresh_one(self, fund, fund_data, is_return, cancel_event)

    def search_code(self, is_return=True, cancel_event=None):
        self._cache_dirty = False
        self.result = []
        configured_worker_count = get_fund_refresh_config().get('request_batch_size', 5)
        self._refresh_semaphore = threading.Semaphore(configured_worker_count)
        refresh_service = getattr(self, "_refresh_service", None) or FundRefreshService()
        refresh_service.refresh(
            self.CACHE_MAP,
            configured_worker_count,
            lambda fund, fund_data: self.search_one_code(
                fund, fund_data, True, cancel_event
            ),
            cancel_event=cancel_event,
        )

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        estimate1_rows = [row for row in self.result if len(row) > 9 and row[4] != "N/A" and row[9]]
        estimate2_rows = [row for row in self.result if len(row) > 12 and row[10] != "N/A" and row[12]]
        estimate1_current = sum(1 for row in estimate1_rows if row[9] == today)
        estimate2_current = sum(1 for row in estimate2_rows if row[12] == today)
        logger.info(
            f"基金估值刷新结果: rows={len(self.result)}, "
            f"estimate1={len(estimate1_rows)}(current={estimate1_current}), "
            f"estimate2={len(estimate2_rows)}(current={estimate2_current}), "
            f"missing1={max(0, len(self.result) - len(estimate1_rows))}, "
            f"missing2={max(0, len(self.result) - len(estimate2_rows))}"
        )
        if self._cache_dirty:
            self.save_cache()
            self._cache_dirty = False

        self.result.sort(
            key=lambda row: float(row[4].replace("%", "")) if row[4] != "N/A" else -99,
            reverse=True,
        )
        return self.result

    def build_fund_table(self, cancel_event=None):
        from src.fund_table import build_fund_table
        return build_fund_table(self, cancel_event=cancel_event)
