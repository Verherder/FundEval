import datetime
import os, sys, time
import re
import threading
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT))

(_PROJECT_ROOT / "cache").mkdir(parents=True, exist_ok=True)
(_PROJECT_ROOT / "cache" / "logs").mkdir(parents=True, exist_ok=True)

from typing import Any

import urllib3
import requests as _requests
from dotenv import load_dotenv
from flask import Flask, g, request, render_template, redirect, url_for, jsonify, \
    send_file
from loguru import logger

# 确保 INFO 级别日志（含 HTTP 计时）在终端输出；级别由 config.xml 的 http_timing.log_level 控制
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add(
    str(_PROJECT_ROOT / "cache" / "logs" / "fund_server.log"),
    level="INFO",
    encoding="utf-8",
    rotation="10 MB",
    retention="14 days",
)

import src.fund as fund
from src.auth import login_required, get_current_user_id, get_current_username, login_user, logout_user
from src.database import Database
from src.repositories.user_repo import UserRepo
from src.repositories.fund_repo import FundRepo
from src.repositories.transaction_repo import TransactionRepo
from src.repositories.nav_repo import NavRepo
from src.tab_enhancers import enhance_fund_tab_content

from src.config.yaml_config import get_page_refresh_config, load_yaml_config, get_nav_sync_config, get_server_config
from src.services.metrics import safe_float, quantize_shares_2, parse_tx_datetime, calculate_holding_shares_by_time
from src.services.transaction_service import TransactionService
from src.services.import_service import ImportService
from src.services.nav_service import NavService
from src.services.chart_service import ChartService, PERFORMANCE_CHART_INTERVALS, DEFAULT_PERFORMANCE_CHART_INTERVAL, DEFAULT_PROFIT_CHART_INTERVAL
from src.services.fund_service import FundService
from src.services.market_service import MarketService

# 加载环境变量
load_dotenv()

urllib3.disable_warnings()
try:
    _ssl_module = getattr(getattr(urllib3, "util", None), "ssl_", None)
    if _ssl_module is not None and hasattr(_ssl_module, "DEFAULT_CIPHERS"):
        _ssl_module.DEFAULT_CIPHERS = ":".join(
            [
                "ECDHE+AESGCM",
                "ECDHE+CHACHA20",
                'ECDHE-RSA-AES128-SHA',
                'ECDHE-RSA-AES256-SHA',
                "RSA+AESGCM",
                'AES128-SHA',
                'AES256-SHA',
            ]
        )
except Exception:
    pass

app = Flask(__name__, template_folder='src/templates', static_folder='src/static')
_server_cfg = get_server_config()
app.secret_key = _server_cfg.get('secret_key', 'luobobo')
db = Database()  # 初始化数据库
user_repo = UserRepo(db)
fund_repo = FundRepo(db)
transaction_repo = TransactionRepo(db)
nav_repo = NavRepo(db)


def get_lan_fund(user_id=None):
    """返回当前请求的 LanFund 单例（存储在 Flask g 上）。

    每次请求首次调用时创建新实例，同一请求内重复调用返回同一实例。
    修改 fund.py 后重启进程即可，不再通过 importlib 热更新。
    """
    if not hasattr(g, "_lan_fund"):
        g._lan_fund = fund.LanFund(user_id=user_id, db=db)
    return g._lan_fund

tx_service = TransactionService(fund_repo, transaction_repo, nav_repo, get_lan_fund)
import_service = ImportService(fund_repo, transaction_repo, nav_repo, get_lan_fund, tx_service)
nav_service = NavService(db, fund_repo, nav_repo, get_lan_fund)
chart_service = ChartService(db, fund_repo, nav_repo, transaction_repo, nav_service, get_lan_fund)
fund_service = FundService(db, fund_repo, transaction_repo, get_lan_fund, chart_service)
market_service = MarketService(get_lan_fund)

IMPORT_DETAIL_LOG_PATH = str(_PROJECT_ROOT / "cache" / "logs" / "transaction_import.log")
SERVER_LOG_PATH = str(_PROJECT_ROOT / "cache" / "logs" / "fund_server.log")
LOG_CLEANUP_STATE_PATH = str(_PROJECT_ROOT / "cache" / "logs" / ".log_cleanup_state")

_LOG_CLEANUP_LOCK = threading.Lock()
_LOG_CLEANUP_THREAD_STARTED = False


def _get_log_cleanup_config():
    """读取日志清理配置，失败时回退默认值。"""
    default_cfg = {
        "enabled": True,
        "retain_days": 14,
        "interval_hours": 6,
    }
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

        return {
            "enabled": enabled,
            "retain_days": retain_days,
            "interval_hours": interval_hours,
        }
    except Exception as e:
        logger.warning(f"读取 logging_cleanup 配置失败，使用默认值: {e}")
        return default_cfg


def _parse_log_line_datetime(line):
    """尽量从日志行中解析时间戳。支持 `[YYYY-mm-dd HH:MM:SS]` 与 loguru 默认前缀。"""
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
    """按日志行时间戳裁剪文件内容，仅保留最近 retain_days 天。"""
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
            f"日志清理完成: file={file_path}, removed_lines={dropped_count}, kept_lines={len(kept_lines)}, retain_days={retain_days}"
        )
    except Exception as e:
        logger.error(f"日志清理失败: file={file_path}, error={e}")


def _run_log_cleanup_once(retain_days):
    """执行一次日志裁剪。"""
    _trim_log_file_keep_recent(SERVER_LOG_PATH, retain_days)
    _trim_log_file_keep_recent(IMPORT_DETAIL_LOG_PATH, retain_days)


