# FundEval 全面重构规划

> 创建日期：2026-05-22  
> 最后更新：2026-05-22

**执行计划**：[PLAN.md](PLAN.md) — 阶段 **0–11**，与执行/PR 顺序一致；展示层分离、不含 AI。  
**冒烟清单**：[checklist.md](checklist.md)。

### 文档导航

| 阅读顺序 | 文件 | 用途 |
|----------|------|------|
| 1 | **README.md**（本文件） | 了解背景、目标架构、兼容策略 |
| 2 | [GETTING_STARTED.md](GETTING_STARTED.md) | 搭环境、跑通门禁命令 |
| 3 | [PLAN.md](PLAN.md) | 按阶段跟着编码（23 个 PR、0–11 阶段） |
| 4 | [checklist.md](checklist.md) | 每个 PR 合并前按 P0 清单验证 |
| * | [decisions/](decisions/) | 对某个设计决策有疑问时查阅（6 个 ADR） |
| * | [fixtures/](fixtures/) | API 响应形状样例，阶段 0 写测试时参考 |
| * | [progress/](progress/) | 各阶段完成后填写完成记录 |

---

## 背景

项目存在严重的架构问题，代码难以维护、无法测试、功能扩展困难。

### 现状问题

| 文件 | 行数 | 主要问题 |
|------|------|----------|
| module_html.py | 5810 | Python内嵌995行CSS+1540行JS+HTML字符串，无法维护 |
| fund_server.py | 4648 | 上帝文件：HTTP路由+业务逻辑+数据库+日志清理全混在一起 |
| fund.py | 2895 | LanFund类2895行，fund_html方法379行含9个内嵌函数 |

**核心问题**：
- 分层缺失：路由直接操作数据库，无Service层
- HTML/CSS/JS混杂：前端代码以Python字符串形式存在
- 上帝方法：单个方法超过300行
- 硬编码数据：bk_map 180+行、SECTOR_CATEGORIES 100+行
- 重复代码：5个模态框HTML结构相同但独立书写

---

## 目标目录结构

```
FundEval/
├── src/
│   ├── config/                 # 配置层
│   │   ├── settings.py        # Flask配置
│   │   └── data_sources.py    # 数据源URL
│   ├── models/                 # 数据模型层
│   │   ├── fund.py            # Fund数据模型
│   │   ├── user.py            # User数据模型
│   │   └── transaction.py     # Transaction数据模型
│   ├── services/              # 业务逻辑层（新增）
│   │   ├── fund_service.py    # 基金业务
│   │   ├── nav_service.py     # 净值同步
│   │   └── metrics.py         # 持仓指标计算（XIRR等）
│   ├── routes/                # 路由层（新增）
│   │   ├── auth.py            # 登录/注册/登出
│   │   ├── fund.py            # 基金路由
│   │   └── api.py             # API路由
│   ├── data/                  # 静态数据（替代硬编码）
│   │   ├── sectors.py         # MAJOR_CATEGORIES
│   │   └── bk_map.py          # 板块映射
│   ├── utils/                 # 工具函数
│   │   ├── cache.py           # CACHE_MAP缓存管理
│   │   ├── financial.py       # XIRR/XNPV计算
│   │   └── hot_reload.py      # 热重载机制
│   ├── templates/             # Jinja2模板
│   ├── static/                # 静态资源
│   │   ├── css/style.css      # CSS（从get_css_style迁移）
│   │   └── js/main.js         # JS（从get_javascript_code迁移）
│   ├── database.py            # 数据库访问（精简后）
│   ├── fund.py                # LanFund类（精简后）
│   ├── module_html.py         # HTML生成（精简后）
│   └── web/
│       └── app.py             # Flask应用工厂
├── config.yaml                # 配置文件（保留）
└── run.py                     # 启动入口
```

---

## 执行计划概览

> 详细方案见 [PLAN.md](PLAN.md)（阶段 0–11，24–30 个工作日，23 个 PR）。

| 阶段 | 名称 | 主要产出 | 风险 |
|------|------|----------|------|
| 0 | 回归基线 | pytest + fixtures | 低 |
| 1 | 死代码删除 | `module_html.py` ≤2600 行 | 低 |
| 2 | 数据与配置 | `src/data/`、`src/config/` | 低 |
| 3 | 静态迁移去重 | `static/`、`templates/` → `src/` | 中 |
| 4 | LanFund 单例 | `get_lan_fund()`，reload → 0 | 低 |
| 5 | 展示层分离 | Jinja 模板 + presenters，`module_html.py` → 0 | 中 |
| 6 | 工具与指标 | `financial.py`、`metrics.py`、`cache.py` | 低 |
| 7 | Repository | 4 个 repo 替代直连 db | 中 |
| 8 | Service 层 | 6 个子阶段，业务逻辑迁出路由 | 高 |
| 9 | LanFund 瘦身 | `fund.py` <1200 行 + CLI | 中 |
| 10 | Blueprint | `create_app()` + 4 个 Blueprint | 中 |
| 11 | 收尾 | 文档更新、清理 re-export | 低 |

### 阶段依赖

```
0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11
                        ↘ (6/7/8 可部分并行)
```

### 关键门禁

| 阶段 | 命令 | 期望 |
|------|------|------|
| 1 | `wc -l src/module_html.py` | ≤2600 |
| 3 | `rg -c "get_javascript_code" src/ --type py` | 0 |
| 4 | `rg -c "importlib\.reload" fund_server.py` | 0 |
| 5.3 | `rg -c "def \w+_html" src/fund.py` | 0 |
| 5.4 | `rg -c "module_html" src/ --type py` | 0 |

---

## 兼容性保持策略

### 1. 渐进式迁移
每个阶段完成后确保：应用可正常启动、核心功能正常运行、单元测试通过

### 2. 别名兼容
对于移动的函数/类提供废弃警告：
```python
import warnings
def __getattr__(name):
    if name == 'MAJOR_CATEGORIES':
        warnings.warn("使用旧路径已废弃", DeprecationWarning)
        return _MAJOR_CATEGORIES
```

### 3. Feature Flag
在 `config.yaml` 中添加切换开关：
```yaml
refactor:
  use_new_services: false
  use_new_routes: false
```

---

## 验证步骤

每个阶段完成后执行：
1. `python fund_server.py` - 确认应用正常启动
2. 访问 http://localhost:8311 - 验证登录和核心功能
3. 运行现有测试（如有）
4. 检查无新增警告/错误

---

## 关键文件路径

| 文件 | 行数 | 说明 |
|------|------|------|
| `src/fund.py` | 2895 | LanFund类 |
| `src/module_html.py` | 5810 | HTML生成 |
| `src/database.py` | 1444 | 数据库访问 |
| `fund_server.py` | 4648 | Flask入口 |

---

## 目录结构

```
docs/refactor/
├── README.md              # 本文件 - 背景、问题与初版规划
├── PLAN.md                # v4 执行计划（0–11，推荐）
├── progress/              # 各阶段完成记录
│   ├── phase1-xxx.md
│   └── ...
├── checklist.md           # P0/P1/P2 冒烟步骤
├── fixtures/              # API 响应形状样例（匿名化）
└── decisions/             # ADR 001–005
    ├── 001-src-static-templates.md
    ├── 002-remove-legacy-dashboard.md
    ├── 003-flask-g-lanfund-singleton.md
    ├── 004-presentation-layer-split.md
    └── 005-ai-out-of-scope.md
```
