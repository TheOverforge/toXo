"""SettingsMixin — settings dialog, language switch, retranslate, tutorial."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QPushButton, QLabel, QHBoxLayout, QVBoxLayout, QFrame,
    QScrollArea, QSpinBox, QDialog, QSlider, QWidget,
)
from PyQt6.QtCore import Qt, QTimer, QPoint, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen

from shared.i18n import tr, set_language, current_language
from shared.ui.dialogs import CrispCheckBox, DownwardCombo
import app.styles.themes as styles


class _DragTitleBar(QWidget):
    """Draggable title bar for the frameless settings dialog."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._drag_pos: QPoint | None = None
        hl = QHBoxLayout(self)
        hl.setContentsMargins(18, 0, 10, 0)
        hl.setSpacing(8)
        self._lbl = QLabel(title)
        self._lbl.setObjectName("SettingsDialogTitle")
        hl.addWidget(self._lbl)
        hl.addStretch(1)
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("SettingsCloseBtn")
        self.btn_close.setFixedSize(30, 30)
        hl.addWidget(self.btn_close)
        self.setFixedHeight(52)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.window().pos()

    def mouseMoveEvent(self, e):
        if self._drag_pos is not None and e.buttons() == Qt.MouseButton.LeftButton:
            self.window().move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None


