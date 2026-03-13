from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QApplication, QStyleFactory, QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QPalette, QColor

from pathlib import Path

if TYPE_CHECKING:
    from app.bootstrap import MainWindow

from shared.config.paths import ASSETS_DIR, ICONS_DIR, SOUNDS_DIR
_CHECK_SVG = (ICONS_DIR / "check_white.svg").as_posix()
_CHEVRON_SVG = (ICONS_DIR / "chevron_down.svg").as_posix()

# ─── Theme system ──────────────────────────────────────────────────────────
_THEMES: dict[str, dict[str, str]] = {
    "dark": {
        "bg_dark":      "#0d0d0f",
        "bg_panel":     "rgba(28,28,30,0.92)",
        "glass":        "rgba(255,255,255,0.07)",
        "glass_hover":  "rgba(255,255,255,0.12)",
        "glass_border": "rgba(255,255,255,0.12)",
        "accent":       "#0a84ff",
        "accent_glow":  "rgba(10,132,255,0.35)",
        "text":         "#f5f5f7",
        "text_sec":     "#98989d",
        "text_done":    "#636366",
        "danger":       "#ff453a",
        "separator":    "rgba(84,84,88,0.36)",
        "bg_combo":     "#1c1c1e",
        "scroll_h":     "rgba(255,255,255,0.15)",
        "scroll_hv":    "rgba(255,255,255,0.28)",
        "cmd_bg":       "#1c1c1e",
        "palette_text": "#f5f5f7",
        "tutorial_bg":  "rgba(28,28,32,0.98)",
        "chart_bg":     "#0d0d0f",
    },
    "light": {
        # ── Base surfaces ── soft blue-gray, matches finance sidebar ─────
        "bg_dark":      "#E8EFF8",              # App / window bg — cool blue-tinted
        "bg_panel":     "#F0F6FC",              # Cards, list panel, sidebar
        "glass":        "#EDF3FA",              # Chip / button bg
        "glass_hover":  "#DDE8F5",              # Hover: more saturated blue tint
        "glass_border": "#C5D3E6",              # Visible but soft border
        # ── Accent ───────────────────────────────────────────────────────
        "accent":       "#3B82F6",              # Tailwind blue-500
        "accent_glow":  "rgba(59,130,246,0.12)", # Soft accent wash
        # ── Text ─────────────────────────────────────────────────────────
        "text":         "#1A1F2E",              # Near-black — crisp, readable
        "text_sec":     "#52607A",              # Blue-gray secondary
        "text_done":    "#9AA3B5",              # Muted done state
        # ── Status ───────────────────────────────────────────────────────
        "danger":       "#DC2626",              # Red-600 — muted danger
        "separator":    "#C8D6E8",              # Soft blue-gray separator
        # ── Input / combo backgrounds ────────────────────────────────────
        "bg_combo":     "#E8EFF8",              # Search, inputs, sort combo
        # ── Scrollbars ───────────────────────────────────────────────────
        "scroll_h":     "rgba(59,130,246,0.18)",
        "scroll_hv":    "rgba(59,130,246,0.38)",
        # ── Overlay / modal ──────────────────────────────────────────────
        "cmd_bg":       "#EEF4FB",
        "palette_text": "#1A1F2E",
        "tutorial_bg":  "rgba(232,239,248,0.98)",
        # ── Chart surfaces ───────────────────────────────────────────────
        "chart_bg":     "#F0F6FC",              # pyqtgraph chart bg (matches panels)
    },
    "glass": {
        # ── Deep-space frosted glass — dark navy + vivid glows ────────────
        "bg_dark":      "#0d1628",               # Very dark navy base
        "bg_panel":     "rgba(14,26,52,0.86)",   # More translucent dark panel
        "glass":        "rgba(78,118,215,0.10)", # Blue-tinted surface — airy
        "glass_hover":  "rgba(95,135,232,0.17)", # Blue-tinted hover — lighter
        "glass_border": "rgba(148,202,255,0.36)", # Blue-tinted border — crisper
        # ── Accent ────────────────────────────────────────────────────────
        "accent":       "#5ea2ff",               # --primary (softer iOS blue)
        "accent_glow":  "rgba(94,162,255,0.22)", # --primary-soft
        # ── Text ──────────────────────────────────────────────────────────
        "text":         "#e8f0ff",               # Slightly blue-white
        "text_sec":     "#9ab0d4",               # Muted blue-gray
        "text_done":    "#4a5870",               # Dim blue-gray
        # ── Status ────────────────────────────────────────────────────────
        "danger":       "#ff6b6b",               # Warmer red
        "separator":    "rgba(110,158,255,0.14)",
        # ── Input / combo backgrounds ─────────────────────────────────────
        "bg_combo":     "#0e1a30",               # Dark blue combo
        # ── Scrollbars ────────────────────────────────────────────────────
        "scroll_h":     "rgba(100,160,255,0.20)",
        "scroll_hv":    "rgba(100,160,255,0.38)",
        # ── Overlay / modal ───────────────────────────────────────────────
        "cmd_bg":       "#0e1a30",
        "palette_text": "#e8f0ff",
        "tutorial_bg":  "rgba(8,14,28,0.98)",
        # ── Chart surfaces ────────────────────────────────────────────────
        "chart_bg":     "#080e1c",               # Must be opaque HEX — pyqtgraph doesn't parse rgba()
    },
}

_active_theme: str = "dark"


def set_theme(name: str) -> None:
    global _active_theme
    if name in _THEMES:
        _active_theme = name


def current_theme() -> str:
    return _active_theme


# ─── iOS / Telegram-inspired colour palette (dark defaults, for imports) ───
_BG_DARK      = "#0d0d0f"
_BG_PANEL     = "rgba(28,28,30,0.92)"       # iOS dark card
_GLASS        = "rgba(255,255,255,0.07)"
_GLASS_HOVER  = "rgba(255,255,255,0.12)"
_GLASS_BORDER = "rgba(255,255,255,0.12)"
_ACCENT       = "#0a84ff"                    # iOS blue
_ACCENT_GLOW  = "rgba(10,132,255,0.35)"
_TEXT          = "#f5f5f7"                    # Apple text-primary
_TEXT_SEC      = "#98989d"                    # Apple text-secondary
_DANGER       = "#ff453a"                    # iOS red
_SEPARATOR    = "rgba(84,84,88,0.36)"        # iOS separator


