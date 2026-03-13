"""Finance sidebar — compact financial calculator with quick transaction actions."""
from __future__ import annotations
from shared.config.paths import ICONS_DIR

import math
from typing import Optional

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QWidget, QGridLayout, QApplication, QSizePolicy,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QKeyEvent, QIcon, QColor

from shared.i18n import tr


# ── Icon paths (resolved lazily to avoid import-time path issues) ─────────────
def _icon(name: str) -> QIcon:
    from pathlib import Path
    p = ICONS_DIR / name
    return QIcon(str(p)) if p.exists() else QIcon()


# ── Palette tokens ────────────────────────────────────────────────────────────
_INC = "#30d158"
_EXP = "#ff453a"
_ACC = "#0a84ff"


# ─────────────────────────────────────────────────────────────────────────────
# Display
# ─────────────────────────────────────────────────────────────────────────────

class _CalcDisplay(QFrame):
    """Two-line display: small expression above, large current value below."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FinCalcDisplay")
        self.setStyleSheet("""
            QFrame#FinCalcDisplay {
                background: rgba(0,0,0,0.25);
                border-radius: 10px;
                border: 1px solid rgba(255,255,255,0.07);
            }
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(3)

        self._expr = QLabel("")
        self._expr.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._expr.setStyleSheet("color: rgba(255,255,255,0.38); background: transparent;")
        f_small = QFont(); f_small.setPointSize(9)
        self._expr.setFont(f_small)
        self._expr.setFixedHeight(18)
        lay.addWidget(self._expr)

        self._main = QLabel("0")
        self._main.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._main.setStyleSheet("color: #ffffff; background: transparent;")
        _f0 = QFont(); _f0.setPointSize(22); _f0.setWeight(QFont.Weight.Bold)
        self._main.setFont(_f0)
        lay.addWidget(self._main)

        # Fixed height: 10(top) + 18(expr) + 3(spacing) + 34(main) + 12(bottom) + rounding
        self.setFixedHeight(80)

    def set_expr(self, text: str):
        self._expr.setText(text)

    def set_main(self, text: str, is_result: bool = False):
        length = len(text.replace("-", "").replace(".", ""))
        pt = 22 if length < 9 else (17 if length < 13 else 13)
        f = QFont()
        f.setPointSize(pt)
        f.setWeight(QFont.Weight.Bold)
        self._main.setFont(f)
        color = "#30d158" if is_result else "#ffffff"
        self._main.setStyleSheet(f"color: {color}; background: transparent;")
        self._main.setText(text)


# ─────────────────────────────────────────────────────────────────────────────
# Keypad button
# ─────────────────────────────────────────────────────────────────────────────

_BTN_BASE = """
    QPushButton {{
        background: {bg};
        color: {fg};
        border: 1px solid {border};
        border-radius: 7px;
        font-size: {fs}px;
        font-weight: {fw};
        min-height: 34px;
    }}
    QPushButton:hover  {{ background: {hov}; }}
    QPushButton:pressed {{ background: {pre}; }}
"""

def _gl(t: str, b: str) -> str:
    """Shorthand for a vertical Qt linear gradient stop:top → stop:bottom."""
    return f"qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {t},stop:1 {b})"

_DB = "rgba(255,255,255,0.11)"   # dark border — uniform glow on all sides

_STYLES_DARK = {
    "digit": _BTN_BASE.format(
        bg="rgba(255,255,255,0.08)", fg="#ffffff", border=_DB,
        hov="rgba(255,255,255,0.14)", pre="rgba(255,255,255,0.04)",
        fs=14, fw=500),
    "op":    _BTN_BASE.format(
        bg="rgba(255,255,255,0.13)", fg="#ffffff", border=_DB,
        hov="rgba(255,255,255,0.20)", pre="rgba(255,255,255,0.07)",
        fs=15, fw=600),
    "eq":    _BTN_BASE.format(
        bg="#0a84ff", fg="#ffffff", border="rgba(100,180,255,0.35)",
        hov="#409cff", pre="#0068d6",
        fs=16, fw=700),
    "clear": _BTN_BASE.format(
        bg="rgba(255,69,58,0.20)", fg="#ff6b63", border="rgba(255,69,58,0.30)",
        hov="rgba(255,69,58,0.32)", pre="rgba(255,69,58,0.12)",
        fs=13, fw=600),
    "back":  _BTN_BASE.format(
        bg="rgba(255,255,255,0.10)", fg="rgba(255,255,255,0.65)", border=_DB,
        hov="rgba(255,255,255,0.17)", pre="rgba(255,255,255,0.05)",
        fs=14, fw=500),
}

