"""Finance workspace — FinancePage with two UX states (empty / populated dashboard)."""
from __future__ import annotations

from pathlib import Path
from shared.config.paths import ICONS_DIR, IMAGES_DIR
from typing import Optional, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QScrollArea, QFrame, QSizePolicy, QLineEdit, QProgressBar,
    QGridLayout, QStackedWidget, QMainWindow,
)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QSize, QEvent
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QPainterPath, QLinearGradient, QIcon, QPixmap

import pyqtgraph as pg
import numpy as np

from entities.finance.service import FinanceService
from shared.i18n import tr
import app.styles.themes as _styles

_ICON_POPOUT   = str(ICONS_DIR / "popout.svg")
_ICON_DOCKBACK = str(ICONS_DIR / "dock_back.svg")

# Deferred import to avoid circular dependency
def _sidebar_cls():
    from widgets.finance_sidebar.ui import FinanceSidebar
    return FinanceSidebar


# ── Frosted-glass base frame ──────────────────────────────────────────────────
class GlassFrame(QFrame):
    """QFrame subclass that simulates CSS backdrop-filter: blur() in glass theme.

    In glass mode:  paints blurred background region + subtle blue tint + border.
    In other modes: falls back to normal QFrame (QSS handles everything).

    Subclasses that have their own paintEvent should call
    ``super().paintEvent(event)`` FIRST to get the glass background, then
    open a new QPainter to draw custom decorations on top.
    """
    _GLASS_RADIUS  = 14.0          # border-radius (px)
    _GLASS_TINT    = (52, 95, 188, 30)   # RGBA: visible acrylic tint (~12%)
    # top-left bright edge — crisp acrylic inner highlight
    _BORDER_HI     = QColor(185, 235, 255, 155)  # rgba(185,235,255,0.61)
    # right-bottom dim shadow edge
    _BORDER_DIM    = QColor(38,  72,  168, 40)   # rgba(38,72,168,0.16)

    def paintEvent(self, event):
        if _styles.current_theme() != "glass":
            super().paintEvent(event)
            return

        blurred = _styles.get_glass_blur_region(self)

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self._GLASS_RADIUS
        rect_f = QRectF(self.rect())

        # ── 1. Clip to rounded shape ──────────────────────────────────────
        path = QPainterPath()
        path.addRoundedRect(rect_f, r, r)
        p.setClipPath(path)

        # ── 2. Blurred background (backdrop-filter simulation) ────────────
        if blurred and not blurred.isNull():
            p.drawPixmap(0, 0, blurred)
        else:
            # Fallback: solid dark navy when blur cache not yet built
            p.fillPath(path, QColor(8, 14, 28, 200))

        # ── 3. Glass tint overlay ─────────────────────────────────────────
        p.fillPath(path, QColor(*self._GLASS_TINT))

        # ── 4. Border: uniform glass edge on all 4 sides ─────────────────
        p.setClipping(False)
        p.setBrush(Qt.BrushStyle.NoBrush)
        border_path = QPainterPath()
        border_path.addRoundedRect(
            QRectF(0.5, 0.5, self.rect().width() - 1.0, self.rect().height() - 1.0), r, r
        )
        p.setPen(QPen(self._BORDER_HI, 1.0))
        p.drawPath(border_path)

        p.end()

# ── Colour constants ─────────────────────────────────────────────────────────
_INC  = "#30d158"   # green  — income   (dark theme)
_EXP  = "#ff453a"   # red    — expense  (dark theme)
_BAL  = "#0a84ff"   # blue   — balance  (dark theme)
_GOAL = "#bf5af2"   # purple — goals    (dark theme)
_XFER = "#ff9f0a"   # orange — transfer (dark theme)

# Theme-aware finance accent colours (light uses muted/desaturated versions)
_FIN_COLORS: dict[str, dict[str, str]] = {
    "dark":  {"inc": _INC,      "exp": _EXP,      "bal": _BAL,      "goal": _GOAL,    "xfer": _XFER},
    "light": {"inc": "#16a34a", "exp": "#dc2626",  "bal": "#2563eb", "goal": "#7c3aed", "xfer": "#d97706"},
    # Glass: slightly softer neons (--success / --danger / --primary / --purple / --warning)
    "glass": {"inc": "#52d38a", "exp": "#ff6b6b",  "bal": "#5ea2ff", "goal": "#c27cff", "xfer": "#ffb84d"},
}


def _fc(key: str) -> str:
    """Return theme-appropriate finance accent colour."""
    return _FIN_COLORS.get(_styles._active_theme, _FIN_COLORS["dark"]).get(key, "#888888")


def _th() -> dict:
    return _styles._THEMES[_styles._active_theme]


def _ts() -> str:
    """Secondary text colour for finance card backgrounds (brighter on dark themes).
    Returns a hex colour so it works in CSS, QColor(), and pyqtgraph equally."""
    if _styles._active_theme == "light":
        return _styles._THEMES["light"]["text_sec"]   # "#52607A"
    if _styles._active_theme == "glass":
        return "#bdd0ec"   # bright blue-gray for glass cards
    return "#c0c0c8"       # bright neutral gray for dark cards


def _tinted_icon(path: str, color: str) -> QIcon:
    """Return a QIcon re-coloured to *color* (for light-theme SVG adaptation)."""
    from PyQt6.QtGui import QPixmap, QPainter
    from PyQt6.QtCore import QRectF, Qt as _Qt
    px = QPixmap(path)
    if px.isNull():
        return QIcon()
    result = QPixmap(px.size())
    result.fill(_Qt.GlobalColor.transparent)
    p = QPainter(result)
    p.drawPixmap(0, 0, px)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(result.rect(), QColor(color))
    p.end()
    return QIcon(result)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _fmt_amount(amount: float, currency: str = "₽") -> str:
    if abs(amount) >= 1_000_000:
        return f"{amount / 1_000_000:.1f}M {currency}"
    if abs(amount) >= 1_000:
        s = f"{amount:,.0f}".replace(",", "\u202f")
        return f"{s} {currency}"
    return f"{amount:.0f} {currency}"


def _fmt_total_balance(bal_dict: dict) -> str:
    """Format {currency: amount} dict → primary balance string."""
    if not bal_dict:
        return "0"
    # Show the largest-value currency, or first one
    primary = max(bal_dict, key=lambda c: abs(bal_dict[c]))
    return _fmt_amount(bal_dict[primary], primary)


def _safe_plot_widget(min_h: int = 180, max_h: int = 240) -> pg.PlotWidget:
    th = _th()
    fg = _ts()
    pg.setConfigOptions(background="#00000000", foreground=fg, antialias=True)
    pw = pg.PlotWidget()
    pw.setBackground(None)  # always transparent — card frame provides the bg
    pw.setMinimumHeight(min_h)
    pw.setMaximumHeight(max_h)
    pw.setMinimumWidth(100)
    pw.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    pw.showGrid(x=False, y=True, alpha=0.12)
    pw.setMouseEnabled(x=False, y=False)
    pw.setMenuEnabled(False)
    vb = pw.getViewBox()
    vb.setMouseEnabled(x=False, y=False)
    vb.enableAutoRange()
    tf = QFont("Segoe UI", 8)
    pw.getAxis("bottom").setStyle(tickFont=tf)
    pw.getAxis("left").setStyle(tickFont=tf)
    ap = pg.mkPen(fg)
    pw.getAxis("bottom").setTextPen(ap)
    pw.getAxis("left").setTextPen(ap)
    pw.getAxis("bottom").setPen(pg.mkPen(color=fg, width=1))
    pw.getAxis("left").setPen(pg.mkPen(color=fg, width=1))
    return pw


# ── Reusable card components ─────────────────────────────────────────────────

