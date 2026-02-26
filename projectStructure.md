# 基金估值项目概览与登录故障
_Exported on 2026/2/5 at GMT+8 22:29:32 from Cursor (2.2.20)_

---

**User**

这是一个用于查看基金估值的项目，可以在终端启动服务后，在浏览器访问8311端口使用web界面。1. 分析当前项目的逻辑关系；2. 数据会保存在哪里；3. 启动项目后，注册成功了，但登录出现500错误

---

**Cursor**

我先梳理项目结构和关键模块逻辑，然后重点看看认证/登录相关代码与数据存储方式，最后定位你说的注册成功但登录500的具体报错原因并给出修复建议。接下来我会读取主要 Python 文件（尤其是 `fund_server.py` 和 `src` 目录下的模块），必要时再检查模板和静态资源。

已经看完主服务文件的大部分路由结构，接下来我会深入看认证和数据库模块，分析数据存到哪里，并进一步锁定登录500的具体原因。

### 1. 当前项目的整体逻辑关系（模块怎么配合）

- **入口与整体结构**
  - Web 入口是 `fund_server.py`：
    - 创建 `Flask` 应用：`app = Flask(__name__)`，`app.secret_key = "luobobo"`。
    - 初始化数据库：`db = Database()`（来自 `src.database`，底层是 sqlite）。
    - 基金业务逻辑：通过 `importlib.reload(fund); my_fund = fund.LanFund(user_id=..., db=db)` 使用 `fund.py` 里的 `LanFund` 类。
    - HTML 组装：用 `src.module_html` 里的一些函数（例如 `get_portfolio_page_html`、`enhance_fund_tab_content` 等）把表格 HTML 包装成完整页面。

- **认证与会话流程**
  - 认证相关在 `src/auth.py`：
    - `login_required` 装饰器：检查 `session` 里是否有 `user_id`，没有就：
      - 对 `/api/*` 返回 JSON：`{'success': False, 'message': '请先登录'}, 401`
      - 对普通页面重定向到 `/login`
    - `login_user(user_id, username)`：把 `user_id`、`username` 写入 `session`。
    - `logout_user()`：`session.clear()`，并记录日志。
  - `fund_server.py` 中：
    - `/login`：GET 显示登录页面；POST 校验用户名密码，成功后调用 `login_user` 并重定向到 `/fund`（实际上再跳到 `/portfolio`）。
    - `/register`：GET 显示注册页面；POST 校验表单后调用 `db.create_user` 写入数据库，成功后也自动 `login_user` 并跳到 `/portfolio`。
    - `/logout`：清空 session 和 “记住我” cookie，然后回到登录页。
    - 其他所有主要业务页面和 API（`/portfolio`、`/market`、`/api/...` 等）都被 `@login_required` 保护，未登录无法访问。

- **数据库层与业务层**
  - `src/database.py` 负责**用户与基金持仓数据**：
    - 初始化时自动创建 sqlite 数据库和两张表（路径见下一节）：
      - `users(id, username, password_hash, created_at)`
      - `user_funds(user_id, fund_code, fund_key, fund_name, is_hold, shares, sectors, ...)`
    - 用户相关：
      - `create_user(username, password)`：用 `bcrypt.hashpw` 生成 `password_hash`，插入 `users` 表。
      - `get_user_by_username(username)`
      - `verify_password(username, password)`：从 DB 取出密码 hash，用 `bcrypt.checkpw` 验证。
    - 基金相关：
      - `get_user_funds(user_id)`：从 `user_funds` 读取该用户所有基金，组装成一个 `fund_map`（字典，key=基金代码）。
      - `save_user_funds(user_id, fund_map)`：先删掉该用户原有记录，再用 `fund_map` 全量写回。
      - `update_fund_shares(user_id, fund_code, shares)`、`add_fund`、`delete_fund` 等。
  - `fund.py` 的 `LanFund` 类负责**抓取行情 + 生成表格 HTML**：
    - 构造函数：
      - 记录 `user_id` 和 `db`。
      - 调用 `load_cache()`：
        - Web 场景（有 `user_id` 且有 `db`）时：`self.CACHE_MAP = db.get_user_funds(self.user_id)`，即每个用户一份自己的基金缓存。
      - 调用 `self.init()`：初始化外部网站的 csrf 等，用于后续抓取基金数据。
    - `save_cache()`：Web 场景中会把 `self.CACHE_MAP` 写回对应用户的 `user_funds`。
    - 相关功能（很多路由会用到）：
      - `add_code/delete_code`：添加/删除基金代码，并更新缓存和 DB。
      - `fund_html()/bk_html()/kx_html()/real_time_gold_html()/A_html()` 等：调用外部接口，返回包含表格的 HTML 片段。
      - `get_timing_chart_data()/get_volume_chart_data()/get_market_chart_data()`：返回图表 JSON 数据给前端 `Chart.js`。
  - `fund_server.py` 里页面路由的典型流程：
    - 以 `/portfolio` 为例：
      1. 通过 `login_required` 保证已登录，取 `user_id = get_current_user_id()`。
      2. `my_fund = fund.LanFund(user_id=user_id, db=db)` —— 初始化该用户的基金缓存及外部行情环境。
      3. 调用 `my_fund.fund_html()`、`my_fund.A_html()` 等生成表格 HTML。
      4. 再用 `get_portfolio_page_html(...)` 组装成完整的持仓页面。

