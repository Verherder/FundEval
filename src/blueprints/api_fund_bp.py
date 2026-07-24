# -*- coding: UTF-8 -*-
"""Fund API routes — CRUD, transactions, charts, portfolio data."""

import time
import threading
import os

from flask import Blueprint, after_this_request, jsonify, render_template, request, send_file
from loguru import logger

from src.auth import admin_required, get_current_user_id, login_required
from src.dependencies import (
    get_chart_service,
    get_fund_repo,
    get_fund_service,
    get_import_service,
    get_market_service,
    get_nav_service,
    get_tx_service,
)
from src.services.chart_service import (
    DEFAULT_PERFORMANCE_CHART_INTERVAL,
    DEFAULT_PROFIT_CHART_INTERVAL,
    PERFORMANCE_CHART_INTERVALS,
)
from src.tab_enhancers import enhance_fund_tab_content

api_fund_bp = Blueprint("api_fund", __name__, url_prefix="/api")

_PORTFOLIO_REFRESH_EVENTS = {}
_PORTFOLIO_REFRESH_EVENTS_LOCK = threading.Lock()


def _get_portfolio_refresh_event(refresh_id):
    if not refresh_id:
        return None
    with _PORTFOLIO_REFRESH_EVENTS_LOCK:
        event = _PORTFOLIO_REFRESH_EVENTS.get(refresh_id)
        if event is None:
            event = threading.Event()
            _PORTFOLIO_REFRESH_EVENTS[refresh_id] = event
        return event


def _pop_portfolio_refresh_event(refresh_id):
    if not refresh_id:
        return
    with _PORTFOLIO_REFRESH_EVENTS_LOCK:
        _PORTFOLIO_REFRESH_EVENTS.pop(refresh_id, None)


# ------------------------------------------------------------------
# Fund CRUD
# ------------------------------------------------------------------


@api_fund_bp.route("/fund/add", methods=["POST"])
@login_required
def api_fund_add():
    start = time.perf_counter()
    try:
        data = request.json
        codes = data.get("codes", "")
        if not codes:
            return {"success": False, "message": "请提供基金代码"}
        user_id = get_current_user_id()
        result = get_fund_service().add_fund(user_id, codes)
        return result
    except Exception as e:
        logger.error(f"添加基金失败: {e}")
        return {"success": False, "message": f"添加失败: {str(e)}"}
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(f"[API] /api/fund/add elapsed_ms={elapsed:.1f}")


@api_fund_bp.route("/fund/catalog", methods=["GET"])
@login_required
def api_fund_catalog():
    return jsonify(get_fund_repo().get_fund_catalog(get_current_user_id()))


@api_fund_bp.route("/fund/watchlist/add", methods=["POST"])
@login_required
def api_fund_watchlist_add():
    data = request.get_json(silent=True) or {}
    codes = data.get("codes", "")
    if not codes:
        return {"success": False, "message": "请选择基金"}, 400
    return get_fund_service().add_catalog_funds(get_current_user_id(), codes)


@api_fund_bp.route("/fund/backfill-establishment-dates", methods=["POST"])
@admin_required
def api_backfill_establishment_dates():
    start = time.perf_counter()
    try:
        user_id = get_current_user_id()
        return get_nav_service().backfill_all_establishment_dates(user_id)
    except Exception as e:
        logger.error(f"批量回填成立日期失败: {e}")
        return {
            "success": False,
            "message": f"回填失败: {str(e)}",
            "total": 0,
            "missing": 0,
            "updated": 0,
            "failed": 0,
            "failed_codes": [],
        }
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(f"[API] /api/fund/backfill-establishment-dates elapsed_ms={elapsed:.1f}")


@api_fund_bp.route("/fund/delete", methods=["POST"])
@login_required
def api_fund_delete():
    start = time.perf_counter()
    try:
        data = request.json
        codes = data.get("codes", "")
        if not codes:
            return {"success": False, "message": "请提供基金代码"}
        user_id = get_current_user_id()
        result = get_fund_service().delete_fund(user_id, codes)
        return result
    except Exception as e:
        logger.error(f"删除基金失败: {e}")
        return {"success": False, "message": f"删除失败: {str(e)}"}
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(f"[API] /api/fund/delete elapsed_ms={elapsed:.1f}")


@api_fund_bp.route("/fund/hold", methods=["POST"])
@login_required
def api_fund_set_hold():
    start = time.perf_counter()
    try:
        data = request.json
        codes = data.get("codes", "")
        hold = data.get("hold", True)
        if not codes:
            return {"success": False, "message": "请提供基金代码"}
        user_id = get_current_user_id()
        result = get_fund_service().set_hold(user_id, codes, hold)
        return result
    except Exception as e:
        logger.error(f"设置持有标记失败: {e}")
        return {"success": False, "message": f"操作失败: {str(e)}"}
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(f"[API] /api/fund/hold elapsed_ms={elapsed:.1f}")


