from __future__ import annotations

from shared.i18n import tr
import app.styles.themes as _styles


def _th() -> dict:
    return _styles._THEMES[_styles._active_theme]

from PyQt6.QtWidgets import (
    QLineEdit, QStyledItemDelegate,
    QStyleOptionViewItem, QStyle, QApplication,
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QDialog, QListWidget,
)
from PyQt6.QtCore import (
    Qt, QRect, QRectF, QSize, QEvent, pyqtSignal, QMimeData, QPoint,
)
from PyQt6.QtGui import (
    QIcon, QPainter, QColor, QFont, QPen, QPainterPath, QMouseEvent, QDrag, QPixmap,
)


# =========================
# iOS-style task delegate
# =========================

# Colour constants (theme-independent accents)
_ACCENT      = QColor(10, 132, 255)
_GREEN       = QColor("#30d158")       # iOS green

# Priority strip colours (left edge indicator)
_PRI_COLORS = {
    1: QColor("#34c759"),   # low  → iOS green
    2: QColor("#ff9f0a"),   # med  → iOS orange
    3: QColor("#ff453a"),   # high → iOS red
}


class TaskItemDelegate(QStyledItemDelegate):
    """Custom iOS-style rendering for task list items."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_query: str = ""

    def set_search_query(self, query: str) -> None:
        self._search_query = query.strip().lower()

    def paint(self, painter: QPainter, option, index):
        # ── draw base (bg highlight + selection), no text/icon ──
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        opt.icon = QIcon()
        opt.features &= ~QStyleOptionViewItem.ViewItemFeature.HasDecoration
        style = opt.widget.style() if opt.widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)

        is_done = (index.data(Qt.ItemDataRole.CheckStateRole) or 0) == 2
        title = index.data(Qt.ItemDataRole.DisplayRole) or ""
        meta = index.data(Qt.ItemDataRole.UserRole + 1) or ""
        category_color = index.data(Qt.ItemDataRole.UserRole + 2)  # category color hex string
        priority = index.data(Qt.ItemDataRole.UserRole + 3) or 0    # 0=none,1=low,2=med,3=high
        is_pinned = bool(index.data(Qt.ItemDataRole.UserRole + 4))  # pin flag

        # Theme-aware colours (computed each paint so theme changes take effect immediately)
        th = _th()
        _text_pri = QColor(th["text"])
        _text_done = QColor(th.get("text_done", th["text_sec"]))
        _text_sec = QColor(th["text_sec"])
        _check_ring = QColor(th["text_sec"])

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = option.rect

        # ── priority left-edge strip ──
        if priority in _PRI_COLORS and not is_done:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(_PRI_COLORS[priority])
            strip = QRectF(rect.x(), rect.y() + 4, 3, rect.height() - 8)
            painter.drawRoundedRect(strip, 1.5, 1.5)

        # ── category color dot (if task has category) ──
        if category_color:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(category_color))
            dot_x = rect.x() + 6
            dot_y = rect.y() + (rect.height() - 6) // 2
            painter.drawEllipse(QRectF(dot_x, dot_y, 6, 6))

        # ── custom round checkbox ──
        ck_size = 22
        ck_x = rect.x() + 14
        ck_y = rect.y() + (rect.height() - ck_size) // 2
        ck_rect = QRectF(ck_x, ck_y, ck_size, ck_size)

        if is_done:
            # Ring + green checkmark (ring uses theme text colour)
            painter.setPen(QPen(_text_pri, 1.8))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(ck_rect)
            # Green checkmark
            painter.setPen(QPen(_GREEN, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            cx, cy = ck_rect.center().x(), ck_rect.center().y()
            path = QPainterPath()
            path.moveTo(cx - 4.5, cy + 0.5)
            path.lineTo(cx - 1, cy + 4)
            path.lineTo(cx + 5.5, cy - 3.5)
            painter.drawPath(path)
        else:
            # Thin grey ring
            painter.setPen(QPen(_check_ring, 1.8))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(ck_rect)

        # ── title (skip if inline editor is open) ──
        is_editing = bool(index.flags() & Qt.ItemFlag.ItemIsEditable)
        if not is_editing:
            text_left = ck_x + ck_size + 12
            # Reserve space for pin icon on right
            pin_space = 18 if is_pinned else 0
            text_right = rect.right() - 90 - pin_space
            title_rect = QRect(text_left, rect.y(), text_right - text_left, rect.height())

            title_color = _text_done if is_done else _text_pri
            f = painter.font()
            f.setWeight(QFont.Weight.Medium)
            if is_done:
                f.setStrikeOut(True)
            painter.setFont(f)

            fm = painter.fontMetrics()
            elided = fm.elidedText(title, Qt.TextElideMode.ElideRight, title_rect.width())

            # ── search highlight ──
            q = self._search_query
            q_in_title = q and q in title.lower()
            if q_in_title and not is_done:
                t_lower = title.lower()
                idx = t_lower.find(q)
                prefix = elided[:idx] if idx < len(elided) else elided
                matched = elided[idx:idx + len(q)] if idx < len(elided) else ""
                suffix = elided[idx + len(q):] if idx + len(q) < len(elided) else ""

                x = title_rect.x()
                y = title_rect.y()
                h = title_rect.height()

                if prefix:
                    pw = fm.horizontalAdvance(prefix)
                    painter.setPen(title_color)
                    painter.drawText(QRect(x, y, pw, h), Qt.AlignmentFlag.AlignVCenter, prefix)
                    x += pw

                if matched:
                    mw = fm.horizontalAdvance(matched)
                    font_h = fm.height()
                    hi_rect = QRectF(x, y + (h - font_h) // 2, mw, font_h)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor(10, 132, 255, 120))
                    painter.drawRoundedRect(hi_rect, 3, 3)
                    painter.setPen(QColor(255, 255, 255))
                    painter.drawText(QRect(x, y, mw, h), Qt.AlignmentFlag.AlignVCenter, matched)
                    x += mw

                if suffix:
                    painter.setPen(title_color)
                    painter.drawText(
                        QRect(x, y, title_rect.right() - x, h),
                        Qt.AlignmentFlag.AlignVCenter, suffix
                    )
            else:
                painter.setPen(title_color)
                painter.drawText(title_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)

            f.setStrikeOut(False)
            painter.setFont(f)

            # ── pin icon ──
            if is_pinned:
                pin_x = text_right + 4
                pin_rect = QRect(pin_x, rect.y(), 14, rect.height())
                pin_font = QFont(painter.font())
                pin_font.setPointSizeF(max(8.0, pin_font.pointSizeF() - 2))
                painter.setFont(pin_font)
                painter.setPen(_ACCENT)
                painter.drawText(pin_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "📌")
                painter.setFont(f)

        # ── right side: subtask badge + meta date ──
        deadline_at = index.data(Qt.ItemDataRole.UserRole + 5) or ""
        subtask_counts = index.data(Qt.ItemDataRole.UserRole + 6)  # (done, total) or None

        f2 = QFont(painter.font())
        f2.setPointSizeF(max(7.5, f2.pointSizeF() - 1.5))
        f2.setWeight(QFont.Weight.Normal)
        f2.setStrikeOut(False)
        painter.setFont(f2)
        fm2 = painter.fontMetrics()

        # Deadline color for the date
        if deadline_at and not is_done:
            from datetime import datetime, timezone, date as _date
            try:
                dl_dt = datetime.fromisoformat(deadline_at)
                if dl_dt.tzinfo is None:
                    dl_dt = dl_dt.replace(tzinfo=timezone.utc)
                today = datetime.now(timezone.utc).date()
                dl_date = dl_dt.date()
                if dl_date < today:
                    date_color = QColor("#ff453a")   # overdue → red
                elif dl_date == today:
                    date_color = QColor("#ff9f0a")   # today → orange
                else:
                    date_color = _text_sec
            except Exception:
                date_color = _text_sec
        else:
            date_color = _text_sec

        # Subtask badge: "(done/total)" just left of the date
        badge_w = 0
        if subtask_counts and not is_done:
            done_c, total_c = subtask_counts
            badge_text = f"{done_c}/{total_c}"
            badge_w = fm2.horizontalAdvance(badge_text) + 6
            badge_rect = QRect(rect.right() - 85 - badge_w, rect.y(), badge_w, rect.height())
            badge_color = QColor("#34c759") if done_c == total_c else QColor("#98989d")
            painter.setPen(badge_color)
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, badge_text)

        meta_rect = QRect(rect.right() - 85, rect.y(), 75, rect.height())
        meta_elided = fm2.elidedText(meta, Qt.TextElideMode.ElideLeft, meta_rect.width())
        painter.setPen(date_color)
        painter.drawText(meta_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, meta_elided)

        painter.restore()

    def _checkbox_rect(self, item_rect: QRect) -> QRectF:
        ck_size = 22
        ck_x = item_rect.x() + 14
        ck_y = item_rect.y() + (item_rect.height() - ck_size) // 2
        return QRectF(ck_x - 4, ck_y - 4, ck_size + 8, ck_size + 8)

    def editorEvent(self, event, model, option, index):
        if not isinstance(event, QMouseEvent):
            return super().editorEvent(event, model, option, index)

        click_types = (
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonDblClick,
        )
        if event.type() in click_types:
            hit = self._checkbox_rect(option.rect)
            if hit.contains(event.position()):
                if event.type() == QEvent.Type.MouseButtonRelease:
                    cur = index.data(Qt.ItemDataRole.CheckStateRole) or 0
                    new_state = (
                        Qt.CheckState.Unchecked
                        if cur == 2
                        else Qt.CheckState.Checked
                    )
                    model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)
                return True
        return super().editorEvent(event, model, option, index)

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            editor.setStyleSheet(f"""
                QLineEdit {{
                    background: transparent;
                    border: none;
                    border-bottom: 1.5px solid rgba(10, 132, 255, 0.6);
                    border-radius: 0px;
                    color: {_th()["text"]};
                    padding: 0px 2px;
                    font-weight: 500;
                }}
            """)
        return editor

    def updateEditorGeometry(self, editor, option, index):
        rect = option.rect
        text_left = rect.x() + 14 + 22 + 12   # checkbox offset + size + gap
        text_right = rect.right() - 90          # space for meta date
        editor.setGeometry(QRect(text_left, rect.y(), text_right - text_left, rect.height()))

    def sizeHint(self, option, index):
        return QSize(option.rect.width() if option.rect.isValid() else 200, 44)


# ============================
# Category widgets
# ============================

class CategoryChip(QWidget):
    """Widget-chip for category: color dot + name + task count."""

    clicked = pyqtSignal()
    rename_requested = pyqtSignal()

    def __init__(self, category, is_all: bool = False, parent=None):
        super().__init__(parent)
        from entities.category.model import Category
        self.category: Category = category
        self.is_all = is_all
        self.is_selected = False

        self.setObjectName("CategoryChip")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setFixedHeight(32)
        self.setMinimumWidth(80)

        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(6)

        # Color dot
        self.color_dot = QLabel()
        self.color_dot.setFixedSize(8, 8)
        self.color_dot.setStyleSheet(f"""
            background: {category.color if not is_all else '#98989d'};
            border-radius: 4px;
        """)
        layout.addWidget(self.color_dot)

        # Category name
        self.label = QLabel(category.name)
        self.label.setStyleSheet(f"color: {_th()['text']}; font-size: 13px; font-weight: 500;")
        layout.addWidget(self.label, 1)

        # Task count
        self.count_label = QLabel(f"({category.task_count})")
        self.count_label.setStyleSheet(f"color: {_th()['text_sec']}; font-size: 11px;")
        layout.addWidget(self.count_label)

        self._update_style()

        # Enable drag&drop only for regular categories (not "All tasks")
        if not is_all:
            self.setAcceptDrops(True)

    def set_selected(self, selected: bool):
        """Set/unset selection state."""
        self.is_selected = selected
        self._update_style()

    def update_count(self, count: int):
        """Update task count display."""
        self.category.task_count = count
        self.count_label.setText(f"({count})")

    def _update_style(self):
        """Update style based on selected state."""
        if self.is_selected:
            self.setStyleSheet("""
                #CategoryChip {
                    background: rgba(10,132,255,0.35);
                    border: 1px solid #0a84ff;
                    border-radius: 16px;
                }
                #CategoryChip:hover {
                    background: rgba(10,132,255,0.45);
                }
            """)
        else:
            th = _th()
            self.setStyleSheet(f"""
                #CategoryChip {{
                    background: {th["glass"]};
                    border: 1px solid {th["glass_border"]};
                    border-radius: 16px;
                }}
                #CategoryChip:hover {{
                    background: {th["glass_hover"]};
                }}
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.is_all:
            self.rename_requested.emit()
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        """Start drag on mouse move with LMB pressed (for category reordering)."""
        if not self.is_all and event.buttons() & Qt.MouseButton.LeftButton:
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(f"category:{self.category.id}")
            drag.setMimeData(mime_data)
            drag.exec(Qt.DropAction.MoveAction)
        super().mouseMoveEvent(event)

    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if mime.hasText() and mime.text().startswith("category:"):
            event.acceptProposedAction()
        elif not self.is_all and (
            mime.hasFormat("application/x-task-id")
            or mime.hasFormat("application/x-task-ids")
        ):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        mime = event.mimeData()

        # Category reorder
        if mime.hasText() and mime.text().startswith("category:"):
            dragged_id = int(mime.text().split(":")[1])
            if dragged_id != self.category.id and not self.is_all:
                parent_bar = self.parent()
                while parent_bar and not isinstance(parent_bar, CategoryBar):
                    parent_bar = parent_bar.parent()
                if parent_bar:
                    parent_bar.category_reordered.emit(dragged_id, self.category.id)
            event.acceptProposedAction()

        # Task drop (single or multi)
        elif not self.is_all:
            if mime.hasFormat("application/x-task-ids"):
                ids = [int(x) for x in bytes(mime.data("application/x-task-ids")).decode().split(",")]
            elif mime.hasFormat("application/x-task-id"):
                ids = [int(bytes(mime.data("application/x-task-id")).decode())]
            else:
                event.ignore()
                return
            parent_bar = self.parent()
            while parent_bar and not isinstance(parent_bar, CategoryBar):
                parent_bar = parent_bar.parent()
            if parent_bar:
                parent_bar.task_dropped.emit(ids, self.category.id)
            event.acceptProposedAction()

        else:
            event.ignore()

    def contextMenuEvent(self, event):
        """Show context menu for category (rename/delete)."""
        if not self.is_all:
            parent_bar = self.parent()
            while parent_bar and not isinstance(parent_bar, CategoryBar):
                parent_bar = parent_bar.parent()
            if parent_bar:
                parent_bar.show_context_menu(self, event.pos())


