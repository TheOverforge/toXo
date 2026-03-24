"""Unit tests for FinanceService and period helpers against an in-memory DB."""
import pytest
from datetime import date

from shared.api.db.connection import Database
from entities.finance.service import FinanceService, period_range_for, _month_range, _year_range


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_svc() -> FinanceService:
    db = Database(path=":memory:")
    return FinanceService(db)


@pytest.fixture()
def svc():
    return _make_svc()


def _clear(svc: FinanceService):
    """Remove mock seed data so tests start from a clean slate."""
    for tbl in ("fin_transactions", "fin_budgets", "fin_goals", "fin_accounts", "fin_categories"):
        svc.db._con.execute(f"DELETE FROM {tbl}")
    svc.db._con.commit()


# ── period helpers ─────────────────────────────────────────────────────────────

class TestPeriodRangeFor:
    def test_7_days(self):
        since, until = period_range_for(7)
        today = date.today()
        assert until == today.isoformat()
        d_since = date.fromisoformat(since)
        assert (today - d_since).days == 6  # 7 days inclusive

    def test_30_days(self):
        since, until = period_range_for(30)
        today = date.today()
        assert (date.fromisoformat(until) - date.fromisoformat(since)).days == 29

    def test_0_sentinel_is_current_month(self):
        since, until = period_range_for(0)
        today = date.today()
        assert date.fromisoformat(since).day == 1
        assert date.fromisoformat(since).month == today.month
        assert until == today.isoformat()

    def test_minus1_sentinel_is_current_year(self):
        since, until = period_range_for(-1)
        today = date.today()
        d = date.fromisoformat(since)
        assert d.month == 1 and d.day == 1 and d.year == today.year

    def test_since_before_until(self):
        for days in (7, 30, 90, 0, -1):
            since, until = period_range_for(days)
            assert since <= until


# ── accounts ──────────────────────────────────────────────────────────────────

class TestAccounts:
    def test_add_account_returns_account(self, svc):
        _clear(svc)
        acc = svc.add_account("Cash", "cash", 5000.0, "₽", "#30d158")
        assert acc.id > 0
        assert acc.name == "Cash"
        assert acc.balance == pytest.approx(5000.0)
        assert acc.currency == "₽"

    def test_list_accounts_contains_added(self, svc):
        _clear(svc)
        svc.add_account("Savings", "savings", 10_000.0, "$", "#0a84ff")
        accounts = svc.list_accounts()
        assert any(a.name == "Savings" for a in accounts)

    def test_delete_account(self, svc):
        _clear(svc)
        acc = svc.add_account("Temp", "cash", 0, "₽", "#ff453a")
        svc.delete_account(acc.id)
        assert all(a.id != acc.id for a in svc.list_accounts())

    def test_update_account_balance(self, svc):
        _clear(svc)
        acc = svc.add_account("Card", "bank", 1000.0, "₽", "#0a84ff")
        svc.update_account(acc.id, balance=2500.0)
        updated = next(a for a in svc.list_accounts() if a.id == acc.id)
        assert updated.balance == pytest.approx(2500.0)


# ── categories ────────────────────────────────────────────────────────────────

class TestCategories:
    def test_add_and_list_category(self, svc):
        _clear(svc)
        cat = svc.add_category("Food", "expense", "#ff9f0a", "🍕")
        cats = svc.list_categories()
        assert any(c.id == cat.id for c in cats)

    def test_filter_by_type(self, svc):
        _clear(svc)
        svc.add_category("Salary", "income", "#30d158", "💰")
        svc.add_category("Food", "expense", "#ff9f0a", "🍕")
        inc = svc.list_categories(type_="income")
        assert all(c.type == "income" for c in inc)
        exp = svc.list_categories(type_="expense")
        assert all(c.type == "expense" for c in exp)


# ── transactions ──────────────────────────────────────────────────────────────

