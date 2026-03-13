from __future__ import annotations

from shared.i18n import tr

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDateTimeEdit, QComboBox, QCheckBox, QStyledItemDelegate, QStyle,
    QStyleOptionViewItem,
)
from PyQt6.QtCore import (
    Qt, QSize, QDateTime, QRectF,
)
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QPainterPath,
)


class ReminderDialog(QDialog):
    """Dialog to set or clear a reminder or deadline date/time for a task.

    mode="reminder" (default) — shows reminder labels
    mode="deadline"           — shows deadline labels
    """

    def __init__(self, current_remind_at: str | None = None, mode: str = "reminder", parent=None):
        super().__init__(parent)
        is_deadline = (mode == "deadline")
        self.setWindowTitle(tr("rdlg.deadline_title") if is_deadline else tr("rdlg.title"))
        self.setModal(True)
        self.setFixedSize(320, 190)
        self._result_dt: str | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 16)

        lbl = QLabel(tr("rdlg.deadline_at") if is_deadline else tr("rdlg.at"))
        lbl.setStyleSheet("color: #f5f5f7; font-size: 13px;")
        layout.addWidget(lbl)

        self.dt_edit = QDateTimeEdit()
        self.dt_edit.setDisplayFormat("dd.MM.yyyy  HH:mm")
        self.dt_edit.setCalendarPopup(True)

        # Dark theme for the calendar popup
        _cal = self.dt_edit.calendarWidget()
        if _cal is not None:
            _cal.setStyleSheet("""
                QCalendarWidget {
                    background-color: #1c1c1e;
                    color: #f5f5f7;
                    border-radius: 10px;
                }
                QCalendarWidget QWidget#qt_calendar_navigationbar {
                    background-color: #2c2c2e;
                    border-bottom: 1px solid rgba(255,255,255,0.10);
                    min-height: 38px;
                }
                QCalendarWidget QToolButton {
                    background-color: transparent;
                    color: #f5f5f7;
                    font-size: 13px;
                    border: none;
                    border-radius: 6px;
                    padding: 4px 8px;
                    margin: 2px;
                }
                QCalendarWidget QToolButton:hover {
                    background-color: rgba(255,255,255,0.10);
                }
                QCalendarWidget QToolButton:pressed {
                    background-color: rgba(255,255,255,0.18);
                }
                QCalendarWidget QToolButton::menu-indicator { image: none; }
                QCalendarWidget QSpinBox {
                    background-color: rgba(255,255,255,0.07);
                    color: #f5f5f7;
                    border: 1px solid rgba(255,255,255,0.12);
                    border-radius: 4px;
                    padding: 2px 4px;
                    font-size: 13px;
                    selection-background-color: #0a84ff;
                }
                QCalendarWidget QSpinBox::up-button,
                QCalendarWidget QSpinBox::down-button { width: 0; height: 0; }
                QCalendarWidget QAbstractItemView {
                    background-color: #1c1c1e;
                    selection-background-color: #0a84ff;
                    selection-color: #ffffff;
                    color: #f5f5f7;
                    outline: none;
                    gridline-color: rgba(255,255,255,0.06);
                    font-size: 12px;
                }
                QCalendarWidget QAbstractItemView:enabled {
                    color: #f5f5f7;
                }
                QCalendarWidget QAbstractItemView:disabled {
                    color: #48484a;
                }
                QCalendarWidget QWidget {
                    alternate-background-color: #1c1c1e;
                }
                QCalendarWidget QMenu {
                    background-color: #2c2c2e;
                    color: #f5f5f7;
                    border: 1px solid rgba(255,255,255,0.12);
                    border-radius: 8px;
                }
                QCalendarWidget QMenu::item:selected {
                    background-color: #0a84ff;
                }
            """)

        self.dt_edit.setStyleSheet("""
            QDateTimeEdit {
                background: rgba(255,255,255,0.07);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 8px;
                padding: 6px 12px;
                color: #f5f5f7;
                font-size: 14px;
            }
            QDateTimeEdit:focus {
                border: 1px solid #0a84ff;
            }
            QDateTimeEdit::drop-button {
                border: none;
                width: 20px;
            }
        """)

        # Pre-fill: if task already has a reminder, convert UTC → local
        if current_remind_at:
            try:
                from datetime import datetime, timezone
                dt_utc = datetime.fromisoformat(current_remind_at)
                if dt_utc.tzinfo is None:
                    dt_utc = dt_utc.replace(tzinfo=timezone.utc)
                dt_local = dt_utc.astimezone()
                qdt = QDateTime(
                    dt_local.year, dt_local.month, dt_local.day,
                    dt_local.hour, dt_local.minute, 0
                )
                self.dt_edit.setDateTime(qdt)
            except Exception:
                self.dt_edit.setDateTime(self._default_dt())
        else:
            # Default: one hour from now, seconds zeroed so display matches stored value
            self.dt_edit.setDateTime(self._default_dt())

        layout.addWidget(self.dt_edit)
        layout.addStretch(1)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        clear_btn = QPushButton(tr("rdlg.clear"))
        clear_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,69,58,0.10);
                border: 1px solid rgba(255,69,58,0.25);
                border-radius: 8px;
                padding: 6px 12px;
                color: #ff453a;
                font-size: 12px;
            }
            QPushButton:hover { background: rgba(255,69,58,0.20); }
        """)
        clear_btn.clicked.connect(self._on_clear)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch(1)

        cancel_btn = QPushButton(tr("rdlg.cancel"))
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.07);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 8px;
                padding: 6px 14px;
                color: #f5f5f7;
                font-size: 13px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.12); }
        """)
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton(tr("rdlg.save"))
        save_btn.setStyleSheet("""
            QPushButton {
                background: #0a84ff;
                border: none;
                border-radius: 8px;
                padding: 6px 14px;
                color: #ffffff;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover { background: #409cff; }
        """)
        save_btn.clicked.connect(self._on_save)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        self.setStyleSheet("""
            QDialog {
                background: #1c1c1e;
                color: #f5f5f7;
            }
        """)

    @staticmethod
    def _default_dt() -> QDateTime:
        """Current time + 1 hour, seconds zeroed (so display matches what gets stored)."""
        dt = QDateTime.currentDateTime().addSecs(3600)
        dt.setTime(dt.time().addSecs(-dt.time().second()))
        return dt

    def _on_save(self):
        """Convert local QDateTime → UTC ISO string and accept."""
        from datetime import datetime, timezone
        qdt = self.dt_edit.dateTime()
        qdt.setTime(qdt.time().addSecs(-qdt.time().second()))  # zero out seconds
        dt_local = qdt.toPyDateTime()
        local_tz = datetime.now(timezone.utc).astimezone().tzinfo
        dt_local = dt_local.replace(tzinfo=local_tz)
        dt_utc = dt_local.astimezone(timezone.utc)
        self._result_dt = dt_utc.isoformat(timespec="seconds")
        self.accept()

    def _on_clear(self):
        """Clear the reminder and accept."""
        self._result_dt = None
        self.accept()

    def get_remind_at(self) -> str | None:
        """Returns UTC ISO string or None after dialog is accepted."""
        return self._result_dt


