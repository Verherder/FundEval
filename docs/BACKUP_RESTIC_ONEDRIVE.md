# FundEval Restic + OneDrive 备份操作手册

本文按实际操作顺序组织：检查状态、准备工具、配置工具、检查数据库、调整环境、手工备份、
验证恢复、按需修正、启用定时任务，最后才解除旧 `cache` Git 仓库。

## 1. 目标和约定

服务器约定：

```text
项目目录       ~/FundEval
运行数据库     ~/FundEval/cache/fund_data.db
一致性暂存库   ~/FundEval/cache/backup-staging/fund_data.db
备份日志       ~/FundEval/logs/restic_backup.log
Restic仓库     rclone:onedrive:FundEval/restic
```

数据流：

```text
运行中的SQLite
    -> SQLite Online Backup API生成一致性暂存库
    -> Restic加密、分块、去重
    -> Rclone通过Microsoft API写入OneDrive
```

服务备份期间可以继续运行。禁止直接备份正在写入的 `fund_data.db`，也禁止把 OneDrive
挂载成运行数据库目录。Restic 密码丢失后无法恢复，必须另存到服务器以外的密码管理器。

## 2. 检查当前状态

登录服务器后执行：

```bash
cd ~/FundEval
pwd
./scripts/status.sh
test -f cache/fund_data.db && echo "数据库存在"
ls -lh cache/fund_data.db
git status --short
git check-ignore -v cache/fund_data.db
```

检查 `cache` 是否仍被识别为旧数据仓库：

```bash
test -d cache/.git && echo "仍存在旧 cache Git 仓库"
git submodule status
```

此时不要删除 `cache/.git`。必须先完成第 7 节恢复验证。

检查已有工具和配置：

```bash
command -v restic || true
command -v rclone || true
restic version 2>/dev/null || true
rclone version 2>/dev/null || true
test -f ~/.config/rclone/rclone.conf && echo "Rclone配置存在"
test -f ~/.config/fundeval/restic.env && echo "Restic配置存在"
test -f ~/.config/fundeval/restic-password && echo "Restic密码存在"
```

已经完成过首次备份时，再检查现有仓库：

```bash
set -a
. ~/.config/fundeval/restic.env
set +a
restic snapshots --host fundeval-prod --tag fundeval
```

能看到快照表示仓库已经初始化。不要再次执行 `restic init`，继续第 4 节。

## 3. 准备和配置工具

本节只补充第 2 节确认缺少的内容。已有工具、Rclone remote、Restic 密码或仓库不要重建。

### 3.1 安装工具

Ubuntu/Debian：

```bash
sudo apt-get update
sudo apt-get install -y restic rclone util-linux
restic version
rclone version
command -v flock
```

### 3.2 配置 Rclone OneDrive

已有名为 `onedrive` 的 remote 时只验证：

```bash
rclone listremotes
rclone lsd onedrive:
```

没有时执行：

```bash
rclone config
```

依次选择：

1. `n`：新建 remote。
2. 名称：`onedrive`。
3. 类型：Microsoft OneDrive。
4. `client_id`、`client_secret` 留空。
5. 选择实际账户类型。
6. 无浏览器服务器选择不自动打开浏览器。

在有浏览器且 Rclone 版本相近的电脑执行：

```bash
rclone authorize "onedrive"
```

把输出的 Token JSON 完整粘贴回服务器。随后验证：

```bash
chmod 600 ~/.config/rclone/rclone.conf
rclone lsd onedrive:
rclone mkdir onedrive:FundEval/restic
```

不要执行 `rclone sync ~/FundEval/cache ...`、`rclone bisync` 或把 OneDrive mount 到
`cache/`，这些方式无法保证运行中 SQLite 的一致性，并可能同步误删除。

### 3.3 配置 Restic

首次配置时执行：

```bash
mkdir -p ~/.config/fundeval
chmod 700 ~/.config/fundeval
openssl rand -base64 48 > ~/.config/fundeval/restic-password
chmod 600 ~/.config/fundeval/restic-password
```

创建配置：

```bash
cat > ~/.config/fundeval/restic.env <<EOF
RESTIC_REPOSITORY=rclone:onedrive:FundEval/restic
RESTIC_PASSWORD_FILE=$HOME/.config/fundeval/restic-password
RCLONE_CONFIG=$HOME/.config/rclone/rclone.conf
EOF
chmod 600 ~/.config/fundeval/restic.env
```

立即把 `restic-password` 的内容保存到服务器之外的密码管理器。然后初始化一次：

```bash
set -a
. ~/.config/fundeval/restic.env
set +a
restic init
restic snapshots
```

`restic init` 只在新建空仓库时执行一次。已有仓库执行它会报仓库已经初始化，这是操作
路径错误，不需要重建仓库或密码。

## 4. 检查数据库状态

先只读检查，不停止服务：

