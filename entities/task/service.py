from __future__ import annotations

from typing import Optional

from shared.api.db.connection import Database
from entities.task.model import Task


class TaskService:
    UNDO_LIMIT = 50

    def __init__(self):
        self.db = Database()
        self._undo_stack: list[Task] = []

    def list_tasks(self) -> list[Task]:
        return self.db.list_tasks()

    def get_task(self, task_id: int) -> Optional[Task]:
        return self.db.get_task(task_id)

    def create_task(self, title: str = "", description: str = "") -> int:
        new_id = self.db.add_task(title, description)
        self.db.log_event(new_id, "CREATED")
        return new_id

    def update_task(self, task_id: int, title: str, description: str) -> None:
        self.db.update_task(task_id, title, description)

    def set_done(self, task_id: int, is_done: bool) -> None:
        self.db.set_done(task_id, is_done)
        if is_done:
            self.db.log_event(task_id, "COMPLETED")
            # Auto-create next occurrence for recurring tasks
            t = self.db.get_task(task_id)
            if t and t.recurrence:
                self._create_next_recurrence(t)
        else:
            self.db.log_event(task_id, "REOPENED")

    def _create_next_recurrence(self, t: Task) -> int | None:
        """Create the next recurring copy after a recurring task is completed."""
        from datetime import datetime, timezone, timedelta
        new_id = self.db.add_task(t.title or "", t.description or "", t.category_id)
        self.db.set_priority(new_id, t.priority)
        self.db.set_recurrence(new_id, t.recurrence)
        if t.is_pinned:
            self.db.set_pinned(new_id, True)
        def _advance(iso: str) -> str | None:
            """Advance an ISO datetime string by one recurrence period."""
            try:
                dt = datetime.fromisoformat(iso)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if t.recurrence == "daily":
                    return (dt + timedelta(days=1)).isoformat(timespec="seconds")
                elif t.recurrence == "weekly":
                    return (dt + timedelta(weeks=1)).isoformat(timespec="seconds")
                elif t.recurrence == "monthly":
                    import calendar as _cal
                    year = dt.year + (dt.month // 12)
                    month = (dt.month % 12) + 1
                    day = min(dt.day, _cal.monthrange(year, month)[1])
                    return dt.replace(year=year, month=month, day=day).isoformat(timespec="seconds")
            except Exception:
                pass
            return None

        # Advance deadline_at (primary recurrence anchor)
        if t.deadline_at:
            next_iso = _advance(t.deadline_at)
            if next_iso:
                self.db.set_deadline(new_id, next_iso)
        # Carry forward reminder if present, advanced by same period
        if t.remind_at:
            next_iso = _advance(t.remind_at)
            if next_iso:
                self.db.set_reminder(new_id, next_iso)
        self.db.log_event(new_id, "CREATED")
        return new_id

    def delete_task(self, task_id: int) -> None:
        t = self.db.get_task(task_id)
        if t:
            self._undo_stack.append(t)
            if len(self._undo_stack) > self.UNDO_LIMIT:
                self._undo_stack.pop(0)
        self.db.log_event(task_id, "DELETED")
        self.db.delete_task(task_id)

    def duplicate_task(self, task_id: int) -> int | None:
        t = self.db.get_task(task_id)
        if not t:
            return None
        snap = t.__dict__.copy()
        snap.pop("id", None)
        # Reset per-instance state so the copy starts fresh
        snap["is_done"]           = False
        snap["completed_at"]      = None
        snap["remind_shown"]      = False
        snap["deadline_notified"] = 0
        snap["is_archived"]       = False
        # Assign a fresh sort_order so duplicate doesn't collide with original
        snap["sort_order"]        = self.db._con.execute(
            "SELECT COALESCE(MAX(sort_order), 0) FROM tasks"
        ).fetchone()[0] + 1
        new_id = self.db.restore_task(snap)
        # Copy subtasks too
        for sub in self.db.list_subtasks(task_id):
            self.db.add_subtask(new_id, sub["title"])
        self.db.log_event(new_id, "CREATED")
        return new_id

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    def undo_delete(self) -> int | None:
        if not self._undo_stack:
            return None
        t = self._undo_stack.pop()
        new_id = self.db.restore_task(t.__dict__)
        self.db.log_event(new_id, "RESTORED")
        return new_id

    def restore_task(self, snap: dict) -> int:
        """Re-insert a task from a full snapshot dict; returns new task id."""
        new_id = self.db.restore_task(snap)
        self.db.log_event(new_id, "RESTORED")
        return new_id

    def set_reminder(self, task_id: int, remind_at: str | None) -> None:
        """Set or clear a reminder time (UTC ISO string or None)."""
        self.db.set_reminder(task_id, remind_at)

    def get_due_reminders(self) -> list[Task]:
        """Return tasks whose reminder time has passed and not yet shown."""
        return self.db.get_due_reminders()

    def mark_reminder_shown(self, task_id: int) -> None:
        """Mark a reminder as shown so it is not re-fired."""
        self.db.mark_reminder_shown(task_id)

    def set_priority(self, task_id: int, priority: int) -> None:
        self.db.set_priority(task_id, priority)

    def set_pinned(self, task_id: int, is_pinned: bool) -> None:
        self.db.set_pinned(task_id, is_pinned)

    def set_recurrence(self, task_id: int, recurrence: str | None) -> None:
        self.db.set_recurrence(task_id, recurrence)

    # ── subtasks ──────────────────────────────────────────
    def list_subtasks(self, task_id: int) -> list:
        return self.db.list_subtasks(task_id)

    def add_subtask(self, task_id: int, title: str) -> int:
        return self.db.add_subtask(task_id, title)

    def set_subtask_done(self, subtask_id: int, is_done: bool) -> None:
        self.db.set_subtask_done(subtask_id, is_done)

    def update_subtask_title(self, subtask_id: int, title: str) -> None:
        self.db.update_subtask_title(subtask_id, title)

    def delete_subtask(self, subtask_id: int) -> None:
        self.db.delete_subtask(subtask_id)

    def subtask_counts_all(self) -> dict[int, tuple[int, int]]:
        """Return {task_id: (done, total)} for every task that has subtasks."""
        return self.db.subtask_counts_all()

    def set_tags(self, task_id: int, tags: str) -> None:
        self.db.set_tags(task_id, tags)

    def reorder_tasks(self, id_order: list[int]) -> None:
        self.db.reorder_tasks(id_order)

    def reorder_subtasks(self, id_order: list[int]) -> None:
        self.db.reorder_subtasks(id_order)

    def set_deadline(self, task_id: int, deadline_at: str | None) -> None:
        """Set or clear a deadline (UTC ISO string or None)."""
        self.db.set_deadline(task_id, deadline_at)

    def mark_deadline_notified(self, task_id: int, level: int) -> None:
        """Set deadline notification level (1=today, 2=overdue)."""
        self.db.mark_deadline_notified(task_id, level)

    def archive_task(self, task_id: int, archived: bool = True) -> None:
        self.db.archive_task(task_id, archived)

    def archive_completed_tasks(self, older_than: str) -> int:
        return self.db.archive_completed_tasks(older_than)

    def clear_archive(self) -> int:
        return self.db.clear_archive()

    def close(self):
        self.db.close()
