"""Build one portfolio quote row from remote provider responses."""

import datetime
import re

from loguru import logger

from src.providers import Fund123EndpointBlockedError, FundGzClient


class FundQuoteWorker:
    def __init__(self, urls, normalize_nav_date):
        self._urls = urls
        self._normalize_nav_date = normalize_nav_date

    def refresh_one(self, owner, fund, fund_data, is_return, cancel_event=None):
        with owner._refresh_semaphore:
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
                    "Origin": self._urls['fund123_origin'],
                    "Referer": self._urls['fund123_fund_page'],
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                    "X-API-Key": "foobar",
                    "accept": "json"
                }
                # 最新净值来自 fund123 的基金详情接口（matiaria_tpl）。
                # 这里直接从响应文本中提取 netValue / netValueDate，供基金列表、持仓金额、
                # 以及 fund_server._get_latest_fund_quote() 复用。
                url = self._urls['fund123_matiaria_tpl'].format(fund=fund)
                response = owner._request_with_retries(
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
                normalized_net_value_date = self._normalize_nav_date(netValueDate)
                if owner.db is not None and owner.user_id is not None and owner.nav_repo is not None and normalized_net_value_date:
                    net_value_float = float(netValue)
                    owner.nav_repo.upsert_fund_nav_history(
                        fund, normalized_net_value_date, net_value_float, "fund123_latest"
                    )
                    owner._ensure_recent_nav_history_on_refresh(fund, fund_key, normalized_net_value_date)
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
                    latest_estimate = owner.fetch_latest_intraday_estimate(fund_key, cancel_event=cancel_event)
                    if latest_estimate:
                        forecastGrowth = f"{latest_estimate['growth']}%"
                        now_time = latest_estimate["time"]
                        estimateDate = latest_estimate["date"]
                        if now_time == "15:00":
                            fund_cache = owner.CACHE_MAP.get(fund, {})
                            new_history = {estimateDate: latest_estimate["growth"]}
                            if fund_cache.get("estimate_history", {}) != new_history:
                                fund_cache["estimate_history"] = new_history
                                owner._cache_dirty = True
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
                        fundgz_client = FundGzClient(owner._request_with_retries, self._urls)
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
                                fund_cache = owner.CACHE_MAP.get(fund, {})
                                current_history2 = fund_cache.get("estimate_history_2", {})
                                new_history2 = {estimate2_key: estimate2_val}
                                if current_history2 != new_history2:
                                    fund_cache["estimate_history_2"] = new_history2
                                    owner._cache_dirty = True
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
                if owner.CACHE_MAP[fund].get("is_hold", False):
                    fund_name = "⭐ " + fund_name
                sectors = owner.CACHE_MAP[fund].get("sectors", [])
                if sectors:
                    sector_display = ", ".join(sectors)
                    if is_return:
                        fund_name = f"{fund_name} <span style='color: #8b949e; font-size: 12px;'>🏷️ {sector_display}</span>"
                    else:
                        fund_name = f"({sector_display}) {fund_name}"
                consecutive_info = f"{consecutive_count}天 {consecutive_growth}"
                monthly_info = f"{montly_growth_day}/{montly_growth_day_count} {montly_growth_rate}"
                owner.result.append([
                    fund, fund_name, now_time, netValue, forecastGrowth, dayOfGrowth, netValueDate, consecutive_info,
                    monthly_info, estimateDate, estimate2Growth, estimate2Time, estimate2Date
                ])
            except Exception as e:
                logger.error(f"查询基金代码【{fund}】失败: {e}")
