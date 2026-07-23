# -*- coding: UTF-8 -*-

from functools import wraps

import secrets

from flask import abort, session, redirect, url_for, request
from loguru import logger


def login_required(f):
    """装饰器：要求用户登录才能访问"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # 如果是API请求，返回JSON错误
            if request.path.startswith('/api/'):
                return {'success': False, 'message': '请先登录'}, 401
            # 否则重定向到登录页
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)

    return decorated_function


def get_current_user_id():
    """获取当前登录用户的ID

    Returns:
        int or None
    """
    return session.get('user_id')


def get_current_username():
    """获取当前登录用户的用户名

    Returns:
        str or None
    """
    return session.get('username')


def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        from src.dependencies import get_user_repo
        if not get_user_repo().is_admin(get_current_user_id()):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def login_user(user_id, username):
    """登录用户，设置session

    Args:
        user_id: 用户ID
        username: 用户名
    """
    session.clear()
    session['user_id'] = user_id
    session['username'] = username
    session['csrf_token'] = secrets.token_urlsafe(32)
    logger.info(f"User logged in: id={user_id}")


def logout_user():
    """登出用户，清除session"""
    user_id = session.get('user_id', 'unknown')
    session.clear()
    logger.info(f"User logged out: id={user_id}")
