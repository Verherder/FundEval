"""Fund123 API client with response parsing isolated from portfolio services."""

import datetime


class Fund123Client:
    def __init__(self, request_fn, request_json_fn, urls, csrf_getter):
        self._request = request_fn
        self._request_json = request_json_fn
        self._urls = urls
        self._csrf_getter = csrf_getter

    def _headers(self):
        return {
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "close",
            "Content-Type": "application/json",
            "Origin": self._urls["fund123_origin"],
            "Referer": self._urls["fund123_fund_page"],
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
            ),
            "X-API-Key": "foobar",
            "accept": "json",
        }

    def _fetch_intraday_points(self, fund_key, start_date=None, end_date=None):
        start_date = start_date or datetime.date.today()
        end_date = end_date or (start_date + datetime.timedelta(days=1))
        _response, payload = self._request_json(
            "POST",
            self._urls["fund123_intraday_api"],
            headers=self._headers(),
            params={"_csrf": self._csrf_getter()},
            json={
                "startTime": start_date.isoformat(),
                "endTime": end_date.isoformat(),
                "limit": 200,
                "productId": fund_key,
                "format": True,
                "source": "WEALTHBFFWEB",
            },
            verify=False,
        )
        if not isinstance(payload, dict) or not payload.get("success"):
            return []
        return payload.get("list", []) or []

    @staticmethod
    def _parse_intraday_point(point):
        quote_dt = datetime.datetime.fromtimestamp(point["time"] / 1000)
        return {
            "growth": round(float(point["forecastGrowth"]) * 100, 2),
            "net_value": round(float(point["forecastNetValue"]), 4),
            "date": quote_dt.strftime("%Y-%m-%d"),
            "time": quote_dt.strftime("%H:%M"),
        }

    def fetch_latest_estimate(self, fund_key):
        points = self._fetch_intraday_points(fund_key)
        return self._parse_intraday_point(points[-1]) if points else None

    def fetch_intraday_curve(self, fund_key):
        return [self._parse_intraday_point(point) for point in self._fetch_intraday_points(fund_key)]