def _should_run_log_cleanup(interval_hours):
    """基于持久化状态判断是否需要执行清理，避免重启后频繁触发。"""
    try:
        if not os.path.exists(LOG_CLEANUP_STATE_PATH):
            return True
        last_run_ts = os.path.getmtime(LOG_CLEANUP_STATE_PATH)
        elapsed_seconds = max(0, time.time() - last_run_ts)
        return elapsed_seconds >= max(1, int(interval_hours * 3600))
    except Exception:
        return True


def _mark_log_cleanup_ran():
    """记录最近一次清理时间。"""
    try:
        os.makedirs(os.path.dirname(LOG_CLEANUP_STATE_PATH), exist_ok=True)
        with open(LOG_CLEANUP_STATE_PATH, "w", encoding="utf-8") as state_file:
            state_file.write(datetime.datetime.now().isoformat())
    except Exception as e:
        logger.warning(f"写入日志清理状态失败: {e}")


def _log_cleanup_worker(interval_hours, retain_days):
    """后台定时执行日志清理。"""
    interval_seconds = max(1, int(interval_hours * 3600))
    time.sleep(interval_seconds)
    while True:
        if _should_run_log_cleanup(interval_hours):
            _run_log_cleanup_once(retain_days)
            _mark_log_cleanup_ran()
        time.sleep(interval_seconds)


def _start_log_cleanup_worker_if_needed():
    """启动日志清理线程（仅一次）。"""
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
        # 必须最后设置，避免竞态条件
        _LOG_CLEANUP_THREAD_STARTED = True


# ==================== Authentication Routes ====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面和处理"""
    if request.method == 'GET':
        # 检查是否有记住我的cookie
        remember_token = request.cookies.get('remember_token')
        if remember_token:
            # 尝试从token中解析用户信息并自动登录
            try:
                import hashlib
                # token格式: username:hashed_password
                parts = remember_token.split(':')
                if len(parts) == 2:
                    username, token_hash = parts
                    user = user_repo.get_user_by_username(username)
                    if user:
                        # 验证token是否匹配
                        expected_hash = hashlib.sha256(f"{username}:{user['password_hash']}".encode()).hexdigest()
                        if token_hash == expected_hash:
                            login_user(user['id'], username)
                            return redirect(url_for('get_fund'))
            except Exception as e:
                logger.error(f"Auto-login failed: {e}")

        return render_template('login.html')

    # POST request - handle login
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    remember_me = request.form.get('remember_me') == '1'

    if not username or not password:
        return render_template('login.html', error='请输入用户名和密码')

    success, user_id = user_repo.verify_password(username, password)
    if success:
        login_user(user_id, username)
        response = redirect(url_for('get_fund'))

        # 如果勾选了记住我，设置cookie（7天有效）
        if remember_me:
            import hashlib
            user = user_repo.get_user_by_username(username)
            if not user:
                return response
            token_hash = hashlib.sha256(f"{username}:{user['password_hash']}".encode()).hexdigest()
            remember_token = f"{username}:{token_hash}"
            response.set_cookie('remember_token', remember_token, max_age=7 * 24 * 60 * 60, httponly=True,
                                samesite='Lax')

        return response
    else:
        return render_template('login.html', error='用户名或密码错误')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """注册页面和处理"""
    if request.method == 'GET':
        return render_template('register.html')

    # POST request - handle registration
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')

    # 验证输入
    if not username or not password:
        return render_template('register.html', error='请输入用户名和密码')

    if len(username) < 3 or len(username) > 20:
        return render_template('register.html', error='用户名长度应为3-20个字符')

    if len(password) < 6:
        return render_template('register.html', error='密码长度至少为6个字符')

    if password != confirm_password:
        return render_template('register.html', error='两次输入的密码不一致')

    # 创建用户
    success, message, user_id = user_repo.create_user(username, password)
    if success:
        # 注册成功，自动登录
        login_user(user_id, username)
        return redirect(url_for('get_fund'))
    else:
        return render_template('register.html', error=message)


@app.route('/logout')
def logout():
    """登出"""
    logout_user()
    response = redirect(url_for('login'))
    # 清除记住我的cookie
    response.set_cookie('remember_token', '', max_age=0)
    return response


@app.route('/fund/sector', methods=['GET'])
@login_required
def get_sector_funds():
    """获取指定板块的基金列表"""
    bk_id = request.args.get("bk_id")
    user_id = get_current_user_id()
    data = market_service.get_select_fund(user_id, bk_id=bk_id)
    if "error" in data:
        return f'<p style="color: red; padding: 20px;">{data["error"]}</p>'
    return f'''
    <div style="padding: 20px;">
        <h3 style="margin: 0 0 15px 0;">板块: {data["bk_name"]}</h3>
        {render_template('partials/data_table.html',
            title=["基金代码", "基金名称", "基金类型", "日期", "净值", "日增长率", "近1周", "近1月", "近3月", "近6月", "今年来", "近1年", "近2年", "近3年", "成立以来"],
            data=data["results"],
            sortable_columns=[4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
        )}
    </div>'''


# API endpoints for fund operations
@app.route('/api/fund/add', methods=['POST'])
@login_required
def api_fund_add():
    """添加基金"""
    start = time.perf_counter()
    try:
        data = request.json
        codes = data.get('codes', '')
        if not codes:
            return {'success': False, 'message': '请提供基金代码'}
        user_id = get_current_user_id()
        result = fund_service.add_fund(user_id, codes)
        return result
    except Exception as e:
        logger.error(f"添加基金失败: {e}")
        return {'success': False, 'message': f'添加失败: {str(e)}'}
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(f"[API] /api/fund/add elapsed_ms={elapsed:.1f}")


