# FundEval 服务器更新操作手册

本文对应当前实际环境：

- 服务器项目目录：`~/FundEval`
- Python 环境：mamba 的 `finance`
- 应用监听：`127.0.0.1:8888`
- 对外地址：Nginx 的 `/fundeval/`
- 运行数据库：`~/FundEval/cache/fund_data.db`
- Rclone、Restic 和 OneDrive 已配置，并已成功备份过一次
- 本地数据库已经完成多用户 schema v2 改造，服务器采用本地数据库

按本文顺序执行即可。不要在服务器再次执行 `restic init`，也不要执行数据库迁移命令。

## 1. 配置文件说明

服务器上有两个名称相近但用途完全不同的配置文件：

| 文件 | 用途 | 是否进入 Git |
| --- | --- | --- |
| `~/FundEval/.env` | FundEval 服务、Session 和 CSRF 配置 | 否 |
| `~/.config/fundeval/restic.env` | Restic 和 OneDrive 连接配置 | 否 |

`~/FundEval/.env` 不是 Python 环境文件。启停脚本会读取它，并自动找到 mamba 的
`finance` 环境，因此启动前不需要执行 `mamba activate finance`。

`FUNDEVAL_SECRET_KEY` 用于签名登录 Session 和 CSRF 令牌，不是数据库加密密钥。它只在
服务器首次配置时生成一次，以后更新和重启均不得更换，否则现有登录状态会全部失效。

## 2. 本地准备代码

在本地项目目录运行测试：

```bash
cd "/Users/jiaming/Library/CloudStorage/OneDrive-mails.ucas.edu.cn/workspace/FundEval"
mamba run -n finance python -m pytest
git diff --check
git status --short
```

确认结果正常后，只提交程序、测试和文档。不要提交 `cache/`、`.runtime/` 或 `.env`：

```bash
git add src scripts tests docs README.md requirements.txt .env.example .gitignore
git commit -m "完善多用户隔离、权限管理和会话安全"
git push
```

若某个路径没有修改，`git add` 不会因此产生额外内容。提交后再次确认：

```bash
git status --short
```

## 3. 本地生成数据库上传副本

不要直接复制可能正在被本地服务写入的 `cache/fund_data.db`。使用 SQLite Online Backup
API 生成一致性副本：

```bash
cd "/Users/jiaming/Library/CloudStorage/OneDrive-mails.ucas.edu.cn/workspace/FundEval"
rm -f cache/fund_data.upload.db
mamba run -n finance python - <<'PY'
import sqlite3

with sqlite3.connect("cache/fund_data.db") as source:
    with sqlite3.connect("cache/fund_data.upload.db") as target:
        source.backup(target)
        print("integrity_check:", target.execute("PRAGMA integrity_check").fetchone()[0])
        print("foreign_key_check:", target.execute("PRAGMA foreign_key_check").fetchall())
        print("schema_version:", target.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()[0])
PY
chmod 600 cache/fund_data.upload.db
ls -lh cache/fund_data.upload.db
```

预期结果：

```text
integrity_check: ok
foreign_key_check: []
schema_version: 2
```

将副本上传到服务器。把下面的 `服务器地址` 替换为实际域名或 IP：

```bash
scp cache/fund_data.upload.db admin@39.96.1.147:/home/admin/FundEval/cache/fund_data.upload.db
```

## 4. 服务器更新代码

登录服务器：

```bash
ssh admin@服务器地址
cd ~/FundEval
```

确认现有 Restic 仓库可用。这里不重新初始化：

```bash
set -a
. ~/.config/fundeval/restic.env
set +a
restic snapshots --host fundeval-prod --tag fundeval
restic check
```

`restic snapshots` 应显示之前的快照，`restic check` 应成功。

停止服务并更新代码：

```bash
cd ~/FundEval
./scripts/stop.sh
./scripts/status.sh
git pull
mamba run -n finance python -m pip install -r requirements.txt
```

