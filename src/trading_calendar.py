# -*- coding: UTF-8 -*-
"""沪深交易所交易日（XSHG），用于净值缺口判断。"""

import datetime
import threading
from typing import List

from loguru import logger

_calendar_fallback_lock = threading.Lock()
_calendar_fallback_warned = False


def _warn_exchange_calendar_unavailable(exc: BaseException) -> None:
    """日历库缺失或异常时只打一次告警，避免按日刷屏。"""
    global _calendar_fallback_warned
    with _calendar_fallback_lock:
        if _calendar_fallback_warned:
            return
        _calendar_fallback_warned = True
        logger.warning(
            "无法使用 exchange_calendars（XSHG 沪深交易日历），已回退为「自然周工作日」判断应有净值日；"
            "法定节假日仍会当作缺口并反复请求历史净值接口（云端通常也无数据）。"
            "请在运行环境中安装依赖：pip install -r requirements.txt 。详情: {}",
            exc,
        )


def is_cn_sse_trading_day(day: datetime.date) -> bool:
    """是否为沪深交易日（与大多数境内公募基金净值披露日一致）。"""
    try:
        import exchange_calendars as ec
        import pandas as pd

        cal = ec.get_calendar("XSHG")
        return bool(cal.is_session(pd.Timestamp(day)))
    except Exception as e:
        _warn_exchange_calendar_unavailable(e)
        return day.weekday() < 5


def iter_cn_sse_trading_days(start: datetime.date, end: datetime.date) -> List[datetime.date]:
    """闭区间 [start, end] 内全部沪深交易日（升序）。"""
    if not isinstance(start, datetime.date) or not isinstance(end, datetime.date) or start > end:
        return []
    try:
        import exchange_calendars as ec
        import pandas as pd

        cal = ec.get_calendar("XSHG")
        sessions = cal.sessions_in_range(pd.Timestamp(start), pd.Timestamp(end))
        return [ts.date() for ts in sessions]
    except Exception as e:
        _warn_exchange_calendar_unavailable(e)
        out: List[datetime.date] = []
        d = start
        while d <= end:
            if d.weekday() < 5:
                out.append(d)
            d += datetime.timedelta(days=1)
        return out


def cn_sse_range_has_trading_day(start: datetime.date, end: datetime.date) -> bool:
    """闭区间内是否至少包含一个沪深交易日。"""
    if start > end:
        return False
    days = iter_cn_sse_trading_days(start, end)
    return len(days) > 0
