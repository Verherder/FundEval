# FundEval Restic + OneDrive 从零部署手册

## 1. 最终目录和数据流

本手册假设：

- 服务器项目目录是 `~/FundEval`。
- 当前登录用户就是 FundEval 的部署和运行用户。
- 数据库、日志和备份暂存文件都放在 `~/FundEval/cache`。
- 服务器尚未安装 Restic、Rclone 或 OneDrive 客户端。
- `cache/` 整体位于项目 `.gitignore`，不再是 Git 子模块。

最终目录：

```text
~/FundEval/
├── cache/                         # 整体不进入 Git
│   ├── fund_data.db               # SQLite 明文运行库
│   ├── logs/                      # 应用、Gunicorn和备份日志
│   └── backup-staging/            # 备份时短暂存在的一致性快照
├── scripts/
├── src/
└── .env

~/.config/rclone/rclone.conf       # OneDrive OAuth凭据
~/.config/fundeval/restic.env      # Restic仓库配置
~/.config/fundeval/restic-password # Restic解密密码
```

数据流：

```text
~/FundEval/cache/fund_data.db
       │ SQLite Online Backup API
       ▼
~/FundEval/cache/backup-staging/fund_data.db
       │ Restic分块、去重、加密和校验
       ▼
Rclone通过Microsoft API上传
       ▼
OneDrive/FundEval/restic
```

OneDrive不是运行盘。服务器不安装桌面OneDrive客户端，也不挂载OneDrive目录。日常是服务器向OneDrive备份；灾难恢复时才从OneDrive读取。

默认目标：

| 项目 | 默认值 |
| --- | --- |
| 备份频率 | 每6小时 |
| RPO | 最多6小时 |
| 日版本 | 14个 |
| 周版本 | 8个 |
| 月版本 | 12个 |
| 完整性检查 | 每周一次 |
| 恢复演练 | 每月一次 |

## 2. 从旧cache子模块安全切换

主仓库维护端已经完成 `cache` 子模块解除和 `.gitignore` 配置。服务器拉取包含该改动的版本前，
必须先在项目目录外保存数据库副本：

```bash
cd ~/FundEval
test -f cache/fund_data.db && echo "数据库存在"
git submodule status
cp -p cache/fund_data.db "$HOME/fund_data.db.before-cache-conversion"
chmod 600 "$HOME/fund_data.db.before-cache-conversion"
```

然后更新项目：

```bash
git pull
```

如果Git因旧子模块状态拒绝更新，不要使用 `git reset --hard`。确认外部数据库副本存在后，执行：

```bash
git submodule deinit -f cache
git pull
mkdir -p cache/logs cache/backup-staging
cp -p "$HOME/fund_data.db.before-cache-conversion" cache/fund_data.db
```

更新后检查：

```bash
test -f ~/FundEval/cache/fund_data.db
git submodule status
git check-ignore -v cache/fund_data.db
git status --short
```

预期是 `git submodule status` 不再列出cache，`git check-ignore`显示由项目 `.gitignore`忽略，
并且Git不再列出cache内部文件变化。本地 `cache/fund_data.db`必须仍然存在。

旧私有数据仓库的历史清理必须等OneDrive恢复演练成功后再做。

## 3. 安装Restic和Rclone

先识别Linux发行版：

```bash
cat /etc/os-release
```

### Ubuntu

```bash
sudo apt-get update
sudo apt-get install -y restic rclone
```

如果发行版没有Rclone或版本过旧，可以使用Rclone官方安装脚本：

```bash
sudo -v
curl https://rclone.org/install.sh | sudo bash
```

安装完成必须确认：

```bash
restic version
rclone version
command -v restic
command -v rclone
```

## 4. 准备项目和cache目录

```bash
cd ~/FundEval
mkdir -p cache/logs cache/backup-staging
chmod 700 cache cache/logs cache/backup-staging
test -f cache/fund_data.db
```

项目默认直接使用：

```text
~/FundEval/cache/fund_data.db
~/FundEval/cache/logs/
```

`.env` 不需要配置 `FUNDEVAL_DATA_DIR` 或 `FUNDEVAL_LOG_DIR`。如果以前设置过其他路径，应删除这两个变量，避免应用和备份读取不同数据库。

检查实际Python环境和服务状态：

```bash
./scripts/fundctl.sh environment
./scripts/status.sh
```

