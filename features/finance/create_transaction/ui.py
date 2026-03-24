"""Finance dialogs — AddTransaction, AddAccount, AddBudget, AddGoal."""
from __future__ import annotations

from datetime import date

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QLineEdit, QComboBox,
    QDoubleSpinBox, QDateEdit, QColorDialog, QTextEdit,
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor

from entities.finance.model import CURRENCIES, ACCOUNT_TYPES, TX_TYPES, BUDGET_PERIODS
from shared.i18n import tr


# ── Shared helpers ──────────────────────────────────────────────────────────

_INPUT_SS = """
    QLineEdit, QComboBox, QDoubleSpinBox, QDateEdit, QTextEdit {
        background: rgba(255,255,255,0.07);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 8px;
        color: #f5f5f7;
        padding: 6px 10px;
        font-size: 14px;
    }
    QComboBox::drop-down { border: none; width: 24px; }
    QComboBox QAbstractItemView {
        background: #1c1c1e;
        border: 1px solid rgba(255,255,255,0.15);
        color: #f5f5f7;
        selection-background-color: rgba(10,132,255,0.35);
    }
    QPushButton#OkBtn {
        background: #0a84ff;
        border: none; border-radius: 8px;
        color: #fff; font-size: 14px; font-weight: 600;
        padding: 8px 24px;
    }
    QPushButton#OkBtn:hover { background: #1a8fff; }
    QPushButton#CancelBtn {
        background: rgba(255,255,255,0.07);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 8px;
        color: #f5f5f7; font-size: 14px;
        padding: 8px 20px;
    }
    QPushButton#CancelBtn:hover { background: rgba(255,255,255,0.12); }
    QLabel { color: #98989d; font-size: 13px; }
"""

_ACCOUNT_TYPE_LABELS = {
    "cash": "💵 Наличные",
    "bank": "🏦 Банковская карта",
    "savings": "💰 Накопления",
    "investment": "📈 Инвестиции",
    "crypto": "₿ Криптовалюта",
}

_PERIOD_LABELS = {
    "week": tr("fin.period_week"),
    "month": tr("fin.period_month"),
    "year": tr("fin.period_year"),
}


def _make_base_dialog(title: str, parent=None) -> tuple[QDialog, QVBoxLayout, QFormLayout]:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setModal(True)
    dlg.setMinimumWidth(380)
    dlg.setStyleSheet("QDialog { background: #1c1c1e; }" + _INPUT_SS)

    outer = QVBoxLayout(dlg)
    outer.setSpacing(16)
    outer.setContentsMargins(20, 20, 20, 20)

    form = QFormLayout()
    form.setSpacing(10)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
    outer.addLayout(form)

    return dlg, outer, form


def _add_buttons(outer: QVBoxLayout, dlg: QDialog) -> None:
    row = QHBoxLayout()
    row.setSpacing(10)
    btn_cancel = QPushButton(tr("fin.dlg_cancel"))
    btn_cancel.setObjectName("CancelBtn")
    btn_ok = QPushButton(tr("fin.dlg_ok"))
    btn_ok.setObjectName("OkBtn")
    btn_cancel.clicked.connect(dlg.reject)
    btn_ok.clicked.connect(dlg.accept)
    row.addStretch()
    row.addWidget(btn_cancel)
    row.addWidget(btn_ok)
    outer.addLayout(row)


# ── AddTransactionDialog ─────────────────────────────────────────────────────