# =========================
# Crisp anti-aliased checkbox (no Qt-style pixel artifacts)
# =========================
class CrispCheckBox(QCheckBox):
    """Checkbox drawn entirely with QPainter — crisp at any DPI."""

    _SZ = 20    # indicator size in px
    _R  = 5.0   # corner radius

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        sz   = self._SZ
        y0   = (self.height() - sz) // 2
        box  = QRectF(1.0, y0, sz, sz)
        hover   = self.underMouse()
        checked = self.isChecked()

        if checked:
            # Filled accent background
            p.setBrush(QBrush(QColor(10, 132, 255)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(box, self._R, self._R)
            # White checkmark
            pen = QPen(QColor(255, 255, 255), 2.0,
                       Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap,
                       Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            cx, cy = box.center().x(), box.center().y()
            path = QPainterPath()
            path.moveTo(cx - sz * 0.20, cy + sz * 0.02)
            path.lineTo(cx - sz * 0.02, cy + sz * 0.20)
            path.lineTo(cx + sz * 0.22, cy - sz * 0.16)
            p.drawPath(path)
        else:
            border = QColor(10, 132, 255) if hover else QColor(255, 255, 255, 60)
            p.setPen(QPen(border, 1.5))
            p.setBrush(QBrush(QColor(255, 255, 255, 18)))
            p.drawRoundedRect(box, self._R, self._R)

        # Label text
        p.setPen(QColor(245, 245, 247))
        p.setFont(self.font())
        text_rect = self.rect().adjusted(sz + 10, 0, 0, 0)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, self.text())
        p.end()

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def sizeHint(self):
        base = super().sizeHint()
        return QSize(base.width(), max(base.height(), self._SZ + 8))


# =========================
# Combo that always opens downward
# =========================
def _dwm_round_popup(popup_window) -> None:
    """Apply Windows 11 DWM small-round corners to a popup window."""
    try:
        import platform
        if platform.system() != "Windows":
            return
        import ctypes
        hwnd = int(popup_window.winId())
        # DWMWA_WINDOW_CORNER_PREFERENCE = 33, DWMWCP_ROUNDSMALL = 3
        pref = ctypes.c_int(3)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref)
        )
    except Exception:
        pass


