import threading

from src.services.fund_refresh_service import FundRefreshService


def test_refresh_processes_each_fund_once_with_bounded_workers():
    service = FundRefreshService()
    seen = []
    seen_lock = threading.Lock()

    def refresh_one(code, _data):
        with seen_lock:
            seen.append(code)

    result = service.refresh(
        {str(index): {"fund_key": index} for index in range(8)},
        concurrency=3,
        refresh_one=refresh_one,
    )

    assert sorted(seen) == [str(index) for index in range(8)]
    assert result["worker_count"] == 3


def test_refresh_honors_pre_cancelled_event():
    service = FundRefreshService()
    cancel_event = threading.Event()
    cancel_event.set()
    seen = []

    result = service.refresh(
        {"260101": {}},
        concurrency=5,
        refresh_one=lambda code, _data: seen.append(code),
        cancel_event=cancel_event,
    )

    assert seen == []
    assert result["worker_count"] == 0
