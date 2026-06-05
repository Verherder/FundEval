# -*- coding: UTF-8 -*-
"""Market API routes — tabs, sectors, config."""

from flask import Blueprint, jsonify, render_template, request
from loguru import logger

from src.auth import get_current_user_id, login_required
from src.dependencies import get_fund_repo, get_fund_service, get_market_service, get_nav_service
from src.tab_enhancers import enhance_fund_tab_content
from src.config.yaml_config import get_page_refresh_config

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
            content = enhance_fund_tab_content(content, shares_map)
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


@api_market_bp.route("/config/refresh")
def api_config_refresh():
    config = get_page_refresh_config()
    return jsonify(config)