@app.route('/api/fund/backfill-establishment-dates', methods=['POST'])
@login_required
def api_backfill_establishment_dates():
    """批量补齐当前用户基金成立日期（仅处理 establishment_date 缺失的数据）。"""
    start = time.perf_counter()
    try:
        user_id = get_current_user_id()
        return nav_service.backfill_all_establishment_dates(user_id)
    except Exception as e:
        logger.error(f"批量回填成立日期失败: {e}")
        return {
            'success': False,
            'message': f'回填失败: {str(e)}',
            'total': 0,
            'missing': 0,
            'updated': 0,
            'failed': 0,
            'failed_codes': [],
        }
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(f"[API] /api/fund/backfill-establishment-dates elapsed_ms={elapsed:.1f}")


@app.route('/api/fund/delete', methods=['POST'])
@login_required
def api_fund_delete():
    """删除基金"""
    start = time.perf_counter()
    try:
        data = request.json
        codes = data.get('codes', '')
        if not codes:
            return {'success': False, 'message': '请提供基金代码'}
        user_id = get_current_user_id()
        result = fund_service.delete_fund(user_id, codes)
        return result
    except Exception as e:
        logger.error(f"删除基金失败: {e}")
        return {'success': False, 'message': f'删除失败: {str(e)}'}
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(f"[API] /api/fund/delete elapsed_ms={elapsed:.1f}")


@app.route('/api/fund/hold', methods=['POST'])
@login_required
def api_fund_set_hold():
    """设置/取消持有标记"""
    start = time.perf_counter()
    try:
        data = request.json
        codes = data.get('codes', '')
        hold = data.get('hold', True)
        if not codes:
            return {'success': False, 'message': '请提供基金代码'}
        user_id = get_current_user_id()
        result = fund_service.set_hold(user_id, codes, hold)
        return result
    except Exception as e:
        logger.error(f"设置持有标记失败: {e}")
        return {'success': False, 'message': f'操作失败: {str(e)}'}
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(f"[API] /api/fund/hold elapsed_ms={elapsed:.1f}")


@app.route('/api/fund/sector', methods=['POST'])
@login_required
def api_fund_set_sector():
    """设置板块标记"""
    start = time.perf_counter()
    try:
        data = request.json
        codes = data.get('codes', '')
        sectors = data.get('sectors', [])
        if not codes:
            return {'success': False, 'message': '请提供基金代码'}
        if not sectors:
            return {'success': False, 'message': '请选择板块'}
        user_id = get_current_user_id()
        result = fund_service.set_sector(user_id, codes, sectors)
        return result
    except Exception as e:
        logger.error(f"标注板块失败: {e}")
        return {'success': False, 'message': f'操作失败: {str(e)}'}
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(f"[API] /api/fund/sector elapsed_ms={elapsed:.1f}")


@app.route('/api/fund/sector/remove', methods=['POST'])
@login_required
def api_fund_remove_sector():
    """删除板块标记"""
    start = time.perf_counter()
    try:
        data = request.json
        codes = data.get('codes', '')
        if not codes:
            return {'success': False, 'message': '请提供基金代码'}
        user_id = get_current_user_id()
        result = fund_service.remove_sector(user_id, codes)
        return result
    except Exception as e:
        logger.error(f"删除板块标记失败: {e}")
        return {'success': False, 'message': f'操作失败: {str(e)}'}
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(f"[API] /api/fund/sector/remove elapsed_ms={elapsed:.1f}")


# ==================== fund_map File Upload/Download ====================

@app.route('/api/fund/upload', methods=['POST'])
@login_required
def api_fund_upload():
    """上传fund_map.json文件"""
    start = time.perf_counter()
    try:
        if 'file' not in request.files:
            return {'success': False, 'message': '未找到上传文件'}

        file = request.files['file']
        file_bytes = file.read()
        user_id = get_current_user_id()
        result = fund_service.upload_funds(user_id, file_bytes, str(file.filename or ''))
        return result
    except Exception as e:
        logger.error(f"上传文件失败: {e}")
        return {'success': False, 'message': f'上传失败: {str(e)}'}
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(f"[API] /api/fund/upload elapsed_ms={elapsed:.1f}")


@app.route('/api/fund/download', methods=['GET'])
@login_required
def api_fund_download():
    """下载fund_map.json文件"""
    try:
        user_id = get_current_user_id()
        temp_path, download_name, mimetype = fund_service.download_funds(user_id)
        return send_file(temp_path, as_attachment=True, download_name=download_name, mimetype=mimetype)
    except Exception as e:
        logger.error(f"下载文件失败: {e}")
        return {'success': False, 'message': f'下载失败: {str(e)}'}


@app.route('/api/fund/transactions/download-all', methods=['GET'])
@login_required
def api_fund_transactions_download_all():
    """下载当前用户的全部交易记录备份。"""
    try:
        user_id = get_current_user_id()
        temp_path, download_name, mimetype = fund_service.download_all_transactions(user_id)
        return send_file(temp_path, as_attachment=True, download_name=download_name, mimetype=mimetype)
    except Exception as e:
        logger.error(f"下载全部交易记录备份失败: {e}")
        return {'success': False, 'message': f'下载失败: {str(e)}'}


@app.route('/api/fund/shares', methods=['POST'])
@login_required
def api_fund_shares():
    data = request.json or {}
    code = data.get('code', '').strip()
    shares = data.get('shares', 0)
    if not code:
        return {'success': False, 'message': '请提供基金代码'}
    try:
        shares = float(shares)
        if shares < 0:
            return {'success': False, 'message': '份额不能为负数'}
    except (ValueError, TypeError):
        return {'success': False, 'message': '份额格式错误'}
    user_id = get_current_user_id()
    return tx_service.update_fund_shares(user_id, code, shares)