```bash
cd ~/FundEval
mamba run -n finance python - <<'PY'
import sqlite3

path = "cache/fund_data.db"
with sqlite3.connect(path) as conn:
    tables = {
        row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    print("integrity_check:", conn.execute("PRAGMA integrity_check").fetchone()[0])
    print("foreign_key_check:", conn.execute("PRAGMA foreign_key_check").fetchall())
    print("schema_version:", conn.execute(
        "SELECT value FROM schema_meta WHERE key='schema_version'"
    ).fetchone()[0] if "schema_meta" in tables else "不存在")
    for table in ("users", "fund_catalog", "user_watchlist", "fund_transactions"):
        value = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] if table in tables else "不存在"
        print(f"{table}: {value}")
PY
```

当前程序的预期结果：

```text
integrity_check: ok
foreign_key_check: []
schema_version: 2
```

记录四张业务表的数量，恢复验证时必须对比。若完整性检查失败，停止写入并先排查，不要
将已知损坏的库作为新基线。若 schema 不是 2，按部署文档执行对应迁移；不要在备份脚本
中自动迁移数据库。

## 5. 调整目录和脚本

准备目录并限制权限：

```bash
cd ~/FundEval
mkdir -p cache/backup-staging logs .runtime
chmod 700 cache cache/backup-staging logs .runtime
chmod 600 cache/fund_data.db
```

确认项目中的脚本存在：

```bash
test -x scripts/restic_backup.sh
test -x scripts/restic_maintenance.sh
```

若刚从 Git 拉取后没有执行权限：

```bash
chmod 700 scripts/restic_backup.sh scripts/restic_maintenance.sh
```

`restic_backup.sh` 会：

1. 使用 `flock` 防止并发运行。
2. 用 SQLite Online Backup API 生成时间点一致的暂存库。
3. 对暂存库执行完整性和外键检查。
4. 备份暂存库以及项目 `.env`。
5. 上传成功或失败后都删除明文暂存库。

它不会停止 FundEval，也不会修改运行数据库。

## 6. 尝试备份一次

启动手工备份：

```bash
cd ~/FundEval
./scripts/restic_backup.sh
```

脚本正常时终端可能没有输出，因为详细输出写入日志。检查：

```bash
tail -n 100 ~/FundEval/logs/restic_backup.log
test ! -f ~/FundEval/cache/backup-staging/fund_data.db \
  && echo "暂存库已清理"
```

日志末尾必须出现 `backup complete`，并包含 Restic 新快照信息。

## 7. 验证备份结果

仅看到 OneDrive 中存在 `data/`、`index/` 和 `snapshots/` 目录不能证明业务数据库可恢复。
必须同时完成仓库检查和实际恢复。

### 7.1 检查仓库和远端

```bash
set -a
. ~/.config/fundeval/restic.env
set +a

restic snapshots --host fundeval-prod --tag fundeval
restic stats latest
restic check
rclone size onedrive:FundEval/restic
rclone lsf onedrive:FundEval/restic/snapshots
```

要求：

- 最新快照时间与刚才的手工备份一致。
- `stats latest` 的文件数和数据量非零。
- `restic check` 成功。
- Rclone 能看到远端 Restic 对象。

### 7.2 恢复到临时目录

恢复验证不会覆盖运行库：

```bash
rm -rf /tmp/fundeval-restore
mkdir -m 700 /tmp/fundeval-restore
restic restore latest \
  --host fundeval-prod \
  --tag fundeval \
  --target /tmp/fundeval-restore
find /tmp/fundeval-restore -name fund_data.db -type f
```

验证恢复数据库：

```bash
RESTORED_DB="$(find /tmp/fundeval-restore -name fund_data.db -type f | head -n 1)"
test -n "$RESTORED_DB"

mamba run -n finance python - "$RESTORED_DB" <<'PY'
import sqlite3
import sys

with sqlite3.connect(sys.argv[1]) as conn:
    print("integrity_check:", conn.execute("PRAGMA integrity_check").fetchone()[0])
    print("foreign_key_check:", conn.execute("PRAGMA foreign_key_check").fetchall())
    print("schema_version:", conn.execute(
        "SELECT value FROM schema_meta WHERE key='schema_version'"
    ).fetchone()[0])
    for table in ("users", "fund_catalog", "user_watchlist", "fund_transactions"):
        print(f"{table}:", conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
PY
```

恢复库必须满足：完整性为 `ok`、外键错误为空、schema 为 2，四张业务表数量与第 4 节
记录一致。验证完成后删除临时明文文件：

```bash
rm -rf /tmp/fundeval-restore
```

## 8. 按需调整和故障处理

| 现象 | 处理 |
| --- | --- |
| `restic: command not found` | 回到 3.1 安装工具 |
| 无法加载 `restic.env` | 检查文件路径、权限和内容 |
| `repository does not exist` | 仅确认是新仓库后执行一次 `restic init` |
| `wrong password or no key found` | 恢复原来的 Restic 密码，不要初始化新仓库 |
| Rclone Token 过期 | 运行 `rclone config reconnect onedrive:` |
| SQLite `database is locked` | 等待当前长事务结束后重试，不要直接复制数据库文件 |
| 完整性或外键检查失败 | 停止上线该快照，保留现场并排查运行库 |
| 最新快照时间未变化 | 查看 `logs/restic_backup.log` 和网络错误 |
| 暂存库未删除 | 确认没有备份进程后删除 `cache/backup-staging/fund_data.db*` |

