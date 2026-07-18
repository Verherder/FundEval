"""Shared HTTP transport for fund data providers."""

import json
import random
import threading
import time

import requests
from loguru import logger


REQUEST_TIMEOUT = (5, 20)
REQUEST_RETRIES = 3
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
FORBIDDEN_COOLDOWN_SECONDS = 300


class Fund123EndpointBlockedError(requests.exceptions.HTTPError):
    """Raised while an endpoint is temporarily disabled after HTTP 403."""


class FundHttpTransport:
    _blocked_endpoints = {}
    _blocked_endpoints_lock = threading.Lock()

    def __init__(self, session=None, sleep_fn=time.sleep, monotonic_fn=time.monotonic):
        self.session = session or requests.Session()
        self._sleep = sleep_fn
        self._monotonic = monotonic_fn
        self._thread_local = threading.local()
        self._session_state_lock = threading.Lock()
        self._request_schedule_lock = threading.Lock()
        self._next_request_at = 0.0
        self._cooldown_until = 0.0

    def request(self, method, url, *, retries=REQUEST_RETRIES, **kwargs):
        timeout = kwargs.pop("timeout", REQUEST_TIMEOUT)
        last_response = None
        last_error = None
        session = getattr(self._thread_local, "session", None)
        if session is None:
            session = requests.Session()
            with self._session_state_lock:
                session.headers.update(self.session.headers)
                session.cookies.update(self.session.cookies)
            self._thread_local.session = session

        for attempt in range(1, retries + 1):
            self._raise_if_endpoint_blocked(url)
            self._wait_for_request_slot()
            try:
                response = session.request(method, url, timeout=timeout, **kwargs)
                with self._session_state_lock:
                    self.session.cookies.update(session.cookies)
                if response.status_code == 403:
                    self._block_forbidden_endpoint(url)
                    raise Fund123EndpointBlockedError(
                        f"Fund123 接口返回 403，已暂停请求 5 分钟: {url}",
                        response=response,
                    )
                if response.status_code not in RETRY_STATUS_CODES:
                    return response

                last_response = response
                if response.status_code == 429:
                    self._register_rate_limit(response, attempt)
                logger.warning(f"请求 {url} 返回 {response.status_code}，准备重试 ({attempt}/{retries})")
            except Fund123EndpointBlockedError:
                raise
            except requests.exceptions.RequestException as error:
                last_error = error
                logger.warning(f"请求 {url} 失败，准备重试 ({attempt}/{retries}): {error}")

            if attempt < retries:
                self._sleep((0.6 * (2 ** (attempt - 1))) + random.uniform(0, 0.25))

        if last_response is not None:
            last_response.raise_for_status()
            return last_response
        raise last_error

    def request_json(self, method, url, *, json_retries=3, **kwargs):
        last_error = None
        for attempt in range(1, json_retries + 1):
            response = self.request(method, url, **kwargs)
            try:
                if not response.content or not response.text.strip():
                    raise ValueError("响应正文为空")
                return response, response.json()
            except (ValueError, json.JSONDecodeError) as error:
                last_error = error
                content_type = response.headers.get("Content-Type", "")
                logger.warning(
                    f"请求 {url} 返回无效JSON，准备重试 ({attempt}/{json_retries}): "
                    f"status={response.status_code}, content_type={content_type}, error={error}"
                )
                if attempt < json_retries:
                    self._sleep((0.4 * attempt) + random.uniform(0, 0.2))
        raise ValueError(f"请求 {url} 连续返回无效JSON: {last_error}")

    @classmethod
    def clear_circuit_breakers(cls):
        with cls._blocked_endpoints_lock:
            cls._blocked_endpoints.clear()

    def _raise_if_endpoint_blocked(self, url):
        now = self._monotonic()
        with self._blocked_endpoints_lock:
            blocked_until = self._blocked_endpoints.get(url, 0.0)
            if blocked_until <= now:
                self._blocked_endpoints.pop(url, None)
                return
            remaining = max(1, int(blocked_until - now))
        raise Fund123EndpointBlockedError(f"Fund123 接口仍在熔断期（剩余约 {remaining} 秒）: {url}")

    def _block_forbidden_endpoint(self, url):
        now = self._monotonic()
        blocked_until = now + FORBIDDEN_COOLDOWN_SECONDS
        with self._blocked_endpoints_lock:
            first_block = self._blocked_endpoints.get(url, 0.0) <= now
            self._blocked_endpoints[url] = max(self._blocked_endpoints.get(url, 0.0), blocked_until)
        if first_block:
            logger.warning(f"请求 {url} 返回 403，暂停该接口 5 分钟，后续基金使用降级数据")

    def _wait_for_request_slot(self):
        with self._request_schedule_lock:
            now = self._monotonic()
            scheduled_at = max(now, self._next_request_at, self._cooldown_until)
            self._next_request_at = scheduled_at + 0.05
        delay = scheduled_at - now
        if delay > 0:
            self._sleep(delay)

    def _register_rate_limit(self, response, attempt):
        retry_after = response.headers.get("Retry-After", "")
        try:
            cooldown = max(1.0, float(retry_after))
        except (TypeError, ValueError):
            cooldown = min(8.0, 1.5 * (2 ** (attempt - 1))) + random.uniform(0, 0.5)
        with self._request_schedule_lock:
            self._cooldown_until = max(self._cooldown_until, self._monotonic() + cooldown)