@app.route('/api/fund/buy', methods=['POST'])
@login_required
def api_fund_buy():
    data = request.json or {}
    code = str(data.get('code', '')).strip()
    amount = data.get('amount', 0)
    if not code:
        return {'success': False, 'message': '请提供基金代码'}
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return {'success': False, 'message': '买入金额格式错误'}
    if amount <= 0:
        return {'success': False, 'message': '买入金额必须大于0'}
    user_id = get_current_user_id()
    return tx_service.buy_fund(user_id, code, amount)


@app.route('/api/fund/buy-backfill', methods=['POST'])
@login_required
def api_fund_buy_backfill():
    data = request.json or {}
    code = str(data.get('code', '')).strip()
    amount = data.get('amount', 0)
    fee = data.get('fee', 0)
    net_value = data.get('net_value', None)
    trade_date = str(data.get('trade_date', '')).strip()
    if not code:
        return {'success': False, 'message': '请提供基金代码'}
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return {'success': False, 'message': '买入金额格式错误'}
    if amount <= 0:
        return {'success': False, 'message': '买入金额必须大于0'}
    try:
        fee = float(fee)
    except (TypeError, ValueError):
        return {'success': False, 'message': '手续费格式错误'}
    if fee < 0:
        return {'success': False, 'message': '手续费不能为负数'}
    if amount <= fee:
        return {'success': False, 'message': '买入金额需大于手续费'}
    user_id = get_current_user_id()
    return tx_service.buy_backfill(user_id, code, amount, fee, net_value, trade_date)


@app.route('/api/fund/net-value-by-date', methods=['GET'])
@login_required
def api_fund_net_value_by_date():
    code = str(request.args.get('code', '')).strip()
    trade_date = str(request.args.get('date', '')).strip()
    if not code:
        return {'success': False, 'message': '请提供基金代码'}
    user_id = get_current_user_id()
    return tx_service.get_net_value_by_date(user_id, code, trade_date)


@app.route('/api/fund/sell-backfill', methods=['POST'])
@login_required
def api_fund_sell_backfill():
    data = request.json or {}
    code = str(data.get('code', '')).strip()
    shares_input = data.get('shares', None)
    fee = data.get('fee', 0)
    net_value = data.get('net_value', None)
    trade_date = str(data.get('trade_date', '')).strip()
    if not code:
        return {'success': False, 'message': '请提供基金代码'}
    shares = None
    if shares_input is not None and str(shares_input).strip() != "":
        try:
            shares = float(shares_input)
        except (TypeError, ValueError):
            return {'success': False, 'message': '卖出份额格式错误'}
        if shares <= 0:
            return {'success': False, 'message': '卖出份额必须大于0'}
    try:
        fee = float(fee)
    except (TypeError, ValueError):
        return {'success': False, 'message': '手续费格式错误'}
    if fee < 0:
        return {'success': False, 'message': '手续费不能为负数'}
    user_id = get_current_user_id()
    return tx_service.sell_backfill(user_id, code, shares, fee, net_value, trade_date)


@app.route('/api/fund/dividend-backfill', methods=['POST'])
@login_required
def api_fund_dividend_backfill():
    data = request.json or {}
    code = str(data.get('code', '')).strip()
    amount = data.get('amount', 0)
    net_value = data.get('net_value', None)
    trade_date = str(data.get('trade_date', '')).strip()
    if not code:
        return {'success': False, 'message': '请提供基金代码'}
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return {'success': False, 'message': '分红金额格式错误'}
    if amount <= 0:
        return {'success': False, 'message': '分红金额必须大于0'}
    user_id = get_current_user_id()
    return tx_service.dividend_backfill(user_id, code, amount, net_value, trade_date)


@app.route('/api/fund/sell', methods=['POST'])
@login_required
def api_fund_sell():
    data = request.json or {}
    code = str(data.get('code', '')).strip()
    shares = data.get('shares', 0)
    if not code:
        return {'success': False, 'message': '请提供基金代码'}
    try:
        shares = float(shares)
    except (TypeError, ValueError):
        return {'success': False, 'message': '卖出份额格式错误'}
    if shares <= 0:
        return {'success': False, 'message': '卖出份额必须大于0'}
    user_id = get_current_user_id()
    return tx_service.sell_fund(user_id, code, shares)


@app.route('/api/fund/transactions', methods=['GET'])
@login_required
def api_fund_transactions():
    code = str(request.args.get('code', '')).strip()
    if not code:
        return {'success': False, 'message': '请提供基金代码'}
    user_id = get_current_user_id()
    return tx_service.get_transactions(user_id, code)


@app.route('/api/fund/transactions/import', methods=['POST'])
@login_required
def api_fund_transactions_import():
    """从Excel导入交易记录（异步任务）。"""
    try:
        if 'file' not in request.files:
            return {'success': False, 'message': '未找到上传文件'}

        file = request.files['file']
        if file.filename == '':
            return {'success': False, 'message': '未选择文件'}

        file_bytes = file.read()
        user_id = get_current_user_id()
        return import_service.import_transactions(user_id, file_bytes, file.filename)
    except Exception as e:
        logger.error(f"导入交易记录失败: {e}")
        return {'success': False, 'message': f'导入交易记录失败: {str(e)}'}




@app.route('/api/fund/transactions/import-progress', methods=['GET'])
@login_required
def api_fund_transactions_import_progress():
    job_id = str(request.args.get('job_id', '') or '').strip()
    return import_service.get_import_progress(job_id)