class HScrollArea(QScrollArea):
    """QScrollArea that scrolls horizontally on mouse wheel."""
    def wheelEvent(self, event):
        delta_x = event.angleDelta().x()
        delta_y = event.angleDelta().y()
        bar = self.horizontalScrollBar()
        if delta_x != 0:
            bar.setValue(bar.value() - delta_x // 2)
        else:
            bar.setValue(bar.value() - delta_y // 2)
        event.accept()


class CategoryBar(QWidget):
    """Horizontal bar with category chips and add button."""

    category_selected = pyqtSignal(int)       # category selected (id or -1 for "All")
    category_rename = pyqtSignal(int)         # rename requested
    category_delete = pyqtSignal(int)         # delete requested
    add_category = pyqtSignal()               # add button clicked
    category_reordered = pyqtSignal(int, int) # (dragged_id, target_id)
    task_dropped = pyqtSignal(list, int)      # (task_ids, category_id)

    def __init__(self, parent=None):
        super().__init__(parent)
        from entities.category.model import Category
        self.chips: dict[int, CategoryChip] = {}
        self.all_chip: CategoryChip | None = None
        self.selected_category_id: int | None = None  # -1 = all, N = category_id

        # Set Apple glass style for the container
        self.setObjectName("CategoryBar")
        self._apply_bar_css()

        # Layout
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(8, 4, 8, 4)
        self.layout.setSpacing(8)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Scrollable container for categories
        self.scroll_area = HScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setMaximumHeight(40)
        self._apply_scroll_css()

        self.scroll_container = QWidget()
        self.scroll_layout = QHBoxLayout(self.scroll_container)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(8)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.scroll_area.setWidget(self.scroll_container)
        self.layout.addWidget(self.scroll_area, 1)

        # Add category button
        self.add_btn = QPushButton("+")
        self.add_btn.setObjectName("CategoryAddBtn")
        self.add_btn.setFixedSize(32, 32)
        self.add_btn.setToolTip(tr("cat.add_tip"))
        self.add_btn.clicked.connect(self.add_category.emit)
        self.layout.addWidget(self.add_btn)

        # Style for add button
        self._apply_add_btn_css()

    def _apply_bar_css(self):
        th = _th()
        theme = _styles._active_theme
        if theme == "light":
            bg = "rgba(255,255,255,0.90)"
            border = "rgba(175,198,225,0.75)"
        elif theme == "glass":
            bg = "qlineargradient(x1:0,y1:0,x2:0.3,y2:1,stop:0 rgba(62,105,198,0.26),stop:1 rgba(16,42,108,0.14))"
            border = "rgba(100,160,255,0.38)"
        else:  # dark
            bg = "rgba(255,255,255,0.09)"
            border = "rgba(255,255,255,0.28)"
        self.setStyleSheet(f"""
            #CategoryBar {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 14px;
                padding: 8px;
            }}
        """)

    def _apply_scroll_css(self):
        _dark = _styles._active_theme == "dark"
        handle = "rgba(255,255,255,0.20)" if _dark else "rgba(0,0,0,0.20)"
        handle_h = "rgba(255,255,255,0.35)" if _dark else "rgba(0,0,0,0.35)"
        self.scroll_area.setStyleSheet(f"""
            HScrollArea {{ background: transparent; border: none; }}
            HScrollArea > QWidget > QWidget {{ background: transparent; }}
            QScrollBar:horizontal {{ height: 4px; background: transparent; margin: 0; }}
            QScrollBar::handle:horizontal {{ background: {handle}; border-radius: 2px; min-width: 20px; }}
            QScrollBar::handle:horizontal:hover {{ background: {handle_h}; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: none; border: none; width: 0;
            }}
        """)

    def _apply_add_btn_css(self):
        th = _th()
        self.add_btn.setStyleSheet(f"""
            QPushButton#CategoryAddBtn {{
                background: {th["glass"]};
                border: 1px solid {th["glass_border"]};
                border-radius: 16px;
                color: #0a84ff;
                font-size: 18px;
                font-weight: 300;
            }}
            QPushButton#CategoryAddBtn:hover {{
                background: {th["glass_hover"]};
            }}
        """)

    def apply_theme(self):
        """Re-apply CSS for current theme; update all existing chips."""
        self._apply_bar_css()
        self._apply_scroll_css()
        self._apply_add_btn_css()
        th = _th()
        for chip in self.chips.values():
            chip.label.setStyleSheet(f"color: {th['text']}; font-size: 13px; font-weight: 500;")
            chip.count_label.setStyleSheet(f"color: {th['text_sec']}; font-size: 11px;")
            chip._update_style()

    def load_categories(self, categories: list, all_tasks_count: int):
        """Load categories into the bar."""
        from entities.category.model import Category
        # Clear existing chips
        self._clear_chips()

        # Create "All tasks" chip
        all_cat = Category(
            id=-1,
            name=tr("cat.all_tasks"),
            color="#98989d",
            sort_order=-1,
            created_at="",
            task_count=all_tasks_count
        )
        self.all_chip = CategoryChip(all_cat, is_all=True)
        self.all_chip.clicked.connect(lambda: self._on_chip_clicked(-1))
        self.scroll_layout.addWidget(self.all_chip)
        self.chips[-1] = self.all_chip

        # Create chips for categories
        for cat in categories:
            chip = CategoryChip(cat)
            chip.clicked.connect(lambda cid=cat.id: self._on_chip_clicked(cid))
            chip.rename_requested.connect(lambda cid=cat.id: self.category_rename.emit(cid))
            self.scroll_layout.addWidget(chip)
            self.chips[cat.id] = chip

        # Select "All tasks" by default
        self.select_category(-1)

    def _clear_chips(self):
        """Clear all chips."""
        for chip in self.chips.values():
            chip.deleteLater()
        self.chips.clear()
        self.all_chip = None

    def _on_chip_clicked(self, category_id: int):
        """Handle chip click."""
        self.select_category(category_id)
        self.category_selected.emit(category_id)

    def select_category(self, category_id: int):
        """Select category programmatically."""
        self.selected_category_id = category_id
        for cid, chip in self.chips.items():
            chip.set_selected(cid == category_id)

    def update_count(self, category_id: int, count: int):
        """Update task count for a category."""
        if category_id in self.chips:
            self.chips[category_id].update_count(count)

    def update_counts(self, counts: dict[int, int]):
        """Update counts for all categories. counts = {category_id: count, -1: all_count}"""
        for cid, count in counts.items():
            self.update_count(cid, count)

    def show_context_menu(self, chip: CategoryChip, pos):
        """Show context menu for category."""
        if chip.is_all:
            return  # No menu for "All tasks"

        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)

        rename_action = menu.addAction(tr("cat.rename"))
        delete_action = menu.addAction(tr("cat.delete"))

        action = menu.exec(chip.mapToGlobal(pos))

        if action == rename_action:
            self.category_rename.emit(chip.category.id)
        elif action == delete_action:
            self.category_delete.emit(chip.category.id)


class CategoryEditDialog(QDialog):
    """Dialog for creating/editing category."""

    def __init__(self, category=None, parent=None):
        super().__init__(parent)
        from entities.category.model import Category
        self.category: Category | None = category
        self.setWindowTitle(tr("catdlg.edit_title") if category else tr("catdlg.new_title"))
        self.setModal(True)
        self.setFixedSize(340, 220)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Name label
        name_label = QLabel(tr("catdlg.name"))
        name_label.setStyleSheet("color: #f5f5f7; font-size: 12px;")
        layout.addWidget(name_label)

        # Name input
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(tr("catdlg.name_ph"))
        if category:
            self.name_input.setText(category.name)
        layout.addWidget(self.name_input)

        # Color label
        color_label = QLabel(tr("catdlg.color"))
        color_label.setStyleSheet("color: #f5f5f7; font-size: 12px;")
        layout.addWidget(color_label)

        # Color buttons
        self.color_buttons_layout = QHBoxLayout()
        self.color_buttons_layout.setSpacing(8)

        self.colors = [
            "#0a84ff",  # blue (accent)
            "#30d158",  # green
            "#ff9f0a",  # orange
            "#bf5af2",  # purple
            "#ff453a",  # red
            "#64d2ff",  # cyan
            "#ffd60a",  # yellow
            "#ff375f",  # pink
        ]

        self.selected_color = category.color if category else self.colors[0]
        self.color_buttons = []

        for color in self.colors:
            btn = QPushButton()
            btn.setFixedSize(32, 32)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {color};
                    border: 2px solid {'#f5f5f7' if color == self.selected_color else 'transparent'};
                    border-radius: 16px;
                }}
                QPushButton:hover {{
                    border: 2px solid #98989d;
                }}
            """)
            btn.clicked.connect(lambda checked, c=color: self._select_color(c))
            self.color_buttons_layout.addWidget(btn)
            self.color_buttons.append(btn)

        layout.addLayout(self.color_buttons_layout)

        # Buttons
        buttons = QHBoxLayout()
        buttons.addStretch(1)

        cancel_btn = QPushButton(tr("catdlg.cancel"))
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        save_btn = QPushButton(tr("catdlg.save") if category else tr("catdlg.create"))
        save_btn.setObjectName("AccentBtn")
        save_btn.clicked.connect(self.accept)
        buttons.addWidget(save_btn)

        layout.addLayout(buttons)

        # Styles
        self.setStyleSheet("""
            QDialog {
                background: #1c1c1e;
                color: #f5f5f7;
            }
            QLineEdit {
                background: rgba(255,255,255,0.07);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 8px;
                padding: 8px 12px;
                color: #f5f5f7;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #0a84ff;
            }
            QPushButton {
                background: rgba(255,255,255,0.07);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 8px;
                padding: 6px 16px;
                color: #f5f5f7;
                font-size: 13px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.12);
            }
            QPushButton#AccentBtn {
                background: #0a84ff;
                border: none;
                color: #ffffff;
            }
            QPushButton#AccentBtn:hover {
                background: #409cff;
            }
        """)

    def _select_color(self, color: str):
        """Select a color."""
        self.selected_color = color
        # Update button borders
        for i, btn in enumerate(self.color_buttons):
            c = self.colors[i]
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {c};
                    border: 2px solid {'#f5f5f7' if c == color else 'transparent'};
                    border-radius: 16px;
                }}
                QPushButton:hover {{
                    border: 2px solid #98989d;
                }}
            """)

    def get_data(self) -> tuple[str, str]:
        """Return (name, color)."""
        return self.name_input.text().strip(), self.selected_color