class AddTransactionDialog(QDialog):
    """Dialog for adding a new income / expense / transfer transaction."""

    def __init__(self, finance_svc, parent=None,
                 prefill_type: str = "", prefill_amount: float = 0.0):
        super().__init__(parent)
        self._svc = finance_svc
        self.setWindowTitle(tr("fin.dlg_add_tx"))
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setStyleSheet("QDialog { background: #1c1c1e; }" + _INPUT_SS)

        outer = QVBoxLayout(self)
        outer.setSpacing(14)
        outer.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        outer.addLayout(form)

        # Type
        self.combo_type = QComboBox()
        for t in TX_TYPES:
            label = tr(f"fin.type_{t}")
            self.combo_type.addItem(label, t)
        if prefill_type in TX_TYPES:
            self.combo_type.setCurrentIndex(TX_TYPES.index(prefill_type))
        form.addRow(tr("fin.dlg_type"), self.combo_type)

        # Amount
        self.spin_amount = QDoubleSpinBox()
        self.spin_amount.setRange(0.01, 10_000_000)
        self.spin_amount.setSingleStep(100)
        self.spin_amount.setDecimals(2)
        self.spin_amount.setValue(prefill_amount if prefill_amount > 0 else 1000.0)
        form.addRow(tr("fin.dlg_amount"), self.spin_amount)

        # Currency
        self.combo_currency = QComboBox()
        for c in CURRENCIES:
            self.combo_currency.addItem(c)
        form.addRow(tr("fin.dlg_currency"), self.combo_currency)

        # Category (dynamic, depends on type)
        self.combo_cat = QComboBox()
        form.addRow(tr("fin.dlg_category"), self.combo_cat)

        # Account
        self.combo_acc = QComboBox()
        accounts = finance_svc.list_accounts()
        for a in accounts:
            self.combo_acc.addItem(f"{a.name} ({a.currency})", a.id)
        form.addRow(tr("fin.dlg_account"), self.combo_acc)

        # Date
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        form.addRow(tr("fin.dlg_date"), self.date_edit)

        # Title
        self.edit_title = QLineEdit()
        self.edit_title.setPlaceholderText(tr("fin.dlg_title_hint"))
        form.addRow(tr("fin.dlg_title"), self.edit_title)

        # Note
        self.edit_note = QTextEdit()
        self.edit_note.setPlaceholderText(tr("fin.dlg_note_hint"))
        self.edit_note.setFixedHeight(60)
        form.addRow(tr("fin.dlg_note"), self.edit_note)

        _add_buttons(outer, self)

        # Wire type change → rebuild categories
        self.combo_type.currentIndexChanged.connect(self._refresh_categories)
        self._refresh_categories()

    def _refresh_categories(self):
        tx_type = self.combo_type.currentData() or "expense"
        cat_type = "income" if tx_type == "income" else "expense"
        cats = self._svc.list_categories(cat_type)
        self.combo_cat.clear()
        self.combo_cat.addItem(tr("fin.no_category"), None)
        for c in cats:
            self.combo_cat.addItem(f"{c.icon} {c.name}", c.id)

    def result_data(self) -> dict | None:
        """Return dict ready to pass to FinanceService.add_transaction, or None."""
        tx_type = self.combo_type.currentData()
        amount = self.spin_amount.value()
        currency = self.combo_currency.currentText()
        cat_id = self.combo_cat.currentData()
        acc_id = self.combo_acc.currentData()
        dt = self.date_edit.date().toString("yyyy-MM-dd")
        title = self.edit_title.text().strip()
        note = self.edit_note.toPlainText().strip()
        return dict(type_=tx_type, amount=amount, currency=currency,
                    category_id=cat_id, account_id=acc_id,
                    date=dt, title=title, note=note)


# ── AddAccountDialog ─────────────────────────────────────────────────────────