`status` 应显示服务未运行。此时浏览器暂时无法访问是正常现象。

## 5. 服务器创建应用 `.env`

先检查文件是否已经存在：

```bash
cd ~/FundEval
ls -l .env
```

### 5.1 `.env` 已存在

不要覆盖它。检查必需变量是否存在，但不要把密钥内容打印到终端：

```bash
grep -E '^(FUNDEVAL_ENV|FUNDEVAL_SECURE_COOKIE|FUNDEVAL_ENV_NAME)=' .env
grep -qE '^FUNDEVAL_SECRET_KEY=.+$' .env && echo "FUNDEVAL_SECRET_KEY: 已设置"
chmod 600 .env
```

预期至少包含：

```text
FUNDEVAL_ENV=production
FUNDEVAL_SECURE_COOKIE=auto
FUNDEVAL_SESSION_COOKIE_NAME=fundeval_session
FUNDEVAL_ENV_NAME=finance
FUNDEVAL_SECRET_KEY: 已设置
```

将已有配置的 Cookie 模式更新为自动适配：

```bash
if grep -q '^FUNDEVAL_SECURE_COOKIE=' .env; then
  perl -pi -e 's/^FUNDEVAL_SECURE_COOKIE=.*/FUNDEVAL_SECURE_COOKIE=auto/' .env
else
  printf '%s\n' 'FUNDEVAL_SECURE_COOKIE=auto' >> .env
fi
chmod 600 .env
```

`auto` 会根据 Nginx 的 `X-Forwarded-Proto` 设置 Cookie：外部 HTTP 不加 `Secure`，外部
HTTPS 自动加 `Secure`，避免认证成功后浏览器不回传 Session Cookie 造成登录循环。
应用使用独立的 `fundeval_session` Cookie，并自动把路径限制为 `/fundeval`，避免与同一
域名下其他应用的 Session Cookie 冲突。

### 5.2 `.env` 不存在

仅在文件不存在时执行以下命令。该命令直接生成配置，不使用 `sed`：

```bash
cd ~/FundEval
umask 077
SECRET="$(openssl rand -hex 32)"
printf '%s\n' \
  'FUNDEVAL_ENV=production' \
  "FUNDEVAL_SECRET_KEY=${SECRET}" \
  'FUNDEVAL_SECURE_COOKIE=auto' \
  'FUNDEVAL_SESSION_COOKIE_NAME=fundeval_session' \
  'FUNDEVAL_ENV_NAME=finance' \
  > .env
unset SECRET
chmod 600 .env
```

检查配置，不显示密钥：

```bash
grep -E '^(FUNDEVAL_ENV|FUNDEVAL_SECURE_COOKIE|FUNDEVAL_ENV_NAME)=' .env
grep -qE '^FUNDEVAL_SECRET_KEY=.+$' .env && echo "FUNDEVAL_SECRET_KEY: 已设置"
```

以后 `git pull` 不会覆盖 `.env`。不要重新执行本节的生成命令。

## 6. 替换服务器数据库

本次采用已经改造完成的本地 schema v2 数据库，不在服务器运行迁移。

确认上传文件存在：

```bash
ls -lh /home/admin/FundEval/cache/fund_data.upload.db
```

保留服务器旧数据库并安装新数据库：

```bash
cd ~/FundEval
mkdir -p cache
if [ -f cache/fund_data.db ]; then
  cp -p cache/fund_data.db "cache/fund_data.before-v2-$(date +%Y%m%d%H%M%S).db"
fi
install -m 600 /home/admin/FundEval/cache/fund_data.upload.db cache/fund_data.db
rm -f /home/admin/FundEval/cache/fund_data.upload.db
```

检查正式运行库：

