# FundEval 全面重构规划

> 创建日期：2026-05-22
> 最后更新：2026-05-22

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

## 分阶段执行计划

### 阶段一：基础设施解耦（2-3天）

**目标**：将硬编码数据和配置抽取为独立模块

**任务**：
1. 创建 `src/data/` 包
2. 从 `fund.py` 提取 `MAJOR_CATEGORIES` → `src/data/sectors.py`
3. 从 `module_html.py` 提取 `bk_map` → `src/data/bk_map.py`
4. 创建 `src/config/settings.py` 统一Flask配置
5. 更新所有引用，使用新路径导入

**新增文件**：
- `src/data/__init__.py`
- `src/data/sectors.py`
- `src/data/bk_map.py`
- `src/config/settings.py`

---

### 阶段二：工具函数抽取（2-3天）

**目标**：将混杂的计算逻辑独立出来

**任务**：
1. 创建 `src/utils/financial.py` - 从 `fund.py` 的 `fund_html()` 内提取：
   - `xnpv()` 函数
   - `solve_xirr()` 函数
2. 创建 `src/utils/cache.py` - 将 `CACHE_MAP` 管理逻辑独立
3. 更新 `fund.py` 从新模块导入

**新增文件**：
- `src/utils/financial.py`
- `src/utils/cache.py`

---

### 阶段三：业务逻辑层抽取（4-5天）

**目标**：从"god类"和路由中提取业务逻辑到Service层

**任务**：
1. 创建 `src/services/` 包
2. 提取 `fund.py` 中的业务方法：
   - `FundService.search_code()` / `search_one_code()`
   - `FundService.get_fund_today_data()`
   - `FundService.calculate_position_summary()`
   - `FundService.get_fund_chart_data()`
3. 将 `compute_holding_metrics()` 提取到 `src/services/metrics.py`
4. 更新 `fund.py` 调用新服务层

**新增文件**：
- `src/services/__init__.py`
- `src/services/fund_service.py`
- `src/services/metrics.py`

**风险**：阶段三最复杂，`fund_html()` 有379行9层嵌套函数

---

### 阶段四：路由层重构（2-3天）

**目标**：将路由与业务逻辑分离

**任务**：
1. 创建 `src/routes/` 包
2. 从 `fund_server.py` 提取路由：
   - `src/routes/auth.py`：`/login`, `/register`, `/logout`
   - `src/routes/fund.py`：`/fund/sector`, `/fund/detail`
   - `src/routes/api.py`：`/api/fund/*`
3. 创建 Flask Blueprint 注册路由
4. 精简 `fund_server.py` 仅保留应用启动逻辑

**新增文件**：
- `src/routes/__init__.py`
- `src/routes/auth.py`
- `src/routes/fund.py`
- `src/routes/api.py`

**风险**：需确保会话管理和认证逻辑不被破坏

---

### 阶段五：前端资源迁移（3-4天）

**目标**：将Python字符串中的HTML/CSS/JS迁移到标准静态文件

**任务**：
1. 创建 `src/static/css/style.css` - 迁移 `get_css_style()` 的995行CSS
2. 创建 `src/static/js/main.js` - 迁移 `get_javascript_code()` 的1540行JS
3. 创建 `src/templates/` - 使用Jinja2模板替代Python字符串拼接
4. 简化 `module_html.py` - 保留必要的动态生成逻辑，核心HTML迁移到模板
5. 更新Flask的 `template_folder` 和 `static_folder` 配置

**新增文件**：
- `src/static/css/style.css`
- `src/static/js/main.js`
- `src/templates/*.html`

**修改文件**：`src/module_html.py`（大幅精简）

---

### 阶段六：热重载机制重构（1-2天）

**目标**：用模块监视替代脆弱的 `importlib.reload`

**任务**：
1. 创建 `src/utils/hot_reload.py` - 使用 `watchdog` 监控文件变化
2. 修改 `fund_server.py` 使用新的热重载机制

**新增文件**：`src/utils/hot_reload.py`

---

### 阶段七：测试与文档（贯穿全程）

**目标**：确保重构后功能完整

**任务**：
1. 编写单元测试覆盖核心服务
2. 编写集成测试验证路由功能
3. 更新代码注释和README

---

## 工作量估计

| 阶段 | 工作量 | 风险 |
|------|--------|------|
| 阶段一 | 2-3天 | 低 |
| 阶段二 | 2-3天 | 低 |
| 阶段三 | 4-5天 | 高 |
| 阶段四 | 2-3天 | 中 |
| 阶段五 | 3-4天 | 中 |
| 阶段六 | 1-2天 | 低 |
| 阶段七 | 贯穿全程 | 低 |

**总工期**：约 14-20 个工作日

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
├── README.md              # 本文件 - 重构规划总览
├── progress/             # 中间记录
│   ├── phase1-xxx.md     # 各阶段完成后的记录
│   └── ...
└── decisions/            # 重大决策记录
    ├── 001-xxx.md        # 决策编号
    └── ...
```
