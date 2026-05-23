# ADR-002：删除未使用的 Dashboard 与旧整页 HTML

## 状态

已接受（2026-05-22）

## 背景

审计发现以下资产 **无生产路径引用**：

| 资产 | 说明 |
|------|------|
| [`templates/dashboard.html`](../../templates/dashboard.html) | 全仓库无 `render_template('dashboard.html')` |
| `get_full_page_html` / `get_full_page_html_sidebar` | 仅 `module_html.py` 内部互调 |
| `get_sse_loading_page`、旧 sidebar/卡片组件 | 同上 |

主 Web 入口已收敛为 `/portfolio`、`/sectors`；`/fund`、`/market` 等仅 `redirect('/portfolio')`。

## 决策

1. **阶段 1** 删除上述死代码与 `dashboard.html`（约 3200 行 `module_html` 减量）。
2. **不** 将 `get_full_page_html_sidebar` 迁为 Jinja（无调用方）。
3. 保留仍在用的：`get_portfolio_page_html`、`get_sectors_page_html`、`get_table_html`、`enhance_fund_tab_content`（后两者在 **阶段 5** 模板化后删除）。

## 后果

- `module_html.py` 行数降至约 2600，便于评估阶段 5 剩余迁移量。
- 若未来需要「多 Tab 仪表盘」整页，应新建 `templates/pages/dashboard.html`，不复用已删 f-string。

## 关联阶段

- 阶段 1：删除
- 阶段 5.4：删除整个 `module_html.py`
