"""Command Palette — Ctrl+K floating search popup with favorites."""
from __future__ import annotations

import json

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QStyledItemDelegate, QStyle, QStyleOptionViewItem,
)
from PyQt6.QtCore import Qt, QObject, QEvent, QSettings, QSize, QRectF, QPoint
from PyQt6.QtGui import (
    QKeyEvent, QPainter, QColor, QFont, QPixmap,
    QPainterPath, QPen, QLinearGradient, QBrush, QGuiApplication,
)

from shared.i18n import tr


# ── Item data roles ──────────────────────────────────────────────────────────

_CMD_ROLE = Qt.ItemDataRole.UserRole        # dict with label/action/kw
_FAV_ROLE = Qt.ItemDataRole.UserRole + 1   # bool — is favorite
_SEP_ROLE = Qt.ItemDataRole.UserRole + 2   # bool — is separator row


# ── Settings key ─────────────────────────────────────────────────────────────

_SETTINGS_KEY = "command_palette/favorites"


def _load_favorites() -> set[str]:
    raw = QSettings("todo_app", "todo_mvp").value(_SETTINGS_KEY, "[]")
    try:
        return set(json.loads(raw))
    except Exception:
        return set()


def _save_favorites(favs: set[str]) -> None:
    QSettings("todo_app", "todo_mvp").setValue(_SETTINGS_KEY, json.dumps(sorted(favs)))


# ── Custom delegate: label + star glyph ──────────────────────────────────────

class _PaletteDelegate(QStyledItemDelegate):
    """Draws each command row with a star toggle on the right edge."""

    STAR_W = 32  # px reserved for star column

    def _theme_colors(self):
        try:
            import app.styles.themes as styles
            light = styles.current_theme() == "light"
        except Exception:
            light = False
        if light:
            return {
                "sel_bg":    QColor(59, 130, 246, 40),
                "hov_bg":    QColor(59, 130, 246, 18),
                "sel_text":  QColor("#0F172A"),
                "norm_text": QColor("#0F172A"),
                "sec_text":  QColor("#94A3B8"),
                "star_on":   QColor("#F59E0B"),   # amber
                "star_off":  QColor("#CBD5E1"),
            }
        return {
            "sel_bg":    QColor(10, 132, 255, 55),
            "hov_bg":    QColor(10, 132, 255, 25),
            "sel_text":  QColor("#f5f5f7"),
            "norm_text": QColor("#f5f5f7"),
            "sec_text":  QColor("#636366"),
            "star_on":   QColor("#FBBF24"),
            "star_off":  QColor("#48484a"),
        }

    def sizeHint(self, option, index) -> QSize:
        if index.data(_SEP_ROLE):
            return QSize(option.rect.width(), 28)
        return QSize(option.rect.width(), 38)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self._theme_colors()

        # ── Separator row ────────────────────────────────────────────────────
        if index.data(_SEP_ROLE):
            label = index.data(Qt.ItemDataRole.DisplayRole) or ""
            r = option.rect
            painter.setPen(c["sec_text"])
            font = QFont(option.font)
            font.setPointSizeF(font.pointSizeF() * 0.82)
            font.setWeight(QFont.Weight.Medium)
            painter.setFont(font)
            painter.drawText(
                r.adjusted(14, 0, 0, 0),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                label,
            )
            painter.restore()
            return

        # ── Normal command row ───────────────────────────────────────────────
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hover    = bool(option.state & QStyle.StateFlag.State_MouseOver)
        is_fav      = bool(index.data(_FAV_ROLE))

        r = option.rect.adjusted(4, 2, -4, -2)
        if is_selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(c["sel_bg"])
            painter.drawRoundedRect(r, 7, 7)
        elif is_hover:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(c["hov_bg"])
            painter.drawRoundedRect(r, 7, 7)

        # Label text
        label = index.data(Qt.ItemDataRole.DisplayRole) or ""
        text_rect = option.rect.adjusted(14, 0, -self.STAR_W - 4, 0)
        painter.setPen(c["sel_text"] if is_selected else c["norm_text"])
        painter.setFont(option.font)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            label,
        )

        # Star glyph
        star_rect = option.rect.adjusted(
            option.rect.width() - self.STAR_W, 0, 0, 0
        )
        star_color = c["star_on"] if is_fav else c["star_off"]
        if is_hover and not is_fav:
            star_color = QColor(
                star_color.red(), star_color.green(), star_color.blue(), 140
            )
        painter.setPen(star_color)
        star_font = QFont(option.font)
        star_font.setPointSizeF(option.font.pointSizeF() * 1.1)
        painter.setFont(star_font)
        painter.drawText(
            star_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter,
            "★" if is_fav else "☆",
        )

        painter.restore()


