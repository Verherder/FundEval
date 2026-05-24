# 阶段 10：Blueprint 与应用工厂 - 完成记录

## 执行信息

- 日期：2026-05-23
- PR：待提交

## 交付物

- [x] `src/app.py` — `create_app()` 应用工厂（日志、DB 初始化、Blueprint 注册、中间件）
- [x] `run.py` — 瘦入口点（30 行），`python run.py` 启动
- [x] `fund_server.py` — 新增 `REFACTOR_USE_BLUEPRINTS` feature flag 支持切换
- [x] 4 个 Blueprint：`auth_bp`、`pages_bp`、`api_fund_bp`、`api_market_bp`
- [x] `src/dependencies.py` — 11 个 getter 函数（repos + services + lan_fund）
- [x] `FilteredWSGIRequestLogger` 中间件从 `fund_server.py` 迁移到 `src/app.py`

## 架构

```
run.py  →  create_app()
              ├── _setup_logging()
              ├── _setup_environment()
              ├── Database() → init_dependencies(db)
              ├── register auth_bp    (/, /register, /logout)
              ├── register pages_bp   (/, /fund, /market, /portfolio, /sectors, /fund/sector)
              ├── register api_fund_bp (/api/*, ~25 routes)
              ├── register api_market_bp (/api/*, tabs, timing, news, indices, sectors)
              └── FilteredWSGIRequestLogger
```

## 冒烟测试

- P0：`fund_server.py` 向后兼容，原有路由全部保留
- P1：`python run.py` 启动成功，50 条路由全部注册

## 门禁验证

```bash
# 两种启动方式路由数一致（均为 50 条）
python run.py         # 新入口
python fund_server.py # 旧入口（向后兼容）

# feature flag 切换
REFACTOR_USE_BLUEPRINTS=true python fund_server.py
```
