# FundEval 重构冒烟清单

> 对应 [PLAN.md](PLAN.md) 阶段 0。默认服务：`python fund_server.py` → `http://localhost:8311`  
> **P0**：每个 PR 合并前必跑。**P1**：阶段 5 完成后纳入常规回归。**P2**：阶段 8 完成后纳入。

## 前置条件

1. 已安装依赖：`pip install -r requirements.txt`（阶段 0 另需 `pip install -r requirements-dev.txt`）。
2. 服务已启动，终端无 traceback。
3. 使用**专用测试账号**（勿用生产真实持仓数据）；无账号时先完成「注册」步骤。
4. 浏览器建议无痕窗口，或先访问 `/logout` 清空会话。

---

## P0（每 PR）

### P0-1 登录

| 步骤 | 操作 |
|------|------|
| 1 | `GET http://localhost:8311/login` |
| 2 | 页面含用户名、密码表单（非 500 白屏） |
| 3 | `POST /login`，`Content-Type: application/x-www-form-urlencoded`，字段 `username`、`password` 为有效测试账号 |
| 4 | 跟随重定向（最终进入应用，通常为 `/portfolio` 或经 `/fund` 重定向） |

| 通过标准 | 失败标准 |
|----------|----------|
| HTTP 302/200，响应头 `Set-Cookie` 含 session；持仓页或基金相关 HTML 可见 | 仍停留在 `/login` 且页面 `error` 提示；HTTP 5xx；无限重定向 |

---

### P0-2 持仓页加载

| 步骤 | 操作 |
|------|------|
| 1 | 已登录状态下 `GET http://localhost:8311/portfolio` |
| 2 | 页面含基金列表区域（表格或卡片），导航/样式正常 |
| 3 | 浏览器 Network：`/static/css/style.css`、`/static/js/main.js` 状态 **200**（阶段 3 后为 `src/static` 路径，URL 仍为 `/static/...`） |

| 通过标准 | 失败标准 |
|----------|----------|
| HTTP 200；无「数据加载失败」红色错误条；静态资源非 404 | 500；整页空白；CSS/JS 大量 404；重复加载同一份 CSS 体积异常翻倍（阶段 3 去重后检查） |

---

### P0-3 添加基金

| 步骤 | 操作 |
|------|------|
| 1 | 记下当前自选数量（页面或 `GET /api/fund/data` 的 key 数量） |
| 2 | 通过 UI「添加基金」或 `POST /api/fund/add`，JSON 示例：`{"code":"000001"}`（使用未在列表中的公募代码） |
| 3 | 刷新持仓或再次 `GET /api/fund/data` |

| 通过标准 | 失败标准 |
|----------|----------|
| API 返回 `success: true`（或 UI 提示成功）；`fund/data` 中出现新 `code` | `success: false` 且无合理业务说明；添加后列表未变；5xx |

**记录**：`code` = __________（方便回归确认） |

---

### P0-4 删除基金

| 步骤 | 操作 |
|------|------|
| 1 | 对 P0-3 添加的测试基金执行删除：`POST /api/fund/delete`，`{"code":"<测试代码>"}` |
| 2 | 再次 `GET /api/fund/data` |

| 通过标准 | 失败标准 |
|----------|----------|
| 返回成功；该基金 code 从 map 中消失 | 仍存在于列表；5xx |

**记录**：`code` = __________（方便回归确认） |

---

### P0-5 买入（待确认或成交）

| 步骤 | 操作 |
|------|------|
| 1 | 任选自选池中基金 `code`，`POST /api/fund/buy`，`{"code":"<code>","amount":100}` |
| 2 | 可选：`GET /api/fund/transactions?code=<code>` 查看流水 |

| 通过标准 | 失败标准 |
|----------|----------|
| 返回 `success: true`（含 pending 确认说明亦可）；无 5xx | `基金不存在`（code 不在自选）；金额 ≤0 仍成功；5xx |

**记录**：`code` = __________（方便回归确认） |