_GB = "rgba(130,170,255,0.18)"   # glass border — blue-tinted uniform glow

_STYLES_GLASS = {
    "digit": _BTN_BASE.format(
        bg="rgba(55,95,175,0.18)", fg="#e8f0ff", border=_GB,
        hov="rgba(65,110,195,0.28)", pre="rgba(40,75,155,0.12)",
        fs=14, fw=500),
    "op":    _BTN_BASE.format(
        bg="rgba(65,110,195,0.22)", fg="#b0d0ff", border=_GB,
        hov="rgba(75,125,215,0.32)", pre="rgba(50,90,175,0.14)",
        fs=15, fw=600),
    "eq":    _BTN_BASE.format(
        bg="#5ea2ff", fg="#ffffff", border="rgba(140,190,255,0.40)",
        hov="#7bb4ff", pre="#4a8de8",
        fs=16, fw=700),
    "clear": _BTN_BASE.format(
        bg="rgba(255,107,107,0.18)", fg="#ff8a8a", border="rgba(255,107,107,0.28)",
        hov="rgba(255,107,107,0.28)", pre="rgba(255,107,107,0.10)",
        fs=13, fw=600),
    "back":  _BTN_BASE.format(
        bg="rgba(60,100,200,0.14)", fg="rgba(180,210,255,0.70)", border=_GB,
        hov="rgba(70,115,220,0.24)", pre="rgba(45,80,175,0.10)",
        fs=14, fw=500),
}

_LB = "rgba(180,196,220,0.55)"   # light border

_STYLES_LIGHT = {
    "digit": _BTN_BASE.format(
        bg="rgba(255,255,255,0.82)", fg="#3a4a62", border=_LB,
        hov="rgba(255,255,255,0.96)", pre="rgba(225,232,244,0.70)",
        fs=14, fw=500),
    "op":    _BTN_BASE.format(
        bg="rgba(235,242,255,0.85)", fg="#3b69cc", border="rgba(150,185,255,0.40)",
        hov="rgba(225,236,255,0.96)", pre="rgba(205,220,252,0.75)",
        fs=15, fw=600),
    "eq":    _BTN_BASE.format(
        bg="#3b82f6", fg="#ffffff", border="rgba(80,145,255,0.55)",
        hov="#5597f8", pre="#2a6de0",
        fs=16, fw=700),
    "clear": _BTN_BASE.format(
        bg="rgba(255,220,220,0.70)", fg="#c44040", border="rgba(220,150,150,0.40)",
        hov="rgba(255,200,200,0.85)", pre="rgba(240,175,175,0.65)",
        fs=13, fw=600),
    "back":  _BTN_BASE.format(
        bg="rgba(255,255,255,0.82)", fg="#5a6a85", border=_LB,
        hov="rgba(255,255,255,0.96)", pre="rgba(225,232,244,0.70)",
        fs=14, fw=500),
}

_STYLES = _STYLES_DARK   # default; updated by apply_theme

# Map of display label → internal token
_OP_MAP = {"÷": "/", "×": "*", "−": "-"}
_OP_SYM = {v: k for k, v in _OP_MAP.items()}   # "/" → "÷" etc.


class _CalcBtn(QPushButton):
    def __init__(self, label: str, kind: str = "digit", parent=None):
        super().__init__(label, parent)
        self._kind = kind
        self.setStyleSheet(_STYLES.get(kind, _STYLES["digit"]))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def restyle(self, styles: dict):
        self.setStyleSheet(styles.get(self._kind, styles["digit"]))