@app.route('/api/fund/transaction/update', methods=['POST'])
@login_required
def api_fund_transaction_update():
    """更新交易记录并重算持仓份额。"""
    try:
        data = request.json or {}
        code = str(data.get('code', '')).strip()
        tx_id_raw = data.get('transaction_id', None)
        tx_type = str(data.get('tx_type', '')).strip().lower()
        amount = data.get('amount', 0)
        shares = data.get('shares', 0)
        net_value = data.get('net_value', 0)
        fee = data.get('fee', 0)
        tx_time_raw = str(data.get('tx_time', '')).strip()
        user_id = get_current_user_id()

        try:
            tx_id = int(str(tx_id_raw).strip())
        except (TypeError, ValueError):
            return {'success': False, 'message': '交易ID格式错误'}

        return tx_service.update_transaction(
            user_id, code, tx_id, tx_type,
            float(amount) if amount else 0,
            float(shares) if shares else 0,
            float(net_value) if net_value else None,
            float(fee) if fee else 0,
            tx_time_raw,
        )
    except Exception as e:
        logger.error(f"更新交易记录失败: {e}")
        return {'success': False, 'message': f'更新交易记录失败: {str(e)}'}


@app.route('/api/fund/transaction/delete', methods=['POST'])
@login_required
def api_fund_transaction_delete():
    """删除交易记录并重算持仓份额。"""
    try:
        data = request.json or {}
        code = str(data.get('code', '')).strip()
        tx_id_raw = data.get('transaction_id', None)
        user_id = get_current_user_id()

        try:
            tx_id = int(str(tx_id_raw).strip())
        except (TypeError, ValueError):
            return {'success': False, 'message': '交易ID格式错误'}

        return tx_service.delete_transaction(user_id, code, tx_id)
    except Exception as e:
        logger.error(f"删除交易记录失败: {e}")
        return {'success': False, 'message': f'删除交易记录失败: {str(e)}'}


@app.route('/api/fund/transactions/clear', methods=['POST'])
@login_required
def api_fund_transactions_clear():
    """清空单只基金的全部交易记录。"""
    try:
        data = request.json or {}
        code = str(data.get('code', '')).strip()
        confirm_text = str(data.get('confirm_text', '')).strip()
        user_id = get_current_user_id()
        return tx_service.clear_fund_transactions(user_id, code, confirm_text)
    except Exception as e:
        logger.error(f"清空交易记录失败: {e}")
        return {'success': False, 'message': f'清空交易记录失败: {str(e)}'}


@app.route('/api/fund/transactions/clear-all', methods=['POST'])
@login_required
def api_fund_transactions_clear_all():
    """清空当前用户全部基金交易记录。"""
    try:
        data = request.json or {}
        confirm_text = str(data.get('confirm_text', '')).strip()
        user_id = get_current_user_id()
        return tx_service.clear_all_transactions(user_id, confirm_text)
    except Exception as e:
        logger.error(f"清空全部交易记录失败: {e}")
        return {'success': False, 'message': f'清空全部交易记录失败: {str(e)}'}