class FinKpiCard(QFrame):
    """KPI card – all drawing done in paintEvent for pixel-perfect uniform border."""
    _RADIUS = 14.0

    def __init__(self, label: str, accent: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("FinKpiCard")
        self._accent = accent or _fc("bal")
        self.setMinimumHeight(96)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAutoFillBackground(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 0, 14, 14)
        layout.setSpacing(2)

        self._val_lbl = QLabel("—")
        self._val_lbl.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        self._val_lbl.setStyleSheet(f"color: {self._accent}; background: transparent; border: none;")

        self._label_lbl = QLabel(label)
        self._label_lbl.setFont(QFont("Segoe UI", 11))
        self._label_lbl.setStyleSheet(f"color: {_th()['text_sec']}; background: transparent; border: none;")

        layout.addStretch()
        layout.addWidget(self._val_lbl)
        layout.addSpacing(2)
        layout.addWidget(self._label_lbl)

    def set_value(self, text: str):
        self._val_lbl.setText(text)

    def set_label(self, text: str):
        self._label_lbl.setText(text)

    def set_accent(self, color: str):
        self._accent = color
        self._val_lbl.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        self.update()

    def apply_theme(self):
        self._label_lbl.setStyleSheet(f"color: {_th()['text_sec']}; background: transparent; border: none;")
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        r = self._RADIUS
        rect_f = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        path = QPainterPath()
        path.addRoundedRect(rect_f, r, r)

        theme = _styles.current_theme()

        if theme == "glass":
            blurred = _styles.get_glass_blur_region(self)
            p.setClipPath(path)
            if blurred and not blurred.isNull():
                p.drawPixmap(0, 0, blurred)
            else:
                p.fillPath(path, QColor(8, 14, 28, 200))
            p.fillPath(path, QColor(52, 95, 188, 25))
            p.setClipping(False)
            border_color = QColor(160, 200, 255, 90)
        elif theme == "light":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 220))
            p.drawPath(path)
            border_color = QColor(175, 198, 225, 190)
        else:  # dark
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 18))
            p.drawPath(path)
            border_color = QColor(255, 255, 255, 55)

        # Uniform border — drawn with QPen, identical on all 4 sides
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(border_color, 1.0))
        p.drawPath(path)

        # Left accent stripe
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._accent))
        stripe = QPainterPath()
        stripe.addRoundedRect(QRectF(0.0, 8.0, 3.0, self.height() - 16.0), 1.5, 1.5)
        p.drawPath(stripe)

        p.end()