def apply_app_style(w: "MainWindow", zoom: float = 1.0) -> None:
    # ── resolve theme colours ──
    _th = _THEMES[_active_theme]
    _BG_DARK      = _th["bg_dark"]
    _BG_PANEL     = _th["bg_panel"]
    _GLASS        = _th["glass"]
    _GLASS_HOVER  = _th["glass_hover"]
    _GLASS_BORDER = _th["glass_border"]
    _ACCENT       = _th["accent"]
    _ACCENT_GLOW  = _th["accent_glow"]
    _TEXT          = _th["text"]
    _TEXT_SEC      = _th["text_sec"]
    _DANGER       = _th["danger"]
    _SEPARATOR    = _th["separator"]
    _BG_COMBO     = _th["bg_combo"]
    _SCROLL_H     = _th["scroll_h"]
    _SCROLL_HV    = _th["scroll_hv"]
    _CMD_BG       = _th["cmd_bg"]
    _PALETTE_TEXT = _th["palette_text"]
    _TUTORIAL_BG  = _th["tutorial_bg"]

    _light = _active_theme == "light"
    _glass = _active_theme == "glass"

    # ── Card surfaces ─────────────────────────────────────────────────────────
    if _light:
        _card_bg     = "rgba(255,255,255,0.90)"
        _card_bg_hov = "rgba(255,255,255,0.97)"
        _card_border = "rgba(175,198,225,0.75)"
        _card_hi     = _card_border   # uniform: no directional highlight in light
        _card_border_uni = _card_border
    elif _glass:
        _card_bg     = "qlineargradient(x1:0,y1:0,x2:0.3,y2:1,stop:0 rgba(62,105,198,0.26),stop:1 rgba(16,42,108,0.14))"
        _card_bg_hov = "qlineargradient(x1:0,y1:0,x2:0.3,y2:1,stop:0 rgba(78,122,215,0.34),stop:1 rgba(22,56,130,0.20))"
        _card_border = "rgba(42,88,185,0.32)"
        _card_hi     = "rgba(185,235,255,0.72)"
        _card_border_uni = "rgba(100,160,255,0.38)"   # equal glow all sides
    else:
        _card_bg     = "rgba(255,255,255,0.09)"  # slightly more visible than _GLASS (0.07)
        _card_bg_hov = _GLASS_HOVER
        _card_border = _GLASS_BORDER
        _card_hi     = "rgba(255,255,255,0.08)"
        _card_border_uni = "rgba(255,255,255,0.28)"   # equal glow all sides

    # ── Settings card surface (more opaque than FinSectionCard) ──────────────
    if _light:
        _settings_card_bg  = "rgba(255,255,255,0.94)"
        _settings_card_bor = "rgba(175,198,225,0.80)"
    elif _glass:
        _settings_card_bg  = ("qlineargradient(x1:0,y1:0,x2:0.4,y2:1,"
                              "stop:0 rgba(55,100,210,0.42),stop:1 rgba(14,38,115,0.28))")
        _settings_card_bor = "rgba(120,180,255,0.55)"
    else:
        _settings_card_bg  = "rgba(255,255,255,0.10)"
        _settings_card_bor = "rgba(255,255,255,0.20)"

    # ── Theme-conditional CSS tokens ──────────────────────────────────────────
    _slider_groove_bg    = _SEPARATOR    if _light else "rgba(255,255,255,0.12)"
    _slider_tick_bg      = _GLASS_BORDER if _light else "rgba(255,255,255,0.25)"
    _inline_bar_bg       = _BG_COMBO          if _light else "rgba(10,14,24,0.82)"
    _inline_bar_border   = "rgba(0,0,0,0.14)" if _light else "rgba(255,255,255,0.10)"
    _tutorial_cb_border  = _GLASS_BORDER if _light else "rgba(255,255,255,0.22)"
    _tutorial_skip_br    = _GLASS_BORDER if _light else "rgba(255,255,255,0.14)"
    _tutorial_skip_br_hv = _ACCENT       if _light else "rgba(255,255,255,0.3)"
    _pri_none_border     = _GLASS_BORDER if _light else "rgba(255,255,255,0.3)"
    _analytics_chk_text  = _ACCENT       if _light else "#ffffff"
    _today_chk_text      = _DANGER       if _light else "#ffffff"
    _archive_chk_text    = _TEXT         if _light else "#ffffff"
    _accent_btn_text     = _ACCENT       if _light else "#ffffff"
    _accent_btn_hover_bg = "rgba(59,130,246,0.28)" if _light else "rgba(94,162,255,0.32)" if _glass else "rgba(10,132,255,0.55)"
    _accent_btn_press_bg = "rgba(59,130,246,0.42)" if _light else "rgba(94,162,255,0.48)" if _glass else "rgba(10,132,255,0.70)"
    _subtask_pb_bg       = _SEPARATOR    if _light else "rgba(255,255,255,0.08)"
    _new_hover_bg        = "#60A5FA"     if _light else "#7bb4ff" if _glass else "#409cff"
    _new_press_bg        = "#2563EB"     if _light else "#4a8de8" if _glass else "#0070e0"
    _settings_chk_border = _GLASS_BORDER if _light else "rgba(255,255,255,0.25)"
    _list_sel_inactive   = _ACCENT_GLOW  if _light else "rgba(94,162,255,0.14)" if _glass else "rgba(10,132,255,0.20)"
    _popup_bg            = _BG_PANEL     if _light else _BG_PANEL if _glass else "#1c1c1e"
    _popup_shadow        = "rgba(15,23,42,0.12)" if _light else "rgba(0,0,0,0.50)" if _glass else "rgba(0,0,0,0.40)"

    # Glass theme: app background — very dark navy base (radial glows added by _GlassBg)
    _app_bg = ("qlineargradient(x1:0.1,y1:0,x2:0.9,y2:1,"
               "stop:0 #0d1628,stop:0.4 #080e1c,stop:0.8 #060a16,stop:1 #04070f)"
               if _glass else _BG_DARK)

    # Glass theme: pill / FilterBtn — visible glass body
    _glass_pill_bg  = ("qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                       "stop:0 rgba(65,105,202,0.18),stop:1 rgba(28,56,145,0.09))"
                       if _glass else _GLASS)
    _glass_pill_hov = ("qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                       "stop:0 rgba(86,126,225,0.26),stop:1 rgba(42,78,172,0.14))"
                       if _glass else _GLASS_HOVER)
    _glass_pill_chk = ("qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                       "stop:0 rgba(94,162,255,0.40),stop:1 rgba(94,162,255,0.22))"
                       if _glass else _ACCENT_GLOW)

    # Dark-popup style (font button + floating panels) — near-black, semi-transparent
    _popup_bg     = "rgba(250,252,255,0.90)" if _light else "rgba(10,14,24,0.82)"
    _popup_bg_hov = "rgba(59,130,246,0.08)"  if _light else "rgba(10,14,24,0.94)"
    _popup_bor    = "rgba(0,0,0,0.14)"        if _light else "rgba(255,255,255,0.10)"

    # Danger button adapts to glass warmer red
    _danger_bg      = "rgba(255,107,107,0.14)" if _glass else "rgba(255,69,58,0.08)"
    _danger_bg_hov  = "rgba(255,107,107,0.24)" if _glass else "rgba(255,69,58,0.18)"
    _danger_bg_pre  = "rgba(255,107,107,0.34)" if _glass else "rgba(255,69,58,0.28)"
    _danger_border  = "rgba(255,107,107,0.28)" if _glass else "rgba(255,69,58,0.25)"
    _danger_border_hov = "rgba(255,107,107,0.50)" if _glass else "rgba(255,69,58,0.45)"

    # Glass theme: task list / editor — visible frosted acrylic panels
    _list_bg = ("qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                "stop:0 rgba(42,78,165,0.22),stop:1 rgba(14,34,88,0.13))"
                if _glass else _BG_PANEL)
    _list_border = "rgba(148,202,255,0.38)" if _glass else _GLASS_BORDER
    _item_sel_bg = ("qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                    "stop:0 rgba(94,162,255,0.30),stop:1 rgba(94,162,255,0.16))"
                    if _glass else _ACCENT_GLOW)
    _editor_bg = ("qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                  "stop:0 rgba(42,78,165,0.22),stop:1 rgba(14,34,88,0.13))"
                  if _glass else _GLASS)

    app = QApplication.instance()
    if app is not None:
        app.setStyle(QStyleFactory.create("Fusion"))
        # Set global palette so ALL widgets default to theme bg, not system white/black.
        # In glass theme: Window is transparent so structural wrappers let _GlassBg show through.
        # QMainWindow/QDialog/list/cards all have explicit CSS that overrides the palette.
        _bg  = QColor(0, 0, 0, 0) if _glass else QColor(_BG_DARK)
        _base = QColor(_BG_COMBO)
        _txt  = QColor(_TEXT)
        _acc  = QColor(_ACCENT)
        _hi_txt = QColor("#ffffff")
        pal = QPalette()
        for _g in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive,
                   QPalette.ColorGroup.Disabled):
            pal.setColor(_g, QPalette.ColorRole.Window,          _bg)
            pal.setColor(_g, QPalette.ColorRole.WindowText,      _txt)
            pal.setColor(_g, QPalette.ColorRole.Base,            _base)
            pal.setColor(_g, QPalette.ColorRole.AlternateBase,   _bg)
            pal.setColor(_g, QPalette.ColorRole.Text,            _txt)
            pal.setColor(_g, QPalette.ColorRole.Button,          _bg)
            pal.setColor(_g, QPalette.ColorRole.ButtonText,      _txt)
            pal.setColor(_g, QPalette.ColorRole.Highlight,       _acc)
            pal.setColor(_g, QPalette.ColorRole.HighlightedText, _hi_txt)
        app.setPalette(pal)

    p  = lambda n: round(n * zoom)                        # scale sizes/radii/padding
    fp = lambda n: round(n * (1 + (zoom - 1) * 0.5))     # fonts grow at half rate

    PILL_H   = p(32)
    PILL_R   = PILL_H // 2
    CIRCLE   = p(36)
    CIRCLE_R = CIRCLE // 2
    SML_H    = p(26)   # priority / pin / reminder / deadline buttons
    SML_R    = SML_H // 2
    MED_H    = p(36)   # export / tutorial / lang buttons

    if hasattr(w, "search"):
        w.search.setFixedHeight(PILL_H)
    if hasattr(w, "sort_combo"):
        w.sort_combo.setFixedHeight(PILL_H)
    if hasattr(w, "btn_all"):
        w.btn_all.setFixedHeight(PILL_H)
    if hasattr(w, "btn_active"):
        w.btn_active.setFixedHeight(PILL_H)
    if hasattr(w, "btn_done"):
        w.btn_done.setFixedHeight(PILL_H)
    if hasattr(w, "btn_delete"):
        w.btn_delete.setFixedHeight(PILL_H)
    if hasattr(w, "btn_new"):
        w.btn_new.setFixedSize(CIRCLE, CIRCLE)
    if hasattr(w, "btn_hamburger"):
        w.btn_hamburger.setFixedSize(CIRCLE, CIRCLE)
    if hasattr(w, "btn_analytics"):
        w.btn_analytics.setFixedHeight(PILL_H)
    if hasattr(w, "btn_settings"):
        w.btn_settings.setFixedHeight(PILL_H)
    if hasattr(w, "btn_today"):
        w.btn_today.setFixedHeight(PILL_H)
    if hasattr(w, "btn_archive"):
        w.btn_archive.setFixedHeight(PILL_H)
    if hasattr(w, "btn_calendar"):
        w.btn_calendar.setFixedHeight(PILL_H)

    # Pre-compute conditional CSS blocks (triple-quotes can't go inside f""")
    _glass_scroll_css = (
        # Scroll areas and inner viewport widgets
        "QScrollArea, QAbstractScrollArea > QWidget { background: transparent; } "
        # Structural wrappers — right_stack, _task_area, page containers
        "QStackedWidget { background: transparent; } "
        # Splitter body (handle already has transparent CSS globally)
        "QSplitter { background: transparent; } "
        if _glass else ""
    )
    _glass_card_css = (
        "QFrame#FinKpiCard, QFrame#FinTransactionRow, QFrame#FinAccountCard,"
        "QFrame#FinBudgetCard, QFrame#FinGoalCard, QFrame#FinDonutCard"
        "{ background: transparent; border: none; }"
        "QFrame#FinKpiCard:hover, QFrame#FinTransactionRow:hover,"
        "QFrame#FinAccountCard:hover, QFrame#FinBudgetCard:hover,"
        "QFrame#FinGoalCard:hover { background: transparent; }"
        if _glass else ""
    )

    style = f"""
        /* ─── Global ─── */
        QMainWindow {{
            background: {_app_bg};
        }}
        QDialog {{
            background: {_app_bg};
        }}
        QWidget {{
            color: {_TEXT};
            font-family: -apple-system, "SF Pro Text", "Segoe UI", system-ui, sans-serif;
            font-size: {fp(13)}px;
        }}

        /* ─── Quick-add bar ─── */
        QLineEdit#QuickAdd {{
            background: {_GLASS};
            border: 1px solid {_GLASS_BORDER};
            border-radius: {p(10)}px;
            padding: 0 {p(12)}px;
            color: {_TEXT};
            font-size: {fp(13)}px;
        }}
        QLineEdit#QuickAdd:focus {{
            border-color: {_ACCENT};
            background: {_GLASS_HOVER};
        }}

        /* ─── Glass pill controls ─── */
        QPushButton#FilterBtn,
        QPushButton#DangerBtn {{
            min-height: {PILL_H}px;
            max-height: {PILL_H}px;
            border-radius: {PILL_R}px;
            background: {_glass_pill_bg};
            border: 1px solid {_GLASS_BORDER};
            padding: 0 {fp(16)}px;
            font-size: {fp(13)}px;
        }}
        QLineEdit#SearchBox,
        QComboBox#SortCombo {{
            min-height: {PILL_H}px;
            max-height: {PILL_H}px;
            border-radius: {PILL_R}px;
            background-color: {_BG_COMBO};
            border: 1px solid {_GLASS_BORDER};
            padding: 0 {fp(16)}px;
            font-size: {fp(13)}px;
        }}

        /* Focus glow */
        QLineEdit#SearchBox:focus,
        QComboBox#SortCombo:focus {{
            background-color: {_GLASS_HOVER};
            border: 1px solid {_ACCENT};
        }}

        /* ─── Description font button (dark popup style) ─── */
        QPushButton#DescFontCombo {{
            min-height: 24px;
            max-height: 24px;
            border-radius: 12px;
            background: {_popup_bg};
            border: 1px solid {_popup_bor};
            padding: 0 12px;
            font-size: {fp(12)}px;
            color: {_TEXT};
            text-align: left;
        }}
        QPushButton#DescFontCombo:hover {{
            background: {_popup_bg_hov};
            border-color: {_ACCENT};
        }}
        QPushButton#DescFontCombo:pressed {{
            background: {_popup_bg_hov};
        }}
        QPushButton#DescSizeBtn {{
            min-width: 24px;  max-width: 24px;
            min-height: 24px; max-height: 24px;
            border-radius: 12px;
            background: {_popup_bg};
            border: 1px solid {_popup_bor};
            color: {_TEXT};
            font-size: {fp(14)}px;
            font-weight: 600;
            padding: 0;
        }}
        QPushButton#DescSizeBtn:hover {{
            background: {_popup_bg_hov};
            border-color: {_ACCENT};
        }}
        QPushButton#DescSizeBtn:pressed {{
            background: {_popup_bg_hov};
        }}
        QLabel#DescSizeLbl {{
            color: {_TEXT};
            font-size: {fp(12)}px;
            background: transparent;
        }}

        /* ─── Filter buttons ─── */
        QPushButton#FilterBtn {{
            background: {_glass_pill_bg};
            border: 1px solid {_GLASS_BORDER};
            font-weight: 500;
        }}
        QPushButton#FilterBtn:hover {{
            background: {_glass_pill_hov};
            border-color: {_ACCENT};
        }}
        QPushButton#FilterBtn:checked {{
            background: {_glass_pill_chk};
            border: 1px solid {_ACCENT};
            color: {_ACCENT};
        }}

        /* ─── New task circle button ─── */
        QPushButton#NewBtn {{
            min-width: {CIRCLE}px; min-height: {CIRCLE}px;
            max-width: {CIRCLE}px; max-height: {CIRCLE}px;
            border-radius: {CIRCLE_R}px;
            padding: 0;
            background-color: {_ACCENT};
            border: none;
            font-size: {fp(20)}px;
            font-weight: 300;
            color: #ffffff;
        }}
        QPushButton#NewBtn:hover {{
            background-color: {_new_hover_bg};
        }}
        QPushButton#NewBtn:pressed {{
            background-color: {_new_press_bg};
        }}

        /* ─── Hamburger menu button ─── */
        QPushButton#HamburgerBtn {{
            min-width: {CIRCLE}px; min-height: {CIRCLE}px;
            max-width: {CIRCLE}px; max-height: {CIRCLE}px;
            border-radius: {CIRCLE_R}px;
            padding: 0;
            background: {_glass_pill_bg};
            border: 1px solid {_GLASS_BORDER};
            font-size: {fp(18)}px;
            font-weight: 400;
            color: {_TEXT_SEC};
        }}
        QPushButton#HamburgerBtn:hover {{
            background: {_glass_pill_hov};
            border-color: {_ACCENT};
            color: {_TEXT};
        }}
        QPushButton#HamburgerBtn:pressed {{
            background: {_glass_pill_chk};
        }}

        /* ─── Hamburger popup menu ─── */
        QMenu#HamburgerMenu {{
            background-color: {_popup_bg};
            border: 1px solid {_GLASS_BORDER};
            border-radius: {p(12)}px;
            padding: {p(5)}px {p(4)}px;
            font-size: {fp(13)}px;
        }}
        QMenu#HamburgerMenu::item {{
            padding: {p(8)}px {p(18)}px {p(8)}px {p(14)}px;
            border-radius: {p(8)}px;
            min-width: {p(160)}px;
            color: {_TEXT};
        }}
        QMenu#HamburgerMenu::item:selected {{
            background-color: {_GLASS_HOVER};
            color: {_TEXT};
        }}
        QMenu#HamburgerMenu::item:checked {{
            color: {_ACCENT};
        }}
        QMenu#HamburgerMenu::item:disabled {{
            color: {_TEXT_SEC};
        }}
        QMenu#HamburgerMenu::separator {{
            height: 1px;
            background: {_SEPARATOR};
            margin: {p(4)}px {p(8)}px;
        }}

        /* ─── Sort combo ─── */
        QComboBox#SortCombo {{
            padding-right: {p(40)}px;
        }}
        QComboBox#SortCombo::drop-down {{
            border: none;
            width: {p(32)}px;
            border-top-right-radius: {PILL_R}px;
            border-bottom-right-radius: {PILL_R}px;
            background: transparent;
        }}
        QComboBox#SortCombo::down-arrow {{
            width: {p(10)}px;
            height: {p(10)}px;
        }}
        QComboBox QAbstractItemView {{
            background: {_BG_COMBO};
            border: 1px solid {_GLASS_BORDER};
            border-radius: {p(12)}px;
            padding: 4px;
            selection-background-color: {_ACCENT_GLOW};
            outline: none;
        }}

        /* ─── Delete button ─── */
        QPushButton#DangerBtn {{
            color: {_DANGER};
            border: 1px solid {_danger_border};
            background: {_danger_bg};
            font-weight: 500;
        }}
        QPushButton#DangerBtn:hover {{
            background: {_danger_bg_hov};
            border-color: {_danger_border_hov};
        }}
        QPushButton#DangerBtn:pressed {{
            background: {_danger_bg_pre};
        }}

        /* ─── Neutral action button (settings) ─── */
        QPushButton#NeutralBtn {{
            color: {_ACCENT};
            border: 1px solid rgba(10,132,255,0.30);
            background: rgba(10,132,255,0.07);
            border-radius: 18px;
            min-height: 36px;
            padding: 0 14px;
            font-weight: 500;
        }}
        QPushButton#NeutralBtn:hover {{
            background: rgba(10,132,255,0.15);
            border-color: rgba(10,132,255,0.50);
        }}
        QPushButton#NeutralBtn:pressed {{
            background: rgba(10,132,255,0.24);
        }}

        /* ─── Description clear-format button ─── */
        QPushButton#DescClearBtn {{
            min-width: 32px; max-width: 32px;
            min-height: 24px; max-height: 24px;
            border-radius: 12px;
            background: {_popup_bg};
            border: 1px solid {_GLASS_BORDER};
            color: {_TEXT};
            font-size: 11px;
            font-weight: 600;
            padding: 0;
        }}
        QPushButton#DescClearBtn:hover {{
            background: {_popup_bg_hov};
            border-color: {_ACCENT};
        }}
        QPushButton#DescClearBtn:pressed {{
            background: {_popup_bg_hov};
        }}

        /* ─── Editor title ─── */
        QLineEdit#EditorTitle {{
            background: transparent;
            border: none;
            border-bottom: 2px solid transparent;
            padding: 0;
            border-radius: 0;
            font-size: {fp(28)}px;
            font-weight: 700;
            letter-spacing: -0.5px;
        }}
        QLineEdit#EditorTitle:focus {{
            border-bottom: 2px solid {_ACCENT};
        }}

        /* ─── Editor description ─── */
        QTextEdit#EditorDesc {{
            background: transparent;
            border: none;
            padding: {p(8)}px;
            color: {_TEXT};
            font-size: {fp(14)}px;
            line-height: 1.5;
        }}

        /* ─── Meta + hint labels ─── */
        QLabel#EditorMeta {{
            color: {_TEXT_SEC};
            font-size: {fp(12)}px;
        }}
        QLabel#AppName {{
            color: #c2c2cc;
            font-size: {fp(52)}px;
            font-weight: 700;
            letter-spacing: -1px;
        }}
        QLabel#EmptyHint {{
            color: {_TEXT_SEC};
            font-size: {fp(16)}px;
        }}

        /* ─── Task list ─── */
        QListWidget#SubtaskListWidget {{
            background: transparent;
            border: none;
            border-radius: 0;
        }}
        QListWidget {{
            background: {_card_bg};
            border: 1px solid {_card_border_uni};
            border-radius: {p(16)}px;
            padding: {p(6)}px;
            margin-top: 4px;
            margin-bottom: 6px;
            outline: none;
        }}
        QListWidget::item {{
            padding: {p(10)}px {p(12)}px;
            border-radius: {p(12)}px;
            margin: 2px 0;
        }}
        QListWidget::item:hover {{
            background: {_GLASS_HOVER};
        }}
        QListWidget::item:selected {{
            background: {_item_sel_bg};
        }}
        QListWidget::item:selected:!active {{
            background: {_list_sel_inactive};
        }}

        /* ─── Hide native checkbox (delegate draws its own) ─── */
        QListWidget::indicator {{
            width: 0px;
            height: 0px;
            margin: 0px;
            padding: 0px;
        }}

        /* ─── Scrollbars (iOS-thin) ─── */
        QScrollBar:vertical {{
            background: transparent;
            width: 6px;
            margin: 4px 0;
        }}
        QScrollBar::handle:vertical {{
            background: {_SCROLL_H};
            border-radius: 3px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {_SCROLL_HV};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical,
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {{
            background: none;
            border: none;
            height: 0;
        }}
        QScrollBar:horizontal {{
            height: 0;
        }}

        /* ─── Splitter handle ─── */
        QSplitter::handle {{
            background: transparent;
        }}

        /* ─── Separator line ─── */
        QFrame {{
            color: {_SEPARATOR};
        }}

        /* ─── Stats label ─── */
        QLabel#StatsLabel {{
            color: {_TEXT_SEC};
            font-size: {fp(11)}px;
        }}

        /* ─── Bulk count label ─── */
        QLabel#BulkCountLabel {{
            color: {_TEXT};
            font-size: {fp(22)}px;
            font-weight: 600;
            letter-spacing: -0.3px;
        }}

        /* ─── Accent action button (e.g. calendar add-task) ─── */
        QPushButton#AccentBtn {{
            min-height: {PILL_H}px;
            max-height: {PILL_H}px;
            border-radius: {PILL_R}px;
            background-color: {_ACCENT_GLOW};
            border: 1px solid {_ACCENT};
            padding: 0 {fp(16)}px;
            font-size: {fp(13)}px;
            font-weight: 600;
            color: {_accent_btn_text};
        }}
        QPushButton#AccentBtn:hover {{
            background-color: {_accent_btn_hover_bg};
            border-color: {_ACCENT};
        }}
        QPushButton#AccentBtn:pressed {{
            background-color: {_accent_btn_press_bg};
        }}

        /* ─── Analytics button ─── */
        QPushButton#AnalyticsBtn {{
            min-height: {PILL_H}px;
            max-height: {PILL_H}px;
            border-radius: {PILL_R}px;
            background-color: {_GLASS};
            border: 1px solid {_GLASS_BORDER};
            padding: 0 {fp(16)}px;
            font-size: {fp(13)}px;
            font-weight: 500;
            color: {_ACCENT};
        }}
        QPushButton#AnalyticsBtn:hover {{
            background-color: {_GLASS_HOVER};
            border-color: {_ACCENT};
        }}
        QPushButton#AnalyticsBtn:checked {{
            background-color: {_ACCENT_GLOW};
            border: 1px solid {_ACCENT};
            color: {_analytics_chk_text};
        }}

        /* ─── Priority buttons ─── */
        QPushButton#PriNoneBtn,
        QPushButton#PriLowBtn,
        QPushButton#PriMedBtn,
        QPushButton#PriHighBtn {{
            min-height: {SML_H}px; max-height: {SML_H}px;
            border-radius: {SML_R}px;
            background-color: {_GLASS};
            border: 1px solid {_GLASS_BORDER};
            padding: 0 {fp(10)}px;
            font-size: {fp(11)}px; font-weight: 500;
            color: {_TEXT_SEC};
        }}
        QPushButton#PriNoneBtn:hover, QPushButton#PriLowBtn:hover,
        QPushButton#PriMedBtn:hover, QPushButton#PriHighBtn:hover {{
            background-color: {_GLASS_HOVER};
        }}
        QPushButton#PriNoneBtn:checked {{
            background: {_GLASS_HOVER};
            border-color: {_pri_none_border};
            color: {_TEXT};
        }}
        QPushButton#PriLowBtn:checked {{
            background: rgba(52,199,89,0.18);
            border-color: #34c759;
            color: #34c759;
        }}
        QPushButton#PriMedBtn:checked {{
            background: rgba(255,159,10,0.18);
            border-color: #ff9f0a;
            color: #ff9f0a;
        }}
        QPushButton#PriHighBtn:checked {{
            background: rgba(255,69,58,0.18);
            border-color: #ff453a;
            color: #ff453a;
        }}

        /* ─── Pin button ─── */
        QPushButton#PinBtn {{
            min-height: {SML_H}px; max-height: {SML_H}px;
            border-radius: {SML_R}px;
            background-color: {_GLASS};
            border: 1px solid {_GLASS_BORDER};
            padding: 0 {fp(10)}px;
            font-size: {fp(11)}px; font-weight: 500;
            color: {_TEXT_SEC};
        }}
        QPushButton#PinBtn:hover {{
            background-color: {_GLASS_HOVER};
        }}
        QPushButton#PinBtn:checked {{
            background: {_ACCENT_GLOW};
            border-color: {_ACCENT};
            color: {_ACCENT};
        }}

        /* ─── Recurrence combo ─── */
        QComboBox#RecCombo {{
            min-height: {SML_H}px; max-height: {SML_H}px;
            border-radius: {SML_R}px;
            background-color: {_GLASS};
            border: 1px solid {_GLASS_BORDER};
            padding-left: {p(10)}px;
            padding-right: {p(24)}px;
            font-size: {fp(11)}px; font-weight: 500;
            color: {_TEXT_SEC};
        }}
        QComboBox#RecCombo:hover {{
            background-color: {_GLASS_HOVER};
        }}
        QComboBox#RecCombo:on {{
            border-color: {_ACCENT};
            color: {_ACCENT};
        }}
        QComboBox#RecCombo::drop-down {{
            border: none; width: {p(20)}px;
            border-top-right-radius: {SML_R}px;
            border-bottom-right-radius: {SML_R}px;
            background: transparent;
        }}
        QComboBox#RecCombo::down-arrow {{
            image: url({_CHEVRON_SVG});
            width: {p(10)}px;
            height: {p(7)}px;
        }}

        /* ─── RecCombo popup ─── */
        QComboBox#RecCombo QAbstractItemView {{
            background: {_popup_bg};
            border: none;
            border-radius: {p(14)}px;
            padding: {p(5)}px {p(4)}px;
            outline: none;
        }}
        QComboBox#RecCombo QAbstractItemView::item {{
            padding: {p(8)}px {p(14)}px;
            border-radius: {p(8)}px;
            min-height: {p(24)}px;
            color: {_TEXT};
            border: none;
        }}
        QComboBox#RecCombo QAbstractItemView::item:hover {{
            background: {_GLASS_HOVER};
        }}
        QComboBox#RecCombo QAbstractItemView::item:selected,
        QComboBox#RecCombo QAbstractItemView::item:selected:active {{
            background: {_ACCENT_GLOW};
            color: {_ACCENT};
            border: none;
        }}

        /* ─── Subtasks ─── */
        QLabel#SubtasksTitle {{
            color: {_TEXT_SEC};
            font-size: {fp(11)}px;
            font-weight: 600;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }}
        QLineEdit#SubtaskInput {{
            background: {_GLASS};
            border: 1px solid {_GLASS_BORDER};
            border-radius: {p(8)}px;
            padding: {p(4)}px {p(10)}px;
            color: {_TEXT};
            font-size: {fp(13)}px;
        }}
        QLineEdit#SubtaskInput:focus {{
            border-color: {_ACCENT};
        }}

        /* ─── Subtask progress bar ─── */
        QProgressBar#SubtaskProgress {{
            background: {_subtask_pb_bg};
            border: none;
            border-radius: 2px;
        }}
        QProgressBar#SubtaskProgress::chunk {{
            background: #30d158;
            border-radius: 2px;
        }}

        /* ─── Export buttons ─── */
        QPushButton#ExportBtn {{
            min-height: {MED_H}px; max-height: {MED_H}px;
            border-radius: {p(12)}px;
            background-color: {_GLASS};
            border: 1px solid {_GLASS_BORDER};
            padding: 0 {fp(16)}px;
            font-size: {fp(13)}px; font-weight: 500;
            color: {_TEXT_SEC};
        }}
        QPushButton#ExportBtn:hover {{
            background-color: {_GLASS_HOVER};
            color: {_TEXT};
        }}

        /* ─── Tutorial overlay card ─── */
        QWidget#TutorialCard {{
            background: {_TUTORIAL_BG};
            border: 1.5px solid rgba(10,132,255,0.55);
            border-radius: {p(16)}px;
        }}
        QLabel#TutorialStep {{
            color: {_ACCENT};
            font-size: {fp(11)}px;
            font-weight: 600;
            letter-spacing: 0.4px;
        }}
        QLabel#TutorialTitle {{
            color: {_TEXT};
            font-size: {fp(15)}px;
            font-weight: 700;
        }}
        QLabel#TutorialBody {{
            color: {_TEXT_SEC};
            font-size: {fp(13)}px;
        }}
        QPushButton#TutorialNext {{
            background: {_ACCENT};
            border: none;
            border-radius: {p(10)}px;
            color: white;
            font-size: {fp(13)}px;
            font-weight: 600;
            padding: 0 {fp(18)}px;
        }}
        QPushButton#TutorialNext:hover {{ background: #409cff; }}
        QPushButton#TutorialSkip {{
            background: transparent;
            border: 1px solid {_tutorial_skip_br};
            border-radius: {p(10)}px;
            color: {_TEXT_SEC};
            font-size: {fp(13)}px;
            padding: 0 {fp(14)}px;
        }}
        QPushButton#TutorialSkip:hover {{
            border-color: {_tutorial_skip_br_hv};
            color: {_TEXT};
        }}
        QCheckBox#TutorialCB {{
            color: #6e6e73;
            font-size: {fp(11)}px;
            spacing: {p(6)}px;
        }}
        QCheckBox#TutorialCB::indicator {{
            width: {p(14)}px; height: {p(14)}px;
            border: 1px solid {_tutorial_cb_border};
            border-radius: {p(4)}px;
            background: transparent;
        }}
        QCheckBox#TutorialCB::indicator:checked {{
            background: {_ACCENT};
            border-color: {_ACCENT};
        }}
        /* Tutorial button in settings */
        QPushButton#TutorialBtn {{
            min-height: {MED_H}px; max-height: {MED_H}px;
            border-radius: {p(12)}px;
            background-color: {_GLASS};
            border: 1px solid {_GLASS_BORDER};
            padding: 0 {fp(18)}px;
            font-size: {fp(13)}px; font-weight: 500;
            color: {_ACCENT};
        }}
        QPushButton#TutorialBtn:hover {{
            background-color: {_GLASS_HOVER};
            border-color: {_ACCENT};
        }}

        /* ─── Per-task export buttons (editor bottom row) ─── */
        QPushButton#TaskExportBtn {{
            min-height: {p(24)}px; max-height: {p(24)}px;
            border-radius: {p(12)}px;
            background-color: {_GLASS};
            border: 1px solid {_GLASS_BORDER};
            padding: 0 {fp(10)}px;
            font-size: {fp(11)}px; font-weight: 500;
            color: {_TEXT_SEC};
        }}
        QPushButton#TaskExportBtn:hover {{
            background-color: {_GLASS_HOVER};
            color: {_TEXT};
        }}

        /* ─── Today / overdue filter button ─── */
        QPushButton#TodayBtn {{
            min-height: {PILL_H}px;
            max-height: {PILL_H}px;
            border-radius: {PILL_R}px;
            background-color: rgba(255,69,58,0.08);
            border: 1px solid rgba(255,69,58,0.25);
            padding: 0 {fp(14)}px;
            font-size: {fp(13)}px;
            font-weight: 500;
            color: {_DANGER};
        }}
        QPushButton#TodayBtn:hover {{
            background-color: rgba(255,69,58,0.18);
            border-color: {_DANGER};
        }}
        QPushButton#TodayBtn:checked {{
            background-color: rgba(255,69,58,0.28);
            border: 1px solid {_DANGER};
            color: {_today_chk_text};
        }}

        /* ─── Archive filter button ─── */
        QPushButton#ArchiveBtn {{
            min-height: {PILL_H}px; max-height: {PILL_H}px;
            border-radius: {PILL_R}px;
            background-color: rgba(152,152,157,0.08);
            border: 1px solid rgba(152,152,157,0.25);
            color: {_TEXT_SEC};
            padding: 0 {fp(14)}px; font-size: {fp(13)}px; font-weight: 500;
        }}
        QPushButton#ArchiveBtn:hover {{
            background-color: rgba(152,152,157,0.15);
            color: {_TEXT};
        }}
        QPushButton#ArchiveBtn:checked {{
            background-color: rgba(152,152,157,0.28);
            border: 1px solid rgba(152,152,157,0.55);
            color: {_archive_chk_text};
        }}

        /* ─── Calendar button ─── */
        QPushButton#CalendarBtn {{
            min-height: {PILL_H}px; max-height: {PILL_H}px;
            border-radius: {PILL_R}px;
            background-color: rgba(48,209,88,0.10);
            border: 1px solid rgba(48,209,88,0.25);
            color: {_TEXT_SEC};
            padding: 0 {fp(14)}px; font-size: {fp(13)}px; font-weight: 500;
        }}
        QPushButton#CalendarBtn:hover {{
            background-color: rgba(48,209,88,0.18);
            color: {_TEXT};
        }}
        QPushButton#CalendarBtn:checked {{
            background-color: rgba(48,209,88,0.28);
            border: 1px solid rgba(48,209,88,0.55);
            color: #30d158;
        }}

        /* ─── Tags input in editor ─── */
        QLineEdit#TagsInput {{
            background: {_GLASS};
            border: 1px solid {_GLASS_BORDER};
            border-radius: {p(8)}px;
            padding: {p(4)}px {p(10)}px;
            color: {_TEXT};
            font-size: {fp(13)}px;
        }}
        QLineEdit#TagsInput:focus {{
            border-color: {_ACCENT};
        }}

        /* ─── Reminder button ─── */
        QPushButton#ReminderBtn {{
            min-height: {SML_H}px;
            max-height: {SML_H}px;
            border-radius: {SML_R}px;
            background-color: {_GLASS};
            border: 1px solid {_GLASS_BORDER};
            padding: 0 {fp(14)}px;
            font-size: {fp(12)}px;
            font-weight: 500;
            color: {_ACCENT};
        }}
        QPushButton#ReminderBtn:hover {{
            background-color: {_GLASS_HOVER};
            border-color: {_ACCENT};
        }}

        /* ─── Deadline button ─── */
        QPushButton#DeadlineBtn {{
            min-height: {SML_H}px;
            max-height: {SML_H}px;
            border-radius: {SML_R}px;
            background-color: rgba(255,159,10,0.08);
            border: 1px solid rgba(255,159,10,0.25);
            padding: 0 {fp(14)}px;
            font-size: {fp(12)}px;
            font-weight: 500;
            color: #ff9f0a;
        }}
        QPushButton#DeadlineBtn:hover {{
            background-color: rgba(255,159,10,0.18);
            border-color: #ff9f0a;
        }}

        /* ─── Task ··· menu button ─── */
        QToolButton#TaskMenuBtn {{
            min-width: {p(28)}px; max-width: {p(28)}px;
            min-height: {p(28)}px; max-height: {p(28)}px;
            border-radius: {p(8)}px;
            background-color: transparent;
            border: none;
            font-size: {fp(16)}px;
            font-weight: 700;
            color: {_TEXT_SEC};
            letter-spacing: 1px;
        }}
        QToolButton#TaskMenuBtn:hover {{
            background-color: {_GLASS};
            color: {_TEXT};
        }}
        QToolButton#TaskMenuBtn:pressed {{
            background-color: {_GLASS_HOVER};
        }}

        /* ─── Settings button ─── */
        QPushButton#SettingsBtn {{
            min-height: {PILL_H}px;
            max-height: {PILL_H}px;
            border-radius: {PILL_R}px;
            background-color: {_GLASS};
            border: 1px solid {_GLASS_BORDER};
            padding: 0 {fp(16)}px;
            font-size: {fp(13)}px;
            font-weight: 500;
            color: {_TEXT_SEC};
        }}
        QPushButton#SettingsBtn:hover {{
            background-color: {_GLASS_HOVER};
            color: {_TEXT};
        }}
        QPushButton#SettingsBtn:checked {{
            background-color: {_GLASS_HOVER};
            border-color: {_settings_chk_border};
            color: {_TEXT};
        }}

        /* ─── Settings page ─── */
        QLabel#SettingsDialogTitle {{
            color: {_TEXT};
            font-size: {fp(15)}px;
            font-weight: 700;
            letter-spacing: -0.2px;
        }}
        QPushButton#SettingsCloseBtn {{
            background: transparent;
            color: {_TEXT_SEC};
            font-size: {fp(14)}px;
            font-weight: 500;
            border: none;
            border-radius: 15px;
        }}
        QPushButton#SettingsCloseBtn:hover {{
            background: rgba(255,80,80,0.18);
            color: #ff6b6b;
        }}
        QPushButton#SettingsCloseBtn:pressed {{
            background: rgba(255,80,80,0.30);
        }}
        QLabel#SettingsTitle {{
            color: {_TEXT};
            font-size: {fp(22)}px;
            font-weight: 700;
            letter-spacing: -0.3px;
        }}
        QLabel#SettingsSectionLabel {{
            color: {_TEXT_SEC};
            font-size: {fp(11)}px;
            font-weight: 600;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }}
        QPushButton#LangBtn {{
            min-height: {MED_H}px;
            max-height: {MED_H}px;
            border-radius: {p(18)}px;
            min-width: {p(70)}px;
            background-color: {_GLASS};
            border: 1px solid {_GLASS_BORDER};
            font-size: {fp(14)}px;
            font-weight: 500;
            color: {_TEXT_SEC};
        }}
        QPushButton#LangBtn:hover {{
            background-color: {_GLASS_HOVER};
        }}
        QPushButton#LangBtn:checked {{
            background-color: {_ACCENT_GLOW};
            border-color: {_ACCENT};
            color: {_ACCENT};
        }}
        QCheckBox#SettingsCheck {{
            font-size: {fp(14)}px;
        }}

        /* ─── Sound dropdown ─── */
        QComboBox#SoundCombo {{
            min-height: {p(40)}px;
            max-height: {p(40)}px;
            border-radius: {p(10)}px;
            background-color: {_GLASS};
            border: 1px solid {_GLASS_BORDER};
            padding-left: {p(14)}px;
            padding-right: {p(40)}px;
            font-size: {fp(14)}px;
            color: {_TEXT};
        }}
        QComboBox#SoundCombo:hover {{
            background-color: {_GLASS_HOVER};
        }}
        QComboBox#SoundCombo:on {{
            border-color: {_ACCENT};
        }}
        QComboBox#SoundCombo::drop-down {{
            border: none;
            width: {p(36)}px;
            border-top-right-radius: {p(10)}px;
            border-bottom-right-radius: {p(10)}px;
            background: transparent;
        }}
        QComboBox#SoundCombo::down-arrow {{
            image: url({_CHEVRON_SVG});
            width: {p(12)}px;
            height: {p(8)}px;
        }}

        /* ─── Zoom slider ─── */
        QSlider#ZoomSlider::groove:horizontal {{
            background: {_slider_groove_bg};
            height: 4px;
            border-radius: 2px;
        }}
        QSlider#ZoomSlider::sub-page:horizontal {{
            background: {_ACCENT};
            border-radius: 2px;
        }}
        QSlider#ZoomSlider::handle:horizontal {{
            background: {_ACCENT};
            width: 16px;
            height: 16px;
            border-radius: 8px;
            margin: -6px 0;
        }}
        QSlider#ZoomSlider::handle:horizontal:hover {{
            background: #409cff;
        }}
        QSlider#ZoomSlider::tick-mark:horizontal {{
            background: {_slider_tick_bg};
            width: 1px;
            height: 4px;
        }}

        /* ─── Text colour bar (floating) ─── */
        /* Background is painted in paintEvent (WA_TranslucentBackground bypasses CSS) */
        QFrame#TextColorBar {{
            background: transparent;
        }}

        /* ─── Inline colour toolbar (pill above description) ─── */
        QFrame#InlineColorBar {{
            background: {_inline_bar_bg};
            border: 1px solid {_inline_bar_border};
            border-radius: 16px;
        }}

        /* ─── Command Palette (glassmorphism — paintEvent draws bg) ─── */
        QDialog#CommandPalette {{
            background: transparent;
            border: none;
        }}
        QLineEdit#PaletteSearch {{
            background: transparent;
            border: none;
            border-bottom: 1px solid {_GLASS_BORDER};
            border-radius: 0;
            color: {_PALETTE_TEXT};
            font-size: 15px;
            padding: 0 16px;
        }}
        QListWidget#PaletteList {{
            background: transparent;
            border: none;
            color: {_PALETTE_TEXT};
            font-size: 13px;
            padding: 4px;
            outline: none;
        }}
        QListWidget#PaletteList::item {{
            padding: 0;
            border-radius: 0;
        }}
        QListWidget#PaletteList::item:selected {{
            background: transparent;
        }}
        QListWidget#PaletteList::item:hover {{
            background: transparent;
        }}

        /* ─── Settings SpinBox ─── */
        QSpinBox#SettingsSpinBox {{
            background: {_GLASS};
            border: 1px solid {_GLASS_BORDER};
            border-radius: 6px;
            color: {_TEXT};
            padding: 2px 6px;
            font-size: {fp(13)}px;
        }}
        QSpinBox#SettingsSpinBox::up-button,
        QSpinBox#SettingsSpinBox::down-button {{ width: 16px; }}

        /* ─── Toast notification ─── */
        QLabel#ToastLabel {{
            background: {_CMD_BG};
            color: {_PALETTE_TEXT};
            border: 1px solid {_GLASS_BORDER};
            border-radius: {p(20)}px;
            padding: {p(8)}px {p(20)}px;
            font-size: {fp(13)}px;
            font-weight: 500;
        }}

        /* ─── Finance transactions search ─── */
        QLineEdit#Search {{
            background: {_card_bg};
            border: 1px solid {_card_border_uni};
            border-radius: 16px;
            padding: 0 14px;
            color: {_TEXT};
            font-size: {fp(13)}px;
            min-height: 32px;
            max-height: 32px;
        }}
        QLineEdit#Search:focus {{
            border-color: {_ACCENT};
            background: {_card_bg_hov};
        }}

        /* ─── Glass panels (editor + left panel) ─── */
        QFrame#DescPanel, QFrame#SubtaskPanel, QFrame#EditorMetaPanel,
        QFrame#FilterSortPanel, QFrame#TaskListPanel {{
            background: {_card_bg};
            border: 1px solid {_card_border_uni};
            border-radius: 14px;
        }}

        /* ─── Task list inside TaskListPanel: transparent (panel provides the card) ─── */
        QListWidget#TaskList {{
            background: transparent;
            border: none;
            border-radius: 0;
            padding: {p(4)}px;
            margin-top: 0;
            margin-bottom: 0;
            outline: none;
        }}

        /* ─── Finance workspace ─── */
        QFrame#FinTransactionRow {{
            background: {_card_bg};
            border: 1px solid {_card_border_uni};
            border-radius: 10px;
        }}
        QFrame#FinTransactionRow:hover {{
            background: {_card_bg_hov};
        }}
        QPushButton#TxDeleteBtn {{
            background: transparent;
            border: none;
            color: {_DANGER};
            border-radius: 13px;
            padding: 0;
            opacity: 0.7;
        }}
        QPushButton#TxDeleteBtn:hover {{
            background: rgba(255,107,107,0.15);
            color: {_DANGER};
        }}
        QFrame#FinAccountCard {{
            background: {_card_bg};
            border: 1px solid {_card_border_uni};
            border-radius: 12px;
        }}
        QFrame#FinAccountCard:hover {{
            background: {_card_bg_hov};
        }}
        QFrame#FinGoalCard {{
            background: {_card_bg};
            border: 1px solid {_card_border_uni};
            border-radius: 14px;
        }}
        QFrame#FinGoalCard:hover {{
            background: {_card_bg_hov};
        }}
        QFrame#FinBudgetCard {{
            background: {_card_bg};
            border: 1px solid {_card_border_uni};
            border-radius: 12px;
        }}
        QFrame#FinBudgetCard:hover {{
            background: {_card_bg_hov};
        }}
        QFrame#FinKpiCard {{
            background: transparent;
            border: none;
        }}
        QFrame#FinSectionCard, QFrame#FinDonutCard {{
            background: {_card_bg};
            border: 1px solid {_card_border_uni};
            border-radius: 14px;
        }}
        QFrame#SettingsCard {{
            background: {_settings_card_bg};
            border: 1px solid {_settings_card_bor};
            border-radius: 14px;
        }}
        QWidget#SettingsPage {{
            background: transparent;
        }}
        QProgressBar#FinBudgetBar {{
            background: {_GLASS_BORDER};
            border: none;
            border-radius: 4px;
            height: 8px;
            text-align: center;
            font-size: 0px;
        }}
        QProgressBar#FinBudgetBar::chunk {{
            border-radius: 4px;
            background: {_ACCENT};
        }}
        QProgressBar#FinBudgetBarDanger {{
            background: {_GLASS_BORDER};
            border: none;
            border-radius: 4px;
            height: 8px;
            text-align: center;
            font-size: 0px;
        }}
        QProgressBar#FinBudgetBarDanger::chunk {{
            border-radius: 4px;
            background: {_DANGER};
        }}
        {_glass_scroll_css}
        {_glass_card_css}
    """

    if app is not None:
        app.setStyleSheet(style)

        _mw_widgets = []
        for _attr in ("search", "sort_combo", "btn_all", "btn_active",
                      "btn_done", "btn_delete", "btn_new", "list"):
            if hasattr(w, _attr):
                _mw_widgets.append(getattr(w, _attr))
        for widget in _mw_widgets:
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.updateGeometry()
            widget.update()

        cw = w.centralWidget()
        if cw is not None and cw.layout() is not None:
            cw.layout().activate()
        w.updateGeometry()
        w.repaint()
    else:
        w.setStyleSheet(style)

    # Glass ambient-glow background widget
    if _glass:
        install_glass_bg(w)
    else:
        remove_glass_bg(w)

    # Windows 11: tint the native title-bar frame to match the theme.
    # Deferred so it runs after the window has a valid HWND.
    import sys as _sys
    if _sys.platform == "win32":
        from PyQt6.QtCore import QTimer
        _theme_snap = _active_theme
        QTimer.singleShot(80, lambda: _set_win_titlebar(w, _theme_snap))


