# -*- coding: UTF-8 -*-
"""Market API routes — tabs, sectors, config."""

import datetime
import hashlib
import secrets

from flask import Blueprint, jsonify, render_template, request
from loguru import logger

from src.auth import admin_required, get_current_user_id, login_required
from src.dependencies import get_fund_repo, get_fund_service, get_market_service, get_nav_service, get_user_repo
from src.tab_enhancers import enhance_fund_tab_content
from src.config.yaml_config import MAX_FUND_REFRESH_BATCH_SIZE, get_refresh_settings, save_refresh_settings
from src.security_validation import validate_password

api_market_bp = Blueprint("api_market", __name__, url_prefix="/api")


# ------------------------------------------------------------------
# Tab fragments
# ------------------------------------------------------------------


@api_market_bp.route("/tab/<tab_id>")
@login_required
def api_get_tab_data(tab_id):
    try:
        user_id = get_current_user_id()
        market_service = get_market_service()

        if tab_id == "bk":
            content = render_template(
                "partials/data_table.html",
                title=["板块名称", "今日涨跌幅", "今日主力净流入", "今日主力净流入占比", "今日小单净流入", "今日小单流入占比"],
                data=market_service.get_bk_data_raw(user_id),
                sortable_columns=[1, 2, 3, 4, 5],
            )
        elif tab_id == "fund":
            titles, rows, sortable_columns = market_service.build_fund_table(user_id)
            content = render_template(
                "partials/data_table.html", title=titles, data=rows, sortable_columns=sortable_columns
            )
            fund_map = get_fund_repo().get_user_funds(user_id)
            shares_map = {code: data.get("shares", 0) for code, data in fund_map.items()}
            content = enhance_fund_tab_content(
                content,
                shares_map,
                is_admin=get_user_repo().is_admin(user_id),
            )
        elif tab_id == "select_fund":
            data = market_service.get_select_fund(user_id)
            bk_list = data["bk_list"]
            major_categories = market_service.get_major_categories(user_id)
            categorized_sectors = []
            for category, sectors in major_categories.items():
                items = [(idx + 1, bk_list[idx]) for idx in range(len(bk_list)) if bk_list[idx] in sectors]
                if items:
                    categorized_sectors.append((category, items))
            content = render_template(
                "partials/sector_selection.html", categorized_sectors=categorized_sectors
            )
        else:
            return jsonify({"success": False, "message": f"未知的tab ID: {tab_id}"}), 404

        return jsonify({"success": True, "content": content})
    except Exception as e:
        logger.error(f"加载tab {tab_id} 数据失败: {e}")
        return jsonify({"success": False, "message": f"数据加载失败: {str(e)}"}), 500


# ------------------------------------------------------------------
# Sectors
# ------------------------------------------------------------------


@api_market_bp.route("/sectors")
@login_required
def api_sectors():
    try:
        sectors = get_market_service().fetch_sectors()
        return jsonify({"success": True, "data": sectors})
    except Exception as e:
        logger.error(f"获取行业板块失败: {e}")
        return jsonify({"success": False, "message": f"数据加载失败: {str(e)}"}), 500


@api_market_bp.route("/sector/<sector_id>")
@login_required
def api_sector_funds(sector_id):
    try:
        user_id = get_current_user_id()
        result = get_market_service().get_select_fund(user_id, bk_id=sector_id)

        funds = []
        if result:
            for item in result:
                if len(item) >= 5:
                    funds.append({
                        "code": item[0],
                        "name": item[1],
                        "net_value": item[2],
                        "day_growth": item[3],
                        "estimated_growth": item[4] if len(item) > 4 else "",
                    })

        return jsonify({"success": True, "data": funds})
    except Exception as e:
        logger.error(f"获取板块基金失败: {e}")
        return jsonify({"success": False, "message": f"数据加载失败: {str(e)}"}), 500


# ------------------------------------------------------------------
# Index sync + config
# ------------------------------------------------------------------


@api_market_bp.route("/index/sync-nav", methods=["POST"])
@login_required
def api_index_sync_nav():
    body = request.get_json(silent=True) or {}
    index_code = str(body.get("index_code", "000300")).strip()
    start_date = str(body.get("start_date", "")).strip()
    end_date = str(body.get("end_date", "")).strip()
    try:
        result = get_nav_service().sync_index_nav(index_code, start_date, end_date)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Failed to fetch index nav for {index_code}: {e}")
        return jsonify({"error": str(e)}), 500


