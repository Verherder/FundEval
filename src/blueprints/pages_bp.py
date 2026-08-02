# -*- coding: UTF-8 -*-
"""Page routes — full HTML pages served via Jinja templates."""

from flask import Blueprint, redirect, render_template, request, url_for
from loguru import logger

from src.auth import admin_required, get_current_user_id, get_current_username, login_required
from src.dependencies import get_fund_repo, get_fund_service, get_market_service, get_user_repo
from src.tab_enhancers import enhance_fund_tab_content

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
@login_required
def get_index():
    return redirect(url_for("pages.get_portfolio"))


@pages_bp.route("/fund")
@login_required
def get_fund():
    return redirect(url_for("pages.get_portfolio"))


@pages_bp.route("/market")
@login_required
def get_market():
    return redirect(url_for("pages.get_portfolio"))


@pages_bp.route("/market-indices")
@login_required
def get_market_indices():
    return redirect(url_for("pages.get_portfolio"))


@pages_bp.route("/portfolio")
@login_required
def get_portfolio():
    add = request.args.get("add")
    delete = request.args.get("delete")
    user_id = get_current_user_id()
    is_admin = get_user_repo().is_admin(user_id)
    fund_service = get_fund_service()

    fund_service.settle_pending_buys(user_id)
    if add:
        fund_service.add_fund(user_id, add)
    if delete:
        fund_service.delete_fund(user_id, delete)

    try:
        titles, rows, sortable_columns = get_market_service().build_fund_table(user_id)
        fund_content = render_template(
            "partials/data_table.html", title=titles, data=rows, sortable_columns=sortable_columns
        )
        fund_map = get_fund_repo().get_user_funds(user_id)
        shares_map = {code: data.get("shares", 0) for code, data in fund_map.items()}
        fund_content = enhance_fund_tab_content(fund_content, shares_map, is_admin=is_admin)
    except Exception as e:
        fund_content = f"<p style='color:#f44336;'>数据加载失败: {str(e)}</p>"

    user_funds = get_fund_repo().get_user_funds(user_id)

    default_fund = None
    fund_chart_data = None
    fund_chart_info = {}
    fund_repo = get_fund_repo()

    if user_funds:
        saved_default = fund_repo.get_chart_default_fund(user_id)
        if saved_default and saved_default["fund_code"] in user_funds:
            default_fund = saved_default
        else:
            held_funds = {code: data for code, data in user_funds.items() if data.get("shares", 0) > 0}
            if held_funds:
                first_code = list(held_funds.keys())[0]
                default_fund = {
                    "fund_code": first_code,
                    "fund_key": held_funds[first_code]["fund_key"],
                    "fund_name": held_funds[first_code]["fund_name"],
                }
            else:
                first_code = list(user_funds.keys())[0]
                default_fund = {
                    "fund_code": first_code,
                    "fund_key": user_funds[first_code]["fund_key"],
                    "fund_name": user_funds[first_code]["fund_name"],
                }

        for code, data in user_funds.items():
            fund_chart_info[code] = {
                "name": data["fund_name"],
                "is_default": (default_fund and code == default_fund["fund_code"]),
            }

    return render_template(
        "pages/portfolio.html",
        fund_content=fund_content,
        fund_chart_data=fund_chart_data,
        fund_chart_info=fund_chart_info,
        username=get_current_username(),
    )


@pages_bp.route("/sectors")
@login_required
def get_sectors():
    user_id = get_current_user_id()
    market_service = get_market_service()

    try:
        sectors_content = render_template(
            "partials/data_table.html",
            title=["板块名称", "今日涨跌幅", "今日主力净流入", "今日主力净流入占比", "今日小单净流入", "今日小单流入占比"],
            data=market_service.get_bk_data_raw(user_id),
            sortable_columns=[1, 2, 3, 4, 5],
        )
        logger.debug("✓ 行业板块")
    except Exception as e:
        sectors_content = f"<p style='color:#f44336;'>数据加载失败: {str(e)}</p>"

    try:
        data = market_service.get_select_fund(user_id)
        bk_list = data["bk_list"]
        major_categories = market_service.get_major_categories(user_id)
        categorized_sectors = []
        for category, sectors in major_categories.items():
            items = [(idx + 1, bk_list[idx]) for idx in range(len(bk_list)) if bk_list[idx] in sectors]
            if items:
                categorized_sectors.append((category, items))
        select_fund_content = render_template(
            "partials/sector_selection.html", categorized_sectors=categorized_sectors
        )
        logger.debug("✓ 板块基金查询")
    except Exception as e:
        select_fund_content = f"<p style='color:#f44336;'>数据加载失败: {str(e)}</p>"

    return render_template(
        "pages/sectors.html",
        sectors_content=sectors_content,
        select_fund_content=select_fund_content,
        username=get_current_username(),
    )


@pages_bp.route("/fund/sector")
@login_required
def get_sector_funds():
    bk_id = request.args.get("bk_id")
    user_id = get_current_user_id()
    data = get_market_service().get_select_fund(user_id, bk_id=bk_id)
    if "error" in data:
        return f'<p style="color: red; padding: 20px;">{data["error"]}</p>'
    return render_template(
        "partials/data_table.html",
        title=[
            "基金代码", "基金名称", "基金类型", "日期", "净值", "日增长率",
            "近1周", "近1月", "近3月", "近6月", "今年来", "近1年", "近2年", "近3年", "成立以来",
        ],
        data=data["results"],
        sortable_columns=[4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
    )


@pages_bp.route("/settings")
@admin_required
def get_settings():
    return render_template("pages/settings.html", username=get_current_username())