class _GlassSettingsDlg(QDialog):
    """Frameless translucent settings dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(False)
        self.setMinimumSize(480, 600)
        self.resize(500, 740)

    def paintEvent(self, event):
        th = styles.current_theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if th == "glass":
            p.setBrush(QColor(24, 44, 100, 195))
            p.setPen(QPen(QColor(90, 150, 255, 120), 1.0))
        elif th == "light":
            p.setBrush(QColor(240, 244, 252, 253))
            p.setPen(QPen(QColor(190, 208, 235, 200), 1.0))
        else:
            p.setBrush(QColor(16, 16, 20, 253))
            p.setPen(QPen(QColor(60, 62, 72, 180), 1.0))
        p.drawRoundedRect(rect, 16, 16)
        p.end()


class SettingsMixin:
    """Mixin: settings dialog build/refresh, sound, language, retranslate, tutorial."""

    # ──── Settings page ──────────────────────────────────

    def _build_settings_page(self) -> QWidget:
        def _card():
            f = QFrame()
            f.setObjectName("SettingsCard")
            vl = QVBoxLayout(f)
            vl.setContentsMargins(18, 14, 18, 14)
            vl.setSpacing(10)
            return f, vl

        page = QWidget()
        page.setObjectName("SettingsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 24, 20, 24)
        layout.setSpacing(10)

        self._settings_title_lbl = QLabel(tr("settings.title"))
        self._settings_title_lbl.setObjectName("SettingsTitle")
        layout.addWidget(self._settings_title_lbl)
        layout.addSpacing(6)

        # ── Theme card ──
        c, vl = _card()
        self._settings_theme_lbl = QLabel(tr("settings.theme_section").upper())
        self._settings_theme_lbl.setObjectName("SettingsSectionLabel")
        vl.addWidget(self._settings_theme_lbl)
        theme_row = QHBoxLayout()
        theme_row.setSpacing(10)
        theme_row.setContentsMargins(0, 0, 0, 0)
        self._btn_theme_dark = QPushButton(tr("settings.theme_dark"))
        self._btn_theme_dark.setObjectName("LangBtn")
        self._btn_theme_dark.setCheckable(True)
        self._btn_theme_dark.clicked.connect(lambda: self._on_set_theme("dark"))
        self._btn_theme_light = QPushButton(tr("settings.theme_light"))
        self._btn_theme_light.setObjectName("LangBtn")
        self._btn_theme_light.setCheckable(True)
        self._btn_theme_light.clicked.connect(lambda: self._on_set_theme("light"))
        self._btn_theme_glass = QPushButton(tr("settings.theme_glass"))
        self._btn_theme_glass.setObjectName("LangBtn")
        self._btn_theme_glass.setCheckable(True)
        self._btn_theme_glass.clicked.connect(lambda: self._on_set_theme("glass"))
        theme_row.addWidget(self._btn_theme_dark, 1)
        theme_row.addWidget(self._btn_theme_light, 1)
        theme_row.addWidget(self._btn_theme_glass, 1)
        vl.addLayout(theme_row)
        layout.addWidget(c)

        # ── Language card ──
        c, vl = _card()
        self._settings_lang_lbl = QLabel(tr("settings.lang_section").upper())
        self._settings_lang_lbl.setObjectName("SettingsSectionLabel")
        vl.addWidget(self._settings_lang_lbl)
        lang_row = QHBoxLayout()
        lang_row.setSpacing(10)
        lang_row.setContentsMargins(0, 0, 0, 0)
        self._btn_lang_ru = QPushButton(tr("settings.lang_ru"))
        self._btn_lang_ru.setObjectName("LangBtn")
        self._btn_lang_ru.setCheckable(True)
        self._btn_lang_ru.clicked.connect(lambda: self.on_set_language("ru"))
        self._btn_lang_en = QPushButton(tr("settings.lang_en"))
        self._btn_lang_en.setObjectName("LangBtn")
        self._btn_lang_en.setCheckable(True)
        self._btn_lang_en.clicked.connect(lambda: self.on_set_language("en"))
        lang_row.addWidget(self._btn_lang_ru, 1)
        lang_row.addWidget(self._btn_lang_en, 1)
        vl.addLayout(lang_row)
        layout.addWidget(c)

        # ── Zoom card ──
        c, vl = _card()
        self._settings_zoom_lbl = QLabel(tr("settings.zoom_section").upper())
        self._settings_zoom_lbl.setObjectName("SettingsSectionLabel")
        vl.addWidget(self._settings_zoom_lbl)
        zoom_row = QHBoxLayout()
        zoom_row.setSpacing(12)
        zoom_row.setContentsMargins(0, 0, 0, 0)
        self._zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self._zoom_slider.setObjectName("ZoomSlider")
        self._zoom_slider.setRange(0, 8)
        self._zoom_slider.setSingleStep(1)
        self._zoom_slider.setPageStep(2)
        self._zoom_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._zoom_slider.setTickInterval(1)
        self._zoom_slider.setFixedWidth(180)
        self._zoom_slider.valueChanged.connect(self._on_zoom_slider_changed)
        self._zoom_pct_lbl = QLabel("100%")
        self._zoom_pct_lbl.setObjectName("EditorMeta")
        self._zoom_pct_lbl.setMinimumWidth(40)
        zoom_row.addWidget(self._zoom_slider)
        zoom_row.addWidget(self._zoom_pct_lbl)
        zoom_row.addStretch(1)
        vl.addLayout(zoom_row)
        layout.addWidget(c)

        # ── General card ──
        c, vl = _card()
        self._settings_general_lbl = QLabel(tr("settings.general").upper())
        self._settings_general_lbl.setObjectName("SettingsSectionLabel")
        vl.addWidget(self._settings_general_lbl)
        self._cb_confirm_del = CrispCheckBox(tr("settings.confirm_del"))
        self._cb_confirm_del.setObjectName("SettingsCheck")
        self._cb_confirm_del.setChecked(self._confirm_delete)
        self._cb_confirm_del.toggled.connect(self._on_confirm_del_toggled)
        vl.addWidget(self._cb_confirm_del)
        layout.addWidget(c)

        # ── Archive card ──
        c, vl = _card()
        self._settings_archive_lbl = QLabel(tr("settings.archive").upper())
        self._settings_archive_lbl.setObjectName("SettingsSectionLabel")
        vl.addWidget(self._settings_archive_lbl)
        archive_days_row = QHBoxLayout()
        archive_days_row.setSpacing(8)
        archive_days_row.setContentsMargins(0, 0, 0, 0)
        self._spin_archive_days = QSpinBox()
        self._spin_archive_days.setMinimum(0)
        self._spin_archive_days.setMaximum(365)
        self._spin_archive_days.setValue(self._archive_auto_days)
        self._spin_archive_days.setFixedWidth(60)
        self._spin_archive_days.setObjectName("SettingsSpinBox")
        self._spin_archive_days.valueChanged.connect(self._on_archive_days_changed)
        archive_days_row.addWidget(self._spin_archive_days)
        self._lbl_archive_days = QLabel(tr("settings.archive_days_lbl"))
        self._lbl_archive_days.setObjectName("EditorMeta")
        self._lbl_archive_days.setWordWrap(True)
        archive_days_row.addWidget(self._lbl_archive_days, 1)
        vl.addLayout(archive_days_row)
        self._btn_clear_archive = QPushButton(tr("archive.clear_all"))
        self._btn_clear_archive.setObjectName("DangerBtn")
        self._btn_clear_archive.setFixedHeight(36)
        self._btn_clear_archive.clicked.connect(self._clear_archive)
        vl.addWidget(self._btn_clear_archive)
        layout.addWidget(c)

        # ── Startup card ──
        c, vl = _card()
        self._settings_startup_lbl = QLabel(tr("settings.startup").upper())
        self._settings_startup_lbl.setObjectName("SettingsSectionLabel")
        vl.addWidget(self._settings_startup_lbl)
        self._cb_autostart = CrispCheckBox(tr("settings.autostart"))
        self._cb_autostart.setObjectName("SettingsCheck")
        self._cb_autostart.setChecked(self._is_autostart_enabled())
        self._cb_autostart.toggled.connect(self._set_autostart)
        vl.addWidget(self._cb_autostart)
        layout.addWidget(c)

        # ── Sound card ──
        c, vl = _card()
        self._settings_sound_lbl = QLabel(tr("settings.sound_section").upper())
        self._settings_sound_lbl.setObjectName("SettingsSectionLabel")
        vl.addWidget(self._settings_sound_lbl)
        self._sound_combo = DownwardCombo()
        self._sound_combo.setObjectName("SoundCombo")
        self._sound_combo.setFixedWidth(300)
        self._sound_combo.currentTextChanged.connect(self._on_sound_selected)
        vl.addWidget(self._sound_combo)
        layout.addWidget(c)

        # ── Export / Import card ──
        c, vl = _card()
        self._settings_export_lbl = QLabel(tr("export.title").upper())
        self._settings_export_lbl.setObjectName("SettingsSectionLabel")
        vl.addWidget(self._settings_export_lbl)
        export_row = QHBoxLayout()
        export_row.setSpacing(10)
        export_row.setContentsMargins(0, 0, 0, 0)
        self._btn_export_csv = QPushButton(tr("export.csv"))
        self._btn_export_csv.setObjectName("ExportBtn")
        self._btn_export_csv.setFixedHeight(36)
        self._btn_export_csv.clicked.connect(lambda: self.export_tasks("csv"))
        export_row.addWidget(self._btn_export_csv)
        self._btn_export_json = QPushButton(tr("export.json"))
        self._btn_export_json.setObjectName("ExportBtn")
        self._btn_export_json.setFixedHeight(36)
        self._btn_export_json.clicked.connect(lambda: self.export_tasks("json"))
        export_row.addWidget(self._btn_export_json)
        export_row.addStretch(1)
        vl.addLayout(export_row)
        self._settings_import_lbl = QLabel(tr("settings.import_section").upper())
        self._settings_import_lbl.setObjectName("SettingsSectionLabel")
        vl.addWidget(self._settings_import_lbl)
        import_row = QHBoxLayout()
        import_row.setSpacing(10)
        import_row.setContentsMargins(0, 0, 0, 0)
        self._btn_import_csv = QPushButton(tr("import.csv"))
        self._btn_import_csv.setObjectName("ExportBtn")
        self._btn_import_csv.setFixedHeight(36)
        self._btn_import_csv.clicked.connect(lambda: self.import_tasks("csv"))
        import_row.addWidget(self._btn_import_csv)
        self._btn_import_json = QPushButton(tr("import.json"))
        self._btn_import_json.setObjectName("ExportBtn")
        self._btn_import_json.setFixedHeight(36)
        self._btn_import_json.clicked.connect(lambda: self.import_tasks("json"))
        import_row.addWidget(self._btn_import_json)
        import_row.addStretch(1)
        vl.addLayout(import_row)
        layout.addWidget(c)

        # ── Danger zone card ──
        c, vl = _card()
        self._settings_danger_lbl = QLabel(tr("settings.danger_zone").upper())
        self._settings_danger_lbl.setObjectName("SettingsSectionLabel")
        vl.addWidget(self._settings_danger_lbl)
        self._btn_seed_mock = QPushButton(tr("settings.seed_mock_data"))
        self._btn_seed_mock.setObjectName("NeutralBtn")
        self._btn_seed_mock.setFixedHeight(36)
        self._btn_seed_mock.setToolTip(tr("settings.seed_mock_data_tip"))
        self._btn_seed_mock.clicked.connect(self._seed_mock_data)
        self._btn_strip_formatting = QPushButton(tr("settings.strip_all_formatting"))
        self._btn_strip_formatting.setObjectName("NeutralBtn")
        self._btn_strip_formatting.setFixedHeight(36)
        self._btn_strip_formatting.setToolTip(tr("settings.strip_all_formatting_tip"))
        self._btn_strip_formatting.clicked.connect(self._strip_all_task_formatting)
        self._btn_clear_all_data = QPushButton(tr("settings.clear_all_data"))
        self._btn_clear_all_data.setObjectName("DangerBtn")
        self._btn_clear_all_data.setFixedHeight(36)
        self._btn_clear_all_data.clicked.connect(self._clear_all_data)
        vl.addWidget(self._btn_seed_mock)
        vl.addWidget(self._btn_strip_formatting)
        vl.addWidget(self._btn_clear_all_data)
        layout.addWidget(c)

        # ── Tutorial card ──
        c, vl = _card()
        self._settings_tutorial_lbl = QLabel(tr("settings.tutorial").upper())
        self._settings_tutorial_lbl.setObjectName("SettingsSectionLabel")
        vl.addWidget(self._settings_tutorial_lbl)
        self._btn_tutorial = QPushButton(tr("settings.tutorial"))
        self._btn_tutorial.setObjectName("TutorialBtn")
        self._btn_tutorial.setFixedHeight(36)
        self._btn_tutorial.setToolTip(tr("settings.tutorial_tip"))
        self._btn_tutorial.clicked.connect(self._on_tutorial_from_settings)
        tut_row = QHBoxLayout()
        tut_row.setContentsMargins(0, 0, 0, 0)
        tut_row.addWidget(self._btn_tutorial)
        tut_row.addStretch(1)
        vl.addLayout(tut_row)
        layout.addWidget(c)

        layout.addStretch(1)
        self._refresh_settings_page()
        return page

    def _on_set_theme(self, theme: str):
        styles.set_theme(theme)
        self._settings.setValue("theme", theme)
        self._apply_styles()
        # Update titlebar/border — dark titlebar for dark + glass themes
        _dark = (theme in ("dark", "glass"))
        self._apply_dark_titlebar(self, _dark)
        # Repaint settings dialog on theme change (CSS updates globally)
        if hasattr(self, "_settings_dlg") and self._settings_dlg is not None:
            self._settings_dlg.update()
        # Recreate category chips with new theme colours
        if hasattr(self, "refresh_categories"):
            self.refresh_categories()
        self._refresh_settings_page()

    def _refresh_settings_page(self):
        if hasattr(self, "_btn_theme_dark"):
            _th = styles.current_theme()
            self._btn_theme_dark.setChecked(_th == "dark")
            self._btn_theme_light.setChecked(_th == "light")
            self._btn_theme_glass.setChecked(_th == "glass")
        lang = current_language()
        if hasattr(self, "_btn_lang_ru"):
            self._btn_lang_ru.setChecked(lang == "ru")
            self._btn_lang_en.setChecked(lang == "en")
        if hasattr(self, "_zoom_slider"):
            _idx = max(0, min(8, round((self.zoom_factor - 0.7) / 0.1)))
            self._zoom_slider.blockSignals(True)
            self._zoom_slider.setValue(_idx)
            self._zoom_slider.blockSignals(False)
            self._zoom_pct_lbl.setText(f"{round(self.zoom_factor * 100)}%")
        if hasattr(self, "_cb_confirm_del"):
            self._cb_confirm_del.blockSignals(True)
            self._cb_confirm_del.setChecked(self._confirm_delete)
            self._cb_confirm_del.blockSignals(False)
        if hasattr(self, "_cb_autostart"):
            self._cb_autostart.blockSignals(True)
            self._cb_autostart.setChecked(self._is_autostart_enabled())
            self._cb_autostart.blockSignals(False)
        if hasattr(self, "_spin_archive_days"):
            self._spin_archive_days.blockSignals(True)
            self._spin_archive_days.setValue(self._archive_auto_days)
            self._spin_archive_days.blockSignals(False)
        if hasattr(self, "_sound_combo"):
            self._rebuild_sound_combo()

    def _rebuild_sound_combo(self):
        wav_names = sorted(p.stem for p in styles.SOUNDS_DIR.glob("*.wav"))
        current = self._settings.value("notification_sound", "toXo_default")

        self._sound_combo.blockSignals(True)
        self._sound_combo.clear()
        for name in wav_names:
            self._sound_combo.addItem(name)
        idx = self._sound_combo.findText(current)
        if idx < 0:
            idx = self._sound_combo.findText("toXo_default")
        if idx < 0 and self._sound_combo.count() > 0:
            idx = 0
        if idx >= 0:
            self._sound_combo.setCurrentIndex(idx)
        self._sound_combo.blockSignals(False)

    def _on_sound_selected(self, sound_key: str):
        if not sound_key:
            return
        self._settings.setValue("notification_sound", sound_key)
        self._preview_sound(sound_key)

    def _preview_sound(self, sound_key: str):
        try:
            import winsound
            sound_path = styles.SOUNDS_DIR / f"{sound_key}.wav"
            if sound_path.exists():
                winsound.PlaySound(
                    str(sound_path),
                    winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
                )
        except Exception:
            pass

    def _on_confirm_del_toggled(self, checked: bool):
        self._confirm_delete = checked
        self._settings.setValue("confirm_delete", checked)

    def _on_archive_days_changed(self, days: int):
        self._archive_auto_days = days
        self._settings.setValue("archive_auto_days", days)

    @staticmethod
    def _apply_dark_titlebar(window, dark: bool = True) -> None:
        """Apply DWM titlebar/border colour. dark=True → dark theme, dark=False → light."""
        try:
            import ctypes
            hwnd = int(window.winId())
            dwm = ctypes.windll.dwmapi

            mode = ctypes.c_int(1 if dark else 0)
            for attr in (20, 19):
                try:
                    dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(mode), ctypes.sizeof(mode))
                except Exception:
                    pass

            # COLORREF = 0x00BBGGRR
            # dark  #0d0d0f → 0x000F0D0D
            # light #F3F6FB → 0x00FBF6F3
            color = ctypes.c_uint32(0x000F0D0D if dark else 0x00FBF6F3)
            DWMWA_BORDER_COLOR = 34
            DWMWA_CAPTION_COLOR = 35
            for attr in (DWMWA_CAPTION_COLOR, DWMWA_BORDER_COLOR):
                try:
                    dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(color), ctypes.sizeof(color))
                except Exception:
                    pass
        except Exception:
            pass

    def _apply_themed_titlebar(self, window) -> None:
        """Apply titlebar colour matching the current active theme."""
        self._apply_dark_titlebar(window, dark=(styles.current_theme() != "light"))

    def _get_settings_dialog(self) -> _GlassSettingsDlg:
        if not hasattr(self, "_settings_dlg") or self._settings_dlg is None:
            dlg = _GlassSettingsDlg(self)

            from PyQt6.QtWidgets import QVBoxLayout as _VL, QScrollArea as _SA
            vl = _VL(dlg)
            vl.setContentsMargins(10, 10, 10, 10)
            vl.setSpacing(0)

            # ── Title bar ──
            title_bar = _DragTitleBar(tr("settings.title"), dlg)
            title_bar.btn_close.clicked.connect(dlg.hide)
            title_bar.setStyleSheet("background: transparent;")
            vl.addWidget(title_bar)

            # ── Scroll area ──
            scroll = _SA()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setStyleSheet(
                "QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget"
                " { background: transparent; }"
            )
            settings_page = self._build_settings_page()
            # remove the in-page title label (it's now in the custom title bar)
            if hasattr(self, "_settings_title_lbl"):
                self._settings_title_lbl.setParent(None)
            settings_page.layout().setContentsMargins(20, 8, 20, 24)
            settings_page.setStyleSheet("background: transparent;")
            scroll.setWidget(settings_page)
            vl.addWidget(scroll)

            # store ref for retranslate
            dlg._title_bar = title_bar
            self._settings_dlg = dlg
        return self._settings_dlg

    def toggle_settings(self):
        dlg = self._get_settings_dialog()
        if dlg.isVisible():
            dlg.raise_()
            dlg.activateWindow()
            return
        self._refresh_settings_page()
        geo = self.geometry()
        dlg.move(
            geo.center().x() - dlg.width() // 2,
            geo.center().y() - dlg.height() // 2,
        )
        dlg.show()

    def on_set_language(self, lang: str):
        set_language(lang)
        self._settings.setValue("language", lang)
        self.retranslate()
        self._refresh_settings_page()

    def retranslate(self):
        self.search.setPlaceholderText(tr("toolbar.search"))
        self.quick_add.setPlaceholderText(tr("toolbar.quick_add_ph"))
        self.btn_new.setToolTip(tr("toolbar.new_tooltip"))
        self.btn_hamburger.setToolTip(tr("toolbar.menu"))
        self.btn_delete.setText(tr("toolbar.delete"))
        self.btn_delete.setToolTip(tr("toolbar.delete_tooltip"))

        self.empty_hint.setText(tr("editor.empty_hint"))
        self.editor_desc.setPlaceholderText(tr("editor.desc_ph"))
        self.btn_reminder.setToolTip(tr("editor.reminder_tip"))
        self.btn_deadline.setToolTip(tr("editor.deadline_tip"))
        self.btn_task_menu.setToolTip(tr("editor.task_menu_tip"))
        if hasattr(self, "lbl_priority_label"):
            self.lbl_priority_label.setText(tr("editor.priority_label"))
        if hasattr(self, "lbl_recurrence_label"):
            self.lbl_recurrence_label.setText(tr("editor.recurrence_label"))
        self.btn_pri_none.setText(tr("editor.pri_none"))
        self.btn_pri_low.setText(tr("editor.pri_low"))
        self.btn_pri_med.setText(tr("editor.pri_med"))
        self.btn_pri_high.setText(tr("editor.pri_high"))
        self.btn_pin.setToolTip(tr("editor.pin_tip"))
        if not self.btn_pin.isChecked():
            self.btn_pin.setText(tr("editor.pin_btn"))
        else:
            self.btn_pin.setText(tr("editor.pinned_btn"))
        self.subtask_input.setPlaceholderText(tr("editor.subtask_add_ph"))
        self.lbl_subtasks.setText(tr("editor.subtasks_title"))
        if self.current_task_id is not None:
            t = self.svc.get_task(self.current_task_id)
            if t:
                self._update_reminder_label(t)
                self._update_deadline_label(t)
        else:
            self.btn_reminder.setText(tr("editor.reminder_btn"))
            self.btn_deadline.setText(tr("editor.deadline_btn"))
        if hasattr(self, "lbl_tags_label"):
            self.lbl_tags_label.setText(tr("editor.tags_label") + ":")
        if hasattr(self, "tags_input"):
            self.tags_input.setPlaceholderText(tr("editor.tag_add_ph"))
        self.rec_combo.blockSignals(True)
        cur_rec = self.rec_combo.currentData()
        self.rec_combo.clear()
        self.rec_combo.addItem(tr("editor.rec_none"),    None)
        self.rec_combo.addItem(tr("editor.rec_daily"),   "daily")
        self.rec_combo.addItem(tr("editor.rec_weekly"),  "weekly")
        self.rec_combo.addItem(tr("editor.rec_monthly"), "monthly")
        rec_idx = {"daily": 1, "weekly": 2, "monthly": 3}.get(cur_rec or "", 0)
        self.rec_combo.setCurrentIndex(rec_idx)
        self.rec_combo.blockSignals(False)

        self.btn_bulk_done.setText(tr("bulk.done"))
        self.btn_bulk_undone.setText(tr("bulk.undone"))
        self.btn_bulk_move.setText(tr("bulk.move"))
        self.btn_bulk_delete.setText(tr("bulk.delete"))

        self.analytics_page.retranslate()

        if hasattr(self, "calendar_page"):
            self.calendar_page.retranslate()

        if hasattr(self, "finance_page"):
            self.finance_page.retranslate()

        if hasattr(self, "_settings_dlg") and self._settings_dlg is not None:
            self._settings_dlg.setWindowTitle(tr("settings.title"))
            if hasattr(self._settings_dlg, "_title_bar"):
                self._settings_dlg._title_bar._lbl.setText(tr("settings.title"))

        if hasattr(self, "_settings_title_lbl"):
            self._settings_title_lbl.setText(tr("settings.title"))
            self._settings_lang_lbl.setText(tr("settings.lang_section").upper())
            if hasattr(self, "_settings_zoom_lbl"):
                self._settings_zoom_lbl.setText(tr("settings.zoom_section").upper())
            self._settings_general_lbl.setText(tr("settings.general").upper())
            self._settings_startup_lbl.setText(tr("settings.startup").upper())
            self._settings_sound_lbl.setText(tr("settings.sound_section").upper())
            self._cb_confirm_del.setText(tr("settings.confirm_del"))
            self._cb_autostart.setText(tr("settings.autostart"))
        if hasattr(self, "_settings_archive_lbl"):
            self._settings_archive_lbl.setText(tr("settings.archive").upper())
        if hasattr(self, "_lbl_archive_days"):
            self._lbl_archive_days.setText(tr("settings.archive_days_lbl"))
        if hasattr(self, "_btn_clear_archive"):
            self._btn_clear_archive.setText(tr("archive.clear_all"))
        if hasattr(self, "_settings_export_lbl"):
            self._settings_export_lbl.setText(tr("export.title").upper())
            self._btn_export_csv.setText(tr("export.csv"))
            self._btn_export_json.setText(tr("export.json"))
        if hasattr(self, "_settings_import_lbl"):
            self._settings_import_lbl.setText(tr("settings.import_section").upper())
            self._btn_import_csv.setText(tr("import.csv"))
            self._btn_import_json.setText(tr("import.json"))
        if hasattr(self, "_settings_theme_lbl"):
            self._settings_theme_lbl.setText(tr("settings.theme_section").upper())
            self._btn_theme_dark.setText(tr("settings.theme_dark"))
            self._btn_theme_light.setText(tr("settings.theme_light"))
            self._btn_theme_glass.setText(tr("settings.theme_glass"))
        if hasattr(self, "_settings_danger_lbl"):
            self._settings_danger_lbl.setText(tr("settings.danger_zone").upper())
            self._btn_clear_all_data.setText(tr("settings.clear_all_data"))
            self._btn_strip_formatting.setText(tr("settings.strip_all_formatting"))
            self._btn_strip_formatting.setToolTip(tr("settings.strip_all_formatting_tip"))
            self._btn_seed_mock.setText(tr("settings.seed_mock_data"))
            self._btn_seed_mock.setToolTip(tr("settings.seed_mock_data_tip"))
        if hasattr(self, "_settings_tutorial_lbl"):
            self._settings_tutorial_lbl.setText(tr("settings.tutorial").upper())
            self._btn_tutorial.setText(tr("settings.tutorial"))
            self._btn_tutorial.setToolTip(tr("settings.tutorial_tip"))

        current_data = self.sort_combo.currentData()
        self.sort_combo.blockSignals(True)
        self.sort_combo.clear()
        self.sort_combo.addItem(tr("sort.new"), self.SORT_NEW)
        self.sort_combo.addItem(tr("sort.old"), self.SORT_OLD)
        self.sort_combo.addItem(tr("sort.alpha"), self.SORT_ALPHA)
        self.sort_combo.addItem(tr("sort.undone"), self.SORT_UNDONE_FIRST)
        self.sort_combo.addItem(tr("sort.manual"), self.SORT_MANUAL)
        idx = self.sort_combo.findData(current_data)
        if idx >= 0:
            self.sort_combo.setCurrentIndex(idx)
        self.sort_combo.blockSignals(False)

        if hasattr(self, "_tray_action_show"):
            self._tray_action_show.setText(tr("tray.open"))
            self._tray_action_settings.setText(tr("tray.settings"))
            self._tray_action_quit.setText(tr("tray.quit"))

        self.refresh_categories()
        self.apply_filter(keep_selection=True)

    # ── Tutorial ──────────────────────────────────────────

    def _tutorial_steps(self) -> list[dict]:
        return [
            {"title": tr("tutorial.s1_title"), "body": tr("tutorial.s1_body"),  "widget": None},
            {"title": tr("tutorial.s2_title"), "body": tr("tutorial.s2_body"),  "widget": self.btn_new},
            {"title": tr("tutorial.s3_title"), "body": tr("tutorial.s3_body"),  "widget": self.search},
            {"title": tr("tutorial.s4_title"), "body": tr("tutorial.s4_body"),  "widget": self.controls_wrap},
            {"title": tr("tutorial.s5_title"), "body": tr("tutorial.s5_body"),  "widget": self.category_bar},
            {"title": tr("tutorial.s6_title"), "body": tr("tutorial.s6_body"),  "widget": self.list},
            {"title": tr("tutorial.s7_title"), "body": tr("tutorial.s7_body"),
             "on_enter": self._tutorial_enter_analytics},
            {"title": tr("tutorial.s8_title"), "body": tr("tutorial.s8_body"),
             "on_enter": self._tutorial_enter_calendar},
            {"title": tr("tutorial.s9_title"), "body": tr("tutorial.s9_body"),
             "on_enter": self._tutorial_enter_finance},
            {"title": tr("tutorial.s10_title"), "body": tr("tutorial.s10_body"),
             "on_enter": self._tutorial_enter_settings},
        ]

    def _tutorial_enter_analytics(self, overlay):
        from widgets.tutorial.ui import _MenuPreviewPanel
        if overlay._menu_panel is None:
            overlay._menu_panel = _MenuPreviewPanel(self.btn_hamburger, overlay)
            overlay._menu_panel.show()
        return overlay._menu_panel.analytics

    def _tutorial_enter_calendar(self, overlay):
        return overlay._menu_panel.calendar if overlay._menu_panel else None

    def _tutorial_enter_finance(self, overlay):
        return overlay._menu_panel.finance if overlay._menu_panel else None

    def _tutorial_enter_settings(self, overlay):
        return overlay._menu_panel.settings_ if overlay._menu_panel else None

    def _start_tutorial(self):
        from widgets.tutorial.ui import TutorialOverlay
        overlay = TutorialOverlay(self, self._tutorial_steps(), zoom=self.zoom_factor)
        overlay.done.connect(self._on_tutorial_done)
        overlay.show()

    def _on_tutorial_from_settings(self):
        if hasattr(self, "_settings_dlg") and self._settings_dlg is not None:
            self._settings_dlg.hide()
        self._start_tutorial()

    def _on_tutorial_done(self, dont_show: bool):
        if dont_show:
            self._settings.setValue("tutorial_shown", True)
