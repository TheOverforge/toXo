from __future__ import annotations

import shutil
from pathlib import Path as _Path

from PyQt6.QtWidgets import (
    QLineEdit, QTextEdit, QApplication, QLabel,
    QHBoxLayout, QVBoxLayout, QPushButton, QFrame, QColorDialog, QSizePolicy,
    QGraphicsDropShadowEffect, QDialog, QScrollArea, QWidget, QFileDialog,
)
from PyQt6.QtCore import (
    Qt, QBuffer, QByteArray, QUrl, QIODevice, QPoint, pyqtSignal, QTimer,
    QPropertyAnimation, QEasingCurve, QRect, QRectF, QEvent,
)
from PyQt6.QtGui import (
    QPainter, QImage, QTextImageFormat, QTextCursor, QPixmap, QTextDocument,
    QColor, QConicalGradient, QPen, QBrush, QLinearGradient, QPainterPath,
    QFont, QTextCharFormat, QRegion,
)


# =========================
# QTextDocument subclass that decodes data-URL images on load
# =========================
class _ImageTextDocument(QTextDocument):
    """Decodes ``data:image/…;base64,…`` URLs in loadResource so that
    images embedded via toHtml()/setHtml() round-trips display correctly."""

    def loadResource(self, resource_type, url):
        if resource_type == QTextDocument.ResourceType.ImageResource:
            name = url.toString()
            if name.startswith("data:image/") and "," in name:
                try:
                    ba = QByteArray.fromBase64(
                        name.split(",", 1)[1].encode("ascii")
                    )
                    img = QImage.fromData(ba)
                    if not img.isNull():
                        return img
                except Exception:
                    pass
        return super().loadResource(resource_type, url)


# =========================
# Text colour toolbar
# =========================
_PRESET_COLORS = [
    "#f5f5f7",  # white / default
    "#ff453a",  # red
    "#ff9f0a",  # orange
    "#ffd60a",  # yellow
    "#30d158",  # green
    "#0a84ff",  # blue
    "#bf5af2",  # purple
    "#ff375f",  # pink
]
_SW = 22  # swatch diameter


class _ColorSwatch(QPushButton):
    """Small circular colour button with optional active-highlight ring."""
    def __init__(self, color: str, size: int = _SW, parent=None):
        super().__init__(parent)
        self._color  = color
        self._size   = size
        self._active = False
        self.setFixedSize(size, size)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()

    def _apply_style(self):
        r = self._size // 2
        if self._active:
            self.setStyleSheet(
                f"QPushButton{{background:{self._color};border-radius:{r}px;"
                f"border:2.5px solid rgba(255,255,255,0.95);}}"
                f"QPushButton:hover{{border:2.5px solid white;}}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton{{background:{self._color};border-radius:{r}px;"
                f"border:1.5px solid rgba(255,255,255,0.18);}}"
                f"QPushButton:hover{{border:2px solid rgba(255,255,255,0.9);}}"
            )

    def set_active(self, active: bool):
        if self._active != active:
            self._active = active
            self._apply_style()


