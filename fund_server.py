import datetime
import os, sys, time

os.makedirs("cache", exist_ok=True)

import importlib
import json
from decimal import Decimal, ROUND_HALF_UP

import urllib3
from dotenv import load_dotenv
from flask import Flask, request, render_template, redirect, url_for, jsonify, \
    send_file
from loguru import logger

# 确保 INFO 级别日志（含 HTTP 计时）在终端输出；级别由 config.xml 的 http_timing.log_level 控制
logger.remove()
logger.add(sys.stderr, level="INFO")

import fund
from src.auth import login_required, get_current_user_id, get_current_username, login_user, logout_user
from src.database import Database
from src.module_html import enhance_fund_tab_content
from src.yaml_config import get_page_refresh_config

PERFORMANCE_CHART_INTERVALS = {
    "ONE_MONTH",
    "THREE_MONTH",
    "SIX_MONTH",
    "ONE_YEAR",
    "THREE_YEAR",
}

# 加载环境变量
load_dotenv()

urllib3.disable_warnings()
urllib3.util.ssl_.DEFAULT_CIPHERS = ":".join(
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

app = Flask(__name__)
app.secret_key = "luobobo"
db = Database()  # 初始化数据库


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
                    user = db.get_user_by_username(username)
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

    success, user_id = db.verify_password(username, password)
    if success:
        login_user(user_id, username)
        response = redirect(url_for('get_fund'))

        # 如果勾选了记住我，设置cookie（7天有效）
        if remember_me:
            import hashlib
            user = db.get_user_by_username(username)
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
    success, message, user_id = db.create_user(username, password)
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
    importlib.reload(fund)
    my_fund = fund.LanFund(db=db)
    return my_fund.select_fund_html(bk_id=bk_id)


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
        importlib.reload(fund)
        my_fund = fund.LanFund(user_id=user_id, db=db)
        my_fund.add_code(codes)
        result = {'success': True, 'message': f'已添加基金: {codes}'}
        return result
    except Exception as e:
        logger.error(f"添加基金失败: {e}")
        result = {'success': False, 'message': f'添加失败: {str(e)}'}
        return result
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(f"[API] /api/fund/add elapsed_ms={elapsed:.1f}")


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
        importlib.reload(fund)
        my_fund = fund.LanFund(user_id=user_id, db=db)
        my_fund.delete_code(codes)
        result = {'success': True, 'message': f'已删除基金: {codes}'}
        return result
    except Exception as e:
        logger.error(f"删除基金失败: {e}")
        result = {'success': False, 'message': f'删除失败: {str(e)}'}
        return result
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
        importlib.reload(fund)
        my_fund = fund.LanFund(user_id=user_id, db=db)
        code_list = [c.strip() for c in codes.split(',')]
        for code in code_list:
            if code in my_fund.CACHE_MAP:
                my_fund.CACHE_MAP[code]['is_hold'] = hold
        my_fund.save_cache()
        action = '标记持有' if hold else '取消持有'
        result = {'success': True, 'message': f'已{action}: {codes}'}
        return result
    except Exception as e:
        logger.error(f"设置持有标记失败: {e}")
        result = {'success': False, 'message': f'操作失败: {str(e)}'}
        return result
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
        importlib.reload(fund)
        my_fund = fund.LanFund(user_id=user_id, db=db)
        code_list = [c.strip() for c in codes.split(',')]
        # 使用Web专用方法
        my_fund.mark_fund_sector_web(code_list, sectors)
        sectors_str = ", ".join(sectors)
        result = {'success': True, 'message': f'已标注板块: {codes} -> {sectors_str}'}
        return result
    except Exception as e:
        logger.error(f"标注板块失败: {e}")
        result = {'success': False, 'message': f'操作失败: {str(e)}'}
        return result
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
        importlib.reload(fund)
        my_fund = fund.LanFund(user_id=user_id, db=db)
        code_list = [c.strip() for c in codes.split(',')]
        # 使用Web专用方法
        my_fund.unmark_fund_sector_web(code_list)
        result = {'success': True, 'message': f'已删除板块标记: {codes}'}
        return result
    except Exception as e:
        logger.error(f"删除板块标记失败: {e}")
        result = {'success': False, 'message': f'操作失败: {str(e)}'}
        return result
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
        if file.filename == '':
            return {'success': False, 'message': '未选择文件'}

        if not file.filename.endswith('.json'):
            return {'success': False, 'message': '只支持JSON文件'}

        # 读取并解析JSON
        content = file.read().decode('gbk')  # 使用GBK编码
        fund_map = json.loads(content)

        # 验证数据格式
        if not isinstance(fund_map, dict):
            return {'success': False, 'message': '文件格式错误：应为JSON对象'}

        for code, fund_data in fund_map.items():
            if not isinstance(fund_data, dict):
                return {'success': False, 'message': f'基金{code}数据格式错误'}
            if 'fund_key' not in fund_data or 'fund_name' not in fund_data:
                return {'success': False, 'message': f'基金{code}缺少必要字段'}

        # 保存到数据库
        user_id = get_current_user_id()
        success = db.save_user_funds(user_id, fund_map)

        if success:
            result = {'success': True, 'message': f'成功导入{len(fund_map)}个基金'}
        else:
            result = {'success': False, 'message': '保存失败'}
        return result

    except json.JSONDecodeError:
        result = {'success': False, 'message': 'JSON格式错误'}
        return result
    except Exception as e:
        logger.error(f"上传文件失败: {e}")
        result = {'success': False, 'message': f'上传失败: {str(e)}'}
        return result
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(f"[API] /api/fund/upload elapsed_ms={elapsed:.1f}")


@app.route('/api/fund/download', methods=['GET'])
@login_required
def api_fund_download():
    """下载fund_map.json文件"""
    try:
        user_id = get_current_user_id()
        fund_map = db.get_user_funds(user_id)

        # 生成JSON文件
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', encoding='gbk', suffix='.json', delete=False) as f:
            json.dump(fund_map, f, ensure_ascii=False, indent=4)
            temp_path = f.name

        return send_file(
            temp_path,
            as_attachment=True,
            download_name='fund_map.json',
            mimetype='application/json'
        )

    except Exception as e:
        logger.error(f"下载文件失败: {e}")
        return {'success': False, 'message': f'下载失败: {str(e)}'}


# ==================== Shares Management ====================


def _normalize_nav_date(nav_date_text):
    """规范化净值日期到 YYYY-MM-DD。"""
    if not nav_date_text:
        return None
    nav_date_text = str(nav_date_text).strip()
    try:
        if len(nav_date_text) == 5:  # MM-DD
            current_year = datetime.date.today().year
            nav_date_text = f"{current_year}-{nav_date_text}"
        return datetime.date.fromisoformat(nav_date_text).isoformat()
    except Exception:
        return None


def _extract_net_value_and_date(net_value_text):
    """从形如 1.2345(2026-03-15) 的字符串提取净值和日期。"""
    text = str(net_value_text or '').strip()
    if not text:
        return None, None

    nav_value = None
    nav_date = None
    try:
        nav_value = float(text.split('(')[0])
    except Exception:
        nav_value = None

    if '(' in text and ')' in text:
        try:
            date_text = text.split('(')[1].split(')')[0]
            nav_date = _normalize_nav_date(date_text)
        except Exception:
            nav_date = None

    return nav_value, nav_date


def _get_latest_fund_quote(user_id, fund_code):
    """获取基金最新净值与净值日期。"""
    user_funds = db.get_user_funds(user_id)
    if fund_code not in user_funds:
        return None, None, None

    # 最新净值不是从业绩曲线接口取，而是复用 fund.search_code(True) 的结果。
    # 该结果内部会请求 DATA_SOURCE_URLS['fund123_matiaria_tpl']，并从响应中解析
    # netValue / netValueDate，这也是页面基金表“最新净值”的来源。
    importlib.reload(fund)
    my_fund = fund.LanFund(user_id=user_id, db=db)
    rows = my_fund.search_code(True) or []
    for row in rows:
        if row[0] == fund_code:
            net_value, nav_date = _extract_net_value_and_date(row[3])
            return net_value, nav_date, user_funds[fund_code]
    return None, None, user_funds[fund_code]


def _get_buy_effective_date(now_time=None):
    """买入生效净值日：15:00前为当日，15:00后为次日（交易日由净值更新自然对齐）。"""
    now_time = now_time or datetime.datetime.now()
    effective_date = now_time.date()
    if now_time.hour >= 15:
        effective_date = effective_date + datetime.timedelta(days=1)
    return effective_date.isoformat()


def _settle_pending_buys(user_id):
    """结算到期的待确认买入单。"""
    pending_orders = db.get_pending_buys(user_id)
    if not pending_orders:
        return 0

    settled_count = 0
    quote_cache = {}

    for order in pending_orders:
        fund_code = str(order.get('fund_code', '')).strip()
        if not fund_code:
            continue

        effective_date_text = str(order.get('effective_date', '')).strip()
        try:
            effective_date = datetime.date.fromisoformat(effective_date_text)
        except Exception:
            continue

        if fund_code not in quote_cache:
            quote_cache[fund_code] = _get_latest_fund_quote(user_id, fund_code)
        latest_net_value, latest_nav_date_text, _fund_data = quote_cache[fund_code]

        if not latest_net_value or latest_net_value <= 0 or not latest_nav_date_text:
            continue

        try:
            latest_nav_date = datetime.date.fromisoformat(latest_nav_date_text)
        except Exception:
            continue

        if latest_nav_date < effective_date:
            continue

        amount = float(order.get('amount', 0) or 0)
        shares = float((Decimal(str(amount)) / Decimal(str(latest_net_value))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        if amount <= 0 or shares <= 0:
            continue

        current_shares = db.update_fund_shares_delta(user_id, fund_code, shares)
        if current_shares is None:
            continue

        tx_time = f"{effective_date.isoformat()} 15:00:00"
        tx_id = db.add_fund_transaction(
            user_id=user_id,
            fund_code=fund_code,
            tx_type='buy',
            amount=amount,
            shares=shares,
            net_value=latest_net_value,
            tx_time=tx_time,
        )

        if tx_id is None:
            db.update_fund_shares_delta(user_id, fund_code, -shares)
            continue

        marked = db.mark_pending_buy_settled(
            pending_id=order['id'],
            settled_tx_id=tx_id,
            settled_net_value=latest_net_value,
            settled_shares=shares,
        )
        if marked:
            settled_count += 1

    return settled_count


def _find_net_value_by_date_from_trend(user_id, fund_code, target_date):
    """从基金业绩趋势点中查找指定日期净值（若趋势数据包含净值）。"""
    user_funds = db.get_user_funds(user_id)
    fund_data = user_funds.get(fund_code)
    if not fund_data:
        return None

    importlib.reload(fund)
    my_fund = fund.LanFund(user_id=user_id, db=db)
    chart_data = my_fund.get_fund_performance_chart_data(fund_code, fund_data, "THREE_YEAR")

    labels = chart_data.get('labels', []) or []
    net_values = chart_data.get('net_values', []) or []
    if not labels or not net_values:
        return None

    short_date = target_date[5:] if isinstance(target_date, str) and len(target_date) == 10 else target_date
    for index, label in enumerate(labels):
        if label != target_date and label != short_date:
            continue
        if index >= len(net_values):
            continue
        value = net_values[index]
        try:
            nav = float(value)
            if nav > 0:
                return round(nav, 4)
        except (TypeError, ValueError):
            continue

    return None

def _get_latest_fund_net_value(user_id, fund_code):
    """获取基金最新净值（用于买入/卖出换算）。"""
    net_value, _nav_date, fund_data = _get_latest_fund_quote(user_id, fund_code)
    return net_value, fund_data

@app.route('/api/fund/shares', methods=['POST'])
@login_required
def api_fund_shares():
    """更新基金持仓份额"""
    try:
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
        success = db.update_fund_shares(user_id, code, shares)

        if success:
            fund_map = db.get_user_funds(user_id)
            latest = fund_map.get(code, {})
            latest_shares = float(latest.get('shares', shares) or 0)
            latest_is_hold = bool(latest.get('is_hold', latest_shares > 0))
            return {
                'success': True,
                'message': f'已更新份额: {latest_shares:.4f}',
                'current_shares': latest_shares,
                'current_is_hold': latest_is_hold,
            }
        else:
            return {'success': False, 'message': '更新失败，基金不存在'}

    except Exception as e:
        logger.error(f"更新份额失败: {e}")
        return {'success': False, 'message': f'更新失败: {str(e)}'}


@app.route('/api/fund/buy', methods=['POST'])
@login_required
def api_fund_buy():
    """按金额买入基金，按净值日规则延迟确认份额。"""
    try:
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
        user_funds = db.get_user_funds(user_id)
        if code not in user_funds:
            return {'success': False, 'message': '基金不存在'}

        effective_date = _get_buy_effective_date()
        pending_id = db.add_pending_buy(
            user_id=user_id,
            fund_code=code,
            amount=amount,
            effective_date=effective_date,
        )
        if not pending_id:
            return {'success': False, 'message': '买入失败，待确认记录写入失败'}

        _settle_pending_buys(user_id)

        pending_list = db.get_pending_buys(user_id, code)
        is_pending = any(int(item.get('id', -1)) == int(pending_id) for item in pending_list)
        latest_funds = db.get_user_funds(user_id)
        current_shares = float(latest_funds.get(code, {}).get('shares', 0) or 0)

        today_text = datetime.date.today().isoformat()
        if is_pending:
            if effective_date == today_text:
                message = f'买入已提交：¥{amount:,.2f}，将按{effective_date}净值确认份额（15:00后）'
            else:
                message = f'买入已提交：¥{amount:,.2f}，将按{effective_date}及之后首个净值日确认份额'
        else:
            message = f'买入已确认：¥{amount:,.2f}，份额已按净值入账'

        return {
            'success': True,
            'message': message,
            'current_shares': current_shares,
            'pending': is_pending,
            'effective_date': effective_date,
        }
    except Exception as e:
        logger.error(f"买入失败: {e}")
        return {'success': False, 'message': f'买入失败: {str(e)}'}


@app.route('/api/fund/buy-backfill', methods=['POST'])
@login_required
def api_fund_buy_backfill():
    """补录买入：按指定日期净值与金额生成买入交易。"""
    try:
        data = request.json or {}
        code = str(data.get('code', '')).strip()
        amount = data.get('amount', 0)
        net_value = data.get('net_value', 0)
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
            net_value = float(net_value)
        except (TypeError, ValueError):
            return {'success': False, 'message': '净值格式错误'}
        if net_value <= 0:
            return {'success': False, 'message': '净值必须大于0'}

        try:
            normalized_date = datetime.date.fromisoformat(trade_date).isoformat()
        except Exception:
            return {'success': False, 'message': '交易日期格式错误，请使用YYYY-MM-DD'}

        buy_shares = float((Decimal(str(amount)) / Decimal(str(net_value))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        if buy_shares <= 0:
            return {'success': False, 'message': '买入金额过小，折算份额为0'}

        user_id = get_current_user_id()
        user_funds = db.get_user_funds(user_id)
        if code not in user_funds:
            return {'success': False, 'message': '基金不存在'}

        new_shares = db.update_fund_shares_delta(user_id, code, buy_shares)
        if new_shares is None:
            return {'success': False, 'message': '补录失败，份额更新异常'}

        tx_time = f"{normalized_date} 15:00:00"
        tx_id = db.add_fund_transaction(
            user_id=user_id,
            fund_code=code,
            tx_type='buy',
            amount=amount,
            shares=buy_shares,
            net_value=net_value,
            tx_time=tx_time,
        )
        if tx_id is None:
            db.update_fund_shares_delta(user_id, code, -buy_shares)
            return {'success': False, 'message': '补录失败，交易记录写入异常'}

        return {
            'success': True,
            'message': f'补录成功：{normalized_date} 按净值 {net_value:.4f} 买入 ¥{amount:,.2f}（{buy_shares:.2f}份）',
            'current_shares': new_shares,
            'trade_date': normalized_date,
            'shares': buy_shares,
        }
    except Exception as e:
        logger.error(f"补录买入失败: {e}")
        return {'success': False, 'message': f'补录买入失败: {str(e)}'}


@app.route('/api/fund/net-value-by-date', methods=['GET'])
@login_required
def api_fund_net_value_by_date():
    """按日期从趋势数据获取基金净值（若可用）。"""
    try:
        code = str(request.args.get('code', '')).strip()
        trade_date = str(request.args.get('date', '')).strip()

        if not code:
            return {'success': False, 'message': '请提供基金代码'}

        try:
            normalized_date = datetime.date.fromisoformat(trade_date).isoformat()
        except Exception:
            return {'success': False, 'message': '日期格式错误，请使用YYYY-MM-DD'}

        user_id = get_current_user_id()
        net_value = _find_net_value_by_date_from_trend(user_id, code, normalized_date)

        if net_value is None:
            return {
                'success': True,
                'found': False,
                'message': '趋势数据中未找到该日期净值，请手动输入',
                'trade_date': normalized_date,
            }

        return {
            'success': True,
            'found': True,
            'trade_date': normalized_date,
            'net_value': net_value,
        }
    except Exception as e:
        logger.error(f"按日期查询净值失败: {e}")
        return {'success': False, 'message': f'按日期查询净值失败: {str(e)}'}


@app.route('/api/fund/sell', methods=['POST'])
@login_required
def api_fund_sell():
    """按份额卖出基金并记录交易。"""
    try:
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
        _settle_pending_buys(user_id)
        user_funds = db.get_user_funds(user_id)
        if code not in user_funds:
            return {'success': False, 'message': '基金不存在'}

        current_holding = float(user_funds[code].get('shares', 0) or 0)
        if shares > current_holding:
            return {'success': False, 'message': f'卖出份额超过当前持仓（{current_holding:.4f}）'}

        net_value, _fund_data = _get_latest_fund_net_value(user_id, code)
        if not net_value or net_value <= 0:
            return {'success': False, 'message': '无法获取基金净值，暂无法卖出'}

        sell_amount = shares * net_value
        new_shares = db.update_fund_shares_delta(user_id, code, -shares)
        if new_shares is None:
            return {'success': False, 'message': '卖出失败，份额更新异常'}

        db.add_fund_transaction(
            user_id=user_id,
            fund_code=code,
            tx_type='sell',
            amount=sell_amount,
            shares=shares,
            net_value=net_value,
        )

        return {
            'success': True,
            'message': f'卖出成功：{shares:.4f} 份，约 ¥{sell_amount:,.2f}',
            'current_shares': new_shares,
            'net_value': net_value,
        }
    except Exception as e:
        logger.error(f"卖出失败: {e}")
        return {'success': False, 'message': f'卖出失败: {str(e)}'}


@app.route('/api/fund/data', methods=['GET'])
@login_required
def api_fund_data():
    """获取用户的基金数据（用于前端加载份额等信息）"""
    try:
        user_id = get_current_user_id()
        _settle_pending_buys(user_id)
        fund_map = db.get_user_funds(user_id)
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
        importlib.reload(fund)
        my_fund = fund.LanFund(user_id=user_id, db=db)

        # 定义tab ID到函数的映射
        tab_functions = {
            'kx': my_fund.kx_html,
            'marker': my_fund.marker_html,
            'real_time_gold': my_fund.real_time_gold_html,
            'gold': my_fund.gold_html,
            'seven_A': my_fund.seven_A_html,
            'A': my_fund.A_html,
            'fund': my_fund.fund_html,
            'bk': my_fund.bk_html,
            'select_fund': my_fund.select_fund_html,
        }

        if tab_id not in tab_functions:
            return jsonify({'success': False, 'message': f'未知的tab ID: {tab_id}'}), 404

        # 获取数据
        content = tab_functions[tab_id]()

        # 如果是fund tab，需要增强内容（传递份额数据）
        if tab_id == 'fund':
            user_id = get_current_user_id()
            fund_map = db.get_user_funds(user_id)
            shares_map = {code: data.get('shares', 0) for code, data in fund_map.items()}
            content = enhance_fund_tab_content(content, shares_map)

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
        importlib.reload(fund)
        my_fund = fund.LanFund(user_id=user_id, db=db)

        # 使用现有的 get_timing_chart_data 方法
        data = my_fund.get_timing_chart_data()

        # 添加当前价格和涨跌幅信息（使用原始数据中的正确涨跌幅）
        if data['prices']:
            data['current_price'] = data['prices'][-1]
            data['change'] = data['change_amounts'][-1] if data.get('change_amounts') else 0
            data['change_pct'] = data['change_pcts'][-1] if data.get('change_pcts') else 0

        return jsonify({'success': True, 'data': data})
    except Exception as e:
        logger.error(f"获取上证分时数据失败: {e}")
        return jsonify({'success': False, 'message': f'数据加载失败: {str(e)}'}), 500


@app.route('/api/news/7x24', methods=['GET'])
@login_required
def api_news_7x24():
    """获取7*24快讯"""
    try:
        importlib.reload(fund)
        my_fund = fund.LanFund(user_id=get_current_user_id(), db=db)

        # 获取快讯数据
        result = my_fund.kx(True)

        # 将数据转换为JSON格式
        # kx() 返回的是 list of dicts，需要正确提取字段
        news_items = []
        if result:
            for item in result:
                try:
                    # 提取标题和内容
                    title = item.get('title', '')
                    if not title and 'content' in item and 'items' in item['content']:
                        content_items = item['content'].get('items', [])
                        if content_items and len(content_items) > 0:
                            title = content_items[0].get('data', '')

                    # 提取发布时间
                    publish_time = item.get('publish_time', '')
                    if publish_time:
                        # 转换时间戳为可读格式
                        import datetime
                        try:
                            publish_time = datetime.datetime.fromtimestamp(int(publish_time)).strftime("%H:%M:%S")
                        except:
                            publish_time = ''

                    # 提取评估（利好/利空）
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
        importlib.reload(fund)
        my_fund = fund.LanFund(user_id=get_current_user_id(), db=db)

        # 获取全球指数数据 - 使用正确的方法名
        result = my_fund.get_market_info(True)

        # 将数据转换为JSON格式
        # result 格式: [[名称, 指数, 涨跌幅], ...]
        indices = []
        if result:
            for item in result:
                if len(item) >= 3:
                    # 清理涨跌幅中的颜色代码和%符号
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
        importlib.reload(fund)
        my_fund = fund.LanFund(user_id=get_current_user_id(), db=db)

        # 使用现有的 get_volume_chart_data 方法
        data = my_fund.get_volume_chart_data()

        return jsonify({'success': True, 'data': data})
    except Exception as e:
        logger.error(f"获取成交量趋势失败: {e}")
        return jsonify({'success': False, 'message': f'数据加载失败: {str(e)}'}), 500


@app.route('/api/gold/real-time', methods=['GET'])
@login_required
def api_gold_realtime():
    """获取实时贵金属价格"""
    try:
        importlib.reload(fund)
        my_fund = fund.LanFund(user_id=get_current_user_id(), db=db)

        # 获取实时金价数据
        # real_time_gold 返回 [[...], [...], [...]] 三个贵金属的数据
        # 每个数组有10列: [名称, 最新价, 涨跌额, 涨跌幅, 开盘价, 最高价, 最低价, 昨收价, 更新时间, 单位]
        result = my_fund.real_time_gold(True)

        # 将数据转换为JSON格式，保留所有10列
        gold_data = []
        gold_names = ['中国黄金', '周大福', '周生生']  # 根据API代码 JO_71, JO_92233, JO_92232

        if result and len(result) >= 3:
            # result[0], result[1], result[2] 分别是三种贵金属的数据
            for i, gold_type_data in enumerate(result):
                if len(gold_type_data) >= 4:  # 至少需要前4列
                    gold_data.append({
                        'name': gold_type_data[0] if gold_type_data else gold_names[i],
                        'price': gold_type_data[1] if len(gold_type_data) > 1 else '',
                        'change_amount': gold_type_data[2] if len(gold_type_data) > 2 else '',
                        'change_pct': gold_type_data[3] if len(gold_type_data) > 3 else '',
                        'open_price': gold_type_data[4] if len(gold_type_data) > 4 else '',
                        'high_price': gold_type_data[5] if len(gold_type_data) > 5 else '',
                        'low_price': gold_type_data[6] if len(gold_type_data) > 6 else '',
                        'prev_close': gold_type_data[7] if len(gold_type_data) > 7 else '',
                        'update_time': gold_type_data[8] if len(gold_type_data) > 8 else '',
                        'unit': gold_type_data[9] if len(gold_type_data) > 9 else ''
                    })

        return jsonify({'success': True, 'data': gold_data})
    except Exception as e:
        logger.error(f"获取实时金价失败: {e}")
        return jsonify({'success': False, 'message': f'数据加载失败: {str(e)}'}), 500


@app.route('/api/gold/history', methods=['GET'])
@login_required
def api_gold_history():
    """获取历史金价数据"""
    try:
        importlib.reload(fund)
        my_fund = fund.LanFund(user_id=get_current_user_id(), db=db)

        # 获取历史金价数据 (gold 是静态方法，返回 raw data)
        result = my_fund.gold(True)

        # gold 返回格式: [[日期, 中国黄金基础金价, 周大福金价, 中国黄金基础金价涨跌, 周大福金价涨跌], ...]
        gold_history = []
        if result:
            for item in result:
                if len(item) >= 3:
                    gold_history.append({
                        'date': item[0],
                        'china_gold_price': item[1],
                        'chow_tai_fook_price': item[2],
                        'china_gold_change': item[3] if len(item) > 3 else '',
                        'chow_tai_fook_change': item[4] if len(item) > 4 else ''
                    })

        return jsonify({'success': True, 'data': gold_history})
    except Exception as e:
        logger.error(f"获取历史金价失败: {e}")
        return jsonify({'success': False, 'message': f'数据加载失败: {str(e)}'}), 500


@app.route('/api/sectors', methods=['GET'])
@login_required
def api_sectors():
    """获取行业板块数据"""
    try:
        importlib.reload(fund)

        # 获取板块数据 (bk 是静态方法，返回 raw data)
        # 需要从API获取板块代码
        import requests
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "cb": "",
            "fid": "f62",
            "po": "1",
            "pz": "100",
            "pn": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "ut": "8dec03ba335b81bf4ebdf7b29ec27d15",
            "fs": "m:90 t:2",
            "fields": "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124,f1,f13"
        }
        response = requests.get(url, params=params, timeout=10, verify=False)
        if str(response.json()["data"]):
            data = response.json()["data"]
            sectors = []
            for bk in data["diff"]:
                sectors.append({
                    'code': bk["f12"],  # 板块代码
                    'name': bk["f14"],  # 板块名称
                    'change': str(bk["f3"]) + "%",  # 涨跌幅
                    'main_inflow': str(round(bk["f62"] / 100000000, 2)) + "亿",  # 主力净流入
                    'main_inflow_pct': str(round(bk["f184"], 2)) + "%",  # 主力净流入占比
                    'small_inflow': str(round(bk["f84"] / 100000000, 2)) + "亿",  # 小单净流入
                    'small_inflow_pct': str(round(bk["f87"], 2)) + "%"  # 小单流入占比
                })

            # 按涨跌幅降序排序（与原始 bk() 函数的排序逻辑一致）
            sectors = sorted(
                sectors,
                key=lambda x: float(x['change'].replace("%", "")) if x['main_inflow_pct'] != "N/A" else -99,
                reverse=True
            )
        else:
            sectors = []

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
        importlib.reload(fund)
        my_fund = fund.LanFund(user_id=user_id, db=db)

        # 获取用户基金数据
        fund_map = db.get_user_funds(user_id)

        # 将数据转换为JSON格式
        funds = []
        for code, data in fund_map.items():
            fund_info = my_fund.CACHE_MAP.get(code, {})
            funds.append({
                'code': code,
                'name': data.get('fund_name', fund_info.get('name', '')),
                'shares': data.get('shares', 0),
                'is_hold': data.get('is_hold', False),
                'sectors': data.get('sectors', []),
                'net_value': fund_info.get('net_value', 0),
                'day_growth': fund_info.get('day_growth', 0),
                'estimated_growth': fund_info.get('estimated_growth', 0)
            })

        return jsonify({'success': True, 'data': funds})
    except Exception as e:
        logger.error(f"获取基金列表失败: {e}")
        return jsonify({'success': False, 'message': f'数据加载失败: {str(e)}'}), 500


@app.route('/api/sector/<sector_id>', methods=['GET'])
@login_required
def api_sector_funds(sector_id):
    """获取指定板块的基金列表"""
    try:
        importlib.reload(fund)
        my_fund = fund.LanFund(user_id=get_current_user_id(), db=db)

        # 获取板块基金数据
        result = my_fund.select_fund(bk_id=sector_id, is_return=True)

        # 将数据转换为JSON格式
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


@app.route('/precious-metals', methods=['GET'])
@login_required
def get_precious_metals():
    """贵金属行情页面"""
    user_id = get_current_user_id()
    importlib.reload(fund)
    my_fund = fund.LanFund(user_id=user_id, db=db)

    # 加载贵金属数据
    precious_metals_data = {}
    try:
        precious_metals_data['real_time'] = my_fund.real_time_gold_html()
        logger.debug("✓ 实时贵金属")
    except Exception as e:
        precious_metals_data['real_time'] = f"<p style='color:#f44336;'>加载失败: {str(e)}</p>"

    try:
        precious_metals_data['history'] = my_fund.gold_html()
        logger.debug("✓ 历史金价")
    except Exception as e:
        precious_metals_data['history'] = f"<p style='color:#f44336;'>加载失败: {str(e)}</p>"

    from src.module_html import get_precious_metals_page_html
    html = get_precious_metals_page_html(precious_metals_data, username=get_current_username())
    return html


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
        _settle_pending_buys(user_id)
        importlib.reload(fund)
        my_fund = fund.LanFund(user_id=user_id, db=db)
        fund_table_html = my_fund.fund_html()
        fund_map = db.get_user_funds(user_id)
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
    _settle_pending_buys(user_id)
    importlib.reload(fund)
    my_fund = fund.LanFund(user_id=user_id, db=db)
    if add:
        my_fund.add_code(add)
    if delete:
        my_fund.delete_code(delete)

    # 加载基金数据
    try:
        fund_content = my_fund.fund_html()
        # 获取用户份额数据并传递给enhance_fund_tab_content
        fund_map = db.get_user_funds(user_id)
        shares_map = {code: data.get('shares', 0) for code, data in fund_map.items()}
        fund_content = enhance_fund_tab_content(fund_content, shares_map)
    except Exception as e:
        fund_content = f"<p style='color:#f44336;'>数据加载失败: {str(e)}</p>"

    # 获取用户基金列表
    user_funds = db.get_user_funds(user_id)

    # 确定默认显示的基金
    default_fund = None
    fund_chart_data = None
    fund_chart_info = {}

    if user_funds:
        # 1. 检查是否有用户设置的默认基金
        saved_default = db.get_chart_default_fund(user_id)
        if saved_default and saved_default['fund_code'] in user_funds:
            default_fund = saved_default
        # 2. 选择有持仓的基金（预估收益最高的）
        else:
            held_funds = {code: data for code, data in user_funds.items() if data.get('shares', 0) > 0}
            if held_funds:
                # 简化处理：选择第一个有持仓的基金
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
            fund_chart_data = my_fund.get_fund_chart_data(default_fund['fund_code'], default_fund)

        # 准备基金选择器信息
        for code, data in user_funds.items():
            fund_chart_info[code] = {
                'name': data['fund_name'],
                'is_default': (default_fund and code == default_fund['fund_code'])
            }

    from src.module_html import get_portfolio_page_html
    html = get_portfolio_page_html(
        fund_content=fund_content,
        fund_map=my_fund.CACHE_MAP,
        fund_chart_data=fund_chart_data,
        fund_chart_info=fund_chart_info,
        username=get_current_username()
    )
    return html


@app.route('/api/fund/chart-data')
@login_required
def api_fund_chart_data():
    """获取基金估值趋势图数据"""
    fund_code = request.args.get('code')
    if not fund_code:
        return jsonify({'error': 'Missing fund code'}), 400

    user_id = get_current_user_id()
    user_funds = db.get_user_funds(user_id)

    if fund_code not in user_funds:
        return jsonify({'error': 'Fund not in user list'}), 400

    fund_data = {
        'fund_key': user_funds[fund_code]['fund_key'],
        'fund_name': user_funds[fund_code]['fund_name']
    }

    importlib.reload(fund)
    my_fund = fund.LanFund(user_id=user_id, db=db)
    chart_data = my_fund.get_fund_chart_data(fund_code, fund_data)

    return jsonify({
        'chart_data': chart_data,
        'fund_info': {
            'code': fund_code,
            'name': fund_data['fund_name']
        }
    })


@app.route('/api/fund/performance-chart-data')
@login_required
def api_fund_performance_chart_data():
    """获取基金业绩曲线数据。"""
    fund_code = request.args.get('code')
    date_interval = request.args.get('interval', 'ONE_YEAR').strip().upper()
    if not fund_code:
        return jsonify({'error': 'Missing fund code'}), 400

    if date_interval not in PERFORMANCE_CHART_INTERVALS:
        return jsonify({'error': 'Invalid interval'}), 400

    user_id = get_current_user_id()
    user_funds = db.get_user_funds(user_id)

    if fund_code not in user_funds:
        return jsonify({'error': 'Fund not in user list'}), 400

    fund_data = {
        'fund_key': user_funds[fund_code]['fund_key'],
        'fund_name': user_funds[fund_code]['fund_name']
    }

    importlib.reload(fund)
    my_fund = fund.LanFund(user_id=user_id, db=db)
    chart_data = my_fund.get_fund_performance_chart_data(fund_code, fund_data, date_interval)

    transactions = db.get_fund_transactions(user_id, fund_code)
    chart_labels = chart_data.get('labels', []) or []
    chart_growth = chart_data.get('growth', []) or []
    growth_by_label = {
        str(label): chart_growth[index]
        for index, label in enumerate(chart_labels)
        if index < len(chart_growth)
    }

    trade_markers = []
    for tx in transactions:
        tx_time = str(tx.get('tx_time', '')).strip()
        if not tx_time:
            continue
        tx_date = tx_time.split(' ')[0]
        point_value = growth_by_label.get(tx_date)
        if point_value is None:
            continue
        tx_type = str(tx.get('tx_type', '')).strip().lower()
        trade_markers.append({
            'type': tx_type,
            'x': tx_date,
            'y': point_value,
            'amount': float(tx.get('amount', 0) or 0),
            'shares': float(tx.get('shares', 0) or 0),
            'net_value': float(tx.get('net_value', 0) or 0),
            'tx_time': tx_time,
        })

    chart_data['trade_markers'] = trade_markers

    latest_net_value, latest_nav_date, _latest_fund_data = _get_latest_fund_quote(user_id, fund_code)
    if latest_net_value and latest_net_value > 0:
        chart_data['latest_net_value'] = round(float(latest_net_value), 4)
    if latest_nav_date:
        chart_data['latest_net_value_date'] = latest_nav_date

    return jsonify({
        'chart_data': chart_data,
        'fund_info': {
            'code': fund_code,
            'name': fund_data['fund_name']
        }
    })


@app.route('/api/fund/chart-default', methods=['POST'])
@login_required
def api_fund_chart_default():
    """设置估值趋势图默认基金"""
    data = request.json
    fund_code = data.get('fund_code')
    if not fund_code:
        return jsonify({'error': 'Missing fund code'}), 400

    user_id = get_current_user_id()
    user_funds = db.get_user_funds(user_id)

    if fund_code not in user_funds:
        return jsonify({'error': 'Fund not in user list'}), 400

    db.update_chart_default(user_id, fund_code)
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
    importlib.reload(fund)
    my_fund = fund.LanFund(user_id=user_id, db=db)

    # 加载行业板块数据
    try:
        sectors_content = my_fund.bk_html()
        logger.debug("✓ 行业板块")
    except Exception as e:
        sectors_content = f"<p style='color:#f44336;'>数据加载失败: {str(e)}</p>"

    # 加载板块基金查询数据
    try:
        select_fund_content = my_fund.select_fund_html()
        logger.debug("✓ 板块基金查询")
    except Exception as e:
        select_fund_content = f"<p style='color:#f44336;'>数据加载失败: {str(e)}</p>"

    from src.module_html import get_sectors_page_html
    html = get_sectors_page_html(
        sectors_content=sectors_content,
        select_fund_content=select_fund_content,
        fund_map=my_fund.CACHE_MAP,
        username=get_current_username()
    )
    return html


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
    # 用中间件包裹Flask app，过滤静态资源日志
    from werkzeug.serving import run_simple
    app.wsgi_app = FilteredWSGIRequestLogger(app.wsgi_app)
    run_simple('0.0.0.0', 8311, app, use_reloader=True, use_debugger=False)
