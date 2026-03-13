"""FilterMixin — search, filter, sort, list-item creation and display."""
from __future__ import annotations

import re

from PyQt6.QtWidgets import QListWidgetItem
from PyQt6.QtCore import Qt, QTimer

from shared.i18n import tr

_RE_HTML_TAG = re.compile(r"<[^>]+>")


def _desc_plain(text: str) -> str:
    """Strip HTML tags for plain-text search."""
    return _RE_HTML_TAG.sub("", text or "")


class FilterMixin:
    """Mixin: search, filter, sort, list-item creation, refresh, apply_filter."""

    def _on_inline_edit_close(self, editor, hint):
        if not self._inline_editing:
            return
        self._inline_editing = False

        it = self.list.currentItem()
        if it is None:
            return

        it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)

        new_title = ""
        try:
            new_title = editor.text().strip()
        except (RuntimeError, AttributeError):
            new_title = it.text().strip()

        self._populating_list = True
        try:
            it.setText(new_title or tr("editor.untitled"))
        finally:
            self._populating_list = False

        if self.current_task_id is not None:
            self._block_editor_signals = True
            try:
                self.editor_title.setText(new_title)
            finally:
                self._block_editor_signals = False
            self._dirty = True
            self.save_current_task_if_dirty()

    def _on_search_changed(self, text: str):
        self.list.itemDelegate().set_search_query(text)
        self.list.update()
        self.apply_filter(keep_selection=True)

    # ---------------- filter/sort ----------------
    def set_filter(self, mode: str):
        self.filter_mode = mode
        self.btn_all.setChecked(mode == self.FILTER_ALL)
        self.btn_active.setChecked(mode == self.FILTER_ACTIVE)
        self.btn_done.setChecked(mode == self.FILTER_DONE)
        self.btn_today.setChecked(mode == self.FILTER_TODAY)
        self.btn_archive.setChecked(mode == self.FILTER_ARCHIVE)
        self.apply_filter(keep_selection=True)

    def on_sort_changed(self, _):
        from entities.task.ui.task_list import TaskListWidget
        self.sort_mode = self.sort_combo.currentData()
        if self.sort_mode == self.SORT_MANUAL:
            self.list.setDragDropMode(TaskListWidget.DragDropMode.InternalMove)
        else:
            self.list.setDragDropMode(TaskListWidget.DragDropMode.DragOnly)
        self.apply_filter(keep_selection=True)

    def _sorted_tasks(self, tasks):
        if self.sort_mode == self.SORT_NEW:
            result = sorted(tasks, key=lambda t: t.created_at or "", reverse=True)
        elif self.sort_mode == self.SORT_OLD:
            result = sorted(tasks, key=lambda t: t.created_at or "")
        elif self.sort_mode == self.SORT_ALPHA:
            result = sorted(tasks, key=lambda t: (t.title or "").lower())
        elif self.sort_mode == self.SORT_UNDONE_FIRST:
            undone = [t for t in tasks if not t.is_done]
            done = [t for t in tasks if t.is_done]
            undone.sort(key=lambda t: t.created_at or "", reverse=True)
            done.sort(key=lambda t: t.created_at or "", reverse=True)
            result = undone + done
        elif self.sort_mode == self.SORT_MANUAL:
            result = sorted(tasks, key=lambda t: t.sort_order)
        else:
            result = list(tasks)
        pinned = [t for t in result if t.is_pinned]
        unpinned = [t for t in result if not t.is_pinned]
        return pinned + unpinned

    # ---------------- list items ----------------
    def make_item(self, t) -> QListWidgetItem:
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, t.id)

        if t.category_id:
            cat = next((c for c in self.categories if c.id == t.category_id), None)
            if cat:
                item.setData(Qt.ItemDataRole.UserRole + 2, cat.color)

        item.setData(Qt.ItemDataRole.UserRole + 3, t.priority)
        item.setData(Qt.ItemDataRole.UserRole + 4, t.is_pinned)
        item.setData(Qt.ItemDataRole.UserRole + 5, t.deadline_at or "")
        item.setData(Qt.ItemDataRole.UserRole + 6, self._subtask_counts.get(t.id))

        item.setFlags(
            item.flags()
            | Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEnabled
        )

        item.setCheckState(Qt.CheckState.Checked if t.is_done else Qt.CheckState.Unchecked)
        self._update_item_display(item, t)

        return item

    @staticmethod
    def _utc_to_local(iso_str: str) -> str:
        from datetime import datetime, timezone
        try:
            dt = datetime.fromisoformat(iso_str.replace("+00:00", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone().strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return iso_str or ""

    def _format_meta(self, t) -> str:
        local = self._utc_to_local(t.created_at or "")
        if len(local) >= 16:
            date_part = local[5:10].replace("-", ".")
            time_part = local[11:16]
            return f"{date_part} {time_part}"
        return ""

    _MONTHS_SHORT = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

    def _format_meta_full(self, t) -> str:
        from datetime import datetime as _dt
        local = self._utc_to_local(t.created_at or "")
        if len(local) >= 16:
            try:
                d = _dt.fromisoformat(local)
                return f"{d.day} {self._MONTHS_SHORT[d.month - 1]} {d.year},  {d.strftime('%H:%M')}"
            except Exception:
                pass
            return local
        return t.created_at or ""

    @staticmethod
    def _format_deadline_meta(deadline_at: str) -> str:
        from datetime import datetime, timezone
        try:
            dl = datetime.fromisoformat(deadline_at)
            if dl.tzinfo is None:
                dl = dl.replace(tzinfo=timezone.utc)
            return f"⏰{dl.astimezone().strftime('%d.%m')}"
        except Exception:
            return ""

    def _update_item_display(self, item: QListWidgetItem, t) -> None:
        title = (t.title or "").strip() or tr("editor.untitled")
        if t.deadline_at and not t.is_done:
            meta = self._format_deadline_meta(t.deadline_at)
        else:
            meta = self._format_meta(t)
        item.setText(title)
        item.setData(Qt.ItemDataRole.UserRole + 1, meta)
        item.setData(Qt.ItemDataRole.UserRole + 5, t.deadline_at or "")
        counts = getattr(self, "_subtask_counts", {}).get(t.id)
        item.setData(Qt.ItemDataRole.UserRole + 6, counts)
        desc = (t.description or "").strip()
        item.setToolTip(desc if desc else "")

    def _select_item_by_id(self, task_id: int) -> None:
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it is None:
                continue
            if int(it.data(Qt.ItemDataRole.UserRole)) == task_id:
                self.list.setCurrentItem(it)
                break

    # ---------------- data refresh ----------------
    def refresh(self):
        self.all_tasks = self.svc.list_tasks()
        self._subtask_counts: dict[int, tuple[int, int]] = self.svc.subtask_counts_all()
        self.refresh_categories()
        self.apply_filter(keep_selection=True)

    def apply_filter(self, keep_selection: bool = False):
        selected_id = self.selected_task_id() if keep_selection else None
        q = self.search.text().strip().lower()

        archived_tasks = [t for t in self.all_tasks if t.is_archived]
        tasks = [t for t in self.all_tasks if not t.is_archived]

        if self.filter_mode == self.FILTER_ARCHIVE:
            tasks = archived_tasks
        elif self.filter_mode == self.FILTER_ACTIVE:
            tasks = [t for t in tasks if not t.is_done]
        elif self.filter_mode == self.FILTER_DONE:
            tasks = [t for t in tasks if t.is_done]
        elif self.filter_mode == self.FILTER_CATEGORY:
            if self.current_category_id is not None and self.current_category_id != -1:
                tasks = [t for t in tasks if t.category_id == self.current_category_id]
        elif self.filter_mode == self.FILTER_CALENDAR_DAY:
            if self._calendar_filter_date:
                ds = self._calendar_filter_date.isoformat()
                tasks = [t for t in tasks if t.deadline_at and t.deadline_at[:10] == ds]
        elif self.filter_mode == self.FILTER_TODAY:
            from datetime import datetime, timezone, date as _date
            _today = _date.today()

            def _deadline_due(t):
                if t.is_done or not t.deadline_at:
                    return False
                try:
                    dl = datetime.fromisoformat(t.deadline_at)
                    if dl.tzinfo is None:
                        dl = dl.replace(tzinfo=timezone.utc)
                    return dl.astimezone().date() <= _today
                except Exception:
                    return False
            tasks = [t for t in tasks if _deadline_due(t)]

        if q.startswith("#") and len(q) > 1:
            tag = q[1:]
            tasks = [t for t in tasks
                     if tag in [x.strip() for x in (t.tags or "").split(",") if x.strip()]]
        elif q:
            tasks = [t for t in tasks if q in (t.title or "").lower() or q in _desc_plain(t.description).lower()]

        tasks = self._sorted_tasks(tasks)

        self._populating_list = True
        try:
            self.list.clear()
            done_cnt = sum(1 for t in tasks if t.is_done)

            for t in tasks:
                it = self.make_item(t)
                self.list.addItem(it)

            self.stats.setText(tr("stats.label", count=len(tasks), done=done_cnt))

            non_archived = [t for t in self.all_tasks if not t.is_archived]
            total = len(non_archived)
            done_total = sum(1 for t in non_archived if t.is_done)
            active_total = total - done_total
            archive_n = len(archived_tasks)
            self.btn_all.setText(tr("filter.all_n", n=total))
            self.btn_active.setText(tr("filter.active_n", n=active_total))
            self.btn_done.setText(tr("filter.done_n", n=done_total))
            self.btn_archive.setText(
                tr("filter.archive_n", n=archive_n) if archive_n else tr("filter.archive")
            )
            from datetime import datetime, timezone, date as _date2
            _td = _date2.today()
            today_n = 0
            for _t in non_archived:
                if _t.is_done or not _t.deadline_at:
                    continue
                try:
                    _dl = datetime.fromisoformat(_t.deadline_at)
                    if _dl.tzinfo is None:
                        _dl = _dl.replace(tzinfo=timezone.utc)
                    if _dl.astimezone().date() <= _td:
                        today_n += 1
                except Exception:
                    pass
            self.btn_today.setText(tr("filter.today_n", n=today_n))

            if selected_id is not None:
                self._select_item_by_id(selected_id)
        finally:
            self._populating_list = False
        self.on_selection_changed()

    def _on_item_double_clicked(self, item):
        task_id = self.selected_task_id()
        if task_id is None:
            return
        self.btn_analytics.setChecked(False)
        self.btn_calendar.setChecked(False)
        self.right_stack.setCurrentIndex(1)
        self.load_task_into_editor(self.svc.get_task(task_id))
