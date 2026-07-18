"""FundGz latest-estimate client."""

import json
import re


class FundGzClient:
    _JSONP_PATTERN = re.compile(r"jsonpgz\((.*)\);?\s*$")

    def __init__(self, request_fn, urls):
        self._request = request_fn
        self._urls = urls

    def fetch_latest_estimate(self, fund_code):
        response = self._request(
            "GET",
            self._urls["fundgz_js_tpl"].format(fund=fund_code),
            verify=False,
        )
        match = self._JSONP_PATTERN.search(response.text.strip())
        if not match:
            raise ValueError(
                f"FundGz 估值响应格式异常: status={response.status_code}, "
                f"content_length={len(response.text or '')}"
            )

        payload = json.loads(match.group(1))
        growth_raw = payload.get("gszzl")
        growth = None if growth_raw in (None, "", "N/A") else round(float(growth_raw), 2)
        quote_time = str(payload.get("gztime") or "").strip()
        date = ""
        time = "N/A"
        if quote_time:
            parts = quote_time.split()
            if len(parts) >= 2:
                date = parts[0]
                time = parts[1][:5]
        return {
            "growth": growth,
            "date": date,
            "time": time,
            "quote_time": quote_time,
        }