若数据库仍是旧schema，先按部署文档执行：

```bash
./scripts/stop.sh
./scripts/fundctl.sh migrate --dry-run
./scripts/fundctl.sh migrate
./scripts/fundctl.sh reset-password jiaming
./scripts/start.sh
```

## 5. 在无浏览器服务器授权OneDrive

服务器执行：

```bash
rclone config
```

配置选择：

1. 选择 `n` 新建remote。
2. 名称输入 `onedrive`。
3. 存储类型选择 `Microsoft OneDrive`。
4. `client_id`和`client_secret`通常留空。
5. 账户类型选择Personal or Business
6. 询问是否使用浏览器自动认证时选择 `n`。

服务器会提示在有浏览器的电脑上执行：

```bash
rclone authorize "onedrive"
```

在电脑浏览器登录目标Microsoft账号，将输出的Token JSON完整粘贴回服务器。官方建议两台机器使用相同Rclone版本。

完成后检查配置位置和权限：

```bash
rclone config file
chmod 600 ~/.config/rclone/rclone.conf
```

验证连接：

```bash
rclone lsd onedrive:
rclone mkdir onedrive:FundEval/restic
rclone lsd onedrive:FundEval
```

禁止执行：

```text
rclone mount onedrive: .../cache
rclone bisync .../cache onedrive:...
rclone sync ~/FundEval/cache onedrive:...
```

这些命令可能把运行中的SQLite文件、不完整状态或误删除同步到云端。

## 6. 初始化Restic仓库

创建配置目录：

```bash
mkdir -p ~/.config/fundeval
chmod 700 ~/.config/fundeval
```

生成Restic密码：

```bash
openssl rand -base64 48 > ~/.config/fundeval/restic-password
chmod 600 ~/.config/fundeval/restic-password
```

创建 `~/.config/fundeval/restic.env`：

```bash
cat > ~/.config/fundeval/restic.env <<EOF
RESTIC_REPOSITORY=rclone:onedrive:FundEval/restic
RESTIC_PASSWORD_FILE=$HOME/.config/fundeval/restic-password
RCLONE_CONFIG=$HOME/.config/rclone/rclone.conf
EOF
chmod 600 ~/.config/fundeval/restic.env
```

将Restic密码另存到密码管理器。密码丢失后，OneDrive中的备份无法恢复。

加载配置并初始化：

```bash
set -a
. ~/.config/fundeval/restic.env
set +a
restic init
```

`restic init`只执行一次。验证：

```bash
restic snapshots
```

## 7. 首次手工备份

### 7.1 生成SQLite一致性快照

日常备份不需要停止FundEval服务。这里“不要复制运行中的SQLite文件”是指不能直接对
`cache/fund_data.db`执行 `cp`、`rclone copy`或 `restic backup`，不是要求备份期间禁止数据库写入。

SQLite Online Backup API通过数据库连接生成事务一致的时间点快照：

- 页面刷新、行情写入和交易操作可以继续执行。
- Backup API只在分批读取页面时短暂持有读锁，不会在Restic上传期间锁住运行库。
- 备份过程中发生的新写入可能属于本次快照，也可能进入下一次快照，但不会产生“只写入一半”的数据库。
- 在WAL模式下，Backup API会正确处理主数据库和WAL中的已提交事务；直接复制单个主数据库文件做不到这一点。
- Restic上传的是生成完成后不再变化的暂存快照，上传速度不会影响生产数据库一致性。

流程是：

```text
运行服务继续读写 cache/fund_data.db
              │
              │ SQLite Online Backup API
              ▼
生成一个一致时间点的 backup-staging/fund_data.db
              │
              │ Restic上传，运行库继续工作
              ▼
上传成功后删除暂存快照
```

只有替换生产数据库、执行破坏性schema迁移，或者Online Backup API持续失败需要离线排查时，
才需要停止服务。

使用finance环境的Python调用SQLite Backup API：

```bash
cd ~/FundEval
mamba run -n finance python - \
  "$HOME/FundEval/cache/fund_data.db" \
  "$HOME/FundEval/cache/backup-staging/fund_data.db" <<'PY'
import os
import sqlite3
import sys

source, target = sys.argv[1:3]
temp = target + ".tmp"
for path in (temp, target):
    if os.path.exists(path):
        os.unlink(path)
with sqlite3.connect(source) as src, sqlite3.connect(temp) as dst:
    src.backup(dst)
    result = dst.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise SystemExit(f"SQLite integrity_check failed: {result}")
os.chmod(temp, 0o600)
os.replace(temp, target)
PY
```