# ─────────────────────────────────────────────────────────────────────────────
# Calculator core (embedded in sidebar)
# ─────────────────────────────────────────────────────────────────────────────

class _FinCalc(QWidget):
    """Financial calculator: display + keypad + state machine."""

    result_ready = pyqtSignal(float)   # emitted when a clean result is available

    _MAX_LEN = 15

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        # ── State ──────────────────────────────────────────────────────────
        self._left:    Optional[float] = None
        self._op:      Optional[str]   = None   # internal: + - * /
        self._current: str             = ""
        self._just_eq: bool            = False
        self._result:  Optional[float] = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self._display = _CalcDisplay()
        lay.addWidget(self._display)
        lay.addLayout(self._build_keypad())

    # ── Build keypad ───────────────────────────────────────────────────────

    def _build_keypad(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(5)

        # (label, row, col, kind)
        keys = [
            ("C",  0, 0, "clear"), ("⌫",  0, 1, "back"),
            ("%",  0, 2, "op"),    ("÷",  0, 3, "op"),
            ("7",  1, 0, "digit"), ("8",  1, 1, "digit"),
            ("9",  1, 2, "digit"), ("×",  1, 3, "op"),
            ("4",  2, 0, "digit"), ("5",  2, 1, "digit"),
            ("6",  2, 2, "digit"), ("−",  2, 3, "op"),
            ("1",  3, 0, "digit"), ("2",  3, 1, "digit"),
            ("3",  3, 2, "digit"), ("+",  3, 3, "op"),
            ("±",  4, 0, "back"),  ("0",  4, 1, "digit"),
            (".",  4, 2, "digit"), ("=",  4, 3, "eq"),
        ]
        for label, row, col, kind in keys:
            btn = _CalcBtn(label, kind)
            btn.setFixedHeight(36)   # explicit Qt height — grid uses this, not CSS min-height
            grid.addWidget(btn, row, col)
            btn.clicked.connect(lambda _, k=label: self._key(k))

        return grid

    # ── Public ─────────────────────────────────────────────────────────────

    def current_result(self) -> Optional[float]:
        """Return the latest usable numeric value."""
        if self._result is not None:
            return self._result
        if self._current:
            try:
                return float(self._current)
            except ValueError:
                pass
        return None

    def get_display(self) -> _CalcDisplay:
        return self._display

    # ── Key dispatch ───────────────────────────────────────────────────────

    def _key(self, k: str):
        if k in "0123456789":
            self._digit(k)
        elif k == ".":
            self._dot()
        elif k == "C":
            self._clear()
        elif k == "⌫":
            self._backspace()
        elif k == "%":
            self._percent()
        elif k in ("÷", "×", "−", "+"):
            self._operator(_OP_MAP.get(k, k))
        elif k == "=":
            self._equals()
        elif k == "±":
            self._negate()
        self._refresh()

    def _digit(self, d: str):
        if self._just_eq:
            self._left = None; self._op = None
            self._current = ""; self._just_eq = False
            self._result = None
        if self._current == "0":
            self._current = d
        elif len(self._current.replace(".", "").replace("-", "")) < self._MAX_LEN:
            self._current += d

    def _dot(self):
        if self._just_eq:
            self._left = None; self._op = None
            self._current = "0"; self._just_eq = False; self._result = None
        if not self._current:
            self._current = "0"
        if "." not in self._current:
            self._current += "."

    def _clear(self):
        self._left = None; self._op = None
        self._current = ""; self._just_eq = False; self._result = None

    def _backspace(self):
        if not self._just_eq:
            self._current = self._current[:-1]

    def _percent(self):
        if not self._current:
            return
        try:
            val = float(self._current)
        except ValueError:
            return
        if self._op in ("+", "-") and self._left is not None:
            # Financial: 1000 + 10% → add 10% of 1000
            self._current = _fmt(self._left * val / 100)
        else:
            self._current = _fmt(val / 100)

    def _operator(self, op: str):
        self._just_eq = False
        if self._current:
            try:
                val = float(self._current)
            except ValueError:
                val = 0.0
            if self._op is not None and self._left is not None:
                try:
                    self._left = _compute(self._left, self._op, val)
                except ZeroDivisionError:
                    self._clear()
                    self._display.set_expr("")
                    self._display.set_main("Ошибка")
                    return
            else:
                self._left = val
            self._current = ""
        self._op = op

    def _equals(self):
        if self._op is not None and self._left is not None and self._current:
            try:
                right = float(self._current)
                res   = _compute(self._left, self._op, right)
            except (ValueError, ZeroDivisionError):
                self._display.set_expr("")
                self._display.set_main("Ошибка")
                self._clear()
                return
            self._result  = res
            self._current = _fmt(res)
            self._left    = res
            self._op      = None
            self._just_eq = True
            self.result_ready.emit(res)
        elif self._current:
            try:
                self._result = float(self._current)
                self.result_ready.emit(self._result)
            except ValueError:
                pass

    def _negate(self):
        if self._current:
            self._current = self._current[1:] if self._current.startswith("-") \
                            else "-" + self._current
        elif self._left is not None:
            self._left = -self._left

    # ── Display refresh ────────────────────────────────────────────────────

    def _refresh(self):
        # Expression line
        if self._op is not None and self._left is not None:
            sym = _OP_SYM.get(self._op, self._op)
            self._display.set_expr(f"{_fmt(self._left)}  {sym}")
        else:
            self._display.set_expr("")

        # Main value line
        if self._current:
            self._display.set_main(self._current, is_result=self._just_eq)
        elif self._left is not None:
            self._display.set_main(_fmt(self._left))
        else:
            self._display.set_main("0")

    # ── Keyboard passthrough (called by FinanceSidebar) ────────────────────

    def handle_key_event(self, event: QKeyEvent) -> bool:
        """Return True if the event was consumed."""
        key  = event.key()
        text = event.text()

        if text in "0123456789":       self._key(text);  return True
        if text == ".":                self._key(".");   return True
        if text == "+":                self._key("+");   return True
        if text in ("-",):             self._key("−");   return True
        if text in ("*",):             self._key("×");   return True
        if text in ("/",):             self._key("÷");   return True
        if text == "%":                self._key("%");   return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._key("="); return True
        if key == Qt.Key.Key_Backspace:
            self._key("⌫"); return True
        if key == Qt.Key.Key_Escape:
            self._key("C"); return True
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar shell
# ─────────────────────────────────────────────────────────────────────────────

class FinanceSidebar(QFrame):
    """Left sidebar panel for the Finance workspace.

    Contains:
      1. Financial calculator
      2. Quick-action buttons (Use as income / expense / Copy)
    """

    use_as_income  = pyqtSignal(float)
    use_as_expense = pyqtSignal(float)

    WIDTH = 220

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FinSidebar")
        self.setFixedWidth(self.WIDTH)
        # Outer frame: transparent container that holds the glass card
        self.setStyleSheet("QFrame#FinSidebar { background: transparent; border: none; }")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(0)

        # ── Glass card ─────────────────────────────────────────────────────
        self._card = QFrame()
        self._card.setObjectName("FinCalcCard")
        self._card.setStyleSheet("""
            QFrame#FinCalcCard {
                background: rgba(255,255,255,0.22);
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 18px;
            }
        """)
        # Drop shadow for glass depth
        self._shadow = QGraphicsDropShadowEffect()
        self._shadow.setBlurRadius(18)
        self._shadow.setColor(QColor(0, 0, 0, 90))
        self._shadow.setOffset(0, 4)
        self._card.setGraphicsEffect(self._shadow)
        outer.addWidget(self._card)
        outer.addStretch()

        root = QVBoxLayout(self._card)
        root.setContentsMargins(10, 10, 10, 16)
        root.setSpacing(6)

        # ── Title ──────────────────────────────────────────────────────────
        self._title_lbl = QLabel(tr("fin.calc_title"))
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_lbl.setFixedHeight(22)
        f = QFont(); f.setPointSize(11); f.setWeight(QFont.Weight.DemiBold)
        self._title_lbl.setFont(f)
        self._title_lbl.setStyleSheet("color: rgba(255,255,255,0.55); background: transparent;")
        root.addWidget(self._title_lbl)

        # ── Calculator ─────────────────────────────────────────────────────
        self._calc = _FinCalc()
        self._calc.result_ready.connect(self._on_result_ready)
        root.addWidget(self._calc)

        # ── Separator ──────────────────────────────────────────────────────
        self._sep = QFrame()
        self._sep.setFrameShape(QFrame.Shape.HLine)
        self._sep.setFixedHeight(1)
        self._sep.setStyleSheet("background: rgba(255,255,255,0.09);")
        root.addWidget(self._sep)

        # ── Quick actions ──────────────────────────────────────────────────
        root.addWidget(self._build_actions())

        # Keyboard focus so key events reach us
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Apply correct theme on construction (avoids needing a theme-change
        # cycle to get the right look on first startup).
        import app.styles.themes as _styles_mod
        self.apply_theme(_styles_mod._active_theme)

    # ── Quick-action panel ─────────────────────────────────────────────────

    def _build_actions(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(7)

        lbl = QLabel(tr("fin.calc_use_result").upper())
        fl = QFont(); fl.setPointSize(9); fl.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
        lbl.setFont(fl)
        lbl.setStyleSheet("color: rgba(255,255,255,0.45); background: transparent;")
        self._lbl_use_result = lbl
        lay.addWidget(lbl)

        self._btn_income = self._action_btn(
            f"↑  {tr('fin.calc_as_income')}",
            f"background: rgba(48,209,88,0.16); color: {_INC}; "
            f"border: 1px solid rgba(48,209,88,0.28);",
            f"background: rgba(48,209,88,0.26); border: 1px solid rgba(48,209,88,0.38);",
        )
        self._btn_income.clicked.connect(self._emit_income)
        lay.addWidget(self._btn_income)

        self._btn_expense = self._action_btn(
            f"↓  {tr('fin.calc_as_expense')}",
            f"background: rgba(255,69,58,0.16); color: {_EXP}; "
            f"border: 1px solid rgba(255,69,58,0.28);",
            f"background: rgba(255,69,58,0.26); border: 1px solid rgba(255,69,58,0.38);",
        )
        self._btn_expense.clicked.connect(self._emit_expense)
        lay.addWidget(self._btn_expense)

        self._btn_copy = self._action_btn(
            tr("fin.calc_copy"),
            "background: rgba(255,255,255,0.09); color: rgba(255,255,255,0.70); "
            "border: 1px solid rgba(255,255,255,0.12);",
            "background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.18);",
        )
        self._btn_copy.clicked.connect(self._copy)
        lay.addWidget(self._btn_copy)

        self._set_actions_enabled(False)
        return w

    @staticmethod
    def _action_btn(text: str, normal_css: str, hover_css: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(36)
        btn.setStyleSheet(f"""
            QPushButton {{
                {normal_css}
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
                text-align: left;
                padding-left: 10px;
            }}
            QPushButton:hover  {{ {hover_css} }}
            QPushButton:pressed {{ opacity: 0.7; }}
            QPushButton:disabled {{ opacity: 0.30; }}
        """)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    # ── Slots ──────────────────────────────────────────────────────────────

    def _on_result_ready(self, val: float):
        self._set_actions_enabled(val > 0)

    def _set_actions_enabled(self, ok: bool):
        self._btn_income.setEnabled(ok)
        self._btn_expense.setEnabled(ok)
        self._btn_copy.setEnabled(ok)

    def _emit_income(self):
        val = self._calc.current_result()
        if val and val > 0:
            self.use_as_income.emit(abs(val))

    def _emit_expense(self):
        val = self._calc.current_result()
        if val and val > 0:
            self.use_as_expense.emit(abs(val))

    def _copy(self):
        val = self._calc.current_result()
        if val is not None:
            QApplication.clipboard().setText(_fmt(val))

    # ── Retranslate ────────────────────────────────────────────────────────

    def retranslate(self):
        self._title_lbl.setText(tr("fin.calc_title"))
        self._lbl_use_result.setText(tr("fin.calc_use_result").upper())
        self._btn_income.setText(f"↑  {tr('fin.calc_as_income')}")
        self._btn_expense.setText(f"↓  {tr('fin.calc_as_expense')}")
        self._btn_copy.setText(tr("fin.calc_copy"))

    def apply_theme(self, theme=False):
        """Swap full palette for light/dark/glass theme.
        Accepts theme name string ('light'/'dark'/'glass') or legacy bool (True=light).
        """
        if isinstance(theme, bool):
            theme = "light" if theme else "dark"
        is_light = theme == "light"
        is_glass = theme == "glass"
        styles = _STYLES_LIGHT if is_light else _STYLES_GLASS if is_glass else _STYLES_DARK
        disp   = self._calc.get_display()

        if is_glass:
            self.setStyleSheet("""
                QFrame#FinSidebar {
                    background: transparent;
                    border: none;
                    border-top-right-radius: 16px;
                    border-bottom-right-radius: 16px;
                    border-top-left-radius: 8px;
                    border-bottom-left-radius: 8px;
                }
            """)
            self._card.setStyleSheet("""
                QFrame#FinCalcCard {
                    background: qlineargradient(x1:0, y1:0, x2:0.3, y2:1,
                        stop:0 rgba(55,95,175,0.20), stop:1 rgba(18,40,95,0.09));
                    border: 1px solid rgba(100,160,255,0.22);
                    border-radius: 14px;
                }
            """)
            self._shadow.setColor(QColor(0, 0, 0, 100))
            self._shadow.setBlurRadius(40)
            self._shadow.setOffset(0, 12)
            self._title_lbl.setStyleSheet("color: rgba(180,210,255,0.80); background: transparent;")
            disp.setStyleSheet("""
                QFrame#FinCalcDisplay {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(4,10,28,0.55), stop:1 rgba(4,10,28,0.42));
                    border-radius: 12px;
                    border-top: 1px solid rgba(100,150,255,0.18);
                    border-left: 1px solid rgba(80,130,255,0.12);
                    border-right: 1px solid rgba(4,8,20,0.30);
                    border-bottom: 1px solid rgba(4,8,20,0.35);
                }
            """)
            disp._expr.setStyleSheet("color: rgba(150,185,255,0.50); background: transparent;")
            disp._main.setStyleSheet("color: #e8f0ff; background: transparent;")
            self._sep.setStyleSheet("background: rgba(100,150,255,0.14);")
            self._lbl_use_result.setStyleSheet("color: rgba(150,185,255,0.55); background: transparent;")
            # Action buttons — blue-glass tinted
            _ai = _gl("rgba(82,211,138,0.22)", "rgba(82,211,138,0.12)")
            _ah = _gl("rgba(82,211,138,0.32)", "rgba(82,211,138,0.18)")
            _ap = _gl("rgba(82,211,138,0.12)", "rgba(82,211,138,0.08)")
            self._btn_income.setStyleSheet(f"""
                QPushButton {{
                    background: {_ai}; color: #52d38a;
                    border: 1px solid rgba(82,211,138,0.30);
                    border-radius: 10px; font-size: 13px; font-weight: 600;
                    text-align: left; padding-left: 14px; min-height: 36px;
                }}
                QPushButton:hover   {{ background: {_ah}; }}
                QPushButton:pressed  {{ background: {_ap}; }}
                QPushButton:disabled {{ opacity: 0.30; }}
            """)
            _ei = _gl("rgba(255,107,107,0.22)", "rgba(255,107,107,0.12)")
            _eh = _gl("rgba(255,107,107,0.32)", "rgba(255,107,107,0.18)")
            _ep = _gl("rgba(255,107,107,0.12)", "rgba(255,107,107,0.08)")
            self._btn_expense.setStyleSheet(f"""
                QPushButton {{
                    background: {_ei}; color: #ff8a8a;
                    border: 1px solid rgba(255,107,107,0.30);
                    border-radius: 10px; font-size: 13px; font-weight: 600;
                    text-align: left; padding-left: 14px; min-height: 36px;
                }}
                QPushButton:hover   {{ background: {_eh}; }}
                QPushButton:pressed  {{ background: {_ep}; }}
                QPushButton:disabled {{ opacity: 0.30; }}
            """)
            _ci = _gl("rgba(60,100,200,0.14)", "rgba(40,70,160,0.07)")
            _ch = _gl("rgba(70,115,220,0.22)", "rgba(50,85,180,0.12)")
            _cp = _gl("rgba(40,70,160,0.09)", "rgba(30,55,140,0.05)")
            self._btn_copy.setStyleSheet(f"""
                QPushButton {{
                    background: {_ci}; color: rgba(180,210,255,0.85);
                    border: 1px solid rgba(100,150,255,0.22);
                    border-radius: 10px; font-size: 13px; font-weight: 600;
                    min-height: 36px;
                }}
                QPushButton:hover   {{ background: {_ch}; }}
                QPushButton:pressed  {{ background: {_cp}; }}
                QPushButton:disabled {{ opacity: 0.30; }}
            """)
        elif is_light:
            self.setStyleSheet("QFrame#FinSidebar { background: transparent; border: none; }")
            # ── Glass card: translucent panel (simulates backdrop blur) ─────
            # Since Qt has no backdrop-filter, use higher opacity to keep
            # the card clearly readable against the blue-gray sidebar bg.
            self._card.setStyleSheet("""
                QFrame#FinCalcCard {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(255,255,255,0.84),
                        stop:1 rgba(240,245,255,0.74));
                    border: 1px solid rgba(200,215,235,0.65);
                    border-radius: 18px;
                }
            """)
            self._shadow.setColor(QColor(70, 88, 120, 32))
            self._shadow.setBlurRadius(34)
            self._shadow.setOffset(0, 12)
            self._title_lbl.setStyleSheet("color: #66738c; background: transparent;")
            # ── Display: blue-tinted inset ───────────────────────────────────
            disp.setStyleSheet("""
                QFrame#FinCalcDisplay {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(210,220,238,0.55),
                        stop:1 rgba(194,208,228,0.40));
                    border-radius: 10px;
                    border: 1px solid rgba(255,255,255,0.50);
                }
            """)
            disp._expr.setStyleSheet("color: #7e8aa3; background: transparent;")
            disp._main.setStyleSheet("color: #1f2a3d; background: transparent;")
            self._sep.setStyleSheet("background: rgba(191,201,219,0.35);")
            self._lbl_use_result.setStyleSheet("color: #8a95aa; background: transparent;")
            self._btn_income.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(220,248,230,0.80); color: #238b53;
                    border: 1px solid rgba(160,220,180,0.55);
                    border-radius: 8px; font-size: 12px; font-weight: 600;
                    text-align: left; padding-left: 10px; min-height: 32px;
                }}
                QPushButton:hover   {{ background: rgba(195,240,212,0.90); }}
                QPushButton:pressed  {{ background: rgba(175,225,196,0.75); }}
                QPushButton:disabled {{ opacity: 0.30; }}
            """)
            self._btn_expense.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255,220,218,0.80); color: #c44040;
                    border: 1px solid rgba(220,155,155,0.50);
                    border-radius: 8px; font-size: 12px; font-weight: 600;
                    text-align: left; padding-left: 10px; min-height: 32px;
                }}
                QPushButton:hover   {{ background: rgba(255,200,198,0.90); }}
                QPushButton:pressed  {{ background: rgba(240,175,173,0.75); }}
                QPushButton:disabled {{ opacity: 0.30; }}
            """)
            self._btn_copy.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255,255,255,0.70); color: #526080;
                    border: 1px solid rgba(185,200,220,0.55);
                    border-radius: 8px; font-size: 12px; font-weight: 600;
                    min-height: 32px;
                }}
                QPushButton:hover   {{ background: rgba(255,255,255,0.90); }}
                QPushButton:pressed  {{ background: rgba(230,236,248,0.75); }}
                QPushButton:disabled {{ opacity: 0.30; }}
            """)
        else:
            # ── Outer sidebar: transparent (dark bg shows through) ──────────
            self.setStyleSheet("QFrame#FinSidebar { background: transparent; border: none; }")
            # ── Glass card: semi-transparent with bright top-edge highlight ─
            self._card.setStyleSheet("""
                QFrame#FinCalcCard {
                    background: rgba(255,255,255,0.22);
                    border: 1px solid rgba(255,255,255,0.15);
                    border-radius: 18px;
                }
            """)
            self._shadow.setColor(QColor(0, 0, 0, 90))
            self._shadow.setBlurRadius(18)
            self._shadow.setOffset(0, 4)
            self._title_lbl.setStyleSheet("color: rgba(255,255,255,0.55); background: transparent;")
            disp.setStyleSheet("""
                QFrame#FinCalcDisplay {
                    background: rgba(0,0,0,0.30);
                    border-radius: 10px;
                    border: 1px solid rgba(255,255,255,0.07);
                }
            """)
            disp._expr.setStyleSheet("color: rgba(255,255,255,0.38); background: transparent;")
            disp._main.setStyleSheet("color: #ffffff; background: transparent;")
            self._sep.setStyleSheet("background: rgba(255,255,255,0.09);")
            self._lbl_use_result.setStyleSheet("color: rgba(255,255,255,0.45); background: transparent;")
            self._btn_income.setStyleSheet("""
                QPushButton {
                    background: rgba(48,209,88,0.16); color: #30d158;
                    border: 1px solid rgba(48,209,88,0.28);
                    border-radius: 8px; font-size: 12px; font-weight: 600;
                    text-align: left; padding-left: 10px; min-height: 32px;
                }
                QPushButton:hover  { background: rgba(48,209,88,0.26); }
                QPushButton:pressed { background: rgba(48,209,88,0.10); }
                QPushButton:disabled { opacity: 0.30; }
            """)
            self._btn_expense.setStyleSheet("""
                QPushButton {
                    background: rgba(255,69,58,0.16); color: #ff453a;
                    border: 1px solid rgba(255,69,58,0.28);
                    border-radius: 8px; font-size: 12px; font-weight: 600;
                    text-align: left; padding-left: 10px; min-height: 32px;
                }
                QPushButton:hover  { background: rgba(255,69,58,0.26); }
                QPushButton:pressed { background: rgba(255,69,58,0.10); }
                QPushButton:disabled { opacity: 0.30; }
            """)
            self._btn_copy.setStyleSheet("""
                QPushButton {
                    background: rgba(255,255,255,0.08);
                    color: rgba(255,255,255,0.65); border: 1px solid rgba(255,255,255,0.10);
                    border-radius: 8px; font-size: 12px; font-weight: 600;
                    min-height: 32px;
                }
                QPushButton:hover { background: rgba(255,255,255,0.14); }
                QPushButton:pressed { background: rgba(255,255,255,0.05); }
                QPushButton:disabled { opacity: 0.30; }
            """)

        # Re-style all calculator keypad buttons; updateGeometry so parent
        # VBox reallocates height when button minimum sizes change (e.g. light theme).
        for btn in self._calc.findChildren(_CalcBtn):
            btn.restyle(styles)
        self._card.updateGeometry()

    # ── Keyboard passthrough ───────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        if not self._calc.handle_key_event(event):
            super().keyPressEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fmt(val: float) -> str:
    """Strip trailing zeros; show int when possible."""
    if math.isnan(val) or math.isinf(val):
        return "Ошибка"
    if val == int(val):
        return str(int(val))
    return f"{val:.8f}".rstrip("0").rstrip(".")


def _compute(a: float, op: str, b: float) -> float:
    if op == "+":  return a + b
    if op == "-":  return a - b
    if op == "*":  return a * b
    if op == "/":
        if b == 0:
            raise ZeroDivisionError
        return a / b
    return b
