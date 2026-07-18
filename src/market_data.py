# -*- coding: UTF-8 -*-
"""Standalone market data functions extracted from MiniFund."""

import json
import random

import requests

from src.data.bk_map import BK_MAP
from src.config.yaml_config import get_data_source_urls

DATA_SOURCE_URLS = get_data_source_urls()


# ------------------------------------------------------------------
# Sector / board data
# ------------------------------------------------------------------

def fetch_bk():
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
                add_market_cap = bk["f62"]
                add_market_cap = str(round(add_market_cap / 100000000, 2)) + "亿"
                add_market_cap2 = bk["f84"]
                add_market_cap2 = str(round(add_market_cap2 / 100000000, 2)) + "亿"
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
        key=lambda x: float(x[1].replace("%", "")) if x[3] != "N/A" else -99,
        reverse=True
    )
    return bk_result


# ------------------------------------------------------------------
# Fund selection by sector
# ------------------------------------------------------------------

def fetch_select_fund(bk_id=None):
    """Fetch funds by sector from Eastmoney API."""
    bk_map = BK_MAP
    bk_list = list(bk_map.keys())

    if bk_id is None:
        return {"bk_map": bk_map, "bk_list": bk_list}

    id_map = {
        str(index): bk_map[name]
        for index, name in enumerate(bk_list, start=1)
    }

    if bk_id not in id_map:
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

    return {
        "bk_id": bk_id,
        "bk_name": list(bk_map.keys())[int(bk_id) - 1] if bk_id.isdigit() else bk_id,
        "results": fund_results
    }