确认：

```bash
ls -lh cache/backup-staging/fund_data.db
```

### 7.2 上传到OneDrive

```bash
set -a
. ~/.config/fundeval/restic.env
set +a

restic backup "$HOME/FundEval/cache/backup-staging/fund_data.db" \
  --host fundeval-prod \
  --tag fundeval
```

查看快照并检查仓库：

```bash
restic snapshots --host fundeval-prod --tag fundeval
restic check
```

`restic snapshots`能看到新快照才代表业务数据已经提交到Restic仓库。只执行 `restic init`只会创建空仓库结构，不代表数据库已经备份。

成功后删除明文暂存快照：

```bash
rm -f ~/FundEval/cache/backup-staging/fund_data.db
```

运行库 `cache/fund_data.db`不能删除。

### 7.3 OneDrive中为什么看不到fund_data.db

Restic不会把原始文件名直接上传到OneDrive。它会加密、分块并使用内容哈希命名，因此OneDrive中的正常结构类似：

```text
FundEval/restic/
├── config
├── keys/
├── snapshots/
├── index/
├── data/
└── locks/
```

判断上传是否成功不能只在Finder中搜索 `fund_data.db`，应在服务器执行：

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

预期：

- `snapshots`至少有一条带 `fundeval`标签的记录。
- `stats latest`显示非零文件数和数据量。
- `check`成功。
- OneDrive远端存在 `snapshots`、`index`和 `data`对象。

macOS OneDrive启用Files On-Demand时，本地同步目录可能只有云端占位文件。此时 `du`显示的本地占用空间会远小于
`ls -l`显示的逻辑文件大小，这是正常现象，不表示云端对象为空。需要判断云端数据量时以服务器上的
`rclone size`和Restic命令为准。

## 8. 自动备份脚本要求

项目中的长期备份脚本应执行：

1. 通过 `flock` 防止并发备份。
2. 使用 `~/FundEval/cache/fund_data.db`作为源库。
3. 通过SQLite Backup API生成 `cache/backup-staging/fund_data.db`。
4. 执行 `PRAGMA integrity_check`。
5. 使用Restic上传并打上 `fundeval` 标签。
6. 无论成功或失败都删除明文暂存快照。
7. 日志写入 `cache/logs/restic_backup.log`，不得打印密码或Token。

计划脚本路径：

```text
~/FundEval/scripts/restic_backup.sh
~/FundEval/scripts/restic_maintenance.sh
```

在这些脚本实际加入项目并完成一次手工验证前，不要配置定时器。

## 9. 用户级systemd定时器

脚本实现后创建目录：

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
Description=Run FundEval backup every six hours

[Timer]
OnCalendar=*-*-* 00,06,12,18:20:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
```

让退出SSH后用户定时器继续运行：

```bash
sudo loginctl enable-linger "$USER"
systemctl --user daemon-reload
systemctl --user enable --now fundeval-backup.timer
systemctl --user list-timers fundeval-backup.timer
```

立即试运行：

```bash
systemctl --user start fundeval-backup.service
journalctl --user -u fundeval-backup.service -n 100 --no-pager
tail -n 100 ~/FundEval/cache/logs/restic_backup.log
```

## 10. 保留策略和完整性检查

加载配置：

```bash
set -a
. ~/.config/fundeval/restic.env
set +a
```

首次只预览：

```bash
restic forget \
  --host fundeval-prod \
  --tag fundeval \
  --keep-daily 14 \
  --keep-weekly 8 \
  --keep-monthly 12 \
  --dry-run
```

确认无误后去掉 `--dry-run`并增加 `--prune`。`prune`网络读写较多，建议每周执行一次，而不是每6小时执行。

每周至少执行：

```bash
restic check
```

定期执行更完整但耗时更长的检查：

```bash
restic check --read-data
```

## 11. 恢复演练

### 11.1 恢复到临时目录

```bash
set -a
. ~/.config/fundeval/restic.env
set +a

rm -rf /tmp/fundeval-restore
mkdir -m 700 /tmp/fundeval-restore

