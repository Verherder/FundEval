# FundEval 重构后架构说明

## 一句话概览

请求从 **run.py** 进入，经 **Flask 应用工厂** 创建 app，由 **4 个 Blueprint** 分发路由，路由调用 **6 个 Service** 处理业务逻辑，Service 通过 **3 个渠道** 读写数据：4 个 Repository（本地数据库）、MiniFund（远程基金抓取）、market_data 工具函数（东方财富等源）。

---

## 入口层

```
用户请求
    │
    ▼
run.py  (30 行)
  └── from src.app import create_app
        ├── _setup_logging()       # loguru → stderr + cache/logs/
        ├── _setup_environment()   # .env, SSL ciphers
        ├── _ensure_directories()  # cache/ 目录
        ├── Database()             # SQLite 连接
        ├── init_dependencies(db)  # 初始化所有 repo/service（见依赖注入节）
        ├── register 4 blueprints  # 注册路由
        └── FilteredWSGIRequestLogger  # 静态资源不刷日志
```

项目只保留 `run.py` 一个应用入口：开发环境使用 `python run.py`，生产环境由 Gunicorn 加载 `run:app`。

---

## 路由层：4 个 Blueprint

| Blueprint | 文件 | URL 前缀 | 职责 | 路由数 |
|-----------|------|----------|------|--------|
| `auth_bp` | `blueprints/auth_bp.py` | 无 | 登录/注册/登出 | 3 |
| `pages_bp` | `blueprints/pages_bp.py` | 无 | SSR 页面渲染（portfolio、sectors 等） | 7 |
| `api_fund_bp` | `blueprints/api_fund_bp.py` | `/api` | 基金 CRUD、交易、图表、导入导出 | ~25 |
| `api_market_bp` | `blueprints/api_market_bp.py` | `/api` | 行情 tab、板块、指数净值同步、刷新配置 | ~6 |

**URL 前缀不冲突**：`auth_bp` 和 `pages_bp` 均无前缀但路由规则不重叠（`/login`、`/portfolio` 等互不相同），`api_fund_bp` 和 `api_market_bp` 共享 `/api` 前缀但端点路径也不重叠。

**路由文件的代码模式**：
```python
@api_fund_bp.route("/fund/list")
@login_required                    # 认证装饰器
def api_fund_list():
    user_id = get_current_user_id()
    data = get_fund_service().get_fund_list(user_id)   # 通过 getter 拿 service
    return jsonify({"success": True, "data": data})
```

---

## 依赖注入：`dependencies.py`

这是连接各层的**枢纽**。90 行，三件事：

### 1. 初始化（应用启动时执行一次）

```
create_app()
  └── db = Database()
  └── init_dependencies(db)
        ├── 4 个 Repo(db) 一次性创建
        └── 6 个 Service(repo..., get_lan_fund) 一次性创建，注入依赖
```

### 2. 访问器（请求时调用）

```python
get_db()              get_tx_service()
get_user_repo()       get_import_service()
get_fund_repo()        get_nav_service()
get_transaction_repo()  get_chart_service()
get_nav_repo()        get_fund_service()
                      get_market_service()
```

每个 Blueprint 在模块顶部 `from src.dependencies import get_xxx`，路由函数内调用 getter 获取单例。

### 3. MiniFund 工厂（请求级单例）

```python
def get_lan_fund(user_id=None):
    if not hasattr(g, "_lan_fund"):
        g._lan_fund = MiniFund(user_id=user_id, db=_db)
    return g._lan_fund
```

每个 HTTP 请求第一次调用 `get_lan_fund()` 时创建实例并缓存在 Flask `g` 上，同一请求内多次调用返回同一实例。请求结束后 `g` 自动销毁。

---

## 业务层：6 个 Service

每个 Service 封装一类业务逻辑，不碰 Flask request/response，只处理数据和领域对象。

| Service | 文件 | 依赖 | 主要职责 |
|---------|------|------|----------|
| **TransactionService** | `services/transaction_service.py` | FundRepo, TransactionRepo, NavRepo, get_lan_fund | 买入/卖出/分红补录、交易增删改查、持仓汇总 |
| **ImportService** | `services/import_service.py` | FundRepo, TransactionRepo, NavRepo, get_lan_fund, TransactionService | 批量导入交易（CSV/Excel 解析）、进度查询 |
| **NavService** | `services/nav_service.py` | DB, FundRepo, NavRepo, get_lan_fund | 净值同步（增量抓取、日期补全、指数净值落库） |
| **ChartService** | `services/chart_service.py` | DB, FundRepo, NavRepo, TransactionRepo, NavService, get_lan_fund | 业绩曲线、收益曲线、回撤计算、基准叠加 |
| **FundService** | `services/fund_service.py` | DB, FundRepo, TransactionRepo, get_lan_fund, ChartService | 基金增删改查、持仓管理、上传下载、份额/板块操作 |
| **MarketService** | `services/market_service.py` | get_lan_fund | 行情数据聚合（tab 数据、指数、板块、快讯、分时图） |