class TestTransactions:
    def test_add_transaction_increments_count(self, svc):
        _clear(svc)
        before = svc.transaction_count()
        cat = svc.add_category("Food", "expense", "#ff9f0a", "🍕")
        acc = svc.add_account("Cash", "cash", 5000, "₽", "#30d158")
        svc.add_transaction("expense", 500, "₽", cat.id, acc.id, "2026-03-01", "Lunch")
        assert svc.transaction_count() == before + 1

    def test_list_transactions_includes_added(self, svc):
        _clear(svc)
        cat = svc.add_category("Food", "expense", "#ff9f0a", "🍕")
        acc = svc.add_account("Cash", "cash", 5000, "₽", "#30d158")
        svc.add_transaction("expense", 750, "₽", cat.id, acc.id, "2026-03-01", "Dinner")
        txs = svc.list_transactions(days=30)
        assert any(tx.title == "Dinner" for tx in txs)

    def test_delete_transaction(self, svc):
        _clear(svc)
        cat = svc.add_category("Food", "expense", "#ff9f0a", "🍕")
        acc = svc.add_account("Cash", "cash", 5000, "₽", "#30d158")
        tx = svc.add_transaction("expense", 200, "₽", cat.id, acc.id, "2026-03-01")
        svc.delete_transaction(tx.id)
        txs = svc.list_transactions(days=30)
        assert all(t.id != tx.id for t in txs)

    def test_recent_transactions_limit(self, svc):
        _clear(svc)
        cat = svc.add_category("Misc", "expense", "#888888", "📦")
        acc = svc.add_account("Cash", "cash", 10_000, "₽", "#30d158")
        for i in range(15):
            svc.add_transaction("expense", 10 * i, "₽", cat.id, acc.id, "2026-03-01", f"tx{i}")
        recent = svc.recent_transactions(limit=8)
        assert len(recent) == 8


# ── budgets ───────────────────────────────────────────────────────────────────

class TestBudgets:
    def test_add_and_list_budget(self, svc):
        _clear(svc)
        cat = svc.add_category("Food", "expense", "#ff9f0a", "🍕")
        b = svc.add_budget(cat.id, 15_000.0, "month")
        budgets = svc.list_budgets()
        assert any(bud.id == b.id for bud in budgets)
        assert b.limit_amount == pytest.approx(15_000.0)

    def test_delete_budget(self, svc):
        _clear(svc)
        cat = svc.add_category("Food", "expense", "#ff9f0a", "🍕")
        b = svc.add_budget(cat.id, 5_000.0, "month")
        svc.delete_budget(b.id)
        assert all(bud.id != b.id for bud in svc.list_budgets())

    def test_budget_status_spent(self, svc):
        _clear(svc)
        cat = svc.add_category("Food", "expense", "#ff9f0a", "🍕")
        acc = svc.add_account("Cash", "cash", 10_000, "₽", "#30d158")
        svc.add_budget(cat.id, 15_000.0, "month")
        # Add a transaction in current month
        today = date.today().isoformat()
        svc.add_transaction("expense", 3_000, "₽", cat.id, acc.id, today, "Groceries")
        statuses = svc.budget_status(days=30)
        b_status = next((b for b in statuses if b.category_id == cat.id), None)
        assert b_status is not None
        assert b_status.spent == pytest.approx(3_000.0)


# ── goals ─────────────────────────────────────────────────────────────────────

class TestGoals:
    def test_add_and_list_goal(self, svc):
        _clear(svc)
        g = svc.add_goal("New monitor", 45_000, 18_000, "₽", "#bf5af2")
        goals = svc.list_goals()
        assert any(gl.id == g.id for gl in goals)

    def test_goal_progress_on_retrieved(self, svc):
        _clear(svc)
        g = svc.add_goal("Trip", 120_000, 60_000, "₽", "#0a84ff")
        found = next(gl for gl in svc.list_goals() if gl.id == g.id)
        assert found.progress_pct == 50

    def test_update_goal(self, svc):
        _clear(svc)
        g = svc.add_goal("Car", 500_000, 0, "₽", "#ff9f0a")
        svc.update_goal(g.id, current_amount=100_000)
        found = next(gl for gl in svc.list_goals() if gl.id == g.id)
        assert found.current_amount == pytest.approx(100_000.0)

    def test_delete_goal(self, svc):
        _clear(svc)
        g = svc.add_goal("Bike", 30_000, 5_000, "₽", "#30d158")
        svc.delete_goal(g.id)
        assert all(gl.id != g.id for gl in svc.list_goals())