class _RoundedItemDelegate(QStyledItemDelegate):
    """Item delegate that draws rounded selection/hover backgrounds."""

    _RADIUS = 8

    @staticmethod
    def _accent_colors():
        """Return (sel_bg, hov_bg, sel_text) QColors for the active theme."""
        try:
            import app.styles.themes as styles
            th = styles.current_theme()
            if th == "light":
                return (QColor(59, 130, 246, 38), QColor(59, 130, 246, 18), QColor(59, 130, 246))
        except Exception:
            pass
        # dark default
        return (QColor(10, 132, 255, 60), QColor(10, 132, 255, 28), QColor(10, 132, 255))

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hover    = bool(option.state & QStyle.StateFlag.State_MouseOver)

        sel_bg, hov_bg, sel_text = self._accent_colors()
        r = option.rect.adjusted(3, 2, -3, -2)

        if is_selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(sel_bg)
            painter.drawRoundedRect(r, self._RADIUS, self._RADIUS)
        elif is_hover:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(hov_bg)
            painter.drawRoundedRect(r, self._RADIUS, self._RADIUS)

        # Draw text — strip selection/focus flags so Fusion doesn't overlay its rectangle
        text_option = QStyleOptionViewItem(option)
        text_option.state &= ~(QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_HasFocus)
        if is_selected:
            text_option.palette.setColor(text_option.palette.currentColorGroup(),
                                         text_option.palette.ColorRole.Text, sel_text)
        painter.restore()
        super().paint(painter, text_option, index)


class RoundedPopupCombo(QComboBox):
    """QComboBox that opens below the widget with DWM-rounded popup corners."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Custom delegate draws rounded selection; disabling focus prevents
        # Fusion from drawing an extra rectangular focus frame on top.
        self.view().setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.view().setItemDelegate(_RoundedItemDelegate(self.view()))
        self.view().setMouseTracking(True)

    def showPopup(self):
        super().showPopup()
        # Force popup below the button (Qt aligns selected item with combo by default)
        popup = self.view().window()
        popup.move(self.mapToGlobal(self.rect().bottomLeft()))
        _dwm_round_popup(popup)


class DownwardCombo(QComboBox):
    """QComboBox whose popup always appears below the widget, regardless of selected item."""

    def showPopup(self):
        super().showPopup()
        # After Qt positions the popup (possibly upward), force it below the combo.
        popup = self.view().window()
        below = self.mapToGlobal(self.rect().bottomLeft())
        popup.move(below)
        _dwm_round_popup(popup)