# ── Star click event filter ───────────────────────────────────────────────────

class _StarClickFilter(QObject):
    """Intercepts mouse clicks in the star column of the palette list."""

    def __init__(self, palette: "CommandPalette"):
        super().__init__(palette)
        self._pal = palette

    def eventFilter(self, obj, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseButtonRelease:
            pos = event.position().toPoint()
            item = self._pal._list.itemAt(pos)
            if item and not item.isHidden() and not item.data(_SEP_ROLE):
                item_rect = self._pal._list.visualItemRect(item)
                star_x = item_rect.right() - _PaletteDelegate.STAR_W
                if pos.x() >= star_x:
                    self._pal._toggle_fav(item)
                    return True  # consume — don't execute the command
        return super().eventFilter(obj, event)


# ── CommandPalette ────────────────────────────────────────────────────────────

class CommandPalette(QDialog):
    """Frameless popup with searchable list of app commands + favorites."""

    _W = 500
    _H = 420

    def __init__(self, main_window):
        super().__init__(
            main_window,
            Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint,
        )
        self.mw = main_window
        # WA_TranslucentBackground: lets the rounded corners from CSS show through
        # (the body of the dialog will use an opaque color — no transparency)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self._W, self._H)
        self.setObjectName("CommandPalette")

        self._favorites: set[str] = _load_favorites()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._search = QLineEdit()
        self._search.setObjectName("PaletteSearch")
        self._search.setPlaceholderText(tr("cmd.palette_placeholder"))
        self._search.setFixedHeight(50)
        self._search.textChanged.connect(self._filter)
        layout.addWidget(self._search)

        self._list = QListWidget()
        self._list.setObjectName("PaletteList")
        self._list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._list.setMouseTracking(True)
        self._list.setItemDelegate(_PaletteDelegate(self._list))
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list)

        # Install star-click filter on the viewport
        self._list.viewport().installEventFilter(_StarClickFilter(self))
        self._list.viewport().setMouseTracking(True)

        self._commands = self._build_commands()
        self._populate()
        self._search.setFocus()
        self._bg_pixmap: QPixmap | None = None

    # ── glassmorphism background ──────────────────────────────────────────────

    def showEvent(self, event):
        # Capture what's on screen at our position BEFORE we are painted
        self._capture_background()
        super().showEvent(event)

    def _capture_background(self):
        screen = self.screen() or QGuiApplication.primaryScreen()
        if not screen:
            return
        pos = self.mapToGlobal(QPoint(0, 0))
        raw = screen.grabWindow(0, pos.x(), pos.y(), self.width(), self.height())
        self._bg_pixmap = self._blur_pixmap(raw)

    @staticmethod
    def _blur_pixmap(pm: QPixmap) -> QPixmap:
        """Fast blur via 8× scale-down → scale-up (smooth transform)."""
        img = pm.toImage()
        w, h = max(1, img.width()), max(1, img.height())
        small = img.scaled(
            max(1, w // 8), max(1, h // 8),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        blurred = small.scaled(
            w, h,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        result = QPixmap.fromImage(blurred)
        result.setDevicePixelRatio(pm.devicePixelRatio())
        return result

    def paintEvent(self, _event):
        try:
            import app.styles.themes as styles
            light = styles.current_theme() == "light"
        except Exception:
            light = False

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        radius = 16.0
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)

        painter.setClipPath(path)

        # 1 — blurred background (what was on screen behind us)
        if self._bg_pixmap:
            painter.drawPixmap(0, 0, self._bg_pixmap)

        # 2 — glass tint overlay
        if light:
            painter.fillRect(self.rect(), QColor(235, 242, 255, 200))
        else:
            painter.fillRect(self.rect(), QColor(14, 14, 20, 210))

        # 3 — top-edge sheen (glass highlight)
        sheen = QLinearGradient(0, 0, 0, 56)
        sheen.setColorAt(0.0, QColor(255, 255, 255, 28 if not light else 55))
        sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(self.rect(), QBrush(sheen))

        # 4 — border
        painter.setClipping(False)
        border = QColor(59, 130, 246, 60) if light else QColor(255, 255, 255, 38)
        painter.setPen(QPen(border, 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)

    # ── command registry ──────────────────────────────────────────────────────

    def _build_commands(self) -> list[dict]:
        mw = self.mw
        return [
            {"label": tr("cmd.new_task"),      "action": mw.create_new_task,           "kw": "new create add задача создать"},
            {"label": tr("cmd.toggle_done"),   "action": mw.toggle_done_current,       "kw": "done complete check выполнить отметить"},
            {"label": tr("cmd.duplicate"),     "action": mw.duplicate_task,            "kw": "copy dup дубликат копировать"},
            {"label": tr("cmd.delete"),        "action": mw.on_delete,                 "kw": "delete remove удалить"},
            {"label": tr("cmd.analytics"),     "action": mw.toggle_analytics,          "kw": "stats chart аналитика графики"},
            {"label": tr("cmd.calendar"),      "action": mw.toggle_calendar,           "kw": "calendar day календарь дни"},
            {"label": tr("cmd.settings"),      "action": mw.toggle_settings,           "kw": "settings prefs настройки параметры"},
            {"label": tr("cmd.filter_all"),    "action": lambda: mw.set_filter(mw.FILTER_ALL),          "kw": "all все фильтр filter"},
            {"label": tr("cmd.filter_active"), "action": lambda: mw.set_filter(mw.FILTER_ACTIVE),       "kw": "active активные"},
            {"label": tr("cmd.filter_done"),   "action": lambda: mw.set_filter(mw.FILTER_DONE),         "kw": "done выполненные"},
            {"label": tr("cmd.filter_today"),  "action": lambda: mw.set_filter(mw.FILTER_TODAY),        "kw": "today сегодня"},
            {"label": tr("cmd.sort_new"),      "action": lambda: mw._set_sort(mw.SORT_NEW),             "kw": "sort new сортировка новые"},
            {"label": tr("cmd.sort_old"),      "action": lambda: mw._set_sort(mw.SORT_OLD),             "kw": "sort old старые"},
            {"label": tr("cmd.sort_prio"),     "action": lambda: mw._set_sort(mw.SORT_UNDONE_FIRST),    "kw": "sort priority приоритет невыполненные"},
            {"label": tr("cmd.sort_alpha"),    "action": lambda: mw._set_sort(mw.SORT_ALPHA),           "kw": "sort alpha алфавит"},
            {"label": tr("cmd.sort_manual"),   "action": lambda: mw._set_sort(mw.SORT_MANUAL),          "kw": "sort manual вручную"},
            {"label": tr("cmd.lang_ru"),       "action": lambda: mw.on_set_language("ru"),              "kw": "lang language русский russian"},
            {"label": tr("cmd.lang_en"),       "action": lambda: mw.on_set_language("en"),              "kw": "lang language english английский"},
            {"label": tr("cmd.select_all"),    "action": mw.select_all_tasks,                           "kw": "select all выбрать все bulk"},
            {"label": tr("cmd.bulk_done"),     "action": lambda: mw.bulk_mark_done(True),               "kw": "bulk done выполнить выбранные"},
            {"label": tr("cmd.bulk_delete"),   "action": mw.bulk_delete,                                "kw": "bulk delete удалить выбранные"},
            {"label": tr("cmd.export_json"),   "action": lambda: mw.export_tasks("json"),               "kw": "export json экспорт"},
            {"label": tr("cmd.export_csv"),    "action": lambda: mw.export_tasks("csv"),                "kw": "export csv экспорт"},
            {"label": tr("cmd.import"),        "action": lambda: mw.import_tasks("json"),               "kw": "import импорт"},
            {"label": tr("cmd.zoom_in"),       "action": lambda: mw.change_zoom(+1),                    "kw": "zoom in bigger масштаб увеличить"},
            {"label": tr("cmd.zoom_out"),      "action": lambda: mw.change_zoom(-1),                    "kw": "zoom out smaller уменьшить"},
        ]

    # ── list population ───────────────────────────────────────────────────────

    def _make_sep(self, label: str) -> QListWidgetItem:
        item = QListWidgetItem(label)
        item.setData(_SEP_ROLE, True)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        return item

    def _make_cmd_item(self, cmd: dict) -> QListWidgetItem:
        item = QListWidgetItem(cmd["label"])
        item.setData(_CMD_ROLE, cmd)
        item.setData(_FAV_ROLE, cmd["label"] in self._favorites)
        item.setData(_SEP_ROLE, False)
        return item

    def _populate(self):
        self._list.clear()
        favs = [c for c in self._commands if c["label"] in self._favorites]
        rest = [c for c in self._commands if c["label"] not in self._favorites]

        if favs:
            self._list.addItem(self._make_sep(tr("cmd.section_favorites")))
            for cmd in favs:
                self._list.addItem(self._make_cmd_item(cmd))
            self._list.addItem(self._make_sep(tr("cmd.section_all")))

        for cmd in rest:
            self._list.addItem(self._make_cmd_item(cmd))

        self._select_first_command()

    # ── filtering ─────────────────────────────────────────────────────────────

    def _filter(self, text: str):
        q = text.lower().strip()
        first_visible: int | None = None
        prev_was_sep = False

        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(_SEP_ROLE):
                # Temporarily hide separators; we'll decide after scanning all rows
                item.setHidden(bool(q))  # hide separators when searching
                continue
            cmd = item.data(_CMD_ROLE)
            if cmd is None:
                continue
            visible = (
                not q
                or q in cmd["label"].lower()
                or any(q in k for k in cmd["kw"].split())
            )
            item.setHidden(not visible)
            if visible and first_visible is None:
                first_visible = i

        if first_visible is not None:
            self._list.setCurrentRow(first_visible)
        else:
            self._list.clearSelection()

    # ── favorites ─────────────────────────────────────────────────────────────

    def _toggle_fav(self, item: QListWidgetItem):
        cmd = item.data(_CMD_ROLE)
        if cmd is None:
            return
        label = cmd["label"]
        if label in self._favorites:
            self._favorites.discard(label)
        else:
            self._favorites.add(label)
        _save_favorites(self._favorites)
        # Rebuild list maintaining search text
        query = self._search.text()
        self._populate()
        if query:
            self._filter(query)

    # ── navigation ────────────────────────────────────────────────────────────

    def _select_first_command(self):
        for i in range(self._list.count()):
            item = self._list.item(i)
            if not item.isHidden() and not item.data(_SEP_ROLE):
                self._list.setCurrentRow(i)
                return

    def _move_selection(self, delta: int):
        current = self._list.currentRow()
        count = self._list.count()
        new = current + delta
        while 0 <= new < count:
            item = self._list.item(new)
            if not item.isHidden() and not item.data(_SEP_ROLE):
                self._list.setCurrentRow(new)
                return
            new += delta

    # ── execution ─────────────────────────────────────────────────────────────

    def _execute_item(self, item: QListWidgetItem):
        if item and not item.isHidden() and not item.data(_SEP_ROLE):
            cmd = item.data(_CMD_ROLE)
            if cmd:
                self.accept()
                cmd["action"]()

    def _on_item_clicked(self, item: QListWidgetItem):
        """Only execute on click if not on the star area (handled by filter)."""
        self._execute_item(item)

    def _execute_current(self):
        self._execute_item(self._list.currentItem())

    # ── key handling ──────────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.reject()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._execute_current()
        elif key == Qt.Key.Key_Up:
            self._move_selection(-1)
        elif key == Qt.Key.Key_Down:
            self._move_selection(1)
        else:
            super().keyPressEvent(event)
