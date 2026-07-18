# -*- coding: UTF-8 -*-

import argparse
import datetime
import json
import os
import re
import threading
import time
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import urllib3
import tabulate as tabulate_module
from dotenv import load_dotenv
from loguru import logger
from tabulate import tabulate

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

from src.data.bk_map import BK_MAP
from src.data.sectors import MAJOR_CATEGORIES
from src.services.metrics import (
    compute_holding_metrics,
    format_diff_value,
    format_money_value,
    format_pct_value,
    parse_growth_percent,
    safe_float,
)
from src.services.fund_refresh_service import FundRefreshService
from src.utils.financial import solve_xirr, xnpv
from src.repositories.fund_repo import FundRepo
from src.repositories.nav_repo import NavRepo
from src.config.yaml_config import get_data_source_urls, get_fund_refresh_config
from src.market_data import (
    fetch_bk,
    fetch_select_fund,
)
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

tabulate_module.PRESERVE_WHITESPACE = True


def format_table_msg(table, tablefmt="pretty"):
    return tabulate(table, tablefmt=tablefmt, missingval="N/A")


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
        self.report_dir = None  # 默认不输出报告文件（需通过 -o 参数指定）
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

    def mark_fund_sector_cli(self):
        """
        标记基金板块（命令行交互）。
        这是独立功能
        """
        now_codes = list(self.CACHE_MAP.keys())
        logger.debug(f"当前缓存基金代码: {now_codes}")
        logger.info("请输入基金代码, 多个基金代码以英文逗号分隔:")
        codes = input()
        codes = codes.split(",")
        codes = [code.strip() for code in codes if code.strip()]

        # 构建板块序号到名称的映射
        all_sectors = []
        for category, sectors in MAJOR_CATEGORIES.items():
            for sector in sectors:
                all_sectors.append(sector)

        # 表格形式展示板块分类
        logger.info("板块分类列表:")
        results = []
        for i in range(0, len(all_sectors), 5):
            tmp = all_sectors[i:i + 5]
            tmp = [f"{i + 1 + j}. {tmp[j]}" for j in range(len(tmp))]
            results.append(tmp)
        for line_msg in format_table_msg(results).split("\n"):
            logger.info(line_msg)

        for code in codes:
            try:
                if code not in self.CACHE_MAP:
                    logger.warning(f"标记板块【{code}】失败: 不存在该基金代码, 请先添加该基金代码")
                    continue

                # 选择板块
                logger.info(f"为基金 【{code} {self.CACHE_MAP[code]['fund_name']}】 选择板块:")
                logger.info("请输入板块序号或自定义板块名称 (多个用逗号分隔, 如: 1,3,5 或 新能源,医药 或 1,新能源):")
                sector_input = input().strip()

                if sector_input:
                    sector_items = [s.strip() for s in sector_input.split(",")]
                    selected_sectors = []
                    for item in sector_items:
                        # 尝试解析为序号
                        try:
                            idx = int(item)
                            if 1 <= idx <= len(all_sectors):
                                # 是有效序号，从板块列表中获取
                                selected_sectors.append(all_sectors[idx - 1])
                            else:
                                # 序号超出范围，当作自定义板块名称
                                selected_sectors.append(item)
                        except ValueError:
                            # 不是数字，直接作为自定义板块名称
                            selected_sectors.append(item)

                    if selected_sectors:
                        self.CACHE_MAP[code]["sectors"] = selected_sectors
                        logger.info(f"✓ 已绑定板块: {', '.join(selected_sectors)}")
                    else:
                        logger.info("未选择任何板块")
                else:
                    logger.info("未选择任何板块")

                logger.info(f"标记板块【{code}】成功")

            except Exception as e:
                logger.error(f"标记板块【{code}】失败: {e}")
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

    def unmark_fund_sector_cli(self):
        """
        删除基金板块标记（命令行交互）。
        """
        # 找出所有有板块标记的基金
        marked_codes = [code for code, data in self.CACHE_MAP.items() if data.get("sectors", [])]
        if not marked_codes:
            logger.warning("暂无板块标记的基金代码")
            return

        logger.debug(f"当前有板块标记的基金代码: {marked_codes}")
        logger.debug("请输入基金代码, 多个基金代码以英文逗号分隔:")
        codes = input()
        codes = codes.split(",")
        codes = [code.strip() for code in codes if code.strip()]

        for code in codes:
            try:
                if code in self.CACHE_MAP:
                    if self.CACHE_MAP[code].get("sectors", []):
                        self.CACHE_MAP[code]["sectors"] = []
                        logger.info(f"删除板块标记【{code}】成功")
                    else:
                        logger.warning(f"删除板块标记【{code}】失败: 该基金没有板块标记")
                else:
                    logger.warning(f"删除板块标记【{code}】失败: 不存在该基金代码")
            except Exception as e:
                logger.error(f"删除板块标记【{code}】失败: {e}")
        self.save_cache()

    def search_one_code(self, fund, fund_data, is_return, cancel_event=None):
        with self._refresh_semaphore:
            def is_cancelled():
                if cancel_event is not None and cancel_event.is_set():
                    logger.info(f"刷新已停止，跳过基金代码【{fund}】后续请求")
                    return True
                return False

            if is_cancelled():
                return
            try:
                fund_key = fund_data["fund_key"]
                fund_name = fund_data["fund_name"]

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
                # 最新净值来自 fund123 的基金详情接口（matiaria_tpl）。
                # 这里直接从响应文本中提取 netValue / netValueDate，供基金列表、持仓金额、
                # 以及 fund_server._get_latest_fund_quote() 复用。
                url = DATA_SOURCE_URLS['fund123_matiaria_tpl'].format(fund=fund)
                response = self._request_with_retries(
                    "GET",
                    url,
                    headers=headers,
                    verify=False,
                )
                if is_cancelled():
                    return
                day_growth_match = re.findall(r'"dayOfGrowth":"(.*?)"', response.text)
                net_value_match = re.findall(r'"netValue":"(.*?)"', response.text)
                net_value_date_match = re.findall(r'"netValueDate":"(.*?)"', response.text)
                if not day_growth_match or not net_value_match or not net_value_date_match:
                    logger.warning(f"查询基金代码【{fund}】详情响应格式异常，跳过该基金")
                    return

                dayOfGrowth = day_growth_match[0]
                dayOfGrowth = str(round(float(dayOfGrowth), 2)) + "%"

                netValue = net_value_match[0]
                netValueDate = net_value_date_match[0]
                # 先落库净值，再拼装显示字符串
                normalized_net_value_date = normalize_nav_date_for_storage(netValueDate)
                if self.db is not None and self.user_id is not None and self.nav_repo is not None and normalized_net_value_date:
                    net_value_float = float(netValue)
                    self.nav_repo.upsert_fund_nav_history(
                        fund, normalized_net_value_date, net_value_float, "fund123_latest"
                    )
                    self._ensure_recent_nav_history_on_refresh(fund, fund_key, normalized_net_value_date)
                netValueDate = normalized_net_value_date or netValueDate
                netValue = netValue + f"({netValueDate})"
                # 组合刷新只取净值和估值；业绩/趋势数据由图表接口在用户展开时按需加载。
                montly_growth_day = "N/A"
                montly_growth_day_count = 0
                montly_growth_rate = "N/A"
                consecutive_count = "N/A"
                consecutive_growth = "N/A"

                today = datetime.datetime.now().strftime("%Y-%m-%d")
                now_time = "N/A"
                forecastGrowth = "N/A"
                estimateDate = ""
                try:
                    latest_estimate = self.fetch_latest_intraday_estimate(fund_key, cancel_event=cancel_event)
                    if latest_estimate:
                        forecastGrowth = f"{latest_estimate['growth']}%"
                        now_time = latest_estimate["time"]
                        estimateDate = latest_estimate["date"]
                        if now_time == "15:00":
                            fund_cache = self.CACHE_MAP.get(fund, {})
                            new_history = {estimateDate: latest_estimate["growth"]}
                            if fund_cache.get("estimate_history", {}) != new_history:
                                fund_cache["estimate_history"] = new_history
                                self._cache_dirty = True
                except Fund123EndpointBlockedError as e:
                    logger.debug(f"基金【{fund}】估值1接口已熔断，使用 N/A: {e}")
                except Exception as e:
                    logger.warning(f"基金【{fund}】估值1请求失败: {e}")

                estimate2Growth = "N/A"
                estimate2Time = "N/A"
                estimate2Date = ""
                try:
                    if is_cancelled():
                        return
                    fundgz_client = getattr(self, "_fundgz_client", None)
                    if fundgz_client is None:
                        fundgz_client = FundGzClient(self._request_with_retries, DATA_SOURCE_URLS)
                    estimate2 = fundgz_client.fetch_latest_estimate(fund)
                    if is_cancelled():
                        return
                    if estimate2["growth"] is not None:
                        estimate2Growth = f"{estimate2['growth']}%"
                    estimate2Date = estimate2["date"]
                    estimate2Time = estimate2["time"]
                    gztime_raw = estimate2["quote_time"]
                    if gztime_raw:
                        # 估值2收盘缓存（仅当时间为15:00时入库），用于后续与净值日实际涨幅比较
                        try:
                            estimate2_dt = datetime.datetime.strptime(gztime_raw, "%Y-%m-%d %H:%M")
                            is_final_estimate2 = (estimate2_dt.hour == 15 and estimate2_dt.minute == 0)
                            if is_final_estimate2 and estimate2["growth"] is not None:
                                estimate2_key = estimate2_dt.strftime("%Y-%m-%d")
                                estimate2_val = estimate2["growth"]
                                fund_cache = self.CACHE_MAP.get(fund, {})
                                current_history2 = fund_cache.get("estimate_history_2", {})
                                new_history2 = {estimate2_key: estimate2_val}
                                if current_history2 != new_history2:
                                    fund_cache["estimate_history_2"] = new_history2
                                    self._cache_dirty = True
                        except Exception:
                            pass
                except Exception as e:
                    logger.warning(f"基金【{fund}】最新估值请求失败: {e}")
                if estimate2Date and estimate2Date != today:
                    logger.debug(f"基金代码【{fund}】使用最近交易日估值: {estimate2Date}，当前日期: {today}")

                if not is_return:
                    if forecastGrowth != "N/A":
                        if "-" in forecastGrowth:
                            forecastGrowth = "\033[1;32m" + forecastGrowth
                        else:
                            forecastGrowth = "\033[1;31m" + forecastGrowth
                    if "-" in dayOfGrowth:
                        dayOfGrowth = "\033[1;32m" + dayOfGrowth
                    else:
                        dayOfGrowth = "\033[1;31m" + dayOfGrowth
                    if estimate2Growth != "N/A":
                        if "-" in estimate2Growth:
                            estimate2Growth = "\033[1;32m" + estimate2Growth
                        else:
                            estimate2Growth = "\033[1;31m" + estimate2Growth
                if self.CACHE_MAP[fund].get("is_hold", False):
                    fund_name = "⭐ " + fund_name
                sectors = self.CACHE_MAP[fund].get("sectors", [])
                if sectors:
                    sector_display = ", ".join(sectors)
                    if is_return:
                        fund_name = f"{fund_name} <span style='color: #8b949e; font-size: 12px;'>🏷️ {sector_display}</span>"
                    else:
                        fund_name = f"({sector_display}) {fund_name}"
                consecutive_info = f"{consecutive_count}天 {consecutive_growth}"
                monthly_info = f"{montly_growth_day}/{montly_growth_day_count} {montly_growth_rate}"
                self.result.append([
                    fund, fund_name, now_time, netValue, forecastGrowth, dayOfGrowth, netValueDate, consecutive_info,
                    monthly_info, estimateDate, estimate2Growth, estimate2Time, estimate2Date
                ])
            except Exception as e:
                logger.error(f"查询基金代码【{fund}】失败: {e}")

    def search_code(self, is_return=False, cancel_event=None):
        self._cache_dirty = False
        self.result = []
        configured_worker_count = get_fund_refresh_config().get('request_batch_size', 5)
        self._refresh_semaphore = threading.Semaphore(configured_worker_count)
        refresh_service = getattr(self, "_refresh_service", None) or FundRefreshService()
        refresh_result = refresh_service.refresh(
            self.CACHE_MAP,
            configured_worker_count,
            lambda fund, fund_data: self.search_one_code(
                fund, fund_data, is_return, cancel_event
            ),
            cancel_event=cancel_event,
        )
        worker_count = refresh_result["worker_count"]

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

        if is_return:
            self.result = sorted(
                self.result,
                key=lambda x: float(x[4].replace("%", "")) if x[4] != "N/A" else -99,
                reverse=True
            )
            return self.result

        if self.result:
            self.result = sorted(
                self.result,
                key=lambda x: float(x[4].split("m")[1].replace("%", "")) if x[4] != "N/A" else -99,
                reverse=True
            )

            # 计算并显示持仓统计
            position_summary = self.calculate_position_summary()
            if position_summary:
                # 收益统计表格
                logger.critical(f"{time.strftime('%Y-%m-%d %H:%M')} 收益统计:")

                # 准备表格数据
                total_value = position_summary['total_value']
                est_gain = position_summary['estimated_gain']
                est_gain_pct = position_summary['estimated_gain_pct']
                act_gain = position_summary['actual_gain']
                act_gain_pct = position_summary['actual_gain_pct']
                settled_value = position_summary.get('settled_value', 0)

                est_color = '\033[1;31m' if est_gain >= 0 else '\033[1;32m'
                act_color = '\033[1;31m' if act_gain >= 0 else '\033[1;32m'
                est_sign = '+' if est_gain >= 0 else ''
                act_sign = '+' if act_gain >= 0 else ''

                # 今日实际涨跌：只有当有基金净值更新至今日时才显示数值
                if settled_value > 0:
                    actual_gain_str = f"{act_color}{act_sign}¥{act_gain:,.2f} ({act_sign}{act_gain_pct:.2f}%)\033[0m"
                else:
                    actual_gain_str = "\033[1;90m净值未更新\033[0m"  # 灰色显示

                summary_table = [
                    ["总持仓金额", f"¥{total_value:,.2f}"],
                    ["今日预估涨跌", f"{est_color}{est_sign}¥{est_gain:,.2f} ({est_sign}{est_gain_pct:.2f}%)\033[0m"],
                    ["今日实际涨跌", actual_gain_str],
                ]

                for line_msg in format_table_msg(summary_table).split("\n"):
                    logger.info(line_msg)

                # 显示每个基金的详细涨跌（表格格式）
                if 'fund_details' in position_summary and position_summary['fund_details']:
                    logger.critical(f"{time.strftime('%Y-%m-%d %H:%M')} 分基金涨跌明细:")

                    # 准备表格数据
                    table_data = []
                    for detail in position_summary['fund_details']:
                        est_color = '\033[1;31m' if detail['estimated_gain'] >= 0 else '\033[1;32m'
                        act_color = '\033[1;31m' if detail['actual_gain'] >= 0 else '\033[1;32m'
                        est_sign = '+' if detail['estimated_gain'] >= 0 else ''
                        act_sign = '+' if detail['actual_gain'] >= 0 else ''

                        table_data.append([
                            detail['code'],
                            detail['name'],
                            f"{detail['shares']:,.2f}",
                            f"¥{detail['position_value']:,.2f}",
                            f"{est_color}{est_sign}¥{detail['estimated_gain']:,.2f}\n"
                            f"{est_sign}{detail['estimated_gain_pct']:.2f}%\033[0m",
                            f"{act_color}{act_sign}¥{detail['actual_gain']:,.2f}\n"
                            f"{act_sign}{detail['actual_gain_pct']:.2f}%\033[0m",
                        ])

                    for line_msg in format_table_msg([
                        ["基金代码", "基金名称", "持仓份额", "持仓市值", "预估收益", "实际收益"],
                        *table_data
                    ]).split("\n"):
                        logger.info(line_msg)

            # CLI模式删除净值列，避免表格过宽
            cli_result = [[row[0], row[1], row[2], row[4], row[5], row[6], row[7]] for row in self.result]
            logger.critical(f"{time.strftime('%Y-%m-%d %H:%M')} 基金估值信息:")
            for line_msg in format_table_msg([
                [
                    "基金代码", "基金名称", "时间", "估值", "日涨幅", "连涨/跌", "近30天"
                ],
                *cli_result
            ]).split("\n"):
                logger.info(line_msg)

    def calculate_position_summary(self):
        """计算持仓统计信息（CLI 输出用，委托给独立函数）。"""
        from src.fund_table import calculate_position_summary
        return calculate_position_summary(self.result, self.CACHE_MAP, self.db, self.user_id)

    def modify_shares(self):
        """修改基金持仓份额（CLI交互式）"""
        now_codes = list(self.CACHE_MAP.keys())
        if not now_codes:
            logger.warning("暂无基金代码，请先添加基金")
            return

        logger.info("当前基金列表:")
        for code, data in self.CACHE_MAP.items():
            shares = data.get('shares', 0)
            logger.info(f"  {code} - {data['fund_name']} (当前份额: {shares})")

        logger.info("\n请输入基金代码, 多个基金代码以英文逗号分隔:")
        codes = input()
        codes = codes.split(",")
        codes = [code.strip() for code in codes if code.strip()]

        for code in codes:
            try:
                if code not in self.CACHE_MAP:
                    logger.warning(f"修改份额【{code}】失败: 不存在该基金代码, 请先添加该基金代码")
                    continue

                fund_name = self.CACHE_MAP[code]['fund_name']
                current_shares = self.CACHE_MAP[code].get('shares', 0)

                logger.info(f"\n基金 【{code} {fund_name}】")
                logger.info(f"当前份额: {current_shares}")
                logger.info("请输入新的份额数量 (输入0表示清空):")
                shares_input = input().strip()

                if shares_input:
                    try:
                        shares = float(shares_input)
                        if shares < 0:
                            logger.warning("份额不能为负数")
                            continue

                        self.CACHE_MAP[code]['shares'] = shares

                        # 如果份额>0，自动标记为持有
                        if shares > 0:
                            self.CACHE_MAP[code]['is_hold'] = True

                        logger.info(f"✓ 已更新份额: {shares}")
                    except ValueError:
                        logger.warning("份额格式错误，请输入数字")
                        continue
                else:
                    logger.info("未输入份额，跳过")

            except Exception as e:
                logger.error(f"修改份额【{code}】失败: {e}")

        self.save_cache()
        logger.info("\n份额修改完成")

    def build_fund_table(self, cancel_event=None):
        from src.fund_table import build_fund_table
        return build_fund_table(self, cancel_event=cancel_event)

    def select_fund(self, bk_id=None, is_return=False):
        return fetch_select_fund(bk_id, is_return)


    def run(self, is_add=False, is_delete=False, is_hold=False, is_not_hold=False, report_dir=None,
            deep_mode=False, fast_mode=False, with_ai=False, select_mode=False, mark_sector=False, unmark_sector=False,
            modify_shares=False):
        """
        高层入口：根据参数执行数据更新、添加、删除、持有标记、AI分析等。
        记录整体耗时日志（仅输出到终端）。
        """
        import time
        start = time.perf_counter()

        try:
            if select_mode:
                self.select_fund()
                return

            # 处理修改份额功能
            if modify_shares:
                self.modify_shares()
                return

            # 处理标记板块功能
            if mark_sector:
                self.mark_fund_sector_cli()
                return

            # 处理删除标记板块功能
            if unmark_sector:
                self.unmark_fund_sector_cli()
                return

            # 存储报告目录到实例属性（None 表示不保存报告文件）
            self.report_dir = report_dir

            if not self.CACHE_MAP:
                logger.warning("暂无缓存代码信息, 请先添加基金代码")
                is_add = True
                is_delete = False
                is_hold = False
                is_not_hold = False
            if is_not_hold:
                hold_codes = [code for code, data in self.CACHE_MAP.items() if data.get("is_hold", False)]
                if not hold_codes:
                    logger.warning("暂无持有标注基金代码")
                    return
                logger.debug(f"当前持有标注基金代码: {hold_codes}")
                logger.debug("请输入基金代码, 多个基金代码以英文逗号分隔:")
                codes = input()
                codes = codes.split(",")
                codes = [code.strip() for code in codes if code.strip()]
                for code in codes:
                    try:
                        if code in self.CACHE_MAP:
                            self.CACHE_MAP[code]["is_hold"] = False
                            logger.info(f"删除持有标注【{code}】成功")
                        else:
                            logger.warning(f"删除持有标注【{code}】失败: 不存在该基金代码")
                    except Exception as e:
                        logger.error(f"删除持有标注【{code}】失败: {e}")
                self.save_cache()
                return
            if is_hold:
                now_codes = list(self.CACHE_MAP.keys())
                logger.debug(f"当前缓存基金代码: {now_codes}")
                logger.info("请输入基金代码, 多个基金代码以英文逗号分隔:")
                codes = input()
                codes = codes.split(",")
                codes = [code.strip() for code in codes if code.strip()]

                for code in codes:
                    try:
                        if code not in self.CACHE_MAP:
                            logger.warning(f"添加持有标注【{code}】失败: 不存在该基金代码, 请先添加该基金代码")
                            continue

                        self.CACHE_MAP[code]["is_hold"] = True
                        logger.info(f"添加持有标注【{code}】成功")

                    except Exception as e:
                        logger.error(f"添加持有标注【{code}】失败: {e}")
                self.save_cache()
                return

            if is_delete:
                now_codes = list(self.CACHE_MAP.keys())
                logger.debug(f"当前缓存基金代码: {now_codes}")
                logger.debug("请输入基金代码, 多个基金代码以英文逗号分隔:")
                codes = input()
                self.delete_code(codes)
                logger.success("删除基金代码成功")
                if not is_add:
                    return
            if is_add:
                logger.debug("请输入基金代码, 多个基金代码以英文逗号分隔:")
                codes = input()
                self.add_code(codes)
                logger.success("添加基金代码成功")
            else:
                self.bk()
                self.search_code()
                if with_ai:
                    self.ai_analysis(deep_mode=deep_mode, fast_mode=fast_mode)
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            print(f"[FUNC] MiniFund.run total_elapsed_ms={elapsed:.1f}")

    def bk(self, is_return=False):
        return fetch_bk(is_return)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='MiniFund')
    parser.add_argument('-a', '--add', action='store_true', help='添加基金代码')
    parser.add_argument("-d", "--delete", action="store_true", help="删除基金代码")
    parser.add_argument("-c", "--hold", action="store_true", help="添加持有基金标注")
    parser.add_argument("-b", "--not_hold", action="store_true", help="删除持有基金标注")
    parser.add_argument("-e", "--mark_sector", action="store_true", help="标记板块")
    parser.add_argument("-u", "--unmark_sector", action="store_true", help="删除标记板块")
    parser.add_argument("-s", "--select", action="store_true", help="选择板块查看基金列表")
    parser.add_argument("-m", "--modify-shares", action="store_true", help="修改基金持仓份额")
    parser.add_argument("-o", "--output", type=str, nargs='?', const="reports", default=None,
                        help="输出AI分析报告到指定目录（默认: reports）。只有使用此参数时才会保存报告文件")
    parser.add_argument("-f", "--fast", action="store_true", help="启用快速分析模式")
    parser.add_argument("-D", "--deep", action="store_true", help="启用深度研究模式")
    parser.add_argument("-W", "--with-ai", action="store_true", help="AI分析")
    args = parser.parse_args()

    lan_fund = MiniFund()
    # 只有指定了 -o 参数时才传入 report_dir，否则传入 None 表示不保存报告
    report_dir = args.output if args.output is not None else None
    lan_fund.run(args.add, args.delete, args.hold, args.not_hold, report_dir, args.deep, args.fast, args.with_ai,
                 args.select, args.mark_sector, args.unmark_sector, args.modify_shares)