调整后重新执行第 6、7 节，直到手工备份和恢复验证都成功，再配置定时器。

## 9. 设置定时器

使用部署用户的 systemd user timer，不使用 root 运行备份。

```bash
mkdir -p ~/.config/systemd/user
```

创建 `~/.config/systemd/user/fundeval-backup.service`：

```ini
[Unit]
Description=FundEval encrypted backup to OneDrive
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=%h/FundEval
ExecStart=%h/FundEval/scripts/restic_backup.sh
```

创建 `~/.config/systemd/user/fundeval-backup.timer`：

```ini
[Unit]
Description=Back up FundEval every six hours

[Timer]
OnCalendar=*-*-* 00,06,12,18:20:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
```

创建每周维护服务 `~/.config/systemd/user/fundeval-maintenance.service`：

```ini
[Unit]
Description=Check and prune FundEval Restic repository
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=%h/FundEval
ExecStart=%h/FundEval/scripts/restic_maintenance.sh
```

创建 `~/.config/systemd/user/fundeval-maintenance.timer`：

```ini
[Unit]
Description=Maintain FundEval Restic repository weekly

[Timer]
OnCalendar=Sun *-*-* 03:30:00
Persistent=true
RandomizedDelaySec=600

[Install]
WantedBy=timers.target
```

启用：

```bash
sudo loginctl enable-linger "$USER"
systemctl --user daemon-reload
systemctl --user enable --now fundeval-backup.timer
systemctl --user enable --now fundeval-maintenance.timer
systemctl --user list-timers 'fundeval-*'
```

立即通过 systemd 再测试一次：

```bash
systemctl --user start fundeval-backup.service
systemctl --user status fundeval-backup.service --no-pager
journalctl --user -u fundeval-backup.service -n 50 --no-pager
tail -n 100 ~/FundEval/logs/restic_backup.log
```

第二天检查定时任务确实产生了新快照，不要只看 timer 显示 `active`。

## 10. 解除旧 cache Git 仓库

只有第 7 节恢复验证成功后才执行。

主仓库已经通过 `.gitignore` 忽略 `cache/`，但旧子模块可能留下 `cache/.git`，导致 IDE
继续显示数据库修改。先重命名保留一段观察期：

```bash
cd ~/FundEval
test -d cache/.git
mv cache/.git cache/.git.retired-$(date +%Y%m%d)
git status --short
test -f cache/fund_data.db
./scripts/status.sh
```

重命名不会修改或删除数据库。连续观察自动备份和恢复至少 7 天后，再删除退休的 Git
元数据；不要删除 `cache/fund_data.db`：

```bash
find cache -maxdepth 1 -type d -name '.git.retired-*' -print
```

确认输出路径正确后再手工删除对应目录。旧私有 Git 数据仓库可以停止推送。

## 11. 生产恢复

先按第 7.2 节恢复并验证到临时目录。确认无误后才替换：

```bash
cd ~/FundEval
./scripts/stop.sh
cp -p cache/fund_data.db "cache/fund_data.before-restore-$(date +%Y%m%d%H%M%S).db"
install -m 600 "$RESTORED_DB" cache/fund_data.db
./scripts/start.sh
./scripts/status.sh
```

登录检查用户、自选、持仓、交易和收益曲线。确认正常后立即产生一份新备份。

新服务器恢复还需要：项目代码、`restic-password`、Rclone 授权配置和项目 `.env`。
`restic-password` 与 Rclone 配置不能只备份在同一个 Restic 仓库中，否则无法打开仓库。

## 12. 验收清单

- 运行数据库完整性为 `ok`，外键错误为空，schema 为 2。
- 手工备份日志以 `backup complete` 结束。
- Restic 最新快照时间正确且 `restic check` 成功。
- 已实际恢复数据库并核对四张业务表数量。
- 暂存目录没有遗留明文数据库。
- systemd 手工试跑成功，定时器能产生后续快照。
- Restic 密码已保存在服务器以外。
- 完成上述检查后才解除 `cache/.git`。

## 13. 参考资料

- [Restic 安装](https://restic.readthedocs.io/en/stable/020_installation.html)
- [Restic 使用 Rclone 后端](https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html)
- [Restic 恢复](https://restic.readthedocs.io/en/stable/050_restore.html)
- [Rclone 安装](https://rclone.org/install/)
- [Rclone 无浏览器授权](https://rclone.org/remote_setup/)
- [Rclone OneDrive](https://rclone.org/onedrive/)
- [SQLite Online Backup API](https://www.sqlite.org/backup.html)
