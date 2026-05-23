# ADR-003：用 Flask `g.lan_fund` 替代 `importlib.reload(fund)`

## 状态

已接受（2026-05-22）

## 背景

`fund_server.py` 中有 **27** 处 `importlib.reload(fund)`，随后构造 `LanFund`。意图是开发时热更新 `fund.py`，但：

- 增加每次请求开销与不可预测状态
- 后续重构 `fund_server` 时易误触 reload 语义
- 阶段 3 调整静态路径、阶段 5 改路由时风险叠加

## 决策

在 **阶段 4**（阶段 5 展示层分离之前）统一改为请求内单例。

**实现位置**：`src/web/lan_fund_session.py`（或 `src/utils/lan_fund_session.py`），由 `fund_server.py` / 后续 `routes/*` 导入。

```python
from flask import g, current_app
from src.fund import LanFund

def get_lan_fund(user_id: int) -> LanFund:
    if "lan_fund" not in g:
        db = current_app.extensions["db"]
        lan = LanFund(user_id=user_id, db=db)
        lan.load_cache()
        g.lan_fund = lan
    return g.lan_fund
```

**机械替换模式**（共 27 处）：

```python
# 前
importlib.reload(fund)
my_fund = fund.LanFund(user_id=user_id, db=db)

# 后
my_fund = get_lan_fund(user_id)
```

**规则**：

- 开发环境仅 Werkzeug `use_reloader` 重启进程（已 `exclude_patterns` 排除 `cache/`），**禁止** `importlib.reload(fund)`。
- **后台线程**（日志清理等）无 Flask 请求上下文：不得调用 `get_lan_fund`；若需 `LanFund` 则显式 `LanFund(db=db)` 或只传 `user_id` 调 service。
- 无 `user_id` 的少数路由（若存在）：保持显式构造，不塞进 `g`。
- 门禁：`rg "importlib.reload" fund_server.py` → **0**；可选 `tests/test_lan_fund_session.py` 断言同请求内 `id(g.lan_fund)` 不变。

## 后果

- 阶段 8 Service 迁移时无需再处理 reload。
- 修改 `fund.py` 后需重启进程（或 Werkzeug reloader）才能生效，与标准 Flask 开发体验一致。
