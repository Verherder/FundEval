"""
HTTP 请求计时与日志封装（Loguru）。

目标：
- 在不改动业务逻辑的前提下，为每次对外 HTTP 请求记录耗时，便于定位慢点。
- 兼容 requests.Session / requests 模块 / curl_cffi 的 Session（只要提供 .request(method, url, **kwargs)）。

配置：从 config.xml 读取 <http_timing> 节点。
- enabled: 是否开启计时日志（true/false）
- log_level: 日志级别（INFO/DEBUG/WARNING/ERROR 等）
- min_ms: 仅记录耗时 >= 该值（毫秒）的请求，0 表示全部记录
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from .yaml_config import load_yaml_config
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from loguru import logger




_REDACT_QUERY_KEYS = {
    "token",
    "access_token",
    "authorization",
    "apikey",
    "api_key",
    "key",
    "_csrf",
    "acs-token",
}

# 缓存解析后的 http_timing 配置，避免重复读文件
_http_timing_config: Optional[dict] = None


def _find_config_path() -> Optional[Path]:
    """查找 config.yaml：环境变量 FUNDEVAL_CONFIG > 当前工作目录 > 项目根。"""
    explicit = os.getenv("FUNDEVAL_CONFIG")
    if explicit:
        p = Path(explicit)
        if p.exists() and p.is_file():
            return p
    cwd = Path(os.getcwd())
    for p in [cwd, cwd / "config.yaml", Path(__file__).resolve().parent.parent]:
        if p.is_dir():
            candidate = p / "config.yaml"
        else:
            candidate = p
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _load_http_timing_config() -> dict:
    """从 config.yaml 读取 http_timing 配置，缺失时使用默认值。"""
    global _http_timing_config
    if _http_timing_config is not None:
        return _http_timing_config

    defaults = {
        "enabled": True,
        "log_level": "INFO",
        "min_ms": 0.0,
    }
    try:
        config = load_yaml_config()
        logging_cfg = config.get("logging", {})
        http_timing_cfg = config.get("http_timing", {})
        enabled = logging_cfg.get("log_response_time", True)
        log_level = logging_cfg.get("level", "INFO").upper()
        min_ms = float(logging_cfg.get("min_ms", 0.0))
        console_log = http_timing_cfg.get("console_log", False)
        _http_timing_config = {
            "enabled": enabled,
            "log_level": log_level,
            "min_ms": min_ms,
            "console_log": console_log,
        }
        return _http_timing_config
    except Exception:
        _http_timing_config = defaults
        return _http_timing_config


def reload_http_timing_config() -> None:
    """强制下次请求时重新读取 config.xml（修改配置后调用生效）。"""
    global _http_timing_config
    _http_timing_config = None


def _redact_url(url: str) -> str:
    """脱敏 URL 查询参数（避免日志里泄露 token/csrf 等）。"""
    try:
        parts = urlsplit(url)
        if not parts.query:
            return url
        q = parse_qsl(parts.query, keep_blank_values=True)
        redacted = []
        for k, v in q:
            if k.lower() in _REDACT_QUERY_KEYS:
                redacted.append((k, "***"))
            else:
                redacted.append((k, v))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(redacted), parts.fragment))
    except Exception:
        return url


def timed_http_request(
    client: Any,
    method: str,
    url: str,
    *,
    source: Optional[str] = None,
    log_level: Optional[str] = None,
    **kwargs: Any,
):
    """对 client.request(method, url, **kwargs) 进行计时并记录日志。

    Args:
        client: 提供 request 方法的对象（requests / requests.Session / curl_cffi.Session 等）
        method: HTTP 方法，如 "GET"/"POST"
        url: 请求 URL
        source: 可选，标记来源（例如 fund123 / eastmoney / baidu），便于过滤
        log_level: 可选，覆盖 config.xml 中的 log_level
        **kwargs: 原样传给 client.request
    """
    cfg = _load_http_timing_config()
    if not cfg["enabled"]:
        return client.request(method, url, **kwargs)

    level = (log_level or cfg["log_level"]).upper()
    min_ms = cfg["min_ms"]

    safe_url = _redact_url(url)
    method_u = (method or "GET").upper()
    timeout = kwargs.get("timeout", None)

    start = time.perf_counter()
    resp = None
    err: Optional[BaseException] = None
    try:
        resp = client.request(method_u, url, **kwargs)
        return resp
    except BaseException as e:
        err = e
        raise
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        if elapsed_ms < min_ms:
            return

        status_code = getattr(resp, "status_code", None) if resp is not None else None
        content_length = None
        headers = getattr(resp, "headers", None)
        if headers:
            try:
                content_length = headers.get("Content-Length")
            except Exception:
                content_length = None

        prefix = "[HTTP]"
        if source:
            prefix += f"[{source}]"

        base_msg = (
            f"{prefix} {method_u} {safe_url} "
            f"status={status_code if status_code is not None else '-'} "
            f"elapsed_ms={elapsed_ms:.1f}"
        )
        if timeout is not None:
            base_msg += f" timeout={timeout}"
        if content_length is not None:
            base_msg += f" content_length={content_length}"

        # 根据配置决定是否打印到终端
        if cfg.get("console_log", False):
            print(base_msg)
