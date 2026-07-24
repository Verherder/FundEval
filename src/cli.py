# -*- coding: UTF-8 -*-
"""Administrative commands for schema migration and user access."""

import argparse
import datetime
import hashlib
import getpass
import json
import os
import secrets
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

from src.database import Database
from src.schema import migrate_legacy_database
from src.security_validation import validate_password


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def default_db_path():
    return Path(os.environ.get("FUNDEVAL_DATA_DIR", PROJECT_ROOT / "cache")) / "fund_data.db"


def sqlite_snapshot(source, target):
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with sqlite3.connect(str(source)) as src, sqlite3.connect(str(target)) as dst:
        src.backup(dst)
    os.chmod(target, 0o600)


def command_migrate(args):
    db_path = Path(args.database)
    legacy_path = PROJECT_ROOT / "cache" / "fund_data.db"
    source_path = db_path if db_path.exists() else legacy_path
    if not source_path.exists():
        raise SystemExit(f"数据库不存在: {db_path}")
    summary = migrate_legacy_database(source_path, apply=False)
    if args.dry_run:
        print(json.dumps({**summary, "source": str(source_path), "target": str(db_path)}, ensure_ascii=False, indent=2))
        return
    if source_path != db_path:
        sqlite_snapshot(source_path, db_path)
    backup_path = db_path.with_suffix(f".pre-v2-{datetime.datetime.now():%Y%m%d%H%M%S}.bak")
    sqlite_snapshot(db_path, backup_path)
    result = migrate_legacy_database(db_path, apply=True)
    print(json.dumps({**result, "backup": str(backup_path)}, ensure_ascii=False, indent=2))


def command_invite(args):
    db = Database(args.database)
    with db.get_connection() as conn:
        admin = conn.execute("SELECT id FROM users WHERE username=? AND is_admin=1", (args.admin,)).fetchone()
    if not admin:
        raise SystemExit("管理员不存在或没有管理员权限")
    token = secrets.token_urlsafe(24)
    expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=args.days)
    db.create_invitation(hashlib.sha256(token.encode()).hexdigest(), admin[0], expires.isoformat())
    print(token)


def command_reset_password(args):
    password = getpass.getpass("新密码: ")
    confirmation = getpass.getpass("再次输入: ")
    if password != confirmation:
        raise SystemExit("两次输入的密码不一致")
    if not validate_password(password):
        raise SystemExit("密码须为12-20位字母、数字或允许的安全符号")
    if not Database(args.database).reset_password(args.username, password):
        raise SystemExit("用户不存在")
    print("密码已更新，旧登录令牌已撤销")


def main():
    parser = argparse.ArgumentParser(prog="fundeval-admin")
    sub = parser.add_subparsers(required=True)
    migrate = sub.add_parser("migrate")
    migrate.add_argument("--database", default=str(default_db_path()))
    migrate.add_argument("--dry-run", action="store_true")
    migrate.set_defaults(func=command_migrate)
    invite = sub.add_parser("invite")
    invite.add_argument("--database", default=str(default_db_path()))
    invite.add_argument("--admin", default="jiaming")
    invite.add_argument("--days", type=int, default=7)
    invite.set_defaults(func=command_invite)
    reset_password = sub.add_parser("reset-password")
    reset_password.add_argument("username")
    reset_password.add_argument("--database", default=str(default_db_path()))
    reset_password.set_defaults(func=command_reset_password)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
