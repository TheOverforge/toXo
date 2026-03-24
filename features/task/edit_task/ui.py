"""EditorMixin — editor load/save, priority, pin, recurrence, subtasks, reminders, deadlines."""
from __future__ import annotations

from PyQt6.QtWidgets import QListWidgetItem, QDialog
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCharFormat, QTextCursor

from shared.i18n import tr


class EditorMixin:
    """Mixin: editor, priority/pin/recurrence, subtasks, reminders, deadlines."""

    # ---------------- editor ----------------
    def load_task_into_editor(self, t):
        self._block_editor_signals = True
        self.btn_back_to_calendar.hide()
        try:
            if t is None:
                self.show_empty_right()
                return

            self.current_task_id = t.id
            self._dirty = False

            self.editor_title.setText(t.title or "")
            status = tr("editor.done") if t.is_done else tr("editor.undone")
            self.editor_meta.setText(f"{status} • {tr('editor.created', date=self._format_meta_full(t))}")
            self._saved_desc_cursor = None
            self.editor_desc.set_content(t.description or "")
            self._update_reminder_label(t)
            self._update_deadline_label(t)
            self._set_priority_buttons(t.priority)
            self.btn_pin.setChecked(t.is_pinned)
            self.btn_pin.setText(tr("editor.pinned_btn") if t.is_pinned else tr("editor.pin_btn"))
            self.rec_combo.blockSignals(True)
            rec_idx = {"daily": 1, "weekly": 2, "monthly": 3}.get(t.recurrence or "", 0)
            self.rec_combo.setCurrentIndex(rec_idx)
            self.rec_combo.blockSignals(False)
            self._reload_subtasks(t.id)
            self.tags_input.blockSignals(True)
            self.tags_input.setText(t.tags or "")
            self.tags_input.blockSignals(False)
        finally:
            self._block_editor_signals = False

        self.show_editor_right()

    def on_editor_changed(self):
        if self._block_editor_signals or self.current_task_id is None:
            return
        self._dirty = True
        it = self.list.currentItem()
        if it is not None:
            title = (self.editor_title.text() or "").strip() or tr("editor.untitled")
            self._populating_list = True
            try:
                it.setText(title)
            finally:
                self._populating_list = False

    def save_current_task_if_dirty(self):
        if self.current_task_id is None or self._block_editor_signals:
            return
        if not self._dirty:
            return

        try:
            title = self.editor_title.text().strip()
            desc = self.editor_desc.get_content()

            old_t = self.svc.get_task(self.current_task_id)
            old_title = (old_t.title or "") if old_t else title
            old_desc = (old_t.description or "") if old_t else desc

            self.svc.update_task(self.current_task_id, title, desc)
            self._dirty = False

            if title != old_title or desc != old_desc:
                _tid = self.current_task_id
                from shared.i18n import tr as _tr

                def _undo_edit(_tid=_tid, old_title=old_title, old_desc=old_desc):
                    self.svc.update_task(_tid, old_title, old_desc)
                    if self.current_task_id == _tid:
                        self._block_editor_signals = True
                        try:
                            self.editor_title.setText(old_title)
                            self.editor_desc.set_content(old_desc)
                        finally:
                            self._block_editor_signals = False
                        self._dirty = False

                def _redo_edit(_tid=_tid, title=title, desc=desc):
                    self.svc.update_task(_tid, title, desc)
                    if self.current_task_id == _tid:
                        self._block_editor_signals = True
                        try:
                            self.editor_title.setText(title)
                            self.editor_desc.set_content(desc)
                        finally:
                            self._block_editor_signals = False
                        self._dirty = False

                self._push_action(_tr("history.edit"), _undo_edit, _redo_edit)

            it = self.list.currentItem()
            if it is not None:
                t = self.svc.get_task(self.current_task_id)
                if t:
                    self._update_item_display(it, t)

            self.all_tasks = self.svc.list_tasks()
        except Exception as e:
            self.show_error(str(e))

    # ---------------- description font ----------------
    def _toggle_desc_font_panel(self):
        if self._desc_font_panel.isVisible():
            self._desc_font_panel.hide()
            return
        btn = self._desc_font_btn
        sh = self._desc_font_panel.sizeHint()
        pw = max(sh.width(), btn.width())
        ph = max(sh.height(), 80)
        # btn is embedded in main window — mapToGlobal works correctly here
        gp = btn.mapToGlobal(btn.rect().bottomLeft())
        x = gp.x()
        y = gp.y() + 2
        if btn.screen():
            sg = btn.screen().availableGeometry()
            x = max(sg.left() + 4, min(x, sg.right() - pw - 4))
            if y + ph > sg.bottom() - 4:
                y = btn.mapToGlobal(btn.rect().topLeft()).y() - ph - 2
        self._desc_font_panel.show_animated(x, y, source_btn=btn)

    def _on_desc_font_chosen(self, family: str):
        self._desc_font_panel.hide()
        self._desc_font_btn.setText(family)
        self._apply_desc_font()

    def _on_desc_selection_changed(self):
        if self._block_editor_signals:
            return
        cursor = self.editor_desc.textCursor()
        if cursor.hasSelection():
            self._saved_desc_cursor = QTextCursor(cursor)

    def _sync_font_toolbar(self, cursor=None):
        if not hasattr(self, '_desc_font_btn'):
            return
        if cursor is None:
            cursor = self.editor_desc.textCursor()
        cf = cursor.charFormat()
        fam = cf.fontFamily()
        fsz = int(cf.fontPointSize())
        if fam:
            self._desc_font_btn.setText(fam)
        if fsz > 0:
            self._desc_size_lbl.setText(str(fsz))

    def _apply_desc_font(self):
        # Use saved selection — clicking toolbar steals focus and drops selection
        cursor = self.editor_desc.textCursor()
        if not cursor.hasSelection() and getattr(self, "_saved_desc_cursor", None):
            cursor = QTextCursor(self._saved_desc_cursor)

        if not cursor.hasSelection():
            return  # nothing selected — do nothing

        family = self._desc_font_btn.text()
        size = int(self._desc_size_lbl.text())

        fmt = QTextCharFormat()
        fmt.setFontFamily(family)
        fmt.setFontPointSize(float(size))

        cursor.mergeCharFormat(fmt)
        self.editor_desc.setTextCursor(cursor)

    def _change_desc_size(self, delta: int):
        size = max(8, min(48, int(self._desc_size_lbl.text()) + delta))
        self._desc_size_lbl.setText(str(size))
        self._apply_desc_font()

    def _clear_desc_format(self):
        """Remove all inline character formatting from the selection (or whole document)."""
        cursor = self.editor_desc.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.Document)
        cursor.setCharFormat(QTextCharFormat())
        self.editor_desc.setTextCursor(cursor)
        self.editor_desc.setFocus()

    # ---------------- list interactions ----------------
    def on_selection_changed(self):
        if self._populating_list:
            return
        selected = self.list.selectedItems()
        count = len(selected)
        if count == 0:
            self.save_current_task_if_dirty()
            self.show_empty_right()
        elif count == 1:
            self.save_current_task_if_dirty()
            try:
                task_id = int(selected[0].data(Qt.ItemDataRole.UserRole))
            except Exception:
                self.show_empty_right()
                return
            self.load_task_into_editor(self.svc.get_task(task_id))
        else:
            self.save_current_task_if_dirty()
            self.current_task_id = None
            self._show_bulk_page(count)

    def on_list_item_changed(self, item: QListWidgetItem):
        if self._populating_list or self._inline_editing:
            return
        try:
            task_id = int(item.data(Qt.ItemDataRole.UserRole))
        except Exception:
            return

        want_done = (item.checkState() == Qt.CheckState.Checked)
        try:
            if self.current_task_id == task_id:
                self.save_current_task_if_dirty()

            self.svc.set_done(task_id, want_done)

            t = self.svc.get_task(task_id)
            if t:
                self._update_item_display(item, t)

                if self.current_task_id == task_id:
                    self._block_editor_signals = True
                    try:
                        status = tr("editor.done") if t.is_done else tr("editor.undone")
                        self.editor_meta.setText(f"{status} • {tr('editor.created', date=self._format_meta_full(t))}")
                    finally:
                        self._block_editor_signals = False

            self.all_tasks = self.svc.list_tasks()
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.apply_filter(keep_selection=True))
            self._refresh_analytics_if_visible()
        except Exception as e:
            self.show_error(str(e))

    # ── Priority / Pin / Recurrence ──────────────────────

    def _set_priority_buttons(self, priority: int):
        self._block_editor_signals = True
        try:
            self.btn_pri_none.setChecked(priority == 0)
            self.btn_pri_low.setChecked(priority == 1)
            self.btn_pri_med.setChecked(priority == 2)
            self.btn_pri_high.setChecked(priority == 3)
        finally:
            self._block_editor_signals = False

    def on_priority_changed(self, priority: int):
        if self._block_editor_signals or self.current_task_id is None:
            return
        try:
            self.svc.set_priority(self.current_task_id, priority)
            self._set_priority_buttons(priority)
            it = self.list.currentItem()
            if it:
                it.setData(Qt.ItemDataRole.UserRole + 3, priority)
            self.all_tasks = self.svc.list_tasks()
        except Exception as e:
            self.show_error(str(e))

    def on_pin_clicked(self):
        if self.current_task_id is None:
            return
        is_pinned = self.btn_pin.isChecked()
        try:
            self.svc.set_pinned(self.current_task_id, is_pinned)
            self.btn_pin.setText(tr("editor.pinned_btn") if is_pinned else tr("editor.pin_btn"))
            it = self.list.currentItem()
            if it:
                it.setData(Qt.ItemDataRole.UserRole + 4, is_pinned)
            self.all_tasks = self.svc.list_tasks()
            self.apply_filter(keep_selection=True)
        except Exception as e:
            self.show_error(str(e))

    def on_recurrence_changed(self, _idx: int):
        if self._block_editor_signals or self.current_task_id is None:
            return
        rec = self.rec_combo.currentData()
        try:
            self.svc.set_recurrence(self.current_task_id, rec)
        except Exception as e:
            self.show_error(str(e))

    # ── Subtasks ──────────────────────────────────────────

    def _clear_subtasks_ui(self):
        self.subtask_list.clear()

    def _apply_subtask_progress(self, subs: list) -> None:
        total = len(subs)
        done = sum(1 for s in subs if s["is_done"])
        self.subtask_progress.setMaximum(max(total, 1))
        self.subtask_progress.setValue(done)
        self.subtask_progress.setVisible(total > 0)
        label = tr("editor.subtasks_title")
        self.lbl_subtasks.setText(f"{label}  {done}/{total}" if total > 0 else label)

    def _update_subtask_progress(self) -> None:
        if self.current_task_id is None:
            self._apply_subtask_progress([])
            return
        try:
            subs = self.svc.list_subtasks(self.current_task_id)
        except Exception:
            return
        self._apply_subtask_progress(subs)

    def _reload_subtasks(self, task_id: int):
        self._clear_subtasks_ui()
        try:
            subs = self.svc.list_subtasks(task_id)
        except Exception:
            self._apply_subtask_progress([])
            return
        for sub in subs:
            self._add_subtask_row(sub)
        self._apply_subtask_progress(subs)

    def _add_subtask_row(self, sub: dict):
        from PyQt6.QtWidgets import QListWidgetItem as _LWI
        item = _LWI()
        item.setData(Qt.ItemDataRole.DisplayRole, sub["title"])
        item.setData(Qt.ItemDataRole.UserRole, sub["id"])
        item.setData(Qt.ItemDataRole.UserRole + 1, bool(sub["is_done"]))
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable)
        self.subtask_list.addItem(item)

    def _refresh_item_subtask_badge(self, task_id: int) -> None:
        self._subtask_counts = self.svc.subtask_counts_all()
        it = self.list.currentItem()
        if it and int(it.data(Qt.ItemDataRole.UserRole)) == task_id:
            it.setData(Qt.ItemDataRole.UserRole + 6, self._subtask_counts.get(task_id))
            self.list.viewport().update()

    def on_add_subtask(self):
        if self.current_task_id is None:
            return
        title = self.subtask_input.text().strip()
        if not title:
            return
        try:
            self.svc.add_subtask(self.current_task_id, title)
            self.subtask_input.clear()
            self._reload_subtasks(self.current_task_id)
            self._refresh_item_subtask_badge(self.current_task_id)
        except Exception as e:
            self.show_error(str(e))

    def _on_subtask_toggle(self, subtask_id: int, checked: bool):
        try:
            self.svc.set_subtask_done(subtask_id, checked)
            if self.current_task_id:
                self._reload_subtasks(self.current_task_id)
                self._refresh_item_subtask_badge(self.current_task_id)
        except Exception as e:
            self.show_error(str(e))

    def _on_subtask_toggle_by_id(self, sub_id: int):
        for i in range(self.subtask_list.count()):
            it = self.subtask_list.item(i)
            if it is not None and it.data(Qt.ItemDataRole.UserRole) == sub_id:
                is_done = bool(it.data(Qt.ItemDataRole.UserRole + 1))
                self._on_subtask_toggle(sub_id, not is_done)
                return

    def _on_subtask_rename(self, subtask_id: int, title: str):
        title = title.strip()
        if not title:
            return
        try:
            self.svc.update_subtask_title(subtask_id, title)
        except Exception as e:
            self.show_error(str(e))

    def _on_subtask_delete(self, subtask_id: int, _row_widget=None):
        try:
            self.svc.delete_subtask(subtask_id)
            if self.current_task_id:
                self._reload_subtasks(self.current_task_id)
                self._refresh_item_subtask_badge(self.current_task_id)
        except Exception as e:
            self.show_error(str(e))

    def _on_subtask_reordered(self, id_order: list):
        if not id_order or self.current_task_id is None:
            return
        try:
            self.svc.reorder_subtasks(id_order)
        except Exception as e:
            self.show_error(str(e))

    # ── Tags ──────────────────────────────────────────────

    def on_tags_changed(self):
        if self.current_task_id is None:
            return
        raw = self.tags_input.text().strip()
        parts = [t.strip().lstrip("#").lower() for t in raw.split(",") if t.strip()]
        tags = ",".join(parts)
        self.tags_input.blockSignals(True)
        self.tags_input.setText(tags)
        self.tags_input.blockSignals(False)
        try:
            self.svc.set_tags(self.current_task_id, tags)
            self.all_tasks = self.svc.list_tasks()
        except Exception as e:
            self.show_error(str(e))

    # ── Reminders / Deadlines ─────────────────────────────

    def on_reminder_btn_clicked(self):
        if self.current_task_id is None:
            return
        task = self.svc.get_task(self.current_task_id)
        if not task:
            return
        self.save_current_task_if_dirty()
        from shared.ui.dialogs import ReminderDialog
        dlg = ReminderDialog(current_remind_at=task.remind_at, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_remind_at = dlg.get_remind_at()
            try:
                self.svc.set_reminder(self.current_task_id, new_remind_at)
                updated = self.svc.get_task(self.current_task_id)
                if updated:
                    self._update_reminder_label(updated)
                self.all_tasks = self.svc.list_tasks()
            except Exception as e:
                self.show_error(str(e))

    def _update_reminder_label(self, t):
        if t.remind_at:
            local_str = self._utc_to_local(t.remind_at)
            self.btn_reminder.setText(f"🔔 {local_str}")
            if t.remind_shown:
                self.btn_reminder.setStyleSheet(
                    "QPushButton#ReminderBtn { color: #48484a; border-color: rgba(255,255,255,0.08); }"
                )
            else:
                self.btn_reminder.setStyleSheet(
                    "QPushButton#ReminderBtn { color: #0a84ff; border-color: rgba(10,132,255,0.5); }"
                )
        else:
            self.btn_reminder.setText(tr("editor.reminder_btn"))
            self.btn_reminder.setStyleSheet("")

    def on_deadline_btn_clicked(self):
        if self.current_task_id is None:
            return
        task = self.svc.get_task(self.current_task_id)
        if not task:
            return
        self.save_current_task_if_dirty()
        from shared.ui.dialogs import ReminderDialog
        dlg = ReminderDialog(current_remind_at=task.deadline_at, mode="deadline", parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_deadline = dlg.get_remind_at()
            try:
                self.svc.set_deadline(self.current_task_id, new_deadline)
                updated = self.svc.get_task(self.current_task_id)
                if updated:
                    self._update_deadline_label(updated)
                self.all_tasks = self.svc.list_tasks()
                if updated:
                    for _i in range(self.list.count()):
                        _it = self.list.item(_i)
                        if _it is not None and int(_it.data(Qt.ItemDataRole.UserRole)) == updated.id:
                            self._update_item_display(_it, updated)
                            self.list.viewport().update()
                            break
            except Exception as e:
                self.show_error(str(e))

    def _update_deadline_label(self, t):
        if not t.deadline_at:
            self.btn_deadline.setText(tr("editor.deadline_btn"))
            self.btn_deadline.setStyleSheet("")
            return
        local_str = self._utc_to_local(t.deadline_at)
        from datetime import datetime, timezone, date
        try:
            dl = datetime.fromisoformat(t.deadline_at)
            if dl.tzinfo is None:
                dl = dl.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            dl_local_date = dl.astimezone().date()
            today = date.today()
            if dl <= now:
                self.btn_deadline.setText(f"⏰ {local_str}")
                self.btn_deadline.setStyleSheet(
                    "QPushButton#DeadlineBtn { color: #ff453a; border-color: rgba(255,69,58,0.5); "
                    "background-color: rgba(255,69,58,0.12); }"
                )
            elif dl_local_date == today:
                self.btn_deadline.setText(f"⏰ {local_str}")
                self.btn_deadline.setStyleSheet(
                    "QPushButton#DeadlineBtn { color: #ff9f0a; border-color: rgba(255,159,10,0.5); "
                    "background-color: rgba(255,159,10,0.15); }"
                )
            else:
                self.btn_deadline.setText(f"⏰ {local_str}")
                self.btn_deadline.setStyleSheet(
                    "QPushButton#DeadlineBtn { color: #98989d; border-color: rgba(152,152,157,0.35); }"
                )
        except Exception:
            self.btn_deadline.setText(f"⏰ {local_str}")
            self.btn_deadline.setStyleSheet("")
