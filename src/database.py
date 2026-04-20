# -*- coding: UTF-8 -*-

import json
import sqlite3
from decimal import Decimal, ROUND_HALF_UP

import bcrypt
from loguru import logger


class Database:
    def __init__(self, db_path="cache/fund_data.db"):
        self.db_path = db_path
        self.init_database()

    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 返回字典格式
        return conn

    @staticmethod
    def _round_shares(value):
        try:
            return float(Decimal(str(value or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        except Exception:
            return 0.0

    def init_database(self):
        """初始化数据库表"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 创建用户表
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS users
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           username
                           TEXT
                           UNIQUE
                           NOT
                           NULL,
                           password_hash
                           TEXT
                           NOT
                           NULL,
                           created_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP
                       )
                       ''')

        # 创建用户基金表
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS user_funds
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           user_id
                           INTEGER
                           NOT
                           NULL,
                           fund_code
                           TEXT
                           NOT
                           NULL,
                           fund_key
                           TEXT
                           NOT
                           NULL,
                           fund_name
                           TEXT
                           NOT
                           NULL,
                           is_hold
                           BOOLEAN
                           DEFAULT
                           0,
                           shares
                           REAL
                           DEFAULT
                           0,
                           sectors
                           TEXT,
                           establishment_date
                           TEXT,
                           estimate_history
                           TEXT
                           DEFAULT
                           '{}',
                           FOREIGN
                           KEY
                       (
                           user_id
                       ) REFERENCES users
                       (
                           id
                       ) ON DELETE CASCADE,
                           UNIQUE
                       (
                           user_id,
                           fund_code
                       )
                           )
                       ''')

        # 交易记录表（用于后续收益率与年化收益率计算）
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS fund_transactions
                       (
                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                           user_id INTEGER NOT NULL,
                           fund_code TEXT NOT NULL,
                           order_no TEXT,
                           tx_type TEXT NOT NULL,
                           amount REAL NOT NULL DEFAULT 0,
                           shares REAL NOT NULL DEFAULT 0,
                           net_value REAL,
                           tx_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                           FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                       )
                       ''')

        # 历史数据归一化：份额统一保留两位小数
        try:
            cursor.execute('''
                UPDATE user_funds
                SET shares = ROUND(COALESCE(shares, 0), 2)
            ''')
            cursor.execute('''
                UPDATE fund_transactions
                SET shares = ROUND(COALESCE(shares, 0), 2)
            ''')
        except Exception as e:
            logger.warning(f"Failed to normalize historical shares precision: {e}")

        cursor.execute("PRAGMA table_info(fund_transactions)")
        tx_columns = [col[1] for col in cursor.fetchall()]
        if 'order_no' not in tx_columns:
            try:
                cursor.execute('ALTER TABLE fund_transactions ADD COLUMN order_no TEXT')
                logger.debug("Added order_no column to fund_transactions table")
            except Exception as e:
                if "duplicate column" not in str(e).lower():
                    logger.warning(f"Failed to add order_no column: {e}")

        if 'fee' not in tx_columns:
            try:
                cursor.execute('ALTER TABLE fund_transactions ADD COLUMN fee REAL NOT NULL DEFAULT 0')
                logger.debug("Added fee column to fund_transactions table")
            except Exception as e:
                if "duplicate column" not in str(e).lower():
                    logger.warning(f"Failed to add fee column: {e}")

        try:
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_fund_transactions_order_no_unique
                ON fund_transactions(order_no)
                WHERE order_no IS NOT NULL AND order_no != ''
            ''')
        except Exception as e:
            logger.warning(f"Failed to create unique index for order_no: {e}")

        # 待确认买入记录（按生效净值日确认份额）
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS fund_pending_buys
                       (
                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                           user_id INTEGER NOT NULL,
                           fund_code TEXT NOT NULL,
                           amount REAL NOT NULL DEFAULT 0,
                           effective_date TEXT NOT NULL,
                           status TEXT NOT NULL DEFAULT 'pending',
                           settled_tx_id INTEGER,
                           settled_net_value REAL,
                           settled_shares REAL,
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                           settled_at TIMESTAMP,
                           FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                           FOREIGN KEY (settled_tx_id) REFERENCES fund_transactions (id)
                       )
                       ''')

        # 基金历史净值缓存（用于快速按日期读取，减少远端请求）
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS fund_nav_history
                       (
                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                           fund_code TEXT NOT NULL,
                           nav_date TEXT NOT NULL,
                           nav_value REAL NOT NULL,
                           source TEXT,
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                           updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                           UNIQUE(fund_code, nav_date)
                       )
                       ''')

        try:
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_fund_nav_history_code_date
                ON fund_nav_history(fund_code, nav_date)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_fund_nav_history_date
                ON fund_nav_history(nav_date)
            ''')
        except Exception as e:
            logger.warning(f"Failed to create indexes for fund_nav_history: {e}")

        # 基金业绩曲线缓存（本地优先读取，降低远端请求频率）
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS fund_performance_curve_cache
                       (
                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                           fund_code TEXT NOT NULL,
                           date_interval TEXT NOT NULL,
                           curve_date TEXT NOT NULL,
                           growth_rate REAL,
                           benchmark_growth_rate REAL,
                           nav_value REAL,
                           source TEXT,
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                           updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                           UNIQUE(fund_code, date_interval, curve_date)
                       )
                       ''')

        try:
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_curve_cache_code_interval_date
                ON fund_performance_curve_cache(fund_code, date_interval, curve_date)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_curve_cache_code_date
                ON fund_performance_curve_cache(fund_code, curve_date)
            ''')
        except Exception as e:
            logger.warning(f"Failed to create indexes for fund_performance_curve_cache: {e}")

        # 指数历史净值缓存（用于业绩曲线基准对比）
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS index_nav_history
                       (
                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                           index_code TEXT NOT NULL,
                           nav_date TEXT NOT NULL,
                           close REAL NOT NULL,
                           change_pct REAL,
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                           updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                           UNIQUE(index_code, nav_date)
                       )
                       ''')
        try:
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_index_nav_history_code_date
                ON index_nav_history(index_code, nav_date)
            ''')
        except Exception as e:
            logger.warning(f"Failed to create indexes for index_nav_history: {e}")

        # 检查并添加chart_default字段
        cursor.execute("PRAGMA table_info(user_funds)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'chart_default' not in columns:
            try:
                cursor.execute('ALTER TABLE user_funds ADD COLUMN chart_default BOOLEAN DEFAULT 0')
                logger.debug("Added chart_default column to user_funds table")
            except Exception as e:
                if "duplicate column" not in str(e).lower():
                    logger.warning(f"Failed to add chart_default column: {e}")

        # 检查并添加estimate_history字段
        if 'estimate_history' not in columns:
            try:
                cursor.execute("ALTER TABLE user_funds ADD COLUMN estimate_history TEXT DEFAULT '{}'")
                logger.debug("Added estimate_history column to user_funds table")
            except Exception as e:
                if "duplicate column" not in str(e).lower():
                    logger.warning(f"Failed to add estimate_history column: {e}")

        # 检查并添加establishment_date字段
        if 'establishment_date' not in columns:
            try:
                cursor.execute("ALTER TABLE user_funds ADD COLUMN establishment_date TEXT")
                logger.debug("Added establishment_date column to user_funds table")
            except Exception as e:
                if "duplicate column" not in str(e).lower():
                    logger.warning(f"Failed to add establishment_date column: {e}")

        conn.commit()
        conn.close()
        logger.debug("Database initialized successfully")

    # ==================== User Operations ====================

    def create_user(self, username, password):
        """创建新用户

        Args:
            username: 用户名
            password: 明文密码

        Returns:
            (success: bool, message: str, user_id: int or None)
        """
        try:
            # 检查用户名是否已存在
            if self.get_user_by_username(username):
                return False, "用户名已存在", None

            # 生成密码哈希
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12))

            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO users (username, password_hash) VALUES (?, ?)',
                (username, password_hash)
            )
            user_id = cursor.lastrowid
            conn.commit()
            conn.close()

            logger.info(f"User created successfully: {username} (ID: {user_id})")
            return True, "注册成功", user_id

        except Exception as e:
            logger.error(f"Failed to create user {username}: {e}")
            return False, f"注册失败: {str(e)}", None

    def get_user_by_username(self, username):
        """根据用户名获取用户信息

        Returns:
            dict or None
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            row = cursor.fetchone()
            conn.close()

            if row:
                return dict(row)
            return None

        except Exception as e:
            logger.error(f"Failed to get user {username}: {e}")
            return None

    def verify_password(self, username, password):
        """验证用户密码

        Returns:
            (success: bool, user_id: int or None)
        """
        try:
            user = self.get_user_by_username(username)
            if not user:
                return False, None

            password_hash = user['password_hash']
            if isinstance(password_hash, str):
                password_hash = password_hash.encode('utf-8')

            if bcrypt.checkpw(password.encode('utf-8'), password_hash):
                return True, user['id']
            else:
                return False, None

        except Exception as e:
            logger.error(f"Failed to verify password for {username}: {e}")
            return False, None

    # ==================== Fund Operations ====================

    def get_user_funds(self, user_id):
        """获取用户的所有基金数据

        Returns:
            dict: 格式与 fund_map.json 相同
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM user_funds WHERE user_id = ?', (user_id,))
            rows = cursor.fetchall()
            conn.close()

            fund_map = {}
            for row in rows:
                fund_code = row['fund_code']
                sectors = json.loads(row['sectors']) if row['sectors'] else []
                estimate_history = json.loads(row['estimate_history']) if row['estimate_history'] else {}

                fund_map[fund_code] = {
                    'fund_key': row['fund_key'],
                    'fund_name': row['fund_name'],
                    'is_hold': bool(row['is_hold']),
                    'shares': float(row['shares']) if row['shares'] else 0,
                    'sectors': sectors,  # 始终包含 sectors 字段
                    'establishment_date': row['establishment_date'],
                    'estimate_history': estimate_history,
                }

            return fund_map

        except Exception as e:
            logger.error(f"Failed to get funds for user {user_id}: {e}")
            return {}

    def save_user_funds(self, user_id, fund_map):
        """保存用户的所有基金数据（完全替换）

        Args:
            user_id: 用户ID
            fund_map: dict, 格式与 fund_map.json 相同
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # 删除用户现有的所有基金数据
            cursor.execute('DELETE FROM user_funds WHERE user_id = ?', (user_id,))

            # 插入新的基金数据
            for fund_code, fund_data in fund_map.items():
                sectors_json = json.dumps(fund_data.get('sectors', []), ensure_ascii=False)
                estimate_history_json = json.dumps(fund_data.get('estimate_history', {}), ensure_ascii=False)

                cursor.execute('''
                               INSERT INTO user_funds
                                   (user_id, fund_code, fund_key, fund_name, is_hold, shares, sectors, establishment_date, estimate_history)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                               ''', (
                                   user_id,
                                   fund_code,
                                   fund_data['fund_key'],
                                   fund_data['fund_name'],
                                   1 if fund_data.get('is_hold', False) else 0,
                                   fund_data.get('shares', 0),
                                   sectors_json,
                                   fund_data.get('establishment_date'),
                                   estimate_history_json
                               ))

            conn.commit()
            conn.close()
            logger.debug(f"Saved {len(fund_map)} funds for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save funds for user {user_id}: {e}")
            return False

    def update_fund_shares(self, user_id, fund_code, shares):
        """更新基金持仓份额

        Args:
            user_id: 用户ID
            fund_code: 基金代码
            shares: 份额数量
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            shares = self._round_shares(shares)
            is_hold = 1 if shares > 0 else 0

            cursor.execute('''
                           UPDATE user_funds
                           SET shares = ?, is_hold = ?
                           WHERE user_id = ?
                             AND fund_code = ?
                           ''', (shares, is_hold, user_id, fund_code))

            conn.commit()
            affected_rows = cursor.rowcount
            conn.close()

            if affected_rows > 0:
                logger.debug(f"Updated shares for user {user_id}, fund {fund_code}: {shares}")
                return True
            else:
                logger.warning(f"No fund found to update: user {user_id}, fund {fund_code}")
                return False

        except Exception as e:
            logger.error(f"Failed to update shares: {e}")
            return False

    def add_fund(self, user_id, fund_code, fund_key, fund_name):
        """添加基金到用户列表

        Returns:
            bool: 是否成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO user_funds
                (user_id, fund_code, fund_key, fund_name, is_hold, shares, sectors, establishment_date, estimate_history)
                VALUES (?, ?, ?, ?, 0, 0, '[]', NULL, '{}')
            ''', (user_id, fund_code, fund_key, fund_name))

            conn.commit()
            conn.close()
            logger.debug(f"Added fund {fund_code} for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add fund: {e}")
            return False

    def delete_fund(self, user_id, fund_code):
        """删除用户的基金

        Returns:
            bool: 是否成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                           DELETE
                           FROM user_funds
                           WHERE user_id = ?
                             AND fund_code = ?
                           ''', (user_id, fund_code))

            conn.commit()
            affected_rows = cursor.rowcount
            conn.close()

            if affected_rows > 0:
                logger.debug(f"Deleted fund {fund_code} for user {user_id}")
                return True
            else:
                logger.warning(f"No fund found to delete: user {user_id}, fund {fund_code}")
                return False

        except Exception as e:
            logger.error(f"Failed to delete fund: {e}")
            return False

    def update_chart_default(self, user_id, fund_code):
        """设置估值趋势图默认基金

        Args:
            user_id: 用户ID
            fund_code: 基金代码

        Returns:
            bool: 是否成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # 先清除该用户的所有chart_default标记
            cursor.execute('UPDATE user_funds SET chart_default = 0 WHERE user_id = ?', (user_id,))

            # 设置新的默认基金
            cursor.execute('''
                           UPDATE user_funds
                           SET chart_default = 1
                           WHERE user_id = ?
                             AND fund_code = ?
                           ''', (user_id, fund_code))

            conn.commit()
            affected_rows = cursor.rowcount
            conn.close()

            if affected_rows > 0:
                logger.debug(f"Set chart default fund for user {user_id}: {fund_code}")
                return True
            else:
                logger.warning(f"No fund found to set as default: user {user_id}, fund {fund_code}")
                return False

        except Exception as e:
            logger.error(f"Failed to update chart default: {e}")
            return False

    def update_fund_shares_delta(self, user_id, fund_code, shares_delta):
        """按增量更新基金份额，返回更新后的份额。"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT shares FROM user_funds
                WHERE user_id = ? AND fund_code = ?
            ''', (user_id, fund_code))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return None

            current_shares = self._round_shares(row['shares'] or 0)
            delta_shares = self._round_shares(shares_delta)
            new_shares = self._round_shares(current_shares + delta_shares)
            if new_shares < 0:
                conn.close()
                return None

            is_hold = 1 if new_shares > 0 else 0
            cursor.execute('''
                UPDATE user_funds
                SET shares = ?, is_hold = ?
                WHERE user_id = ? AND fund_code = ?
            ''', (new_shares, is_hold, user_id, fund_code))

            conn.commit()
            conn.close()
            return new_shares
        except Exception as e:
            logger.error(f"Failed to update shares delta: {e}")
            return None

    def update_fund_establishment_date(self, user_id, fund_code, establishment_date):
        """更新用户基金成立日期（YYYY-MM-DD）。"""
        try:
            value = str(establishment_date or '').strip()
            if not value:
                return False

            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE user_funds
                SET establishment_date = ?
                WHERE user_id = ? AND fund_code = ?
            ''', (value, user_id, fund_code))

            conn.commit()
            affected_rows = cursor.rowcount
            conn.close()
            return affected_rows > 0
        except Exception as e:
            logger.error(f"Failed to update fund establishment date: {e}")
            return False

    def recalculate_fund_shares_from_transactions(self, user_id, fund_code):
        """按交易流水重算单只基金当前持仓并回写 user_funds。"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id FROM user_funds
                WHERE user_id = ? AND fund_code = ?
            ''', (user_id, fund_code))
            fund_row = cursor.fetchone()
            if not fund_row:
                conn.close()
                return None

            cursor.execute('''
                SELECT tx_type, shares
                FROM fund_transactions
                WHERE user_id = ? AND fund_code = ?
                ORDER BY datetime(tx_time) ASC, id ASC
            ''', (user_id, fund_code))
            rows = cursor.fetchall()

            total_shares = 0.0
            for row in rows:
                tx_type = str(row['tx_type'] or '').strip().lower()
                tx_shares = self._round_shares(row['shares'] or 0)
                if tx_type == 'buy':
                    total_shares += tx_shares
                elif tx_type == 'sell':
                    total_shares -= tx_shares

            total_shares = self._round_shares(max(total_shares, 0.0))
            is_hold = 1 if total_shares > 0 else 0

            cursor.execute('''
                UPDATE user_funds
                SET shares = ?, is_hold = ?
                WHERE user_id = ? AND fund_code = ?
            ''', (total_shares, is_hold, user_id, fund_code))

            conn.commit()
            conn.close()
            return {
                'current_shares': total_shares,
                'current_is_hold': bool(is_hold),
            }
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            logger.error(f"Failed to recalculate fund shares from transactions: {e}")
            return None

    def add_fund_transaction(self, user_id, fund_code, tx_type, amount, shares, net_value=None, tx_time=None, fee=0.0,
                             order_no=None):
        """写入基金交易记录。"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            normalized_order_no = str(order_no).strip() if order_no is not None else None
            if normalized_order_no == '':
                normalized_order_no = None
            normalized_shares = self._round_shares(shares)

            if tx_time:
                cursor.execute('''
                    INSERT INTO fund_transactions
                    (user_id, fund_code, order_no, tx_type, amount, shares, net_value, tx_time, fee)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, fund_code, normalized_order_no, tx_type, amount, normalized_shares, net_value, tx_time, fee))
            else:
                cursor.execute('''
                    INSERT INTO fund_transactions
                    (user_id, fund_code, order_no, tx_type, amount, shares, net_value, fee)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, fund_code, normalized_order_no, tx_type, amount, normalized_shares, net_value, fee))

            tx_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return tx_id
        except Exception as e:
            logger.error(f"Failed to add transaction: {e}")
            return None

    def add_pending_buy(self, user_id, fund_code, amount, effective_date):
        """创建待确认买入记录。"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO fund_pending_buys
                (user_id, fund_code, amount, effective_date, status)
                VALUES (?, ?, ?, ?, 'pending')
            ''', (user_id, fund_code, amount, effective_date))
            pending_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return pending_id
        except Exception as e:
            logger.error(f"Failed to add pending buy: {e}")
            return None

    def get_pending_buys(self, user_id, fund_code=None):
        """获取待确认买入记录（按创建时间正序）。"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            if fund_code:
                cursor.execute('''
                    SELECT id, user_id, fund_code, amount, effective_date, status,
                           settled_tx_id, settled_net_value, settled_shares, created_at, settled_at
                    FROM fund_pending_buys
                    WHERE user_id = ? AND fund_code = ? AND status = 'pending'
                    ORDER BY datetime(created_at) ASC, id ASC
                ''', (user_id, fund_code))
            else:
                cursor.execute('''
                    SELECT id, user_id, fund_code, amount, effective_date, status,
                           settled_tx_id, settled_net_value, settled_shares, created_at, settled_at
                    FROM fund_pending_buys
                    WHERE user_id = ? AND status = 'pending'
                    ORDER BY datetime(created_at) ASC, id ASC
                ''', (user_id,))

            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get pending buys for user {user_id}: {e}")
            return []

    def mark_pending_buy_settled(self, pending_id, settled_tx_id, settled_net_value, settled_shares):
        """将待确认买入标记为已结算。"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE fund_pending_buys
                SET status = 'settled',
                    settled_tx_id = ?,
                    settled_net_value = ?,
                    settled_shares = ?,
                    settled_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'pending'
            ''', (settled_tx_id, settled_net_value, settled_shares, pending_id))
            conn.commit()
            affected_rows = cursor.rowcount
            conn.close()
            return affected_rows > 0
        except Exception as e:
            logger.error(f"Failed to mark pending buy settled: {e}")
            return False

    def get_fund_transactions(self, user_id, fund_code):
        """获取单只基金的交易记录（按时间正序）。"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, user_id, fund_code, order_no, tx_type, amount, shares, net_value, tx_time, fee
                FROM fund_transactions
                WHERE user_id = ? AND fund_code = ?
                ORDER BY datetime(tx_time) ASC, id ASC
            ''', (user_id, fund_code))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get transactions for user {user_id}, fund {fund_code}: {e}")
            return []

    def get_all_fund_transactions(self, user_id):
        """获取当前用户的全部基金交易记录（按时间正序）。"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, user_id, fund_code, order_no, tx_type, amount, shares, net_value, tx_time, fee
                FROM fund_transactions
                WHERE user_id = ?
                ORDER BY fund_code ASC, datetime(tx_time) ASC, id ASC
            ''', (user_id,))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get all transactions for user {user_id}: {e}")
            return []

    def exists_transaction_order_no(self, order_no):
        """检查订单号是否已存在。"""
        try:
            normalized_order_no = str(order_no or '').strip()
            if not normalized_order_no:
                return False

            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 1
                FROM fund_transactions
                WHERE order_no = ?
                LIMIT 1
            ''', (normalized_order_no,))
            row = cursor.fetchone()
            conn.close()
            return row is not None
        except Exception as e:
            logger.error(f"Failed to check transaction order_no exists: {e}")
            return False

    def get_fund_nav_by_date(self, fund_code, nav_date):
        """读取本地缓存的基金净值。"""
        try:
            code = str(fund_code or '').strip()
            date_text = str(nav_date or '').strip()
            if not code or not date_text:
                return None

            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT nav_value
                FROM fund_nav_history
                WHERE fund_code = ? AND nav_date = ?
                LIMIT 1
            ''', (code, date_text))
            row = cursor.fetchone()
            conn.close()
            if not row:
                return None
            value = float(row['nav_value'])
            return value if value > 0 else None
        except Exception as e:
            logger.error(f"Failed to get fund nav by date: {e}")
            return None

    def upsert_fund_nav_history(self, fund_code, nav_date, nav_value, source=None):
        """写入/更新基金历史净值缓存。"""
        try:
            code = str(fund_code or '').strip()
            date_text = str(nav_date or '').strip()
            value = float(nav_value)
            source_text = str(source or '').strip() if source is not None else None
            if not code or not date_text or value <= 0:
                return False

            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO fund_nav_history (fund_code, nav_date, nav_value, source, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(fund_code, nav_date)
                DO UPDATE SET
                    nav_value = excluded.nav_value,
                    source = excluded.source,
                    updated_at = CURRENT_TIMESTAMP
            ''', (code, date_text, value, source_text))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to upsert fund nav history: {e}")
            return False

    def get_fund_nav_history_range(self, fund_code, start_date=None, end_date=None):
        """按日期区间读取基金净值缓存，返回 {nav_date: nav_value}。"""
        try:
            code = str(fund_code or '').strip()
            if not code:
                return {}

            conn = self.get_connection()
            cursor = conn.cursor()

            sql = '''
                SELECT nav_date, nav_value
                FROM fund_nav_history
                WHERE fund_code = ?
            '''
            params = [code]

            if start_date:
                sql += ' AND nav_date >= ?'
                params.append(str(start_date).strip())

            if end_date:
                sql += ' AND nav_date <= ?'
                params.append(str(end_date).strip())

            sql += ' ORDER BY nav_date ASC'

            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            conn.close()

            result = {}
            for row in rows:
                nav_date = str(row['nav_date'] or '').strip()
                if not nav_date:
                    continue
                try:
                    nav_value = float(row['nav_value'])
                except Exception:
                    continue
                if nav_value > 0:
                    result[nav_date] = round(nav_value, 4)
            return result
        except Exception as e:
            logger.error(f"Failed to get fund nav history range: {e}")
            return {}

    def get_fund_performance_curve_cache(self, fund_code, date_interval, start_date=None, end_date=None):
        """读取基金业绩曲线缓存（按日期正序）。"""
        try:
            code = str(fund_code or '').strip()
            interval = str(date_interval or '').strip().upper()
            if not code or not interval:
                return []

            conn = self.get_connection()
            cursor = conn.cursor()

            sql = '''
                SELECT curve_date, growth_rate, benchmark_growth_rate, nav_value
                FROM fund_performance_curve_cache
                WHERE fund_code = ? AND date_interval = ?
            '''
            params = [code, interval]

            if start_date:
                sql += ' AND curve_date >= ?'
                params.append(str(start_date).strip())

            if end_date:
                sql += ' AND curve_date <= ?'
                params.append(str(end_date).strip())

            sql += ' ORDER BY curve_date ASC'

            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get fund performance curve cache: {e}")
            return []

    def bulk_upsert_fund_performance_curve_cache(self, fund_code, date_interval, curve_points, source=None):
        """批量写入/更新基金业绩曲线缓存。"""
        try:
            code = str(fund_code or '').strip()
            interval = str(date_interval or '').strip().upper()
            if not code or not interval or not curve_points:
                return 0

            source_text = str(source or '').strip() if source is not None else None
            rows = []
            for point in curve_points:
                curve_date = str(point.get('curve_date') or '').strip()
                if not curve_date:
                    continue

                growth_rate = point.get('growth_rate')
                benchmark_growth_rate = point.get('benchmark_growth_rate')
                nav_value = point.get('nav_value')

                try:
                    growth_rate = float(growth_rate) if growth_rate is not None else None
                except Exception:
                    growth_rate = None

                try:
                    benchmark_growth_rate = float(benchmark_growth_rate) if benchmark_growth_rate is not None else None
                except Exception:
                    benchmark_growth_rate = None

                try:
                    nav_value = float(nav_value) if nav_value is not None else None
                except Exception:
                    nav_value = None

                rows.append((
                    code,
                    interval,
                    curve_date,
                    growth_rate,
                    benchmark_growth_rate,
                    nav_value,
                    source_text,
                ))

            if not rows:
                return 0

            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT INTO fund_performance_curve_cache
                (fund_code, date_interval, curve_date, growth_rate, benchmark_growth_rate, nav_value, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(fund_code, date_interval, curve_date)
                DO UPDATE SET
                    growth_rate = excluded.growth_rate,
                    benchmark_growth_rate = excluded.benchmark_growth_rate,
                    nav_value = excluded.nav_value,
                    source = excluded.source,
                    updated_at = CURRENT_TIMESTAMP
            ''', rows)
            conn.commit()
            conn.close()
            return len(rows)
        except Exception as e:
            logger.error(f"Failed to bulk upsert fund performance curve cache: {e}")
            return 0

    def update_fund_transaction_and_recalculate(self, user_id, fund_code, tx_id, tx_type, amount, shares, net_value, tx_time, fee=0.0):
        """更新交易并按剩余交易重算该基金份额。"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id FROM fund_transactions
                WHERE id = ? AND user_id = ? AND fund_code = ?
            ''', (tx_id, user_id, fund_code))
            target_tx = cursor.fetchone()
            if not target_tx:
                conn.close()
                return None

            shares = self._round_shares(shares)
            cursor.execute('''
                UPDATE fund_transactions
                SET tx_type = ?, amount = ?, shares = ?, net_value = ?, tx_time = ?, fee = ?
                WHERE id = ? AND user_id = ? AND fund_code = ?
            ''', (tx_type, amount, shares, net_value, tx_time, fee, tx_id, user_id, fund_code))
            if cursor.rowcount <= 0:
                conn.rollback()
                conn.close()
                return None

            cursor.execute('''
                SELECT tx_type, shares
                FROM fund_transactions
                WHERE user_id = ? AND fund_code = ?
                ORDER BY datetime(tx_time) ASC, id ASC
            ''', (user_id, fund_code))
            rows = cursor.fetchall()

            total_shares = 0.0
            for row in rows:
                now_type = str(row['tx_type'] or '').strip().lower()
                now_shares = self._round_shares(row['shares'] or 0)
                if now_type == 'buy':
                    total_shares += now_shares
                elif now_type == 'sell':
                    total_shares -= now_shares

            total_shares = self._round_shares(max(total_shares, 0.0))
            is_hold = 1 if total_shares > 0 else 0
            cursor.execute('''
                UPDATE user_funds
                SET shares = ?, is_hold = ?
                WHERE user_id = ? AND fund_code = ?
            ''', (total_shares, is_hold, user_id, fund_code))

            conn.commit()
            conn.close()
            return {
                'current_shares': total_shares,
                'current_is_hold': bool(is_hold),
            }
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            logger.error(f"Failed to update transaction and recalculate shares: {e}")
            return None

    def delete_fund_transaction_and_recalculate(self, user_id, fund_code, tx_id):
        """删除交易并按剩余交易重算该基金份额。"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, tx_type, shares
                FROM fund_transactions
                WHERE id = ? AND user_id = ? AND fund_code = ?
            ''', (tx_id, user_id, fund_code))
            target_tx = cursor.fetchone()
            if not target_tx:
                conn.close()
                return None

            cursor.execute('''
                UPDATE fund_pending_buys
                SET settled_tx_id = NULL
                WHERE settled_tx_id = ?
            ''', (tx_id,))

            cursor.execute('''
                DELETE FROM fund_transactions
                WHERE id = ? AND user_id = ? AND fund_code = ?
            ''', (tx_id, user_id, fund_code))
            if cursor.rowcount <= 0:
                conn.rollback()
                conn.close()
                return None

            cursor.execute('''
                SELECT tx_type, shares
                FROM fund_transactions
                WHERE user_id = ? AND fund_code = ?
                ORDER BY datetime(tx_time) ASC, id ASC
            ''', (user_id, fund_code))
            rows = cursor.fetchall()

            total_shares = 0.0
            for row in rows:
                tx_type = str(row['tx_type'] or '').strip().lower()
                tx_shares = self._round_shares(row['shares'] or 0)
                if tx_type == 'buy':
                    total_shares += tx_shares
                elif tx_type == 'sell':
                    total_shares -= tx_shares

            total_shares = self._round_shares(max(total_shares, 0.0))
            is_hold = 1 if total_shares > 0 else 0
            cursor.execute('''
                UPDATE user_funds
                SET shares = ?, is_hold = ?
                WHERE user_id = ? AND fund_code = ?
            ''', (total_shares, is_hold, user_id, fund_code))

            conn.commit()
            conn.close()
            return {
                'deleted': {
                    'id': int(target_tx['id']),
                    'tx_type': str(target_tx['tx_type'] or ''),
                    'shares': self._round_shares(target_tx['shares'] or 0),
                },
                'current_shares': total_shares,
                'current_is_hold': bool(is_hold),
            }
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            logger.error(f"Failed to delete transaction and recalculate shares: {e}")
            return None

    def clear_fund_transactions_and_recalculate(self, user_id, fund_code):
        """清空单只基金的全部交易记录，并将该基金持仓重置为0。"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id
                FROM fund_transactions
                WHERE user_id = ? AND fund_code = ?
                ORDER BY datetime(tx_time) ASC, id ASC
            ''', (user_id, fund_code))
            rows = cursor.fetchall()
            tx_ids = [int(row['id']) for row in rows]

            if tx_ids:
                placeholders = ','.join(['?'] * len(tx_ids))
                cursor.execute(
                    f'''
                    UPDATE fund_pending_buys
                    SET settled_tx_id = NULL
                    WHERE settled_tx_id IN ({placeholders})
                    ''',
                    tx_ids,
                )

            cursor.execute('''
                DELETE FROM fund_transactions
                WHERE user_id = ? AND fund_code = ?
            ''', (user_id, fund_code))
            deleted_count = int(cursor.rowcount or 0)

            cursor.execute('''
                UPDATE user_funds
                SET shares = 0, is_hold = 0
                WHERE user_id = ? AND fund_code = ?
            ''', (user_id, fund_code))

            conn.commit()
            conn.close()
            return {
                'deleted_count': deleted_count,
                'current_shares': 0.0,
                'current_is_hold': False,
            }
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            logger.error(f"Failed to clear transactions and recalculate shares: {e}")
            return None

    def clear_all_fund_transactions_and_recalculate(self, user_id):
        """清空当前用户全部基金交易记录，并将全部持仓重置为0。"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id FROM fund_transactions WHERE user_id = ?
            ''', (user_id,))
            rows = cursor.fetchall()
            tx_ids = [int(row['id']) for row in rows]

            if tx_ids:
                placeholders = ','.join(['?'] * len(tx_ids))
                cursor.execute(
                    f'''
                    UPDATE fund_pending_buys
                    SET settled_tx_id = NULL
                    WHERE settled_tx_id IN ({placeholders})
                    ''',
                    tx_ids,
                )

            cursor.execute('''
                DELETE FROM fund_transactions WHERE user_id = ?
            ''', (user_id,))
            deleted_count = int(cursor.rowcount or 0)

            cursor.execute('''
                UPDATE user_funds
                SET shares = 0, is_hold = 0
                WHERE user_id = ?
            ''', (user_id,))
            affected_funds = int(cursor.rowcount or 0)

            conn.commit()
            conn.close()
            return {
                'deleted_count': deleted_count,
                'affected_funds': affected_funds,
            }
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            logger.error(f"Failed to clear all transactions and recalculate shares: {e}")
            return None

    def get_chart_default_fund(self, user_id):
        """获取估值趋势图默认基金

        Args:
            user_id: 用户ID

        Returns:
            dict or None: {'fund_code': str, 'fund_key': str, 'fund_name': str}
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                           SELECT fund_code, fund_key, fund_name
                           FROM user_funds
                           WHERE user_id = ? AND chart_default = 1
                           ''', (user_id,))
            row = cursor.fetchone()
            conn.close()

            if row:
                return {
                    'fund_code': row['fund_code'],
                    'fund_key': row['fund_key'],
                    'fund_name': row['fund_name']
                }
            return None

        except Exception as e:
            logger.error(f"Failed to get chart default fund for user {user_id}: {e}")
            return None

    def bulk_upsert_index_nav_history(self, index_code, records):
        """批量写入指数历史净值。records 为 list of dict，每项含 nav_date, close, change_pct。"""
        try:
            code = str(index_code or '').strip()
            if not code or not records:
                return False
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT INTO index_nav_history (index_code, nav_date, close, change_pct, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(index_code, nav_date)
                DO UPDATE SET
                    close = excluded.close,
                    change_pct = excluded.change_pct,
                    updated_at = CURRENT_TIMESTAMP
            ''', [(code, r['nav_date'], float(r['close']), r.get('change_pct'), ) for r in records])
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to bulk upsert index nav history: {e}")
            return False

    def get_index_nav_history_range(self, index_code, start_date=None, end_date=None):
        """按日期区间读取指数净值，返回 {nav_date: close}。"""
        try:
            code = str(index_code or '').strip()
            if not code:
                return {}
            conn = self.get_connection()
            cursor = conn.cursor()
            sql = 'SELECT nav_date, close FROM index_nav_history WHERE index_code = ?'
            params = [code]
            if start_date:
                sql += ' AND nav_date >= ?'
                params.append(str(start_date).strip())
            if end_date:
                sql += ' AND nav_date <= ?'
                params.append(str(end_date).strip())
            sql += ' ORDER BY nav_date ASC'
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            conn.close()
            return {row['nav_date']: float(row['close']) for row in rows}
        except Exception as e:
            logger.error(f"Failed to get index nav history range: {e}")
            return {}