@api_fund_bp.route("/fund/sector", methods=["POST"])
@admin_required
def api_fund_set_sector():
    start = time.perf_counter()
    try:
        data = request.json
        codes = data.get("codes", "")
        sectors = data.get("sectors", [])
        if not codes:
            return {"success": False, "message": "请提供基金代码"}
        if not sectors:
            return {"success": False, "message": "请选择板块"}
        user_id = get_current_user_id()
        result = get_fund_service().set_sector(user_id, codes, sectors)
        return result
    except Exception as e:
        logger.error(f"标注板块失败: {e}")
        return {"success": False, "message": f"操作失败: {str(e)}"}
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(f"[API] /api/fund/sector elapsed_ms={elapsed:.1f}")


@api_fund_bp.route("/fund/sector/remove", methods=["POST"])
@admin_required
def api_fund_remove_sector():
    start = time.perf_counter()
    try:
        data = request.json
        codes = data.get("codes", "")
        if not codes:
            return {"success": False, "message": "请提供基金代码"}
        user_id = get_current_user_id()
        result = get_fund_service().remove_sector(user_id, codes)
        return result
    except Exception as e:
        logger.error(f"删除板块标记失败: {e}")
        return {"success": False, "message": f"操作失败: {str(e)}"}
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(f"[API] /api/fund/sector/remove elapsed_ms={elapsed:.1f}")


# ------------------------------------------------------------------
# File upload / download
# ------------------------------------------------------------------


@api_fund_bp.route("/fund/upload", methods=["POST"])
@admin_required
def api_fund_upload():
    start = time.perf_counter()
    try:
        if "file" not in request.files:
            return {"success": False, "message": "未找到上传文件"}
        file = request.files["file"]
        file_bytes = file.read()
        user_id = get_current_user_id()
        result = get_fund_service().upload_funds(user_id, file_bytes, str(file.filename or ""))
        return result
    except Exception as e:
        logger.error(f"上传文件失败: {e}")
        return {"success": False, "message": f"上传失败: {str(e)}"}
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(f"[API] /api/fund/upload elapsed_ms={elapsed:.1f}")


@api_fund_bp.route("/fund/download", methods=["GET"])
@login_required
def api_fund_download():
    try:
        user_id = get_current_user_id()
        temp_path, download_name, mimetype = get_fund_service().download_funds(user_id)
        @after_this_request
        def cleanup_download(response):
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            return response
        return send_file(temp_path, as_attachment=True, download_name=download_name, mimetype=mimetype)
    except Exception as e:
        logger.error(f"下载文件失败: {e}")
        return {"success": False, "message": f"下载失败: {str(e)}"}


@api_fund_bp.route("/fund/transactions/download-all", methods=["GET"])
@login_required
def api_fund_transactions_download_all():
    try:
        user_id = get_current_user_id()
        temp_path, download_name, mimetype = get_fund_service().download_all_transactions(user_id)
        @after_this_request
        def cleanup_download(response):
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            return response
        return send_file(temp_path, as_attachment=True, download_name=download_name, mimetype=mimetype)
    except Exception as e:
        logger.error(f"下载全部交易记录备份失败: {e}")
        return {"success": False, "message": f"下载失败: {str(e)}"}


# ------------------------------------------------------------------
# Shares & trading
# ------------------------------------------------------------------


@api_fund_bp.route("/fund/shares", methods=["POST"])
@login_required
def api_fund_shares():
    data = request.json or {}
    code = data.get("code", "").strip()
    shares = data.get("shares", 0)
    if not code:
        return {"success": False, "message": "请提供基金代码"}
    try:
        shares = float(shares)
        if shares < 0:
            return {"success": False, "message": "份额不能为负数"}
    except (ValueError, TypeError):
        return {"success": False, "message": "份额格式错误"}
    user_id = get_current_user_id()
    return get_tx_service().update_fund_shares(user_id, code, shares)


@api_fund_bp.route("/fund/buy", methods=["POST"])
@login_required
def api_fund_buy():
    data = request.json or {}
    code = str(data.get("code", "")).strip()
    amount = data.get("amount", 0)
    if not code:
        return {"success": False, "message": "请提供基金代码"}
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return {"success": False, "message": "买入金额格式错误"}
    if amount <= 0:
        return {"success": False, "message": "买入金额必须大于0"}
    user_id = get_current_user_id()
    return get_tx_service().buy_fund(user_id, code, amount)


