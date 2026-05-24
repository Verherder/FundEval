# -*- coding: UTF-8 -*-
"""Standalone market data functions extracted from LanFund.

Each function takes explicit parameters (session, is_return, etc.) so both
LanFund (CLI) and MarketService (web) can use them without coupling.
"""

import datetime
import json
import random
import re
import time

import requests
from loguru import logger
from tabulate import tabulate

from src.data.bk_map import BK_MAP
from src.config.yaml_config import get_data_source_urls

DATA_SOURCE_URLS = get_data_source_urls()


def format_table_msg(table, tablefmt="pretty"):
    return tabulate(table, tablefmt=tablefmt, missingval="N/A")


# ------------------------------------------------------------------
# Sector / board data
# ------------------------------------------------------------------

def fetch_bk(is_return=False):
    """Fetch Eastmoney sector/board data."""
    bk_result = []
    try:
        url = DATA_SOURCE_URLS['eastmoney_bk_api']
        params = {
            "cb": "",
            "fid": "f62",
            "po": "1",
            "pz": "100",
            "pn": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "ut": "8dec03ba335b81bf4ebdf7b29ec27d15",
            "fs": "m:90 t:2",
            "fields": "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124,f1,f13"
        }
        response = requests.get(
            url,
            params=params,
            timeout=10,
            verify=False,
        )
        if str(response.json()["data"]):
            data = response.json()["data"]
            for bk in data["diff"]:
                ratio = str(bk["f3"]) + "%"
                if not is_return:
                    if "-" in ratio:
                        ratio = "\033[1;32m" + ratio
                    else:
                        ratio = "\033[1;31m" + ratio
                add_market_cap = bk["f62"]
                add_market_cap = str(round(add_market_cap / 100000000, 2)) + "亿"
                if not is_return:
                    if "-" in add_market_cap:
                        add_market_cap = "\033[1;32m" + add_market_cap
                    else:
                        add_market_cap = "\033[1;31m" + add_market_cap
                add_market_cap2 = bk["f84"]
                add_market_cap2 = str(round(add_market_cap2 / 100000000, 2)) + "亿"
                if not is_return:
                    if "-" in add_market_cap2:
                        add_market_cap2 = "\033[1;32m" + add_market_cap2
                    else:
                        add_market_cap2 = "\033[1;31m" + add_market_cap2
                bk_result.append([
                    bk["f14"],
                    ratio,
                    add_market_cap,
                    str(round(bk["f184"], 2)) + "%",
                    add_market_cap2,
                    str(round(bk["f87"], 2)) + "%",
                ])
    except Exception:
        pass

    bk_result = sorted(
        bk_result,
        key=lambda x: float(x[1].split("m")[-1].replace("%", "")) if x[3] != "N/A" else -99,
        reverse=True
    )
    if is_return:
        return bk_result
    if bk_result:
        logger.critical(f"{time.strftime('%Y-%m-%d %H:%M')} 行业板块:")
        for line_msg in format_table_msg([
            [
                "板块名称", "今日涨跌幅", "今日主力净流入", "今日主力净流入占比", "今日小单净流入", "今日小单流入占比"
            ],
            *bk_result
        ]).split("\n"):
            logger.info(line_msg)


# ------------------------------------------------------------------
# Fund selection by sector
# ------------------------------------------------------------------