class _DonutWidget(GlassFrame):
    """Custom-painted multi-arc donut chart with legend."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("FinDonutCard")
        self.setMinimumHeight(260)
        self._title = title
        self._slices: list[tuple[float, str, str]] = []

    def set_data(self, slices: list[tuple[float, str, str]]):
        self._slices = slices
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)  # GlassFrame: blurred bg + tint + border
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        th = _th()
        w, h = self.width(), self.height()

        p.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        p.setPen(QColor(th["text"]))
        p.drawText(QRectF(14, 10, w - 28, 22), Qt.AlignmentFlag.AlignLeft, self._title)

        if not self._slices:
            p.setFont(QFont("Segoe UI", 10))
            p.setPen(QColor(_ts()))
            p.drawText(QRectF(0, h / 2 - 12, w, 24), Qt.AlignmentFlag.AlignCenter, tr("fin.no_data"))
            p.end()
            return

        total = sum(v for v, _, _ in self._slices)
        if total <= 0:
            p.end()
            return

        legend_w = max(w * 0.42, 120)
        donut_w = w - legend_w
        cx = donut_w / 2
        cy = (h + 32) / 2
        r_outer = min(donut_w / 2 - 30, (h - 50) / 2)
        r_outer = max(r_outer, 28)
        r_inner = r_outer * 0.56

        angle = -90.0
        p.setPen(Qt.PenStyle.NoPen)
        for value, color, _ in self._slices:
            span = (value / total) * 360.0
            p.setBrush(QColor(color))
            path = QPainterPath()
            outer_rect = QRectF(cx - r_outer, cy - r_outer, r_outer * 2, r_outer * 2)
            inner_rect = QRectF(cx - r_inner, cy - r_inner, r_inner * 2, r_inner * 2)
            path.moveTo(cx + r_outer * np.cos(np.radians(angle)),
                        cy + r_outer * np.sin(np.radians(angle)))
            path.arcTo(outer_rect, -angle, -span)
            path.arcTo(inner_rect, -(angle + span), span)
            path.closeSubpath()
            p.drawPath(path)
            angle += span

        p.setFont(QFont("Segoe UI", 9))
        p.setPen(QColor(_ts()))
        p.drawText(QRectF(cx - r_inner, cy - 12, r_inner * 2, 24),
                   Qt.AlignmentFlag.AlignCenter, _fmt_amount(total))

        lx = donut_w + 6
        ly = 38.0
        row_h = 34.0
        for value, color, label in self._slices:
            if ly + row_h > h - 8:
                break
            p.setBrush(QColor(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(lx, ly + 7, 10, 10), 2.5, 2.5)
            pct = int(value / total * 100)
            p.setFont(QFont("Segoe UI", 10))
            p.setPen(QColor(th["text"]))
            p.drawText(QRectF(lx + 16, ly, legend_w - 20, 18),
                       Qt.AlignmentFlag.AlignVCenter, f"{label[:13]}  {pct}%")
            p.setFont(QFont("Segoe UI", 9))
            p.setPen(QColor(_ts()))
            p.drawText(QRectF(lx + 16, ly + 16, legend_w - 20, 16),
                       Qt.AlignmentFlag.AlignVCenter, _fmt_amount(value))
            ly += row_h
        p.end()


class _TxRow(GlassFrame):
    """Single transaction row widget."""
    _GLASS_RADIUS = 10.0

    def __init__(self, tx, on_delete=None, parent=None):
        super().__init__(parent)
        self.setObjectName("FinTransactionRow")
        self.setFixedHeight(52)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._cat_color = tx.category_color if tx.category_color else (
            _fc("inc") if tx.type == "income" else (_fc("xfer") if tx.type == "transfer" else _fc("exp"))
        )
        self._on_delete = on_delete

        row = QHBoxLayout(self)
        row.setContentsMargins(18, 6, 8, 6)
        row.setSpacing(10)

        icon_text = tx.category_icon if tx.category_icon else ("+" if tx.type == "income" else "−")
        icon_lbl = QLabel(icon_text)
        icon_lbl.setFixedWidth(28)
        icon_lbl.setFont(QFont("Segoe UI", 16))
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(icon_lbl)

        mid = QVBoxLayout()
        mid.setSpacing(2)
        title = tx.title if tx.title else (tx.category_name if tx.category_name else tr(f"fin.type_{tx.type}"))
        tl = QLabel(title)
        tl.setFont(QFont("Segoe UI", 14, QFont.Weight.Medium))
        tl.setStyleSheet(f"color: {_th()['text']};")
        cl = QLabel(tx.date + ("  •  " + tx.category_name if tx.category_name else ""))
        cl.setFont(QFont("Segoe UI", 11))
        cl.setStyleSheet(f"color: {_th()['text_sec']};")
        mid.addWidget(tl)
        mid.addWidget(cl)
        row.addLayout(mid, stretch=1)

        sign = "+" if tx.type == "income" else ("" if tx.type == "transfer" else "−")
        color = _fc("inc") if tx.type == "income" else (_fc("xfer") if tx.type == "transfer" else _fc("exp"))
        al = QLabel(f"{sign}{_fmt_amount(tx.amount, tx.currency)}")
        al.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
        al.setStyleSheet(f"color: {color};")
        al.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(al)

        self._del_btn = QPushButton("×")
        self._del_btn.setFixedSize(26, 26)
        self._del_btn.setFont(QFont("Segoe UI", 15))
        self._del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._del_btn.setObjectName("TxDeleteBtn")
        self._del_btn.setVisible(False)
        self._del_btn.clicked.connect(lambda: on_delete() if on_delete else None)
        row.addWidget(self._del_btn)

    def event(self, ev):
        if ev.type() == QEvent.Type.HoverEnter:
            self._del_btn.setVisible(True)
        elif ev.type() == QEvent.Type.HoverLeave:
            self._del_btn.setVisible(False)
        return super().event(ev)

    def paintEvent(self, event):
        super().paintEvent(event)  # GlassFrame: blurred bg + tint + border
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._cat_color))
        p.drawRoundedRect(QRectF(0, 6, 3, self.height() - 12), 1.5, 1.5)
        p.end()


_ACC_ICONS = {
    "cash": "💵", "bank": "🏦", "savings": "🐷",
    "investment": "📈", "crypto": "₿",
}


class _AccountCard(GlassFrame):
    """Compact account balance card with type icon, coloured accent stripe."""
    _GLASS_RADIUS = 14.0

    def __init__(self, account, total_balance: float = 0.0, parent=None):
        super().__init__(parent)
        self.setObjectName("FinAccountCard")
        self.setFixedHeight(100)
        self._accent = account.color or _fc("bal")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 10, 14, 10)
        layout.setSpacing(2)

        # Name row: icon + name
        name_row = QHBoxLayout()
        name_row.setSpacing(6)
        icon_lbl = QLabel(_ACC_ICONS.get(account.type, "💳"))
        icon_lbl.setFont(QFont("Segoe UI", 14))
        nl = QLabel(account.name)
        nl.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        nl.setStyleSheet(f"color: {_th()['text']};")
        name_row.addWidget(icon_lbl)
        name_row.addWidget(nl, stretch=1)
        layout.addLayout(name_row)

        type_map = {
            "cash": tr("fin.acc_cash"), "bank": tr("fin.acc_bank"),
            "savings": tr("fin.acc_savings"), "investment": tr("fin.acc_investment"),
            "crypto": tr("fin.acc_crypto"),
        }
        tl = QLabel(type_map.get(account.type, account.type))
        tl.setFont(QFont("Segoe UI", 11))
        tl.setStyleSheet(f"color: {_th()['text_sec']};")
        layout.addWidget(tl)

        layout.addStretch()

        # Balance + share row
        bal_row = QHBoxLayout()
        bal_row.setSpacing(8)
        bl = QLabel(_fmt_amount(account.balance, account.currency))
        bl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        bl.setStyleSheet(f"color: {self._accent};")
        bal_row.addWidget(bl, stretch=1)
        if total_balance > 0:
            share = int(abs(account.balance) / total_balance * 100)
            sl = QLabel(f"{share}%")
            sl.setFont(QFont("Segoe UI", 10))
            sl.setStyleSheet(f"color: {_th()['text_sec']};")
            sl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            bal_row.addWidget(sl)
        layout.addLayout(bal_row)

    def paintEvent(self, event):
        super().paintEvent(event)  # GlassFrame: blurred bg + tint + border
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._accent))
        p.drawRoundedRect(QRectF(0, 0, 4, self.height()), 2, 2)
        p.end()


class _BudgetCard(GlassFrame):
    """Budget card — compact HBox layout matching GoalCard style."""

    def __init__(self, budget, on_add_expense: Callable = None, parent=None):
        super().__init__(parent)
        self.setObjectName("FinBudgetCard")
        self.setFixedHeight(148 if on_add_expense else 120)

        pct = int(budget.spent / budget.limit_amount * 100) if budget.limit_amount > 0 else 0
        danger = pct >= 90
        pct_color = _fc("exp") if danger else (_fc("xfer") if pct >= 75 else _fc("inc"))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        # Left: big percentage + mini progress bar
        left = QVBoxLayout()
        left.setSpacing(4)
        left.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        pct_lbl = QLabel(f"{pct}%")
        pct_lbl.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        pct_lbl.setStyleSheet(f"color: {pct_color};")
        pct_lbl.setFixedWidth(72)
        pct_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bar = QProgressBar()
        bar.setObjectName("FinBudgetBarDanger" if danger else "FinBudgetBar")
        bar.setRange(0, 100)
        bar.setValue(min(pct, 100))
        bar.setFixedHeight(6)
        bar.setFixedWidth(72)
        bar.setTextVisible(False)
        left.addWidget(pct_lbl)
        left.addWidget(bar)
        layout.addLayout(left)

        # Right: category name, spent/limit, remaining, optional button
        right = QVBoxLayout()
        right.setSpacing(2)

        icon_name = f"{budget.category_icon} {budget.category_name}" if budget.category_icon else budget.category_name
        cat_lbl = QLabel(icon_name)
        cat_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        cat_lbl.setStyleSheet(f"color: {_th()['text']};")
        cat_lbl.setWordWrap(True)

        sl = QLabel(f"{_fmt_amount(budget.spent)} / {_fmt_amount(budget.limit_amount)}")
        sl.setFont(QFont("Segoe UI", 11))
        sl.setStyleSheet(f"color: {pct_color};")

        remaining = max(0.0, budget.limit_amount - budget.spent)
        rl = QLabel(f"{tr('fin.remaining')}: {_fmt_amount(remaining)}")
        rl.setFont(QFont("Segoe UI", 10))
        rl.setStyleSheet(f"color: {_th()['text_sec']};")

        right.addWidget(cat_lbl)
        right.addWidget(sl)
        right.addWidget(rl)
        right.addStretch()

        if on_add_expense:
            btn = QPushButton(f"+ {tr('fin.budget_add_expense')}")
            btn.setObjectName("FilterBtn")
            btn.setFixedHeight(24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(on_add_expense)
            right.addWidget(btn)

        layout.addLayout(right, stretch=1)


class _GoalCard(GlassFrame):
    """Goal card with circular arc progress via QPainter."""
    _GLASS_RADIUS = 14.0
    _ARC_W = 8

    def __init__(self, goal, on_deposit: Callable = None, parent=None):
        super().__init__(parent)
        self.setObjectName("FinGoalCard")
        self.setFixedHeight(148 if on_deposit else 120)
        self._goal = goal
        self._color = goal.color or _fc("goal")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        self._arc_ph = QWidget()
        self._arc_ph.setFixedSize(70, 70)
        self._arc_ph.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self._arc_ph, alignment=Qt.AlignmentFlag.AlignVCenter)

        right = QVBoxLayout()
        right.setSpacing(2)

        nl = QLabel(goal.name)
        nl.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        nl.setStyleSheet(f"color: {_th()['text']};")
        nl.setWordWrap(True)

        sl = QLabel(f"{_fmt_amount(goal.current_amount, goal.currency)} / {_fmt_amount(goal.target_amount, goal.currency)}")
        sl.setFont(QFont("Segoe UI", 11))
        sl.setStyleSheet(f"color: {self._color};")

        rl = QLabel(f"{tr('fin.remaining')}: {_fmt_amount(goal.remaining, goal.currency)}")
        rl.setFont(QFont("Segoe UI", 10))
        rl.setStyleSheet(f"color: {_th()['text_sec']};")

        right.addWidget(nl)
        right.addWidget(sl)
        right.addWidget(rl)
        right.addStretch()

        if on_deposit:
            btn = QPushButton(f"+ {tr('fin.goal_deposit')}")
            btn.setObjectName("FilterBtn")
            btn.setFixedHeight(24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(on_deposit)
            right.addWidget(btn)

        layout.addLayout(right, stretch=1)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ph = self._arc_ph
        offset = ph.mapTo(self, QPointF(0, 0).toPoint())
        cx = offset.x() + ph.width() / 2
        cy = offset.y() + ph.height() / 2
        r = ph.width() / 2 - self._ARC_W / 2 - 2
        rect = QRectF(cx - r, cy - r, r * 2, r * 2)
        p.setPen(QPen(QColor(100, 100, 110, 60), self._ARC_W, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(rect, 0, 360 * 16)
        pct = self._goal.progress_pct
        if pct > 0:
            p.setPen(QPen(QColor(self._color), self._ARC_W, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(rect, 90 * 16, -int(pct / 100 * 360 * 16))
        p.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        p.setPen(QColor(self._color))
        p.drawText(QRectF(cx - 26, cy - 11, 52, 22), Qt.AlignmentFlag.AlignCenter, f"{pct}%")
        p.end()


# ── Section header helper ─────────────────────────────────────────────────────

def _section_header(text: str, btn_text: str = "", btn_cb=None) -> tuple:
    """Returns (QHBoxLayout, QLabel) so callers can store the label for retranslate."""
    row = QHBoxLayout()
    row.setSpacing(8)
    lbl = QLabel(text)
    lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
    lbl.setStyleSheet(f"color: {_th()['text']};")
    row.addWidget(lbl)
    row.addStretch()
    if btn_text and btn_cb:
        btn = QPushButton(btn_text)
        btn.setObjectName("FilterBtn")
        btn.setFixedHeight(26)
        btn.clicked.connect(btn_cb)
        row.addWidget(btn)
    return row, lbl


# ── Empty state ───────────────────────────────────────────────────────────────

class _EmptyState(QWidget):
    """Onboarding screen shown when no transactions exist."""

    def __init__(self, on_add_tx: Callable, on_add_account: Callable,
                 on_load_demo: Callable, parent=None):
        super().__init__(parent)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        inner = QWidget()
        inner.setAutoFillBackground(False)
        vbox = QVBoxLayout(inner)
        vbox.setContentsMargins(20, 20, 20, 40)
        vbox.setSpacing(18)
        vbox.addStretch(1)

        # ── Hero card ──────────────────────────────────────────────────────
        hero = QFrame()
        hero.setObjectName("FinSectionCard")
        hero.setMinimumHeight(160)
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(32, 28, 32, 28)
        hero_layout.setSpacing(10)
        hero_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel("🏦")
        icon_lbl.setFont(QFont("Segoe UI", 38))
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_lbl = QLabel(tr("fin.empty_title"))
        title_lbl.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {_th()['text']};")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        sub_lbl = QLabel(tr("fin.empty_subtitle"))
        sub_lbl.setFont(QFont("Segoe UI", 13))
        sub_lbl.setStyleSheet(f"color: {_th()['text_sec']};")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_lbl.setWordWrap(True)

        hero_layout.addWidget(icon_lbl)
        hero_layout.addWidget(title_lbl)
        hero_layout.addWidget(sub_lbl)
        vbox.addWidget(hero)

        # ── CTA row ───────────────────────────────────────────────────────
        cta_row = QHBoxLayout()
        cta_row.setSpacing(10)

        def _cta(label: str, accent: str, cb: Callable) -> QPushButton:
            btn = QPushButton(label)
            btn.setFixedHeight(42)
            btn.setFont(QFont("Segoe UI", 13, QFont.Weight.Medium))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {accent};
                    border: none; border-radius: 10px;
                    color: #fff; padding: 0 20px;
                }}
                QPushButton:hover {{ background: {accent}cc; }}
                QPushButton:pressed {{ background: {accent}99; }}
            """)
            btn.clicked.connect(cb)
            return btn

        cta_row.addWidget(_cta(tr("fin.cta_add_tx"),      _fc("bal"),  on_add_tx))
        cta_row.addWidget(_cta(tr("fin.cta_add_account"),  _fc("goal"), on_add_account))
        cta_row.addWidget(_cta(tr("fin.cta_load_demo"),    _fc("inc"),  on_load_demo))
        vbox.addLayout(cta_row)

        # ── Setup suggestion cards ─────────────────────────────────────────
        grid = QHBoxLayout()
        grid.setSpacing(12)
        for icon, title, desc in [
            ("🏦", tr("fin.setup_account_title"), tr("fin.setup_account_desc")),
            ("💰", tr("fin.setup_income_title"),  tr("fin.setup_income_desc")),
            ("📊", tr("fin.setup_track_title"),   tr("fin.setup_track_desc")),
        ]:
            card = QFrame()
            card.setObjectName("FinSectionCard")
            card.setMinimumHeight(130)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(20, 16, 20, 16)
            card_layout.setSpacing(6)

            il = QLabel(icon)
            il.setFont(QFont("Segoe UI", 24))
            tl = QLabel(title)
            tl.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
            tl.setStyleSheet(f"color: {_th()['text']};")
            dl = QLabel(desc)
            dl.setFont(QFont("Segoe UI", 11))
            dl.setStyleSheet(f"color: {_th()['text_sec']};")
            dl.setWordWrap(True)

            card_layout.addWidget(il)
            card_layout.addWidget(tl)
            card_layout.addWidget(dl)
            grid.addWidget(card, stretch=1)
        vbox.addLayout(grid)

        # ── Chart preview placeholder ──────────────────────────────────────
        preview = QFrame()
        preview.setObjectName("FinSectionCard")
        preview.setFixedHeight(80)
        prev_layout = QHBoxLayout(preview)
        prev_layout.setContentsMargins(20, 0, 20, 0)
        prev_lbl = QLabel(tr("fin.empty_chart_hint"))
        prev_lbl.setFont(QFont("Segoe UI", 12))
        prev_lbl.setStyleSheet(f"color: {_th()['text_sec']};")
        prev_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prev_layout.addWidget(prev_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(preview)

        vbox.addStretch(1)

        scroll.setWidget(inner)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)