@app.route('/api/fund/data', methods=['GET'])
@login_required
def api_fund_data():
    """获取用户的基金数据（用于前端加载份额等信息）"""
    try:
        user_id = get_current_user_id()
        fund_map = fund_service.get_fund_data(user_id)
        return jsonify(fund_map)
    except Exception as e:
        logger.error(f"获取基金数据失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tab/<tab_id>', methods=['GET'])
@login_required
def api_get_tab_data(tab_id):
    """按需加载单个tab的数据"""
    try:
        user_id = get_current_user_id()

        if tab_id == 'kx':
            result = market_service.get_kx_news_raw(user_id)
            table_data = []
            for v in result:
                evaluate = v.get("evaluate", "")
                title_text = v.get("title", v["content"]["items"][0]["data"])
                publish_time = v["publish_time"]
                publish_time = datetime.datetime.fromtimestamp(int(publish_time)).strftime("%H:%M:%S")
                if evaluate == "利好":
                    evaluate = f'<span class="positive">{evaluate}</span>'
                elif evaluate == "利空":
                    evaluate = f'<span class="negative">{evaluate}</span>'
                table_data.append([publish_time, evaluate, title_text])
            content = render_template('partials/data_table.html',
                title=["时间", "多空", "快讯内容"],
                data=table_data)
        elif tab_id == 'marker':
            content = render_template('partials/data_table.html',
                title=["指数名称", "指数", "涨跌幅"],
                data=market_service.get_market_info_raw(user_id))
        elif tab_id == 'bk':
            content = render_template('partials/data_table.html',
                title=["板块名称", "今日涨跌幅", "今日主力净流入", "今日主力净流入占比", "今日小单净流入", "今日小单流入占比"],
                data=market_service.get_bk_data_raw(user_id),
                sortable_columns=[1, 2, 3, 4, 5])
        elif tab_id == 'seven_A':
            result = market_service.get_seven_a_data_raw(user_id)
            content = render_template('partials/data_table.html',
                title=["日期", "总成交额", "上交所", "深交所", "北交所"],
                data=result or [],
                sortable_columns=[1, 2, 3, 4])
        elif tab_id == 'A':
            content = render_template('partials/data_table.html',
                title=["时间", "指数", "涨跌额", "涨跌幅", "成交量", "成交额"],
                data=market_service.get_a_share_data_raw(user_id))
        elif tab_id == 'fund':
            titles, rows, sortable_columns = market_service.build_fund_table(user_id)
            content = render_template('partials/data_table.html', title=titles, data=rows, sortable_columns=sortable_columns)
            fund_map = fund_repo.get_user_funds(user_id)
            shares_map = {code: data.get('shares', 0) for code, data in fund_map.items()}
            content = enhance_fund_tab_content(content, shares_map)
        elif tab_id == 'select_fund':
            data = market_service.get_select_fund(user_id)
            bk_list = data["bk_list"]
            major_categories = market_service.get_major_categories(user_id)
            categorized_sectors = []
            for category, sectors in major_categories.items():
                items = [(idx + 1, bk_list[idx]) for idx in range(len(bk_list)) if bk_list[idx] in sectors]
                if items:
                    categorized_sectors.append((category, items))
            content = render_template('partials/sector_selection.html',
                categorized_sectors=categorized_sectors)
        else:
            return jsonify({'success': False, 'message': f'未知的tab ID: {tab_id}'}), 404

        return jsonify({'success': True, 'content': content})
    except Exception as e:
        logger.error(f"加载tab {tab_id} 数据失败: {e}")
        return jsonify({'success': False, 'message': f'数据加载失败: {str(e)}'}), 500


# ==================== New API Endpoints for Auto-Refresh ====================

@app.route('/api/timing', methods=['GET'])
@login_required
def api_timing_data():
    """获取上证分时数据"""
    try:
        user_id = get_current_user_id()
        data = market_service.get_timing_chart_data(user_id)
        response_data: dict[str, Any] = dict(data)

        prices = response_data.get('prices') or []
        if prices:
            response_data['current_price'] = prices[-1]
            change_amounts = response_data.get('change_amounts') or []
            change_pcts = response_data.get('change_pcts') or []
            response_data['change'] = change_amounts[-1] if change_amounts else 0
            response_data['change_pct'] = change_pcts[-1] if change_pcts else 0

        return jsonify({'success': True, 'data': response_data})
    except Exception as e:
        logger.error(f"获取上证分时数据失败: {e}")
        return jsonify({'success': False, 'message': f'数据加载失败: {str(e)}'}), 500


@app.route('/api/news/7x24', methods=['GET'])
@login_required
def api_news_7x24():
    """获取7*24快讯"""
    try:
        user_id = get_current_user_id()
        result = market_service.get_kx_news_raw(user_id)

        news_items = []
        if result:
            for item in result:
                try:
                    title = item.get('title', '')
                    if not title and 'content' in item and 'items' in item['content']:
                        content_items = item['content'].get('items', [])
                        if content_items and len(content_items) > 0:
                            title = content_items[0].get('data', '')

                    publish_time = item.get('publish_time', '')
                    if publish_time:
                        try:
                            publish_time = datetime.datetime.fromtimestamp(int(publish_time)).strftime("%H:%M:%S")
                        except Exception:
                            publish_time = ''

                    evaluate = item.get('evaluate', '')

                    news_items.append({
                        'time': publish_time,
                        'content': title,
                        'source': evaluate if evaluate else ''
                    })
                except Exception as e:
                    logger.debug(f"Error processing news item: {e}")
                    continue

        return jsonify({'success': True, 'data': news_items})
    except Exception as e:
        logger.error(f"获取7*24快讯失败: {e}")
        return jsonify({'success': False, 'message': f'数据加载失败: {str(e)}'}), 500


@app.route('/api/indices/global', methods=['GET'])
@login_required
def api_indices_global():
    """获取全球指数数据"""
    try:
        user_id = get_current_user_id()
        result = market_service.get_market_info_raw(user_id)

        indices = []
        if result:
            for item in result:
                if len(item) >= 3:
                    change_str = item[2] if item[2] else "0%"
                    change_str = change_str.replace('%', '').replace('\033[1;31m', '').replace('\033[1;32m', '')
                    change = float(change_str) if change_str else 0
                    indices.append({
                        'name': item[0],
                        'value': item[1],
                        'change': change_str + '%',
                        'change_pct': change
                    })

        return jsonify({'success': True, 'data': indices})
    except Exception as e:
        logger.error(f"获取全球指数失败: {e}")
        return jsonify({'success': False, 'message': f'数据加载失败: {str(e)}'}), 500


@app.route('/api/indices/volume', methods=['GET'])
@login_required
def api_indices_volume():
    """获取成交量趋势数据"""
    try:
        user_id = get_current_user_id()
        data = market_service.get_volume_chart_data(user_id)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        logger.error(f"获取成交量趋势失败: {e}")
        return jsonify({'success': False, 'message': f'数据加载失败: {str(e)}'}), 500

@app.route('/api/sectors', methods=['GET'])
@login_required
def api_sectors():
    """获取行业板块数据"""
    try:
        sectors = market_service.fetch_sectors()
        return jsonify({'success': True, 'data': sectors})
    except Exception as e:
        logger.error(f"获取行业板块失败: {e}")
        return jsonify({'success': False, 'message': f'数据加载失败: {str(e)}'}), 500


@app.route('/api/fund/list', methods=['GET'])
@login_required
def api_fund_list():
    """获取基金列表（含份额数据）"""
    try:
        user_id = get_current_user_id()
        result = fund_service.get_fund_list(user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"获取基金列表失败: {e}")
        return jsonify({'success': False, 'message': f'数据加载失败: {str(e)}'}), 500


@app.route('/api/sector/<sector_id>', methods=['GET'])
@login_required
def api_sector_funds(sector_id):
    """获取指定板块的基金列表"""
    try:
        user_id = get_current_user_id()
        result = market_service.get_select_fund(user_id, bk_id=sector_id)

        funds = []
        if result:
            for item in result:
                if len(item) >= 5:
                    funds.append({
                        'code': item[0],
                        'name': item[1],
                        'net_value': item[2],
                        'day_growth': item[3],
                        'estimated_growth': item[4] if len(item) > 4 else ''
                    })

        return jsonify({'success': True, 'data': funds})
    except Exception as e:
        logger.error(f"获取板块基金失败: {e}")
        return jsonify({'success': False, 'message': f'数据加载失败: {str(e)}'}), 500


@app.route('/', methods=['GET'])
@login_required
def get_index():
    # 重定向到持仓基金页面
    return redirect('/portfolio')


@app.route('/fund', methods=['GET'])
@login_required
def get_fund():
    # 重定向到持仓基金页面
    return redirect('/portfolio')


@app.route('/market', methods=['GET'])
@login_required
def get_market():
    # old 7*24快讯 route removed, redirect to portfolio
    return redirect('/portfolio')

@app.route('/market-indices', methods=['GET'])
@login_required
def get_market_indices():
    # market indices page removed; redirect to portfolio
    return redirect('/portfolio')


@app.route('/api/portfolio/fund-table', methods=['GET'])
@login_required
def api_portfolio_fund_table():
    """获取投资组合的基金表格数据（用于刷新）"""
    try:
        user_id = get_current_user_id()
        fund_service.settle_pending_buys(user_id)
        titles, rows, sortable_columns = market_service.build_fund_table(user_id)
        fund_table_html = render_template('partials/data_table.html', title=titles, data=rows, sortable_columns=sortable_columns)
        fund_map = fund_repo.get_user_funds(user_id)
        shares_map = {code: data.get('shares', 0) for code, data in fund_map.items()}
        fund_table_html = enhance_fund_tab_content(fund_table_html, shares_map)
        return jsonify({
            'success': True,
            'html': fund_table_html
        })
    except Exception as e:
        logger.error(f"获取基金表格失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取基金表格失败: {str(e)}'
        }), 500


