# -*- coding: UTF-8 -*-
"""Authentication routes — login, register, logout."""

import hashlib

from flask import Blueprint, redirect, render_template, request, url_for
from loguru import logger

from src.auth import login_user, logout_user
from src.dependencies import get_user_repo

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        remember_token = request.cookies.get("remember_token")
        if remember_token:
            try:
                parts = remember_token.split(":")
                if len(parts) == 2:
                    username, token_hash = parts
                    user = get_user_repo().get_user_by_username(username)
                    if user:
                        expected_hash = hashlib.sha256(
                            f"{username}:{user['password_hash']}".encode()
                        ).hexdigest()
                        if token_hash == expected_hash:
                            login_user(user["id"], username)
                            return redirect(url_for("pages.get_fund"))
            except Exception as e:
                logger.error(f"Auto-login failed: {e}")

        return render_template("login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    remember_me = request.form.get("remember_me") == "1"

    if not username or not password:
        return render_template("login.html", error="请输入用户名和密码")

    success, user_id = get_user_repo().verify_password(username, password)
    if success:
        login_user(user_id, username)
        response = redirect(url_for("pages.get_fund"))

        if remember_me:
            user = get_user_repo().get_user_by_username(username)
            if user:
                token_hash = hashlib.sha256(
                    f"{username}:{user['password_hash']}".encode()
                ).hexdigest()
                remember_token = f"{username}:{token_hash}"
                response.set_cookie(
                    "remember_token",
                    remember_token,
                    max_age=7 * 24 * 60 * 60,
                    httponly=True,
                    samesite="Lax",
                    path=request.script_root or "/",
                )

        return response
    else:
        return render_template("login.html", error="用户名或密码错误")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not username or not password:
        return render_template("register.html", error="请输入用户名和密码")

    if len(username) < 3 or len(username) > 20:
        return render_template("register.html", error="用户名长度应为3-20个字符")

    if len(password) < 6:
        return render_template("register.html", error="密码长度至少为6个字符")

    if password != confirm_password:
        return render_template("register.html", error="两次输入的密码不一致")

    success, message, user_id = get_user_repo().create_user(username, password)
    if success:
        login_user(user_id, username)
        return redirect(url_for("pages.get_fund"))
    else:
        return render_template("register.html", error=message)


@auth_bp.route("/logout")
def logout():
    logout_user()
    response = redirect(url_for("auth.login"))
    response.set_cookie(
        "remember_token",
        "",
        max_age=0,
        path=request.script_root or "/",
    )
    return response