# ── Dashboard (populated state) ───────────────────────────────────────────────

class _Dashboard(QWidget):
    """Populated dashboard shown when transactions exist."""

    def __init__(self, svc: FinanceService, parent=None):
        super().__init__(parent)
        self._svc = svc
        self._charts_ready = False

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._inner = QWidget()
        self._inner.setAutoFillBackground(False)
        self._vbox = QVBoxLayout(self._inner)
        self._vbox.setSpacing(12)
        self._vbox.setContentsMargins(4, 8, 4, 16)

        # ── 1. KPI row (5 cards) ───────────────────────────────────────────
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(8)
        self._kpi_bal = FinKpiCard(tr("fin.kpi_balance"),  _fc("bal"))
        self._kpi_inc = FinKpiCard(tr("fin.kpi_income"),   _fc("inc"))
        self._kpi_exp = FinKpiCard(tr("fin.kpi_expenses"), _fc("exp"))
        self._kpi_net = FinKpiCard(tr("fin.kpi_net"),      _fc("goal"))
        self._kpi_avg = FinKpiCard(tr("fin.kpi_avg_day"),  _fc("xfer"))
        for k in (self._kpi_bal, self._kpi_inc, self._kpi_exp, self._kpi_net, self._kpi_avg):
            kpi_row.addWidget(k)
        self._vbox.addLayout(kpi_row)

        # Lazy chart placeholder
        self._chart_placeholder = self._vbox.addStretch(1)

        scroll.setWidget(self._inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _ensure_charts(self):
        if self._charts_ready:
            return
        self._vbox.removeItem(self._chart_placeholder)

        # ── 2. Main chart: Income vs Expenses (dominant, full width) ───────
        chart_hdr_row, self._chart_hdr_lbl = _section_header(tr("fin.chart_inc_exp"))
        self._vbox.addLayout(chart_hdr_row)
        self._bar_chart = _safe_plot_widget(min_h=220, max_h=260)
        _bar_card = QFrame()
        _bar_card.setObjectName("FinSectionCard")
        _bar_card_lay = QVBoxLayout(_bar_card)
        _bar_card_lay.setContentsMargins(12, 10, 12, 10)
        _bar_card_lay.setSpacing(0)
        _bar_card_lay.addWidget(self._bar_chart)
        self._vbox.addWidget(_bar_card)

        # ── 3. Two-column: Recent tx (55%) | Expense donut (45%) ───────────
        col_row = QHBoxLayout()
        col_row.setSpacing(12)

        # Left: recent transactions section card
        tx_card = QFrame()
        tx_card.setObjectName("FinSectionCard")
        tx_vbox = QVBoxLayout(tx_card)
        tx_vbox.setContentsMargins(14, 12, 14, 12)
        tx_vbox.setSpacing(6)
        self._tx_hdr = QLabel(tr("fin.recent_transactions"))
        self._tx_hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        self._tx_hdr.setStyleSheet(f"color: {_th()['text']};")
        tx_vbox.addWidget(self._tx_hdr)
        self._recent_vbox = QVBoxLayout()
        self._recent_vbox.setSpacing(4)
        tx_vbox.addLayout(self._recent_vbox)
        col_row.addWidget(tx_card, stretch=55)

        # Right: expense donut
        self._exp_donut = _DonutWidget(tr("fin.chart_exp_by_cat"))
        col_row.addWidget(self._exp_donut, stretch=45)
        self._vbox.addLayout(col_row)

        # ── 4. Preview row: Budgets (50%) | Goals (50%) ────────────────────
        preview_row = QHBoxLayout()
        preview_row.setSpacing(12)

        bud_frame = QFrame()
        bud_frame.setObjectName("FinSectionCard")
        bud_vbox = QVBoxLayout(bud_frame)
        bud_vbox.setContentsMargins(14, 12, 14, 12)
        bud_vbox.setSpacing(6)
        self._bud_hdr = QLabel(tr("fin.tab_budgets"))
        self._bud_hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        self._bud_hdr.setStyleSheet(f"color: {_th()['text']};")
        bud_vbox.addWidget(self._bud_hdr)
        self._budget_preview_vbox = QVBoxLayout()
        self._budget_preview_vbox.setSpacing(6)
        bud_vbox.addLayout(self._budget_preview_vbox)
        bud_vbox.addStretch()
        preview_row.addWidget(bud_frame, stretch=1)

        goal_frame = QFrame()
        goal_frame.setObjectName("FinSectionCard")
        goal_vbox = QVBoxLayout(goal_frame)
        goal_vbox.setContentsMargins(14, 12, 14, 12)
        goal_vbox.setSpacing(6)
        self._goal_hdr = QLabel(tr("fin.tab_goals"))
        self._goal_hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        self._goal_hdr.setStyleSheet(f"color: {_th()['text']};")
        goal_vbox.addWidget(self._goal_hdr)
        self._goal_preview_vbox = QVBoxLayout()
        self._goal_preview_vbox.setSpacing(4)
        goal_vbox.addLayout(self._goal_preview_vbox)
        goal_vbox.addStretch()
        preview_row.addWidget(goal_frame, stretch=1)

        self._vbox.addLayout(preview_row)

        # ── 5. Accounts strip ──────────────────────────────────────────────
        acc_hdr_row, self._acc_hdr_lbl = _section_header(tr("fin.tab_accounts"))
        self._vbox.addLayout(acc_hdr_row)
        self._acc_row = QHBoxLayout()
        self._acc_row.setSpacing(10)
        self._vbox.addLayout(self._acc_row)

        self._vbox.addStretch(1)
        self._charts_ready = True

    def refresh(self, days: int = 30):
        self._ensure_charts()

        # ── KPIs ──────────────────────────────────────────────────────────
        summary  = self._svc.summary(days)
        bal_dict = self._svc.total_balance()
        inc  = summary.get("income", 0)
        exp  = summary.get("expenses", 0)
        net  = summary.get("net", 0)
        avg  = summary.get("avg_per_day", 0)

        self._kpi_bal.set_value(_fmt_total_balance(bal_dict))
        self._kpi_inc.set_value(_fmt_amount(inc))
        self._kpi_exp.set_value(_fmt_amount(exp))
        self._kpi_net.set_value(("+" if net >= 0 else "") + _fmt_amount(net))
        self._kpi_avg.set_value(_fmt_amount(avg) + "/d")

        # ── Income vs Expenses grouped bar chart ──────────────────────────
        self._bar_chart.clear()
        flow = self._svc.daily_flow(days)  # list of (date_str, inc, exp) tuples
        if flow:
            n = len(flow)
            xs = list(range(n))
            inc_ys = [r[1] for r in flow]
            exp_ys = [r[2] for r in flow]
            bw = max(0.12, min(0.28, 0.6 / max(n / 10, 1)))  # adaptive bar width
            gap = bw * 0.18
            inc_bars = pg.BarGraphItem(
                x=[x - bw / 2 - gap / 2 for x in xs], height=inc_ys, width=bw,
                brush=pg.mkBrush(_fc("inc") + "cc"), pen=pg.mkPen(None),
            )
            exp_bars = pg.BarGraphItem(
                x=[x + bw / 2 + gap / 2 for x in xs], height=exp_ys, width=bw,
                brush=pg.mkBrush(_fc("exp") + "cc"), pen=pg.mkPen(None),
            )
            self._bar_chart.addItem(inc_bars)
            self._bar_chart.addItem(exp_bars)
            # Date tick labels (every ~7 labels max)
            step = max(1, n // 7)
            ticks = [(i, flow[i][0][5:]) for i in range(0, n, step)]  # "MM-DD"
            self._bar_chart.getAxis("bottom").setTicks([ticks])
            self._bar_chart.getViewBox().enableAutoRange()
        else:
            self._bar_chart.getAxis("bottom").setTicks(None)
            self._bar_chart.getViewBox().setRange(xRange=[0, 1], yRange=[0, 1], padding=0)

        # ── Expense donut ─────────────────────────────────────────────────
        exp_cats = self._svc.expense_by_category(days)  # (id, name, color, icon, total)
        self._exp_donut.set_data(
            [(r[4], r[2], f"{r[3]}{r[1]}") for r in exp_cats if r[4] > 0]
        )

        # ── Recent transactions ───────────────────────────────────────────
        while self._recent_vbox.count():
            item = self._recent_vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for tx in self._svc.recent_transactions(limit=6):
            self._recent_vbox.addWidget(_TxRow(tx))

        # ── Budget mini-preview ───────────────────────────────────────────
        while self._budget_preview_vbox.count():
            item = self._budget_preview_vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        budgets = self._svc.budget_status(days)
        if budgets:
            for b in budgets[:3]:
                pct = int(b.spent / b.limit_amount * 100) if b.limit_amount > 0 else 0
                danger = pct >= 90
                badge_color = _fc("exp") if danger else (_fc("xfer") if pct >= 75 else _fc("inc"))

                brow = QWidget()
                brow_v = QVBoxLayout(brow)
                brow_v.setContentsMargins(0, 2, 0, 2)
                brow_v.setSpacing(4)

                top = QHBoxLayout()
                top.setSpacing(6)
                name = QLabel(f"{b.category_icon} {b.category_name}" if b.category_icon else b.category_name)
                name.setFont(QFont("Segoe UI", 11))
                name.setStyleSheet(f"color: {_th()['text']};")
                amt_lbl = QLabel(f"{_fmt_amount(b.spent)} / {_fmt_amount(b.limit_amount)}")
                amt_lbl.setFont(QFont("Segoe UI", 10))
                amt_lbl.setStyleSheet(f"color: {_th()['text_sec']};")
                pct_lbl = QLabel(f"{pct}%")
                pct_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                pct_lbl.setStyleSheet(f"color: {badge_color};")
                pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
                top.addWidget(name, stretch=1)
                top.addWidget(amt_lbl)
                top.addWidget(pct_lbl)

                bar = QProgressBar()
                bar.setObjectName("FinBudgetBarDanger" if danger else "FinBudgetBar")
                bar.setRange(0, 100)
                bar.setValue(min(pct, 100))
                bar.setFixedHeight(6)
                bar.setTextVisible(False)

                brow_v.addLayout(top)
                brow_v.addWidget(bar)
                self._budget_preview_vbox.addWidget(brow)
        else:
            el = QLabel(tr("fin.no_budgets"))
            el.setFont(QFont("Segoe UI", 11))
            el.setStyleSheet(f"color: {_th()['text_sec']};")
            self._budget_preview_vbox.addWidget(el)

        # ── Goals mini-preview ────────────────────────────────────────────
        while self._goal_preview_vbox.count():
            item = self._goal_preview_vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        goals = self._svc.list_goals()
        if goals:
            for g in goals[:2]:
                card = _GoalCard(g)
                self._goal_preview_vbox.addWidget(card)
        else:
            el = QLabel(tr("fin.no_goals"))
            el.setFont(QFont("Segoe UI", 11))
            el.setStyleSheet(f"color: {_th()['text_sec']};")
            self._goal_preview_vbox.addWidget(el)

        # ── Accounts strip ────────────────────────────────────────────────
        while self._acc_row.count():
            item = self._acc_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        accounts = self._svc.list_accounts()
        total_bal = sum(abs(a.balance) for a in accounts) or 0.0
        for a in accounts:
            self._acc_row.addWidget(_AccountCard(a, total_balance=total_bal), stretch=1)
        if not accounts:
            el = QLabel(tr("fin.no_accounts"))
            el.setFont(QFont("Segoe UI", 11))
            el.setStyleSheet(f"color: {_th()['text_sec']};")
            self._acc_row.addWidget(el)
        self._acc_row.addStretch()

    def retranslate(self):
        self._kpi_bal.set_label(tr("fin.kpi_balance"))
        self._kpi_inc.set_label(tr("fin.kpi_income"))
        self._kpi_exp.set_label(tr("fin.kpi_expenses"))
        self._kpi_net.set_label(tr("fin.kpi_net"))
        self._kpi_avg.set_label(tr("fin.kpi_avg_day"))
        if self._charts_ready:
            self._chart_hdr_lbl.setText(tr("fin.chart_inc_exp"))
            self._tx_hdr.setText(tr("fin.recent_transactions"))
            self._bud_hdr.setText(tr("fin.tab_budgets"))
            self._goal_hdr.setText(tr("fin.tab_goals"))
            self._acc_hdr_lbl.setText(tr("fin.tab_accounts"))
            self._exp_donut._title = tr("fin.chart_exp_by_cat")
            self._exp_donut.update()

    def apply_theme(self):
        # Update KPI accent colours for new theme
        for card, key in (
            (self._kpi_bal, "bal"), (self._kpi_inc, "inc"), (self._kpi_exp, "exp"),
            (self._kpi_net, "goal"), (self._kpi_avg, "xfer"),
        ):
            card.set_accent(_fc(key))
            card.apply_theme()
        if self._charts_ready:
            th = _th()
            fg = _ts()
            pg.setConfigOptions(background="#00000000", foreground=fg, antialias=True)
            self._bar_chart.setBackground(None)  # always transparent
            for axis in ("bottom", "left"):
                self._bar_chart.getAxis(axis).setTextPen(pg.mkPen(fg))
                self._bar_chart.getAxis(axis).setPen(pg.mkPen(color=fg, width=1))


# ── Overview tab (state-switching shell) ──────────────────────────────────────

class _OverviewTab(QWidget):
    """Shows either empty-state or populated dashboard depending on data."""

    def __init__(self, svc: FinanceService,
                 on_add_tx: Callable, on_add_account: Callable, on_load_demo: Callable,
                 parent=None):
        super().__init__(parent)
        self._svc = svc

        self._inner_stack = QStackedWidget()

        self._empty = _EmptyState(on_add_tx, on_add_account, on_load_demo)
        self._dashboard = _Dashboard(svc)

        self._inner_stack.addWidget(self._empty)     # 0
        self._inner_stack.addWidget(self._dashboard) # 1

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._inner_stack)

    def refresh(self, days: int = 30):
        has_data = self._svc.transaction_count() > 0
        self._inner_stack.setCurrentIndex(1 if has_data else 0)
        if has_data:
            self._dashboard.refresh(days)

    def apply_theme(self):
        self._dashboard.apply_theme()

    def retranslate(self):
        self._dashboard.retranslate()


# ── Sub-tabs ──────────────────────────────────────────────────────────────────

class _TransactionsTab(QWidget):
    data_changed = pyqtSignal()

    def __init__(self, svc: FinanceService, parent=None):
        super().__init__(parent)
        self._svc = svc
        self._filter_type: Optional[str] = None
        self._days = 30

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        self._btns: list[QPushButton] = []
        for key, label in [
            (None,       tr("fin.filter_all")),
            ("income",   tr("fin.type_income")),
            ("expense",  tr("fin.type_expense")),
            ("transfer", tr("fin.type_transfer")),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("FilterBtn")
            btn.setCheckable(True)
            btn.setProperty("tx_type", key)
            btn.clicked.connect(lambda _checked, k=key: self._set_filter(k))
            self._btns.append(btn)
            filter_row.addWidget(btn)
        self._btns[0].setChecked(True)

        self._search = QLineEdit()
        self._search.setObjectName("Search")
        self._search.setPlaceholderText(tr("fin.search_placeholder"))
        self._search.textChanged.connect(lambda _: self._populate())
        filter_row.addStretch()
        filter_row.addWidget(self._search)
        outer.addLayout(filter_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._inner = QWidget()
        self._inner.setAutoFillBackground(False)
        self._list_vbox = QVBoxLayout(self._inner)
        self._list_vbox.setSpacing(6)
        self._list_vbox.setContentsMargins(0, 0, 8, 16)
        self._list_vbox.addStretch()
        scroll.setWidget(self._inner)
        outer.addWidget(scroll)

    def _set_filter(self, key):
        self._filter_type = key
        for btn in self._btns:
            btn.setChecked(btn.property("tx_type") == key)
        self._populate()

    def _populate(self):
        while self._list_vbox.count() > 1:
            item = self._list_vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        search = self._search.text().strip() or None
        txs = self._svc.list_transactions(days=self._days, tx_type=self._filter_type, search=search)
        if not txs:
            lbl = QLabel(tr("fin.no_transactions"))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {_th()['text_sec']}; font-size: 13px;")
            self._list_vbox.insertWidget(0, lbl)
            return
        for i, tx in enumerate(txs):
            self._list_vbox.insertWidget(i, _TxRow(tx, on_delete=lambda tid=tx.id: self._delete_tx(tid)))

    def _delete_tx(self, tx_id: int):
        self._svc.delete_transaction(tx_id)
        self._populate()
        self.data_changed.emit()

    def refresh(self, days: int = 30):
        self._days = days
        self._populate()


class _BudgetsTab(QWidget):
    data_changed = pyqtSignal()

    def __init__(self, svc: FinanceService, parent=None):
        super().__init__(parent)
        self._svc = svc
        self._days = 30
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)
        top = QHBoxLayout()
        top.addStretch()
        self._btn_add = QPushButton(f"+ {tr('fin.add_budget')}")
        self._btn_add.setObjectName("FilterBtn")
        top.addWidget(self._btn_add)
        outer.addLayout(top)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._inner = QWidget()
        self._inner.setAutoFillBackground(False)
        self._vbox = QVBoxLayout(self._inner)
        self._vbox.setSpacing(10)
        self._vbox.setContentsMargins(0, 0, 8, 16)
        self._vbox.addStretch()
        scroll.setWidget(self._inner)
        outer.addWidget(scroll)

    def _add_expense(self, budget):
        from features.finance.create_transaction.ui import AddTransactionDialog
        dlg = AddTransactionDialog(self._svc, self, prefill_type="expense")
        if dlg.exec():
            data = dlg.result_data()
            if data and data.get("account_id") is not None:
                self._svc.add_transaction(**data)
                self.refresh(self._days)
                self.data_changed.emit()

    def refresh(self, days: int = 30):
        self._days = days
        while self._vbox.count() > 1:
            item = self._vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        budgets = self._svc.budget_status(days)
        if not budgets:
            lbl = QLabel(tr("fin.no_budgets"))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {_th()['text_sec']}; font-size: 13px;")
            self._vbox.insertWidget(0, lbl)
            return
        for i, b in enumerate(budgets):
            self._vbox.insertWidget(i, _BudgetCard(b, on_add_expense=lambda bud=b: self._add_expense(bud)))

    @property
    def btn_add(self) -> QPushButton:
        return self._btn_add


class _GoalsTab(QWidget):
    data_changed = pyqtSignal()

    def __init__(self, svc: FinanceService, parent=None):
        super().__init__(parent)
        self._svc = svc
        self._days = 30
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)
        top = QHBoxLayout()
        top.addStretch()
        self._btn_add = QPushButton(f"+ {tr('fin.add_goal')}")
        self._btn_add.setObjectName("FilterBtn")
        top.addWidget(self._btn_add)
        outer.addLayout(top)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._inner = QWidget()
        self._inner.setAutoFillBackground(False)
        self._vbox = QVBoxLayout(self._inner)
        self._vbox.setSpacing(10)
        self._vbox.setContentsMargins(0, 0, 8, 16)
        self._vbox.addStretch()
        scroll.setWidget(self._inner)
        outer.addWidget(scroll)

    def _deposit(self, goal):
        from PyQt6.QtWidgets import QInputDialog
        val, ok = QInputDialog.getDouble(
            self,
            tr("fin.goal_deposit_title"),
            f"{goal.name}\n{tr('fin.goal_deposit_prompt')}",
            value=0.0, min=0.0, max=1_000_000_000.0, decimals=2,
        )
        if ok and val > 0:
            new_amount = min(goal.target_amount, goal.current_amount + val)
            self._svc.update_goal(goal.id, current_amount=new_amount)
            self.refresh(self._days)
            self.data_changed.emit()

    def refresh(self, days: int = 30):
        self._days = days
        while self._vbox.count() > 1:
            item = self._vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        goals = self._svc.list_goals()
        if not goals:
            lbl = QLabel(tr("fin.no_goals"))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {_th()['text_sec']}; font-size: 13px;")
            self._vbox.insertWidget(0, lbl)
            return
        for i, g in enumerate(goals):
            self._vbox.insertWidget(i, _GoalCard(g, on_deposit=lambda goal=g: self._deposit(goal)))

    @property
    def btn_add(self) -> QPushButton:
        return self._btn_add


class _AccountsTab(QWidget):
    def __init__(self, svc: FinanceService, parent=None):
        super().__init__(parent)
        self._svc = svc
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)
        self._total_lbl = QLabel()
        self._total_lbl.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        self._total_lbl.setStyleSheet(f"color: {_th()['text']};")
        outer.addWidget(self._total_lbl)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._inner = QWidget()
        self._inner.setAutoFillBackground(False)
        self._grid = QGridLayout(self._inner)
        self._grid.setSpacing(10)
        scroll.setWidget(self._inner)
        outer.addWidget(scroll)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_add = QPushButton(f"+ {tr('fin.add_account')}")
        self._btn_add.setObjectName("FilterBtn")
        btn_row.addWidget(self._btn_add)
        outer.addLayout(btn_row)

    def refresh(self, days: int = 30):
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        # clear previous stretch rows
        for r in range(self._grid.rowCount()):
            self._grid.setRowStretch(r, 0)
        bal_dict = self._svc.total_balance()
        self._total_lbl.setText(f"{tr('fin.total_balance')}: {_fmt_total_balance(bal_dict)}")
        accounts = self._svc.list_accounts()
        if not accounts:
            lbl = QLabel(tr("fin.no_accounts"))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {_th()['text_sec']}; font-size: 13px;")
            self._grid.addWidget(lbl, 0, 0, 1, 2)
            return
        total_bal = sum(abs(a.balance) for a in accounts) or 0.0
        for i, a in enumerate(accounts):
            self._grid.addWidget(_AccountCard(a, total_balance=total_bal), i // 2, i % 2)
        # push cards to top — stretch fills remaining space
        last_row = (len(accounts) - 1) // 2 + 1
        self._grid.setRowStretch(last_row, 1)

    @property
    def btn_add(self) -> QPushButton:
        return self._btn_add


# ── FinancePage ───────────────────────────────────────────────────────────────

class FinancePage(QWidget):
    """Finance workspace — right_stack index 5, or inside FinanceWindow."""

    data_changed     = pyqtSignal()   # emitted after any write to finance data
    popout_requested = pyqtSignal()   # embedded page: user clicked "open in window"
    dock_requested   = pyqtSignal()   # windowed page: user clicked "dock back"

    _PERIODS = [
        ("fin.period_7d",    7),
        ("fin.period_30d",  30),
        ("fin.period_90d",  90),
        ("fin.period_month", 0),
        ("fin.period_year", -1),
    ]
    _TABS = [
        "fin.tab_overview",
        "fin.tab_transactions",
        "fin.tab_budgets",
        "fin.tab_goals",
        "fin.tab_accounts",
    ]

    def __init__(self, finance_svc: FinanceService, popout_mode: bool = False, parent=None):
        super().__init__(parent)
        self._svc = finance_svc
        self._days = 30
        self._popout_mode = popout_mode

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 12, 8, 12)
        root.setSpacing(10)

        # ── Header: period buttons + add-tx ───────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(6)
        self._period_btns: list[QPushButton] = []
        for key, days in self._PERIODS:
            btn = QPushButton(tr(key))
            btn.setObjectName("FilterBtn")
            btn.setCheckable(True)
            btn.setProperty("days_val", days)
            btn.clicked.connect(lambda _, d=days: self._set_period(d))
            self._period_btns.append(btn)
            header.addWidget(btn)
        self._period_btns[1].setChecked(True)
        header.addStretch()
        self._btn_add_tx = QPushButton(f"+ {tr('fin.add_transaction')}")
        self._btn_add_tx.setCursor(Qt.CursorShape.PointingHandCursor)
        _bal = _fc("bal")
        self._btn_add_tx.setStyleSheet(f"""
            QPushButton {{
                background: {_bal};
                border: none;
                border-radius: 16px;
                color: #ffffff;
                font-size: 14px;
                font-weight: 600;
                padding: 0 26px;
                min-height: 38px;
            }}
            QPushButton:hover {{ background: {_bal}cc; }}
            QPushButton:pressed {{ background: {_bal}99; }}
        """)
        self._btn_add_tx.clicked.connect(self._on_add_transaction)
        header.addWidget(self._btn_add_tx)

        # Pop-out / dock-back button
        self._btn_window = QPushButton()
        self._btn_window.setObjectName("FilterBtn")
        self._btn_window.setFixedSize(28, 28)
        self._btn_window.setIcon(_tinted_icon(_ICON_POPOUT, _ts()))
        self._btn_window.setIconSize(QSize(14, 14))
        self._btn_window.setToolTip(tr("fin.popout"))
        self._btn_window.clicked.connect(self._on_btn_window_clicked)
        header.addWidget(self._btn_window)
        if popout_mode:
            self.set_popout_mode(True)

        root.addLayout(header)

        # ── Tab bar ───────────────────────────────────────────────────────
        tab_bar = QHBoxLayout()
        tab_bar.setSpacing(4)
        self._tab_btns: list[QPushButton] = []
        for i, key in enumerate(self._TABS):
            btn = QPushButton(tr(key))
            btn.setObjectName("FilterBtn")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, idx=i: self._switch_tab(idx))
            self._tab_btns.append(btn)
            tab_bar.addWidget(btn)
        tab_bar.addStretch()
        root.addLayout(tab_bar)
        self._tab_btns[0].setChecked(True)

        # ── Tab stack ─────────────────────────────────────────────────────
        self._stack = QStackedWidget()
        root.addWidget(self._stack)

        self._overview_tab = _OverviewTab(
            self._svc,
            on_add_tx=self._on_add_transaction,
            on_add_account=self._on_add_account,
            on_load_demo=self._on_load_demo,
        )
        self._tx_tab       = _TransactionsTab(self._svc)
        self._budgets_tab  = _BudgetsTab(self._svc)
        self._goals_tab    = _GoalsTab(self._svc)
        self._accounts_tab = _AccountsTab(self._svc)

        for tab in (self._overview_tab, self._tx_tab, self._budgets_tab,
                    self._goals_tab, self._accounts_tab):
            self._stack.addWidget(tab)

        self._budgets_tab.btn_add.clicked.connect(self._on_add_budget)
        self._goals_tab.btn_add.clicked.connect(self._on_add_goal)
        self._accounts_tab.btn_add.clicked.connect(self._on_add_account)

        # Propagate data writes from sub-tabs up through FinancePage
        self._goals_tab.data_changed.connect(self.data_changed)
        self._tx_tab.data_changed.connect(self._on_tx_deleted)
        self._budgets_tab.data_changed.connect(self.data_changed)

    # ── Navigation ────────────────────────────────────────────────────────

    def _set_period(self, days: int):
        self._days = days
        for btn in self._period_btns:
            btn.setChecked(btn.property("days_val") == days)
        self._refresh_current_tab()

    def _switch_tab(self, idx: int):
        for i, btn in enumerate(self._tab_btns):
            btn.setChecked(i == idx)
        self._stack.setCurrentIndex(idx)
        self._refresh_current_tab()

    def _refresh_current_tab(self):
        tabs = [self._overview_tab, self._tx_tab, self._budgets_tab,
                self._goals_tab, self._accounts_tab]
        idx = self._stack.currentIndex()
        if 0 <= idx < len(tabs):
            tabs[idx].refresh(self._days)

    # ── Public API ────────────────────────────────────────────────────────

    def refresh(self):
        self._refresh_current_tab()

    def retranslate(self):
        """Update all static translatable strings and rebuild dynamic content."""
        for btn, (key, _) in zip(self._period_btns, self._PERIODS):
            btn.setText(tr(key))
        for btn, key in zip(self._tab_btns, self._TABS):
            btn.setText(tr(key))
        self._btn_add_tx.setText(f"+ {tr('fin.add_transaction')}")
        self._btn_window.setToolTip(
            tr("fin.dock_back") if self._popout_mode else tr("fin.popout")
        )
        self._overview_tab.retranslate()
        self._refresh_current_tab()

    def apply_theme(self):
        self._overview_tab.apply_theme()
        # Update popout icon colour for current theme
        icon_color = _ts()
        icon_path = _ICON_DOCKBACK if self._popout_mode else _ICON_POPOUT
        self._btn_window.setIcon(_tinted_icon(icon_path, icon_color))
        # Rebuild dynamic widgets (TxRow, BudgetCard, GoalCard) with new theme colours
        self._refresh_current_tab()

    def _on_btn_window_clicked(self):
        """Emit the correct signal depending on current presentation mode."""
        if self._popout_mode:
            self.dock_requested.emit()
        else:
            self.popout_requested.emit()

    def set_popout_mode(self, mode: bool):
        """Switch between embedded (False) and undocked-window (True) presentation.

        In window (popout) mode the FinanceWindow owns a dedicated title-bar
        dock button, so we hide the small inline button to avoid duplication.
        """
        self._popout_mode = mode
        if mode:
            self._btn_window.setVisible(True)
            self._btn_window.setIcon(_tinted_icon(_ICON_DOCKBACK, _ts()))
            self._btn_window.setIconSize(QSize(14, 14))
            self._btn_window.setToolTip(tr("fin.dock_back"))
        else:
            self._btn_window.setVisible(True)
            self._btn_window.setIcon(_tinted_icon(_ICON_POPOUT, _ts()))
            self._btn_window.setIconSize(QSize(14, 14))
            self._btn_window.setToolTip(tr("fin.popout"))

    # ── Dialog handlers ───────────────────────────────────────────────────

    def _on_add_transaction(self):
        from features.finance.create_transaction.ui import AddTransactionDialog
        dlg = AddTransactionDialog(self._svc, self)
        if dlg.exec():
            data = dlg.result_data()
            if data and data.get("account_id") is not None:
                self._svc.add_transaction(**data)
                self._refresh_current_tab()
                self.data_changed.emit()

    def _on_tx_deleted(self):
        self._overview_tab.refresh(self._days)
        self.data_changed.emit()

    def _on_add_budget(self):
        from features.finance.create_transaction.ui import AddBudgetDialog
        dlg = AddBudgetDialog(self._svc, self)
        if dlg.exec():
            data = dlg.result_data()
            if data.get("category_id") is not None:
                self._svc.add_budget(**data)
                self._budgets_tab.refresh(self._days)
                self.data_changed.emit()

    def _on_add_goal(self):
        from features.finance.create_transaction.ui import AddGoalDialog
        dlg = AddGoalDialog(self)
        if dlg.exec():
            data = dlg.result_data()
            if data.get("name"):
                self._svc.add_goal(**data)
                self._goals_tab.refresh(self._days)
                self.data_changed.emit()

    def _on_add_account(self):
        from features.finance.create_transaction.ui import AddAccountDialog
        dlg = AddAccountDialog(self)
        if dlg.exec():
            data = dlg.result_data()
            if data.get("name"):
                self._svc.add_account(**data)
                self._accounts_tab.refresh(self._days)
                # Refresh overview in case we were on empty state
                if self._stack.currentIndex() == 0:
                    self._overview_tab.refresh(self._days)
                self.data_changed.emit()

    def _on_load_demo(self):
        self._svc.load_demo_data()
        self._refresh_current_tab()
        self.data_changed.emit()