class _RainbowSwatch(QPushButton):
    """Conical-gradient circle — opens QColorDialog on click."""
    def __init__(self, size: int = _SW, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Custom colour…")
        self.setStyleSheet("background:transparent;border:none;")

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(2, 2, -2, -2)
        g = QConicalGradient(r.center().x(), r.center().y(), 0)
        for i in range(7):
            g.setColorAt(i / 6, QColor.fromHsv(i * 60, 230, 240))
        p.setBrush(QBrush(g))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(r)
        if self.underMouse():
            p.setPen(QPen(QColor(255, 255, 255, 200), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(r.adjusted(1, 1, -1, -1))
        p.end()


# ── Custom font infrastructure ────────────────────────────────────────────────
_CUSTOM_FONTS_DIR = _Path(__file__).parent.parent / "assets" / "fonts"
_BUILTIN_FONTS = ["Segoe UI", "Arial", "Georgia", "Courier New",
                  "Consolas", "Verdana", "Times New Roman"]


def load_custom_fonts() -> None:
    """Load all .ttf/.otf from _CUSTOM_FONTS_DIR into QFontDatabase. Call once at startup."""
    from PyQt6.QtGui import QFontDatabase
    from PyQt6.QtCore import QSettings
    _CUSTOM_FONTS_DIR.mkdir(parents=True, exist_ok=True)
    for fname in QSettings("todo_app", "todo_mvp").value("custom_font_files", [], type=list):
        p = _CUSTOM_FONTS_DIR / fname
        if p.exists():
            QFontDatabase.addApplicationFont(str(p))


def get_font_presets() -> list:
    """Return builtin + user-installed font family names."""
    from PyQt6.QtCore import QSettings
    custom = list(QSettings("todo_app", "todo_mvp").value("custom_fonts", [], type=list))
    return _BUILTIN_FONTS + [f for f in custom if f not in _BUILTIN_FONTS]


class CustomFontDialog(QDialog):
    """Small modal for adding / removing custom fonts (.ttf / .otf)."""

    fonts_changed = pyqtSignal()

    def __init__(self, parent=None):
        from shared.i18n import tr as _tr
        super().__init__(parent or QApplication.activeWindow())
        self.setWindowTitle(_tr("font.dlg_title"))
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)
        self.setModal(True)

        try:
            from app.styles.themes import current_theme as _ct
            self._theme = _ct()
        except Exception:
            self._theme = "dark"

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(18, 18, 18, 14)

        title = QLabel(_tr("font.dlg_title"))
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
        root.addWidget(title)

        _hint_clr = "rgba(60,70,90,0.72)" if self._theme == "light" else "rgba(200,200,210,0.72)"
        hint = QLabel(_tr("font.dlg_hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet(f"font-size: 12px; color: {_hint_clr};")
        root.addWidget(hint)

        # ── scroll list ──────────────────────────────────────────────────
        self._inner = QFrame()
        self._inner.setObjectName("CustomFontList")
        self._vbox = QVBoxLayout(self._inner)
        self._vbox.setContentsMargins(0, 4, 0, 4)
        self._vbox.setSpacing(2)
        self._vbox.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self._inner)
        scroll.setMinimumHeight(140)
        root.addWidget(scroll)

        # ── bottom buttons ────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_add = QPushButton(_tr("font.dlg_add"))
        btn_add.setObjectName("FilterBtn")
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.clicked.connect(self._add_font)
        btn_row.addWidget(btn_add)
        btn_row.addStretch()
        btn_close = QPushButton(_tr("font.dlg_close"))
        btn_close.setObjectName("FilterBtn")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        root.addLayout(btn_row)

        self._rebuild()

    def _rebuild(self):
        while self._vbox.count() > 1:
            item = self._vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        from PyQt6.QtCore import QSettings
        from shared.i18n import tr as _tr
        families = list(QSettings("todo_app", "todo_mvp").value("custom_fonts", [], type=list))
        if not families:
            lbl = QLabel(_tr("font.dlg_empty"))
            lbl.setStyleSheet("font-size: 12px; padding: 4px 0;")
            self._vbox.insertWidget(0, lbl)
            return

        _is_light = self._theme == "light"
        _name_clr = "rgba(26,31,46,0.90)" if _is_light else "white"
        _sec_clr = "rgba(26,31,46,0.55)" if _is_light else "rgba(255,255,255,0.60)"

        for fam in families:
            row = QFrame()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(4, 3, 4, 3)
            name_lbl = QLabel(fam)
            name_lbl.setStyleSheet(f"color: {_name_clr}; font-size: 13px;")
            rl.addWidget(name_lbl)
            rl.addStretch()
            sample = QLabel("Aa Bb 123")
            sample.setFont(QFont(fam, 11))
            sample.setStyleSheet(f"color: {_sec_clr}; font-size: 11px;")
            rl.addWidget(sample)
            btn_del = QPushButton("×")
            btn_del.setFixedSize(22, 22)
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.setToolTip(_tr("font.dlg_remove_tip", name=fam))
            btn_del.clicked.connect(lambda _, f=fam: self._remove_font(f))
            rl.addWidget(btn_del)
            self._vbox.insertWidget(self._vbox.count() - 1, row)

    def _add_font(self):
        from PyQt6.QtGui import QFontDatabase
        from PyQt6.QtCore import QSettings
        import json
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select font files", "", "Font files (*.ttf *.otf)"
        )
        if not paths:
            return
        _CUSTOM_FONTS_DIR.mkdir(parents=True, exist_ok=True)
        settings = QSettings("todo_app", "todo_mvp")
        families = list(settings.value("custom_fonts", [], type=list))
        files = list(settings.value("custom_font_files", [], type=list))
        font_map = json.loads(settings.value("custom_font_map", "{}", type=str))
        failed = []
        for src in paths:
            fname = _Path(src).name
            dst = _CUSTOM_FONTS_DIR / fname
            try:
                shutil.copy2(src, dst)
            except Exception as e:
                failed.append(f"{fname}: {e}")
                continue
            font_id = QFontDatabase.addApplicationFont(str(dst))
            if font_id >= 0:
                for f in QFontDatabase.applicationFontFamilies(font_id):
                    if f not in families:
                        families.append(f)
                    font_map[f] = fname   # family → filename
                if fname not in files:
                    files.append(fname)
            else:
                failed.append(f"{fname}: Qt could not read this font file")
                try:
                    dst.unlink(missing_ok=True)
                except Exception:
                    pass
        settings.setValue("custom_fonts", families)
        settings.setValue("custom_font_files", files)
        settings.setValue("custom_font_map", json.dumps(font_map))
        self._rebuild()
        self.fonts_changed.emit()
        if failed:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Some fonts failed to load",
                                "\n".join(failed))

    def _remove_font(self, family: str):
        from PyQt6.QtCore import QSettings
        import json
        settings = QSettings("todo_app", "todo_mvp")
        families = list(settings.value("custom_fonts", [], type=list))
        files = list(settings.value("custom_font_files", [], type=list))
        font_map = json.loads(settings.value("custom_font_map", "{}", type=str))
        if family in families:
            families.remove(family)
        # Look up file via stored map (no addApplicationFont side-effect)
        fname = font_map.pop(family, None)
        if fname:
            if fname in files:
                files.remove(fname)
            try:
                (_CUSTOM_FONTS_DIR / fname).unlink(missing_ok=True)
            except Exception:
                pass
        settings.setValue("custom_fonts", families)
        settings.setValue("custom_font_files", files)
        settings.setValue("custom_font_map", json.dumps(font_map))
        self._rebuild()
        self.fonts_changed.emit()


_FONT_PRESETS = _BUILTIN_FONTS  # legacy alias

class _SizeBtn(QPushButton):
    """Circle button for font size +/−."""
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFixedSize(_SW, _SW)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QPushButton{background:rgba(255,255,255,0.12);border-radius:11px;"
            "border:1px solid rgba(255,255,255,0.20);color:white;"
            "font-size:15px;font-weight:700;padding:0;}"
            "QPushButton:hover{background:rgba(255,255,255,0.24);"
            "border-color:rgba(255,255,255,0.55);}"
            "QPushButton:pressed{background:rgba(255,255,255,0.35);}"
        )


class _FontDropBtn(QPushButton):
    """'A ▾' button — opens the floating font picker panel."""
    def __init__(self, parent=None):
        super().__init__("A  ▾", parent)
        self.setFixedHeight(_SW)
        self.setMinimumWidth(42)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"QPushButton{{background:rgba(255,255,255,0.10);border-radius:{_SW//2}px;"
            "border:1px solid rgba(255,255,255,0.18);color:rgba(255,255,255,0.85);"
            "font-size:11px;font-weight:700;padding:0 7px;}}"
            "QPushButton:hover{background:rgba(255,255,255,0.24);"
            "border-color:rgba(255,255,255,0.55);}"
            "QPushButton:pressed{background:rgba(255,255,255,0.32);}"
        )