---

### 2. 数据保存在哪里？

- **数据库文件位置**
  - 在 `src/database.py` 的构造函数中：`def __init__(self, db_path="cache/fund_data.db")`。
  - 也就是说：  
    **用户账号、密码 hash、用户的基金列表与持仓份额等，都保存在项目根目录下的 `cache/fund_data.db` 这个 sqlite 数据库文件里。**

- **数据库结构简要说明**
  - `users` 表（用户信息）：
    - `id`: 自增主键
    - `username`: 唯一用户名
    - `password_hash`: 使用 `bcrypt` 生成的密码哈希（二进制/文本存在 sqlite 里）
    - `created_at`: 注册时间
  - `user_funds` 表（每个用户的基金与持仓信息）：
    - `user_id`: 对应 `users.id`
    - `fund_code`: 基金代码
    - `fund_key`: 外部网站的基金 key
    - `fund_name`: 基金名称
    - `is_hold`: 是否标记为“持有”
    - `shares`: 持仓份额
    - `sectors`: JSON 字符串，存板块标签列表

- **缓存与文件**
  - Web 模式下：
    - `LanFund.load_cache()` 从数据库读入到内存 `self.CACHE_MAP`。
    - `LanFund.save_cache()` 把 `self.CACHE_MAP` 写回 `user_funds` 表。
  - CLI 模式（直接运行 `python fund.py`，没有 `user_id`）：
    - 如果 `user_id` 为 `None`，则不走数据库，而是读写 `cache/fund_map.json`。
    - 所以命令行模式下，基金列表存 `cache/fund_map.json`；Web 模式下，基金相关数据全部落在 `cache/fund_data.db`。

- **行情类数据**
  - 实时行情、板块信息、金价等并**不持久化**在本地数据库：
    - 每次请求时，`LanFund` 会调用外部接口（fund123、百度、金投网等）实时抓取；
    - 抓取的数据仅在接口调用过程中存在内存，用于渲染当前页面/接口响应。

---

### 3. 注册成功但登录 500 的原因分析与排查建议

你描述的是：**注册成功后，再登录就出现 500**。结合代码，比较大的可能有两类场景：

#### 3.1 500 实际发生在重定向后的页面（更可能）

登录 POST 流程是这样的（`fund_server.py` 中 `/login` 路由）：

1. 表单提交 `/login`（POST）。
2. 校验用户名密码：`success, user_id = db.verify_password(username, password)`。
3. 若密码正确：
   - 调用 `login_user(user_id, username)` 设置 `session`。
   - `return redirect(url_for('get_fund'))`。
4. `get_fund` 路由只是：`return redirect('/portfolio')`。
5. `/portfolio` 路由里：
   - 先通过 `@login_required`，确认 `session` 有 `user_id`。
   - 然后执行：
     ```python
     user_id = get_current_user_id()
     importlib.reload(fund)
     my_fund = fund.LanFund(user_id=user_id, db=db)
     ```
   - `LanFund.__init__` 会调用：
     - `self.load_cache()`（从 DB 读用户基金）
     - `self.init()`：访问外部网站获取 csrf token 等：
       ```python
       res = self.session.get("https://www.fund123.cn/fund", ...)
       self._csrf = re.findall('\"csrf\":\"(.*?)\"', res.text)[0]
       ```
     - **如果网络访问失败 / 被墙 / 响应格式变了，使得 `re.findall(...)` 得到空列表，就会抛 `IndexError`，这是未捕获异常，会直接导致 500。**

所以，在这种情况下：
- “注册成功，登录就 500”其实是**登录成功以后，跳转到 `/portfolio` 时在 `LanFund.init()` 内联网抓数据时报错**，与用户名密码本身无关。
- 你在终端里应该能看到类似堆栈，最后几行在 `fund.py` 的 `init()` 或 `search_code` 之类的位置。

