"""MainWindow — shell that composes UI, connects signals, and inherits all domain mixins."""
from __future__ import annotations

from pathlib import Path
from shared.config.paths import IMAGES_DIR

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem,
    QLabel, QMessageBox, QSplitter, QFrame,
    QCheckBox, QStackedWidget, QLineEdit, QComboBox,
    QApplication, QSizePolicy, QDialog,
    QSystemTrayIcon, QMenu, QScrollArea, QSpinBox, QToolButton, QProgressBar, QSlider,
)
from PyQt6.QtCore import Qt, QTimer, QSettings, QSize, QPoint
from PyQt6.QtGui import QShortcut, QKeySequence, QFont, QPixmap, QIcon

from entities import Task, Category
from entities.task.service import TaskService
from entities.category.service import CategoryService
from entities.analytics.service import AnalyticsService
from entities.finance.service import FinanceService
from shared.i18n import tr, set_language, current_language
from shared.ui.widgets import FocusSaveLineEdit, FocusSaveTextEdit, InlineColorBar, _FontPickerPanel
from entities.task.ui.task_list import TaskItemDelegate, CategoryBar, CategoryEditDialog, TaskListWidget
from entities.task.ui.subtask_widget import SubtaskListWidget, SubtaskDelegate
from shared.ui.dialogs import ReminderDialog, DownwardCombo, CrispCheckBox, RoundedPopupCombo
from pages.analytics.page import AnalyticsPage
from pages.calendar.page import CalendarPage
from pages.finance.page import FinancePage
from widgets.tutorial.ui import TutorialOverlay
import app.styles.themes as styles

from features.task.filter_tasks.ui import FilterMixin, _desc_plain
from features.task.edit_task.ui import EditorMixin
from features.task.manage_tasks.ui import TasksMixin
from features.category.manage_categories.ui import CategoriesMixin
from features.navigation.system.ui import SystemMixin
from features.settings.manage_settings.ui import SettingsMixin
from features.task.undo_redo.ui import HistoryMixin


