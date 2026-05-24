# ADR-004：展示层与业务逻辑分离

## 状态

已接受（2026-05-22）

## 背景

当前 HTML 来源混杂：

- `module_html.py`：整页 f-string（`get_portfolio_page_html` 等）
- `fund.py`：`fund_html()`、`kx_html()` 等返回 HTML 字符串
- `/api/tab/<id>`：将 HTML 片段作为 JSON 的 `content` 字段返回

导致无法单独改页面、难以测试业务逻辑。

## 决策

采用四层边界：

| 层 | 目录 | 职责 |
|----|------|------|
| 路由 | `src/routes/` | HTTP、鉴权、调用下层 |
| 业务 | `src/services/` | 计算与持久化，返回 `dict` / `list` |
| 展示 | `src/presenters/` | 仅 `render_template` |
| 视图 | `src/templates/` | HTML/CSS 结构 |

**硬规则**：

- `services/` 禁止出现 HTML 标签与 `render_template`
- `presenters/` 禁止访问数据库与外部行情 API
- **阶段 5.4** 完成后删除 `module_html.py`

## 迁移顺序（阶段 5）

1. `/portfolio`、`/sectors` 整页模板化（5.2）
2. `fund_html` 及全部 `*_html` → `templates/`（5.3）
3. `/api/tab/*` → `presenters.tabs`（5.3）
4. 删除 `module_html.py`（5.4）

## 后果

- 前端改版主要改 `templates/` 与 `static/`
- **阶段 5** 先于 **阶段 8**（fund_server Service）完成 HTML 迁出；阶段 8 的 service **只返回 dict**，不拼接 HTML
