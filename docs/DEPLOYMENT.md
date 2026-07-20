# FundEval 服务器部署说明

## 1. 环境准备

要求 Linux、Python 3.10 以上，并建议使用独立虚拟环境：

```bash
cd /opt/FundEval
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

修改 `config.yaml`：

```yaml
server:
  host: "127.0.0.1"
  port: 8888
  secret_key: "替换为随机长字符串"
```

使用 Nginx 反向代理时建议监听 `127.0.0.1`；需要直接从其他机器访问时改为 `0.0.0.0`，并配置服务器防火墙。

## 2. 启停命令

```bash
./scripts/start.sh       # 启动
./scripts/stop.sh        # 停止
./scripts/restart.sh     # 重启
./scripts/status.sh      # 查看状态
./scripts/fundctl.sh logs # 跟踪 Gunicorn 错误日志
```

进程 PID 保存在项目本机运行目录 `.runtime/fundeval.pid`，不会写入 `cache` 数据子模块。脚本可以识别并停止同一项目目录下遗留的 `python run.py` 进程，但不会停止其他目录占用同一端口的服务。

常用环境变量：

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `PYTHON_BIN` | `.venv/bin/python` | 指定 Python 解释器 |
| `FUNDEVAL_BIND` | 读取 `config.yaml` | 临时覆盖监听地址 |
| `FUNDEVAL_THREADS` | `8` | Gunicorn 线程数 |
| `FUNDEVAL_TIMEOUT` | `120` | 请求超时秒数 |
| `FUNDEVAL_LOG_RETENTION_DAYS` | `14` | 日志归档保留天数 |

项目默认只启用一个 Gunicorn worker，避免后台任务和进程内状态被重复创建。

## 3. 日志

日志目录为 `cache/logs/`：

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
10 0 * * * /opt/FundEval/scripts/rotate_logs.sh >> /opt/FundEval/cache/logs/rotate.log 2>&1
```

## 4. Nginx 示例

```nginx
server {
    listen 80;
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
cd /opt/FundEval
./scripts/stop.sh
git pull
.venv/bin/pip install -r requirements.txt
./scripts/start.sh
./scripts/status.sh
```
