from __future__ import annotations

import calendar as _cal
from datetime import date, datetime, timedelta

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QScrollArea, QFrame, QSizePolicy, QToolTip
)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QLinearGradient, QBrush, QPainter, QPen

import pyqtgraph as pg
import numpy as np

from entities.analytics.service import AnalyticsService
from shared.i18n import tr
import app.styles.themes as _styles


# ── pyqtgraph global theme ──────────────────────────────
# background="#00000000" (transparent) — individual PlotWidgets set setBackground(None)
# so the card frame provides the visual background with border-radius.
pg.setConfigOptions(
    background="#00000000",
    foreground="#98989d",
    antialias=True,
)

_ACCENT = "#0a84ff"
_GREEN = "#30d158"
_PURPLE = "#bf5af2"
_TEXT = "#f5f5f7"
_TEXT_SEC = "#98989d"
_GLASS = "rgba(255,255,255,0.07)"
_GLASS_BORDER = "rgba(255,255,255,0.12)"

_ORANGE = "#ff9f0a"


def _th() -> dict:
    """Return the active theme colour dict from styles."""
    return _styles._THEMES[_styles._active_theme]


# ── Mini day chart (horizontal bars: created / completed) ────────────────
class _MiniDayChart(QWidget):
    """Two small horizontal progress bars showing created vs completed for a day."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._created = 0
        self._completed = 0
        self.setFixedHeight(46)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_data(self, created: int, completed: int):
        self._created = created
        self._completed = completed
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        label_w = 58
        gap = 8
        bar_x = label_w + gap
        bar_max_w = self.width() - bar_x - 8
        bar_h = 11
        mx = max(self._created, self._completed, 1)

        y1 = (self.height() // 2) - bar_h - 3
        y2 = (self.height() // 2) + 3

        # tracks (dark=white-alpha, light=black-alpha)
        p.setPen(Qt.PenStyle.NoPen)
        _dark = _styles._active_theme == "dark"
        _track = QColor(255, 255, 255, 15) if _dark else QColor(0, 0, 0, 25)
        p.setBrush(_track)
        p.drawRoundedRect(QRectF(bar_x, y1, bar_max_w, bar_h), 4, 4)
        p.drawRoundedRect(QRectF(bar_x, y2, bar_max_w, bar_h), 4, 4)

        # created bar (blue)
        if self._created > 0:
            w = max(int(self._created / mx * bar_max_w), 6)
            p.setBrush(QColor(10, 132, 255, 200))
            p.drawRoundedRect(QRectF(bar_x, y1, w, bar_h), 4, 4)

        # completed bar (green)
        if self._completed > 0:
            w2 = max(int(self._completed / mx * bar_max_w), 6)
            p.setBrush(QColor(48, 209, 88, 200))
            p.drawRoundedRect(QRectF(bar_x, y2, w2, bar_h), 4, 4)

        # labels
        p.setFont(QFont("Segoe UI", 9))
        p.setPen(QColor(_ACCENT))
        p.drawText(QRectF(0, y1 - 1, label_w, bar_h + 2),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   f"+{self._created}")
        p.setPen(QColor(_GREEN))
        p.drawText(QRectF(0, y2 - 1, label_w, bar_h + 2),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   f"✓{self._completed}")
        p.end()


# ── Day detail side-panel (embedded in CalendarOverlay) ───────────────────
class _DayDetailPanel(QFrame):
    """Side panel that appears inside the calendar popup when a day is clicked."""

    _W = 290
    _MAX = 12  # max tasks shown per section

    def __init__(self, analytics: "AnalyticsService", parent=None):
        super().__init__(parent)
        self._analytics = analytics
        self.setObjectName("DayDetailPanel")
        self.setFixedWidth(self._W)
        self._apply_panel_css()

        vl = QVBoxLayout(self)
        vl.setContentsMargins(14, 14, 12, 14)
        vl.setSpacing(8)

        self._date_lbl = QLabel()
        self._date_lbl.setStyleSheet(f"color: {_th()['text']}; font-size: 13px; font-weight: 700;")
        vl.addWidget(self._date_lbl)

        self._chart = _MiniDayChart()
        vl.addWidget(self._chart)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {_th()['separator']};")
        vl.addWidget(sep)

        # Scrollable task list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollBar:vertical { width: 4px; background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255,255,255,0.20); border-radius: 2px; min-height: 20px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self._tasks_w = QWidget()
        self._tasks_vl = QVBoxLayout(self._tasks_w)
        self._tasks_vl.setContentsMargins(0, 2, 4, 2)
        self._tasks_vl.setSpacing(3)
        scroll.setWidget(self._tasks_w)
        vl.addWidget(scroll, 1)

    def _apply_panel_css(self):
        th = _th()
        self.setStyleSheet(f"""
            #DayDetailPanel {{
                background: {th["bg_panel"]};
                border-left: 1px solid {th["glass_border"]};
                border-radius: 0px 14px 14px 0px;
            }}
            QLabel {{ background: transparent; }}
            QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
        """)

    def apply_theme(self):
        self._apply_panel_css()
        self._date_lbl.setStyleSheet(f"color: {_th()['text']}; font-size: 13px; font-weight: 700;")

    def load_day(self, date_str: str):
        from datetime import date as _date
        data = self._analytics.tasks_for_day(date_str)
        completed = data["completed"]
        created = data["created"]

        # Date header
        try:
            d = _date.fromisoformat(date_str)
            months = tr("analytics.months").split(",")
            self._date_lbl.setText(f"{d.day} {months[d.month - 1]} {d.year}")
        except Exception:
            self._date_lbl.setText(date_str)

        self._chart.set_data(len(created), len(completed))

        # Clear old task labels
        while self._tasks_vl.count():
            item = self._tasks_vl.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        def _add_section(tasks, label_txt, color, icon):
            if not tasks:
                return
            hdr = QLabel(f"{icon}  {label_txt}  ({len(tasks)})")
            hdr.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 600;")
            self._tasks_vl.addWidget(hdr)
            for t in tasks[:self._MAX]:
                title = (t.title or "").strip() or "—"
                row = QLabel(f"   {title}")
                row.setStyleSheet(f"color: {_th()['text_sec']}; font-size: 12px;")
                self._tasks_vl.addWidget(row)
            if len(tasks) > self._MAX:
                more = QLabel(f"   {tr('analytics.more', n=len(tasks) - self._MAX)}")
                more.setStyleSheet(f"color: {_th()['text_sec']}; font-size: 11px; font-style: italic;")
                self._tasks_vl.addWidget(more)

        _add_section(completed, tr("analytics.cal_done"), _GREEN, "✓")

        if completed and created:
            sp = QLabel()
            sp.setFixedHeight(4)
            self._tasks_vl.addWidget(sp)

        _add_section(created, tr("analytics.cal_created"), _ACCENT, "+")

        if not completed and not created:
            empty = QLabel(tr("analytics.day_empty"))
            empty.setStyleSheet(f"color: {_th()['text_sec']}; font-size: 12px; font-style: italic;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._tasks_vl.addWidget(empty)

        self._tasks_vl.addStretch(1)


# ── Calendar overlay ─────────────────────────────────
class CalendarOverlay(QFrame):
    """Custom-painted monthly calendar popup with per-day task stats and detail panel."""

    @staticmethod
    def _months() -> list[str]:
        return tr("analytics.months").split(",")

    @staticmethod
    def _dow() -> list[str]:
        return tr("analytics.dow").split(",")

    _CELL_W = 60
    _CELL_H = 56
    _HDR_H = 44
    _DOW_H = 24
    _LEGEND_H = 32
    _PAD = 10

    def __init__(self, analytics: AnalyticsService, parent=None):
        super().__init__(parent)
        self.setObjectName("CalOverlay")
        self.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self._apply_overlay_css()
        self._analytics = analytics
        today = date.today()
        self._year = today.year
        self._month = today.month
        self._data: dict[str, tuple[int, int]] = {}
        self._max_act = 1
        self._selected_date: str | None = None

        self._cal_w = 7 * self._CELL_W + 2 * self._PAD
        self._cal_h = (6 * self._CELL_H + self._HDR_H + self._DOW_H
                       + self._LEGEND_H + 2 * self._PAD)

        self.resize(self._cal_w, self._cal_h)

        # Day detail side panel (child widget, absolutely positioned)
        self._detail = _DayDetailPanel(self._analytics, self)
        self._detail.setGeometry(self._cal_w, 0, _DayDetailPanel._W, self._cal_h)
        self._detail.hide()

        self._left_rect = QRectF()
        self._right_rect = QRectF()
        self._day_rects: list[tuple[QRectF, date]] = []

        self.setMouseTracking(True)

    # ── theme ──
    def _apply_overlay_css(self):
        th = _th()
        self.setStyleSheet(f"""
            #CalOverlay {{
                background: {th["cmd_bg"]};
                border: 1px solid {th["glass_border"]};
                border-radius: 14px;
            }}
        """)

    def apply_theme(self):
        self._apply_overlay_css()
        self._detail.apply_theme()
        self.update()

    # ── data ──
    def _load(self):
        self._data = self._analytics.month_data(self._year, self._month)
        if self._data:
            self._max_act = max(max(cr + co, 1) for cr, co in self._data.values())
        else:
            self._max_act = 1
        self.update()

    # ── show ──
    def show_below(self, btn: QPushButton):
        today = date.today()
        self._year, self._month = today.year, today.month
        self._selected_date = None
        self._detail.hide()
        self.resize(self._cal_w, self._cal_h)
        self._load()
        # Position popup: align right edge with button right edge, shift left a bit
        pos = btn.mapToGlobal(btn.rect().bottomRight())
        pos.setX(pos.x() - self.width())
        pos.setY(pos.y() + 4)
        self.move(pos)
        self.show()

    # ── navigation ──
    def _nav(self):
        """After month change, close detail if selected date is not in new month."""
        if self._selected_date:
            try:
                sel = date.fromisoformat(self._selected_date)
                if sel.year != self._year or sel.month != self._month:
                    self._hide_detail()
            except Exception:
                self._hide_detail()
        self._load()

    def _prev(self):
        if self._month == 1:
            self._month, self._year = 12, self._year - 1
        else:
            self._month -= 1
        self._nav()

    def _next(self):
        if self._month == 12:
            self._month, self._year = 1, self._year + 1
        else:
            self._month += 1
        self._nav()

    def _show_detail(self, date_str: str):
        self._selected_date = date_str
        self._detail.load_day(date_str)
        self._detail.setGeometry(self._cal_w, 0, _DayDetailPanel._W, self._cal_h)
        self.resize(self._cal_w + _DayDetailPanel._W, self._cal_h)
        self._detail.show()
        self.update()

    def _hide_detail(self):
        self._selected_date = None
        self.resize(self._cal_w, self._cal_h)
        self._detail.hide()
        self.update()

    def mousePressEvent(self, ev):
        pos = ev.position()
        if self._left_rect.contains(pos):
            self._prev()
        elif self._right_rect.contains(pos):
            self._next()
        else:
            for rect, day_date in self._day_rects:
                if rect.contains(pos):
                    date_str = day_date.isoformat()
                    if self._selected_date == date_str:
                        self._hide_detail()
                    else:
                        self._show_detail(date_str)
                    return
            super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        pos = ev.position()
        # Check if hovering over a day cell
        for rect, day_date in self._day_rects:
            if rect.contains(pos):
                ds = day_date.isoformat()
                cr, co = self._data.get(ds, (0, 0))
                if cr > 0 or co > 0:
                    tooltip = []
                    if cr > 0:
                        tooltip.append(f"{tr('analytics.cal_created')}: {cr}")
                    if co > 0:
                        tooltip.append(f"{tr('analytics.cal_done')}: {co}")
                    QToolTip.showText(ev.globalPosition().toPoint(), " | ".join(tooltip), self)
                return
        QToolTip.hideText()
        super().mouseMoveEvent(ev)

    # ── paint ──
    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        th = _th()
        _dark = _styles._active_theme == "dark"
        _txt = th["text"]
        _txt_sec = th["text_sec"]

        pad = self._PAD
        cw, ch = self._CELL_W, self._CELL_H
        today = date.today()
        self._day_rects.clear()

        # ── header: arrows + month name ──
        arrow_w = 30
        self._left_rect = QRectF(pad, pad, arrow_w, self._HDR_H)
        self._right_rect = QRectF(self.width() - pad - arrow_w, pad, arrow_w, self._HDR_H)

        p.setPen(QColor(_ACCENT))
        p.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        p.drawText(self._left_rect, Qt.AlignmentFlag.AlignCenter, "\u25C0")
        p.drawText(self._right_rect, Qt.AlignmentFlag.AlignCenter, "\u25B6")

        p.setPen(QColor(_txt))
        p.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        hdr = QRectF(pad, pad, self.width() - 2 * pad, self._HDR_H)
        p.drawText(hdr, Qt.AlignmentFlag.AlignCenter,
                   f"{self._months()[self._month - 1]} {self._year}")

        # ── weekday headers ──
        y_dow = pad + self._HDR_H
        p.setPen(QColor(_txt_sec))
        p.setFont(QFont("Segoe UI", 9))
        for col, name in enumerate(self._dow()):
            r = QRectF(pad + col * cw, y_dow, cw, self._DOW_H)
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, name)

        # ── day grid ──
        y_grid = y_dow + self._DOW_H
        cal = _cal.Calendar(firstweekday=0)
        weeks = cal.monthdayscalendar(self._year, self._month)

        for ri, week in enumerate(weeks):
            for ci, day in enumerate(week):
                if day == 0:
                    continue
                x = pad + ci * cw
                y = y_grid + ri * ch
                cell = QRectF(x + 2, y + 2, cw - 4, ch - 4)

                day_date = date(self._year, self._month, day)
                ds = day_date.isoformat()
                cr, co = self._data.get(ds, (0, 0))
                total = cr + co
                is_today = day_date == today

                # Store rect for mouse events
                self._day_rects.append((cell, day_date))

                # cell background intensity (white-alpha on dark, black-alpha on light)
                if total > 0:
                    intensity = total / self._max_act
                    alpha = int(8 + 40 * intensity)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QColor(255, 255, 255, alpha) if _dark else QColor(0, 0, 0, alpha))
                    p.drawRoundedRect(cell, 8, 8)

                # selected day highlight
                is_selected = (ds == self._selected_date)
                if is_selected:
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QColor(10, 132, 255, 45))
                    p.drawRoundedRect(cell, 8, 8)

                # today border
                if is_today:
                    p.setPen(QPen(QColor(_ACCENT), 1.5))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRoundedRect(cell, 8, 8)
                elif is_selected:
                    p.setPen(QPen(QColor(_ACCENT), 1.0))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRoundedRect(cell, 8, 8)

                # day number
                clr = QColor(_ACCENT) if is_today else (
                    QColor(_txt) if total > 0 else QColor(_txt_sec)
                )
                p.setPen(clr)
                p.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
                dr = QRectF(x + 6, y + 6, cw - 12, 18)
                p.drawText(dr, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                           str(day))

                # completed (green, bottom-left)
                if co > 0:
                    p.setPen(QColor(_GREEN))
                    p.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
                    cr2 = QRectF(x + 5, y + ch - 20, cw / 2 - 5, 16)
                    p.drawText(cr2, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
                               f"\u2713{co}")

                # created (blue, bottom-right)
                if cr > 0:
                    p.setPen(QColor(_ACCENT))
                    p.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
                    cr3 = QRectF(x + cw / 2, y + ch - 20, cw / 2 - 7, 16)
                    p.drawText(cr3, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
                               f"+{cr}")

        # ── legend ──
        y_legend = y_grid + 6 * ch + 8
        dot_r = 5
        p.setFont(QFont("Segoe UI", 9))

        # Green dot + "Выполнено"
        lx1 = pad + 20
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(_GREEN))
        p.drawEllipse(QRectF(lx1, y_legend + 3, dot_r * 2, dot_r * 2))
        p.setPen(QColor(_txt_sec))
        p.drawText(QRectF(lx1 + 14, y_legend, 80, 16), Qt.AlignmentFlag.AlignLeft, tr("analytics.cal_done"))

        # Blue dot + created
        lx2 = lx1 + 110
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(_ACCENT))
        p.drawEllipse(QRectF(lx2, y_legend + 3, dot_r * 2, dot_r * 2))
        p.setPen(QColor(_txt_sec))
        p.drawText(QRectF(lx2 + 14, y_legend, 80, 16), Qt.AlignmentFlag.AlignLeft, tr("analytics.cal_created"))

        p.end()


class KpiCard(QFrame):
    """Single glass KPI card showing a value + label + delta trend."""

    clicked = pyqtSignal()

    @staticmethod
    def _make_ss() -> str:
        th = _th()
        return f"""
            #KpiCard {{
                background: {th["glass"]};
                border: 1px solid {th["glass_border"]};
                border-radius: 14px;
                padding: 12px 8px;
            }}
            #KpiCard:hover {{
                background: {th["glass_hover"]};
                border-color: {th["glass_border"]};
            }}
        """

    def __init__(self, label: str, tooltip: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("KpiCard")
        self.setStyleSheet(self._make_ss())
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(2)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._value_label = QLabel("—")
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value_label.setStyleSheet(f"color: {_th()['text']}; font-size: 22px; font-weight: 700;")

        self._desc_label = QLabel(label)
        self._desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._desc_label.setStyleSheet(f"color: {_th()['text_sec']}; font-size: 11px;")

        self._delta_label = QLabel("")
        self._delta_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._delta_label.setStyleSheet(f"color: {_th()['text_sec']}; font-size: 10px;")
        self._delta_label.setFixedHeight(14)

        self._hint_label = QLabel("")
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint_label.setStyleSheet(f"color: {_th()['text_sec']}; font-size: 9px; opacity: 0.6;")
        self._hint_label.setFixedHeight(12)

        lay.addWidget(self._value_label)
        lay.addWidget(self._desc_label)
        lay.addWidget(self._delta_label)
        lay.addWidget(self._hint_label)

    def set_value(self, text: str):
        self._value_label.setText(text)

    def set_label(self, text: str):
        self._desc_label.setText(text)

    def set_delta(self, text: str, color: str = _TEXT_SEC):
        self._delta_label.setText(text)
        self._delta_label.setStyleSheet(f"color: {color}; font-size: 10px;")

    def set_period_hint(self, text: str):
        self._hint_label.setText(text)

    def apply_theme(self):
        self.setStyleSheet(self._make_ss())
        self._value_label.setStyleSheet(f"color: {_th()['text']}; font-size: 22px; font-weight: 700;")
        self._desc_label.setStyleSheet(f"color: {_th()['text_sec']}; font-size: 11px;")
        self._hint_label.setStyleSheet(f"color: {_th()['text_sec']}; font-size: 9px; opacity: 0.6;")

    def highlight(self, on: bool = True):
        if on:
            self.setStyleSheet(self._make_ss() + f"""
                #KpiCard {{ border-color: {_ACCENT}; background: rgba(10,132,255,0.10); }}
            """)
        else:
            self.setStyleSheet(self._make_ss())

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


class DonutChart(QFrame):
    """Custom-painted donut chart for status distribution."""

    _ORANGE = "#ff9f0a"

    @staticmethod
    def _make_ss() -> str:
        th = _th()
        return f"""
            #DonutChart {{
                background: {th["glass"]};
                border: 1px solid {th["glass_border"]};
                border-radius: 14px;
            }}
        """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DonutChart")
        self.setStyleSheet(self._make_ss())
        self.setMinimumHeight(200)
        self.setMaximumHeight(240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._active = 0
        self._done = 0

    def apply_theme(self):
        self.setStyleSheet(self._make_ss())
        self.update()

    def set_data(self, active: int, done: int):
        self._active = active
        self._done = done
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        total = self._active + self._done
        th = _th()
        _txt = th["text"]
        _txt_sec = th["text_sec"]

        if total == 0:
            # Draw empty state text
            p.setPen(QColor(_txt_sec))
            p.setFont(QFont("Segoe UI", 11))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("analytics.donut_no_data"))
            p.end()
            return

        # Title
        p.setPen(QColor(_txt))
        p.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        p.drawText(QRectF(0, 8, self.width(), 24), Qt.AlignmentFlag.AlignCenter, tr("analytics.donut_title"))

        # Donut dimensions
        side = min(self.width(), self.height() - 50) - 40
        ring = max(side * 0.22, 12)
        cx = self.width() / 2
        cy = (self.height() + 30) / 2
        rect = QRectF(cx - side / 2, cy - side / 2, side, side)

        done_angle = int(self._done / total * 360 * 16)
        active_angle = 360 * 16 - done_angle

        # Draw done arc (green)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(_GREEN))
        p.drawPie(rect, 90 * 16, -done_angle)

        # Draw active arc (orange)
        p.setBrush(QColor(self._ORANGE))
        p.drawPie(rect, 90 * 16 - done_angle, -active_angle)

        # Cut out center — use chart_bg (always opaque hex) to approximate card surface
        inner = rect.adjusted(ring, ring, -ring, -ring)
        p.setBrush(QColor(th.get("chart_bg", th["bg_dark"])))
        p.drawEllipse(inner)

        # Center text
        pct = round(self._done / total * 100)
        p.setPen(QColor(_txt))
        p.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        p.drawText(inner, Qt.AlignmentFlag.AlignCenter, f"{pct}%")

        # Legend below donut
        legend_y = cy + side / 2 + 10
        dot_r = 5
        font = QFont("Segoe UI", 9)
        p.setFont(font)

        # Done legend
        lx = cx - 60
        p.setBrush(QColor(_GREEN))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(lx, legend_y - dot_r, dot_r * 2, dot_r * 2))
        p.setPen(QColor(_txt_sec))
        p.drawText(QRectF(lx + 14, legend_y - 8, 70, 16), Qt.AlignmentFlag.AlignLeft, f"{tr('analytics.donut_done')} {self._done}")

        # Active legend
        lx = cx + 10
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._ORANGE))
        p.drawEllipse(QRectF(lx, legend_y - dot_r, dot_r * 2, dot_r * 2))
        p.setPen(QColor(_txt_sec))
        p.drawText(QRectF(lx + 14, legend_y - 8, 80, 16), Qt.AlignmentFlag.AlignLeft, f"{tr('analytics.donut_active')} {self._active}")

        p.end()


class AnalyticsPage(QWidget):
    """Analytics page with period selector, KPI cards and pyqtgraph charts."""

    def __init__(self, analytics: AnalyticsService, parent=None):
        super().__init__(parent)
        self._analytics = analytics
        self._days = 7
        self._charts_ready = False
        self._build_ui()

    # ── build ────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # scroll area wrapping everything
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        inner = QWidget()
        self._inner = inner
        inner.setAutoFillBackground(True)
        self._layout = QVBoxLayout(inner)
        self._layout.setContentsMargins(4, 8, 4, 16)
        self._layout.setSpacing(16)

        self._build_period_selector()
        self._build_kpi_row()
        # Charts are created lazily on first show to avoid pyqtgraph
        # crash when painting axes inside a zero-size QStackedWidget page.

        self._layout.addStretch(1)
        self._stretch_item = self._layout.itemAt(self._layout.count() - 1)
        scroll.setWidget(inner)
        self._scroll = scroll
        root.addWidget(scroll)

    def _build_period_selector(self):
        row = QHBoxLayout()
        row.setSpacing(8)

        self._period_btns: list[QPushButton] = []
        _period_keys = ["analytics.period_today", "analytics.period_7",
                        "analytics.period_30", "analytics.period_90"]
        for (days, _), key in zip([(1, None), (7, None), (30, None), (90, None)], _period_keys):
            btn = QPushButton(tr(key))
            btn.setObjectName("FilterBtn")
            btn.setCheckable(True)
            btn.setChecked(days == self._days)
            btn.setMinimumWidth(70)
            btn.clicked.connect(lambda checked, d=days: self._on_period(d))
            row.addWidget(btn)
            self._period_btns.append(btn)

        # Calendar button
        self._cal_btn = QPushButton(tr("analytics.calendar"))
        self._cal_btn.setObjectName("FilterBtn")
        self._cal_btn.setMinimumWidth(85)
        self._cal_btn.setToolTip(tr("analytics.calendar_tip"))
        self._cal_btn.clicked.connect(self._toggle_calendar)
        row.addWidget(self._cal_btn)

        row.addStretch(1)
        self._layout.addLayout(row)

        self._cal_overlay: CalendarOverlay | None = None

    def _toggle_calendar(self):
        if self._cal_overlay is not None and self._cal_overlay.isVisible():
            self._cal_overlay.hide()
            return
        if self._cal_overlay is None:
            self._cal_overlay = CalendarOverlay(self._analytics, self)
        self._cal_overlay.show_below(self._cal_btn)

    def _build_kpi_row(self):
        row = QHBoxLayout()
        row.setSpacing(10)

        self.kpi_completed = KpiCard(
            tr("analytics.kpi_completed"),
            tooltip=tr("analytics.tip_completed"),
        )
        self.kpi_pct = KpiCard(
            tr("analytics.kpi_pct"),
            tooltip=tr("analytics.tip_pct"),
        )
        self.kpi_avg = KpiCard(
            tr("analytics.kpi_avg"),
            tooltip=tr("analytics.tip_avg"),
        )
        self.kpi_streak = KpiCard(
            tr("analytics.kpi_streak"),
            tooltip=tr("analytics.tip_streak"),
        )

        for card in (self.kpi_completed, self.kpi_pct, self.kpi_avg, self.kpi_streak):
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row.addWidget(card)

        # Card clicks → highlight associated chart
        self.kpi_completed.clicked.connect(lambda: self._on_kpi_click(0))
        self.kpi_pct.clicked.connect(lambda: self._on_kpi_click(1))
        self.kpi_avg.clicked.connect(lambda: self._on_kpi_click(2))
        self.kpi_streak.clicked.connect(lambda: self._on_kpi_click(3))
        self._highlighted_kpi: int | None = None

        self._layout.addLayout(row)

    @staticmethod
    def _safe_plot_widget() -> pg.PlotWidget:
        """Create a non-interactive PlotWidget with fixed view."""
        th = _th()
        fg = th["text_sec"]
        pw = pg.PlotWidget()
        pw.setBackground(None)  # always transparent — card frame provides the bg
        pw.setMinimumHeight(180)
        pw.setMaximumHeight(220)
        pw.setMinimumWidth(100)
        pw.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        pw.showGrid(x=False, y=True, alpha=0.15)

        # Disable all mouse interaction
        pw.setMouseEnabled(x=False, y=False)
        pw.setMenuEnabled(False)
        vb = pw.getViewBox()
        vb.setMouseEnabled(x=False, y=False)
        vb.enableAutoRange()

        # Set safe initial range
        pw.setXRange(0, 1, padding=0)
        pw.setYRange(0, 1, padding=0)
        tick_font = QFont("Segoe UI", 8)
        pw.getAxis("bottom").setStyle(tickFont=tick_font)
        pw.getAxis("left").setStyle(tickFont=tick_font)
        axis_pen = pg.mkPen(fg)
        pw.getAxis("bottom").setTextPen(axis_pen)
        pw.getAxis("left").setTextPen(axis_pen)
        pw.getAxis("bottom").setPen(pg.mkPen(color=fg, width=1))
        pw.getAxis("left").setPen(pg.mkPen(color=fg, width=1))
        return pw

    @staticmethod
    def _chart_card(pw: pg.PlotWidget) -> QFrame:
        """Wrap a PlotWidget in a rounded card frame (FinSectionCard CSS)."""
        card = QFrame()
        card.setObjectName("FinSectionCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(0)
        lay.addWidget(pw)
        return card

    def _build_bar_chart(self):
        self._bar_widget = self._safe_plot_widget()
        self._bar_widget.setLabel("left", tr("analytics.chart_bar_left"))
        self._bar_widget.setTitle(tr("analytics.chart_bar_title"), color=_th()["text"], size="11pt")
        self._layout.addWidget(self._chart_card(self._bar_widget))

    def _build_line_chart(self):
        self._line_widget = self._safe_plot_widget()
        self._line_widget.setTitle(tr("analytics.chart_line_title"), color=_th()["text"], size="11pt")
        self._line_widget.addLegend(offset=(10, 10))
        self._layout.addWidget(self._chart_card(self._line_widget))

    def _build_donut_and_weekday_row(self):
        row = QHBoxLayout()
        row.setSpacing(12)

        self._donut_widget = DonutChart()
        row.addWidget(self._donut_widget, stretch=1)

        self._weekday_widget = self._safe_plot_widget()
        self._weekday_widget.setTitle(tr("analytics.chart_weekday_title"), color=_th()["text"], size="11pt")
        self._weekday_widget.setLabel("left", tr("analytics.chart_weekday_left"))
        row.addWidget(self._chart_card(self._weekday_widget), stretch=1)

        self._layout.addLayout(row)

    def _build_cumulative_chart(self):
        self._cumul_widget = self._safe_plot_widget()
        self._cumul_widget.setTitle(tr("analytics.chart_cumul_title"), color=_th()["text"], size="11pt")
        self._cumul_widget.setLabel("left", tr("analytics.chart_cumul_left"))
        self._layout.addWidget(self._chart_card(self._cumul_widget))

    # ── period switching ─────────────────────────────────
    def _on_period(self, days: int):
        self._days = days
        for btn in self._period_btns:
            btn.setChecked(False)
        idx = {1: 0, 7: 1, 30: 2, 90: 3}.get(days, 2)
        self._period_btns[idx].setChecked(True)
        self.refresh()

    # ── lazy chart init ─────────────────────────────────
    def _ensure_charts(self):
        if self._charts_ready:
            return
        self._layout.removeItem(self._stretch_item)
        self._build_bar_chart()
        self._build_line_chart()
        self._build_donut_and_weekday_row()
        self._build_cumulative_chart()
        self._layout.addStretch(1)
        self._charts_ready = True

    # ── data refresh ─────────────────────────────────────
    def refresh(self, days: int | None = None):
        if days is not None:
            self._days = days
        self._ensure_charts()
        self._refresh_kpi()
        self._refresh_bar()
        self._refresh_lines()
        self._refresh_donut()
        self._refresh_weekday()
        self._refresh_cumulative()

    @staticmethod
    def _fmt_hours(h: float) -> str:
        if h >= 24:
            return f"{h / 24:.1f} {tr('analytics.fmt_d')}"
        if h >= 1:
            return f"{h:.1f} {tr('analytics.fmt_h')}"
        if h > 0:
            return f"{h * 60:.0f} {tr('analytics.fmt_min')}"
        return "—"

    @staticmethod
    def _fmt_hours_delta(h: float) -> str:
        """Format an hours delta to compact human text."""
        a = abs(h)
        if a >= 24:
            return f"{h / 24:+.1f} {tr('analytics.fmt_d')}"
        if a >= 1:
            return f"{h:+.1f} {tr('analytics.fmt_h')}"
        if a > 0:
            return f"{h * 60:+.0f} {tr('analytics.fmt_min')}"
        return "0"

    def _refresh_kpi(self):
        kpi = self._analytics.kpi_with_delta(self._days)

        # ── Выполнено ──
        self.kpi_completed.set_value(str(kpi["total_completed"]))
        dd = kpi["done_delta"]
        if dd > 0:
            self.kpi_completed.set_delta(f"↑ +{dd}", _GREEN)
        elif dd < 0:
            self.kpi_completed.set_delta(f"↓ {dd}", _ORANGE)
        else:
            self.kpi_completed.set_delta("→ 0", _TEXT_SEC)

        # ── % завершения (period-specific: created in period) ──
        self.kpi_pct.set_value(f'{kpi["completion_pct"]}%')
        self.kpi_pct.set_delta(f'{kpi["period_done"]} {tr("analytics.kpi_of")} {kpi["period_tasks"]}', _TEXT_SEC)

        # ── Среднее время (inverted: less = better) ──
        self.kpi_avg.set_value(self._fmt_hours(kpi["avg_hours"]))
        prev_has_avg = kpi.get("prev_has_avg", False)
        if not prev_has_avg:
            self.kpi_avg.set_delta("—", _TEXT_SEC)
        else:
            adh = kpi["avg_delta_hours"]
            if adh < 0:
                self.kpi_avg.set_delta(f"↓ {self._fmt_hours_delta(adh)}", _GREEN)
            elif adh > 0:
                self.kpi_avg.set_delta(f"↑ {self._fmt_hours_delta(adh)}", _ORANGE)
            else:
                self.kpi_avg.set_delta("→ 0", _TEXT_SEC)

        # ── Streak ──
        streak = kpi["streak"]
        self.kpi_streak.set_value(str(streak) if streak > 0 else "—")
        max_s = kpi["max_streak"]
        if streak > 0 and streak >= max_s:
            self.kpi_streak.set_delta(tr("analytics.streak_record"), _GREEN)
        elif max_s > 0:
            self.kpi_streak.set_delta(tr("analytics.streak_best", n=max_s), _TEXT_SEC)
        else:
            self.kpi_streak.set_delta("", _TEXT_SEC)

        # Period hints under each delta
        _hint = tr("analytics.hint_vs_prev", n=self._days)
        self.kpi_completed.set_period_hint(_hint)
        self.kpi_avg.set_period_hint(_hint)
        self.kpi_pct.set_period_hint(tr("analytics.hint_period", n=self._days))
        self.kpi_streak.set_period_hint(tr("analytics.hint_streak"))

    def _on_kpi_click(self, idx: int):
        """Toggle highlight on clicked KPI card and scroll to associated chart."""
        if not self._charts_ready:
            return
        cards = [self.kpi_completed, self.kpi_pct, self.kpi_avg, self.kpi_streak]
        if self._highlighted_kpi == idx:
            # Deselect
            cards[idx].highlight(False)
            self._highlighted_kpi = None
            return
        # Unhighlight previous
        if self._highlighted_kpi is not None:
            cards[self._highlighted_kpi].highlight(False)
        cards[idx].highlight(True)
        self._highlighted_kpi = idx
        # Scroll to associated chart
        chart_map = {
            0: self._bar_widget,
            1: self._line_widget,
            2: self._line_widget,
            3: self._cumul_widget,
        }
        target = chart_map.get(idx)
        if target is not None:
            target.ensurePolished()
            scroll = self._scroll
            pos = target.mapTo(scroll.widget(), target.rect().topLeft())
            scroll.ensureVisible(pos.x(), pos.y(), 0, 20)

    @staticmethod
    def _find_scroll_area(widget) -> "QScrollArea | None":
        """Walk up the widget tree to find the enclosing QScrollArea."""
        from PyQt6.QtWidgets import QScrollArea
        p = widget.parent()
        while p is not None:
            if isinstance(p, QScrollArea):
                return p
            p = p.parent()
        return None

    @staticmethod
    def _show_chart_empty(widget: "pg.PlotWidget", show: bool) -> None:
        """Overlay or hide a 'not enough data' TextItem on a pyqtgraph widget."""
        if not hasattr(widget, "_empty_ti"):
            ti = pg.TextItem(
                tr("analytics.no_data_period"),
                color=_TEXT_SEC,
                anchor=(0.5, 0.5),
            )
            ti.setFont(QFont("Segoe UI", 10))
            widget._empty_ti = ti
            widget.addItem(ti)
        ti = widget._empty_ti
        if show:
            ti.setText(tr("analytics.no_data_period"))
            ti.setPos(0.5, 0.5)
            ti.show()
        else:
            ti.hide()

    def _refresh_bar(self):
        self._bar_widget.clear()
        date_map = self._full_date_range()
        data = self._analytics.completed_per_day(self._days)
        for d_str, cnt in data:
            if d_str in date_map:
                date_map[d_str] = cnt

        dates = sorted(date_map.keys())
        values = [date_map[d] for d in dates]
        x = list(range(len(dates)))

        if not x:
            return

        # Gradient brush for bars (green = completed)
        grad = QLinearGradient(0, 0, 0, 1)
        grad.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectMode)
        grad.setColorAt(0.0, QColor(48, 209, 88, 200))
        grad.setColorAt(1.0, QColor(48, 209, 88, 40))

        bar = pg.BarGraphItem(
            x=x, height=values, width=0.6,
            brush=QBrush(grad),
            pen=pg.mkPen(QColor(48, 209, 88, 255), width=1),
        )
        self._bar_widget.addItem(bar)

        ticks = self._make_date_ticks(dates)
        self._bar_widget.getAxis("bottom").setTicks([ticks])

        # Auto-fit: set range to exactly cover data
        max_val = max(values) if values else 1
        self._bar_widget.setXRange(-0.5, len(dates) - 0.5, padding=0)
        self._bar_widget.setYRange(0, max(max_val * 1.15, 1), padding=0)
        self._show_chart_empty(self._bar_widget, not any(v > 0 for v in values))

    def _refresh_lines(self):
        self._line_widget.clear()
        # Re-add legend after clear
        self._line_widget.addLegend(offset=(10, 10))

        date_map_created: dict[str, int] = {}
        date_map_completed: dict[str, int] = {}
        for d in self._full_date_range():
            date_map_created[d] = 0
            date_map_completed[d] = 0

        data = self._analytics.created_vs_completed(self._days)
        for d_str, cr, co in data:
            if d_str in date_map_created:
                date_map_created[d_str] = cr
                date_map_completed[d_str] = co

        dates = sorted(date_map_created.keys())
        x = list(range(len(dates)))
        created_vals = [date_map_created[d] for d in dates]
        completed_vals = [date_map_completed[d] for d in dates]

        if not x:
            return

        x_arr = np.array(x, dtype=float)
        cr_arr = np.array(created_vals, dtype=float)
        co_arr = np.array(completed_vals, dtype=float)

        # Gradient fill under "Создано" line (blue = created)
        cr_fill = pg.FillBetweenItem(
            pg.PlotDataItem(x_arr, cr_arr),
            pg.PlotDataItem(x_arr, np.zeros_like(x_arr)),
            brush=QBrush(QColor(10, 132, 255, 30)),
        )
        self._line_widget.addItem(cr_fill)

        # Gradient fill under "Выполнено" line (green = completed)
        co_fill = pg.FillBetweenItem(
            pg.PlotDataItem(x_arr, co_arr),
            pg.PlotDataItem(x_arr, np.zeros_like(x_arr)),
            brush=QBrush(QColor(48, 209, 88, 40)),
        )
        self._line_widget.addItem(co_fill)

        # Lines on top
        self._line_widget.plot(
            x, created_vals,
            pen=pg.mkPen(color=_ACCENT, width=2),
            name=tr("analytics.legend_created"),
        )
        self._line_widget.plot(
            x, completed_vals,
            pen=pg.mkPen(color=_GREEN, width=2),
            name=tr("analytics.legend_completed"),
        )

        ticks = self._make_date_ticks(dates)
        self._line_widget.getAxis("bottom").setTicks([ticks])

        # Auto-fit
        all_vals = created_vals + completed_vals
        max_val = max(all_vals) if all_vals else 1
        self._line_widget.setXRange(-0.5, len(dates) - 0.5, padding=0)
        self._line_widget.setYRange(0, max(max_val * 1.15, 1), padding=0)
        self._show_chart_empty(self._line_widget, not any(v > 0 for v in all_vals))

    def _refresh_donut(self):
        dist = self._analytics.status_distribution(self._days)
        self._donut_widget.set_data(dist["active"], dist["done"])

    def _refresh_weekday(self):
        self._weekday_widget.clear()
        data = self._analytics.completed_by_weekday(self._days)

        # Build full 7-day array (0=Mon..6=Sun)
        counts = [0] * 7
        for dow, cnt in data:
            counts[dow] = cnt

        day_labels = tr("analytics.dow").split(",")
        x = list(range(7))

        # Gradient bars
        grad = QLinearGradient(0, 0, 0, 1)
        grad.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectMode)
        grad.setColorAt(0.0, QColor(191, 90, 242, 200))
        grad.setColorAt(1.0, QColor(191, 90, 242, 40))

        bar = pg.BarGraphItem(
            x=x, height=counts, width=0.6,
            brush=QBrush(grad),
            pen=pg.mkPen(QColor(191, 90, 242, 255), width=1),
        )
        self._weekday_widget.addItem(bar)

        ticks = [(i, day_labels[i]) for i in range(7)]
        self._weekday_widget.getAxis("bottom").setTicks([ticks])

        max_val = max(counts) if counts else 1
        self._weekday_widget.setXRange(-0.5, 6.5, padding=0)
        self._weekday_widget.setYRange(0, max(max_val * 1.15, 1), padding=0)

    def _refresh_cumulative(self):
        self._cumul_widget.clear()
        date_map = self._full_date_range()
        data = self._analytics.cumulative_completed(self._days)

        # Fill in cumulative data, carrying forward
        running = 0
        for d_str, total in data:
            if d_str in date_map:
                date_map[d_str] = total
                running = total

        # Forward-fill: if a date had no completions, carry previous total
        dates = sorted(date_map.keys())
        values = []
        prev = 0
        for d in dates:
            v = date_map[d]
            if v > 0:
                prev = v
            values.append(prev)

        x = list(range(len(dates)))
        if not x:
            return

        x_arr = np.array(x, dtype=float)
        v_arr = np.array(values, dtype=float)

        # Gradient fill under area
        fill = pg.FillBetweenItem(
            pg.PlotDataItem(x_arr, v_arr),
            pg.PlotDataItem(x_arr, np.zeros_like(x_arr)),
            brush=QBrush(QColor(10, 132, 255, 50)),
        )
        self._cumul_widget.addItem(fill)

        # Line on top
        self._cumul_widget.plot(
            x, values,
            pen=pg.mkPen(color=_ACCENT, width=2),
        )

        ticks = self._make_date_ticks(dates)
        self._cumul_widget.getAxis("bottom").setTicks([ticks])

        max_val = max(values) if values else 1
        self._cumul_widget.setXRange(-0.5, len(dates) - 0.5, padding=0)
        self._cumul_widget.setYRange(0, max(max_val * 1.15, 1), padding=0)
        self._show_chart_empty(self._cumul_widget, not any(v > 0 for v in values))

    # ── helpers ──────────────────────────────────────────
    def _full_date_range(self) -> dict[str, int]:
        """Returns {date_str: 0, ...} for every day in the current period.

        Always returns at least 2 days so line/area charts can render.
        """
        today = datetime.now().date()
        span = max(self._days, 2)
        result = {}
        for i in range(span):
            d = today - timedelta(days=span - 1 - i)
            result[d.isoformat()] = 0
        return result

    # ── retranslate ──────────────────────────────────────
    def retranslate(self):
        """Update all UI strings to the current language."""
        # Period selector buttons
        _keys = ["analytics.period_today", "analytics.period_7",
                 "analytics.period_30", "analytics.period_90"]
        for btn, key in zip(self._period_btns, _keys):
            btn.setText(tr(key))
        self._cal_btn.setText(tr("analytics.calendar"))
        self._cal_btn.setToolTip(tr("analytics.calendar_tip"))

        # KPI card labels and tooltips
        self.kpi_completed.set_label(tr("analytics.kpi_completed"))
        self.kpi_completed.setToolTip(tr("analytics.tip_completed"))
        self.kpi_pct.set_label(tr("analytics.kpi_pct"))
        self.kpi_pct.setToolTip(tr("analytics.tip_pct"))
        self.kpi_avg.set_label(tr("analytics.kpi_avg"))
        self.kpi_avg.setToolTip(tr("analytics.tip_avg"))
        self.kpi_streak.set_label(tr("analytics.kpi_streak"))
        self.kpi_streak.setToolTip(tr("analytics.tip_streak"))

        if not self._charts_ready:
            return

        # Chart titles and axis labels
        _tc = _th()["text"]
        self._bar_widget.setLabel("left", tr("analytics.chart_bar_left"))
        self._bar_widget.setTitle(tr("analytics.chart_bar_title"), color=_tc, size="11pt")
        self._line_widget.setTitle(tr("analytics.chart_line_title"), color=_tc, size="11pt")
        self._weekday_widget.setTitle(tr("analytics.chart_weekday_title"), color=_tc, size="11pt")
        self._weekday_widget.setLabel("left", tr("analytics.chart_weekday_left"))
        self._cumul_widget.setTitle(tr("analytics.chart_cumul_title"), color=_tc, size="11pt")
        self._cumul_widget.setLabel("left", tr("analytics.chart_cumul_left"))

        # Repaint custom-painted widgets
        self._donut_widget.update()

        # Refresh data that contains translated strings (day labels, legend, KPI deltas)
        self._refresh_kpi()
        self._refresh_weekday()
        self._refresh_lines()

    def apply_theme(self):
        """Re-apply theme colours to all widgets. Call when theme changes."""
        th = _th()
        is_glass = _styles._active_theme == "glass"
        bg = th["bg_dark"]           # analytics page background
        chart_bg = None              # always transparent — card frame provides the bg
        fg = th["text_sec"]
        tc = th["text"]

        # Update scroll area + inner widget background
        if hasattr(self, "_inner"):
            if is_glass:
                self._inner.setAutoFillBackground(False)
            else:
                from PyQt6.QtGui import QPalette, QColor as _QColor
                _pal = self._inner.palette()
                _bg_col = _QColor(bg)
                for _g in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive,
                           QPalette.ColorGroup.Disabled):
                    _pal.setColor(_g, QPalette.ColorRole.Window, _bg_col)
                self._inner.setPalette(_pal)
                self._inner.setAutoFillBackground(True)
        if hasattr(self, "_scroll"):
            if is_glass:
                self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
            else:
                self._scroll.setStyleSheet(
                    f"QScrollArea {{ background: {bg}; border: none; }}"
                    f"QScrollArea > QWidget > QWidget {{ background: {bg}; }}"
                )

        pg.setConfigOptions(background=chart_bg or "#00000000", foreground=fg, antialias=True)

        if self._charts_ready:
            for pw in (self._bar_widget, self._line_widget,
                       self._weekday_widget, self._cumul_widget):
                pw.setBackground(chart_bg)
                for axis in ("bottom", "left"):
                    pw.getAxis(axis).setTextPen(pg.mkPen(fg))
                    pw.getAxis(axis).setPen(pg.mkPen(color=fg, width=1))
            # Update titles
            self._bar_widget.setTitle(tr("analytics.chart_bar_title"), color=tc, size="11pt")
            self._line_widget.setTitle(tr("analytics.chart_line_title"), color=tc, size="11pt")
            self._weekday_widget.setTitle(tr("analytics.chart_weekday_title"), color=tc, size="11pt")
            self._cumul_widget.setTitle(tr("analytics.chart_cumul_title"), color=tc, size="11pt")
            self._bar_widget.setLabel("left", tr("analytics.chart_bar_left"))
            self._weekday_widget.setLabel("left", tr("analytics.chart_weekday_left"))
            self._cumul_widget.setLabel("left", tr("analytics.chart_cumul_left"))

        # Update KPI cards
        for card in (self.kpi_completed, self.kpi_pct, self.kpi_avg, self.kpi_streak):
            card.apply_theme()

        # Update donut
        if hasattr(self, "_donut_widget"):
            self._donut_widget.apply_theme()

        # Update calendar overlay if open
        if self._cal_overlay is not None:
            self._cal_overlay.apply_theme()

        # Refresh charts with new colors
        self.refresh()

    @staticmethod
    def _make_date_ticks(dates: list[str]) -> list[tuple[int, str]]:
        """Create sparse tick labels so they don't overlap."""
        n = len(dates)
        if n <= 1:
            step = 1
        elif n <= 10:
            step = 1
        elif n <= 35:
            step = 5
        else:
            step = 10

        ticks = []
        for i, d in enumerate(dates):
            if i % step == 0 or i == n - 1:
                short = d[5:]  # "MM-DD"
                ticks.append((i, short))
        return ticks
