"""Concurrent portfolio refresh orchestration."""

import queue
import threading
import time

from loguru import logger


class FundRefreshService:
    """Run bounded refresh workers without knowing provider or table formats."""

    def refresh(self, funds, concurrency, refresh_one, cancel_event=None):
        started_at = time.perf_counter()
        task_queue = queue.Queue()
        for fund_code, fund_data in funds.items():
            if cancel_event is not None and cancel_event.is_set():
                logger.info("刷新已停止，后续基金不再发起请求")
                break
            task_queue.put((fund_code, fund_data))

        requested_count = task_queue.qsize()
        worker_count = min(max(1, int(concurrency)), requested_count) if requested_count else 0
        logger.info(
            f"基金刷新开始: funds={task_queue.qsize()}, concurrency={worker_count}, "
            f"configured_concurrency={concurrency}"
        )

        def worker():
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    return
                try:
                    fund_code, fund_data = task_queue.get_nowait()
                except queue.Empty:
                    return
                try:
                    if cancel_event is None or not cancel_event.is_set():
                        refresh_one(fund_code, fund_data)
                finally:
                    task_queue.task_done()

        threads = [
            threading.Thread(target=worker, name=f"fund-refresh-worker-{index + 1}")
            for index in range(worker_count)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        elapsed_seconds = time.perf_counter() - started_at
        logger.info(
            f"基金刷新完成: funds={len(funds)}, concurrency={worker_count}, "
            f"elapsed_seconds={elapsed_seconds:.2f}"
        )
        return {
            "requested": requested_count,
            "worker_count": worker_count,
            "elapsed_seconds": elapsed_seconds,
        }