**调用关系图**：
```
Blueprint 路由
    │
    ├── get_fund_service() ──────→ FundService ──→ FundRepo, TransactionRepo, ChartService
    ├── get_tx_service() ────────→ TransactionService ──→ FundRepo, TransactionRepo, NavRepo
    ├── get_import_service() ────→ ImportService ──→ TransactionService
    ├── get_nav_service() ───────→ NavService ──→ FundRepo, NavRepo
    ├── get_chart_service() ─────→ ChartService ──→ NavService
    └── get_market_service() ────→ MarketService ──→ market_data 工具函数
```

所有 Service 都持有 `get_lan_fund` 回调，用于需要远程抓取时获取 MiniFund 实例。

---

## 数据层

### 4 个 Repository（本地 SQLite）

| Repository | 文件 | 操作的数据库表 |
|------------|------|---------------|
| `UserRepo` | `repositories/user_repo.py` | `users` |
| `FundRepo` | `repositories/fund_repo.py` | `user_funds` |
| `TransactionRepo` | `repositories/transaction_repo.py` | `transactions` |
| `NavRepo` | `repositories/nav_repo.py` | `fund_nav_history` |

每个 Repo 构造时接收 `Database` 实例，方法返回 dict/list，不暴露 SQL 到上层。

### MiniFund（远程数据抓取）

`src/fund.py` 中的 `MiniFund` 类承担**远程行情数据抓取**的职责：
- 使用 `requests.Session` 抓取基金数据（fund123、fundgz 等）
- 通过统一的超时和重试封装处理上游连接抖动
- 管理 `CACHE_MAP` 缓存、板块分类等

Blueprints 和 Services **不直接 import MiniFund**，而是通过 `get_lan_fund(user_id)` 获取请求级实例。

### market_data 工具函数

`src/market_data.py` 提供无状态的行情抓取函数：`fetch_bk()`、`fetch_kx()`、`fetch_A()` 等。MarketService 封装这些函数，从 MiniFund 获取 HTTP session 后传入。

### 其他支撑模块

| 模块 | 职责 |
|------|------|
| `src/auth.py` | `login_required` 装饰器、session 管理 |
| `src/fund_table.py` | 持仓表格构建逻辑（从 fund.py 抽离） |
| `src/tab_enhancers.py` | Tab 页面 HTML 片段增强（份额标注等） |
| `src/data/sectors.py` | 板块分类映射 `MAJOR_CATEGORIES` |
| `src/data/bk_map.py` | 东方财富板块代码映射 |
| `src/utils/financial.py` | XIRR/年化收益率等金融计算 |
| `src/utils/cache.py` | 函数级磁盘缓存装饰器 |
| `src/trading_calendar.py` | A 股交易日历 |
| `src/yaml_config.py` | YAML 配置文件读取 |
| `src/database.py` | 数据库初始化、迁移、Schema 管理 |
| `src/ai_analyzer.py` | LangChain AI 分析 |

---

## 请求完整流转示例

以「查看持仓页面」为例：

```
浏览器 GET /portfolio
    │
    ▼
pages_bp.portfolio_page()                   # blueprints/pages_bp.py
  ├── @login_required → 检查 session
  ├── user_id = get_current_user_id()
  └── render_template("pages/portfolio.html", user_id=user_id)

浏览器加载页面后 AJAX GET /api/tab/fund
    │
    ▼
api_market_bp.api_get_tab_data("fund")      # blueprints/api_market_bp.py
  ├── user_id = get_current_user_id()
  ├── market_service = get_market_service()
  ├── market_service.build_fund_table(user_id)
  │     └── MiniFund.build_fund_table()      # 抓取天天基金数据
  ├── fund_map = get_fund_repo().get_user_funds(user_id)
  └── enhance_fund_tab_content(content, shares_map)

同时 AJAX GET /api/portfolio/fund-table
    │
    ▼
api_fund_bp.api_portfolio_fund_table()      # blueprints/api_fund_bp.py
  ├── fund_service = get_fund_service()
  └── fund_service.get_portfolio_fund_table(user_id)
        ├── FundRepo.get_user_funds()
        ├── TransactionRepo.get_transactions()
        ├── TransactionService.calculate_position_summary()
        └── ChartService.get_profit_chart_data()
              └── NavRepo.get_nav_history()
```

---

## 关键设计决策

### 为什么用模块级单例而不是 Flask `app.extensions`？

模块级变量在 Python 中是天然的单例。`create_app()` 在模块导入时执行一次（Werkzeug reloader 会重载模块），不需要 `app.extensions` 字典的 key 管理。所有 Blueprint 直接 `from src.dependencies import get_xxx` 即可，无需 `current_app` 代理。

### 为什么 MiniFund 是请求级单例而不是全局单例？

MiniFund 持有 `user_id` 和 HTTP session，不同用户的请求需要不同的实例。Flask `g` 在请求结束时自动销毁，天然适合此场景。

### 应用入口

`run.py` 是唯一入口，并通过 `src.app.create_app()` 创建应用。旧的 `fund_server.py` 兼容入口已经删除，避免开发和部署使用不同入口。

### Blueprint 内的 `user_id` 传递方式

每个路由函数自己调用 `get_current_user_id()` 获取当前用户，然后显式传给 Service 方法。这样 Service 不依赖 Flask context，可单独测试。