# ── Pop-out Finance window ────────────────────────────────────────────────────

class FinanceWindow(QMainWindow):
    """Standalone native window: FinanceSidebar (left) + FinancePage (right).

    The FinancePage is reparented INTO this window on undock and reparented back
    into the right_stack on dock-back.  No duplicate FinancePage is ever created.
    A fresh FinanceSidebar is created for the window lifespan (destroyed on close).
    """

    window_closed = pyqtSignal()

    def __init__(self, finance_page: "FinancePage", settings,
                 finance_svc=None, parent=None):
        super().__init__(parent)
        self._settings  = settings
        self._fin_page  = finance_page   # direct ref for showEvent refresh

        self.setWindowTitle("Finance — toXo")

        geom = settings.value("finance_window/geometry")
        if geom:
            self.restoreGeometry(geom)
        else:
            self.resize(1180, 720)

        icon_path = IMAGES_DIR / "app_icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # ── Central container ─────────────────────────────────────────────
        from PyQt6.QtWidgets import (
            QHBoxLayout as _HBox, QVBoxLayout as _VBox, QWidget as _QW,
        )
        from widgets.finance_sidebar.ui import FinanceSidebar

        container = _QW()
        container.setObjectName("FinWinContainer")
        # Use ID-scoped CSS so background does NOT cascade into child widgets
        container.setStyleSheet("QWidget#FinWinContainer { background: transparent; }")
        vbox = _VBox(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # ── Sidebar + finance page ─────────────────────────────────────────
        body = _QW()
        body.setObjectName("FinWinBody")
        body.setStyleSheet("QWidget#FinWinBody { background: transparent; }")
        h = _HBox(body)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        self._win_sidebar = FinanceSidebar()
        # Connect sidebar signals to open the pre-filled dialog via FinancePage
        if finance_svc is not None:
            self._win_sidebar.use_as_income.connect(
                lambda v, s=finance_svc: self._on_calc_use(v, "income", s))
            self._win_sidebar.use_as_expense.connect(
                lambda v, s=finance_svc: self._on_calc_use(v, "expense", s))

        h.addWidget(self._win_sidebar)
        h.addWidget(finance_page, 1)   # reparents finance_page into this container
        vbox.addWidget(body, 1)

        self._container = container
        self.setCentralWidget(container)

        # Apply current theme immediately
        self._apply_win_theme(_styles._active_theme)

    def _apply_win_theme(self, theme=False):
        """Apply dark/light/glass theme to all elements of the standalone window.
        Accepts theme name string or legacy bool (True=light).
        """
        if isinstance(theme, bool):
            theme = "light" if theme else "dark"
        is_light = theme == "light"
        is_glass = theme == "glass"
        th = _styles._THEMES.get(theme, _styles._THEMES["dark"])
        bg = th["bg_dark"]

        # Glass: let _GlassBg widget provide the background (same as main window).
        # Dark/light: explicit solid background on the container.
        if is_glass:
            self._container.setStyleSheet(
                "QWidget#FinWinContainer { background: transparent; }")
            _styles.install_glass_bg(self)
        else:
            _styles.remove_glass_bg(self)
            self._container.setStyleSheet(
                f"QWidget#FinWinContainer {{ background: {bg}; }}")
        self._win_sidebar.apply_theme(theme)

    def _on_calc_use(self, amount: float, tx_type: str, svc):
        from features.finance.create_transaction.ui import AddTransactionDialog
        dlg = AddTransactionDialog(svc, self,
                                   prefill_type=tx_type,
                                   prefill_amount=round(amount, 2))
        if dlg.exec():
            data = dlg.result_data()
            if data and data.get("account_id") is not None:
                svc.add_transaction(**data)
                self._fin_page.refresh()
                self._fin_page.data_changed.emit()

    def showEvent(self, event):
        super().showEvent(event)
        self._fin_page.show()
        self._fin_page.refresh()

    def closeEvent(self, event):
        self._settings.setValue("finance_window/geometry", self.saveGeometry())
        self.window_closed.emit()
        super().closeEvent(event)