def fetch_select_fund(bk_id=None, is_return=False):
    """Fetch funds by sector from Eastmoney API."""
    if not is_return:
        logger.critical("板块基金查询功能")
    bk_map = BK_MAP
    bk_list = list(bk_map.keys())

    if is_return and bk_id is None:
        return {"bk_map": bk_map, "bk_list": bk_list}

    results = []
    id_map = {}
    for i in range(0, len(bk_list), 5):
        tmp = bk_list[i:i + 5]
        tmp = [str(i + 1 + j) + ". " + tmp[j] for j in range(len(tmp))]
        for j in range(len(tmp)):
            id_map[str(i + 1 + j)] = bk_map[bk_list[i + j]]
        results.append(tmp)

    if not is_return:
        for line_msg in format_table_msg(results).split("\n"):
            logger.info(line_msg)

        logger.debug("请输入要查询的板块序号(单选):")
        bk_id = input()
        while bk_id not in id_map:
            logger.error("输入有误, 请重新输入要查询的板块序号:")
            bk_id = input()

    if is_return and bk_id not in id_map:
        if bk_id in bk_map:
            bk_code = bk_map[bk_id]
        else:
            return {"error": "无效的板块ID或名称"}
    else:
        bk_code = id_map[bk_id]

    url = DATA_SOURCE_URLS['eastmoney_fundguide_api']

    params = {
        "dt": "4",
        "sd": "",
        "ed": "",
        "tp": bk_code,
        "sc": "1n",
        "st": "desc",
        "pi": "1",
        "pn": "1000",
        "zf": "diy",
        "sh": "list",
        "rnd": str(random.random())
    }

    headers = {
        "Connection": "keep-alive",
        "Referer": DATA_SOURCE_URLS['eastmoney_fundguide_referer'],
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "sec-ch-ua": "\"Google Chrome\";v=\"143\", \"Chromium\";v=\"143\", \"Not A(Brand\";v=\"24\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\""
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30,
    )
    text = json.loads(response.text.replace("var rankData =", "").strip())
    datas = text["datas"]
    fund_results = []
    for data in datas:
        data_list = data.split(",")
        fund_results.append([
            (data_list[0] or "---"),
            (data_list[1] or "---"),
            (data_list[3] or "---"),
            (data_list[15] or "---"),
            (data_list[16] or "---"),
            (data_list[17] or "---") + "%",
            (data_list[5] or "---") + "%",
            (data_list[6] or "---") + "%",
            (data_list[7] or "---") + "%",
            (data_list[8] or "---") + "%",
            (data_list[4] or "---") + "%",
            (data_list[9] or "---") + "%",
            (data_list[10] or "---") + "%",
            (data_list[11] or "---") + "%",
            (data_list[24] or "---") + "%"
        ])

    if is_return:
        return {
            "bk_id": bk_id,
            "bk_name": list(bk_map.keys())[int(bk_id) - 1] if bk_id.isdigit() else bk_id,
            "results": fund_results
        }

    logger.critical(f"板块【{bk_id}. {list(bk_map.keys())[int(bk_id) - 1]}】基金列表:")
    for line_msg in format_table_msg([
        [
            "基金代码", "基金名称", "基金类型", "日期", "净值|日增长率", "近1周", "近1月", "近3月", "近6月",
            "今年来", "近1年", "近2年", "近3年", "成立以来"
        ],
        *fund_results
    ]).split("\n"):
        logger.info(line_msg)


# ------------------------------------------------------------------
# Baidu-session-dependent market functions
# ------------------------------------------------------------------

def fetch_kx(baidu_session, is_return=False, count=10):
    """Fetch 7x24 news from Baidu API."""
    url = DATA_SOURCE_URLS['baidu_expressnews_tpl'].format(count=count)
    kx_list = []
    try:
        response = baidu_session.get(url, timeout=10, verify=False)
        if response.json()["ResultCode"] == "0":
            kx_list = response.json()["Result"]["content"]["list"]
    except Exception:
        pass

    if is_return:
        return kx_list

    if kx_list:
        logger.critical(f"{time.strftime('%Y-%m-%d %H:%M')} 7*24 快讯:")
        for i, v in enumerate(kx_list):
            evaluate = v.get("evaluate", "")
            if evaluate == "利好":
                pre = "\033[1;31m"
            elif evaluate == "利空":
                pre = "\033[1;32m"
            else:
                pre = ""
            title = v.get("title", v["content"]["items"][0]["data"])
            publish_time = v["publish_time"]
            publish_time = datetime.datetime.fromtimestamp(int(publish_time)).strftime("%Y-%m-%d %H:%M:%S")
            entity = v.get("entity", [])
            entity = ", ".join([f"{x['code'].strip()}-{x['name'].strip()} {x['ratio'].strip()}" for x in entity])
            logger.info(f"{pre}{i + 1}. {publish_time} {title}.")
            if entity:
                logger.debug(f"影响股票: {entity}.")


