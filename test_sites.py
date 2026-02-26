
import json
import os
import random
import re
import threading
import time

import requests
import urllib3
from curl_cffi import requests as curl_requests
from src.http_timing import timed_http_request
from loguru import logger


# baidu_session = curl_requests.Session(impersonate="chrome")
baidu_session = requests.Session()
baidu_session.headers = {
    "accept": "application/vnd.finance-web.v1+json",
    "accept-language": "zh-CN,zh;q=0.9",
    "acs-token": "1769925606098_1770001866425_B6lkFxZg0PzQhmCXjMfTJUxYBn+en+J7W6a8XGyGMqfxPfIv2RgeZG8wimRzlhAxlZlErxq7wN5rVnCfPj6s/UNiA1a1hfyItpnMrru1lzDxUcicsi2ngKjmVCdUfqRZTcHPnfDWrt4phJcS7Ue+Sh6Ru/GVG+1McDUmf/d52zDv5Q6QM7CAJfHDqsCMP65SNjo63Xljm+aAIzDzKErfG+LOR706MJaZGY2o/hGcESyOy3FcWv+pYNFUjpV3M5sMFNEDa50fWh4J9PZpQDxDQLNhr9LSYunQUxe6wtNEGds85p9V6/yU6v+jA9q0h9/OyQJ/ZuD1lP0VPEACEc4qJvfItxhuK9MfKM+j6Spc/N6Qomh6pZYt6iLJjJp652xIqZurCmxem2Z3Vqu+mcZ9FN1l0qU6dx4hkaTZk3850FE/n6YW+HL74Mp8L+YR/Q2VMV3ARkSzPHgOS9iA6rBAaBiJf2Ni/BTHNSyFxJJjazI=",
    "origin": "https://gushitong.baidu.com",
    "priority": "u=1, i",
    "referer": "https://gushitong.baidu.com/",
    "sec-ch-ua": "\"Google Chrome\";v=\"143\", \"Chromium\";v=\"143\", \"Not A(Brand\";v=\"24\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
    }
        

# 百度行情预热：可能因 DNS/网络失败，但不影响主流程
try:
    # timed_http_request(
    #     baidu_session,
    #     "GET",
    #     "https://gushitong.baidu.com/index/ab-000001",
    #     source="baidu",
    #     headers={
    #         "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    #         "referer": "https://gushitong.baidu.com/"
    #     },
    #     timeout=10,
    #     verify=False,
    # )
    baidu_session.get("https://gushitong.baidu.com/index/ab-000001", headers={
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "referer": "https://gushitong.baidu.com/"
        }, timeout=10, verify=False)
    logger.info("chenggong ")
except Exception as e:
    logger.error(f"预热百度行情接口失败（网络或接口问题）: {e}")