**验证方法：**

- 在终端直接运行项目：
  ```bash
  cd /Users/jiaming/Library/CloudStorage/OneDrive-mails.ucas.edu.cn/workspace/FundEval
  python fund_server.py
  ```
- 浏览器重现一次登录，关注终端的完整 traceback：
  - 如果最后几行在 `fund.py` 的 `init`/`A`/`gold` 等函数，说明是外部接口的问题；
  - 如果最后几行在 `database.py` 的 `verify_password` 等函数，才是用户名密码或数据库的问题。

**临时规避方案（如果确实是网络问题）：**

- 在 `LanFund.__init__` 里给 `self.init()` 加 try/except，失败时不要抛异常，只打日志（这样登录后页面会缺少行情数据，但不至于 500），例如：

```python
# 新代码示例（说明思路，实际你可以按需修改）：
def __init__(self, user_id=None, db=None):
    self.user_id = user_id
    self.db = db
    ...
    self.load_cache()
    try:
        self.init()
    except Exception as e:
        logger.error(f"初始化行情环境失败（不影响登录）：{e}")
```

- 或者先在公司/家里能正常访问外网的网络环境下试一次，看是否就没有 500。

如果你愿意，我也可以帮你改一版防御性更好的 `LanFund.__init__` 和相关路由，避免因为外部网站异常把整个登录/页面弄成 500。

#### 3.2 真正登录逻辑本身的问题（可能性相对小）

从代码看，登录表单本身逻辑比较稳健：

- 若用户名或密码为空：返回登录模板并显示“请输入用户名和密码”（不会 500）。
- `db.verify_password` 内部捕获了所有异常，出错只会返回 `(False, None)`，不会抛异常。
- 登录失败时：`return render_template('login.html', error='用户名或密码错误')`，也不会 500。

所以，如果终端 traceback **指向的是 `/login` 这个 view 函数本身**，那可能是：

- `bcrypt` 安装/版本问题，导致 `hashpw`/`checkpw` 内部抛未捕获异常（虽然 `verify_password` 有 try/except，但极端情况下也可能有 C 扩展层面的错误）。
- sqlite 数据文件被手动改动损坏，导致连接或查询异常（但 `verify_password` 已经 try/except，大多数情况还是会返回 False）。

这种情况同样需要你看一次终端完整错误栈，才能更精确判断。

---

### 总结（按你提的 3 点）

1. **项目逻辑关系**：`fund_server.py` 是 Web 入口，路由层；`src/auth.py` 管理 session 和登录保护；`src/database.py` 封装 sqlite 数据库（用户 + 基金持仓）；`fund.py` 的 `LanFund` 负责抓取各类行情、基金数据，生成表格/图表数据，`src/module_html.py` 再把这些拼成完整页面。
2. **数据保存位置**：  
   - **用户及基金数据**：全部保存在 `cache/fund_data.db`（sqlite 库）中的 `users`、`user_funds` 两张表。  
   - **命令行模式的基金列表**：额外会使用 `cache/fund_map.json`。  
   - 行情、指数、金价等为实时抓取，不长期保存在本地。
3. **注册成功但登录 500**：高概率是**登录后重定向到 `/portfolio`，在构造 `LanFund` 并联网抓取外部数据时出错（特别是 `init()` 解析 csrf 失败）**，不是账号密码问题。建议你看终端完整 traceback 确认错误点，并考虑给 `LanFund.__init__` 的 `self.init()` 加一层异常捕获，把外部网络异常变成“只影响行情、不导致整个页面 500”。如果你把那段错误堆栈贴出来，我可以帮你精确改哪几行代码。

```python
     user_id = get_current_user_id()
     importlib.reload(fund)
     my_fund = fund.LanFund(user_id=user_id, db=db)
```

```python
       res = self.session.get("https://www.fund123.cn/fund", ...)
       self._csrf = re.findall('\"csrf\":\"(.*?)\"', res.text)[0]
```

```shellscript
  cd /Users/jiaming/Library/CloudStorage/OneDrive-mails.ucas.edu.cn/workspace/FundEval
  python fund_server.py
```

```python
# 新代码示例（说明思路，实际你可以按需修改）：
def __init__(self, user_id=None, db=None):
    self.user_id = user_id
    self.db = db
    ...
    self.load_cache()
    try:
        self.init()
    except Exception as e:
        logger.error(f"初始化行情环境失败（不影响登录）：{e}")
```