def _set_win_titlebar(w: "MainWindow", theme: str) -> None:
    """Set the Windows 11 native title-bar caption color via DWM API (DWMWA_CAPTION_COLOR=35).
    No-op on non-Windows or older Windows versions.
    """
    import sys
    if sys.platform != "win32":
        return
    try:
        import ctypes
        DWMWA_CAPTION_COLOR = 35
        # Map theme → RGB  (COLORREF = R | G<<8 | B<<16)
        _colors = {
            "glass": (0x08, 0x0e, 0x1c),   # #080e1c — matches glass bg mid-point
            "dark":  (0x0d, 0x0d, 0x0f),   # #0d0d0f near-black
            "light": (0xf0, 0xf4, 0xf8),   # #f0f4f8 light gray
        }
        r, g, b = _colors.get(theme, _colors["dark"])
        colorref = ctypes.c_int(r | (g << 8) | (b << 16))
        hwnd = int(w.winId())
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_CAPTION_COLOR,
            ctypes.byref(colorref), ctypes.sizeof(colorref)
        )
    except Exception:
        pass


def install_glass_bg(w: "MainWindow") -> None:
    """Paint an ambient radial-glow background inside centralWidget.

    Maintains a blurred QPixmap cache so GlassFrame widgets can sample
    their region to simulate CSS backdrop-filter: blur().
    """
    from PyQt6.QtWidgets import (QWidget, QGraphicsScene,
                                  QGraphicsPixmapItem, QGraphicsBlurEffect)
    from PyQt6.QtGui import (QPainter, QRadialGradient, QLinearGradient,
                              QColor, QPixmap)
    from PyQt6.QtCore import Qt, QObject, QEvent, QRectF, QTimer

    class _GlassBg(QWidget):
        def __init__(self, parent):
            super().__init__(parent)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self.setAutoFillBackground(False)
            self._blur_cache: QPixmap | None = None
            self._blur_scheduled = False

        # ── Rendering ────────────────────────────────────────────────────
        def _do_paint(self, p: QPainter):
            pw, ph = self.width(), self.height()
            # Base: near-black navy diagonal
            base = QLinearGradient(pw * 0.1, 0, pw * 0.9, ph)
            base.setColorAt(0.00, QColor(0x0d, 0x16, 0x28))
            base.setColorAt(0.40, QColor(0x08, 0x0e, 0x1c))
            base.setColorAt(0.80, QColor(0x06, 0x0a, 0x16))
            base.setColorAt(1.00, QColor(0x04, 0x07, 0x10))
            p.fillRect(self.rect(), base)
            # Glow 1: primary blue — upper-center-right (brighter for acrylic pop)
            rg1 = QRadialGradient(pw * 0.68, ph * 0.10, pw * 0.55)
            rg1.setColorAt(0.00, QColor(72, 125, 255, 135))
            rg1.setColorAt(0.35, QColor(55,  98, 225,  68))
            rg1.setColorAt(1.00, QColor(30,  60, 160,   0))
            p.fillRect(self.rect(), rg1)
            # Glow 2: secondary blue — upper-left corner
            rg2 = QRadialGradient(pw * 0.10, ph * 0.08, pw * 0.32)
            rg2.setColorAt(0.00, QColor(82, 115, 235, 95))
            rg2.setColorAt(1.00, QColor(60,  80, 192,  0))
            p.fillRect(self.rect(), rg2)
            # Glow 3: purple — mid-left
            rg3 = QRadialGradient(pw * 0.06, ph * 0.62, pw * 0.24)
            rg3.setColorAt(0.00, QColor(115, 58, 215, 72))
            rg3.setColorAt(1.00, QColor( 90, 45, 192,  0))
            p.fillRect(self.rect(), rg3)
            # Glow 4: warm amber — bottom-right
            rg4 = QRadialGradient(pw * 0.88, ph * 0.85, pw * 0.30)
            rg4.setColorAt(0.00, QColor(205, 125, 42, 72))
            rg4.setColorAt(1.00, QColor(180, 100, 30,  0))
            p.fillRect(self.rect(), rg4)

        def paintEvent(self, _ev):
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            self._do_paint(p)
            p.end()
            # Only schedule blur when cache is absent — prevents an infinite loop:
            # _rebuild_blur → parent.update() → paintEvent → _schedule_blur → repeat.
            if self._blur_cache is None:
                self._schedule_blur()

        # ── Blur cache ───────────────────────────────────────────────────
        def _schedule_blur(self):
            if not self._blur_scheduled:
                self._blur_scheduled = True
                QTimer.singleShot(0, self._rebuild_blur)

        def _rebuild_blur(self):
            self._blur_scheduled = False
            if self.width() <= 0 or self.height() <= 0:
                return
            # Render background to raw pixmap
            raw = QPixmap(self.size())
            raw.fill(Qt.GlobalColor.transparent)
            p = QPainter(raw)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            self._do_paint(p)
            p.end()
            # Apply Gaussian blur via QGraphicsBlurEffect trick
            scene = QGraphicsScene()
            item = QGraphicsPixmapItem(raw)
            effect = QGraphicsBlurEffect()
            effect.setBlurRadius(20)
            item.setGraphicsEffect(effect)
            scene.addItem(item)
            scene.setSceneRect(QRectF(raw.rect()))
            blurred = QPixmap(raw.size())
            blurred.fill(Qt.GlobalColor.transparent)
            p2 = QPainter(blurred)
            scene.render(p2)
            p2.end()
            self._blur_cache = blurred
            # Trigger repaints on all siblings so GlassFrame cards switch
            # from the solid fallback to the actual blurred background.
            p = self.parent()
            if p is not None:
                p.update()

        def get_blurred_region(self, source_rect):
            """Return blurred bg snippet at source_rect (in self's coords)."""
            if self._blur_cache is None or self._blur_cache.isNull():
                return None
            return self._blur_cache.copy(source_rect)

    class _SizeSync(QObject):
        def __init__(self, bg, cw):
            super().__init__(cw)
            self._bg = bg
        def eventFilter(self, obj, event):
            if event.type() == QEvent.Type.Resize:
                self._bg.setGeometry(obj.rect())
                self._bg._blur_cache = None   # invalidate so paintEvent reschedules rebuild
                self._bg.update()
                self._bg._schedule_blur()
            return False

    cw = w.centralWidget()
    if cw is None:
        return

    # Remove old glass bg if already installed
    old = getattr(w, "_glass_bg_widget", None)
    if old is not None:
        try:
            old.deleteLater()
        except RuntimeError:
            pass
    old_sync = getattr(w, "_glass_bg_sync", None)
    if old_sync is not None:
        try:
            cw.removeEventFilter(old_sync)
        except RuntimeError:
            pass

    # Make centralWidget and direct children not auto-fill background
    cw.setAutoFillBackground(False)
    for child in cw.children():
        if isinstance(child, QWidget):
            child.setAutoFillBackground(False)

    bg = _GlassBg(cw)
    bg.setGeometry(cw.rect())
    bg.show()
    bg.lower()

    sync = _SizeSync(bg, cw)
    cw.installEventFilter(sync)

    setattr(w, "_glass_bg_widget", bg)
    setattr(w, "_glass_bg_sync", sync)


