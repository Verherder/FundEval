# -*- coding: UTF-8 -*-

from functools import wraps

import secrets

from flask import abort, current_app, session, redirect, url_for, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from loguru import logger

CSRF_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
CSRF_SALT = "fundeval-csrf-v1"


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
    serializer = URLSafeTimedSerializer(current_app.secret_key, salt=CSRF_SALT)
    return serializer.dumps({"user_id": session.get("user_id")})


def validate_csrf_token(token):
    supplied = str(token or "")
    if not supplied:
        return False
    try:
        serializer = URLSafeTimedSerializer(current_app.secret_key, salt=CSRF_SALT)
        payload = serializer.loads(supplied, max_age=CSRF_MAX_AGE_SECONDS)
        return payload.get("user_id") == session.get("user_id")
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        legacy_token = session.get("csrf_token")
        return bool(
            legacy_token
            and secrets.compare_digest(str(legacy_token), supplied)
        )


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        from src.dependencies import get_user_repo
        if not get_user_repo().is_admin(get_current_user_id()):
            if request.path.startswith("/api/"):
                return {"success": False, "message": "需要管理员权限"}, 403
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
    logger.info(f"User logged in: id={user_id}")


def logout_user():
    """登出用户，清除session"""
    user_id = session.get('user_id', 'unknown')
    session.clear()
    logger.info(f"User logged out: id={user_id}")