@api_market_bp.route("/config/refresh", methods=["GET", "PUT"])
@login_required
def api_config_refresh():
    if request.method == "GET":
        return jsonify(get_refresh_settings())
    if not get_user_repo().is_admin(get_current_user_id()):
        return jsonify({"success": False, "message": "需要管理员权限"}), 403

    body = request.get_json(silent=True) or {}
    try:
        enabled = body.get("auto_refresh_enabled")
        if not isinstance(enabled, bool):
            raise ValueError("自动刷新开关必须是布尔值")
        interval = int(body.get("auto_refresh_interval"))
        batch_size = int(body.get("request_batch_size"))
        if not 10000 <= interval <= 3600000:
            raise ValueError("自动刷新间隔必须在 10 秒到 60 分钟之间")
        if not 1 <= batch_size <= MAX_FUND_REFRESH_BATCH_SIZE:
            raise ValueError(f"同步基金数必须在 1 到 {MAX_FUND_REFRESH_BATCH_SIZE} 之间")
        return jsonify({"success": True, "settings": save_refresh_settings(enabled, interval, batch_size)})
    except (TypeError, ValueError) as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        logger.error(f"保存刷新配置失败: {e}")
        return jsonify({"success": False, "message": "保存设置失败"}), 500


@api_market_bp.route("/admin/invitations", methods=["POST"])
@admin_required
def api_create_invitation():
    body = request.get_json(silent=True) or {}
    try:
        days = int(body.get("days", 7))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "有效天数必须是整数"}), 400
    if not 1 <= days <= 30:
        return jsonify({"success": False, "message": "有效天数必须在 1 到 30 天之间"}), 400

    token = secrets.token_urlsafe(24)
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    invitation_id = get_user_repo().create_invitation(
        token_hash,
        get_current_user_id(),
        expires_at.isoformat(),
    )
    if not invitation_id:
        return jsonify({"success": False, "message": "邀请码生成失败"}), 500
    return jsonify(
        {
            "success": True,
            "invite_code": token,
            "expires_at": expires_at.isoformat(),
        }
    )


@api_market_bp.route("/admin/users", methods=["GET"])
@admin_required
def api_admin_users():
    return jsonify(
        {
            "success": True,
            "current_user_id": get_current_user_id(),
            "users": get_user_repo().list_users(),
        }
    )


@api_market_bp.route("/admin/users/<int:user_id>", methods=["PATCH"])
@admin_required
def api_admin_update_user(user_id):
    body = request.get_json(silent=True) or {}
    action = str(body.get("action", "")).strip()
    current_user_id = get_current_user_id()
    users = {user["id"]: user for user in get_user_repo().list_users()}
    target = users.get(user_id)
    if not target:
        return jsonify({"success": False, "message": "用户不存在"}), 404

    if action == "set_admin":
        if user_id == current_user_id:
            return jsonify({"success": False, "message": "不能修改自己的管理员权限"}), 400
        is_admin = body.get("is_admin")
        if not isinstance(is_admin, bool):
            return jsonify({"success": False, "message": "管理员状态格式错误"}), 400
        if not is_admin and target["is_admin"]:
            admin_count = sum(1 for user in users.values() if user["is_admin"])
            if admin_count <= 1:
                return jsonify({"success": False, "message": "系统必须至少保留一个管理员"}), 400
        success = get_user_repo().set_user_admin(user_id, is_admin)
    elif action == "set_locked":
        if user_id == current_user_id:
            return jsonify({"success": False, "message": "不能锁定自己的账号"}), 400
        is_locked = body.get("is_locked")
        if not isinstance(is_locked, bool):
            return jsonify({"success": False, "message": "锁定状态格式错误"}), 400
        success = get_user_repo().set_user_locked(user_id, is_locked)
    elif action == "reset_password":
        password = str(body.get("password", ""))
        if not validate_password(password):
            return jsonify({"success": False, "message": "密码须为12-20位字母、数字或允许的安全符号"}), 400
        success = get_user_repo().reset_password(target["username"], password)
    else:
        return jsonify({"success": False, "message": "不支持的用户管理操作"}), 400

    if not success:
        return jsonify({"success": False, "message": "用户更新失败"}), 500
    return jsonify({"success": True, "message": "用户已更新"})