def get_glass_blur_region(widget):
    """Return a blurred QPixmap snippet of the glass background at widget's screen position.

    Used by GlassFrame widgets to simulate CSS backdrop-filter: blur().
    Returns None when not in glass mode or blur cache not yet built.
    """
    if _active_theme != "glass":
        return None
    from PyQt6.QtCore import QRect, QPoint
    win = widget.window()
    bg = getattr(win, "_glass_bg_widget", None)
    if bg is None or not hasattr(bg, "get_blurred_region"):
        return None
    # Map widget top-left to bg's coordinate space
    top_left = widget.mapTo(bg, QPoint(0, 0))
    source = QRect(top_left, widget.size())
    return bg.get_blurred_region(source)


def remove_glass_bg(w: "MainWindow") -> None:
    """Remove the glass background widget and restore autoFillBackground."""
    from PyQt6.QtWidgets import QWidget
    cw = w.centralWidget()

    old = getattr(w, "_glass_bg_widget", None)
    if old is not None:
        try:
            old.deleteLater()
        except RuntimeError:
            pass
        setattr(w, "_glass_bg_widget", None)

    old_sync = getattr(w, "_glass_bg_sync", None)
    if old_sync is not None and cw is not None:
        try:
            cw.removeEventFilter(old_sync)
        except RuntimeError:
            pass
        setattr(w, "_glass_bg_sync", None)

    # Restore autoFillBackground for centralWidget and its children
    if cw is not None:
        cw.setAutoFillBackground(True)
        for child in cw.children():
            if isinstance(child, QWidget):
                child.setAutoFillBackground(True)


