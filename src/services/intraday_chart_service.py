"""Intraday estimate chart application service."""

from loguru import logger


class IntradayChartService:
    def __init__(self, fund_repo, provider_factory):
        self._fund_repo = fund_repo
        self._provider_factory = provider_factory

    def get_latest_estimate(self, user_id, fund_code):
        fund_data = self._get_fund(user_id, fund_code)
        if fund_data is None:
            return None
        estimate = self._provider_factory(user_id=user_id).fetch_latest_intraday_estimate(
            fund_data["fund_key"]
        )
        return {
            "estimate": estimate,
            "fund_info": {"code": fund_code, "name": fund_data["fund_name"]},
        }

    def get_curve(self, user_id, fund_code):
        fund_data = self._get_fund(user_id, fund_code)
        if fund_data is None:
            return None

        chart_data = {"labels": [], "growth": [], "net_values": []}
        try:
            points = self._provider_factory(user_id=user_id).fetch_intraday_curve(
                fund_data["fund_key"]
            )
            if points:
                chart_data = {
                    "labels": [point["time"] for point in points],
                    "growth": [point["growth"] for point in points],
                    "net_values": [point["net_value"] for point in points],
                }
        except Exception as error:
            logger.error(f"获取基金估值趋势图数据失败【{fund_code}】: {error}")

        return {
            "chart_data": chart_data,
            "fund_info": {"code": fund_code, "name": fund_data["fund_name"]},
        }

    def _get_fund(self, user_id, fund_code):
        return (self._fund_repo.get_visible_funds(user_id) or {}).get(fund_code)
