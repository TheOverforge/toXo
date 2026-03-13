"""Finance database mixin — tables, CRUD, aggregate queries, mock seed."""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from entities.finance.model import FinAccount, FinCategory, Transaction, Budget, Goal


_ACCOUNT_COLS  = "id, name, type, balance, currency, color, created_at"
_CATEGORY_COLS = "id, name, type, color, icon, created_at"
_TX_COLS       = ("id, type, amount, currency, category_id, account_id, "
                  "date, title, note, tags, is_recurring, recurring_rule, created_at")
_BUDGET_COLS   = "id, category_id, limit_amount, period, created_at"
_GOAL_COLS     = "id, name, target_amount, current_amount, deadline, color, currency, created_at"


def _row_to_account(r) -> FinAccount:
    return FinAccount(*r)


def _row_to_category(r) -> FinCategory:
    return FinCategory(*r)


def _row_to_tx(r) -> Transaction:
    return Transaction(*r)


def _row_to_budget(r) -> Budget:
    return Budget(*r)


def _row_to_goal(r) -> Goal:
    return Goal(*r)


class FinanceDbMixin:
    """Mixin for all Finance-related DB operations.
    Expects self._con (sqlite3.Connection) from the base Database class.
    """

    # ── Schema ────────────────────────────────────────────────────────────────

    def _init_finance_tables(self):
        c = self._con
        c.execute("""
            CREATE TABLE IF NOT EXISTS fin_accounts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                type       TEXT NOT NULL DEFAULT 'bank',
                balance    REAL NOT NULL DEFAULT 0.0,
                currency   TEXT NOT NULL DEFAULT '₽',
                color      TEXT NOT NULL DEFAULT '#0a84ff',
                created_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS fin_categories (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                type       TEXT NOT NULL DEFAULT 'expense',
                color      TEXT NOT NULL DEFAULT '#0a84ff',
                icon       TEXT NOT NULL DEFAULT '●',
                created_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS fin_transactions (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                type           TEXT NOT NULL DEFAULT 'expense',
                amount         REAL NOT NULL DEFAULT 0.0,
                currency       TEXT NOT NULL DEFAULT '₽',
                category_id    INTEGER,
                account_id     INTEGER,
                date           TEXT NOT NULL,
                title          TEXT NOT NULL DEFAULT '',
                note           TEXT NOT NULL DEFAULT '',
                tags           TEXT NOT NULL DEFAULT '',
                is_recurring   INTEGER NOT NULL DEFAULT 0,
                recurring_rule TEXT,
                created_at     TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS fin_budgets (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id  INTEGER NOT NULL,
                limit_amount REAL NOT NULL DEFAULT 0.0,
                period       TEXT NOT NULL DEFAULT 'month',
                created_at   TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS fin_goals (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           TEXT NOT NULL,
                target_amount  REAL NOT NULL DEFAULT 0.0,
                current_amount REAL NOT NULL DEFAULT 0.0,
                deadline       TEXT,
                color          TEXT NOT NULL DEFAULT '#bf5af2',
                currency       TEXT NOT NULL DEFAULT '₽',
                created_at     TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_fin_tx_date ON fin_transactions(date)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_fin_tx_type ON fin_transactions(type)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_fin_tx_cat  ON fin_transactions(category_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_fin_tx_acc  ON fin_transactions(account_id)")
        c.commit()

    # ── Accounts ──────────────────────────────────────────────────────────────

    def add_account(self, name: str, type_: str, balance: float,
                    currency: str, color: str) -> FinAccount:
        now = self._now_iso()
        cur = self._con.execute(
            "INSERT INTO fin_accounts(name,type,balance,currency,color,created_at) "
            "VALUES(?,?,?,?,?,?)",
            (name, type_, balance, currency, color, now)
        )
        self._con.commit()
        return self.get_account(cur.lastrowid)

    def list_accounts(self) -> list[FinAccount]:
        rows = self._con.execute(
            f"SELECT {_ACCOUNT_COLS} FROM fin_accounts ORDER BY created_at"
        ).fetchall()
        return [_row_to_account(r) for r in rows]

    def get_account(self, id_: int) -> Optional[FinAccount]:
        r = self._con.execute(
            f"SELECT {_ACCOUNT_COLS} FROM fin_accounts WHERE id=?", (id_,)
        ).fetchone()
        return _row_to_account(r) if r else None

    def update_account(self, id_: int, **kw):
        allowed = {"name", "type", "balance", "currency", "color"}
        fields = {k: v for k, v in kw.items() if k in allowed}
        if not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        self._con.execute(
            f"UPDATE fin_accounts SET {sets} WHERE id=?",
            (*fields.values(), id_)
        )
        self._con.commit()

    def delete_account(self, id_: int):
        self._con.execute("DELETE FROM fin_accounts WHERE id=?", (id_,))
        self._con.commit()

    # ── Categories ────────────────────────────────────────────────────────────

    def add_fin_category(self, name: str, type_: str, color: str, icon: str) -> FinCategory:
        now = self._now_iso()
        cur = self._con.execute(
            "INSERT INTO fin_categories(name,type,color,icon,created_at) VALUES(?,?,?,?,?)",
            (name, type_, color, icon, now)
        )
        self._con.commit()
        row = self._con.execute(
            f"SELECT {_CATEGORY_COLS} FROM fin_categories WHERE id=?", (cur.lastrowid,)
        ).fetchone()
        return _row_to_category(row)

    def list_fin_categories(self, type_: Optional[str] = None) -> list[FinCategory]:
        if type_:
            rows = self._con.execute(
                f"SELECT {_CATEGORY_COLS} FROM fin_categories WHERE type=? ORDER BY id",
                (type_,)
            ).fetchall()
        else:
            rows = self._con.execute(
                f"SELECT {_CATEGORY_COLS} FROM fin_categories ORDER BY type, id"
            ).fetchall()
        return [_row_to_category(r) for r in rows]

    def update_fin_category(self, id_: int, **kw):
        allowed = {"name", "color", "icon"}
        fields = {k: v for k, v in kw.items() if k in allowed}
        if not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        self._con.execute(
            f"UPDATE fin_categories SET {sets} WHERE id=?",
            (*fields.values(), id_)
        )
        self._con.commit()

    def delete_fin_category(self, id_: int):
        self._con.execute("DELETE FROM fin_categories WHERE id=?", (id_,))
        self._con.commit()

    # ── Transactions ──────────────────────────────────────────────────────────

    def add_transaction(self, type_: str, amount: float, currency: str,
                        category_id: Optional[int], account_id: Optional[int],
                        date: str, title: str = "", note: str = "",
                        tags: str = "", is_recurring: int = 0,
                        recurring_rule: Optional[str] = None) -> Transaction:
        now = self._now_iso()
        cur = self._con.execute(
            "INSERT INTO fin_transactions"
            "(type,amount,currency,category_id,account_id,date,title,note,tags,"
            "is_recurring,recurring_rule,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (type_, amount, currency, category_id, account_id, date,
             title, note, tags, is_recurring, recurring_rule, now)
        )
        self._con.commit()
        return self.get_transaction(cur.lastrowid)

    def get_transaction(self, id_: int) -> Optional[Transaction]:
        r = self._con.execute(
            f"SELECT {_TX_COLS} FROM fin_transactions WHERE id=?", (id_,)
        ).fetchone()
        if not r:
            return None
        tx = _row_to_tx(r)
        self._fill_tx_virtuals([tx])
        return tx

    def list_transactions(self, since: Optional[str] = None, until: Optional[str] = None,
                          tx_type: Optional[str] = None, account_id: Optional[int] = None,
                          category_id: Optional[int] = None,
                          search: Optional[str] = None,
                          limit: int = 500) -> list[Transaction]:
        q = f"SELECT {_TX_COLS} FROM fin_transactions WHERE 1=1"
        p: list = []
        if since:
            q += " AND date >= ?"; p.append(since)
        if until:
            q += " AND date <= ?"; p.append(until)
        if tx_type:
            q += " AND type = ?"; p.append(tx_type)
        if account_id:
            q += " AND account_id = ?"; p.append(account_id)
        if category_id:
            q += " AND category_id = ?"; p.append(category_id)
        if search:
            q += " AND (title LIKE ? OR note LIKE ?)"; p.extend([f"%{search}%", f"%{search}%"])
        q += " ORDER BY date DESC, id DESC"
        q += f" LIMIT {limit}"
        rows = self._con.execute(q, p).fetchall()
        txs = [_row_to_tx(r) for r in rows]
        self._fill_tx_virtuals(txs)
        return txs

    def _fill_tx_virtuals(self, txs: list[Transaction]):
        """Enrich transactions with category/account names and colors."""
        cats = {c.id: c for c in self.list_fin_categories()}
        accs = {a.id: a for a in self.list_accounts()}
        for tx in txs:
            if tx.category_id and tx.category_id in cats:
                c = cats[tx.category_id]
                tx.category_name  = c.name
                tx.category_color = c.color
                tx.category_icon  = c.icon
            if tx.account_id and tx.account_id in accs:
                a = accs[tx.account_id]
                tx.account_name  = a.name
                tx.account_color = a.color

    def update_transaction(self, id_: int, **kw):
        allowed = {"type", "amount", "currency", "category_id", "account_id",
                   "date", "title", "note", "tags", "is_recurring", "recurring_rule"}
        fields = {k: v for k, v in kw.items() if k in allowed}
        if not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        self._con.execute(
            f"UPDATE fin_transactions SET {sets} WHERE id=?",
            (*fields.values(), id_)
        )
        self._con.commit()

    def delete_transaction(self, id_: int):
        self._con.execute("DELETE FROM fin_transactions WHERE id=?", (id_,))
        self._con.commit()

    # ── Budgets ───────────────────────────────────────────────────────────────

    def add_budget(self, category_id: int, limit_amount: float, period: str) -> Budget:
        now = self._now_iso()
        cur = self._con.execute(
            "INSERT INTO fin_budgets(category_id,limit_amount,period,created_at) VALUES(?,?,?,?)",
            (category_id, limit_amount, period, now)
        )
        self._con.commit()
        row = self._con.execute(
            f"SELECT {_BUDGET_COLS} FROM fin_budgets WHERE id=?", (cur.lastrowid,)
        ).fetchone()
        return _row_to_budget(row)

    def list_budgets(self) -> list[Budget]:
        rows = self._con.execute(
            f"SELECT {_BUDGET_COLS} FROM fin_budgets ORDER BY id"
        ).fetchall()
        budgets = [_row_to_budget(r) for r in rows]
        cats = {c.id: c for c in self.list_fin_categories()}
        for b in budgets:
            if b.category_id in cats:
                c = cats[b.category_id]
                b.category_name  = c.name
                b.category_color = c.color
                b.category_icon  = c.icon
        return budgets

    def update_budget(self, id_: int, **kw):
        allowed = {"limit_amount", "period", "category_id"}
        fields = {k: v for k, v in kw.items() if k in allowed}
        if not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        self._con.execute(
            f"UPDATE fin_budgets SET {sets} WHERE id=?",
            (*fields.values(), id_)
        )
        self._con.commit()

    def delete_budget(self, id_: int):
        self._con.execute("DELETE FROM fin_budgets WHERE id=?", (id_,))
        self._con.commit()

    def fin_budget_spent(self, category_id: int, since: str, until: str) -> float:
        r = self._con.execute(
            "SELECT COALESCE(SUM(amount),0) FROM fin_transactions "
            "WHERE type='expense' AND category_id=? AND date>=? AND date<=?",
            (category_id, since, until)
        ).fetchone()
        return float(r[0]) if r else 0.0

    # ── Goals ─────────────────────────────────────────────────────────────────

    def add_goal(self, name: str, target_amount: float, current_amount: float,
                 currency: str, color: str, deadline: Optional[str] = None) -> Goal:
        now = self._now_iso()
        cur = self._con.execute(
            "INSERT INTO fin_goals(name,target_amount,current_amount,deadline,color,currency,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (name, target_amount, current_amount, deadline, color, currency, now)
        )
        self._con.commit()
        row = self._con.execute(
            f"SELECT {_GOAL_COLS} FROM fin_goals WHERE id=?", (cur.lastrowid,)
        ).fetchone()
        return _row_to_goal(row)

    def list_goals(self) -> list[Goal]:
        rows = self._con.execute(
            f"SELECT {_GOAL_COLS} FROM fin_goals ORDER BY created_at"
        ).fetchall()
        return [_row_to_goal(r) for r in rows]

    def get_goal(self, id_: int) -> Optional[Goal]:
        r = self._con.execute(
            f"SELECT {_GOAL_COLS} FROM fin_goals WHERE id=?", (id_,)
        ).fetchone()
        return _row_to_goal(r) if r else None

    def update_goal(self, id_: int, **kw):
        allowed = {"name", "target_amount", "current_amount", "deadline", "color", "currency"}
        fields = {k: v for k, v in kw.items() if k in allowed}
        if not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        self._con.execute(
            f"UPDATE fin_goals SET {sets} WHERE id=?",
            (*fields.values(), id_)
        )
        self._con.commit()

    def delete_goal(self, id_: int):
        self._con.execute("DELETE FROM fin_goals WHERE id=?", (id_,))
        self._con.commit()

    def add_to_goal(self, id_: int, amount: float):
        self._con.execute(
            "UPDATE fin_goals SET current_amount = MIN(target_amount, current_amount+?) WHERE id=?",
            (amount, id_)
        )
        self._con.commit()

    # ── Analytics queries ─────────────────────────────────────────────────────

    def fin_total_balance(self) -> dict[str, float]:
        """Return {currency: total_balance} across all accounts."""
        rows = self._con.execute(
            "SELECT currency, SUM(balance) FROM fin_accounts GROUP BY currency"
        ).fetchall()
        return {r[0]: float(r[1]) for r in rows}

    def fin_summary(self, since: str, until: str) -> dict:
        """Return income, expenses, net, avg_per_day for date range."""
        inc = self._con.execute(
            "SELECT COALESCE(SUM(amount),0) FROM fin_transactions "
            "WHERE type='income' AND date>=? AND date<=?", (since, until)
        ).fetchone()[0]
        exp = self._con.execute(
            "SELECT COALESCE(SUM(amount),0) FROM fin_transactions "
            "WHERE type='expense' AND date>=? AND date<=?", (since, until)
        ).fetchone()[0]
        try:
            d0 = date.fromisoformat(since)
            d1 = date.fromisoformat(until)
            n_days = max(1, (d1 - d0).days + 1)
        except Exception:
            n_days = 30
        return {
            "income":    float(inc),
            "expenses":  float(exp),
            "net":       float(inc) - float(exp),
            "avg_per_day": float(exp) / n_days,
        }

    def fin_daily_flow(self, since: str, until: str) -> list[tuple]:
        """Return list of (date_str, income, expense) for each day in range."""
        rows = self._con.execute(
            """
            SELECT date,
                   COALESCE(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0) as inc,
                   COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) as exp
            FROM fin_transactions
            WHERE date >= ? AND date <= ?
            GROUP BY date
            ORDER BY date
            """,
            (since, until)
        ).fetchall()
        # Fill missing days with zeros
        try:
            d0 = date.fromisoformat(since)
            d1 = date.fromisoformat(until)
        except Exception:
            return [(r[0], float(r[1]), float(r[2])) for r in rows]
        row_map = {r[0]: (float(r[1]), float(r[2])) for r in rows}
        result = []
        cur = d0
        while cur <= d1:
            ds = cur.isoformat()
            inc, exp = row_map.get(ds, (0.0, 0.0))
            result.append((ds, inc, exp))
            cur += timedelta(days=1)
        return result

    def fin_expense_by_category(self, since: str, until: str) -> list[tuple]:
        """Return (cat_id, name, color, icon, total) sorted by total desc."""
        rows = self._con.execute(
            """
            SELECT t.category_id, c.name, c.color, c.icon,
                   COALESCE(SUM(t.amount), 0) as total
            FROM fin_transactions t
            LEFT JOIN fin_categories c ON c.id = t.category_id
            WHERE t.type='expense' AND t.date>=? AND t.date<=?
              AND t.category_id IS NOT NULL
            GROUP BY t.category_id
            ORDER BY total DESC
            """,
            (since, until)
        ).fetchall()
        return [(r[0], r[1] or "?", r[2] or "#98989d", r[3] or "●", float(r[4])) for r in rows]

    def fin_income_by_category(self, since: str, until: str) -> list[tuple]:
        """Return (cat_id, name, color, icon, total) sorted by total desc."""
        rows = self._con.execute(
            """
            SELECT t.category_id, c.name, c.color, c.icon,
                   COALESCE(SUM(t.amount), 0) as total
            FROM fin_transactions t
            LEFT JOIN fin_categories c ON c.id = t.category_id
            WHERE t.type='income' AND t.date>=? AND t.date<=?
              AND t.category_id IS NOT NULL
            GROUP BY t.category_id
            ORDER BY total DESC
            """,
            (since, until)
        ).fetchall()
        return [(r[0], r[1] or "?", r[2] or "#98989d", r[3] or "●", float(r[4])) for r in rows]

    def fin_cumulative_balance(self, since: str, until: str) -> list[tuple]:
        """Return (date_str, cumulative_net) from since to until."""
        rows = self._con.execute(
            """
            SELECT date,
                   SUM(CASE WHEN type='income'  THEN amount ELSE 0 END) -
                   SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as net
            FROM fin_transactions
            WHERE date >= ? AND date <= ?
            GROUP BY date
            ORDER BY date
            """,
            (since, until)
        ).fetchall()
        try:
            d0 = date.fromisoformat(since)
            d1 = date.fromisoformat(until)
        except Exception:
            cum = 0.0
            result = []
            for r in rows:
                cum += float(r[1])
                result.append((r[0], cum))
            return result
        row_map = {r[0]: float(r[1]) for r in rows}
        result = []
        cum = 0.0
        cur = d0
        while cur <= d1:
            ds = cur.isoformat()
            cum += row_map.get(ds, 0.0)
            result.append((ds, cum))
            cur += timedelta(days=1)
        return result

    # ── Mock seed ─────────────────────────────────────────────────────────────

    def _seed_finance_mock(self):
        """Populate DB with realistic demo data (90 days), language-aware."""
        try:
            from shared.i18n import current_language
            lang = current_language()
        except Exception:
            lang = "ru"

        rng = random.Random(42)
        now = self._now_iso()
        today = date.today()

        # ── Locale-specific strings ────────────────────────────────────────────
        if lang == "en":
            cur_sym = "$"
            acc_data = [
                ("Cash",        "cash",         940,  "$", "#30d158"),
                ("Main Card",   "bank",       1_382,  "$", "#0a84ff"),
                ("Savings",     "savings",      967,  "$", "#bf5af2"),
                ("Investments", "investment",   507,  "$", "#ff9f0a"),
            ]
            exp_cats_data = [
                ("Food",           "expense", "#ff9f0a", "🍕"),
                ("Transport",      "expense", "#0a84ff", "🚇"),
                ("Rent",           "expense", "#5e5ce6", "🏠"),
                ("Subscriptions",  "expense", "#bf5af2", "📱"),
                ("Health",         "expense", "#30d158", "💊"),
                ("Shopping",       "expense", "#ff453a", "🛍️"),
                ("Entertainment",  "expense", "#ff6b6b", "🎮"),
                ("Fitness",        "expense", "#32ade6", "🏋️"),
                ("Cafe",           "expense", "#ffd60a", "☕"),
                ("Other",          "expense", "#98989d", "📦"),
            ]
            inc_cats_data = [
                ("Salary",     "income", "#30d158", "💰"),
                ("Freelance",  "income", "#0a84ff", "💻"),
                ("Dividends",  "income", "#ff9f0a", "📈"),
                ("Other",      "income", "#98989d", "📥"),
            ]
            food_titles      = ["Walmart", "Whole Foods", "Trader Joe's", "Costco", "Target", "Groceries"]
            cafe_titles      = ["Coffee", "Business lunch", "Dinner with friends", "Starbucks", "Sushi", "Pizza"]
            transport_titles = ["Subway", "Uber", "Taxi", "Bus", "Lyft", "Bike share"]
            shop_titles      = ["Amazon", "eBay", "Clothing", "Books", "Electronics", "IKEA"]
            entertain_titles = ["Cinema", "Concert", "Bowling", "Escape room", "Theater", "Exhibition"]
            health_titles    = ["Pharmacy", "Doctor", "Lab tests", "Dentist", "Optician"]
            freelance_titles = ["Project A", "Project B", "Client website",
                                "Consulting", "Design order", "Backend dev"]
            sal_title   = "Salary"
            adv_title   = "Advance"
            div_title   = "Dividends"
            rent_title  = "Apartment rent"
            gym_title   = "Gym membership"
            misc_title  = "Miscellaneous"
            sal_full    = 800
            sal_adv     = 310
            div_choices = [36, 46, 61]
            rent_amt    = 1_200
            gym_amt     = 31
            food_lo, food_hi   = 4, 25
            food_big_lo, food_big_hi = 15, 65
            cafe_lo, cafe_hi   = 4, 28
            trans_lo, trans_hi = 2, 18
            shop_lo, shop_hi   = 10, 120
            ent_lo, ent_hi     = 12, 60
            hlth_lo, hlth_hi   = 8, 80
            misc_lo, misc_hi   = 3, 15
            frl_choices = [90, 140, 200, 280, 390]
            budgets_cfg = [
                ("Food",          200, "month"),
                ("Cafe",          130, "month"),
                ("Transport",      70, "month"),
                ("Entertainment",  90, "month"),
                ("Shopping",      170, "month"),
                ("Health",         60, "month"),
            ]
            goals_cfg = [
                ("New MacBook",      2_000,   600, "2025-12-31", "#0a84ff", "$"),
                ("Trip to Asia",     1_700,   970, "2025-09-01", "#30d158", "$"),
                ("Car",             10_000, 2_300, None,         "#ff9f0a", "$"),
                ("Emergency fund",   3_300,   967, None,         "#bf5af2", "$"),
            ]
        else:
            cur_sym = "₽"
            acc_data = [
                ("Наличные",       "cash",       8_450,  "₽", "#30d158"),
                ("Основная карта", "bank",      124_380, "₽", "#0a84ff"),
                ("Накопления",     "savings",    87_000, "₽", "#bf5af2"),
                ("Инвестиции",     "investment", 45_600, "₽", "#ff9f0a"),
            ]
            exp_cats_data = [
                ("Еда",              "expense", "#ff9f0a", "🍕"),
                ("Транспорт",        "expense", "#0a84ff", "🚇"),
                ("Аренда",           "expense", "#5e5ce6", "🏠"),
                ("Подписки",         "expense", "#bf5af2", "📱"),
                ("Здоровье",         "expense", "#30d158", "💊"),
                ("Шоппинг",          "expense", "#ff453a", "🛍️"),
                ("Развлечения",      "expense", "#ff6b6b", "🎮"),
                ("Фитнес",           "expense", "#32ade6", "🏋️"),
                ("Кафе",             "expense", "#ffd60a", "☕"),
                ("Прочее",           "expense", "#98989d", "📦"),
            ]
            inc_cats_data = [
                ("Зарплата",  "income", "#30d158", "💰"),
                ("Фриланс",   "income", "#0a84ff", "💻"),
                ("Дивиденды", "income", "#ff9f0a", "📈"),
                ("Прочее",    "income", "#98989d", "📥"),
            ]
            food_titles      = ["Пятёрочка", "Магнит", "ВкусВилл", "Перекрёсток", "Лента", "Продукты"]
            cafe_titles      = ["Кофе", "Бизнес-ланч", "Ужин с друзьями", "Starbucks", "Суши", "Пицца"]
            transport_titles = ["Метро", "Яндекс Go", "Такси", "Каршеринг", "Автобус", "Самокат"]
            shop_titles      = ["Wildberries", "Ozon", "Одежда", "Книги", "Электроника", "ИКЕА"]
            entertain_titles = ["Кино", "Концерт", "Боулинг", "Квест", "Театр", "Выставка"]
            health_titles    = ["Аптека", "Врач", "Анализы", "Стоматолог", "Оптика"]
            freelance_titles = ["Проект А", "Проект Б", "Сайт для клиента",
                                "Консультация", "Дизайн-заказ", "Backend-разработка"]
            sal_title   = "Зарплата"
            adv_title   = "Аванс"
            div_title   = "Дивиденды"
            rent_title  = "Аренда квартиры"
            gym_title   = "Абонемент в зал"
            misc_title  = "Разное"
            sal_full    = 72_000
            sal_adv     = 28_000
            div_choices = [3_200, 4_100, 5_500]
            rent_amt    = 38_000
            gym_amt     = 2_800
            food_lo, food_hi   = 80,  380
            food_big_lo, food_big_hi = 350, 2_200
            cafe_lo, cafe_hi   = 150, 2_200
            trans_lo, trans_hi = 55,  650
            shop_lo, shop_hi   = 500, 8_500
            ent_lo, ent_hi     = 400, 3_500
            hlth_lo, hlth_hi   = 300, 5_000
            misc_lo, misc_hi   = 100, 900
            frl_choices = [8_000, 12_000, 18_000, 25_000, 35_000]
            budgets_cfg = [
                ("Еда",         18_000, "month"),
                ("Кафе",        12_000, "month"),
                ("Транспорт",    6_000, "month"),
                ("Развлечения",  8_000, "month"),
                ("Шоппинг",     15_000, "month"),
                ("Здоровье",     5_000, "month"),
            ]
            goals_cfg = [
                ("Новый MacBook",        180_000,  54_000, "2025-12-31", "#0a84ff", "₽"),
                ("Отпуск в Азии",        150_000,  87_500, "2025-09-01", "#30d158", "₽"),
                ("Машина",               900_000, 210_000, None,         "#ff9f0a", "₽"),
                ("Подушка безопасности", 300_000,  87_000, None,         "#bf5af2", "₽"),
            ]

        # ── Accounts ──────────────────────────────────────────────────────────
        for name, typ, bal, cur, col in acc_data:
            self._con.execute(
                "INSERT INTO fin_accounts(name,type,balance,currency,color,created_at) "
                "VALUES(?,?,?,?,?,?)", (name, typ, bal, cur, col, now)
            )
        self._con.commit()
        accs = self.list_accounts()
        acc_cash, acc_card, acc_savings, acc_invest = (
            accs[0].id, accs[1].id, accs[2].id, accs[3].id
        )

        # ── Categories ────────────────────────────────────────────────────────
        for name, typ, col, icon in exp_cats_data:
            self._con.execute(
                "INSERT INTO fin_categories(name,type,color,icon,created_at) VALUES(?,?,?,?,?)",
                (name, typ, col, icon, now)
            )
        for name, typ, col, icon in inc_cats_data:
            self._con.execute(
                "INSERT INTO fin_categories(name,type,color,icon,created_at) VALUES(?,?,?,?,?)",
                (name, typ, col, icon, now)
            )
        self._con.commit()

        cats  = self.list_fin_categories()
        exp_c = {c.name: c.id for c in cats if c.type == "expense"}
        inc_c = {c.name: c.id for c in cats if c.type == "income"}

        # Key aliases so transaction-building code is language-agnostic
        k_food  = exp_cats_data[0][0]
        k_trans = exp_cats_data[1][0]
        k_rent  = exp_cats_data[2][0]
        k_subs  = exp_cats_data[3][0]
        k_hlth  = exp_cats_data[4][0]
        k_shop  = exp_cats_data[5][0]
        k_ent   = exp_cats_data[6][0]
        k_gym   = exp_cats_data[7][0]
        k_cafe  = exp_cats_data[8][0]
        k_misc  = exp_cats_data[9][0]
        k_sal   = inc_cats_data[0][0]
        k_frl   = inc_cats_data[1][0]
        k_div   = inc_cats_data[2][0]

        # ── 90 days of transactions ───────────────────────────────────────────
        transactions = []

        for offset in range(90, 0, -1):
            d_obj   = today - timedelta(days=offset)
            d       = d_obj.isoformat()
            day_num = d_obj.day
            is_wend = d_obj.weekday() >= 5

            # Income
            if day_num == 1:
                transactions.append(("income", sal_full, cur_sym, inc_c[k_sal], acc_card, d, sal_title, "", ""))
            elif day_num == 15:
                transactions.append(("income", sal_adv, cur_sym, inc_c[k_sal], acc_card, d, adv_title, "", ""))
            if rng.random() < 0.028:
                transactions.append(("income", rng.choice(frl_choices), cur_sym,
                                     inc_c[k_frl], acc_card, d, rng.choice(freelance_titles), "", "freelance"))
            if day_num == 20:
                transactions.append(("income", rng.choice(div_choices), cur_sym,
                                     inc_c[k_div], acc_invest, d, div_title, "", ""))

            # Fixed monthly expenses
            if day_num == 5:
                transactions.append(("expense", rent_amt, cur_sym, exp_c[k_rent], acc_card, d, rent_title, "", ""))
            if day_num == 3:
                for sub, price in [("YouTube Premium", 4 if lang == "en" else 379),
                                   ("Spotify",         1 if lang == "en" else 299),
                                   ("iCloud 200GB",    3 if lang == "en" else 149),
                                   ("VPN",             2 if lang == "en" else 199)]:
                    transactions.append(("expense", price, cur_sym, exp_c[k_subs], acc_card, d, sub, "", "auto"))
            if day_num == 1:
                transactions.append(("expense", gym_amt, cur_sym, exp_c[k_gym], acc_card, d, gym_title, "", ""))

            # Variable daily
            if rng.random() < 0.78:
                amt = rng.uniform(food_big_lo, food_big_hi) if rng.random() < 0.25 else rng.uniform(food_lo, food_hi)
                transactions.append(("expense", amt, cur_sym, exp_c[k_food], acc_card, d, rng.choice(food_titles), "", ""))
            if rng.random() < (0.50 if not is_wend else 0.28):
                transactions.append(("expense", rng.uniform(cafe_lo, cafe_hi), cur_sym,
                                     exp_c[k_cafe], acc_card, d, rng.choice(cafe_titles), "", ""))
            if rng.random() < (0.72 if not is_wend else 0.22):
                transactions.append(("expense", rng.uniform(trans_lo, trans_hi), cur_sym,
                                     exp_c[k_trans], acc_card if rng.random() < 0.65 else acc_cash,
                                     d, rng.choice(transport_titles), "", ""))
            if rng.random() < 0.18:
                transactions.append(("expense", rng.uniform(shop_lo, shop_hi), cur_sym,
                                     exp_c[k_shop], acc_card, d, rng.choice(shop_titles), "", ""))
            if rng.random() < (0.32 if is_wend else 0.07):
                transactions.append(("expense", rng.uniform(ent_lo, ent_hi), cur_sym,
                                     exp_c[k_ent], acc_card, d, rng.choice(entertain_titles), "", ""))
            if rng.random() < 0.045:
                transactions.append(("expense", rng.uniform(hlth_lo, hlth_hi), cur_sym,
                                     exp_c[k_hlth], acc_card, d, rng.choice(health_titles), "", ""))
            if rng.random() < 0.06:
                transactions.append(("expense", rng.uniform(misc_lo, misc_hi), cur_sym,
                                     exp_c[k_misc], acc_cash, d, misc_title, "", ""))

        for tx in transactions:
            typ, amt, cur, cat_id, acc_id, d, title, note, tags = tx
            self._con.execute(
                "INSERT INTO fin_transactions"
                "(type,amount,currency,category_id,account_id,date,title,note,tags,"
                "is_recurring,recurring_rule,created_at) VALUES(?,?,?,?,?,?,?,?,?,0,NULL,?)",
                (typ, round(amt, 2), cur, cat_id, acc_id, d, title, note, tags, now)
            )
        self._con.commit()

        # ── Budgets ───────────────────────────────────────────────────────────
        for cat_name, limit, period in budgets_cfg:
            self._con.execute(
                "INSERT INTO fin_budgets(category_id,limit_amount,period,created_at) VALUES(?,?,?,?)",
                (exp_c[cat_name], limit, period, now)
            )

        # ── Goals ─────────────────────────────────────────────────────────────
        for name, target, current, deadline, color, cur in goals_cfg:
            self._con.execute(
                "INSERT INTO fin_goals(name,target_amount,current_amount,deadline,color,currency,created_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (name, target, current, deadline, color, cur, now)
            )
        self._con.commit()