class _FontPickerPanel(QFrame):
    """Floating panel with font name rows, shown below _FontDropBtn."""
    font_chosen = pyqtSignal(str)

    _DARK_BG   = (10,  14,  24,  210)   # near-black, semi-transparent
    _DARK_BOR  = (255, 255, 255, 26)
    _GLASS_BG  = (10,  14,  24,  210)   # same for glass (matches dark popup style)
    _GLASS_BOR = (255, 255, 255, 26)
    _LIGHT_BG  = (250, 252, 255, 230)
    _LIGHT_BOR = (0,   0,   0,   22)

    def __init__(self, parent=None):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._theme = "dark"
        self._btns: list[QPushButton] = []
        self._source_btn: "QPushButton | None" = None
        self._anim: "QPropertyAnimation | None" = None

        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(6, 6, 6, 6)
        self._lay.setSpacing(2)

        self._build_font_rows()
        self._apply_btn_css()

    def _build_font_rows(self):
        """(Re)populate font rows + "+" button from current presets."""
        # Clear existing rows (leave layout intact)
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._btns.clear()

        for fam in get_font_presets():
            btn = QPushButton(fam)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFont(QFont(fam, 10))
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda _, f=fam: self.font_chosen.emit(f))
            self._lay.addWidget(btn)
            self._btns.append(btn)

        # ── separator ──────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        _sep_clr = "rgba(0,0,0,0.12)" if self._theme == "light" else "rgba(255,255,255,0.12)"
        sep.setStyleSheet(f"background: {_sep_clr}; border: none;")
        self._lay.addWidget(sep)

        # ── "+" add custom font ────────────────────────────────────────
        btn_add = QPushButton("＋  Add custom font…")
        btn_add.setObjectName("FontPickerAdd")
        btn_add.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setFixedHeight(28)
        btn_add.clicked.connect(self._open_custom_font_dialog)
        self._lay.addWidget(btn_add)

    def refresh_fonts(self):
        """Rebuild font list (call after custom fonts change)."""
        self._build_font_rows()
        self._apply_btn_css()
        self.adjustSize()
        self._update_mask()

    def _open_custom_font_dialog(self):
        self.hide()
        dlg = CustomFontDialog()
        dlg.fonts_changed.connect(self.refresh_fonts)
        dlg.exec()

    def _apply_btn_css(self):
        if self._theme == "light":
            css = (
                "QPushButton{background:transparent;border:none;"
                "color:rgba(26,31,46,0.88);text-align:left;padding:0 8px;"
                "border-radius:6px;}"
                "QPushButton:hover{background:rgba(59,130,246,0.10);}"
                "QPushButton:pressed{background:rgba(59,130,246,0.18);}"
            )
        elif self._theme == "glass":
            css = (
                "QPushButton{background:transparent;border:none;"
                "color:rgba(255,255,255,0.88);text-align:left;padding:0 8px;"
                "border-radius:6px;}"
                "QPushButton:hover{background:rgba(86,126,225,0.22);}"
                "QPushButton:pressed{background:rgba(94,162,255,0.32);}"
            )
        else:
            css = (
                "QPushButton{background:transparent;border:none;"
                "color:rgba(255,255,255,0.85);text-align:left;padding:0 8px;"
                "border-radius:6px;}"
                "QPushButton:hover{background:rgba(255,255,255,0.15);}"
                "QPushButton:pressed{background:rgba(255,255,255,0.25);}"
            )
        for btn in self._btns:
            btn.setStyleSheet(css)
        # "+" button inherits font-row style but accent-coloured text
        add_clr = "rgba(59,130,246,0.90)" if self._theme == "light" else "rgba(100,160,255,0.90)"
        add_css = css.replace(
            "color:rgba(26,31,46,0.88)" if self._theme == "light" else
            ("color:rgba(255,255,255,0.88)" if self._theme == "glass" else "color:rgba(255,255,255,0.85)"),
            f"color:{add_clr}",
        )
        add_btn = self.findChild(QPushButton, "FontPickerAdd")
        if add_btn:
            add_btn.setStyleSheet(add_css)

    def apply_theme(self, theme: str):
        self._theme = theme
        self._apply_btn_css()
        self.update()

    def _update_mask(self):
        """Clip window to rounded rect via OS mask — reliable on all Windows versions."""
        from PyQt6.QtGui import QPainterPath, QTransform
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 12.0, 12.0)
        self.setMask(QRegion(path.toFillPolygon(QTransform()).toPolygon()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_mask()

    def show_animated(self, x: int, y: int, source_btn=None):
        """Slide-down reveal via maximumHeight animation."""
        self._source_btn = source_btn
        full_h = self.sizeHint().height()
        if full_h <= 0:
            full_h = 220
        self.setMaximumHeight(16777215)
        self.resize(self.sizeHint().width(), full_h)
        self.move(x, y)
        self.setMaximumHeight(0)
        self.show()
        self.move(x, y)
        self.raise_()
        self._anim = QPropertyAnimation(self, b"maximumHeight", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.setStartValue(0)
        self._anim.setEndValue(full_h)
        self._anim.finished.connect(lambda: self.setMaximumHeight(16777215))
        self._anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        QApplication.instance().installEventFilter(self)

    def hide(self):
        QApplication.instance().removeEventFilter(self)
        super().hide()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            pos = event.globalPosition().toPoint()
            if not self.geometry().contains(pos):
                # If click is on the source button, let its clicked handler toggle
                if self._source_btn is not None:
                    btn_rect = QRect(
                        self._source_btn.mapToGlobal(QPoint(0, 0)),
                        self._source_btn.size(),
                    )
                    if btn_rect.contains(pos):
                        return False
                self.hide()
        return False

    def paintEvent(self, _):
        if self._theme == "light":
            bg, bor = self._LIGHT_BG, self._LIGHT_BOR
        elif self._theme == "glass":
            bg, bor = self._GLASS_BG, self._GLASS_BOR
        else:
            bg, bor = self._DARK_BG, self._DARK_BOR
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        p.setBrush(QBrush(QColor(*bg)))
        p.setPen(QPen(QColor(*bor), 1.0))
        p.drawRoundedRect(r, 12, 12)
        p.end()


class TextColorBar(QFrame):
    """Floating mini-toolbar for inline text colour picking.

    Appears above the active text selection.  Star button shows a popup of
    recently used colours (auto-tracked; no manual adding needed).
    """

    def __init__(self, editor: "FocusSaveTextEdit"):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("TextColorBar")
        self._editor     = editor
        self._last_color = "#f5f5f7"
        self._theme      = "dark"
        self._anim: "QPropertyAnimation | None" = None

        h = QHBoxLayout(self)
        h.setContentsMargins(10, 7, 10, 7)
        h.setSpacing(5)

        for color in _PRESET_COLORS:
            sw = _ColorSwatch(color, _SW, self)
            sw.clicked.connect(lambda _, c=color: self._apply(c))
            h.addWidget(sw)

        rain = _RainbowSwatch(_SW, self)
        rain.clicked.connect(self._pick_custom)
        h.addWidget(rain)

        # ── separator ──────────────────────────────────────────────────────
        self._sep1 = QFrame()
        self._sep1.setFixedSize(1, 16)
        h.addWidget(self._sep1)

        # ── size controls ──────────────────────────────────────────────────
        self._btn_sm = _SizeBtn("−")
        self._btn_sm.clicked.connect(lambda: self._change_size(-1))
        h.addWidget(self._btn_sm)

        self._size_lbl = QLabel("13")
        self._size_lbl.setFixedWidth(20)
        self._size_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(self._size_lbl)

        self._btn_lg = _SizeBtn("+")
        self._btn_lg.clicked.connect(lambda: self._change_size(+1))
        h.addWidget(self._btn_lg)

        # ── separator ──────────────────────────────────────────────────────
        self._sep2 = QFrame()
        self._sep2.setFixedSize(1, 16)
        h.addWidget(self._sep2)

        # ── font picker dropdown ────────────────────────────────────────────
        self._font_drop_btn = _FontDropBtn(self)
        self._font_drop_btn.clicked.connect(self._toggle_font_panel)
        h.addWidget(self._font_drop_btn)

        self._font_panel = _FontPickerPanel()
        self._font_panel.font_chosen.connect(self._on_font_chosen)

        # Apply default dark theme styling to separators / labels
        self.apply_theme("dark")

    # ── theme ─────────────────────────────────────────────────────────────

    def apply_theme(self, theme: str):
        self._theme = theme
        self._font_panel.apply_theme(theme)
        is_light = theme == "light"
        is_glass = theme == "glass"
        sep_bg  = "rgba(0,0,0,0.15)"    if is_light else "rgba(148,202,255,0.25)" if is_glass else "rgba(255,255,255,0.22)"
        lbl_clr = "rgba(26,31,46,0.75)" if is_light else "rgba(255,255,255,0.85)"

        # ── size +/− buttons ──────────────────────────────────────────────
        btn_css_base = (
            "QPushButton{{background:{bg};border-radius:11px;"
            "border:1px solid {bor};color:{clr};"
            "font-size:15px;font-weight:700;padding:0;}}"
            "QPushButton:hover{{background:{hov};border-color:{hov_bor};}}"
            "QPushButton:pressed{{background:{pr};}}"
        )
        if is_light:
            btn_css = btn_css_base.format(
                bg="rgba(0,0,0,0.07)", bor="rgba(0,0,0,0.14)", clr="rgba(26,31,46,0.8)",
                hov="rgba(59,130,246,0.15)", hov_bor="rgba(59,130,246,0.45)",
                pr="rgba(59,130,246,0.25)",
            )
        elif is_glass:
            btn_css = btn_css_base.format(
                bg="qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(65,105,202,0.18),stop:1 rgba(28,56,145,0.09))",
                bor="rgba(148,202,255,0.36)", clr="white",
                hov="qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(86,126,225,0.26),stop:1 rgba(42,78,172,0.14))",
                hov_bor="rgba(148,202,255,0.65)",
                pr="qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(94,162,255,0.40),stop:1 rgba(94,162,255,0.22))",
            )
        else:
            btn_css = btn_css_base.format(
                bg="rgba(255,255,255,0.12)", bor="rgba(255,255,255,0.20)", clr="white",
                hov="rgba(255,255,255,0.24)", hov_bor="rgba(255,255,255,0.55)",
                pr="rgba(255,255,255,0.35)",
            )

        # ── A▾ drop button ────────────────────────────────────────────────
        drop_css_base = (
            "QPushButton{{background:{bg};border-radius:11px;"
            "border:1px solid {bor};color:{clr};"
            "font-size:11px;font-weight:700;padding:0 7px;}}"
            "QPushButton:hover{{background:{hov};border-color:{hov_bor};}}"
            "QPushButton:pressed{{background:{pr};}}"
        )
        if is_light:
            drop_css = drop_css_base.format(
                bg="rgba(0,0,0,0.07)", bor="rgba(0,0,0,0.14)", clr="rgba(26,31,46,0.8)",
                hov="rgba(59,130,246,0.15)", hov_bor="rgba(59,130,246,0.45)",
                pr="rgba(59,130,246,0.25)",
            )
        elif is_glass:
            drop_css = drop_css_base.format(
                bg="qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(65,105,202,0.18),stop:1 rgba(28,56,145,0.09))",
                bor="rgba(148,202,255,0.36)", clr="rgba(255,255,255,0.90)",
                hov="qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(86,126,225,0.26),stop:1 rgba(42,78,172,0.14))",
                hov_bor="rgba(148,202,255,0.65)",
                pr="qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(94,162,255,0.40),stop:1 rgba(94,162,255,0.22))",
            )
        else:
            drop_css = drop_css_base.format(
                bg="rgba(255,255,255,0.10)", bor="rgba(255,255,255,0.18)",
                clr="rgba(255,255,255,0.85)",
                hov="rgba(255,255,255,0.24)", hov_bor="rgba(255,255,255,0.55)",
                pr="rgba(255,255,255,0.32)",
            )
        self._sep1.setStyleSheet(f"background:{sep_bg};")
        self._sep2.setStyleSheet(f"background:{sep_bg};")
        self._size_lbl.setStyleSheet(
            f"color:{lbl_clr};font-size:11px;background:transparent;"
        )
        self._btn_sm.setStyleSheet(btn_css)
        self._btn_lg.setStyleSheet(btn_css)
        self._font_drop_btn.setStyleSheet(drop_css)
        self.update()

    # ── font / size application ───────────────────────────────────────────

    def _change_size(self, delta: int):
        size = max(8, min(48, int(self._size_lbl.text()) + delta))
        self._size_lbl.setText(str(size))
        cursor = self._editor.textCursor()
        if cursor.hasSelection():
            fmt = QTextCharFormat()
            fmt.setFontPointSize(float(size))
            cursor.mergeCharFormat(fmt)
            self._editor.setTextCursor(cursor)

    def _toggle_font_panel(self):
        if self._font_panel.isVisible():
            self._font_panel.hide()
            return
        from PyQt6.QtGui import QCursor
        sh = self._font_panel.sizeHint()
        pw, ph = max(sh.width(), 160), max(sh.height(), 80)
        cp = QCursor.pos()          # exact screen pos of mouse at click moment
        x = cp.x() - pw // 2       # center panel on click X
        y = cp.y() + 26             # below the button (button ~28px, cursor near top)
        if self.screen():
            sg = self.screen().availableGeometry()
            x = max(sg.left() + 4, min(x, sg.right() - pw - 4))
            if y + ph > sg.bottom() - 4:
                y = cp.y() - ph - 4
        self._font_panel.show_animated(x, y, source_btn=self._font_drop_btn)

    def _on_font_chosen(self, family: str):
        self._font_panel.hide()
        cursor = self._editor.textCursor()
        if cursor.hasSelection():
            fmt = QTextCharFormat()
            fmt.setFontFamily(family)
            cursor.mergeCharFormat(fmt)
            self._editor.setTextCursor(cursor)

    def hideEvent(self, event):
        self._font_panel.hide()
        super().hideEvent(event)

    # ── colour application ────────────────────────────────────────────────

    def _apply(self, color: str):
        self._last_color = color
        cursor = self._editor.textCursor()
        if cursor.hasSelection():
            fmt = cursor.charFormat()
            fmt.setForeground(QColor(color))
            cursor.mergeCharFormat(fmt)
            vbar   = self._editor.verticalScrollBar()
            scroll = vbar.value()
            self._editor.setTextCursor(cursor)
            vbar.setValue(scroll)

    def _pick_custom(self):
        vbar   = self._editor.verticalScrollBar()
        scroll = vbar.value()
        color  = QColorDialog.getColor(QColor(self._last_color), self._editor, "Pick colour")
        vbar.setValue(scroll)
        if color.isValid():
            self._apply(color.name())

    # ── background painting ───────────────────────────────────────────────
    # WA_TranslucentBackground bypasses CSS on Windows, so we draw manually.

    def paintEvent(self, _):
        if self._theme == "light":
            bg  = QColor(250, 252, 255, 230)
            bor = QColor(0, 0, 0, 22)
        else:
            bg  = QColor(10, 14, 24, 210)
            bor = QColor(255, 255, 255, 26)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        radius = r.height() / 2
        p.setBrush(QBrush(bg))
        p.setPen(QPen(bor, 1.0))
        p.drawRoundedRect(r, radius, radius)
        p.end()

    # ── positioning ───────────────────────────────────────────────────────

    def reposition(self):
        ed = self._editor
        cursor = ed.textCursor()
        if not cursor.hasSelection():
            self.hide()
            return
        # Sync size label with the font size at selection start
        sz = int(cursor.charFormat().fontPointSize())
        if sz > 0:
            self._size_lbl.setText(str(sz))
        self.adjustSize()
        bw, bh = self.width(), self.height()
        sel_c = QTextCursor(ed.document())
        sel_c.setPosition(cursor.selectionStart())
        rect  = ed.cursorRect(sel_c)
        gp    = ed.viewport().mapToGlobal(rect.topLeft())
        x = gp.x() - bw // 2
        y = gp.y() - bh - 8
        if ed.screen():
            sg = ed.screen().availableGeometry()
            x  = max(sg.left() + 4, min(x, sg.right() - bw - 4))
            if y < sg.top() + 4:
                y = gp.y() + rect.height() + 8
        target = QRect(x, y, bw, bh)
        self._bar_target = target  # used by _toggle_font_panel for positioning
        if not self.isVisible():
            # Slide-in from center: starts as a zero-width sliver, expands outward
            self.setGeometry(QRect(x + bw // 2, y, 0, bh))
            self.show()
            self._anim = QPropertyAnimation(self, b"geometry", self)
            self._anim.setDuration(160)
            self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._anim.setStartValue(QRect(x + bw // 2, y, 0, bh))
            self._anim.setEndValue(target)
            self._anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        else:
            self.setGeometry(target)
        self.raise_()


# =========================
# Inline (embedded) colour toolbar
# =========================
_SW_INLINE = 20  # slightly smaller than the floating bar

class InlineColorBar(QFrame):
    """Persistent pill-shaped colour toolbar embedded above the description editor.

    • Applies colour to the current selection, or sets it as the typing colour.
    • Highlights the swatch that matches the cursor's current text colour.
    • Clock button opens a popup of recently used colours (auto-tracked).
    """

    def __init__(self, editor: "FocusSaveTextEdit", parent=None):
        super().__init__(parent)
        self.setObjectName("InlineColorBar")
        self._editor     = editor
        self._last_color = "#f5f5f7"
        self._preset_swatches: list[_ColorSwatch] = []

        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        h = QHBoxLayout(self)
        h.setContentsMargins(10, 5, 10, 5)
        h.setSpacing(5)

        for color in _PRESET_COLORS:
            sw = _ColorSwatch(color, _SW_INLINE, self)
            sw.clicked.connect(lambda _, c=color: self._apply(c))
            h.addWidget(sw)
            self._preset_swatches.append(sw)

        rain = _RainbowSwatch(_SW_INLINE, self)
        rain.clicked.connect(self._pick_custom)
        h.addWidget(rain)

        editor.cursorPositionChanged.connect(self._on_cursor_changed)
        editor.selectionChanged.connect(self._on_cursor_changed)

    # ── cursor tracking ───────────────────────────────────────────────

    def _on_cursor_changed(self):
        cursor = self._editor.textCursor()
        brush  = cursor.charFormat().foreground()
        active = (
            brush.color().name().lower()
            if brush.style() != Qt.BrushStyle.NoBrush
            else ""
        )
        for sw in self._preset_swatches:
            sw.set_active(sw._color.lower() == active)

    # ── colour application ────────────────────────────────────────────

    def _apply(self, color: str):
        self._last_color = color
        cursor = self._editor.textCursor()
        if not cursor.hasSelection():
            return
        fmt = cursor.charFormat()
        fmt.setForeground(QColor(color))
        vbar   = self._editor.verticalScrollBar()
        scroll = vbar.value()
        cursor.mergeCharFormat(fmt)
        self._editor.setTextCursor(cursor)
        vbar.setValue(scroll)
        self._editor.setFocus()
        for sw in self._preset_swatches:
            sw.set_active(sw._color.lower() == color.lower())

    def _pick_custom(self):
        vbar   = self._editor.verticalScrollBar()
        scroll = vbar.value()
        color  = QColorDialog.getColor(QColor(self._last_color), self._editor, "Pick colour")
        vbar.setValue(scroll)
        if color.isValid():
            self._apply(color.name())


# =========================
# Save-on-focus editors
# =========================
class FocusSaveLineEdit(QLineEdit):
    def __init__(self, on_focus_out, on_enter=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_focus_out = on_focus_out
        self._on_enter = on_enter

    def focusOutEvent(self, event):
        try:
            if callable(self._on_focus_out):
                self._on_focus_out()
        finally:
            super().focusOutEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if callable(self._on_enter):
                self._on_enter()
            event.accept()
            return
        super().keyPressEvent(event)


class FocusSaveTextEdit(QTextEdit):
    """QTextEdit with focus-out save callback and inline image support.

    Images can be pasted from the clipboard (Ctrl+V).  They are encoded as
    base64 PNG data-URLs and embedded directly in the document's HTML, so
    no external files are needed.  Drag an image within the editor to
    reposition it.
    """

    context_menu_requested = pyqtSignal(QPoint)  # global pos — opens command palette

    _MAX_IMG_W = 560  # pixels — images are scaled down if wider

    def __init__(self, on_focus_out, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_focus_out = on_focus_out
        # Custom document that can decode data-URL images on setHtml()
        self.setDocument(_ImageTextDocument(self))
        # Image drag state
        self._img_fmt: "QTextImageFormat | None" = None
        self._img_src_pos: int = -1
        self._img_press_pos: "QPoint | None" = None
        self._img_dragging: bool = False
        self._img_preview: "QLabel | None" = None
        # Text colour bar — appears above selection on mouse release
        self._color_bar = TextColorBar(self)
        self._sel_timer = QTimer(self)
        self._sel_timer.setSingleShot(True)
        self._sel_timer.setInterval(150)
        self._sel_timer.timeout.connect(self._update_color_bar)
        self.selectionChanged.connect(self._sel_timer.start)

    # ── Context menu → Command Palette ───────────────────────────────

    def contextMenuEvent(self, event):
        self.context_menu_requested.emit(event.globalPos())
        # Do NOT call super() — replaces the standard context menu entirely

    # ── Focus-out save ────────────────────────────────────────────────

    def focusOutEvent(self, event):
        # Delay hiding so that clicking color-bar buttons (which use
        # WindowDoesNotAcceptFocus) doesn't prematurely close the bar.
        # If focus genuinely moves to another widget, hasFocus() will be
        # False after the delay and the bar will hide.
        QTimer.singleShot(120, lambda: (
            self._color_bar.hide() if not self.hasFocus() else None
        ))
        try:
            if callable(self._on_focus_out):
                self._on_focus_out()
        finally:
            super().focusOutEvent(event)

    # ── Content helpers (HTML when rich formatting present, plain text otherwise) ──

    def get_content(self) -> str:
        html = self.toHtml()
        # Preserve HTML whenever Qt embedded any inline formatting:
        # <img> = images, <span = font/color/size overrides, <b>/<i>/<u> = bold/italic/underline
        if any(tag in html for tag in ("<img ", "<span ", "<b>", "<i>", "<u>", "<s>")):
            return html
        return self.toPlainText()

    def set_content(self, text: str) -> None:
        if text and "<!DOCTYPE" in text[:100]:
            self.setHtml(text)
        else:
            self.setPlainText(text)
        # Defer cursor reset so Qt finishes all internal signal handling from
        # setHtml/setPlainText before we move the cursor.  setTextCursor
        # triggers updateCurrentCharFormatIfChanged() inside Qt, which resets
        # lastCharFormat to the format at position 0 of this task's document
        # — preventing typing-format leak from the previous task.
        QTimer.singleShot(0, self._reset_typing_format)

    # ── Image paste (Ctrl+V / drag from outside) ─────────────────────

    def _reset_typing_format(self) -> None:
        """Reset Qt's internal 'lastCharFormat' (the typing format) to the
        document default — prevents font/colour from a previous task leaking
        into newly typed text in this one.

        setCurrentCharFormat *merges* the given format into lastCharFormat, so
        we must explicitly set the properties we want cleared (font → doc
        default; foreground → NoBrush = inherit from CSS/palette).
        """
        fmt = QTextCharFormat()
        fmt.setFont(self.document().defaultFont())
        fmt.setForeground(QBrush(Qt.BrushStyle.NoBrush))
        fmt.setBackground(QBrush(Qt.BrushStyle.NoBrush))
        self.setCurrentCharFormat(fmt)

    def insertFromMimeData(self, source):
        if source.hasImage():
            img = source.imageData()
            if isinstance(img, QImage) and not img.isNull():
                self._embed_image(img)
                return
        super().insertFromMimeData(source)

    def _embed_image(self, img: QImage) -> None:
        """Scale, encode as base64 PNG and insert at current cursor position."""
        if img.width() > self._MAX_IMG_W:
            img = img.scaledToWidth(
                self._MAX_IMG_W, Qt.TransformationMode.SmoothTransformation
            )
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        buf.close()
        b64 = bytes(ba.toBase64()).decode("ascii")
        data_url = f"data:image/png;base64,{b64}"
        # Register so the document can display it immediately
        self.document().addResource(
            QTextDocument.ResourceType.ImageResource, QUrl(data_url), img
        )
        fmt = QTextImageFormat()
        fmt.setName(data_url)
        fmt.setWidth(img.width())
        fmt.setHeight(img.height())
        self.textCursor().insertImage(fmt)

    # ── Image hit-testing ─────────────────────────────────────────────

    def _img_at(self, pos: QPoint):
        """Return ``(doc_pos, QTextImageFormat)`` for the image at screen *pos*,
        or ``(None, None)`` if no image is there."""
        c = self.cursorForPosition(pos)
        p = c.position()
        doc = self.document()
        for cp in (p, p - 1):
            if cp < 0:
                continue
            tc = QTextCursor(doc)
            tc.setPosition(cp)
            tc.movePosition(
                QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor
            )
            fmt = tc.charFormat()
            if fmt.isImageFormat():
                return cp, fmt.toImageFormat()
        return None, None

    def _pm_from_fmt(self, fmt: QTextImageFormat) -> QPixmap:
        """Decode a data-URL QTextImageFormat back to a QPixmap."""
        name = fmt.name()
        if "," in name:
            try:
                ba = QByteArray.fromBase64(
                    name.split(",", 1)[1].encode("ascii")
                )
                img = QImage.fromData(ba)
                if not img.isNull():
                    return QPixmap.fromImage(img)
            except Exception:
                pass
        return QPixmap(name)

    # ── Mouse events: drag-to-reposition ─────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            src_pos, fmt = self._img_at(pos)
            if fmt is not None:
                self._img_fmt = fmt
                self._img_src_pos = src_pos
                self._img_press_pos = pos
                self._img_dragging = False
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        if self._img_fmt is not None and event.buttons() & Qt.MouseButton.LeftButton:
            dist = (pos - self._img_press_pos).manhattanLength()
            if dist >= QApplication.startDragDistance():
                self._img_dragging = True
            if self._img_dragging:
                self._update_preview(pos)
                event.accept()
                return
        # Hover cursor — indicate that images are draggable
        if not event.buttons():
            _, fmt = self._img_at(pos)
            self.viewport().setCursor(
                Qt.CursorShape.SizeAllCursor if fmt else Qt.CursorShape.IBeamCursor
            )
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._img_fmt is not None:
            if self._img_dragging:
                self._finish_drag(event.position().toPoint())
            self._reset_drag()
            event.accept()
            return
        super().mouseReleaseEvent(event)
        # Show colour bar immediately on mouse-up (no 150 ms delay)
        if event.button() == Qt.MouseButton.LeftButton:
            self._sel_timer.stop()
            self._update_color_bar()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self._img_dragging:
            self._reset_drag()
            event.accept()
            return
        super().keyPressEvent(event)

    # ── Drag helpers ──────────────────────────────────────────────────

    def _update_preview(self, pos: QPoint) -> None:
        """Create or move the semi-transparent drag preview label."""
        if self._img_preview is None:
            pm = self._pm_from_fmt(self._img_fmt)
            if pm.isNull():
                return
            pm = pm.scaled(
                110, 110,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            # Apply 65 % opacity
            result = QPixmap(pm.size())
            result.fill(Qt.GlobalColor.transparent)
            p = QPainter(result)
            p.setOpacity(0.65)
            p.drawPixmap(0, 0, pm)
            p.end()
            lbl = QLabel(self)
            lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            lbl.setPixmap(result)
            lbl.setFixedSize(result.size())
            lbl.raise_()
            self._img_preview = lbl
            self._preview_half = QPoint(result.width() // 2, result.height() // 2)
        self._img_preview.move(pos - self._preview_half)
        self._img_preview.show()

    def _finish_drag(self, drop_pos: QPoint) -> None:
        """Remove image from source position and insert at drop position."""
        src = self._img_src_pos
        fmt = self._img_fmt
        if src < 0 or fmt is None:
            return
        doc = self.document()
        # Delete from source
        del_c = QTextCursor(doc)
        del_c.setPosition(src)
        del_c.movePosition(
            QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor
        )
        del_c.removeSelectedText()
        # Compute target (account for removed character)
        ins_pos = self.cursorForPosition(drop_pos).position()
        if ins_pos > src:
            ins_pos -= 1
        ins_c = QTextCursor(doc)
        ins_c.setPosition(max(0, ins_pos))
        ins_c.insertImage(fmt)
        # Trigger save
        if callable(self._on_focus_out):
            self._on_focus_out()

    def _reset_drag(self) -> None:
        self._img_fmt = None
        self._img_src_pos = -1
        self._img_press_pos = None
        self._img_dragging = False
        if self._img_preview is not None:
            self._img_preview.deleteLater()
            self._img_preview = None

    # ── Text colour bar ───────────────────────────────────────────────

    def _update_color_bar(self):
        if self.textCursor().hasSelection():
            self._color_bar.reposition()
        else:
            self._color_bar.hide()


# ─────────────────────────────────────────────────────────────────────────────
# LiquidFrame — glass-morphism base for all panels
# ─────────────────────────────────────────────────────────────────────────────
class LiquidFrame(QFrame):
    """Liquid glass-morphism frame for dark / light themes.

    Layers (bottom → top):
      1. Base fill  — semi-transparent white on dark; near-opaque white on light
      2. Inner haze — white gradient fading top→bottom (depth simulation)
      3. Gloss strip — bright top-30% highlight (simulates curvature / gloss)
      4. Directional border — top/left brighter, bottom/right dimmer (iOS ref)
      5. Rim glow   — QGraphicsDropShadowEffect with offset 0 (subtle outer edge)

    GlassFrame (finance/page.py) inherits this and overrides for blur-backdrop
    glass theme, delegating to super().paintEvent() for dark/light.

    Class attributes to customise per subclass:
      _RADIUS  = 14.0   border-radius in px
      _DENSITY = 1.0    fill opacity multiplier (1.3 = denser for large cards)
    """
    _RADIUS:  float = 14.0
    _DENSITY: float = 1.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAutoFillBackground(False)
        self._hovered = False
        # Rim glow
        self._rim = QGraphicsDropShadowEffect(self)
        self._rim.setOffset(0, 0)
        self._rim.setBlurRadius(16)
        self._rim.setColor(QColor(255, 255, 255, 16))
        self.setGraphicsEffect(self._rim)

    def update_rim(self):
        """Re-colour rim glow to match the current theme. Call after theme changes."""
        import app.styles.themes as _st
        theme = _st.current_theme()
        if theme == "glass":
            self._rim.setColor(QColor(100, 160, 255, 42))
        elif theme == "light":
            self._rim.setColor(QColor(59, 130, 246, 22))
        else:
            self._rim.setColor(QColor(255, 255, 255, 16))

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        import app.styles.themes as _st
        theme = _st.current_theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        r  = self._RADIUS
        d  = self._DENSITY * (1.15 if self._hovered else 1.0)
        w, h = self.width(), self.height()
        rect_f = QRectF(0.5, 0.5, w - 1.0, h - 1.0)

        clip = QPainterPath()
        clip.addRoundedRect(rect_f, r, r)
        p.setClipPath(clip)

        # ── 1. Base fill ──────────────────────────────────────────────────
        if theme == "light":
            p.fillPath(clip, QColor(255, 255, 255, min(255, int(230 * d))))
        else:
            # dark (glass mode handled by GlassFrame subclass)
            p.fillPath(clip, QColor(255, 255, 255, min(255, int(23 * d))))

        # ── 2. Inner haze (top-bright → transparent) ──────────────────────
        haze = QLinearGradient(0, 0, 0, h)
        if theme == "light":
            haze.setColorAt(0.0, QColor(255, 255, 255, min(255, int(50 * d))))
            haze.setColorAt(0.5, QColor(255, 255, 255, 0))
        else:
            haze.setColorAt(0.0, QColor(255, 255, 255, min(255, int(26 * d))))
            haze.setColorAt(0.4, QColor(255, 255, 255, min(255, int(6 * d))))
            haze.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillPath(clip, QBrush(haze))

        # ── 3. Gloss strip (top 28%) ──────────────────────────────────────
        gloss = QLinearGradient(0, 0, 0, h * 0.28)
        if theme == "light":
            gloss.setColorAt(0.0, QColor(255, 255, 255, 65))
            gloss.setColorAt(1.0, QColor(255, 255, 255, 0))
        else:
            gloss.setColorAt(0.0, QColor(255, 255, 255, 34))
            gloss.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillPath(clip, QBrush(gloss))

        # ── 4. Directional border ─────────────────────────────────────────
        p.setClipping(False)
        ri = int(r)
        if theme == "light":
            tl_c = QColor(255, 255, 255, 210)
            br_c = QColor(175, 198, 225, 100)
        else:
            tl_c = QColor(255, 255, 255, 88)
            br_c = QColor(255, 255, 255, 30)

        p.setPen(QPen(tl_c, 1.0))
        p.drawLine(ri, 0,     w - ri, 0)       # top
        p.drawLine(0,  ri,    0,      h - ri)  # left
        p.setPen(QPen(br_c, 1.0))
        p.drawLine(ri,    h - 1, w - ri, h - 1)  # bottom
        p.drawLine(w - 1, ri,    w - 1,  h - ri)  # right

        p.end()