@app.route('/portfolio', methods=['GET'])
@login_required
def get_portfolio():
    """持仓基金页面"""
    add = request.args.get("add")
    delete = request.args.get("delete")
    user_id = get_current_user_id()
    fund_service.settle_pending_buys(user_id)
    if add:
        fund_service.add_fund(user_id, add)
    if delete:
        fund_service.delete_fund(user_id, delete)

    # 加载基金数据
    try:
        titles, rows, sortable_columns = market_service.build_fund_table(user_id)
        fund_content = render_template('partials/data_table.html', title=titles, data=rows, sortable_columns=sortable_columns)
        fund_map = fund_repo.get_user_funds(user_id)
        shares_map = {code: data.get('shares', 0) for code, data in fund_map.items()}
        fund_content = enhance_fund_tab_content(fund_content, shares_map)
    except Exception as e:
        fund_content = f"<p style='color:#f44336;'>数据加载失败: {str(e)}</p>"

    # 获取用户基金列表
    user_funds = fund_repo.get_user_funds(user_id)

    # 确定默认显示的基金
    default_fund = None
    fund_chart_data = None
    fund_chart_info = {}

    if user_funds:
        # 1. 检查是否有用户设置的默认基金
        saved_default = fund_repo.get_chart_default_fund(user_id)
        if saved_default and saved_default['fund_code'] in user_funds:
            default_fund = saved_default
        # 2. 选择有持仓的基金（预估收益最高的）
        else:
            held_funds = {code: data for code, data in user_funds.items() if data.get('shares', 0) > 0}
            if held_funds:
                first_code = list(held_funds.keys())[0]
                default_fund = {
                    'fund_code': first_code,
                    'fund_key': held_funds[first_code]['fund_key'],
                    'fund_name': held_funds[first_code]['fund_name']
                }
            # 3. 选择自选列表第一个
            else:
                first_code = list(user_funds.keys())[0]
                default_fund = {
                    'fund_code': first_code,
                    'fund_key': user_funds[first_code]['fund_key'],
                    'fund_name': user_funds[first_code]['fund_name']
                }

        # 加载图表数据
        if default_fund:
            result = chart_service.get_fund_chart_data(user_id, default_fund['fund_code'])
            if result:
                fund_chart_data = result.get('chart_data')

        # 准备基金选择器信息
        for code, data in user_funds.items():
            fund_chart_info[code] = {
                'name': data['fund_name'],
                'is_default': (default_fund and code == default_fund['fund_code'])
            }

    return render_template('pages/portfolio.html',
        fund_content=fund_content,
        fund_chart_data=fund_chart_data,
        fund_chart_info=fund_chart_info,
        username=get_current_username()
    )


@app.route('/api/fund/chart-data')
@login_required
def api_fund_chart_data():
    """获取基金估值趋势图数据"""
    fund_code = request.args.get('code')
    if not fund_code:
        return jsonify({'error': 'Missing fund code'}), 400

    user_id = get_current_user_id()
    result = chart_service.get_fund_chart_data(user_id, fund_code)
    if result is None:
        return jsonify({'error': 'Fund not in user list'}), 400
    return jsonify(result)


@app.route('/api/fund/performance-chart-data')
@login_required
def api_fund_performance_chart_data():
    """获取基金业绩曲线数据。"""
    fund_code = request.args.get('code')
    date_interval = request.args.get('interval', DEFAULT_PERFORMANCE_CHART_INTERVAL).strip().upper()
    if not fund_code:
        return jsonify({'error': 'Missing fund code'}), 400

    if date_interval not in PERFORMANCE_CHART_INTERVALS:
        return jsonify({'error': 'Invalid interval'}), 400

    user_id = get_current_user_id()
    result = chart_service.get_fund_performance_chart_data(user_id, fund_code, date_interval)
    if result is None:
        return jsonify({'error': 'Fund not in user list'}), 400
    return jsonify(result)


