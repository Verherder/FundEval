# -*- coding: UTF-8 -*-
"""Application factory for FundEval — create_app() with Blueprint wiring."""

import datetime
import os
import re
import secrets
import sys
import threading
import time
from pathlib import Path

import urllib3
from dotenv import load_dotenv
from flask import Flask, abort, request, session
from loguru import logger
from werkzeug.middleware.proxy_fix import ProxyFix

from src.dependencies import init_dependencies
from src.config.yaml_config import get_server_config, load_yaml_config

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


def _load_secret_key(db):
    configured = os.environ.get("FUNDEVAL_SECRET_KEY", "")
    if configured:
        return configured
    if db is not None:
        return "test-only-secret"
    if os.environ.get("FUNDEVAL_ENV", "development").lower() == "production":
        raise RuntimeError("生产环境必须设置 FUNDEVAL_SECRET_KEY")

    runtime_dir = Path(os.environ.get("FUNDEVAL_RUNTIME_DIR", _PROJECT_ROOT / ".runtime"))
    runtime_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    secret_path = runtime_dir / "session-secret"
    try:
        existing = secret_path.read_text(encoding="ascii").strip()
        if existing:
            return existing
    except FileNotFoundError:
        pass

    generated = secrets.token_urlsafe(48)
    try:
        fd = os.open(secret_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as secret_file:
            secret_file.write(generated)
        return generated
    except FileExistsError:
        return secret_path.read_text(encoding="ascii").strip()


def _setup_logging():
    """Configure loguru: stderr + rotating file."""
    log_dir = Path(os.environ.get("FUNDEVAL_LOG_DIR", _PROJECT_ROOT / "cache" / "logs"))
    log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add(
        str(log_dir / "fund_server.log"),
        level="INFO",
        encoding="utf-8",
        rotation="00:00",
        retention="14 days",
        compression="gz",
    )


def _setup_environment():
    """Load .env, suppress urllib3 warnings, configure SSL ciphers."""
    load_dotenv()
    urllib3.disable_warnings()
    try:
        _ssl_module = getattr(getattr(urllib3, "util", None), "ssl_", None)
        if _ssl_module is not None and hasattr(_ssl_module, "DEFAULT_CIPHERS"):
            _ssl_module.DEFAULT_CIPHERS = ":".join(
                [
                    "ECDHE+AESGCM",
                    "ECDHE+CHACHA20",
                    "ECDHE-RSA-AES128-SHA",
                    "ECDHE-RSA-AES256-SHA",
                    "RSA+AESGCM",
                    "AES128-SHA",
                    "AES256-SHA",
                ]
            )
    except Exception:
        pass


def _ensure_directories():
    Path(os.environ.get("FUNDEVAL_DATA_DIR", _PROJECT_ROOT / "cache")).mkdir(parents=True, exist_ok=True, mode=0o700)
    Path(os.environ.get("FUNDEVAL_LOG_DIR", _PROJECT_ROOT / "cache" / "logs")).mkdir(parents=True, exist_ok=True, mode=0o700)


_LOG_DIR = Path(os.environ.get("FUNDEVAL_LOG_DIR", _PROJECT_ROOT / "cache" / "logs"))
IMPORT_DETAIL_LOG_PATH = str(_LOG_DIR / "transaction_import.log")
SERVER_LOG_PATH = str(_LOG_DIR / "fund_server.log")
LOG_CLEANUP_STATE_PATH = str(_LOG_DIR / ".log_cleanup_state")

_LOG_CLEANUP_LOCK = threading.Lock()
_LOG_CLEANUP_THREAD_STARTED = False


def _get_log_cleanup_config():
    default_cfg = {"enabled": True, "retain_days": 14, "interval_hours": 6}
    try:
        cfg = load_yaml_config().get("logging_cleanup", {})
        if not isinstance(cfg, dict):
            return default_cfg
        enabled = bool(cfg.get("enabled", default_cfg["enabled"]))
        retain_days = int(cfg.get("retain_days", default_cfg["retain_days"]))
        if retain_days < 1:
            retain_days = default_cfg["retain_days"]
        interval_hours = int(cfg.get("interval_hours", default_cfg["interval_hours"]))
        if interval_hours < 1:
            interval_hours = default_cfg["interval_hours"]
        return {"enabled": enabled, "retain_days": retain_days, "interval_hours": interval_hours}
    except Exception as e:
        logger.warning(f"读取 logging_cleanup 配置失败，使用默认值: {e}")
        return default_cfg


def _parse_log_line_datetime(line):
    if not line:
        return None
    bracket_match = re.match(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]", line)
    if bracket_match:
        try:
            return datetime.datetime.strptime(bracket_match.group(1), "%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    loguru_match = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?)", line)
    if loguru_match:
        ts_text = loguru_match.group(1)
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.datetime.strptime(ts_text, fmt)
            except Exception:
                continue
    return None


def _trim_log_file_keep_recent(file_path, retain_days):
    if not os.path.exists(file_path):
        return
    cutoff = datetime.datetime.now() - datetime.timedelta(days=retain_days)
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        kept_lines = []
        dropped_count = 0
        for line in lines:
            dt = _parse_log_line_datetime(line)
            if dt is None or dt >= cutoff:
                kept_lines.append(line)
            else:
                dropped_count += 1
        if dropped_count <= 0:
            return
        temp_path = f"{file_path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            f.writelines(kept_lines)
        os.replace(temp_path, file_path)
        logger.info(
            f"日志清理完成: file={file_path}, removed_lines={dropped_count}, "
            f"kept_lines={len(kept_lines)}, retain_days={retain_days}"
        )
    except Exception as e:
        logger.error(f"日志清理失败: file={file_path}, error={e}")


def _run_log_cleanup_once(retain_days):
    _trim_log_file_keep_recent(SERVER_LOG_PATH, retain_days)
    _trim_log_file_keep_recent(IMPORT_DETAIL_LOG_PATH, retain_days)


def _should_run_log_cleanup(interval_hours):
    try:
        if not os.path.exists(LOG_CLEANUP_STATE_PATH):
            return True
        last_run_ts = os.path.getmtime(LOG_CLEANUP_STATE_PATH)
        elapsed_seconds = max(0, time.time() - last_run_ts)
        return elapsed_seconds >= max(1, int(interval_hours * 3600))
    except Exception:
        return True


def _mark_log_cleanup_ran():
    try:
        os.makedirs(os.path.dirname(LOG_CLEANUP_STATE_PATH), exist_ok=True)
        with open(LOG_CLEANUP_STATE_PATH, "w", encoding="utf-8") as state_file:
            state_file.write(datetime.datetime.now().isoformat())
    except Exception as e:
        logger.warning(f"写入日志清理状态失败: {e}")


def _log_cleanup_worker(interval_hours, retain_days):
    interval_seconds = max(1, int(interval_hours * 3600))
    time.sleep(interval_seconds)
    while True:
        if _should_run_log_cleanup(interval_hours):
            _run_log_cleanup_once(retain_days)
            _mark_log_cleanup_ran()
        time.sleep(interval_seconds)


def _start_log_cleanup_worker_if_needed():
    global _LOG_CLEANUP_THREAD_STARTED
    cfg = _get_log_cleanup_config()
    if not cfg.get("enabled", True):
        logger.info("日志清理任务已禁用（logging_cleanup.enabled=false）")
        return
    with _LOG_CLEANUP_LOCK:
        if _LOG_CLEANUP_THREAD_STARTED:
            return
        worker = threading.Thread(
            target=_log_cleanup_worker,
            args=(cfg["interval_hours"], cfg["retain_days"]),
            daemon=True,
            name="log-cleanup-worker",
        )
        worker.start()
        logger.info(
            f"日志清理任务已启动: interval_hours={cfg['interval_hours']}, retain_days={cfg['retain_days']}"
        )
        _LOG_CLEANUP_THREAD_STARTED = True


class FilteredWSGIRequestLogger:
    """WSGI middleware that suppresses werkzeug logs for static files."""

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        import logging
        if path.startswith("/static/") or path.endswith(".ico") or path.startswith("/favicon"):
            logging.getLogger("werkzeug").setLevel(logging.ERROR)
        else:
            logging.getLogger("werkzeug").setLevel(logging.INFO)
        return self.app(environ, start_response)


def create_app(db=None):
    """Create and configure the Flask application."""
    _setup_logging()
    _setup_environment()
    _ensure_directories()

    from src.database import Database

    app = Flask(__name__, template_folder="templates", static_folder="static")
    _server_cfg = get_server_config()
    app.secret_key = _load_secret_key(db)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("FUNDEVAL_SECURE_COOKIE", "0") == "1",
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    )

    if db is None:
        db = Database()
    init_dependencies(db)

    from src.blueprints.auth_bp import auth_bp
    from src.blueprints.pages_bp import pages_bp
    from src.blueprints.api_fund_bp import api_fund_bp
    from src.blueprints.api_market_bp import api_market_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(api_fund_bp)
    app.register_blueprint(api_market_bp)

    from src.auth import get_csrf_token, get_current_user_id, validate_csrf_token
    from src.dependencies import get_user_repo

    @app.context_processor
    def inject_security_context():
        user_id = get_current_user_id()
        return {
            "csrf_token": get_csrf_token,
            "is_admin": bool(user_id and get_user_repo().is_admin(user_id)),
        }

    @app.before_request
    def enforce_csrf():
        if app.config.get("TESTING"):
            return None
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return None
        if request.endpoint == "auth.logout" and "user_id" not in session:
            return None
        supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
        if not validate_csrf_token(supplied):
            abort(400, description="CSRF validation failed")

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'",
        )
        return response

    app.wsgi_app = ProxyFix(
        FilteredWSGIRequestLogger(app.wsgi_app),
        x_for=1,
        x_proto=1,
        x_host=1,
        x_prefix=1,
    )

    if (
        os.environ.get("WERKZEUG_RUN_MAIN") == "true"
        or os.environ.get("FUNDEVAL_START_BACKGROUND_TASKS") == "1"
    ):
        _start_log_cleanup_worker_if_needed()

    return app
