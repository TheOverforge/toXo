"""TasksMixin — task CRUD, navigation, bulk ops, import/export."""
from __future__ import annotations

from PyQt6.QtWidgets import QMenu, QMessageBox, QCheckBox, QListWidgetItem
from PyQt6.QtCore import Qt, QTimer

from shared.i18n import tr, current_language


class TasksMixin:
    """Mixin: rename, create, quick-add, duplicate, context menu, delete, bulk, archive,
    escape, reorder, toggle-done, navigate, import/export, task ··· menu."""

    def rename_task(self):
        it = self.list.currentItem()
        if it is None:
            return
        self.save_current_task_if_dirty()
        self._inline_editing = True
        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsEditable)
        self.list.editItem(it)

    def create_new_task(self):
        try:
            self.save_current_task_if_dirty()
            new_id = self.svc.create_task("", "")
            self.refresh()
            self._refresh_analytics_if_visible()
            self._select_item_by_id(new_id)
            self.load_task_into_editor(self.svc.get_task(new_id))

            it = self.list.currentItem()
            if it:
                self._inline_editing = True
                self._populating_list = True
                try:
                    it.setText("")
                    it.setFlags(it.flags() | Qt.ItemFlag.ItemIsEditable)
                finally:
                    self._populating_list = False
                self.list.editItem(it)
        except Exception as e:
            self.show_error(str(e))

    def on_quick_add(self):
        title = self.quick_add.text().strip()
        if not title:
            return
        try:
            self.save_current_task_if_dirty()
            cat_id = self.current_category_id if (self.current_category_id or 0) > 0 else None
            new_id = self.svc.create_task(title, "")
            if cat_id:
                self.svc.db.move_task_to_category(new_id, cat_id)
            self.quick_add.clear()
            self.all_tasks = self.svc.list_tasks()
            self._subtask_counts = self.svc.subtask_counts_all()
            self.apply_filter(keep_selection=True)
            self._select_item_by_id(new_id)
        except Exception as e:
            self.show_error(str(e))

    def duplicate_task(self):
        task_id = self.selected_task_id()
        if task_id is None:
            return
        try:
            self.save_current_task_if_dirty()
            new_id = self.svc.duplicate_task(task_id)
            if new_id is None:
                return
            self.refresh()
            self._select_item_by_id(new_id)
            self.load_task_into_editor(self.svc.get_task(new_id))
        except Exception as e:
            self.show_error(str(e))

    def show_list_context_menu(self, pos):
        menu = QMenu(self)
        task_ids = self.selected_task_ids()
        count = len(task_ids)

        if count > 1:
            noun = self._task_noun(count)
            action_done = menu.addAction(tr("ctx.done_n", count=count, noun=noun))
            action_undone = menu.addAction(tr("ctx.undone_n", count=count, noun=noun))
            menu.addSeparator()
            move_menu = menu.addMenu(tr("ctx.move_to_cat"))
            move_none = move_menu.addAction(tr("ctx.no_category"))
            if self.categories:
                move_menu.addSeparator()
                for cat in self.categories:
                    a = move_menu.addAction(cat.name)
                    a.setData(cat.id)
            menu.addSeparator()
            action_del = menu.addAction(tr("ctx.delete_n", count=count, noun=noun))
            action = menu.exec(self.list.mapToGlobal(pos))
            if action == action_done:
                self.bulk_mark_done(True)
            elif action == action_undone:
                self.bulk_mark_done(False)
            elif action == action_del:
                self.bulk_delete()
            elif action is not None and action.parent() == move_menu:
                category_id = None if action == move_none else action.data()
                try:
                    for tid in task_ids:
                        self.category_svc.set_task_category(tid, category_id)
                    self.refresh()
                    self.refresh_categories()
                except Exception as e:
                    self.show_error(str(e))
            return

        action_new = menu.addAction(tr("ctx.new_task"))
        action_dup = menu.addAction(tr("ctx.duplicate"))
        action_toggle = menu.addAction(tr("ctx.toggle"))
        task_id = task_ids[0] if task_ids else None
        has_item = task_id is not None

        action_pin = None
        action_archive = None
        action_unarchive = None
        action_del_forever = None
        t_ctx = None
        if has_item:
            t_ctx = self.svc.get_task(task_id)
            if t_ctx:
                if t_ctx.is_archived:
                    action_unarchive = menu.addAction(tr("ctx.unarchive"))
                    action_del_forever = menu.addAction(tr("archive.delete_forever"))
                else:
                    action_pin = menu.addAction(tr("ctx.unpin") if t_ctx.is_pinned else tr("ctx.pin"))
                    move_menu = menu.addMenu(tr("ctx.move_to"))
                    no_cat_action = move_menu.addAction(tr("ctx.no_category"))
                    no_cat_action.triggered.connect(lambda: self.move_task_to_category(task_id, None))
                    move_menu.addSeparator()
                    for cat in self.categories:
                        cat_action = move_menu.addAction(cat.name)
                        cat_action.triggered.connect(lambda checked, cid=cat.id: self.move_task_to_category(task_id, cid))
                    action_archive = menu.addAction(tr("ctx.archive"))

        action_move_to_cal = None
        if (has_item and t_ctx and not t_ctx.is_archived
                and self.right_stack.currentIndex() == 4):
            cal_date = self.calendar_page.selected_date
            date_str = f"{cal_date.day:02d}.{cal_date.month:02d}.{cal_date.year}"
            menu.addSeparator()
            action_move_to_cal = menu.addAction(tr("ctx.move_deadline_cal", date=date_str))

        menu.addSeparator()
        action_delete = menu.addAction(tr("ctx.delete"))

        action_dup.setEnabled(has_item)
        action_toggle.setEnabled(has_item and (t_ctx is None or not t_ctx.is_archived))
        action_delete.setEnabled(has_item)

        action = menu.exec(self.list.mapToGlobal(pos))
        if action is None:
            return
        if action == action_new:
            self.create_new_task()
        elif action == action_dup:
            self.duplicate_task()
        elif action == action_toggle:
            if has_item:
                t = self.svc.get_task(task_id)
                if t:
                    self.svc.set_done(task_id, not t.is_done)
                    self.refresh()
                    self._refresh_analytics_if_visible()
        elif action_pin and action == action_pin:
            if has_item and t_ctx:
                new_pin = not t_ctx.is_pinned
                try:
                    self.svc.set_pinned(task_id, new_pin)
                    self.all_tasks = self.svc.list_tasks()
                    self.apply_filter(keep_selection=True)
                    if self.current_task_id == task_id:
                        self.btn_pin.setChecked(new_pin)
                        self.btn_pin.setText(tr("editor.pinned_btn") if new_pin else tr("editor.pin_btn"))
                except Exception as e:
                    self.show_error(str(e))
        elif action_archive and action == action_archive:
            self._archive_selected(True)
        elif action_unarchive and action == action_unarchive:
            self._archive_selected(False)
        elif action_del_forever and action == action_del_forever:
            self._delete_selected_forever()
        elif action_move_to_cal and action == action_move_to_cal:
            from datetime import datetime, timezone as _tz
            d = self.calendar_page.selected_date
            iso = datetime(d.year, d.month, d.day, 9, 0, tzinfo=_tz.utc).isoformat(timespec="seconds")
            try:
                self.svc.set_deadline(task_id, iso)
                self.all_tasks = self.svc.list_tasks()
                self.apply_filter(keep_selection=True)
                self.calendar_page.refresh(self.all_tasks, self.categories)
            except Exception as e:
                self.show_error(str(e))
        elif action == action_delete:
            self.on_delete()

    def on_delete(self):
        task_ids = self.selected_task_ids()
        if not task_ids:
            return
        if len(task_ids) > 1:
            self.bulk_delete()
            return
        task_id = task_ids[0]
        t = self.svc.get_task(task_id)
        if not t:
            return

        if self._confirm_delete:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle(tr("dlg.del_task_title"))
            title = (t.title or tr("editor.untitled")).strip()
            if len(title) > 60:
                title = title[:57] + "..."
            box.setText(tr("dlg.del_task_text", title=title))
            box.setInformativeText(tr("dlg.del_task_hint"))
            box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            box.setDefaultButton(QMessageBox.StandardButton.No)

            cb = QCheckBox(tr("dlg.dont_ask"))
            box.setCheckBox(cb)

            box.setStyleSheet("""
                QMessageBox { background: #1c1c1e; color: #f5f5f7; }
                QLabel { color: #f5f5f7; }
                QCheckBox { color: #98989d; padding-top: 6px; }
                QCheckBox::indicator {
                    width: 18px; height: 18px;
                    border-radius: 4px;
                    border: 1.5px solid #48484a;
                    background: transparent;
                }
                QCheckBox::indicator:checked {
                    background: #0a84ff;
                    border-color: #0a84ff;
                }
                QPushButton {
                    background: rgba(255,255,255,0.07);
                    border: 1px solid rgba(255,255,255,0.12);
                    padding: 8px 16px;
                    border-radius: 12px;
                    color: #f5f5f7;
                    min-width: 90px;
                    font-weight: 500;
                }
                QPushButton:hover { background: rgba(255,255,255,0.12); }
            """)

            res = box.exec()
            if cb.isChecked():
                self._confirm_delete = False
                self._settings.setValue("confirm_delete", False)
            if res != QMessageBox.StandardButton.Yes:
                return

        try:
            self.save_current_task_if_dirty()
            snap = t.__dict__.copy()
            state = {"tid": task_id}

            def _undo_del(snap=snap, state=state):
                new_id = self.svc.restore_task(snap)
                state["tid"] = new_id
                self.all_tasks = self.svc.list_tasks()
                if hasattr(self, "_subtask_counts"):
                    self._subtask_counts = self.svc.subtask_counts_all()
                self.apply_filter(keep_selection=False)
                self._select_item_by_id(new_id)

            def _redo_del(state=state):
                self.svc.delete_task(state["tid"])
                self.show_empty_right()

            self._push_action(tr("history.delete"), _undo_del, _redo_del)
            self.svc.delete_task(task_id)
            self.refresh()
            self._refresh_analytics_if_visible()
            self.show_empty_right()
        except Exception as e:
            self.show_error(str(e))

    def undo_delete(self):
        if not self.svc.can_undo():
            return
        try:
            new_id = self.svc.undo_delete()
            if new_id is None:
                return
            self.refresh()
            self._refresh_analytics_if_visible()
            self._select_item_by_id(new_id)
            self.load_task_into_editor(self.svc.get_task(new_id))
        except Exception as e:
            self.show_error(str(e))

    def select_all_tasks(self):
        self.list.selectAll()

    def _task_noun(self, n: int) -> str:
        if current_language() == "en":
            return tr("noun.task1") if n == 1 else tr("noun.task5")
        if 11 <= n % 100 <= 19:
            return tr("noun.task5")
        r = n % 10
        if r == 1:
            return tr("noun.task1")
        if 2 <= r <= 4:
            return tr("noun.task2")
        return tr("noun.task5")

    def _show_bulk_page(self, count: int):
        self.lbl_bulk_count.setText(tr("bulk.selected", count=count, noun=self._task_noun(count)))
        self.btn_analytics.setChecked(False)
        self.btn_calendar.setChecked(False)
        self.right_stack.setCurrentIndex(3)

    def bulk_mark_done(self, done: bool):
        task_ids = self.selected_task_ids()
        if not task_ids:
            return
        try:
            for tid in task_ids:
                self.svc.set_done(tid, done)
            self.refresh()
            self._refresh_analytics_if_visible()
        except Exception as e:
            self.show_error(str(e))

    def bulk_move_to_category(self):
        task_ids = self.selected_task_ids()
        if not task_ids:
            return

        from PyQt6.QtCore import QPoint
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #1c1c1e;
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 10px;
                color: #f5f5f7;
                font-size: 13px;
                padding: 4px 0;
            }
            QMenu::item { padding: 6px 20px; }
            QMenu::item:selected { background: rgba(10,132,255,0.35); }
            QMenu::separator { height: 1px; background: rgba(255,255,255,0.1); margin: 4px 0; }
        """)

        action_none = menu.addAction(tr("ctx.no_category"))
        if self.categories:
            menu.addSeparator()
            for cat in self.categories:
                act = menu.addAction(cat.name)
                act.setData(cat.id)

        btn_pos = self.btn_bulk_move.mapToGlobal(QPoint(0, self.btn_bulk_move.height()))
        action = menu.exec(btn_pos)
        if action is None:
            return

        category_id = None if action == action_none else action.data()
        try:
            for tid in task_ids:
                self.category_svc.set_task_category(tid, category_id)
            self.refresh()
            self.refresh_categories()
            self._show_bulk_page(len(task_ids))
        except Exception as e:
            self.show_error(str(e))

    def bulk_delete(self):
        task_ids = self.selected_task_ids()
        if not task_ids:
            return
        count = len(task_ids)
        noun = self._task_noun(count)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(tr("dlg.del_tasks_title"))
        box.setText(tr("dlg.del_tasks_text", count=count, noun=noun))
        box.setInformativeText(tr("dlg.del_tasks_hint"))
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        box.setStyleSheet("""
            QMessageBox { background: #1c1c1e; color: #f5f5f7; }
            QLabel { color: #f5f5f7; }
            QPushButton {
                background: rgba(255,255,255,0.07);
                border: 1px solid rgba(255,255,255,0.12);
                padding: 8px 16px; border-radius: 12px;
                color: #f5f5f7; min-width: 90px; font-weight: 500;
            }
            QPushButton:hover { background: rgba(255,255,255,0.12); }
        """)
        if box.exec() == QMessageBox.StandardButton.Yes:
            try:
                snaps = []
                for tid in task_ids:
                    t = self.svc.get_task(tid)
                    if t:
                        snaps.append(t.__dict__.copy())
                ids_state = {"ids": list(task_ids)}

                def _undo_bulk(snaps=snaps, ids_state=ids_state):
                    new_ids = [self.svc.restore_task(s) for s in snaps]
                    ids_state["ids"] = new_ids
                    self.all_tasks = self.svc.list_tasks()
                    if hasattr(self, "_subtask_counts"):
                        self._subtask_counts = self.svc.subtask_counts_all()
                    self.apply_filter(keep_selection=False)

                def _redo_bulk(ids_state=ids_state):
                    for tid in ids_state["ids"]:
                        self.svc.delete_task(tid)
                    self.show_empty_right()

                self._push_action(tr("history.delete"), _undo_bulk, _redo_bulk)
                for tid in task_ids:
                    self.svc.delete_task(tid)
                self.refresh()
                self._refresh_analytics_if_visible()
                self.show_empty_right()
            except Exception as e:
                self.show_error(str(e))

    def _archive_selected(self, archived: bool):
        ids = self.selected_task_ids()
        if not ids:
            return
        try:
            for tid in ids:
                self.svc.archive_task(tid, archived)
            self.all_tasks = self.svc.list_tasks()
            self.apply_filter(keep_selection=not archived)
            if archived:
                self.show_empty_right()
        except Exception as e:
            self.show_error(str(e))

    def _delete_selected_forever(self):
        ids = self.selected_task_ids()
        if not ids:
            return
        count = len(ids)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(tr("archive.delete_forever"))
        box.setText(tr("dlg.del_tasks_text", count=count, noun=self._task_noun(count)))
        box.setInformativeText(tr("dlg.del_tasks_hint"))
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        box.setStyleSheet("""
            QMessageBox { background: #1c1c1e; color: #f5f5f7; }
            QLabel { color: #f5f5f7; }
            QPushButton { background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.12);
                padding: 8px 16px; border-radius: 12px; color: #f5f5f7; min-width: 90px; }
            QPushButton:hover { background: rgba(255,255,255,0.12); }
        """)
        if box.exec() == QMessageBox.StandardButton.Yes:
            try:
                for tid in ids:
                    self.svc.delete_task(tid)
                self.all_tasks = self.svc.list_tasks()
                self.apply_filter()
                self.show_empty_right()
            except Exception as e:
                self.show_error(str(e))

    def _clear_archive(self):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(tr("archive.clear_all"))
        box.setText(tr("archive.clear_confirm"))
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        box.setStyleSheet("""
            QMessageBox { background: #1c1c1e; color: #f5f5f7; }
            QLabel { color: #f5f5f7; }
            QPushButton { background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.12);
                padding: 8px 16px; border-radius: 12px; color: #f5f5f7; min-width: 90px; }
            QPushButton:hover { background: rgba(255,255,255,0.12); }
        """)
        if box.exec() == QMessageBox.StandardButton.Yes:
            try:
                from PyQt6.QtWidgets import QSystemTrayIcon
                n = self.svc.clear_archive()
                self.all_tasks = self.svc.list_tasks()
                self.apply_filter()
                self.show_empty_right()
                if hasattr(self, "tray"):
                    self.tray.showMessage(
                        tr("archive.clear_all"),
                        tr("archive.cleared", n=n),
                        QSystemTrayIcon.MessageIcon.Information, 3000
                    )
            except Exception as e:
                self.show_error(str(e))

    def _clear_all_data(self):
        from PyQt6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(tr("settings.clear_all_data"))
        box.setText(tr("settings.clear_all_confirm"))
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        box.setStyleSheet("""
            QMessageBox { background: #1c1c1e; color: #f5f5f7; }
            QLabel { color: #f5f5f7; }
            QPushButton { background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.12);
                padding: 8px 16px; border-radius: 12px; color: #f5f5f7; min-width: 90px; }
            QPushButton:hover { background: rgba(255,255,255,0.12); }
        """)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        try:
            db = self.svc.db
            db._con.executescript("""
                DELETE FROM subtasks;
                DELETE FROM tasks;
                DELETE FROM fin_transactions;
                DELETE FROM fin_accounts;
                DELETE FROM fin_categories;
                DELETE FROM fin_budgets;
                DELETE FROM fin_goals;
            """)
            db._con.commit()
            # Seed tutorial task immediately so the user isn't left with an empty list
            db._seed_tutorial_task()
            self._settings.setValue("tutorial_task_seeded", True)
            self.all_tasks = self.svc.list_tasks()
            self.apply_filter()
            self.show_empty_right()
            if hasattr(self, "analytics_page"):
                self.analytics_page.refresh()
            if hasattr(self, "finance_page"):
                self.finance_page.refresh()
            self._show_toast(tr("settings.clear_all_done"))
        except Exception as e:
            self.show_error(str(e))

    def _strip_all_task_formatting(self):
        """Remove all inline HTML formatting from every task description in DB."""
        from PyQt6.QtGui import QTextDocument
        try:
            tasks = self.svc.list_tasks()
            count = 0
            for t in tasks:
                if t.description and "<!DOCTYPE" in t.description[:100]:
                    # Let Qt parse its own HTML and extract plain text
                    doc = QTextDocument()
                    doc.setHtml(t.description)
                    plain = doc.toPlainText().strip()
                    self.svc.update_task(t.id, t.title, plain)
                    count += 1
            self.all_tasks = self.svc.list_tasks()
            self.apply_filter()
            if self.current_task_id is not None:
                t = self.svc.get_task(self.current_task_id)
                if t:
                    self._block_editor_signals = True
                    try:
                        self.editor_desc.set_content(t.description or "")
                    finally:
                        self._block_editor_signals = False
            self._show_toast(tr("settings.strip_formatting_done", n=count))
        except Exception as e:
            self.show_error(str(e))

    def _seed_mock_data(self):
        """Clear all data and seed demo tasks + finance mock data."""
        try:
            db = self.svc.db
            db._seed_task_history()
            if hasattr(db, "_seed_finance_mock"):
                db._seed_finance_mock()
            self.all_tasks = self.svc.list_tasks()
            self.apply_filter()
            self.show_empty_right()
            if hasattr(self, "analytics_page"):
                self.analytics_page.refresh()
            if hasattr(self, "finance_page"):
                self.finance_page.refresh()
            self._show_toast(tr("settings.seed_mock_done"))
        except Exception as e:
            self.show_error(str(e))

    def on_escape(self):
        if hasattr(self, "_settings_dlg") and self._settings_dlg is not None and self._settings_dlg.isVisible():
            self._settings_dlg.hide()
            return
        if self.btn_back_to_calendar.isVisible():
            self.save_current_task_if_dirty()
            self.toggle_calendar()
            return
        idx = self.right_stack.currentIndex()
        if idx == 2:
            self.toggle_analytics()
            self.list.clearSelection()
            self.show_empty_right()
            return
        if idx == 4:
            self.toggle_calendar()
            self.list.clearSelection()
            self.show_empty_right()
            return
        if idx == 1:
            if self.current_task_id is not None:
                title = (self.editor_title.text() or "").strip()
                desc = (self.editor_desc.get_content() or "").strip()
                if title == "" and desc == "":
                    tid = self.current_task_id
                    try:
                        self.svc.delete_task(tid)
                        self.refresh()
                    except Exception as e:
                        self.show_error(str(e))
                else:
                    self.save_current_task_if_dirty()
            self.list.clearSelection()
            self.show_empty_right()

    def on_list_reordered(self, ids: list) -> None:
        try:
            self.svc.reorder_tasks(ids)
            self.all_tasks = self.svc.list_tasks()
        except Exception as e:
            self.show_error(str(e))

    def toggle_done_current(self):
        task_id = self.selected_task_id()
        if task_id is None:
            return
        t = self.svc.get_task(task_id)
        if t is None:
            return
        try:
            old_done = t.is_done
            tid = task_id

            def _undo_toggle(tid=tid, old_done=old_done):
                self.svc.set_done(tid, old_done)

            def _redo_toggle(tid=tid, old_done=old_done):
                self.svc.set_done(tid, not old_done)

            self._push_action(tr("history.done"), _undo_toggle, _redo_toggle)
            self.svc.set_done(task_id, not t.is_done)
            t2 = self.svc.get_task(task_id)
            if t2:
                it = self.list.currentItem()
                if it:
                    self._populating_list = True
                    try:
                        it.setCheckState(Qt.CheckState.Checked if t2.is_done else Qt.CheckState.Unchecked)
                    finally:
                        self._populating_list = False
                    self._update_item_display(it, t2)
                    if self.current_task_id == task_id:
                        self._block_editor_signals = True
                        try:
                            status = tr("editor.done") if t2.is_done else tr("editor.undone")
                            self.editor_meta.setText(
                                f"{status} • {tr('editor.created', date=self._format_meta_full(t2))}"
                            )
                        finally:
                            self._block_editor_signals = False
            self.all_tasks = self.svc.list_tasks()
            QTimer.singleShot(0, lambda: self.apply_filter(keep_selection=True))
            self._refresh_analytics_if_visible()
        except Exception as e:
            self.show_error(str(e))

    def navigate_list(self, direction: int) -> None:
        count = self.list.count()
        if count == 0:
            return
        current = self.list.currentRow()
        if current < 0:
            new_row = 0 if direction > 0 else count - 1
        else:
            new_row = max(0, min(count - 1, current + direction))
        if new_row != current:
            self.list.setCurrentRow(new_row)

    def import_tasks(self, fmt: str):
        import csv
        import json
        from PyQt6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self, tr("import.title"), "",
            "CSV (*.csv)" if fmt == "csv" else "JSON (*.json)"
        )
        if not path:
            return

        count = 0
        try:
            if fmt == "csv":
                with open(path, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        title = row.get("title", "").strip()
                        if not title:
                            continue
                        new_id = self.svc.create_task(title, row.get("description", "") or "")
                        if row.get("is_done", "0") in ("1", "True", "true"):
                            self.svc.set_done(new_id, True)
                        pri = int(row.get("priority", "0") or "0")
                        if pri:
                            self.svc.set_priority(new_id, pri)
                        if row.get("is_pinned", "0") in ("1", "True", "true"):
                            self.svc.set_pinned(new_id, True)
                        if row.get("recurrence"):
                            self.svc.set_recurrence(new_id, row["recurrence"])
                        if row.get("tags"):
                            self.svc.set_tags(new_id, row["tags"])
                        if row.get("remind_at"):
                            self.svc.set_reminder(new_id, row["remind_at"])
                        if row.get("deadline_at"):
                            self.svc.set_deadline(new_id, row["deadline_at"])
                        count += 1
            else:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    data = [data]
                for item in data:
                    title = (item.get("title") or "").strip()
                    if not title:
                        continue
                    new_id = self.svc.create_task(title, item.get("description", "") or "")
                    if item.get("is_done"):
                        self.svc.set_done(new_id, True)
                    pri = int(item.get("priority", 0) or 0)
                    if pri:
                        self.svc.set_priority(new_id, pri)
                    if item.get("is_pinned"):
                        self.svc.set_pinned(new_id, True)
                    if item.get("recurrence"):
                        self.svc.set_recurrence(new_id, item["recurrence"])
                    if item.get("tags"):
                        self.svc.set_tags(new_id, item["tags"])
                    if item.get("remind_at"):
                        self.svc.set_reminder(new_id, item["remind_at"])
                    if item.get("deadline_at"):
                        self.svc.set_deadline(new_id, item["deadline_at"])
                    count += 1

            self.refresh()
            QMessageBox.information(self, tr("import.title"), tr("import.ok", n=count))
        except Exception as e:
            self.show_error(tr("import.err", e=e))

    def export_tasks(self, fmt: str = "csv"):
        import csv
        import json
        from PyQt6.QtWidgets import QFileDialog
        from datetime import datetime

        default_name = f"tasks_{datetime.now().strftime('%Y%m%d_%H%M')}.{fmt}"
        path, _ = QFileDialog.getSaveFileName(
            self, tr("export.title"), default_name,
            "CSV (*.csv)" if fmt == "csv" else "JSON (*.json)"
        )
        if not path:
            return

        tasks = self.svc.list_tasks()
        try:
            if fmt == "csv":
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f)
                    w.writerow(["id", "title", "description", "is_done",
                                "priority", "is_pinned", "recurrence", "tags",
                                "category_id", "created_at", "completed_at",
                                "remind_at", "deadline_at"])
                    for t in tasks:
                        w.writerow([
                            t.id, t.title, t.description,
                            int(t.is_done), t.priority,
                            int(t.is_pinned), t.recurrence or "",
                            t.tags or "", t.category_id or "",
                            t.created_at or "", t.completed_at or "",
                            t.remind_at or "", t.deadline_at or ""
                        ])
            else:
                data = [
                    {
                        "id": t.id, "title": t.title, "description": t.description,
                        "is_done": t.is_done, "priority": t.priority,
                        "is_pinned": t.is_pinned, "recurrence": t.recurrence,
                        "tags": t.tags, "category_id": t.category_id,
                        "created_at": t.created_at, "completed_at": t.completed_at,
                        "remind_at": t.remind_at, "deadline_at": t.deadline_at,
                    }
                    for t in tasks
                ]
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

            QMessageBox.information(self, tr("export.title"), tr("export.ok", path=path))
        except Exception as e:
            self.show_error(tr("export.err", e=e))

    def export_current_task(self, fmt: str):
        import csv
        import json
        from PyQt6.QtWidgets import QFileDialog
        from datetime import datetime

        if self.current_task_id is None:
            return
        self.save_current_task_if_dirty()
        t = self.svc.get_task(self.current_task_id)
        if not t:
            return
        subtasks = self.svc.list_subtasks(t.id)

        title_slug = (t.title or "task").strip()[:40].replace(" ", "_")
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        default_name = f"{title_slug}_{ts}.{fmt}"
        filters = {"md": "Markdown (*.md)", "csv": "CSV (*.csv)", "json": "JSON (*.json)"}
        path, _ = QFileDialog.getSaveFileName(
            self, tr("export.title"), default_name, filters.get(fmt, "*.*")
        )
        if not path:
            return

        pri_map = {0: "—", 1: tr("editor.pri_low"), 2: tr("editor.pri_med"), 3: tr("editor.pri_high")}
        try:
            if fmt == "md":
                lines = [f"# {t.title or tr('editor.untitled')}", ""]
                lines.append(f"**{tr('editor.done') if t.is_done else tr('editor.undone')}**  ")
                if t.priority:
                    lines.append(f"**Priority:** {pri_map.get(t.priority, '—')}  ")
                if t.is_pinned:
                    lines.append(f"**Pinned:** yes  ")
                if t.recurrence:
                    lines.append(f"**Recurrence:** {t.recurrence}  ")
                lines.append(f"**Created:** {t.created_at or '—'}  ")
                if t.completed_at:
                    lines.append(f"**Completed:** {t.completed_at}  ")
                if t.deadline_at:
                    lines.append(f"**Deadline:** {t.deadline_at}  ")
                if t.remind_at:
                    lines.append(f"**Reminder:** {t.remind_at}  ")
                if t.description and t.description.strip():
                    lines += ["", "## Description", "", t.description.strip()]
                if subtasks:
                    lines += ["", "## Subtasks", ""]
                    for s in subtasks:
                        check = "x" if s["is_done"] else " "
                        lines.append(f"- [{check}] {s['title']}")
                with open(path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))

            elif fmt == "csv":
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f)
                    w.writerow(["field", "value"])
                    for field, val in [
                        ("id", t.id), ("title", t.title or ""),
                        ("description", t.description or ""),
                        ("is_done", int(t.is_done)), ("priority", t.priority),
                        ("is_pinned", int(t.is_pinned)), ("recurrence", t.recurrence or ""),
                        ("created_at", t.created_at or ""), ("completed_at", t.completed_at or ""),
                        ("remind_at", t.remind_at or ""), ("deadline_at", t.deadline_at or ""),
                    ]:
                        w.writerow([field, val])
                    if subtasks:
                        w.writerow([])
                        w.writerow(["subtask_id", "subtask_title", "subtask_done"])
                        for s in subtasks:
                            w.writerow([s["id"], s["title"], int(s["is_done"])])

            else:  # json
                data = {
                    "id": t.id, "title": t.title, "description": t.description,
                    "is_done": t.is_done, "priority": t.priority,
                    "is_pinned": t.is_pinned, "recurrence": t.recurrence,
                    "created_at": t.created_at, "completed_at": t.completed_at,
                    "remind_at": t.remind_at, "deadline_at": t.deadline_at,
                    "subtasks": [
                        {"id": s["id"], "title": s["title"], "is_done": s["is_done"]}
                        for s in subtasks
                    ],
                }
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

            QMessageBox.information(self, tr("export.title"), tr("export.ok", path=path))
        except Exception as e:
            self.show_error(tr("export.err", e=e))

    def _show_task_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #1c1c1e; border: 1px solid rgba(255,255,255,0.12);
                border-radius: 8px; color: #f5f5f7; font-size: 13px; }
            QMenu::item { padding: 6px 20px; }
            QMenu::item:selected { background: rgba(10,132,255,0.35); }
            QMenu::separator { height: 1px; background: rgba(255,255,255,0.10); margin: 2px 0; }
        """)

        has_task = self.current_task_id is not None
        current_task = self.svc.get_task(self.current_task_id) if has_task else None
        is_archived = current_task.is_archived if current_task else False

        if has_task:
            a_arch = menu.addAction(tr("ctx.unarchive") if is_archived else tr("ctx.archive"))
            menu.addSeparator()
        else:
            a_arch = None

        a_md  = menu.addAction(tr("editor.export_md"))
        a_csv = menu.addAction(tr("editor.export_csv"))
        a_jso = menu.addAction(tr("editor.export_json"))
        a_md.setEnabled(has_task)
        a_csv.setEnabled(has_task)
        a_jso.setEnabled(has_task)

        menu.addSeparator()
        a_imp_csv  = menu.addAction(tr("import.csv"))
        a_imp_json = menu.addAction(tr("import.json"))

        menu.addSeparator()
        a_exp_all_csv  = menu.addAction(tr("export.csv"))
        a_exp_all_json = menu.addAction(tr("export.json"))

        from PyQt6.QtCore import QPoint
        btn_rect = self.btn_task_menu.rect()
        pos = self.btn_task_menu.mapToGlobal(QPoint(0, btn_rect.height()))
        action = menu.exec(pos)
        if a_arch and action == a_arch:
            self._archive_selected(not is_archived)
        elif action == a_md:
            self.export_current_task("md")
        elif action == a_csv:
            self.export_current_task("csv")
        elif action == a_jso:
            self.export_current_task("json")
        elif action == a_imp_csv:
            self.import_tasks("csv")
        elif action == a_imp_json:
            self.import_tasks("json")
        elif action == a_exp_all_csv:
            self.export_tasks("csv")
        elif action == a_exp_all_json:
            self.export_tasks("json")
