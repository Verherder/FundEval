# -*- coding: UTF-8 -*-
"""Authentication routes with invite-only registration and revocable tokens."""

import datetime
import hashlib
import secrets

from flask import Blueprint, redirect, render_template, request, session, url_for
from loguru import logger

from src.auth import get_csrf_token, login_user, logout_user
from src.dependencies import get_user_repo
from src.security_validation import validate_password, validate_username

auth_bp = Blueprint("auth", __name__)


def _token_hash(token):
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _set_remember_cookie(response, token, max_age=7 * 24 * 60 * 60):
    response.set_cookie(
        "remember_token", token, max_age=max_age, httponly=True,
        secure=request.is_secure, samesite="Lax", path=request.script_root or "/",
    )


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        remember_token = request.cookies.get("remember_token")
        if remember_token:
            user = get_user_repo().consume_remember_token(_token_hash(remember_token))
            if user:
                login_user(user["user_id"], user["username"])
                response = redirect(url_for("pages.get_fund"))
                replacement = secrets.token_urlsafe(48)
                expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
                get_user_repo().save_remember_token(user["user_id"], _token_hash(replacement), expires.isoformat())
                _set_remember_cookie(response, replacement)
                return response
        return render_template("login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    if not username or not password:
        return render_template("login.html", error="请输入用户名和密码")

    identity = _token_hash(f"{username.lower()}|{request.remote_addr or ''}")
    if get_user_repo().login_is_limited(identity):
        return render_template("login.html", error="登录尝试过多，请稍后再试"), 429
    success, user_id = get_user_repo().verify_password(username, password)
    get_user_repo().record_login_attempt(identity, success)
    if not success:
        logger.warning("Login failed")
        return render_template("login.html", error="用户名或密码错误"), 401
    user = get_user_repo().get_user_by_username(username)
    if user and user.get("password_reset_required"):
        return render_template("login.html", error="密码已失效，请联系管理员重置"), 403

    login_user(user_id, username)
    response = redirect(url_for("pages.get_fund"))
    if request.form.get("remember_me") == "1":
        raw_token = secrets.token_urlsafe(48)
        expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
        get_user_repo().save_remember_token(user_id, _token_hash(raw_token), expires.isoformat())
        _set_remember_cookie(response, raw_token)
    return response


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")
    invite_code = request.form.get("invite_code", "").strip()
    invite_hash = _token_hash(invite_code)

    if not get_user_repo().invitation_is_valid(invite_hash):
        return render_template("register.html", error="邀请码无效或已过期"), 400
    if not validate_username(username):
        return render_template("register.html", error="用户名须为3-20位字母、数字或下划线"), 400
    if not validate_password(password):
        return render_template("register.html", error="密码须为12-20位字母、数字或允许的安全符号"), 400
    if password != confirm_password:
        return render_template("register.html", error="两次输入的密码不一致"), 400

    success, message, user_id = get_user_repo().create_user(username, password)
    if not success:
        return render_template("register.html", error=message), 400
    if not get_user_repo().consume_invitation(invite_hash, user_id):
        return render_template("register.html", error="邀请码已被使用，请联系管理员"), 409
    login_user(user_id, username)
    return redirect(url_for("pages.get_fund"))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    user_id = session.get("user_id")
    if user_id:
        get_user_repo().revoke_remember_tokens(user_id)
    logout_user()
    response = redirect(url_for("auth.login"))
    _set_remember_cookie(response, "", max_age=0)
    return response