class _HamburgerPopup(QWidget):
    """Custom popup that mirrors _MenuPreviewPanel styling exactly (proper border-radius on Windows)."""

    def __init__(self, parent: QWidget, items: list, pos: QPoint):
        super().__init__(parent)
        try:
            import app.styles.themes as _st
            _theme = _st.current_theme()
            _th = _st._THEMES.get(_theme, _st._THEMES["dark"])
        except Exception:
            _theme = "dark"
            _th = {}
        _light = _theme == "light"
        _glass = _theme == "glass"

        # Use exact token values from themes.py so popup matches other themed elements
        _bg      = _th.get("bg_panel",     "#F7F8FB" if _light else "rgba(14,26,52,0.86)" if _glass else "#1c1c1e")
        _bdr     = _th.get("glass_border", "#D5DCE8" if _light else "rgba(148,202,255,0.36)" if _glass else "rgba(255,255,255,0.12)")
        _txt     = _th.get("text",         "#1A1F2E" if _light else "#e8f0ff" if _glass else "#f5f5f7")
        _hov     = _th.get("glass_hover",  "rgba(59,130,246,0.08)" if _light else "rgba(95,135,232,0.17)" if _glass else "rgba(255,255,255,0.08)")
        _chk_bg  = _th.get("accent_glow",  "rgba(59,130,246,0.15)" if _light else "rgba(94,162,255,0.22)" if _glass else "rgba(10,132,255,0.22)")
        _chk_txt = _th.get("accent",       "#3B82F6" if _light else "#5ea2ff" if _glass else "#0a84ff")
        _sep_c   = _th.get("separator",    "#D5DCE8" if _light else "rgba(110,158,255,0.14)" if _glass else "rgba(255,255,255,0.12)")

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("HamburgerPopup")
        self.setStyleSheet(f"""
            QWidget#HamburgerPopup {{
                background-color: {_bg};
                border: 1px solid {_bdr};
                border-radius: 12px;
            }}
            QPushButton#HBItem {{
                color: {_txt};
                font-size: 13px;
                font-weight: 400;
                padding: 7px 20px 7px 12px;
                min-width: 180px;
                text-align: left;
                background: transparent;
                border: none;
                border-radius: 8px;
            }}
            QPushButton#HBItem:hover {{
                background-color: {_hov};
            }}
            QPushButton#HBItemChecked {{
                color: {_chk_txt};
                font-size: 13px;
                font-weight: 400;
                padding: 7px 20px 7px 12px;
                min-width: 180px;
                text-align: left;
                background-color: {_chk_bg};
                border: none;
                border-radius: 8px;
            }}
            QPushButton#HBItemChecked:hover {{
                background-color: {_chk_bg};
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(1)

        for item in items:
            if item is None:
                sep = QFrame()
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background: {_sep_c}; border: none; margin: 2px 6px;")
                lay.addWidget(sep)
            else:
                label, checked, callback = item
                btn = QPushButton(label)
                btn.setObjectName("HBItemChecked" if checked else "HBItem")
                btn.clicked.connect(lambda _=False, cb=callback: (self.close(), cb()))
                lay.addWidget(btn)

        self.adjustSize()

        # Clamp to parent bounds
        pw = parent.width()
        x = min(pos.x(), pw - self.width() - 4)
        self.move(max(0, x), pos.y())
        self.raise_()
        self.show()

        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.MouseButtonPress:
            gp = event.globalPosition().toPoint()
            local = self.parent().mapFromGlobal(gp)
            if not self.geometry().contains(local):
                self.close()
        return False

    def closeEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        mw = self.parent()
        if hasattr(mw, '_hb_popup') and mw._hb_popup is self:
            import time
            mw._hb_popup = None
            mw._hamburger_closed_at = time.time()
        super().closeEvent(event)


class MainWindow(HistoryMixin, FilterMixin, EditorMixin, TasksMixin, CategoriesMixin, SystemMixin, SettingsMixin, QMainWindow):
    FILTER_ALL          = "ALL"
    FILTER_ACTIVE       = "ACTIVE"
    FILTER_DONE         = "DONE"
    FILTER_CATEGORY     = "CATEGORY"
    FILTER_TODAY        = "TODAY"
    FILTER_ARCHIVE      = "ARCHIVE"
    FILTER_CALENDAR_DAY = "CALENDAR_DAY"

    SORT_NEW = "NEW"
    SORT_OLD = "OLD"
    SORT_ALPHA = "ALPHA"
    SORT_UNDONE_FIRST = "UNDONE_FIRST"
    SORT_MANUAL = "MANUAL"

    ZOOM_MIN = 0.7
    ZOOM_MAX = 1.5
    ZOOM_STEP = 0.1

    def __init__(self):
        super().__init__()
        self.svc = TaskService()
        self.analytics_svc = AnalyticsService(self.svc.db)
        self.category_svc = CategoryService(self.svc.db)
        self.finance_svc = FinanceService(self.svc.db)

        self.all_tasks: list[Task] = []
        self.categories: list[Category] = []
        self.current_task_id: int | None = None
        self.current_category_id: int | None = None

        self._block_editor_signals = False
        self._dirty = False
        self._populating_list = False
        self._inline_editing = False
        self._finance_window = None
        self._hamburger_closed_at = 0.0
        self._hb_popup: "_HamburgerPopup | None" = None

        self.filter_mode = self.FILTER_ALL
        self.sort_mode = self.SORT_NEW
        self._calendar_filter_date = None
        self._settings = QSettings("todo_app", "todo_mvp")
        self._confirm_delete = self._settings.value("confirm_delete", True, type=bool)
        self._archive_auto_days = self._settings.value("archive_auto_days", 7, type=int)

        self._base_font = QApplication.font()
        _saved_zoom = self._settings.value("zoom_factor", 1.0, type=float)
        self.zoom_factor = max(self.ZOOM_MIN, min(self.ZOOM_MAX, _saved_zoom))

        _saved_theme = self._settings.value("theme", "dark", type=str)
        styles.set_theme(_saved_theme)

        self.setWindowTitle("toXo")
        self.resize(1600, 960)

        self._build_ui()
        self._connect_signals()
        self._setup_hotkeys()

        # Restore saved description font
        _fam = self._settings.value("desc_font_family", "Segoe UI", type=str)
        _fsz = self._settings.value("desc_font_size", 13, type=int)
        from shared.ui.widgets import get_font_presets as _gfp
        if _fam in _gfp():
            self._desc_font_btn.setText(_fam)
        self._desc_size_lbl.setText(str(_fsz))
        _init_font = QFont(_fam, _fsz)
        self.editor_desc.setFont(_init_font)
        self.editor_desc.document().setDefaultFont(_init_font)
        self._init_history()

        styles.apply_app_style(self, self.zoom_factor)
        styles.apply_button_shadows(self)
        styles.force_white_text(self)
        if hasattr(self.editor_desc, "_color_bar"):
            self.editor_desc._color_bar.apply_theme(styles.current_theme())

        # First-launch: if no tasks at all, seed the tutorial task
        if not self._settings.value("tutorial_task_seeded", False, type=bool):
            if not self.svc.list_tasks():
                self.svc.db._seed_tutorial_task()
            self._settings.setValue("tutorial_task_seeded", True)

        self.refresh()
        self.show_empty_right()

        self._setup_tray()
        self._setup_reminder_timer()

        if not self._settings.value("tutorial_shown", False, type=bool):
            QTimer.singleShot(600, self._start_tutorial)

    # ---------------- UI build ----------------
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(self.splitter, 1)

        # Floating toast label (shown by HistoryMixin._show_toast)
        self._toast_label = QLabel(root)
        self._toast_label.setObjectName("ToastLabel")
        self._toast_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._toast_label.hide()

        left = self._build_left_panel()
        right = self._build_right_panel()

        # Finance sidebar lives inside _task_area (index 1); Finance mode auto-switches it
        from widgets.finance_sidebar.ui import FinanceSidebar as _FinanceSidebar
        self._finance_sidebar = _FinanceSidebar()
        self._finance_sidebar.use_as_income.connect(
            lambda v: self._on_calc_use(v, "income"))
        self._finance_sidebar.use_as_expense.connect(
            lambda v: self._on_calc_use(v, "expense"))
        self._task_area.addWidget(self._finance_sidebar)        # index 1: finance calc

        self.splitter.addWidget(left)
        self.splitter.addWidget(right)

        self._split_ratio = 0.30
        self._setup_splitter(left, right)
        self.splitter.splitterMoved.connect(self._on_splitter_moved)

    def _build_left_panel(self) -> QWidget:
        left = QWidget()
        self.left_panel = left
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 16, 8, 16)
        left_layout.setSpacing(10)

        self.controls_wrap = QWidget()
        self.controls_wrap.setObjectName("ControlsWrap")
        self.controls_wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        cw = QVBoxLayout(self.controls_wrap)
        cw.setContentsMargins(0, 0, 0, 0)
        cw.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        top_row.setSpacing(10)

        self.btn_hamburger = QPushButton("☰")
        self.btn_hamburger.setObjectName("HamburgerBtn")
        self.btn_hamburger.setToolTip(tr("toolbar.menu"))

        self.search = QLineEdit()
        self.search.setObjectName("SearchBox")
        self.search.setPlaceholderText(tr("toolbar.search"))

        self.btn_new = QPushButton("+")
        self.btn_new.setObjectName("NewBtn")
        self.btn_new.setToolTip(tr("toolbar.new_tooltip"))

        top_row.addWidget(self.btn_hamburger)
        top_row.addWidget(self.search, 1)
        top_row.addWidget(self.btn_new)
        cw.addLayout(top_row)

        filters_row = QHBoxLayout()
        filters_row.setSpacing(12)
        filters_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.btn_all = QPushButton(tr("filter.all"))
        self.btn_all.setObjectName("FilterBtn")
        self.btn_active = QPushButton(tr("filter.active"))
        self.btn_active.setObjectName("FilterBtn")
        self.btn_done = QPushButton(tr("filter.done"))
        self.btn_done.setObjectName("FilterBtn")
        self.btn_today = QPushButton(tr("filter.today"))
        self.btn_today.setObjectName("TodayBtn")

        for b in (self.btn_all, self.btn_active, self.btn_done):
            b.setCheckable(True)
            b.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            b.setMinimumWidth(100)
        self.btn_today.setCheckable(True)
        self.btn_today.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self.btn_archive = QPushButton(tr("filter.archive"))
        self.btn_archive.setObjectName("ArchiveBtn")
        self.btn_archive.setCheckable(True)
        self.btn_archive.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self.btn_all.setChecked(True)

        filters_row.addWidget(self.btn_all)
        filters_row.addWidget(self.btn_active)
        filters_row.addWidget(self.btn_today)
        filters_row.addWidget(self.btn_done)
        filters_row.addWidget(self.btn_archive)

        self.sort_combo = QComboBox()
        self.sort_combo.setObjectName("SortCombo")
        self.sort_combo.addItem(tr("sort.new"), self.SORT_NEW)
        self.sort_combo.addItem(tr("sort.old"), self.SORT_OLD)
        self.sort_combo.addItem(tr("sort.alpha"), self.SORT_ALPHA)
        self.sort_combo.addItem(tr("sort.undone"), self.SORT_UNDONE_FIRST)
        self.sort_combo.addItem(tr("sort.manual"), self.SORT_MANUAL)

        sort_row = QHBoxLayout()
        sort_row.setSpacing(12)
        sort_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        sort_row.addWidget(self.sort_combo, 1)

        # Wrap filters + sort into a single widget so they can be hidden in finance mode
        self._task_filter_sort = QFrame()
        self._task_filter_sort.setObjectName("FilterSortPanel")
        tfs = QVBoxLayout(self._task_filter_sort)
        tfs.setContentsMargins(10, 8, 10, 8)
        tfs.setSpacing(8)
        tfs.addLayout(filters_row)
        tfs.addLayout(sort_row)
        cw.addWidget(self._task_filter_sort)

        left_layout.addWidget(self.controls_wrap, 0)

        self.category_bar = CategoryBar()
        self.category_bar.category_selected.connect(self.on_category_selected)
        self.category_bar.category_rename.connect(self.on_category_rename)
        self.category_bar.category_delete.connect(self.on_category_delete)
        self.category_bar.add_category.connect(self.on_add_category)
        self.category_bar.category_reordered.connect(self.on_category_reordered)
        self.category_bar.task_dropped.connect(self.on_task_dropped_to_category)

        self.quick_add = QLineEdit()
        self.quick_add.setObjectName("QuickAdd")
        self.quick_add.setPlaceholderText(tr("toolbar.quick_add_ph"))
        self.quick_add.setFixedHeight(34)

        self.list = TaskListWidget()
        self.list.setObjectName("TaskList")
        self.list.setAlternatingRowColors(False)
        self.list.setSpacing(2)
        self.list.setWordWrap(False)
        self.list.setItemDelegate(TaskItemDelegate(self.list))
        self.list.setSelectionMode(TaskListWidget.SelectionMode.ExtendedSelection)
        self.list.setDragEnabled(True)
        self.list.setDragDropMode(TaskListWidget.DragDropMode.DragOnly)

        # Hidden nav buttons — kept as attributes so internal setChecked() calls still work
        self.btn_analytics = QPushButton(tr("toolbar.analytics"), left)
        self.btn_analytics.setObjectName("AnalyticsBtn")
        self.btn_analytics.setCheckable(True)
        self.btn_analytics.hide()

        self.btn_calendar = QPushButton(tr("toolbar.calendar"), left)
        self.btn_calendar.setObjectName("CalendarBtn")
        self.btn_calendar.setCheckable(True)
        self.btn_calendar.hide()

        self.btn_settings = QPushButton(tr("toolbar.settings"), left)
        self.btn_settings.setObjectName("SettingsBtn")
        self.btn_settings.hide()

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 8, 0, 12)
        self.btn_delete = QPushButton(tr("toolbar.delete"))
        self.btn_delete.setObjectName("DangerBtn")
        self.btn_delete.setToolTip(tr("toolbar.delete_tooltip"))
        bottom.addWidget(self.btn_delete)

        bottom.addStretch(1)

        self.stats = QLabel(tr("stats.default"))
        self.stats.setObjectName("StatsLabel")
        self.stats.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        bottom.addWidget(self.stats)

        # ── Task-content area — only this is swapped in Finance mode ───────
        # controls_wrap (hamburger/search/+/filters/sort) stays visible above.
        tasks_page = QWidget()
        tasks_page.setObjectName("TasksPage")
        tasks_page.setStyleSheet("#TasksPage { background: transparent; }")
        tp = QVBoxLayout(tasks_page)
        tp.setContentsMargins(0, 0, 0, 0)
        tp.setSpacing(10)
        task_list_panel = QFrame()
        task_list_panel.setObjectName("TaskListPanel")
        tlp = QVBoxLayout(task_list_panel)
        tlp.setContentsMargins(6, 6, 6, 6)
        tlp.setSpacing(0)
        tlp.addWidget(self.list)

        tp.addWidget(self.category_bar, 0)
        tp.addWidget(self.quick_add)
        tp.addWidget(task_list_panel, 1)
        tp.addLayout(bottom)

        self._task_area = QStackedWidget()
        self._task_area.addWidget(tasks_page)           # index 0: task content
        # index 1 (FinanceSidebar) added in _build_ui after sidebar is created
        left_layout.addWidget(self._task_area, 1)

        return left

    def _build_right_panel(self) -> QWidget:
        right = QWidget()
        self.right_panel = right
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 16, 8, 10)
        right_layout.setSpacing(8)

        self.right_stack = QStackedWidget()
        right_layout.addWidget(self.right_stack, 1)

        # Empty page (index 0)
        empty_page = QWidget()
        ep = QVBoxLayout(empty_page)
        ep.setContentsMargins(0, 0, 0, 0)
        ep.setSpacing(0)
        ep.addStretch(1)
        _logo_row_w = QWidget()
        _logo_row = QHBoxLayout(_logo_row_w)
        _logo_row.setContentsMargins(0, 0, 0, 0)
        _logo_row.setSpacing(0)
        _logo_row.addStretch(1)
        _lbl_to = QLabel("to")
        _lbl_to.setObjectName("AppName")
        _lbl_to.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        _logo_row.addWidget(_lbl_to)
        _icon_path = IMAGES_DIR / "app_icon.png"
        _icon_lbl = QLabel()
        _icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if _icon_path.exists():
            _px = QPixmap(str(_icon_path)).scaled(72, 72, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            _icon_lbl.setPixmap(_px)
        _logo_row.addWidget(_icon_lbl)
        _lbl_o = QLabel("o")
        _lbl_o.setObjectName("AppName")
        _lbl_o.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        _logo_row.addWidget(_lbl_o)
        _logo_row.addStretch(1)
        ep.addWidget(_logo_row_w)
        ep.addSpacing(16)
        self.empty_hint = QLabel(tr("editor.empty_hint"))
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_hint.setObjectName("EmptyHint")
        ep.addWidget(self.empty_hint)
        ep.addStretch(1)

        # Editor page (index 1)
        editor_page = QWidget()
        er = QVBoxLayout(editor_page)
        er.setContentsMargins(0, 0, 0, 0)
        er.setSpacing(10)

        self.editor_title = FocusSaveLineEdit(
            self.save_current_task_if_dirty,
            self.save_current_task_if_dirty
        )
        self.editor_title.setObjectName("EditorTitle")
        self.editor_title.setPlaceholderText("")

        self.editor_meta = QLabel("")
        self.editor_meta.setObjectName("EditorMeta")
        self.editor_meta.setWordWrap(True)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Plain)

        self.editor_desc = FocusSaveTextEdit(self.save_current_task_if_dirty)
        self.editor_desc.setPlaceholderText(tr("editor.desc_ph"))
        self.editor_desc.setAcceptRichText(False)
        self.editor_desc.setObjectName("EditorDesc")

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(6)

        self.btn_back_to_calendar = QToolButton()
        self.btn_back_to_calendar.setText("←")
        self.btn_back_to_calendar.setObjectName("TaskMenuBtn")
        self.btn_back_to_calendar.setFixedSize(28, 28)
        self.btn_back_to_calendar.setToolTip(tr("toolbar.calendar"))
        self.btn_back_to_calendar.hide()
        title_row.addWidget(self.btn_back_to_calendar)

        title_row.addWidget(self.editor_title, 1)
        self.btn_task_menu = QToolButton()
        self.btn_task_menu.setText("···")
        self.btn_task_menu.setObjectName("TaskMenuBtn")
        self.btn_task_menu.setFixedSize(28, 28)
        self.btn_task_menu.setToolTip(tr("editor.task_menu_tip"))
        title_row.addWidget(self.btn_task_menu)
        er.addLayout(title_row)
        er.addWidget(self.editor_meta)
        er.addWidget(line)

        # Priority / Pin / Recurrence + Tags — wrapped in a glass card
        meta_panel = QFrame()
        meta_panel.setObjectName("EditorMetaPanel")
        _mp = QVBoxLayout(meta_panel)
        _mp.setContentsMargins(10, 8, 10, 8)
        _mp.setSpacing(6)

        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(6)

        self.lbl_priority_label = QLabel(tr("editor.priority_label"))
        self.lbl_priority_label.setObjectName("EditorMeta")
        self.lbl_priority_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        meta_row.addWidget(self.lbl_priority_label)

        self.btn_pri_none = QPushButton(tr("editor.pri_none"))
        self.btn_pri_low  = QPushButton(tr("editor.pri_low"))
        self.btn_pri_med  = QPushButton(tr("editor.pri_med"))
        self.btn_pri_high = QPushButton(tr("editor.pri_high"))
        for btn, obj in (
            (self.btn_pri_none, "PriNoneBtn"),
            (self.btn_pri_low,  "PriLowBtn"),
            (self.btn_pri_med,  "PriMedBtn"),
            (self.btn_pri_high, "PriHighBtn"),
        ):
            btn.setObjectName(obj)
            btn.setCheckable(True)
            btn.setFixedHeight(26)
            meta_row.addWidget(btn)

        meta_row.addSpacing(8)

        self.btn_pin = QPushButton(tr("editor.pin_btn"))
        self.btn_pin.setObjectName("PinBtn")
        self.btn_pin.setCheckable(True)
        self.btn_pin.setFixedHeight(26)
        self.btn_pin.setToolTip(tr("editor.pin_tip"))
        meta_row.addWidget(self.btn_pin)

        meta_row.addSpacing(8)

        self.lbl_recurrence_label = QLabel(tr("editor.recurrence_label"))
        self.lbl_recurrence_label.setObjectName("EditorMeta")
        self.lbl_recurrence_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        meta_row.addWidget(self.lbl_recurrence_label)

        self.rec_combo = RoundedPopupCombo()
        self.rec_combo.setObjectName("RecCombo")
        self.rec_combo.addItem(tr("editor.rec_none"),    None)
        self.rec_combo.addItem(tr("editor.rec_daily"),   "daily")
        self.rec_combo.addItem(tr("editor.rec_weekly"),  "weekly")
        self.rec_combo.addItem(tr("editor.rec_monthly"), "monthly")
        self.rec_combo.setFixedHeight(26)
        self.rec_combo.setMinimumWidth(110)
        self.rec_combo.setToolTip(tr("editor.rec_tip"))
        meta_row.addWidget(self.rec_combo)

        meta_row.addSpacing(8)

        self.btn_reminder = QPushButton(tr("editor.reminder_btn"))
        self.btn_reminder.setObjectName("ReminderBtn")
        self.btn_reminder.setFixedHeight(26)
        self.btn_reminder.setToolTip(tr("editor.reminder_tip"))
        meta_row.addWidget(self.btn_reminder)

        self.btn_deadline = QPushButton(tr("editor.deadline_btn"))
        self.btn_deadline.setObjectName("DeadlineBtn")
        self.btn_deadline.setFixedHeight(26)
        self.btn_deadline.setToolTip(tr("editor.deadline_tip"))
        meta_row.addWidget(self.btn_deadline)

        meta_row.addStretch(1)
        _mp.addLayout(meta_row)

        # Tags row
        tags_row = QHBoxLayout()
        tags_row.setContentsMargins(0, 0, 0, 0)
        tags_row.setSpacing(8)
        self.lbl_tags_label = QLabel(tr("editor.tags_label") + ":")
        self.lbl_tags_label.setObjectName("EditorMeta")
        self.lbl_tags_label.setFixedWidth(44)
        tags_row.addWidget(self.lbl_tags_label)
        self.tags_input = QLineEdit()
        self.tags_input.setObjectName("TagsInput")
        self.tags_input.setPlaceholderText(tr("editor.tag_add_ph"))
        self.tags_input.setFixedHeight(26)
        tags_row.addWidget(self.tags_input, 1)
        _mp.addLayout(tags_row)
        er.addWidget(meta_panel)

        # Description + Subtasks in a vertical splitter
        _ds = QSplitter(Qt.Orientation.Vertical)
        _ds.setChildrenCollapsible(False)
        _ds.setHandleWidth(8)
        _ds.setStyleSheet("""
            QSplitter::handle {
                background: rgba(255,255,255,0.06);
                border-radius: 2px;
                margin: 0 4px;
            }
            QSplitter::handle:hover { background: rgba(10,132,255,0.45); }
        """)

        _desc_pane = QFrame()
        _desc_pane.setObjectName("DescPanel")
        _dp = QVBoxLayout(_desc_pane)
        _dp.setContentsMargins(8, 6, 8, 6)
        _dp.setSpacing(4)

        # Font controls + colour bar in one row
        # Layout: [left_wrapper(expand)] [colorbar] [right_wrapper(expand)]
        # left_wrapper contains font controls left-aligned; right_wrapper is empty.
        # Equal expand factors give true center for the colour bar.
        _bar_row = QHBoxLayout()
        _bar_row.setContentsMargins(0, 4, 0, 0)
        _bar_row.setSpacing(0)

        # ── left side: font controls ──────────────────────────────────────
        _left_w = QWidget()
        _left_w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        _left_lay = QHBoxLayout(_left_w)
        _left_lay.setContentsMargins(0, 0, 0, 0)
        _left_lay.setSpacing(6)

        self._desc_font_btn = QPushButton("Segoe UI")
        self._desc_font_btn.setObjectName("DescFontCombo")
        self._desc_font_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._desc_font_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._desc_font_btn.clicked.connect(self._toggle_desc_font_panel)
        _left_lay.addWidget(self._desc_font_btn)
        self._desc_font_panel = _FontPickerPanel()
        self._desc_font_panel.font_chosen.connect(self._on_desc_font_chosen)

        _btn_font_sm = QPushButton("−")
        _btn_font_sm.setObjectName("DescSizeBtn")
        _btn_font_sm.setFixedSize(24, 24)
        _btn_font_sm.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        _btn_font_sm.setCursor(Qt.CursorShape.PointingHandCursor)
        _left_lay.addWidget(_btn_font_sm)

        self._desc_size_lbl = QLabel("13")
        self._desc_size_lbl.setObjectName("DescSizeLbl")
        self._desc_size_lbl.setFixedWidth(24)
        self._desc_size_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _left_lay.addWidget(self._desc_size_lbl)

        _btn_font_lg = QPushButton("+")
        _btn_font_lg.setObjectName("DescSizeBtn")
        _btn_font_lg.setFixedSize(24, 24)
        _btn_font_lg.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        _btn_font_lg.setCursor(Qt.CursorShape.PointingHandCursor)
        _left_lay.addWidget(_btn_font_lg)

        _btn_clear_fmt = QPushButton("✕A")
        _btn_clear_fmt.setObjectName("DescClearBtn")
        _btn_clear_fmt.setFixedSize(32, 24)
        _btn_clear_fmt.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        _btn_clear_fmt.setCursor(Qt.CursorShape.PointingHandCursor)
        _btn_clear_fmt.setToolTip(tr("editor.clear_format_tip"))
        _btn_clear_fmt.clicked.connect(self._clear_desc_format)
        _left_lay.addWidget(_btn_clear_fmt)
        _left_lay.addStretch()  # push controls to the left within the wrapper

        # ── center: colour bar ────────────────────────────────────────────
        self.inline_color_bar = InlineColorBar(self.editor_desc, _desc_pane)

        # ── right side: empty mirror to balance left ──────────────────────
        _right_w = QWidget()
        _right_w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        _bar_row.addWidget(_left_w, 1)
        _bar_row.addWidget(self.inline_color_bar, 0, Qt.AlignmentFlag.AlignVCenter)
        _bar_row.addWidget(_right_w, 1)
        _dp.addLayout(_bar_row)

        self._saved_desc_cursor = None
        self.editor_desc.selectionChanged.connect(self._on_desc_selection_changed)
        # _desc_font_btn → _toggle_desc_font_panel / _on_desc_font_chosen (wired above)
        _btn_font_sm.clicked.connect(lambda: self._change_desc_size(-1))
        _btn_font_lg.clicked.connect(lambda: self._change_desc_size(+1))

        _dp.addWidget(self.editor_desc)
        _ds.addWidget(_desc_pane)

        _sub_pane = QFrame()
        _sub_pane.setObjectName("SubtaskPanel")
        _sp = QVBoxLayout(_sub_pane)
        _sp.setContentsMargins(14, 12, 14, 12)
        _sp.setSpacing(4)

        subtask_header = QHBoxLayout()
        subtask_header.setContentsMargins(0, 0, 0, 2)
        subtask_header.setSpacing(8)
        self.lbl_subtasks = QLabel(tr("editor.subtasks_title"))
        self.lbl_subtasks.setObjectName("SubtasksTitle")
        subtask_header.addWidget(self.lbl_subtasks)
        subtask_header.addStretch(1)
        _sp.addLayout(subtask_header)

        self.subtask_progress = QProgressBar()
        self.subtask_progress.setObjectName("SubtaskProgress")
        self.subtask_progress.setFixedHeight(5)
        self.subtask_progress.setTextVisible(False)
        self.subtask_progress.setRange(0, 1)
        self.subtask_progress.setValue(0)
        self.subtask_progress.setVisible(False)
        _sp.addWidget(self.subtask_progress)

        add_sub_row = QHBoxLayout()
        add_sub_row.setContentsMargins(0, 6, 0, 2)
        add_sub_row.setSpacing(6)
        self.subtask_input = QLineEdit()
        self.subtask_input.setObjectName("SubtaskInput")
        self.subtask_input.setPlaceholderText(tr("editor.subtask_add_ph"))
        self.subtask_input.setFixedHeight(28)
        add_sub_row.addWidget(self.subtask_input, 1)
        _sp.addLayout(add_sub_row)

        self.subtask_list = SubtaskListWidget()
        _sp.addWidget(self.subtask_list, 1)

        _ds.addWidget(_sub_pane)
        _ds.setStretchFactor(0, 3)
        _ds.setStretchFactor(1, 2)

        er.addWidget(_ds, 1)

        self.right_stack.addWidget(empty_page)       # index 0
        self.right_stack.addWidget(editor_page)      # index 1

        # Analytics page (index 2)
        self.analytics_page = AnalyticsPage(self.analytics_svc)
        self.right_stack.addWidget(self.analytics_page)

        # Bulk actions page (index 3)
        bulk_page = QWidget()
        bp = QVBoxLayout(bulk_page)
        bp.setContentsMargins(32, 0, 32, 0)
        bp.setSpacing(14)
        bp.addStretch(1)

        self.lbl_bulk_count = QLabel(tr("bulk.selected", count=0, noun=tr("noun.task5")))
        self.lbl_bulk_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_bulk_count.setObjectName("BulkCountLabel")
        bp.addWidget(self.lbl_bulk_count)

        bulk_row = QHBoxLayout()
        bulk_row.setSpacing(10)
        self.btn_bulk_done = QPushButton(tr("bulk.done"))
        self.btn_bulk_done.setObjectName("FilterBtn")
        self.btn_bulk_undone = QPushButton(tr("bulk.undone"))
        self.btn_bulk_undone.setObjectName("FilterBtn")
        bulk_row.addWidget(self.btn_bulk_done)
        bulk_row.addWidget(self.btn_bulk_undone)
        bp.addLayout(bulk_row)

        self.btn_bulk_move = QPushButton(tr("bulk.move"))
        self.btn_bulk_move.setObjectName("FilterBtn")
        bp.addWidget(self.btn_bulk_move)

        self.btn_bulk_delete = QPushButton(tr("bulk.delete"))
        self.btn_bulk_delete.setObjectName("DangerBtn")
        bp.addWidget(self.btn_bulk_delete)

        bp.addStretch(1)
        self.right_stack.addWidget(bulk_page)  # index 3

        # Calendar page (index 4)
        self.calendar_page = CalendarPage(self.svc, self.analytics_svc)
        self.right_stack.addWidget(self.calendar_page)  # index 4

        # Finance page (index 5)
        self.finance_page = FinancePage(self.finance_svc)
        self.right_stack.addWidget(self.finance_page)   # index 5

        self.right_stack.setCurrentIndex(0)

        return right

    def _connect_signals(self):
        self.search.textChanged.connect(self._on_search_changed)

        self.btn_new.clicked.connect(self.create_new_task)
        self.quick_add.returnPressed.connect(self.on_quick_add)
        self.btn_delete.clicked.connect(self.on_delete)

        self.list.itemSelectionChanged.connect(self.on_selection_changed)
        self.list.itemChanged.connect(self.on_list_item_changed)
        self.list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.list.itemDelegate().closeEditor.connect(self._on_inline_edit_close)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self.show_list_context_menu)

        self.editor_title.textEdited.connect(self.on_editor_changed)
        self.editor_desc.textChanged.connect(self.on_editor_changed)
        self.editor_desc.context_menu_requested.connect(self._show_command_palette_at)

        QWidget.setTabOrder(self.editor_title, self.editor_desc)
        QWidget.setTabOrder(self.editor_desc, self.tags_input)
        QWidget.setTabOrder(self.tags_input, self.subtask_input)

        self.btn_all.clicked.connect(lambda: self.set_filter(self.FILTER_ALL))
        self.btn_active.clicked.connect(lambda: self.set_filter(self.FILTER_ACTIVE))
        self.btn_done.clicked.connect(lambda: self.set_filter(self.FILTER_DONE))
        self.btn_today.clicked.connect(lambda: self.set_filter(self.FILTER_TODAY))
        self.btn_archive.clicked.connect(lambda: self.set_filter(self.FILTER_ARCHIVE))
        self.list.reordered.connect(self.on_list_reordered)
        self.tags_input.editingFinished.connect(self.on_tags_changed)

        self.btn_reminder.clicked.connect(self.on_reminder_btn_clicked)
        self.btn_deadline.clicked.connect(self.on_deadline_btn_clicked)
        self.btn_task_menu.clicked.connect(self._show_task_menu)
        self.btn_back_to_calendar.clicked.connect(self.toggle_calendar)

        self.btn_pri_none.clicked.connect(lambda: self.on_priority_changed(0))
        self.btn_pri_low.clicked.connect(lambda:  self.on_priority_changed(1))
        self.btn_pri_med.clicked.connect(lambda:  self.on_priority_changed(2))
        self.btn_pri_high.clicked.connect(lambda: self.on_priority_changed(3))

        self.btn_pin.clicked.connect(self.on_pin_clicked)
        self.rec_combo.currentIndexChanged.connect(self.on_recurrence_changed)

        self.subtask_input.returnPressed.connect(self.on_add_subtask)
        self.subtask_list.reordered.connect(self._on_subtask_reordered)
        _d = self.subtask_list.delegate
        _d.toggle_requested.connect(self._on_subtask_toggle_by_id)
        _d.delete_requested.connect(lambda sid: self._on_subtask_delete(sid))
        _d.rename_requested.connect(self._on_subtask_rename)
        self.btn_bulk_done.clicked.connect(lambda: self.bulk_mark_done(True))
        self.btn_bulk_undone.clicked.connect(lambda: self.bulk_mark_done(False))
        self.btn_bulk_move.clicked.connect(self.bulk_move_to_category)
        self.btn_bulk_delete.clicked.connect(self.bulk_delete)

        self.btn_hamburger.clicked.connect(self._show_hamburger_menu)
        self.finance_page.popout_requested.connect(self._open_finance_window)
        self.finance_page.dock_requested.connect(self._on_dock_requested)
        # Auto-switch left panel between Tasks and Finance sidebars
        self.right_stack.currentChanged.connect(self._on_right_stack_changed)
        self.calendar_page.task_open_requested.connect(self._on_calendar_task_open)
        self.calendar_page.task_added.connect(self._on_calendar_task_added)
        self.calendar_page.data_changed.connect(self._on_calendar_data_changed)
        self.calendar_page.filter_by_day.connect(self._on_calendar_filter_by_day)
        self.calendar_page.create_task_on_day.connect(self._on_calendar_create_task_on_day)

        self.sort_combo.currentIndexChanged.connect(self.on_sort_changed)

    def _setup_hotkeys(self):
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.create_new_task)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.focus_search)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save_current_task_if_dirty)
        QShortcut(QKeySequence("Escape"), self, activated=self.on_escape)
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.on_undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, activated=self.on_redo)
        QShortcut(QKeySequence("Ctrl+D"), self, activated=self.toggle_done_current)
        QShortcut(QKeySequence("Ctrl+Shift+D"), self, activated=self.duplicate_task)
        QShortcut(QKeySequence("Ctrl+Up"), self, activated=lambda: self.navigate_list(-1))
        QShortcut(QKeySequence("Ctrl+Down"), self, activated=lambda: self.navigate_list(1))
        QShortcut(QKeySequence("F2"), self, activated=self.rename_task)

        QShortcut(QKeySequence("Ctrl+A"), self, activated=self.select_all_tasks)

        QShortcut(QKeySequence("Ctrl++"), self, activated=lambda: self.change_zoom(+1))
        QShortcut(QKeySequence("Ctrl+="), self, activated=lambda: self.change_zoom(+1))
        QShortcut(QKeySequence("Ctrl+-"), self, activated=lambda: self.change_zoom(-1))
        QShortcut(QKeySequence("Ctrl+0"), self, activated=self.reset_zoom)

        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)

        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.save_current_task_if_dirty)
        QShortcut(QKeySequence("Ctrl+Delete"), self, activated=self.on_delete)

        QShortcut(QKeySequence("Ctrl+K"), self, activated=self._show_command_palette)

    def _setup_splitter(self, left: QWidget, right: QWidget):
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setHandleWidth(10)

        left.setMinimumWidth(320)
        right.setMinimumWidth(400)

        left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 7)

        QTimer.singleShot(0, self._apply_split_ratio)

    def _on_splitter_moved(self, _pos: int, _index: int):
        sizes = self.splitter.sizes()
        total = sum(sizes)
        if total > 0:
            self._split_ratio = sizes[0] / total

    def _apply_split_ratio(self):
        total = self.splitter.width()
        if total <= 0:
            return

        left_w = int(total * self._split_ratio)
        right_w = total - left_w

        left_min = self.left_panel.minimumWidth()
        right_min = self.right_panel.minimumWidth()

        left_w = max(left_w, left_min)
        right_w = max(right_w, right_min)

        if left_w + right_w > total:
            right_w = max(right_min, total - left_w)

        self.splitter.setSizes([left_w, right_w])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._apply_split_ratio)
        self._reposition_toast()

    def keyPressEvent(self, event):
        focused = QApplication.focusWidget()
        is_text_input = isinstance(focused, (QLineEdit, FocusSaveTextEdit))
        if event.key() == Qt.Key.Key_Delete and not is_text_input:
            self.on_delete()
            event.accept()
            return
        super().keyPressEvent(event)

    # ---------------- ZOOM ----------------
    def wheelEvent(self, event):
        if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.change_zoom(+1)
            elif delta < 0:
                self.change_zoom(-1)
            event.accept()
            return
        super().wheelEvent(event)

    def change_zoom(self, direction: int):
        new_zoom = self.zoom_factor + (self.ZOOM_STEP * (1 if direction > 0 else -1))
        new_zoom = max(self.ZOOM_MIN, min(self.ZOOM_MAX, new_zoom))
        if abs(new_zoom - self.zoom_factor) < 1e-9:
            return
        self.zoom_factor = new_zoom
        self._settings.setValue("zoom_factor", self.zoom_factor)
        self._apply_styles()
        self._refresh_settings_page()

    def reset_zoom(self):
        self.zoom_factor = 1.0
        self._settings.setValue("zoom_factor", 1.0)
        self._apply_styles()
        self._refresh_settings_page()

    def _set_zoom_from_settings(self, zoom: float) -> None:
        self.zoom_factor = zoom
        self._settings.setValue("zoom_factor", zoom)
        self._apply_styles()
        self._refresh_settings_page()

    def _on_zoom_slider_changed(self, value: int) -> None:
        zoom = round(0.7 + value * 0.1, 1)
        self._set_zoom_from_settings(zoom)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _apply_styles(self):
        styles.apply_app_style(self, self.zoom_factor)
        styles.apply_button_shadows(self)
        styles.force_white_text(self)
        self._reposition_toast()
        if hasattr(self, "category_bar"):
            self.category_bar.apply_theme()
        if hasattr(self, "editor_desc") and hasattr(self.editor_desc, "_color_bar"):
            import app.styles.themes as _st
            self.editor_desc._color_bar.apply_theme(_st.current_theme())
        if hasattr(self, "_desc_font_panel"):
            import app.styles.themes as _st
            self._desc_font_panel.apply_theme(_st.current_theme())
        if hasattr(self, "analytics_page"):
            self.analytics_page.apply_theme()
        if hasattr(self, "calendar_page"):
            self.calendar_page.apply_theme()
        if hasattr(self, "finance_page"):
            self.finance_page.apply_theme()
        if hasattr(self, "_finance_sidebar"):
            import app.styles.themes as _s
            _theme = _s.current_theme()
            self._finance_sidebar.apply_theme(_theme)
            # Also re-theme the standalone FinanceWindow if it's open
            if self._finance_window is not None:
                self._finance_window._apply_win_theme(_theme)

    # ---------------- utils ----------------
    def show_error(self, text: str):
        QMessageBox.critical(self, tr("dlg.error"), text)

    def focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def selected_task_id(self) -> int | None:
        it = self.list.currentItem()
        if not it:
            return None
        try:
            return int(it.data(Qt.ItemDataRole.UserRole))
        except Exception:
            return None

    def selected_task_ids(self) -> list[int]:
        result = []
        for item in self.list.selectedItems():
            try:
                result.append(int(item.data(Qt.ItemDataRole.UserRole)))
            except Exception:
                pass
        return result

    def show_empty_right(self):
        self.current_task_id = None
        self._dirty = False
        self._block_editor_signals = True
        try:
            self.editor_title.setText("")
            self.editor_meta.setText("")
            self.editor_desc.setPlainText("")
            self.btn_reminder.setText(tr("editor.reminder_btn"))
            self.btn_reminder.setStyleSheet("")
            self.btn_deadline.setText(tr("editor.deadline_btn"))
            self.btn_deadline.setStyleSheet("")
            self._set_priority_buttons(0)
            self.btn_pin.setChecked(False)
            self.btn_pin.setText(tr("editor.pin_btn"))
            self.rec_combo.blockSignals(True)
            self.rec_combo.setCurrentIndex(0)
            self.rec_combo.blockSignals(False)
            self._clear_subtasks_ui()
            self.subtask_input.setText("")
            self.tags_input.setText("")
        finally:
            self._block_editor_signals = False
        if self.right_stack.currentIndex() not in (2, 4, 5):
            self.btn_analytics.setChecked(False)
            self.btn_calendar.setChecked(False)
            self.right_stack.setCurrentIndex(0)

    def show_editor_right(self):
        if self.right_stack.currentIndex() in (2, 4, 5):
            return
        self.btn_analytics.setChecked(False)
        self.btn_calendar.setChecked(False)
        self.btn_settings.setChecked(False)
        self.right_stack.setCurrentIndex(1)

    def toggle_analytics(self):
        if self.right_stack.currentIndex() == 2:
            self.btn_analytics.setChecked(False)
            if self.current_task_id is not None:
                self.right_stack.setCurrentIndex(1)
            else:
                self.right_stack.setCurrentIndex(0)
        else:
            self.save_current_task_if_dirty()
            self.btn_analytics.setChecked(True)
            self.btn_calendar.setChecked(False)
            self.btn_settings.setChecked(False)
            self.right_stack.setCurrentIndex(2)
            QTimer.singleShot(50, self.analytics_page.refresh)

    def toggle_calendar(self):
        if self.right_stack.currentIndex() == 4:
            self.btn_calendar.setChecked(False)
            if self.filter_mode == self.FILTER_CALENDAR_DAY:
                self.filter_mode = self.FILTER_ALL
                self._calendar_filter_date = None
                self.apply_filter(keep_selection=False)
            if self.current_task_id is not None:
                self.right_stack.setCurrentIndex(1)
            else:
                self.right_stack.setCurrentIndex(0)
        else:
            self.save_current_task_if_dirty()
            self.btn_analytics.setChecked(False)
            self.btn_calendar.setChecked(True)
            self.btn_settings.setChecked(False)
            self.right_stack.setCurrentIndex(4)
            QTimer.singleShot(50, lambda: self.calendar_page.refresh(self.all_tasks, self.categories))

    def toggle_finance(self):
        if self._finance_window is not None:
            self._finance_window.raise_()
            self._finance_window.activateWindow()
        elif self.right_stack.currentIndex() == 5:
            self.right_stack.setCurrentIndex(1 if self.current_task_id else 0)
        else:
            self.save_current_task_if_dirty()
            self.btn_analytics.setChecked(False)
            self.btn_calendar.setChecked(False)
            self.right_stack.setCurrentIndex(5)
            QTimer.singleShot(50, self.finance_page.refresh)

    # ---------------- Finance undock / dock ----------------

    def _open_finance_window(self):
        """Undock Finance: move FinancePage into its own OS window."""
        from pages.finance.page import FinanceWindow
        if self._finance_window is not None:
            self._finance_window.raise_()
            self._finance_window.activateWindow()
            return

        self.save_current_task_if_dirty()
        self.btn_analytics.setChecked(False)
        self.btn_calendar.setChecked(False)

        # Update button before reparenting (while widget is still visible)
        self.finance_page.set_popout_mode(True)

        # Reparent finance_page into FinanceWindow WHILE it is still visible.
        # FinanceWindow also creates its own FinanceSidebar internally.
        self._finance_window = FinanceWindow(
            self.finance_page, self._settings, self.finance_svc)
        self._finance_window.window_closed.connect(self._on_finance_window_closed)

        # Switch main window to neutral (left_stack auto-switches via currentChanged)
        self.right_stack.setCurrentIndex(0)

        self._finance_window.show()
        self._finance_window.activateWindow()

    def _on_dock_requested(self):
        """User clicked dock-back inside FinanceWindow — restore Finance to main window."""
        if self._finance_window is None:
            return
        self._settings.setValue(
            "finance_window/geometry", self._finance_window.saveGeometry()
        )
        self.finance_page.set_popout_mode(False)
        # Re-insert finance_page at index 5 in right_stack
        self.right_stack.insertWidget(5, self.finance_page)
        self._finance_window.window_closed.disconnect()
        win = self._finance_window
        self._finance_window = None  # clear BEFORE setCurrentIndex so _on_right_stack_changed sees it
        self.right_stack.setCurrentIndex(5)
        win.close()

    def _on_finance_window_closed(self):
        """FinanceWindow closed via OS X button — dock Finance back to main window."""
        if self._finance_window is None:
            return
        self.finance_page.set_popout_mode(False)
        self.right_stack.insertWidget(5, self.finance_page)
        self._finance_window = None  # clear BEFORE setCurrentIndex so _on_right_stack_changed sees it
        self.right_stack.setCurrentIndex(5)

    def _on_right_stack_changed(self, idx: int):
        """Auto-switch left panel: Finance sidebar when Finance is active, Tasks otherwise."""
        if hasattr(self, "_task_area") and self._finance_window is None:
            self._task_area.setCurrentIndex(1 if idx == 5 else 0)
        is_finance = idx == 5
        for w in (self.search, self.btn_new, self._task_filter_sort):
            w.setVisible(not is_finance)
        if hasattr(self, "_finance_sidebar"):
            # FinanceSidebar outer margins: 10 left + 10 right = 20px, plus splitter border ~4px
            sidebar_w = self._finance_sidebar.WIDTH + 20
            if is_finance:
                self._pre_finance_split_ratio = self._split_ratio
                self.left_panel.setMinimumWidth(sidebar_w)
                QTimer.singleShot(0, lambda w=sidebar_w: self.splitter.setSizes(
                    [w, max(400, self.splitter.width() - w)]))
            else:
                self.left_panel.setMinimumWidth(320)
                if hasattr(self, "_pre_finance_split_ratio"):
                    self._split_ratio = self._pre_finance_split_ratio
                QTimer.singleShot(0, self._apply_split_ratio)

    def _on_calc_use(self, amount: float, tx_type: str):
        """Calculator quick action: open AddTransactionDialog pre-filled."""
        from features.finance.create_transaction.ui import AddTransactionDialog
        # Ensure Finance tab is the current context for the dialog parent
        dlg = AddTransactionDialog(
            self.finance_svc, self,
            prefill_type=tx_type,
            prefill_amount=round(amount, 2),
        )
        if dlg.exec():
            data = dlg.result_data()
            if data and data.get("account_id") is not None:
                self.finance_svc.add_transaction(**data)
                self.finance_page.refresh()
                self.finance_page.data_changed.emit()

    def _on_calendar_task_open(self, task_id: int):
        self.btn_calendar.setChecked(False)
        self.right_stack.setCurrentIndex(1)
        task = self.svc.get_task(task_id)
        if task:
            self.load_task_into_editor(task)
        self.btn_back_to_calendar.show()

    def _on_calendar_task_added(self, task_id: int):
        self.all_tasks = self.svc.list_tasks()
        self.apply_filter(keep_selection=False)
        self._on_calendar_task_open(task_id)

    def _on_calendar_data_changed(self):
        self.all_tasks = self.svc.list_tasks()
        self.apply_filter(keep_selection=True)
        self.calendar_page.refresh(self.all_tasks, self.categories)

    def _on_calendar_filter_by_day(self, d):
        self._calendar_filter_date = d
        self.filter_mode = self.FILTER_CALENDAR_DAY
        self.apply_filter(keep_selection=False)

    def _on_calendar_create_task_on_day(self, d):
        from datetime import datetime, timezone as _tz
        deadline_iso = datetime(d.year, d.month, d.day, 9, 0, tzinfo=_tz.utc).isoformat(timespec="seconds")
        tid = self.svc.create_task(title="")
        self.svc.set_deadline(tid, deadline_iso)
        self.all_tasks = self.svc.list_tasks()
        self.apply_filter(keep_selection=False)
        self._on_calendar_task_open(tid)

    def _refresh_analytics_if_visible(self):
        if self.right_stack.currentIndex() == 2:
            self.analytics_page.refresh()
        elif self.right_stack.currentIndex() == 4:
            self.calendar_page.refresh(self.all_tasks, self.categories)

    # ---------------- Command Palette ----------------
    def _set_sort(self, mode: str):
        idx = self.sort_combo.findData(mode)
        if idx >= 0:
            self.sort_combo.setCurrentIndex(idx)

    def _show_command_palette(self):
        from widgets.command_palette.ui import CommandPalette
        p = CommandPalette(self)
        pw, ph = p.width(), p.height()
        # Center within the window's client area
        cw = self.centralWidget() or self
        origin = cw.mapToGlobal(cw.rect().topLeft())
        x = origin.x() + (cw.width() - pw) // 2
        y = origin.y() + max(80, (cw.height() - ph) // 3)
        p.move(x, y)
        p.exec()

    def _show_command_palette_at(self, global_pos: QPoint):
        from widgets.command_palette.ui import CommandPalette
        p = CommandPalette(self)
        # Keep palette on-screen
        screen = self.screen().availableGeometry() if self.screen() else None
        x, y = global_pos.x(), global_pos.y()
        if screen:
            x = min(x, screen.right() - p.width())
            y = min(y, screen.bottom() - p.height())
        p.move(x, y)
        p.exec()

    def _show_hamburger_menu(self):
        import time
        if time.time() - self._hamburger_closed_at < 0.25:
            return
        # Toggle off if already open
        if hasattr(self, '_hb_popup') and self._hb_popup is not None:
            self._hb_popup.close()
            return
        idx = self.right_stack.currentIndex()
        items = [
            (tr("toolbar.analytics"), idx == 2,                                          self.toggle_analytics),
            (tr("toolbar.calendar"),  idx == 4,                                          self.toggle_calendar),
            (tr("toolbar.finance"),   idx == 5 or self._finance_window is not None,      self.toggle_finance),
            None,
            (tr("toolbar.settings"), False,                                              self.toggle_settings),
        ]
        pos = self.btn_hamburger.mapTo(self, QPoint(0, self.btn_hamburger.height() + 4))
        self._hb_popup = _HamburgerPopup(self, items, pos)
