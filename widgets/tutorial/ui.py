from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QFrame
from PyQt6.QtCore import Qt, QRectF, QRect, QPoint, QEvent, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QPen, QFont


# ── Hamburger menu preview panel (used by tutorial steps 7-9) ─────────────────

class _MenuPreviewPanel(QWidget):
    """Floating widget that mimics the hamburger dropdown, used as a tutorial target."""

    def __init__(self, anchor: QWidget, overlay: 'TutorialOverlay'):
        super().__init__(overlay)
        try:
            import app.styles.themes as _st
            _theme = _st.current_theme()
            _th = _st._THEMES.get(_theme, _st._THEMES["dark"])
        except Exception:
            _theme = "dark"
            _th = {}
        _light = _theme == "light"
        _glass = _theme == "glass"

        # Mirror exact token values from themes.py so tutorial matches the real popup
        _bg  = _th.get("bg_panel",     "#F7F8FB" if _light else "rgba(14,26,52,0.86)" if _glass else "#1c1c1e")
        _bdr = _th.get("glass_border", "#D5DCE8" if _light else "rgba(148,202,255,0.36)" if _glass else "rgba(255,255,255,0.12)")
        _txt = _th.get("text",         "#1A1F2E" if _light else "#e8f0ff" if _glass else "#f5f5f7")
        _dim = _th.get("text_sec",     "#94A3B8" if _light else "#9ab0d4" if _glass else "#636366")
        _shd = "rgba(0,0,0,0.08)"    if _light else "rgba(0,0,0,0.45)"

        self.setObjectName("TutorialMenuPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            QWidget#TutorialMenuPanel {{
                background-color: {_bg};
                border: 1px solid {_bdr};
                border-radius: 12px;
            }}
            QLabel#TMItem {{
                color: {_txt};
                font-size: 13px;
                font-weight: 400;
                padding: 8px 20px 8px 14px;
                min-width: 180px;
                border-radius: 8px;
            }}
            QLabel#TMItemOff {{
                color: {_dim};
                font-size: 13px;
                padding: 8px 20px 8px 14px;
                min-width: 180px;
                border-radius: 8px;
            }}
        """)

        from shared.i18n import tr
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(1)

        self.analytics = QLabel(tr("toolbar.analytics"))
        self.analytics.setObjectName("TMItem")
        self.calendar  = QLabel(tr("toolbar.calendar"))
        self.calendar.setObjectName("TMItem")
        self.finance   = QLabel(tr("toolbar.finance"))
        self.finance.setObjectName("TMItem")

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {_bdr}; border: none; margin: 2px 6px;")

        self.settings_ = QLabel(tr("toolbar.settings"))
        self.settings_.setObjectName("TMItem")

        for w in (self.analytics, self.calendar, self.finance, sep, self.settings_):
            lay.addWidget(w)

        self.adjustSize()

        # Position below the anchor button (overlay covers full parent, so coords match)
        mw = overlay.parent()
        p = anchor.mapTo(mw, QPoint(0, anchor.height() + 5))
        self.move(p)
        self.raise_()

    def highlight(self, item: QLabel | None) -> None:
        """Highlight one item row; reset the others."""
        try:
            import app.styles.themes as _st
            _theme = _st.current_theme()
            _th = _st._THEMES.get(_theme, _st._THEMES["dark"])
        except Exception:
            _theme = "dark"
            _th = {}
        _light = _theme == "light"
        sel_bg   = _th.get("accent_glow", "rgba(59,130,246,0.15)" if _light else "rgba(94,162,255,0.22)")
        sel_text = _th.get("accent",      "#3B82F6" if _light else "#5ea2ff")
        norm     = _th.get("text",        "#1A1F2E" if _light else "#f5f5f7")
        for w in (self.analytics, self.calendar, self.finance, self.settings_):
            w.setStyleSheet(f"color: {norm};")
        if item is not None:
            item.setStyleSheet(
                f"background-color: {sel_bg}; color: {sel_text}; border-radius: 8px;"
            )


class TutorialOverlay(QWidget):
    """Semi-transparent onboarding overlay with a spotlight on the target widget.

    Emits ``done(dont_show_again: bool)`` when the tutorial finishes or is skipped.
    """

    done = pyqtSignal(bool)

    _CARD_W = 310

    def __init__(self, parent: QWidget, steps: list[dict], zoom: float = 1.0):
        super().__init__(parent)
        self._steps = steps
        self._idx = 0
        self._target_rect: QRect | None = None
        self._menu_panel: _MenuPreviewPanel | None = None

        # Scale factor: grows at half rate (same as fp in styles.py)
        _s = lambda n: round(n * (1 + (zoom - 1) * 0.5))
        self._card_w = _s(self._CARD_W)

        # Cover the entire parent
        self.setGeometry(parent.rect())
        self.raise_()

        # Block all keyboard input from reaching the rest of the UI
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()
        self.grabKeyboard()

        # ── Card ──────────────────────────────────────────────────────────────
        self._card = QWidget(self)
        self._card.setObjectName("TutorialCard")
        self._card.setFixedWidth(self._card_w)

        card_l = QVBoxLayout(self._card)
        card_l.setContentsMargins(_s(22), _s(20), _s(22), _s(18))
        card_l.setSpacing(_s(10))

        self._lbl_step = QLabel()
        self._lbl_step.setObjectName("TutorialStep")
        card_l.addWidget(self._lbl_step)

        self._lbl_title = QLabel()
        self._lbl_title.setObjectName("TutorialTitle")
        self._lbl_title.setWordWrap(True)
        card_l.addWidget(self._lbl_title)

        self._lbl_body = QLabel()
        self._lbl_body.setObjectName("TutorialBody")
        self._lbl_body.setWordWrap(True)
        card_l.addWidget(self._lbl_body)

        card_l.addSpacing(_s(4))

        # Checkbox row
        self._cb_no_show = QCheckBox()
        self._cb_no_show.setObjectName("TutorialCB")
        card_l.addWidget(self._cb_no_show)

        card_l.addSpacing(_s(2))

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(_s(8))
        btn_row.setContentsMargins(0, 0, 0, 0)

        self._btn_skip = QPushButton()
        self._btn_skip.setObjectName("TutorialSkip")
        self._btn_skip.setFixedHeight(_s(34))

        self._btn_next = QPushButton()
        self._btn_next.setObjectName("TutorialNext")
        self._btn_next.setFixedHeight(_s(34))

        btn_row.addWidget(self._btn_skip)
        btn_row.addStretch(1)
        btn_row.addWidget(self._btn_next)
        card_l.addLayout(btn_row)

        self._btn_next.clicked.connect(self._on_next)
        self._btn_skip.clicked.connect(self._on_skip)

        # Install resize event filter on the parent so overlay stays full-size
        parent.installEventFilter(self)

        self._show_step(0)

    # ── painting ──────────────────────────────────────────────────────────────

    # ── input blocking ────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._on_next()
        elif key == Qt.Key.Key_Escape:
            self._on_skip()
        event.accept()  # consume everything — don't let keys reach parent

    def mousePressEvent(self, event):
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()

    def mouseDoubleClickEvent(self, event):
        event.accept()

    # ── painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Full overlay path minus the spotlight cutout
        path = QPainterPath()
        path.addRect(QRectF(self.rect()))

        if self._target_rect:
            pad = 10
            r = self._target_rect.adjusted(-pad, -pad, pad, pad)
            spot = QPainterPath()
            spot.addRoundedRect(QRectF(r), 12, 12)
            path = path.subtracted(spot)

        painter.fillPath(path, QColor(0, 0, 0, 168))

        # Spotlight border
        if self._target_rect:
            pad = 10
            r = self._target_rect.adjusted(-pad, -pad, pad, pad)
            pen = QPen(QColor(10, 132, 255), 2)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(r), 12, 12)

    # ── event filter (keep overlay sized to parent) ───────────────────────────

    def eventFilter(self, obj, event):
        if obj is self.parent() and event.type() == QEvent.Type.Resize:
            self.setGeometry(self.parent().rect())
            self._position_card()
            self.update()
        return super().eventFilter(obj, event)

    # ── step logic ────────────────────────────────────────────────────────────

    def _show_step(self, idx: int):
        from shared.i18n import tr

        self._idx = idx
        step = self._steps[idx]
        n = len(self._steps)

        self._lbl_step.setText(tr("tutorial.step", cur=idx + 1, total=n))
        self._lbl_title.setText(step["title"])
        self._lbl_body.setText(step["body"])
        self._cb_no_show.setText(tr("tutorial.no_show"))

        is_last = (idx == n - 1)
        self._btn_next.setText(tr("tutorial.finish") if is_last else tr("tutorial.next"))
        self._btn_skip.setText(tr("tutorial.skip"))

        # Call on_enter hook (may create menu panel and return the specific item widget)
        on_enter = step.get("on_enter")
        if on_enter is not None:
            item_w = on_enter(self)
            # Spotlight the whole panel (border will appear outside the panel widget,
            # clearly visible on the dark overlay). Highlight the specific item inside.
            if self._menu_panel is not None:
                self._menu_panel.highlight(item_w)
                target_w = self._menu_panel
            else:
                target_w = item_w
        else:
            target_w = step.get("widget")

        # Resolve target rect (overlay coords == parent coords since overlay is at 0,0)
        if target_w is not None and target_w.isVisible():
            tl = target_w.mapTo(self.parent(), QPoint(0, 0))
            self._target_rect = QRect(tl, target_w.size())
        else:
            self._target_rect = None

        # Keep tutorial card above any newly created children (e.g. menu panel)
        self._card.raise_()

        self._card.adjustSize()
        self._position_card()
        self.update()

    def _position_card(self):
        """Position the card near the spotlight without overlapping it."""
        mw, mh = self.width(), self.height()
        cw = self._card_w
        ch = self._card.sizeHint().height() + 10
        margin = 20

        if self._target_rect is None:
            # Centre on screen
            self._card.move((mw - cw) // 2, (mh - ch) // 2)
            return

        tr = self._target_rect
        pad = 14  # gap between spotlight border and card edge

        # Try: right → left → below → above
        if tr.right() + pad + cw + margin <= mw:
            x = tr.right() + pad
            y = max(margin, min(tr.center().y() - ch // 2, mh - ch - margin))
        elif tr.left() - pad - cw - margin >= 0:
            x = tr.left() - pad - cw
            y = max(margin, min(tr.center().y() - ch // 2, mh - ch - margin))
        elif tr.bottom() + pad + ch + margin <= mh:
            x = max(margin, min(tr.center().x() - cw // 2, mw - cw - margin))
            y = tr.bottom() + pad
        else:
            x = max(margin, min(tr.center().x() - cw // 2, mw - cw - margin))
            y = max(margin, tr.top() - pad - ch)

        self._card.move(x, y)

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_next(self):
        nxt = self._idx + 1
        if nxt >= len(self._steps):
            self._finish()
        else:
            self._show_step(nxt)

    def _on_skip(self):
        self._finish()

    def _finish(self):
        self.releaseKeyboard()
        if self._menu_panel is not None:
            self._menu_panel.hide()
            self._menu_panel = None
        self.parent().removeEventFilter(self)
        self.done.emit(self._cb_no_show.isChecked())
        self.hide()
        self.deleteLater()