@api_fund_bp.route("/fund/buy-backfill", methods=["POST"])
@login_required
def api_fund_buy_backfill():
    data = request.json or {}
    code = str(data.get("code", "")).strip()
    amount = data.get("amount", 0)
    fee = data.get("fee", 0)
    net_value = data.get("net_value", None)
    trade_date = str(data.get("trade_date", "")).strip()
    if not code:
        return {"success": False, "message": "请提供基金代码"}
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return {"success": False, "message": "买入金额格式错误"}
    if amount <= 0:
        return {"success": False, "message": "买入金额必须大于0"}
    try:
        fee = float(fee)
    except (TypeError, ValueError):
        return {"success": False, "message": "手续费格式错误"}
    if fee < 0:
        return {"success": False, "message": "手续费不能为负数"}
    if amount <= fee:
        return {"success": False, "message": "买入金额需大于手续费"}
    user_id = get_current_user_id()
    return get_tx_service().buy_backfill(user_id, code, amount, fee, net_value, trade_date)


@api_fund_bp.route("/fund/net-value-by-date", methods=["GET"])
@login_required
def api_fund_net_value_by_date():
    code = str(request.args.get("code", "")).strip()
    trade_date = str(request.args.get("date", "")).strip()
    if not code:
        return {"success": False, "message": "请提供基金代码"}
    user_id = get_current_user_id()
    return get_tx_service().get_net_value_by_date(user_id, code, trade_date)


@api_fund_bp.route("/fund/sell-backfill", methods=["POST"])
@login_required
def api_fund_sell_backfill():
    data = request.json or {}
    code = str(data.get("code", "")).strip()
    shares_input = data.get("shares", None)
    fee = data.get("fee", 0)
    net_value = data.get("net_value", None)
    trade_date = str(data.get("trade_date", "")).strip()
    if not code:
        return {"success": False, "message": "请提供基金代码"}
    shares = None
    if shares_input is not None and str(shares_input).strip() != "":
        try:
            shares = float(shares_input)
        except (TypeError, ValueError):
            return {"success": False, "message": "卖出份额格式错误"}
        if shares <= 0:
            return {"success": False, "message": "卖出份额必须大于0"}
    try:
        fee = float(fee)
    except (TypeError, ValueError):
        return {"success": False, "message": "手续费格式错误"}
    if fee < 0:
        return {"success": False, "message": "手续费不能为负数"}
    user_id = get_current_user_id()
    return get_tx_service().sell_backfill(user_id, code, shares, fee, net_value, trade_date)


@api_fund_bp.route("/fund/dividend-backfill", methods=["POST"])
@login_required
def api_fund_dividend_backfill():
    data = request.json or {}
    code = str(data.get("code", "")).strip()
    amount = data.get("amount", 0)
    net_value = data.get("net_value", None)
    trade_date = str(data.get("trade_date", "")).strip()
    if not code:
        return {"success": False, "message": "请提供基金代码"}
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return {"success": False, "message": "分红金额格式错误"}
    if amount <= 0:
        return {"success": False, "message": "分红金额必须大于0"}
    user_id = get_current_user_id()
    return get_tx_service().dividend_backfill(user_id, code, amount, net_value, trade_date)


@api_fund_bp.route("/fund/sell", methods=["POST"])
@login_required
def api_fund_sell():
    data = request.json or {}
    code = str(data.get("code", "")).strip()
    shares = data.get("shares", 0)
    if not code:
        return {"success": False, "message": "请提供基金代码"}
    try:
        shares = float(shares)
    except (TypeError, ValueError):
        return {"success": False, "message": "卖出份额格式错误"}
    if shares <= 0:
        return {"success": False, "message": "卖出份额必须大于0"}
    user_id = get_current_user_id()
    return get_tx_service().sell_fund(user_id, code, shares)


# ------------------------------------------------------------------
# Transactions
# ------------------------------------------------------------------


@api_fund_bp.route("/fund/transactions", methods=["GET"])
@login_required
def api_fund_transactions():
    code = str(request.args.get("code", "")).strip()
    if not code:
        return {"success": False, "message": "请提供基金代码"}
    user_id = get_current_user_id()
    return get_tx_service().get_transactions(user_id, code)


@api_fund_bp.route("/fund/transactions/import", methods=["POST"])
@login_required
def api_fund_transactions_import():
    try:
        if "file" not in request.files:
            return {"success": False, "message": "未找到上传文件"}
        file = request.files["file"]
        if file.filename == "":
            return {"success": False, "message": "未选择文件"}
        file_bytes = file.read()
        user_id = get_current_user_id()
        return get_import_service().import_transactions(user_id, file_bytes, file.filename)
    except Exception as e:
        logger.error(f"导入交易记录失败: {e}")
        return {"success": False, "message": f"导入交易记录失败: {str(e)}"}


