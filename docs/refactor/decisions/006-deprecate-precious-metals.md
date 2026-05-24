# ADR-006：废弃贵金属页面（gold/real_time_gold）

## 状态

已接受（2026-05-22）

## 背景

贵金属行情 Tab（gold/real_time_gold）功能：
- 在 `fund.py` 中有 `gold_html`、`real_time_gold_html` 等方法
- 在 `module_html.py` 中有对应的 `get_gold_html`、`get_real_time_gold_html` 等方法
- 路由 `/api/tab/gold` 提供黄金实时数据

该功能**与基金评估核心业务无关**，属于辅助行情功能。

## 决策

**阶段 5 展示层分离时**，贵金属 Tab/页面**不迁移到 Jinja 模板**，直接删除相关实现：

| 待删除 | 位置 |
|--------|------|
| `gold_html`、`real_time_gold_html` | `src/fund.py` |
| `get_gold_html`、`get_real_time_gold_html` | `src/module_html.py` |
| `/api/tab/gold` 路由 | `fund_server.py` |
| `decisions/003-flask-g-lanfund-singleton.md` 规则：后台线程不调 `get_lan_fund` | 维持 |

**阶段 8 Service 化时**，贵金属**不建 `precious_metals_service`**，相关路由直接返回 404 或空数据。

## 后果

- `fund.py` 减少约 300 行贵金属相关代码
- `module_html.py` 减少约 200 行
- 路由减少 1–2 个
- 用户无法访问黄金行情 Tab（若需保留，应在阶段 5 后作为独立静态页面或单独服务）