@app.route('/api/index/sync-nav', methods=['POST'])
@login_required
def api_index_sync_nav():
    """从中证指数官网拉取指定指数历史净值并存库。
    Body JSON: {"index_code": "000300", "start_date": "20260101", "end_date": "20260420"}
    """
    body = request.get_json(silent=True) or {}
    index_code = str(body.get('index_code', '000300')).strip()
    start_date = str(body.get('start_date', '')).strip()
    end_date = str(body.get('end_date', '')).strip()
    try:
        result = nav_service.sync_index_nav(index_code, start_date, end_date)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Failed to fetch index nav for {index_code}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/fund/profit-chart-data')
@login_required
def api_fund_profit_chart_data():
    """获取基金累计收益曲线数据。"""
    fund_code = request.args.get('code')
    date_interval = request.args.get('interval', DEFAULT_PROFIT_CHART_INTERVAL).strip().upper()
    if not fund_code:
        return jsonify({'error': 'Missing fund code'}), 400

    if date_interval not in PERFORMANCE_CHART_INTERVALS:
        return jsonify({'error': 'Invalid interval'}), 400

    user_id = get_current_user_id()
    result = chart_service.get_fund_profit_chart_data(user_id, fund_code, date_interval)
    if result is None:
        return jsonify({'error': 'Fund not in user list'}), 400
    return jsonify(result)


@app.route('/api/fund/chart-default', methods=['POST'])
@login_required
def api_fund_chart_default():
    """设置估值趋势图默认基金"""
    data = request.json
    fund_code = data.get('fund_code')
    if not fund_code:
        return jsonify({'error': 'Missing fund code'}), 400

    user_id = get_current_user_id()
    if not chart_service.set_chart_default(user_id, fund_code):
        return jsonify({'error': 'Fund not in user list'}), 400
    return jsonify({'success': True})


@app.route('/api/config/refresh', methods=['GET'])
def api_config_refresh():
    """获取页面刷新配置"""
    config = get_page_refresh_config()
    return jsonify(config)


@app.route('/sectors', methods=['GET'])
@login_required
def get_sectors():
    """行业板块基金查询页面"""
    user_id = get_current_user_id()

    # 加载行业板块数据
    try:
        sectors_content = render_template('partials/data_table.html',
            title=["板块名称", "今日涨跌幅", "今日主力净流入", "今日主力净流入占比", "今日小单净流入", "今日小单流入占比"],
            data=market_service.get_bk_data_raw(user_id),
            sortable_columns=[1, 2, 3, 4, 5])
        logger.debug("✓ 行业板块")
    except Exception as e:
        sectors_content = f"<p style='color:#f44336;'>数据加载失败: {str(e)}</p>"

    # 加载板块基金查询数据
    try:
        data = market_service.get_select_fund(user_id)
        bk_list = data["bk_list"]
        major_categories = market_service.get_major_categories(user_id)
        categorized_sectors = []
        for category, sectors in major_categories.items():
            items = [(idx + 1, bk_list[idx]) for idx in range(len(bk_list)) if bk_list[idx] in sectors]
            if items:
                categorized_sectors.append((category, items))
        select_fund_content = render_template('partials/sector_selection.html',
            categorized_sectors=categorized_sectors)
        logger.debug("✓ 板块基金查询")
    except Exception as e:
        select_fund_content = f"<p style='color:#f44336;'>数据加载失败: {str(e)}</p>"

    return render_template('pages/sectors.html',
        sectors_content=sectors_content,
        select_fund_content=select_fund_content,
        username=get_current_username()
    )


class FilteredWSGIRequestLogger:
    """
    WSGI中间件，过滤静态资源请求日志（如/static/、/favicon.ico等）。
    """
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        # 过滤静态资源和favicon请求
        if path.startswith('/static/') or path.endswith('.ico') or path.startswith('/favicon'):
            # 禁止Flask默认日志输出
            import logging
            logging.getLogger('werkzeug').setLevel(logging.ERROR)
        else:
            import logging
            logging.getLogger('werkzeug').setLevel(logging.INFO)
        return self.app(environ, start_response)

if __name__ == '__main__':
    from werkzeug.serving import run_simple

    # Feature Flag: 设置环境变量 REFACTOR_USE_BLUEPRINTS=true 可切换到 Blueprint 架构
    if os.environ.get('REFACTOR_USE_BLUEPRINTS', '').lower() in ('1', 'true', 'yes'):
        from src.app import create_app
        app = create_app()

    # 用中间件包裹Flask app，过滤静态资源日志
    if not os.environ.get('REFACTOR_USE_BLUEPRINTS', '').lower() in ('1', 'true', 'yes'):
        app.wsgi_app = FilteredWSGIRequestLogger(app.wsgi_app)

    # 仅在 reloader 子进程启动后台日志清理线程，避免父进程重复启动
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        _start_log_cleanup_worker_if_needed()

    server_cfg = get_server_config()
    host = server_cfg.get("host", "0.0.0.0")
    port = server_cfg.get("port", 8311)

    # 避免日志文件/本地数据库写入触发 reloader 反复重启（会造成"日志清理频繁触发"的错觉）。
    # 低版本 Werkzeug 可能不支持 exclude_patterns，故做兼容回退。
    try:
        run_simple(
            host,
            port,
            app,
            use_reloader=True,
            use_debugger=False,
            exclude_patterns=[
                'cache/logs/*',
                'cache/*.db',
                'cache/**/*.db',
                '*.db-journal',
                '*.db-wal',
                '*.db-shm',
            ],
        )
    except TypeError:
        run_simple(host, port, app, use_reloader=True, use_debugger=False)
