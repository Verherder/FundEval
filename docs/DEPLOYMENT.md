# FundEval 服务器部署说明

## 1. 环境准备

要求 Linux、Python 3.10 以上。使用 mamba 时创建默认的 `finance` 环境：

```bash
cd ~/FundEval
mamba create -n finance python=3.12
mamba run -n finance python -m pip install -r requirements.txt
```

启停脚本会自动定位 `finance` 环境的 Python，不需要先执行 `mamba activate finance`。如果使用其他环境名，设置 `FUNDEVAL_ENV_NAME`；项目 `.venv` 仍作为后备方案。

复制 `.env.example` 为 `.env`，设置权限为 `0600`，至少替换以下密钥：

```bash
FUNDEVAL_SECRET_KEY="$(openssl rand -hex 32)"
FUNDEVAL_SECURE_COOKIE=1
```

生产模式缺少 `FUNDEVAL_SECRET_KEY` 时服务会拒绝启动。数据库和日志默认位于
`~/FundEval/cache`，不需要另外设置数据目录。密钥不得提交到Git。

使用 Nginx 反向代理时建议监听 `127.0.0.1`；需要直接从其他机器访问时改为 `0.0.0.0`，并配置服务器防火墙。

## 2. 启停命令

```bash
./scripts/start.sh       # 启动
./scripts/stop.sh        # 停止
./scripts/restart.sh     # 重启
./scripts/status.sh      # 查看状态
./scripts/fundctl.sh environment # 查看实际使用的 Python 环境
./scripts/fundctl.sh logs # 跟踪 Gunicorn 错误日志
```

进程PID保存在项目本机运行目录 `.runtime/fundeval.pid`；数据库和日志保存在已被Git忽略的
`cache/`目录。脚本可以识别并停止同一项目目录下遗留的 `python run.py`进程，但不会停止其他目录占用同一端口的服务。

常用环境变量：

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `PYTHON_BIN` | 自动查找 | 显式指定 Python 解释器，优先级最高 |
| `FUNDEVAL_ENV_NAME` | `finance` | 指定 mamba/conda 环境名 |
| `MAMBA_EXE` | 自动查找 | mamba/micromamba 可执行文件路径 |
| `FUNDEVAL_BIND` | 读取 `config.yaml` | 临时覆盖监听地址 |
| `FUNDEVAL_THREADS` | `8` | Gunicorn 线程数 |
| `FUNDEVAL_TIMEOUT` | `120` | 请求超时秒数 |
| `FUNDEVAL_LOG_RETENTION_DAYS` | `14` | 日志归档保留天数 |
| `FUNDEVAL_DATA_DIR` | `~/FundEval/cache` | 明文SQLite数据目录，一般无需覆盖 |
| `FUNDEVAL_LOG_DIR` | `~/FundEval/cache/logs` | 运行日志目录，一般无需覆盖 |
| `FUNDEVAL_SECRET_KEY` | 无 | 生产环境 Session 密钥 |
| `FUNDEVAL_SECURE_COOKIE` | `0` | HTTPS 部署时必须设为 `1` |

项目默认只启用一个 Gunicorn worker，避免后台任务和进程内状态被重复创建。

## 3. 日志

日志目录默认为 `~/FundEval/cache/logs/`：

| 文件 | 内容 |
| --- | --- |
| `fund_server.log` | 应用业务日志 |
| `gunicorn_access.log` | HTTP 访问日志 |
| `gunicorn_error.log` | Gunicorn 启动与错误日志 |
| `transaction_import.log` | 交易导入明细 |

应用日志每天自动 gzip 归档。其他日志执行：

```bash
./scripts/rotate_logs.sh
```

建议配置部署用户的 crontab：

```cron
10 0 * * * $HOME/FundEval/scripts/rotate_logs.sh >> $HOME/FundEval/cache/logs/rotate.log 2>&1
```

## 4. Nginx 示例

```nginx
server {
    listen 443 ssl;
    server_name fund.example.com;

    location / {
        proxy_pass http://127.0.0.1:8888;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 180s;
    }
}
```

建议同时启用 HSTS，并将 HTTP 重定向到 HTTPS；应用仅监听 `127.0.0.1:8888`。

部署在 `/fundeval` 子路径时，必须传递 `X-Forwarded-Prefix`：

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

`proxy_pass` 末尾的 `/` 和 `X-Forwarded-Prefix` 都不能省略：前者让 Nginx 转发时移除路径前缀，后者让 Flask 生成带 `/fundeval` 的跳转、静态资源和页面链接。

## 5. 更新发布

```bash
cd ~/FundEval
./scripts/stop.sh
git pull
mamba run -n finance python -m pip install -r requirements.txt
./scripts/start.sh
./scripts/status.sh
```

## 6. 首次多用户迁移

共享基金池、个人数据边界、权限和迁移后的数据处理详见 [多用户数据隔离说明](DATA_ISOLATION.md)。

必须在停止服务后执行。`dry-run` 不会修改数据库：

```bash
./scripts/stop.sh
./scripts/fundctl.sh migrate --dry-run
./scripts/fundctl.sh migrate
./scripts/fundctl.sh reset-password jiaming
./scripts/start.sh
```

迁移工具原地升级 `cache/fund_data.db`，保留 `jiaming`的自选、交易和持仓，
清空其他账号的个人数据并添加三只示例基金。迁移前会在 `cache/`生成权限为 `0600`的一致性备份。

新账号只能使用管理员生成的单次邀请码注册：

```bash
./scripts/fundctl.sh invite --days 7
```

## 7. OneDrive长期备份

数据库不再通过Git或Git子模块备份。`cache/`整体加入主仓库 `.gitignore`，运行数据库继续位于
`~/FundEval/cache/fund_data.db`。

服务器从未安装工具开始配置Restic、Rclone和OneDrive，以及自动备份、保留策略和灾难恢复的完整步骤见：

[Restic + OneDrive从零部署手册](BACKUP_RESTIC_ONEDRIVE.md)