def fetch_A(baidu_session, is_return=False):
    """Fetch Shanghai index minute data from Baidu API."""
    url = DATA_SOURCE_URLS['baidu_getquotation_api']
    params = {
        "srcid": "5353",
        "all": "1",
        "pointType": "string",
        "group": "quotation_index_minute",
        "query": "000001",
        "code": "000001",
        "market_type": "ab",
        "newFormat": "1",
        "name": "上证指数",
        "finClientType": "pc"
    }
    response = baidu_session.get(
        url,
        params=params,
        timeout=10,
        verify=False,
    )
    try:
        if str(response.json()["ResultCode"]) == "0":
            marketData = response.json()["Result"]["newMarketData"]["marketData"][0]["p"]
            if not is_return:
                marketData = marketData.split(";")[-30:]
            else:
                marketData = marketData.split(";")
            marketData = [x.split(",")[1:] for x in marketData]
            if marketData:
                result = []
                for i in marketData:
                    if not is_return:
                        if "+" in i[2]:
                            i[1] = "\033[1;31m" + i[1]
                        else:
                            i[1] = "\033[1;32m" + i[1]
                    i[3] = i[3] + "%"
                    try:
                        i[4] = str(round(float(float(i[4]) / 10000), 2)) + "万手"
                        i[5] = str(round(float(float(i[5]) / 10000 / 10000), 2)) + "亿"
                    except Exception:
                        pass
                    result.append(i[:-2])
                if is_return:
                    return result
                logger.critical(f"{time.strftime('%Y-%m-%d %H:%M')} 近 30 分钟上证指数:")
                for line_msg in format_table_msg([
                    [
                        "时间", "指数", "涨跌额", "涨跌幅", "成交量", "成交额"
                    ],
                    *result
                ]).split("\n"):
                    logger.info(line_msg)
    except Exception as e:
        logger.error(f"获取上证指数信息失败: {e}")


