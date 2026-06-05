# -*- coding: UTF-8 -*-
"""Standalone market data functions extracted from MiniFund."""

import json
import random
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

