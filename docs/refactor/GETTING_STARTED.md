# FundEval 重构开发指南

> 本指南帮助开发者快速启动并执行重构工作。完整执行计划见 [PLAN.md](PLAN.md)。

---

## 环境准备

### 1. 安装依赖

```bash
# 基础依赖
pip install -r requirements.txt

# 开发依赖（含 pytest）
pip install -r requirements-dev.txt
```

### 2. 验证 Fixture 格式

```bash
python3 -c "import json; json.load(open('docs/refactor/fixtures/api_fund_data.json')); json.load(open('docs/refactor/fixtures/api_performance_chart_data.json')); print('OK')"
```

### 3. 启动服务

```bash
# 阶段 0-9：直接运行 fund_server.py
python fund_server.py

# 阶段 10+：使用应用工厂
python run.py
```

服务地址：`http://localhost:8311`

---

## 冒烟测试（P0）

每次 PR 合并前必须通过。详见 [checklist.md](checklist.md)。

### 快速验证命令

```bash
# 自动化测试
pytest tests/ -q

# 核心门禁
rg "importlib\.reload" fund_server.py | wc -l    # 阶段 4 后 → 0
wc -l src/module_html.py                           # 阶段 5.4 后 → 0
rg "def \w+_html" src/fund.py | wc -l              # 阶段 5.3 后 → 0
```

---

## 关键门禁

| 阶段 | 命令 | 期望 |
|------|------|------|
| 1 | `wc -l src/module_html.py` | ≤2600 |
| 4 | `rg -c "importlib\.reload" fund_server.py` | 0 |
| 5.4 | `rg -c "module_html" src/ --type py` | 0 |

完整阶段说明见 [PLAN.md](PLAN.md) |

---

## 常见问题

### Q: `importlib.reload` 不生效？

**原因**：阶段 4 前，`fund_server.py` 使用 `importlib.reload(fund)` 热更新。阶段 4 后已改为 Flask `g` 单例。

**解决**：修改 `fund.py` 后重启进程（或等待 Werkzeug reloader 自动重启）。

### Q: Session 过期？

测试建议使用**无痕窗口**，或访问 `/logout` 清空会话后再登录。

### Q: 静态资源 404？

阶段 3 前：静态资源在根目录 `static/`  
阶段 3 后：迁入 `src/static/`，Flask 配置指向 `src/`

### Q: 数据库报错？

确保 `cache/fund_data.db` 存在且可写。首次启动会自动初始化。

---

## 参考文档

| 文档 | 用途 |
|------|------|
| [PLAN.md](PLAN.md) | 完整执行计划（阶段 0-11） |
| [checklist.md](checklist.md) | P0/P1/P2 冒烟测试步骤 |
| [decisions/](decisions/) | ADR 001-006：关键决策记录 |
| [progress/](progress/) | 各阶段完成记录 |
| [fixtures/](fixtures/) | API 响应样例（匿名化） |