def fetch_seven_A(baidu_session, is_return=False):
    """Fetch 7-day volume data from Baidu API."""
    url = DATA_SOURCE_URLS['baidu_metrictrend_api']
    params = {
        "financeType": "index",
        "market": "ab",
        "code": "000001",
        "targetType": "market",
        "metric": "amount",
        "finClientType": "pc"
    }
    try:
        response = baidu_session.get(
            url,
            params=params,
            timeout=10,
            verify=False,
        )
        if str(response.json()["ResultCode"]) == "0":
            trend = response.json()["Result"]["trend"]
            result = []
            today = datetime.datetime.now()
            dates = [(today - datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(8)]
            for i in dates:
                total = trend[0]
                ss = trend[1]
                sz = trend[2]
                bj = trend[3]
                total_data = [x for x in total["content"] if x["marketDate"] == i]
                ss_data = [x for x in ss["content"] if x["marketDate"] == i]
                sz_data = [x for x in sz["content"] if x["marketDate"] == i]
                bj_data = [x for x in bj["content"] if x["marketDate"] == i]
                if total_data and ss_data and sz_data and bj_data:
                    total_amount = total_data[0]["data"]["amount"] + "亿"
                    ss_amount = ss_data[0]["data"]["amount"] + "亿"
                    sz_amount = sz_data[0]["data"]["amount"] + "亿"
                    bj_amount = bj_data[0]["data"]["amount"] + "亿"
                    result.append([
                        i, total_amount, ss_amount, sz_amount, bj_amount
                    ])

            if is_return:
                return result
            if result:
                logger.critical(f"{time.strftime('%Y-%m-%d %H:%M')} 近 7 日成交量:")
                for line_msg in format_table_msg([
                    [
                        "日期", "总成交额", "上交所", "深交所", "北交所"
                    ],
                    *result
                ]).split("\n"):
                    logger.info(line_msg)
    except Exception as e:
        logger.error(f"获取近七日成交量信息失败: {e}")


def fetch_market_info(baidu_session, is_return=False):
    """Fetch global market indices from Baidu API."""
    result = []
    try:
        markets = ["asia", "america"]
        for market in markets:
            url = DATA_SOURCE_URLS['baidu_getbanner_tpl'].format(market=market)
            response = baidu_session.get(url, timeout=10, verify=False)
            if response.json()["ResultCode"] == "0":
                market_list = response.json()["Result"]["list"]
                for market_info in market_list:
                    ratio = market_info["ratio"]
                    if not is_return:
                        if "-" in ratio:
                            ratio = "\033[1;32m" + ratio
                        else:
                            ratio = "\033[1;31m" + ratio
                    result.append([
                        market_info["name"],
                        market_info["lastPrice"],
                        ratio
                    ])

        # 增加创业板指
        url = DATA_SOURCE_URLS['baidu_getquotation_api']
        params = {
            "srcid": "5353",
            "all": "1",
            "pointType": "string",
            "group": "quotation_index_minute",
            "query": "399006",
            "code": "399006",
            "market_type": "ab",
            "newFormat": "1",
            "name": "创业板指",
            "finClientType": "pc"
        }
        response = baidu_session.get(
            url,
            params=params,
            timeout=10,
            verify=False,
        )
        if str(response.json()["ResultCode"]) == "0":
            cur = response.json()["Result"]["cur"]
            ratio = cur["ratio"]
            if not is_return:
                if "-" in ratio:
                    ratio = "\033[1;32m" + ratio
                else:
                    ratio = "\033[1;31m" + ratio
            result.insert(2, [
                "创业板指",
                cur["price"],
                ratio
            ])
    except Exception as e:
        logger.error(f"获取市场信息失败: {e}")
    if is_return:
        return result
    if result:
        logger.critical(f"{time.strftime('%Y-%m-%d %H:%M')} 市场信息:")
        for line_msg in format_table_msg([
            [
                "指数名称", "指数", "涨跌幅"
            ],
            *result
        ]).split("\n"):
            logger.info(line_msg)


def fetch_market_chart_data(baidu_session):
    """Return global market index chart data (for frontend Chart.js)."""
    result = fetch_market_info(baidu_session, is_return=True)
    labels = [item[0] for item in result] if result else []
    prices = []
    changes = []
    for item in result:
        try:
            price = float(item[1]) if item[1] else 0
            change_str = item[2] if item[2] else "0%"
            change_str = change_str.replace('%', '').replace('\033[1;31m', '').replace('\033[1;32m', '')
            change = float(change_str)
        except Exception:
            price = 0
            change = 0
        prices.append(price)
        changes.append(change)
    return {
        'labels': labels,
        'prices': prices,
        'changes': changes
    }


def fetch_volume_chart_data(baidu_session):
    """Return volume chart data (for frontend Chart.js)."""
    result = fetch_seven_A(baidu_session, is_return=True)
    labels = []
    total_data = []
    ss_data = []
    sz_data = []
    bj_data = []
    for item in result:
        try:
            labels.append(item[0])
            total = float(item[1].replace('亿', '')) if item[1] else 0
            ss = float(item[2].replace('亿', '')) if item[2] else 0
            sz = float(item[3].replace('亿', '')) if item[3] else 0
            bj = float(item[4].replace('亿', '')) if item[4] else 0
            total_data.append(total)
            ss_data.append(ss)
            sz_data.append(sz)
            bj_data.append(bj)
        except Exception:
            continue
    return {
        'labels': labels[::-1],
        'total': total_data[::-1],
        'sh': ss_data[::-1],
        'sz': sz_data[::-1],
        'bj': bj_data[::-1]
    }


def fetch_timing_chart_data(baidu_session):
    """Return Shanghai index intraday chart data (for frontend Chart.js)."""
    result = fetch_A(baidu_session, is_return=True)
    labels = []
    prices = []
    change_pcts = []
    change_amounts = []
    volumes = []
    amounts = []
    for item in result:
        try:
            labels.append(item[0])
            price = float(item[1]) if item[1] else 0
            pct_str = item[3].replace('%', '') if len(item) > 3 and item[3] else '0'
            pct = float(pct_str)
            change_amt = float(item[2]) if len(item) > 2 and item[2] else 0
            vol_str = item[4].replace('万手', '').replace(',', '') if len(item) > 4 and item[4] else '0'
            volume = float(vol_str)
            amt_str = item[5].replace('亿', '').replace(',', '') if len(item) > 5 and item[5] else '0'
            amount = float(amt_str)
            prices.append(price)
            change_pcts.append(pct)
            change_amounts.append(change_amt)
            volumes.append(volume)
            amounts.append(amount)
        except Exception:
            continue
    return {
        'labels': labels,
        'prices': prices,
        'change_pcts': change_pcts,
        'change_amounts': change_amounts,
        'volumes': volumes,
        'amounts': amounts
    }