def apply_button_shadows(w: MainWindow) -> None:
    _light = _active_theme == "light"
    _glass = _active_theme == "glass"

    def add_shadow(widget, blur=18, alpha=60, dy=3, r=0, g=0, b=0):
        if widget is None:
            return
        effect = QGraphicsDropShadowEffect(widget)
        effect.setBlurRadius(blur)
        effect.setOffset(0, dy)
        effect.setColor(QColor(r, g, b, alpha))
        widget.setGraphicsEffect(effect)

    # Accent glow on the "+ new" button
    glow = QGraphicsDropShadowEffect(w.btn_new)
    if _light:
        glow.setBlurRadius(28); glow.setOffset(0, 4)
        glow.setColor(QColor(59, 130, 246, 160))
    elif _glass:
        glow.setBlurRadius(32); glow.setOffset(0, 6)
        glow.setColor(QColor(94, 162, 255, 140))
    else:
        glow.setBlurRadius(22); glow.setOffset(0, 2)
        glow.setColor(QColor(10, 132, 255, 120))
    w.btn_new.setGraphicsEffect(glow)

    from PyQt6.QtWidgets import QFrame
    if _light:
        add_shadow(w.search, blur=18, alpha=32, dy=3, r=15, g=23, b=42)
        add_shadow(w.list,   blur=32, alpha=50, dy=6, r=15, g=23, b=42)
        fp = getattr(w, "_finance_page", None)
        if fp is not None:
            for name in ("FinKpiCard", "FinSectionCard", "FinDonutCard", "FinAccountCard",
                         "FinGoalCard", "FinBudgetCard"):
                for card in fp.findChildren(QFrame, name):
                    add_shadow(card, blur=22, alpha=28, dy=5, r=70, g=90, b=130)
    elif _glass:
        # Glass: larger, deeper shadows for elevated frosted panels
        add_shadow(w.search, blur=24, alpha=55, dy=6, r=0, g=0, b=0)
        add_shadow(w.list,   blur=44, alpha=70, dy=10, r=0, g=0, b=0)
        fp = getattr(w, "_finance_page", None)
        if fp is not None:
            for name in ("FinKpiCard", "FinSectionCard", "FinDonutCard", "FinAccountCard",
                         "FinGoalCard", "FinBudgetCard"):
                for card in fp.findChildren(QFrame, name):
                    add_shadow(card, blur=28, alpha=55, dy=8, r=0, g=0, b=0)
    else:
        add_shadow(w.search, blur=14, alpha=40, dy=2)
        add_shadow(w.list,   blur=24, alpha=50, dy=4)

    # No heavy shadows on filter pills — keep them flat/glass
    flat = [w.btn_all, w.btn_active, w.btn_done, w.btn_delete, w.sort_combo]
    if hasattr(w, "btn_analytics"):
        flat.append(w.btn_analytics)
    if hasattr(w, "btn_reminder"):
        flat.append(w.btn_reminder)
    if hasattr(w, "btn_deadline"):
        flat.append(w.btn_deadline)
    if hasattr(w, "btn_settings"):
        flat.append(w.btn_settings)
    for widget in flat:
        widget.setGraphicsEffect(None)


def force_white_text(w: MainWindow) -> None:
    _th           = _THEMES[_active_theme]
    text_col      = QColor(_th["text"])
    placeholder   = QColor(_th["text_sec"])
    base          = QColor(_th["bg_combo"])
    accent        = QColor(_th["accent"])
    accent.setAlpha(110)
    hi_text       = QColor("#ffffff")          # text on selection always white

    def fix(widget):
        pal = widget.palette()
        for g in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive, QPalette.ColorGroup.Disabled):
            pal.setColor(g, QPalette.ColorRole.Text, text_col)
            pal.setColor(g, QPalette.ColorRole.PlaceholderText, placeholder)
            pal.setColor(g, QPalette.ColorRole.Base, base)
            pal.setColor(g, QPalette.ColorRole.Window, base)
            pal.setColor(g, QPalette.ColorRole.Highlight, accent)
            pal.setColor(g, QPalette.ColorRole.HighlightedText, hi_text)
        widget.setPalette(pal)

    for widget in (w.search, w.list, w.editor_title, w.editor_desc, w.sort_combo):
        fix(widget)