class AddAccountDialog(QDialog):
    """Dialog for adding a new financial account."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("fin.dlg_add_account"))
        self.setModal(True)
        self.setMinimumWidth(380)
        self.setStyleSheet("QDialog { background: #1c1c1e; }" + _INPUT_SS)
        self._color = "#0a84ff"

        outer = QVBoxLayout(self)
        outer.setSpacing(14)
        outer.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        outer.addLayout(form)

        # Name
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText(tr("fin.dlg_account_name_hint"))
        form.addRow(tr("fin.dlg_account_name"), self.edit_name)

        # Type
        self.combo_type = QComboBox()
        for t in ACCOUNT_TYPES:
            self.combo_type.addItem(_ACCOUNT_TYPE_LABELS.get(t, t), t)
        form.addRow(tr("fin.dlg_account_type"), self.combo_type)

        # Balance
        self.spin_balance = QDoubleSpinBox()
        self.spin_balance.setRange(0, 100_000_000)
        self.spin_balance.setSingleStep(1000)
        self.spin_balance.setDecimals(2)
        self.spin_balance.setValue(0.0)
        form.addRow(tr("fin.dlg_balance"), self.spin_balance)

        # Currency
        self.combo_currency = QComboBox()
        for c in CURRENCIES:
            self.combo_currency.addItem(c)
        form.addRow(tr("fin.dlg_currency"), self.combo_currency)

        # Color picker row
        color_row = QHBoxLayout()
        self.btn_color = QPushButton()
        self.btn_color.setFixedSize(32, 32)
        self._set_color_btn(self._color)
        self.btn_color.clicked.connect(self._pick_color)
        color_row.addWidget(self.btn_color)
        color_row.addStretch()
        form.addRow(tr("fin.dlg_color"), color_row)

        _add_buttons(outer, self)

    def _set_color_btn(self, hex_color: str):
        self._color = hex_color
        self.btn_color.setStyleSheet(
            f"background:{hex_color}; border-radius:6px; border:1px solid rgba(255,255,255,0.2);"
        )

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self._color), self, tr("fin.pick_color"))
        if c.isValid():
            self._set_color_btn(c.name())

    def result_data(self) -> dict:
        return dict(
            name=self.edit_name.text().strip(),
            type_=self.combo_type.currentData(),
            balance=self.spin_balance.value(),
            currency=self.combo_currency.currentText(),
            color=self._color,
        )


# ── AddBudgetDialog ──────────────────────────────────────────────────────────

class AddBudgetDialog(QDialog):
    """Dialog for adding a new budget limit for an expense category."""

    def __init__(self, finance_svc, parent=None):
        super().__init__(parent)
        self._svc = finance_svc
        self.setWindowTitle(tr("fin.dlg_add_budget"))
        self.setModal(True)
        self.setMinimumWidth(360)
        self.setStyleSheet("QDialog { background: #1c1c1e; }" + _INPUT_SS)

        outer = QVBoxLayout(self)
        outer.setSpacing(14)
        outer.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        outer.addLayout(form)

        # Category
        self.combo_cat = QComboBox()
        cats = finance_svc.list_categories("expense")
        for c in cats:
            self.combo_cat.addItem(f"{c.icon} {c.name}", c.id)
        form.addRow(tr("fin.dlg_category"), self.combo_cat)

        # Limit
        self.spin_limit = QDoubleSpinBox()
        self.spin_limit.setRange(1, 10_000_000)
        self.spin_limit.setSingleStep(1000)
        self.spin_limit.setDecimals(2)
        self.spin_limit.setValue(10000)
        form.addRow(tr("fin.dlg_budget_limit"), self.spin_limit)

        # Period
        self.combo_period = QComboBox()
        for p in BUDGET_PERIODS:
            self.combo_period.addItem(tr(f"fin.period_{p}"), p)
        self.combo_period.setCurrentIndex(1)  # default: month
        form.addRow(tr("fin.dlg_period"), self.combo_period)

        _add_buttons(outer, self)

    def result_data(self) -> dict:
        return dict(
            category_id=self.combo_cat.currentData(),
            limit_amount=self.spin_limit.value(),
            period=self.combo_period.currentData(),
        )


# ── AddGoalDialog ────────────────────────────────────────────────────────────

class AddGoalDialog(QDialog):
    """Dialog for adding a savings goal."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("fin.dlg_add_goal"))
        self.setModal(True)
        self.setMinimumWidth(380)
        self.setStyleSheet("QDialog { background: #1c1c1e; }" + _INPUT_SS)
        self._color = "#bf5af2"

        outer = QVBoxLayout(self)
        outer.setSpacing(14)
        outer.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        outer.addLayout(form)

        # Name
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText(tr("fin.dlg_goal_name_hint"))
        form.addRow(tr("fin.dlg_goal_name"), self.edit_name)

        # Target amount
        self.spin_target = QDoubleSpinBox()
        self.spin_target.setRange(1, 100_000_000)
        self.spin_target.setSingleStep(1000)
        self.spin_target.setDecimals(2)
        self.spin_target.setValue(50000)
        form.addRow(tr("fin.dlg_target"), self.spin_target)

        # Current saved
        self.spin_current = QDoubleSpinBox()
        self.spin_current.setRange(0, 100_000_000)
        self.spin_current.setSingleStep(1000)
        self.spin_current.setDecimals(2)
        self.spin_current.setValue(0)
        form.addRow(tr("fin.dlg_current_saved"), self.spin_current)

        # Currency
        self.combo_currency = QComboBox()
        for c in CURRENCIES:
            self.combo_currency.addItem(c)
        form.addRow(tr("fin.dlg_currency"), self.combo_currency)

        # Deadline (optional)
        deadline_row = QHBoxLayout()
        self.date_deadline = QDateEdit()
        self.date_deadline.setDate(QDate.currentDate().addDays(180))
        self.date_deadline.setCalendarPopup(True)
        self.date_deadline.setDisplayFormat("dd.MM.yyyy")
        self.date_deadline.setEnabled(False)
        self.chk_deadline = QPushButton(tr("fin.dlg_set_deadline"))
        self.chk_deadline.setCheckable(True)
        self.chk_deadline.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.12); "
            "border-radius: 6px; color: #98989d; font-size: 13px; padding: 4px 10px; }"
            "QPushButton:checked { background: rgba(10,132,255,0.25); color: #0a84ff; border-color: #0a84ff; }"
        )
        self.chk_deadline.toggled.connect(self.date_deadline.setEnabled)
        deadline_row.addWidget(self.chk_deadline)
        deadline_row.addWidget(self.date_deadline)
        deadline_row.addStretch()
        form.addRow(tr("fin.dlg_deadline"), deadline_row)

        # Color
        color_row = QHBoxLayout()
        self.btn_color = QPushButton()
        self.btn_color.setFixedSize(32, 32)
        self._set_color_btn(self._color)
        self.btn_color.clicked.connect(self._pick_color)
        color_row.addWidget(self.btn_color)
        color_row.addStretch()
        form.addRow(tr("fin.dlg_color"), color_row)

        _add_buttons(outer, self)

    def _set_color_btn(self, hex_color: str):
        self._color = hex_color
        self.btn_color.setStyleSheet(
            f"background:{hex_color}; border-radius:6px; border:1px solid rgba(255,255,255,0.2);"
        )

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self._color), self, tr("fin.pick_color"))
        if c.isValid():
            self._set_color_btn(c.name())

    def result_data(self) -> dict:
        deadline = None
        if self.chk_deadline.isChecked():
            deadline = self.date_deadline.date().toString("yyyy-MM-dd")
        return dict(
            name=self.edit_name.text().strip(),
            target_amount=self.spin_target.value(),
            current_amount=self.spin_current.value(),
            currency=self.combo_currency.currentText(),
            color=self._color,
            deadline=deadline,
        )