restic restore latest \
  --host fundeval-prod \
  --path "$HOME/FundEval/cache/backup-staging/fund_data.db" \
  --target /tmp/fundeval-restore
```

恢复后的路径包含原始绝对路径。查找文件：

```bash
find /tmp/fundeval-restore -name fund_data.db -type f
```

设定恢复文件路径并验证：

```bash
RESTORED_DB="$(find /tmp/fundeval-restore -name fund_data.db -type f | head -n 1)"

mamba run -n finance python - "$RESTORED_DB" <<'PY'
import sqlite3
import sys

with sqlite3.connect(sys.argv[1]) as conn:
    tables = {
        row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    print("integrity_check:", conn.execute("PRAGMA integrity_check").fetchone()[0])
    print("foreign_key_check:", conn.execute("PRAGMA foreign_key_check").fetchall())
    print("users:", conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])
    if "schema_meta" not in tables:
        raise SystemExit("恢复的是未迁移旧数据库：缺少 schema_meta")
    print("schema_version:", conn.execute(
        "SELECT value FROM schema_meta WHERE key='schema_version'"
    ).fetchone())
    print("funds:", conn.execute("SELECT COUNT(*) FROM fund_catalog").fetchone()[0])
    print("transactions:", conn.execute("SELECT COUNT(*) FROM fund_transactions").fetchone()[0])
PY
```

`integrity_check`必须是 `ok`，`foreign_key_check`必须是空列表，
`schema_version`必须与当前程序版本一致，其他数量应符合预期。结构完整性检查只能
证明备份文件未损坏；表版本和业务数量检查用于确认备份源确实是当前生产数据库。

### 11.2 替换生产数据库

只有恢复演练验证通过后才能替换：

```bash
cd ~/FundEval
./scripts/stop.sh

cp -p cache/fund_data.db cache/fund_data.db.before-restore
install -m 600 "$RESTORED_DB" cache/fund_data.db

./scripts/start.sh
./scripts/status.sh
```

检查登录、自选基金、交易数量、持仓和个人收益曲线。确认正常后再删除：

```bash
rm -f ~/FundEval/cache/fund_data.db.before-restore
rm -rf /tmp/fundeval-restore
```

## 12. 新服务器从零恢复

新服务器只需：

1. 将项目部署到 `~/FundEval`。
2. 安装finance环境、项目依赖、Restic和Rclone。
3. 重新授权同一个OneDrive账号，或安全复制 `rclone.conf`。
4. 恢复 `restic-password`和 `restic.env`。
5. 按第11节恢复数据库。
6. 将恢复库安装到 `~/FundEval/cache/fund_data.db`。
7. 配置项目 `.env`并启动服务。

服务器不需要安装OneDrive客户端。

## 13. 停止使用Git数据仓库

首次OneDrive备份和恢复演练成功后：

1. 确认主仓库已经忽略整个 `cache/`。
2. 确认新提交不再包含cache子模块指针。
3. 停止向旧FundEval-data仓库推送数据库。
4. 连续观察至少7天自动备份结果。
5. 再处理旧私有仓库中的明文数据库历史和访问凭据。

不要在同一任务中同时写Git数据仓库和Restic仓库。

## 14. 验收清单

- `~/FundEval/cache/fund_data.db`存在且应用正常读取。
- `git status`不显示 `cache`内部文件变化。
- `rclone lsd onedrive:`成功。
- `restic snapshots`能看到至少两个不同时间的快照。
- `restic check`成功。
- 恢复库的 `PRAGMA integrity_check`返回 `ok`。
- 恢复库用户、基金和交易数量符合预期。
- 自动任务退出后 `cache/backup-staging`不残留明文快照。
- Restic密码和Rclone配置已在服务器以外安全保存。

## 15. 官方资料

- [Restic安装](https://restic.readthedocs.io/en/stable/020_installation.html)
- [Restic通过Rclone使用其他存储](https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html)
- [Restic恢复](https://restic.readthedocs.io/en/stable/050_restore.html)
- [Rclone安装](https://rclone.org/install/)
- [Rclone无浏览器服务器授权](https://rclone.org/remote_setup/)
- [Rclone Microsoft OneDrive](https://rclone.org/onedrive/)
- [SQLite Online Backup API](https://www.sqlite.org/backup.html)