```bash
mamba run -n finance python - <<'PY'
import sqlite3

with sqlite3.connect("cache/fund_data.db") as conn:
    print("integrity_check:", conn.execute("PRAGMA integrity_check").fetchone()[0])
    print("foreign_key_check:", conn.execute("PRAGMA foreign_key_check").fetchall())
    print("schema_version:", conn.execute(
        "SELECT value FROM schema_meta WHERE key='schema_version'"
    ).fetchone()[0])
    for table in ("users", "fund_catalog", "user_watchlist", "fund_transactions"):
        count = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"{table}: {count}")
PY
```

必须满足：

- `integrity_check: ok`
- `foreign_key_check: []`
- `schema_version: 2`
- 用户、基金、自选和交易数量符合本地数据库预期

## 7. 启动并验证

启动服务：

```bash
cd ~/FundEval
./scripts/start.sh
./scripts/status.sh
curl -I http://127.0.0.1:8888/
```

`status` 应显示运行中。`curl` 返回 `200` 或跳转到登录页的 `302` 都说明应用端口可访问。

Nginx 子路径配置应为：

```nginx
location = /fundeval {
    return 301 /fundeval/;
}

location /fundeval/ {
    proxy_pass http://127.0.0.1:8888/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Prefix /fundeval;
    proxy_read_timeout 180s;
}
```

检查并重新加载 Nginx：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

浏览器访问：

```text
https://你的域名/fundeval/
```

依次验证：

1. 登录和退出不出现 `Bad Request CSRF validation failed`。
2. 管理员能看到设置、邀请码、用户管理和敏感操作。
3. 普通用户看不到管理员功能，但可以查看全部基金并添加自己的自选。
4. 不同用户的自选、持仓、交易和收益数据相互隔离。
5. 原有管理员的基金、交易和收益数据正确。

登录页的签名 CSRF Token 正常有效期为 7 天。首次发布后，即使浏览器恢复了发布前的旧
登录页，应用也会在严格校验 `Origin/Referer` 与当前站点完全一致后继续处理登录，不再
直接显示 CSRF 400；跨站提交仍会被拒绝。设置、交易和用户管理等其他写操作没有此兜底，
仍必须通过签名 Token 校验。此后只要 `FUNDEVAL_SECRET_KEY` 不变，正常重启不会让令牌失效。

## 8. 向现有 Restic 仓库追加备份

服务可以保持运行。统一使用项目备份脚本，它会通过 SQLite Online Backup API 创建一致性
暂存库、校验、上传并清理暂存文件：

```bash
cd ~/FundEval
./scripts/restic_backup.sh
tail -n 100 logs/restic_backup.log
```

日志应以 `backup complete` 结束。数据库检查、首次配置、实际恢复验证、定时任务和解除旧
`cache/.git` 的完整顺序见：

[Restic + OneDrive 备份手册](BACKUP_RESTIC_ONEDRIVE.md)。

## 9. 日常启停和更新

日常启停：

```bash
cd ~/FundEval
./scripts/start.sh
./scripts/stop.sh
./scripts/restart.sh
./scripts/status.sh
./scripts/fundctl.sh logs
```

以后只更新程序，不再替换数据库：

```bash
cd ~/FundEval
./scripts/stop.sh
git pull
mamba run -n finance python -m pip install -r requirements.txt
./scripts/start.sh
./scripts/status.sh
```

日志位于项目根目录 `~/FundEval/logs/`。首次更新时把旧日志移到新目录：

```bash
cd ~/FundEval
mkdir -p logs
chmod 700 logs
if [ -d cache/logs ]; then
  cp -a cache/logs/. logs/
  rm -rf cache/logs
fi
```

之后应用、Gunicorn 和交易导入日志都只写入 `~/FundEval/logs/`。手工归档：

```bash
cd ~/FundEval
./scripts/rotate_logs.sh
```

每日归档的 crontab：

```cron
10 0 * * * $HOME/FundEval/scripts/rotate_logs.sh >> $HOME/FundEval/logs/rotate.log 2>&1
```
