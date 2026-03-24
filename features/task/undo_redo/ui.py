"""HistoryMixin — application-level undo/redo stack with toast notifications."""
from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt

from shared.i18n import tr


class HistoryMixin:
    """Undo/redo stack for task-level operations.

    Usage:
        After performing an operation, call:
            self._push_action(label, undo_fn, redo_fn)
        Both functions must be zero-argument callables that reverse / re-apply
        the operation and leave the DB in the correct state.  The mixin calls
        _post_history_refresh() afterwards, so the UI always catches up.
    """

    _MAX_HISTORY: int = 50

    # ── initialisation ────────────────────────────────────────────────

    def _init_history(self) -> None:
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []

    # ── public API ────────────────────────────────────────────────────

    def _push_action(self, label: str, undo_fn, redo_fn) -> None:
        """Record an undoable action; clears the redo stack."""
        self._undo_stack.append({"label": label, "undo_fn": undo_fn, "redo_fn": redo_fn})
        if len(self._undo_stack) > self._MAX_HISTORY:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def on_undo(self) -> None:
        # If description editor is focused, delegate to QTextEdit's built-in undo
        if hasattr(self, "editor_desc") and self.editor_desc.hasFocus():
            self.editor_desc.undo()
            return
        if not self._undo_stack:
            return
        action = self._undo_stack.pop()
        self._redo_stack.append(action)
        try:
            action["undo_fn"]()
        except Exception as e:
            self.show_error(str(e))
            return
        self._post_history_refresh()
        self._show_toast(tr("history.undone", label=action["label"]))

    def on_redo(self) -> None:
        if hasattr(self, "editor_desc") and self.editor_desc.hasFocus():
            self.editor_desc.redo()
            return
        if not self._redo_stack:
            return
        action = self._redo_stack.pop()
        self._undo_stack.append(action)
        try:
            action["redo_fn"]()
        except Exception as e:
            self.show_error(str(e))
            return
        self._post_history_refresh()
        self._show_toast(tr("history.redone", label=action["label"]))

    # ── internals ─────────────────────────────────────────────────────

    def _post_history_refresh(self) -> None:
        self.all_tasks = self.svc.list_tasks()
        self.apply_filter(keep_selection=True)
        if hasattr(self, "_refresh_analytics_if_visible"):
            self._refresh_analytics_if_visible()

    def _show_toast(self, text: str) -> None:
        if not hasattr(self, "_toast_label"):
            return
        lbl: QLabel = self._toast_label
        lbl.setText(text)
        lbl.adjustSize()
        self._reposition_toast()
        lbl.show()
        lbl.raise_()
        QTimer.singleShot(2200, lbl.hide)

    def _reposition_toast(self) -> None:
        if not hasattr(self, "_toast_label"):
            return
        lbl: QLabel = self._toast_label
        cw = self.centralWidget()
        if not cw:
            return
        lbl.move(
            cw.width() // 2 - lbl.width() // 2,
            cw.height() - lbl.height() - 28,
        )