@api_fund_bp.route("/fund/transactions/import-progress", methods=["GET"])
@login_required
def api_fund_transactions_import_progress():
    job_id = str(request.args.get("job_id", "") or "").strip()
    return get_import_service().get_import_progress(get_current_user_id(), job_id)


@api_fund_bp.route("/fund/transaction/update", methods=["POST"])
@login_required
def api_fund_transaction_update():
    try:
        data = request.json or {}
        code = str(data.get("code", "")).strip()
        tx_id_raw = data.get("transaction_id", None)
        tx_type = str(data.get("tx_type", "")).strip().lower()
        amount = data.get("amount", 0)
        shares = data.get("shares", 0)
        net_value = data.get("net_value", 0)
        fee = data.get("fee", 0)
        tx_time_raw = str(data.get("tx_time", "")).strip()
        user_id = get_current_user_id()

        try:
            tx_id = int(str(tx_id_raw).strip())
        except (TypeError, ValueError):
            return {"success": False, "message": "交易ID格式错误"}

        return get_tx_service().update_transaction(
            user_id, code, tx_id, tx_type,
            float(amount) if amount else 0,
            float(shares) if shares else 0,
            float(net_value) if net_value else None,
            float(fee) if fee else 0,
            tx_time_raw,
        )
    except Exception as e:
        logger.error(f"更新交易记录失败: {e}")
        return {"success": False, "message": f"更新交易记录失败: {str(e)}"}


@api_fund_bp.route("/fund/transaction/delete", methods=["POST"])
@login_required
def api_fund_transaction_delete():
    try:
        data = request.json or {}
        code = str(data.get("code", "")).strip()
        tx_id_raw = data.get("transaction_id", None)
        user_id = get_current_user_id()

        try:
            tx_id = int(str(tx_id_raw).strip())
        except (TypeError, ValueError):
            return {"success": False, "message": "交易ID格式错误"}

        return get_tx_service().delete_transaction(user_id, code, tx_id)
    except Exception as e:
        logger.error(f"删除交易记录失败: {e}")
        return {"success": False, "message": f"删除交易记录失败: {str(e)}"}


@api_fund_bp.route("/fund/transactions/clear", methods=["POST"])
@admin_required
def api_fund_transactions_clear():
    try:
        data = request.json or {}
        code = str(data.get("code", "")).strip()
        confirm_text = str(data.get("confirm_text", "")).strip()
        user_id = get_current_user_id()
        return get_tx_service().clear_fund_transactions(user_id, code, confirm_text)
    except Exception as e:
        logger.error(f"清空交易记录失败: {e}")
        return {"success": False, "message": f"清空交易记录失败: {str(e)}"}


@api_fund_bp.route("/fund/transactions/clear-all", methods=["POST"])
@admin_required
def api_fund_transactions_clear_all():
    try:
        data = request.json or {}
        confirm_text = str(data.get("confirm_text", "")).strip()
        user_id = get_current_user_id()
        return get_tx_service().clear_all_transactions(user_id, confirm_text)
    except Exception as e:
        logger.error(f"清空全部交易记录失败: {e}")
        return {"success": False, "message": f"清空全部交易记录失败: {str(e)}"}


# ------------------------------------------------------------------
# Fund data
# ------------------------------------------------------------------


@api_fund_bp.route("/fund/data", methods=["GET"])
@login_required
def api_fund_data():
    try:
        user_id = get_current_user_id()
        fund_map = get_fund_service().get_fund_data(user_id)
        return jsonify(fund_map)
    except Exception as e:
        logger.error(f"获取基金数据失败: {e}")
        return jsonify({"error": str(e)}), 500


@api_fund_bp.route("/fund/list", methods=["GET"])
@login_required
def api_fund_list():
    try:
        user_id = get_current_user_id()
        result = get_fund_service().get_fund_list(user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"获取基金列表失败: {e}")
        return jsonify({"success": False, "message": f"数据加载失败: {str(e)}"}), 500


# ------------------------------------------------------------------
# Portfolio
# ------------------------------------------------------------------


