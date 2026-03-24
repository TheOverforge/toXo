from __future__ import annotations

import calendar as _cal
from datetime import date, datetime, timezone

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QPushButton, QLabel, QScrollArea, QSizePolicy, QSplitter, QLineEdit, QToolTip,
)
from PyQt6.QtCore import Qt, QRectF, QPoint, pyqtSignal, QPointF
from PyQt6.QtGui import QFont, QColor, QPainter, QPen

import pyqtgraph as pg

from shared.i18n import tr, current_language
import app.styles.themes as _styles

_ACCENT       = "#0a84ff"
_GREEN        = "#30d158"
_TEXT         = "#f5f5f7"
_TEXT_SEC     = "#98989d"
_BG           = "#0d0d0f"
_GLASS        = "rgba(255,255,255,0.06)"
_GLASS_BORDER = "rgba(255,255,255,0.10)"
_PRI_COLORS   = ["", "#ff9f0a", "#ff9f0a", "#ff453a"]


def _th() -> dict:
    """Return the active theme colour dict from styles."""
    return _styles._THEMES[_styles._active_theme]


def _month_names() -> list[str]:
    return tr("analytics.months").split(",")


def _dow_names() -> list[str]:
    return tr("analytics.dow").split(",")


# ── Task row ─────────────────────────────────────────────────────────────────
class _TaskRow(QFrame):
    clicked          = pyqtSignal(int)
    done_toggled     = pyqtSignal(int, bool)
    deadline_removed = pyqtSignal(int)

    def __init__(self, task, parent=None):
        super().__init__(parent)
        self._task_id = task.id
        self._is_done = task.is_done
        self.setObjectName("CalTaskRow")
        self.setFixedHeight(40)
        _t = _th()
        self.setStyleSheet(f"""
            #CalTaskRow {{
                background: {_t["glass"]};
                border: 1px solid {_t["glass_border"]};
                border-radius: 8px;
            }}
            #CalTaskRow:hover {{ background: {_t["glass_hover"]}; }}
        """)

        h = QHBoxLayout(self)
        h.setContentsMargins(6, 0, 6, 0)
        h.setSpacing(6)

        self._done_btn = QPushButton("✓" if task.is_done else "○")
        self._done_btn.setFixedSize(26, 26)
        self._done_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        done_color = _GREEN if task.is_done else _th()["text_sec"]
        self._done_btn.setStyleSheet(f"""
            QPushButton {{
                color: {done_color}; font-size: 14px;
                background: transparent; border: none; padding: 0;
            }}
            QPushButton:hover {{ color: {_GREEN}; }}
        """)
        self._done_btn.clicked.connect(self._toggle_done)
        h.addWidget(self._done_btn)

        self._lbl = QLabel(task.title or "…")
        _txt_col = "#888" if task.is_done else _th()["text"]
        self._lbl.setStyleSheet(f"""
            color: {_txt_col}; font-size: 13px;
            background: transparent;
            {'text-decoration: line-through;' if task.is_done else ''}
        """)
        self._lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._lbl.setWordWrap(False)
        self._lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        h.addWidget(self._lbl, 1)

        if task.priority > 0:
            badge = QLabel("!" * task.priority)
            badge.setStyleSheet(
                f"color: {_PRI_COLORS[min(task.priority, 3)]}; font-size: 11px; "
                f"font-weight: bold; background: transparent;"
            )
            badge.setFixedWidth(20)
            h.addWidget(badge)

        self._rm_btn = QPushButton("×")
        self._rm_btn.setFixedSize(22, 22)
        self._rm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rm_btn.setToolTip(tr("calendar.remove_deadline"))
        _rm_idle = "rgba(255,255,255,0.3)" if _styles._active_theme == "dark" else "rgba(0,0,0,0.3)"
        self._rm_btn.setStyleSheet(f"""
            QPushButton {{
                color: {_rm_idle}; font-size: 16px;
                background: transparent; border: none; padding: 0;
            }}
            QPushButton:hover {{ color: #ff453a; }}
        """)
        self._rm_btn.clicked.connect(lambda: self.deadline_removed.emit(self._task_id))
        h.addWidget(self._rm_btn)

    def _toggle_done(self):
        self.done_toggled.emit(self._task_id, not self._is_done)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._done_btn.geometry().contains(event.position().toPoint()):
                self.clicked.emit(self._task_id)
        super().mousePressEvent(event)


