# ADR-001：`static/` 与 `templates/` 迁入 `src/`

## 状态

已接受（2026-05-22）

## 背景

- 根目录已有 [`static/`](../../static/)（`style.css`、`main.js` 等）与 [`templates/`](../../templates/)（`login.html`、`register.html`）。
- [`module_html.py`](../../src/module_html.py) 仍内联约 2500 行 CSS/JS，与外链 **重复加载**。
- [PLAN.md](../PLAN.md) 目标结构要求 Flask 工厂统一从 `src/templates`、`src/static` 提供资源。

## 决策

1. **阶段 3** 将根目录 `static/`、`templates/` **整体迁入** `src/static`、`src/templates`。
2. Flask 应用配置：
   - `template_folder` → `src/templates`
   - `static_folder` → `src/static`
   - `static_url_path` 保持 `/static`（浏览器 URL 不变）。
3. 删除 `get_css_style()` / `get_javascript_code()` 后，页面**仅**通过 `<link>` / `<script src>` 引用静态文件。
4. 登录/注册等已用 Jinja 的模板随迁移更新 `url_for('static', ...)` 路径（若硬编码 `/static/` 则保留亦可）。

## 后果

- 正向：资源与 Python 包同处 `src/`，利于打包与部署；消除双份 CSS/JS。
- 负向：短期需全局搜索 `/static/` 与模板路径；开发工具需指向新目录。
- 不回退到「根目录 static + module_html 内联」双轨。

## 关联阶段

- 阶段 3：迁移与去重
- 阶段 10：`create_app()` 固化路径
