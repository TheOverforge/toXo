"""FinanceService — business-logic wrapper around FinanceDbMixin."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from entities.finance.model import FinAccount, FinCategory, Transaction, Budget, Goal


def _period_range(days: int) -> tuple[str, str]:
    """Return (since YYYY-MM-DD, until YYYY-MM-DD) for last N days ending today."""
    today = date.today()
    since = today - timedelta(days=days - 1)
    return since.isoformat(), today.isoformat()


def _month_range() -> tuple[str, str]:
    today = date.today()
    since = today.replace(day=1)
    return since.isoformat(), today.isoformat()


def _year_range() -> tuple[str, str]:
    today = date.today()
    since = today.replace(month=1, day=1)
    return since.isoformat(), today.isoformat()


def period_range_for(days: int) -> tuple[str, str]:
    """Public helper: convert days constant → (since, until)."""
    if days == 0:     # month mode sentinel
        return _month_range()
    elif days == -1:  # year mode sentinel
        return _year_range()
    return _period_range(days)


class FinanceService:
    """Thin service layer over FinanceDbMixin with period helpers."""

    def __init__(self, db):
        self.db = db

    # ── Summary helpers ───────────────────────────────────────────────────────

    def summary(self, days: int) -> dict:
        since, until = period_range_for(days)
        return self.db.fin_summary(since, until)

    def daily_flow(self, days: int) -> list:
        since, until = period_range_for(days)
        return self.db.fin_daily_flow(since, until)

    def expense_by_category(self, days: int) -> list:
        since, until = period_range_for(days)
        return self.db.fin_expense_by_category(since, until)

    def income_by_category(self, days: int) -> list:
        since, until = period_range_for(days)
        return self.db.fin_income_by_category(since, until)

    def cumulative_balance(self, days: int) -> list:
        since, until = period_range_for(days)
        return self.db.fin_cumulative_balance(since, until)

    def total_balance(self) -> dict:
        return self.db.fin_total_balance()

    def budget_status(self, days: int) -> list[Budget]:
        """Return budgets with .spent field populated for current month."""
        since, until = _month_range()
        budgets = self.db.list_budgets()
        for b in budgets:
            b.spent = self.db.fin_budget_spent(b.category_id, since, until)
        return budgets

    def recent_transactions(self, limit: int = 8) -> list[Transaction]:
        return self.db.list_transactions(limit=limit)

    def transaction_count(self) -> int:
        """Return total number of transactions in the database."""
        return self.db._con.execute("SELECT COUNT(*) FROM fin_transactions").fetchone()[0]

    def load_demo_data(self) -> None:
        """Clear all finance data and re-seed mock demo dataset."""
        for tbl in ("fin_transactions", "fin_budgets", "fin_goals", "fin_accounts", "fin_categories"):
            self.db._con.execute(f"DELETE FROM {tbl}")
        self.db._con.commit()
        self.db._seed_finance_mock()

    # ── CRUD proxies ──────────────────────────────────────────────────────────

    # Accounts
    def list_accounts(self) -> list[FinAccount]:
        return self.db.list_accounts()

    def add_account(self, name, type_, balance, currency, color) -> FinAccount:
        return self.db.add_account(name, type_, balance, currency, color)

    def update_account(self, id_, **kw):
        self.db.update_account(id_, **kw)

    def delete_account(self, id_):
        self.db.delete_account(id_)

    # Categories
    def list_categories(self, type_: Optional[str] = None) -> list[FinCategory]:
        return self.db.list_fin_categories(type_)

    def add_category(self, name, type_, color, icon) -> FinCategory:
        return self.db.add_fin_category(name, type_, color, icon)

    # Transactions
    def list_transactions(self, days: int = 30, tx_type: Optional[str] = None,
                          search: Optional[str] = None, limit: int = 500) -> list[Transaction]:
        since, until = period_range_for(days)
        return self.db.list_transactions(since=since, until=until, tx_type=tx_type,
                                         search=search, limit=limit)

    def add_transaction(self, type_, amount, currency, category_id, account_id,
                        date, title="", note="") -> Transaction:
        return self.db.add_transaction(type_, amount, currency, category_id,
                                       account_id, date, title, note)

    def delete_transaction(self, id_):
        self.db.delete_transaction(id_)

    # Budgets
    def list_budgets(self) -> list[Budget]:
        return self.db.list_budgets()

    def add_budget(self, category_id, limit_amount, period) -> Budget:
        return self.db.add_budget(category_id, limit_amount, period)

    def delete_budget(self, id_):
        self.db.delete_budget(id_)

    # Goals
    def list_goals(self) -> list[Goal]:
        return self.db.list_goals()

    def add_goal(self, name, target_amount, current_amount, currency, color,
                 deadline=None) -> Goal:
        return self.db.add_goal(name, target_amount, current_amount, currency, color, deadline)

    def update_goal(self, id_, **kw):
        self.db.update_goal(id_, **kw)

    def delete_goal(self, id_):
        self.db.delete_goal(id_)