# ── Calendar grid ─────────────────────────────────────────────────────────────
class _CalGridWidget(QWidget):
    day_selected      = pyqtSignal(object)   # date → single click
    day_double_clicked = pyqtSignal(object)  # date → double click = create task
    tasks_dropped_on_day = pyqtSignal(list, object)  # [task_ids], date

    _CELL_W = 58
    _CELL_H = 54
    _HDR_H  = 44
    _DOW_H  = 22
    _PAD    = 12

    def __init__(self, parent=None):
        super().__init__(parent)
        today = date.today()
        self._year  = today.year
        self._month = today.month
        self._selected: date = today
        self._hover_date: date | None = None
        self._drag_hover_day: date | None = None

        self._day_rects: list[tuple[QRectF, date]] = []
        self._prev_rect = QRectF()
        self._next_rect = QRectF()

        # {date_str: (total, done, overdue)} for tooltip
        self._day_summaries: dict[str, tuple[int, int, int]] = {}
        # {date_str: [hex_color, ...]} up to 3 per day
        self._cat_dots: dict[str, list[str]] = {}

        self.setMinimumWidth(7 * self._CELL_W + 2 * self._PAD)
        self.setMinimumHeight(self._HDR_H + self._DOW_H + 6 * self._CELL_H + 2 * self._PAD + 8)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)

    def set_day_summaries(self, s: dict):
        self._day_summaries = s
        self.update()

    def set_cat_dots(self, dots: dict):
        self._cat_dots = dots
        self.update()

    # ── navigation ──────────────────────────────────────────────────────────
    def _prev_month(self):
        self._month, self._year = (12, self._year - 1) if self._month == 1 else (self._month - 1, self._year)
        self._clamp_selected()
        self.day_selected.emit(self._selected)
        self.update()

    def _next_month(self):
        self._month, self._year = (1, self._year + 1) if self._month == 12 else (self._month + 1, self._year)
        self._clamp_selected()
        self.day_selected.emit(self._selected)
        self.update()

    def _clamp_selected(self):
        try:
            self._selected = self._selected.replace(year=self._year, month=self._month)
        except ValueError:
            last = _cal.monthrange(self._year, self._month)[1]
            self._selected = self._selected.replace(year=self._year, month=self._month, day=last)

    # ── events ──────────────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        pos = QPointF(event.position())
        if self._prev_rect.contains(pos):
            self._prev_month(); return
        if self._next_rect.contains(pos):
            self._next_month(); return
        for rect, d in self._day_rects:
            if rect.contains(pos):
                self._selected = d
                self.day_selected.emit(d)
                self.update()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        pos = QPointF(event.position())
        for rect, d in self._day_rects:
            if rect.contains(pos):
                self.day_double_clicked.emit(d)
                return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        pos = QPointF(event.position())
        hovered: date | None = None
        for rect, d in self._day_rects:
            if rect.contains(pos):
                hovered = d
                break

        if hovered != self._hover_date:
            self._hover_date = hovered
            self.update()

        if hovered:
            ds = hovered.isoformat()
            lang = current_language()
            ru = lang == "ru"
            if ds in self._day_summaries:
                total, done, overdue = self._day_summaries[ds]
                lines = (
                    [f"Задач: {total}", f"✓ Выполнено: {done}"]
                    if ru else
                    [f"Tasks: {total}", f"✓ Done: {done}"]
                )
                if overdue:
                    lines.append(f"⚠ Просрочено: {overdue}" if ru else f"⚠ Overdue: {overdue}")
                lines.append("Двойной клик — создать задачу" if ru else "Double-click to create task")
                tip = "\n".join(lines)
            else:
                tip = "Двойной клик — создать задачу" if ru else "Double-click to create task"
            QToolTip.showText(event.globalPosition().toPoint(), tip, self)
        else:
            QToolTip.hideText()

        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover_date = None
        QToolTip.hideText()
        self.update()
        super().leaveEvent(event)

    # ── drag-drop (receive task batch) ───────────────────────────────────────
    def _day_at(self, pos: QPoint) -> "date | None":
        for rect, d in self._day_rects:
            if rect.contains(pos.x(), pos.y()):
                return d
        return None

    def dragEnterEvent(self, event):
        m = event.mimeData()
        if m.hasFormat("application/x-task-id") or m.hasFormat("application/x-task-ids"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        d = self._day_at(event.position().toPoint())
        if d != self._drag_hover_day:
            self._drag_hover_day = d
            self.update()
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._drag_hover_day = None
        self.update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        d = self._day_at(event.position().toPoint())
        self._drag_hover_day = None
        self.update()
        if d is None:
            event.ignore()
            return
        m = event.mimeData()
        if m.hasFormat("application/x-task-ids"):
            ids = [int(x) for x in bytes(m.data("application/x-task-ids")).decode().split(",")]
        elif m.hasFormat("application/x-task-id"):
            ids = [int(bytes(m.data("application/x-task-id")).decode())]
        else:
            event.ignore()
            return
        event.acceptProposedAction()
        self.tasks_dropped_on_day.emit(ids, d)

    # ── paint ────────────────────────────────────────────────────────────────
    def paintEvent(self, _event):
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

        # Header arrows
        arrow_w = 36
        self._prev_rect = QRectF(pad, pad, arrow_w, self._HDR_H)
        self._next_rect = QRectF(self.width() - pad - arrow_w, pad, arrow_w, self._HDR_H)
        p.setPen(QColor(_ACCENT))
        p.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        p.drawText(self._prev_rect, Qt.AlignmentFlag.AlignCenter, "◀")
        p.drawText(self._next_rect, Qt.AlignmentFlag.AlignCenter, "▶")

        # Month/year title
        p.setPen(QColor(_txt))
        p.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
        title = f"{_month_names()[self._month - 1]} {self._year}"
        hdr_rect = QRectF(pad + arrow_w, pad, self.width() - 2 * (pad + arrow_w), self._HDR_H)
        p.drawText(hdr_rect, Qt.AlignmentFlag.AlignCenter, title)

        # Weekday headers
        y_dow = pad + self._HDR_H
        p.setPen(QColor(_txt_sec))
        p.setFont(QFont("Segoe UI", 9))
        grid_w = 7 * cw
        grid_x0 = (self.width() - grid_w) // 2 if self.width() > grid_w + 2 * pad else pad
        for col, name in enumerate(_dow_names()):
            p.drawText(QRectF(grid_x0 + col * cw, y_dow, cw, self._DOW_H), Qt.AlignmentFlag.AlignCenter, name)

        # Day grid
        y_grid = y_dow + self._DOW_H
        for ri, week in enumerate(_cal.Calendar(firstweekday=0).monthdayscalendar(self._year, self._month)):
            for ci, day in enumerate(week):
                if day == 0:
                    continue

                x = grid_x0 + ci * cw
                y = y_grid + ri * ch
                inset = 3
                cell = QRectF(x + inset, y + inset, cw - 2 * inset, ch - 2 * inset)
                day_date   = date(self._year, self._month, day)
                ds         = day_date.isoformat()
                is_today    = day_date == today
                is_selected = day_date == self._selected
                is_hovered  = day_date == self._hover_date and not is_selected

                self._day_rects.append((cell, day_date))

                # Cell background (white-alpha on dark, black-alpha on light)
                p.setPen(Qt.PenStyle.NoPen)
                if is_selected:
                    p.setBrush(QColor(10, 132, 255, 55))
                elif is_hovered:
                    p.setBrush(QColor(255, 255, 255, 18) if _dark else QColor(0, 0, 0, 18))
                else:
                    p.setBrush(QColor(255, 255, 255, 10) if _dark else QColor(0, 0, 0, 10))
                p.drawRoundedRect(cell, 8, 8)

                # Border
                if is_today:
                    p.setPen(QPen(QColor(_ACCENT), 1.8))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRoundedRect(cell, 8, 8)
                elif is_selected:
                    p.setPen(QPen(QColor(10, 132, 255, 160), 1.0))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRoundedRect(cell, 8, 8)
                # Drag-hover highlight
                if day_date == self._drag_hover_day:
                    p.setPen(QPen(QColor(10, 132, 255, 220), 2.0))
                    p.setBrush(QColor(10, 132, 255, 40))
                    p.drawRoundedRect(cell, 8, 8)

                # Day number
                if is_today:
                    txt_color = QColor(_ACCENT)
                elif is_selected:
                    txt_color = QColor(_txt)
                else:
                    txt_color = QColor(_txt_sec)
                p.setPen(txt_color)
                p.setFont(QFont("Segoe UI", 13,
                                QFont.Weight.Medium if (is_today or is_selected) else QFont.Weight.Normal))
                p.drawText(
                    QRectF(x + inset, y + inset + 2, cw - 2 * inset, ch - 2 * inset - 10),
                    Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop,
                    str(day),
                )

                # Category colour dots (up to 3) at bottom of cell
                colors = self._cat_dots.get(ds)
                if colors:
                    dot_r   = 3
                    gap     = 3
                    n       = len(colors)
                    total_w = n * 2 * dot_r + (n - 1) * gap
                    sx      = x + cw / 2 - total_w / 2
                    sy      = y + ch - inset - dot_r * 2 - 2
                    p.setPen(Qt.PenStyle.NoPen)
                    for i, color in enumerate(colors):
                        p.setBrush(QColor(color))
                        p.drawEllipse(QRectF(sx + i * (2 * dot_r + gap), sy, dot_r * 2, dot_r * 2))

        p.end()


# ── Day panel ────────────────────────────────────────────────────────────────
class _DayPanel(QFrame):
    task_open    = pyqtSignal(int)
    task_added   = pyqtSignal(int)
    data_changed = pyqtSignal()

    @staticmethod
    def _style_normal() -> str:
        th = _th()
        return f"""
            #CalDayPanel {{
                background: transparent;
                border-left: 1px solid {th["glass_border"]};
            }}
            QLabel {{ background: transparent; }}
            QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
        """

    @staticmethod
    def _style_drop() -> str:
        return f"""
            #CalDayPanel {{
                background: rgba(10,132,255,0.05);
                border-left: 2px solid {_ACCENT};
            }}
            QLabel {{ background: transparent; }}
            QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
        """

    def __init__(self, svc, parent=None):
        super().__init__(parent)
        self._svc = svc
        self._selected_date: date = date.today()
        self._plot_widget: pg.PlotWidget | None = None

        self.setObjectName("CalDayPanel")
        self.setStyleSheet(self._style_normal())
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Header
        hdr = QHBoxLayout()
        self._lbl_date = QLabel()
        self._lbl_date.setStyleSheet(f"color: {_th()['text']}; font-size: 15px; font-weight: 600;")
        hdr.addWidget(self._lbl_date, 1)

        self._btn_add = QPushButton(tr("calendar.add_task"))
        self._btn_add.setObjectName("AccentBtn")
        self._btn_add.setFixedHeight(32)
        self._btn_add.clicked.connect(self._show_inline_input)
        hdr.addWidget(self._btn_add)
        layout.addLayout(hdr)

        # Inline title input
        self._inline_input = QLineEdit()
        self._inline_input.setObjectName("QuickAdd")
        self._inline_input.setPlaceholderText(tr("cal.inline_ph"))
        self._inline_input.setFixedHeight(34)
        self._inline_input.hide()
        self._inline_input.returnPressed.connect(self._confirm_add_task)
        self._inline_input.installEventFilter(self)
        layout.addWidget(self._inline_input)

        # Task scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._tasks_w  = QWidget()
        self._tasks_w.setStyleSheet("background: transparent;")
        self._tasks_vl = QVBoxLayout(self._tasks_w)
        self._tasks_vl.setContentsMargins(0, 0, 0, 0)
        self._tasks_vl.setSpacing(6)
        self._tasks_vl.addStretch(1)
        self._scroll.setWidget(self._tasks_w)
        layout.addWidget(self._scroll, 2)

        # Bar chart — transparent bg, wrapped in glass card like analytics
        self._plot = pg.PlotWidget()
        self._plot.setBackground(None)
        self._plot.setFixedHeight(180)
        self._plot.showGrid(x=False, y=True, alpha=0.15)
        self._plot.setMouseEnabled(x=False, y=False)
        self._plot.setMenuEnabled(False)
        self._plot.hideButtons()
        tick_font = QFont("Segoe UI", 8)
        self._plot.getAxis("bottom").setStyle(tickFont=tick_font)
        self._plot.getAxis("left").setStyle(tickFont=tick_font)
        chart_card = QFrame()
        chart_card.setObjectName("FinSectionCard")
        card_lay = QVBoxLayout(chart_card)
        card_lay.setContentsMargins(12, 10, 12, 10)
        card_lay.setSpacing(0)
        card_lay.addWidget(self._plot)
        layout.addWidget(chart_card)
        self._apply_plot_theme()

    def _apply_plot_theme(self):
        th = _th()
        fg = th["text_sec"]
        self._plot.setBackground(None)
        axis_pen = pg.mkPen(color=fg, width=1)
        self._plot.getAxis("bottom").setTextPen(pg.mkPen(fg))
        self._plot.getAxis("left").setTextPen(pg.mkPen(fg))
        self._plot.getAxis("bottom").setPen(axis_pen)
        self._plot.getAxis("left").setPen(axis_pen)

    def apply_theme(self):
        self.setStyleSheet(self._style_normal())
        self._lbl_date.setStyleSheet(f"color: {_th()['text']}; font-size: 15px; font-weight: 600;")
        self._apply_plot_theme()

    def set_selected_date(self, d: date):
        self._selected_date = d
        self._hide_inline_input()

    def refresh(self, selected_date: date, all_tasks: list, month_data: dict):
        self._selected_date = selected_date
        month_names = _month_names()
        self._lbl_date.setText(
            f"{selected_date.day} {month_names[selected_date.month - 1]} {selected_date.year}"
        )

        # Clear task rows (keep stretch)
        while self._tasks_vl.count() > 1:
            item = self._tasks_vl.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        ds = selected_date.isoformat()
        day_tasks = sorted(
            [t for t in all_tasks if t.deadline_at and t.deadline_at[:10] == ds and not t.is_archived],
            key=lambda t: (t.is_done, t.deadline_at or ""),
        )

        if day_tasks:
            for t in day_tasks:
                row = _TaskRow(t)
                row.clicked.connect(self.task_open)
                row.done_toggled.connect(self._on_done_toggled)
                row.deadline_removed.connect(self._on_deadline_removed)
                self._tasks_vl.insertWidget(self._tasks_vl.count() - 1, row)
        else:
            lbl = QLabel(tr("calendar.empty_day"))
            lbl.setStyleSheet(f"color: {_th()['text_sec']}; font-size: 12px; font-style: italic;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._tasks_vl.insertWidget(0, lbl)

        self._update_chart(month_data, selected_date)

    def _update_chart(self, month_data: dict, selected_date: date):
        self._plot.clear()
        year, month = selected_date.year, selected_date.month
        last_day = _cal.monthrange(year, month)[1]
        xs = list(range(1, last_day + 1))
        created_vals, done_vals = [], []
        for day in xs:
            cr, co = month_data.get(date(year, month, day).isoformat(), (0, 0))
            created_vals.append(cr)
            done_vals.append(co)

        th = _th()
        accent = QColor(th["accent"])
        theme = _styles._active_theme
        green_hex = "#52d38a" if theme == "glass" else "#16a34a" if theme == "light" else "#30d158"
        green = QColor(green_hex)

        bar_w = 0.35
        self._plot.addItem(pg.BarGraphItem(
            x=[x - bar_w / 2 for x in xs], height=created_vals, width=bar_w,
            brush=pg.mkBrush(accent.red(), accent.green(), accent.blue(), 180),
            pen=pg.mkPen(None),
        ))
        self._plot.addItem(pg.BarGraphItem(
            x=[x + bar_w / 2 for x in xs], height=done_vals, width=bar_w,
            brush=pg.mkBrush(green.red(), green.green(), green.blue(), 180),
            pen=pg.mkPen(None),
        ))
        self._plot.addItem(pg.InfiniteLine(
            pos=selected_date.day, angle=90,
            pen=pg.mkPen(color=th["accent"], width=1, style=Qt.PenStyle.DashLine),
        ))
        self._plot.setXRange(0.5, last_day + 0.5, padding=0)
        max_y = max(max(created_vals, default=0), max(done_vals, default=0), 10)
        self._plot.setYRange(0, max_y * 1.15, padding=0)
        self._plot.getAxis("bottom").setTicks([[(x, str(x)) for x in xs]])

    # ── drag-drop (receive tasks from task list) ─────────────────────────
    def dragEnterEvent(self, event):
        m = event.mimeData()
        if m.hasFormat("application/x-task-id") or m.hasFormat("application/x-task-ids"):
            self.setStyleSheet(self._style_drop())
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.setStyleSheet(self._style_normal())
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.setStyleSheet(self._style_normal())
        m = event.mimeData()
        if m.hasFormat("application/x-task-ids"):
            ids = [int(x) for x in bytes(m.data("application/x-task-ids")).decode().split(",")]
        elif m.hasFormat("application/x-task-id"):
            ids = [int(bytes(m.data("application/x-task-id")).decode())]
        else:
            event.ignore()
            return
        event.acceptProposedAction()
        d = self._selected_date
        deadline = datetime(d.year, d.month, d.day, 9, 0, tzinfo=timezone.utc).isoformat(timespec="seconds")
        for tid in ids:
            self._svc.set_deadline(tid, deadline)
        self.data_changed.emit()

    def _on_done_toggled(self, task_id: int, new_done: bool):
        self._svc.set_done(task_id, new_done)
        self.data_changed.emit()

    def _on_deadline_removed(self, task_id: int):
        self._svc.set_deadline(task_id, None)
        self.data_changed.emit()

    def _show_inline_input(self):
        self._btn_add.hide()
        self._inline_input.clear()
        self._inline_input.show()
        self._inline_input.setFocus()

    def _hide_inline_input(self):
        self._inline_input.hide()
        self._btn_add.show()

    def eventFilter(self, obj, event):
        if obj is self._inline_input:
            from PyQt6.QtCore import QEvent
            if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                self._hide_inline_input()
                return True
        return super().eventFilter(obj, event)

    def _confirm_add_task(self):
        title = self._inline_input.text().strip()
        self._hide_inline_input()
        if not title:
            return
        d = self._selected_date
        deadline_iso = datetime(d.year, d.month, d.day, 9, 0, tzinfo=timezone.utc).isoformat(timespec="seconds")
        tid = self._svc.create_task(title=title)
        self._svc.set_deadline(tid, deadline_iso)
        self.task_added.emit(tid)


# ── Calendar page (top-level) ────────────────────────────────────────────────
class CalendarPage(QWidget):
    task_open_requested = pyqtSignal(int)
    task_added          = pyqtSignal(int)
    data_changed        = pyqtSignal()
    filter_by_day       = pyqtSignal(object)   # date → filter left list
    create_task_on_day  = pyqtSignal(object)   # date → create task (double-click)

    def __init__(self, svc, analytics_svc, parent=None):
        super().__init__(parent)
        self._svc            = svc
        self._analytics_svc  = analytics_svc
        self._all_tasks: list = []
        self._categories: list = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        _dark = _styles._active_theme == "dark"
        _spl_clr = "rgba(255,255,255,0.08)" if _dark else "rgba(0,0,0,0.08)"
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {_spl_clr}; }}")
        self._splitter = splitter

        self._cal = _CalGridWidget()
        self._day = _DayPanel(svc)
        splitter.addWidget(self._cal)
        splitter.addWidget(self._day)
        splitter.setSizes([380, 620])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        # Signals
        self._cal.day_selected.connect(self._on_day_selected)
        self._cal.day_double_clicked.connect(self.create_task_on_day)
        self._cal.tasks_dropped_on_day.connect(self._on_tasks_dropped_on_day)
        self._day.task_open.connect(self.task_open_requested)
        self._day.task_added.connect(self.task_added)
        self._day.data_changed.connect(self.data_changed)

    @property
    def selected_date(self) -> date:
        return self._cal._selected

    def refresh(self, all_tasks: list, categories: list | None = None):
        self._all_tasks = all_tasks
        if categories is not None:
            self._categories = categories

        today_str = date.today().isoformat()

        # Category colour dots: {date_str: [color, ...]} up to 3 unique per day
        cat_colors = {c.id: c.color for c in self._categories}
        cat_dots: dict[str, list[str]] = {}
        for t in all_tasks:
            if t.deadline_at and not t.is_archived:
                ds    = t.deadline_at[:10]
                color = cat_colors.get(t.category_id, _TEXT_SEC) if t.category_id else _TEXT_SEC
                lst   = cat_dots.setdefault(ds, [])
                if color not in lst and len(lst) < 3:
                    lst.append(color)
        self._cal.set_cat_dots(cat_dots)

        # Day summaries for hover tooltip: {date_str: (total, done, overdue)}
        summaries: dict[str, list[int]] = {}
        for t in all_tasks:
            if t.deadline_at and not t.is_archived:
                ds = t.deadline_at[:10]
                row = summaries.setdefault(ds, [0, 0, 0])
                row[0] += 1
                if t.is_done:
                    row[1] += 1
                elif ds < today_str:
                    row[2] += 1
        self._cal.set_day_summaries({k: tuple(v) for k, v in summaries.items()})  # type: ignore[arg-type]

        self._refresh_day()

    def _on_day_selected(self, d: date):
        self._day.set_selected_date(d)
        self.filter_by_day.emit(d)   # ← filter left list
        self._refresh_day()

    def _refresh_day(self):
        d = self._cal._selected
        month_data = self._analytics_svc.month_data(d.year, d.month)
        self._day.refresh(d, self._all_tasks, month_data)

    def _on_tasks_dropped_on_day(self, task_ids: list, d: date):
        deadline = datetime(d.year, d.month, d.day, 9, 0, tzinfo=timezone.utc).isoformat(timespec="seconds")
        for tid in task_ids:
            self._svc.set_deadline(tid, deadline)
        self.data_changed.emit()

    def apply_theme(self):
        """Re-apply theme colours when the user switches theme."""
        _dark = _styles._active_theme == "dark"
        _spl_clr = "rgba(255,255,255,0.08)" if _dark else "rgba(0,0,0,0.08)"
        self._splitter.setStyleSheet(f"QSplitter::handle {{ background: {_spl_clr}; }}")
        self._day.apply_theme()
        self._cal.update()
        self._refresh_day()

    def retranslate(self):
        """Update all static UI strings after a language change."""
        self._day._btn_add.setText(tr("calendar.add_task"))
        self._day._inline_input.setPlaceholderText(tr("cal.inline_ph"))