---

### P0-6 卖出

| 步骤 | 操作 |
|------|------|
| 1 | 对**份额 > 0** 的基金 `POST /api/fund/sell`，`{"code":"<code>","shares":0.01}`（份额按实际可调） |
| 2 | 若无持仓，先完成 P0-5 并等待结算或改用已有持仓基金 |

| 通过标准 | 失败标准 |
|----------|----------|
| 返回 `success: true` 或明确的业务错误（份额不足）；非 5xx | 无持仓仍成功；5xx |

---

### P0-7 业绩曲线

| 步骤 | 操作 |
|------|------|
| 1 | 从 `GET /api/fund/data` 取一个 `code` |
| 2 | `GET /api/fund/performance-chart-data?code=<code>&interval=SINCE_ESTABLISHMENT`（Cookie 带 session） |
| 3 | 或在持仓页点击「收益/业绩」相关 UI，图表区域有渲染 |

| 通过标准 | 失败标准 |
|----------|----------|
| JSON 含 `chart_data.labels` 数组（可为空但结构完整）；`fund_info.code` 与请求一致；UI 图表无 JS 报错 | HTTP 400/500；`chart_data` 缺失；前端 console 持续报错 |

---

### P0-8 登出

| 步骤 | 操作 |
|------|------|
| 1 | `GET http://localhost:8311/logout` |
| 2 | `GET http://localhost:8311/portfolio`（未带有效 session） |

| 通过标准 | 失败标准 |
|----------|----------|
| 登出后访问受保护页重定向到 `/login`；`GET /api/fund/data` 返回 401 或登录提示 | 登出后仍可访问持仓与 API |

---

## P1（阶段 5 起，每 PR 建议抽查）

### P1-1 板块页 `/sectors`

| 步骤 | `GET /sectors`（已登录） |
| 通过标准 | 200；板块列表与选基区域有内容，无大面积「数据加载失败」 |
| 失败标准 | 500；样式错乱；关键区块缺失 |

### P1-2 Tab 片段 `/api/tab/fund`

| 步骤 | `GET /api/tab/fund`，检查 JSON `success` 与 `content`（HTML 片段） |
| 通过标准 | `success: true`，`content` 非空且含基金表格相关标记 |
| 失败标准 | 404 tab；`success: false`；`content` 为空 |

### P1-3 其它 Tab（阶段 5.3 后按需）

对 `kx`、`gold`、`marker` 等各请求一次 `/api/tab/<id>`，标准同 P1-2。

---

## P2（阶段 8 起）

### P2-1 Excel 导入

| 步骤 | 准备最小 xlsx（含列：基金代码、交易类型、日期、金额等，与现网模板一致），`POST /api/fund/transactions/import` multipart |
| 通过标准 | 返回 job_id 或成功；`GET /api/fund/transactions/import-progress` 最终 `completed` |
| 失败标准 | 5xx；进度永久卡住 |

### P2-2 交易补录

| 步骤 | `POST /api/fund/buy-backfill` 或 `sell-backfill`（按 UI/API 文档字段） |
| 通过标准 | 成功或清晰校验错误；流水可查 |
| 失败标准 | 5xx；静默失败 |

---

## 自动化（阶段 0）

```bash
pytest tests/ -q
```

| 通过标准 | 失败标准 |
|----------|----------|
| 全部 passed / skipped，无 failed | 任一 failed 或 collection error |

Fixture 形状回归（可选，阶段 0 起）：

```bash
# 确认样例 JSON 可被解析（后续可加 schema 测试）
python -c "import json; json.load(open('docs/refactor/fixtures/api_fund_data.json')); json.load(open('docs/refactor/fixtures/api_performance_chart_data.json'))"
```

---

## PR 记录模板

```markdown
## 冒烟 — PR #N / 阶段 X

- 日期：
- 执行人：
- P0：全部通过 / 失败项：P0-x
- P1：（不适用则 N/A）
- pytest：
- 备注：
```
