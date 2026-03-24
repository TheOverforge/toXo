"""Finance domain models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

CURRENCIES = ["₽", "$", "€", "£", "¥"]

ACCOUNT_TYPES = ["cash", "bank", "savings", "investment", "crypto"]

TX_TYPES = ["income", "expense", "transfer"]

BUDGET_PERIODS = ["week", "month", "year"]


@dataclass
class FinAccount:
    id: int
    name: str
    type: str           # cash / bank / savings / investment / crypto
    balance: float
    currency: str       # ₽ $ € £ ¥
    color: str          # hex color
    created_at: str


@dataclass
class FinCategory:
    id: int
    name: str
    type: str           # 'income' or 'expense'
    color: str
    icon: str           # emoji
    created_at: str


@dataclass
class Transaction:
    id: int
    type: str           # income / expense / transfer
    amount: float
    currency: str
    category_id: Optional[int]
    account_id: Optional[int]
    date: str           # YYYY-MM-DD
    title: str
    note: str
    tags: str           # comma-separated
    is_recurring: int   # 0 or 1
    recurring_rule: Optional[str]   # daily / weekly / monthly
    created_at: str
    # Virtual fields populated by JOIN queries:
    category_name: str = ""
    category_color: str = ""
    category_icon: str = ""
    account_name: str = ""
    account_color: str = ""


@dataclass
class Budget:
    id: int
    category_id: int
    limit_amount: float
    period: str         # week / month / year
    created_at: str
    # Virtual:
    category_name: str = ""
    category_color: str = ""
    category_icon: str = ""
    spent: float = 0.0


@dataclass
class Goal:
    id: int
    name: str
    target_amount: float
    current_amount: float
    deadline: Optional[str]     # YYYY-MM-DD or None
    color: str
    currency: str
    created_at: str

    @property
    def progress_pct(self) -> int:
        if self.target_amount <= 0:
            return 0
        return min(100, int(self.current_amount / self.target_amount * 100))

    @property
    def remaining(self) -> float:
        return max(0.0, self.target_amount - self.current_amount)
