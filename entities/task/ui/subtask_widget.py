from __future__ import annotations

from PyQt6.QtWidgets import (
    QStyledItemDelegate, QStyle, QApplication,
    QWidget, QListWidget, QFrame, QLineEdit, QAbstractItemView, QSizePolicy,
    QStyleOptionViewItem,
)
from PyQt6.QtCore import (
    Qt, QRect, QSize, QEvent, pyqtSignal, QPoint,
)
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QPen,
)


# =========================
# Subtask delegate (native rendering so InternalMove drag-and-drop works)
# =========================
class SubtaskDelegate(QStyledItemDelegate):
    """Draws subtask rows natively: grip | circle checkbox | title | × delete.

    Using child widgets via setItemWidget() prevents InternalMove drag from
    starting because child widgets swallow all mouse events.  This delegate
    renders everything with QPainter and handles clicks in editorEvent().
    """

    toggle_requested = pyqtSignal(int)       # subtask_id
    delete_requested = pyqtSignal(int)       # subtask_id
    rename_requested = pyqtSignal(int, str)  # subtask_id, new_title

    _ROW_H   = 36
    _GRIP_W  = 20
    _CB_PAD  = 6    # gap between grip right edge and circle left
    _CB_R    = 7    # circle checkbox radius
    _TXT_PAD = 6    # gap between circle right and text
    _DEL_W   = 26   # width of the × area on the right

    def sizeHint(self, option, index):
        return QSize(option.rect.width() if option.rect.width() > 0 else 200, self._ROW_H)

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        title   = index.data(Qt.ItemDataRole.DisplayRole) or ""
        is_done = bool(index.data(Qt.ItemDataRole.UserRole + 1))
        r       = option.rect

        # Subtle hover background; suppress any selection highlight
        if option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(r, QColor(255, 255, 255, 10))

        # ── Drag grip ────────────────────────────────────────────
        painter.setPen(QColor(72, 72, 74))
        painter.setFont(QFont("Segoe UI", 11))
        painter.drawText(
            QRect(r.x(), r.y(), self._GRIP_W, r.height()),
            Qt.AlignmentFlag.AlignCenter, "⠿"
        )

        # ── Circle checkbox ──────────────────────────────────────
        cx = r.x() + self._GRIP_W + self._CB_PAD
        cy = r.y() + r.height() // 2
        cb = QRect(cx, cy - self._CB_R, self._CB_R * 2, self._CB_R * 2)
        painter.setPen(Qt.PenStyle.NoPen)
        if is_done:
            painter.setBrush(QColor(48, 209, 88))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(99, 99, 102), 1.5))
        painter.drawEllipse(cb)

        # ── Title text ───────────────────────────────────────────
        tx = r.x() + self._GRIP_W + self._CB_PAD + self._CB_R * 2 + self._TXT_PAD
        tw = r.width() - (tx - r.x()) - self._DEL_W - 4
        f_title = QFont("Segoe UI", 12)
        if is_done:
            f_title.setStrikeOut(True)
        painter.setFont(f_title)
        painter.setPen(QColor(99, 99, 102) if is_done else QColor(245, 245, 247))
        painter.drawText(
            QRect(tx, r.y(), tw, r.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            title,
        )

        # ── Delete (×) ───────────────────────────────────────────
        painter.setPen(QColor(99, 99, 102))
        painter.setFont(QFont("Segoe UI", 14))
        painter.drawText(
            QRect(r.right() - self._DEL_W, r.y(), self._DEL_W, r.height()),
            Qt.AlignmentFlag.AlignCenter, "×"
        )

        painter.restore()

    # ── Hit-test helpers ─────────────────────────────────────────

    def _cb_rect(self, ir: QRect) -> QRect:
        cx = ir.x() + self._GRIP_W + self._CB_PAD
        cy = ir.y() + ir.height() // 2
        m = 5
        return QRect(cx - m, cy - self._CB_R - m,
                     self._CB_R * 2 + m * 2, self._CB_R * 2 + m * 2)

    def _del_rect(self, ir: QRect) -> QRect:
        return QRect(ir.right() - self._DEL_W, ir.y(), self._DEL_W, ir.height())

    # ── Mouse interaction ────────────────────────────────────────

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.Type.MouseButtonRelease:
            try:
                pos = event.position().toPoint()
            except AttributeError:
                return False
            sub_id = index.data(Qt.ItemDataRole.UserRole)
            if sub_id is None:
                return False
            if self._cb_rect(option.rect).contains(pos):
                self.toggle_requested.emit(int(sub_id))
                return True
            if self._del_rect(option.rect).contains(pos):
                self.delete_requested.emit(int(sub_id))
                return True
        return super().editorEvent(event, model, option, index)

    # ── Inline rename editor ─────────────────────────────────────

    def createEditor(self, parent, option, index):
        ed = QLineEdit(parent)
        ed.setStyleSheet("""
            QLineEdit {
                background: rgba(255,255,255,0.08);
                border: 1px solid #0a84ff;
                border-radius: 6px;
                color: #f5f5f7;
                font-size: 12px;
                padding: 1px 6px;
            }
        """)
        return ed

    def setEditorData(self, editor, index):
        editor.setText(index.data(Qt.ItemDataRole.DisplayRole) or "")
        editor.selectAll()

    def setModelData(self, editor, model, index):
        text = editor.text().strip()
        if text:
            model.setData(index, text, Qt.ItemDataRole.DisplayRole)
            sub_id = index.data(Qt.ItemDataRole.UserRole)
            if sub_id is not None:
                self.rename_requested.emit(int(sub_id), text)

    def updateEditorGeometry(self, editor, option, index):
        r = option.rect
        x = r.x() + self._GRIP_W + self._CB_PAD + self._CB_R * 2 + self._TXT_PAD
        w = max(r.width() - (x - r.x()) - self._DEL_W - 4, 50)
        editor.setGeometry(QRect(x, r.y() + 2, w, r.height() - 4))


# =========================
# Drop-line overlay (blue indicator shown during subtask drag)
# =========================
class _SubtaskDropLine(QWidget):
    """Transparent overlay painted on top of the list viewport to show
    a blue line indicating where the dragged item will land."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._y: int = -1
        self.hide()

    def set_y(self, y: int) -> None:
        self._y = y
        self.show()
        self.update()

    def hide_line(self) -> None:
        self._y = -1
        self.hide()

    def paintEvent(self, _event) -> None:
        if self._y < 0:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = 4
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(10, 132, 255))
        p.drawEllipse(QRect(0, self._y - r, r * 2, r * 2))
        p.drawEllipse(QRect(self.width() - r * 2, self._y - r, r * 2, r * 2))
        p.setPen(QPen(QColor(10, 132, 255), 2))
        p.drawLine(r * 2, self._y, self.width() - r * 2, self._y)


# =========================
# Subtask list with manual drag-and-drop reorder
# =========================
class SubtaskListWidget(QListWidget):
    """QListWidget with fully manual drag-and-drop reordering.

    Qt's built-in InternalMove interacts badly with custom delegates on
    Windows/PyQt6, so we implement drag entirely via mouse event overrides.
    The ``reordered`` signal is emitted with the new ID order after a drop.
    """

    reordered = pyqtSignal(list)  # list[int] of subtask IDs in new order

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SubtaskListWidget")
        # Disable Qt's own drag machinery — we handle everything manually.
        self.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSpacing(2)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setStyleSheet("""
            QListWidget { background: transparent; border: none; outline: none; }
            QListWidget::item { background: transparent; border: none; }
            QListWidget::item:selected { background: transparent; border: none; }
            QScrollBar:vertical { width: 4px; background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255,255,255,0.20);
                border-radius: 2px; min-height: 20px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        self._delegate = SubtaskDelegate()
        self.setItemDelegate(self._delegate)

        # Drop indicator overlay (lives on the viewport so it floats above items)
        self._drop_line = _SubtaskDropLine(self.viewport())
        self._drop_line.hide()

        # Drag state
        self._drag_row: int = -1       # row being dragged (-1 = none)
        self._drop_row: int = -1       # target insert-before row (-1 = none)
        self._press_pos: "QPoint | None" = None
        self._is_dragging: bool = False

    @property
    def delegate(self) -> SubtaskDelegate:
        return self._delegate

    # ── Geometry ──────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._drop_line.setGeometry(0, 0,
                                    self.viewport().width(),
                                    self.viewport().height())

    # ── Mouse events (all overridden to avoid Qt drag machinery) ──────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            self._press_pos = pos
            item = self.itemAt(pos)
            self._drag_row = self.row(item) if item is not None else -1
        event.accept()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()

        if event.buttons() & Qt.MouseButton.LeftButton:
            if self._press_pos is not None and self._drag_row >= 0:
                dist = (pos - self._press_pos).manhattanLength()
                if dist >= QApplication.startDragDistance():
                    self._is_dragging = True
            if self._is_dragging:
                self._drop_row = self._calc_drop_row(pos)
                self._refresh_drop_line()

        # Cursor: show resize cursor over the grip zone to hint at draggability
        item = self.itemAt(pos)
        if item is not None:
            ir = self.visualItemRect(item)
            if pos.x() <= ir.x() + SubtaskDelegate._GRIP_W + 4:
                self.viewport().setCursor(Qt.CursorShape.SizeVerCursor)
            else:
                self.viewport().unsetCursor()
        else:
            self.viewport().unsetCursor()

        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_dragging and self._drag_row >= 0:
                self._finish_drag()
            elif not self._is_dragging:
                # Plain click — forward to delegate for checkbox / delete
                pos = event.position().toPoint()
                item = self.itemAt(pos)
                if item is not None:
                    idx = self.indexFromItem(item)
                    opt = QStyleOptionViewItem()
                    opt.initFrom(self)
                    opt.rect = self.visualItemRect(item)
                    opt.widget = self
                    self._delegate.editorEvent(event, self.model(), opt, idx)

            # Reset state regardless
            self._drag_row = -1
            self._drop_row = -1
            self._press_pos = None
            self._is_dragging = False
            self._drop_line.hide_line()
        event.accept()

    def mouseDoubleClickEvent(self, event):
        """Double-click on the title area opens the inline rename editor."""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            item = self.itemAt(pos)
            if item is not None:
                idx = self.indexFromItem(item)
                d = self._delegate
                ir = self.visualItemRect(item)
                title_start = ir.x() + d._GRIP_W + d._CB_PAD + d._CB_R * 2 + d._TXT_PAD
                title_end = ir.right() - d._DEL_W
                if title_start < pos.x() < title_end:
                    self.edit(idx)
        event.accept()

    # ── Drag helpers ──────────────────────────────────────────────────

    def _calc_drop_row(self, pos: "QPoint") -> int:
        """Return the row index *before* which the item should be inserted."""
        for i in range(self.count()):
            rect = self.visualItemRect(self.item(i))
            if pos.y() < rect.top() + rect.height() // 2:
                return i
        return self.count()

    def _refresh_drop_line(self) -> None:
        vp_w = self.viewport().width()
        vp_h = self.viewport().height()
        self._drop_line.setGeometry(0, 0, vp_w, vp_h)
        n = self.count()
        row = self._drop_row
        if n == 0:
            y = 0
        elif row < n:
            y = self.visualItemRect(self.item(row)).top()
        else:
            y = self.visualItemRect(self.item(n - 1)).bottom()
        self._drop_line.set_y(y)

    def _finish_drag(self) -> None:
        """Move the dragged item to the drop position and emit reordered."""
        src = self._drag_row
        dst = self._drop_row
        if src < 0 or dst < 0:
            return
        # When inserting after removal, adjust target index
        final = dst if dst <= src else dst - 1
        if final == src:
            return  # same position — nothing to do
        item = self.takeItem(src)
        if item is None:
            return
        final = max(0, min(final, self.count()))
        self.insertItem(final, item)
        # Collect new ID order and notify
        ids = [
            int(self.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(self.count())
            if self.item(i) is not None
            and self.item(i).data(Qt.ItemDataRole.UserRole) is not None
        ]
        if ids:
            self.reordered.emit(ids)