class TaskListWidget(QListWidget):
    """Custom QListWidget with drag support for tasks."""

    reordered = pyqtSignal(list)   # emits list[int] of task_ids in new order

    def startDrag(self, supportedActions):
        """Start drag for selected tasks — single or batch."""
        selected = self.selectedItems()
        ids = [item.data(Qt.ItemDataRole.UserRole) for item in selected if item]
        if not ids:
            return
        mime = QMimeData()
        if len(ids) == 1:
            mime.setData("application/x-task-id", str(ids[0]).encode())
        else:
            mime.setData("application/x-task-ids", ",".join(str(i) for i in ids).encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        if len(ids) > 1:
            px = self._make_badge_pixmap(len(ids))
            drag.setPixmap(px)
            drag.setHotSpot(QPoint(px.width() // 2, px.height() // 2))
        drag.exec(Qt.DropAction.MoveAction)

    def _make_badge_pixmap(self, n: int) -> QPixmap:
        """Blue rounded badge showing ×N task count."""
        px = QPixmap(52, 28)
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(10, 132, 255))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, 52, 28, 8, 8)
        p.setPen(QColor(255, 255, 255))
        f = QFont()
        f.setPointSize(12)
        f.setBold(True)
        p.setFont(f)
        p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, f"×{n}")
        p.end()
        return px

    def dropEvent(self, event):
        """Handle internal reorder drops; ignore external drops."""
        if event.source() is self:
            super().dropEvent(event)
            ids = []
            for i in range(self.count()):
                it = self.item(i)
                if it is not None:
                    ids.append(int(it.data(Qt.ItemDataRole.UserRole)))
            self.reordered.emit(ids)
            event.accept()
        else:
            event.ignore()