@api_fund_bp.route("/portfolio/fund-table", methods=["GET"])
@login_required
def api_portfolio_fund_table():
    refresh_id = str(request.headers.get("X-Refresh-Id") or request.args.get("refresh_id") or "").strip()
    cancel_event = _get_portfolio_refresh_event(refresh_id)
    try:
        user_id = get_current_user_id()
        get_fund_service().settle_pending_buys(user_id)
        titles, rows, sortable_columns = get_market_service().build_fund_table(user_id, cancel_event=cancel_event)
        if cancel_event is not None and cancel_event.is_set():
            return jsonify({"success": False, "cancelled": True, "message": "刷新已停止"}), 499
        fund_table_html = render_template(
            "partials/data_table.html", title=titles, data=rows, sortable_columns=sortable_columns
        )
        fund_map = get_fund_repo().get_user_funds(user_id)
        shares_map = {code: data.get("shares", 0) for code, data in fund_map.items()}
        from src.dependencies import get_user_repo
        fund_table_html = enhance_fund_tab_content(
            fund_table_html,
            shares_map,
            is_admin=get_user_repo().is_admin(user_id),
        )
        return jsonify({"success": True, "html": fund_table_html})
    except Exception as e:
        logger.error(f"获取基金表格失败: {e}")
        return jsonify({"success": False, "message": f"获取基金表格失败: {str(e)}"}), 500
    finally:
        _pop_portfolio_refresh_event(refresh_id)


@api_fund_bp.route("/portfolio/fund-table/stop", methods=["POST"])
@login_required
def api_portfolio_fund_table_stop():
    body = request.get_json(silent=True) or {}
    refresh_id = str(body.get("refresh_id") or request.headers.get("X-Refresh-Id") or "").strip()
    if not refresh_id:
        return jsonify({"success": False, "message": "缺少 refresh_id"}), 400
    cancel_event = _get_portfolio_refresh_event(refresh_id)
    cancel_event.set()
    logger.info(f"收到组合刷新停止请求: refresh_id={refresh_id}")
    return jsonify({"success": True, "cancelled": True})


# ------------------------------------------------------------------
# Chart data
# ------------------------------------------------------------------


@api_fund_bp.route("/fund/latest-estimate")
@login_required
def api_fund_latest_estimate():
    fund_code = request.args.get("code")
    if not fund_code:
        return jsonify({"error": "Missing fund code"}), 400
    result = get_chart_service().get_latest_fund_estimate(get_current_user_id(), fund_code)
    if result is None:
        return jsonify({"error": "Fund not in user list"}), 400
    return jsonify(result)


@api_fund_bp.route("/fund/chart-data")
@login_required
def api_fund_chart_data():
    fund_code = request.args.get("code")
    if not fund_code:
        return jsonify({"error": "Missing fund code"}), 400
    user_id = get_current_user_id()
    result = get_chart_service().get_fund_chart_data(user_id, fund_code)
    if result is None:
        return jsonify({"error": "Fund not in user list"}), 400
    return jsonify(result)


@api_fund_bp.route("/fund/performance-chart-data")
@login_required
def api_fund_performance_chart_data():
    fund_code = request.args.get("code")
    date_interval = request.args.get("interval", DEFAULT_PERFORMANCE_CHART_INTERVAL).strip().upper()
    if not fund_code:
        return jsonify({"error": "Missing fund code"}), 400
    if date_interval not in PERFORMANCE_CHART_INTERVALS:
        return jsonify({"error": "Invalid interval"}), 400
    user_id = get_current_user_id()
    result = get_chart_service().get_fund_performance_chart_data(user_id, fund_code, date_interval)
    if result is None:
        return jsonify({"error": "Fund not in user list"}), 400
    return jsonify(result)


@api_fund_bp.route("/fund/profit-chart-data")
@login_required
def api_fund_profit_chart_data():
    fund_code = request.args.get("code")
    date_interval = request.args.get("interval", DEFAULT_PROFIT_CHART_INTERVAL).strip().upper()
    if not fund_code:
        return jsonify({"error": "Missing fund code"}), 400
    if date_interval not in PERFORMANCE_CHART_INTERVALS:
        return jsonify({"error": "Invalid interval"}), 400
    user_id = get_current_user_id()
    result = get_chart_service().get_fund_profit_chart_data(user_id, fund_code, date_interval)
    if result is None:
        return jsonify({"error": "Fund not in user list"}), 400
    return jsonify(result)


@api_fund_bp.route("/fund/chart-default", methods=["POST"])
@login_required
def api_fund_chart_default():
    data = request.json
    fund_code = data.get("fund_code")
    if not fund_code:
        return jsonify({"error": "Missing fund code"}), 400
    user_id = get_current_user_id()
    if not get_chart_service().set_chart_default(user_id, fund_code):
        return jsonify({"error": "Fund not in user list"}), 400
    return jsonify({"success": True})
