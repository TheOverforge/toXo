"""TaskDbMixin — task, subtask, reminder, deadline, archive, tag and ordering methods."""
from __future__ import annotations

from typing import List, Optional
from entities.task.model import Task

# Column list (duplicated here for standalone imports; db.py is authoritative)
_TASK_COLS = "id, title, description, is_done, created_at, completed_at, updated_at, priority, category_id, remind_at, remind_shown, deadline_at, deadline_notified, is_pinned, recurrence, tags, sort_order, is_archived"


class TaskDbMixin:
    """Mix-in that provides task-related DB methods.

    Expects the host class to supply:
      self._con     — sqlite3.Connection
      self._now_iso() — UTC ISO timestamp string
    """

    # ── row helper ───────────────────────────────────────
    def _row_to_task(self, r) -> Task:
        return Task(
            id=r[0],
            title=r[1],
            description=r[2],
            is_done=bool(r[3]),
            created_at=r[4],
            completed_at=r[5],
            updated_at=r[6],
            priority=r[7] or 0,
            category_id=r[8] if len(r) > 8 else None,
            remind_at=r[9] if len(r) > 9 else None,
            remind_shown=bool(r[10]) if len(r) > 10 else False,
            deadline_at=r[11] if len(r) > 11 else None,
            deadline_notified=int(r[12]) if len(r) > 12 else 0,
            is_pinned=bool(r[13]) if len(r) > 13 else False,
            recurrence=r[14] if len(r) > 14 else None,
            tags=r[15] if len(r) > 15 else "",
            sort_order=int(r[16]) if len(r) > 16 and r[16] is not None else 0,
            is_archived=bool(r[17]) if len(r) > 17 else False,
        )

    # ── CRUD ─────────────────────────────────────────────
    def add_task(self, title: str = "", description: str = "", category_id: int | None = None) -> int:
        title = (title or "").strip()
        description = (description or "").strip()
        now = self._now_iso()
        max_order = self._con.execute(
            "SELECT COALESCE(MAX(sort_order), 0) FROM tasks"
        ).fetchone()[0]
        cur = self._con.execute(
            "INSERT INTO tasks(title, description, is_done, created_at, updated_at, priority, category_id, sort_order) "
            "VALUES (?, ?, 0, ?, ?, 0, ?, ?)",
            (title, description, now, now, category_id, max_order + 1)
        )
        self._con.commit()
        return int(cur.lastrowid)

    def add_task_full(self, task: Task) -> int:
        """Restore a task with all fields (for undo)."""
        title = (task.title or "").strip()
        description = (task.description or "").strip()
        created_at = (task.created_at or "").strip() or self._now_iso()
        cur = self._con.execute(
            "INSERT INTO tasks(title, description, is_done, created_at, completed_at, updated_at, priority, category_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (title, description, 1 if task.is_done else 0, created_at,
             task.completed_at, task.updated_at, task.priority, task.category_id)
        )
        self._con.commit()
        return int(cur.lastrowid)

    def restore_task(self, snap: dict) -> int:
        """Re-insert a task from a full-field snapshot dict (all columns).

        Snapshot is produced via task.__dict__ or a manually built dict.
        Returns the new task id (may differ from the original).
        """
        now = self._now_iso()
        cur = self._con.execute(
            "INSERT INTO tasks("
            "  title, description, is_done, created_at, completed_at, updated_at,"
            "  priority, category_id, remind_at, remind_shown, deadline_at,"
            "  deadline_notified, is_pinned, recurrence, tags, sort_order, is_archived"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                snap.get("title") or "",
                snap.get("description") or "",
                1 if snap.get("is_done") else 0,
                snap.get("created_at") or now,
                snap.get("completed_at"),
                now,
                int(snap.get("priority") or 0),
                snap.get("category_id"),
                snap.get("remind_at"),
                1 if snap.get("remind_shown") else 0,
                snap.get("deadline_at"),
                int(snap.get("deadline_notified") or 0),
                1 if snap.get("is_pinned") else 0,
                snap.get("recurrence"),
                snap.get("tags") or "",
                int(snap.get("sort_order") or 0),
                1 if snap.get("is_archived") else 0,
            )
        )
        self._con.commit()
        return int(cur.lastrowid)

    def list_tasks(self) -> List[Task]:
        rows = self._con.execute(f"SELECT {_TASK_COLS} FROM tasks").fetchall()
        return [self._row_to_task(r) for r in rows]

    def get_task(self, task_id: int) -> Optional[Task]:
        row = self._con.execute(
            f"SELECT {_TASK_COLS} FROM tasks WHERE id=?", (task_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_task(row)

    def update_task(self, task_id: int, title: str, description: str) -> None:
        title = (title or "").strip()
        description = (description or "").strip()
        now = self._now_iso()
        self._con.execute(
            "UPDATE tasks SET title=?, description=?, updated_at=? WHERE id=?",
            (title, description, now, task_id)
        )
        self._con.commit()

    def set_done(self, task_id: int, is_done: bool) -> None:
        now = self._now_iso()
        if is_done:
            self._con.execute(
                "UPDATE tasks SET is_done=1, completed_at=?, updated_at=? WHERE id=?",
                (now, now, task_id)
            )
        else:
            self._con.execute(
                "UPDATE tasks SET is_done=0, completed_at=NULL, updated_at=? WHERE id=?",
                (now, task_id)
            )
        self._con.commit()

    def delete_task(self, task_id: int) -> None:
        self._con.execute("DELETE FROM subtasks WHERE task_id=?", (task_id,))
        self._con.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        self._con.commit()

    # ── reminders ────────────────────────────────────────
    def set_reminder(self, task_id: int, remind_at: str | None) -> None:
        now = self._now_iso()
        self._con.execute(
            "UPDATE tasks SET remind_at=?, remind_shown=0, updated_at=? WHERE id=?",
            (remind_at, now, task_id)
        )
        self._con.commit()

    def mark_reminder_shown(self, task_id: int) -> None:
        self._con.execute(
            "UPDATE tasks SET remind_shown=1 WHERE id=?", (task_id,)
        )
        self._con.commit()

    def get_due_reminders(self) -> list:
        now = self._now_iso()
        rows = self._con.execute(
            f"SELECT {_TASK_COLS} FROM tasks "
            "WHERE remind_at IS NOT NULL AND remind_shown=0 AND remind_at <= ?",
            (now,)
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    # ── deadlines ────────────────────────────────────────
    def set_deadline(self, task_id: int, deadline_at: str | None) -> None:
        now = self._now_iso()
        self._con.execute(
            "UPDATE tasks SET deadline_at=?, deadline_notified=0, updated_at=? WHERE id=?",
            (deadline_at, now, task_id)
        )
        self._con.commit()

    def mark_deadline_notified(self, task_id: int, level: int) -> None:
        self._con.execute(
            "UPDATE tasks SET deadline_notified=? WHERE id=?", (level, task_id)
        )
        self._con.commit()

    # ── archive ──────────────────────────────────────────
    def archive_task(self, task_id: int, archived: bool = True) -> None:
        self._con.execute(
            "UPDATE tasks SET is_archived=?, updated_at=? WHERE id=?",
            (int(archived), self._now_iso(), task_id)
        )
        self._con.commit()

    def archive_completed_tasks(self, older_than: str) -> int:
        cur = self._con.execute(
            "UPDATE tasks SET is_archived=1, updated_at=? "
            "WHERE is_done=1 AND is_archived=0 "
            "AND completed_at IS NOT NULL AND completed_at <= ?",
            (self._now_iso(), older_than)
        )
        self._con.commit()
        return cur.rowcount

    def clear_archive(self) -> int:
        self._con.execute(
            "DELETE FROM subtasks WHERE task_id IN (SELECT id FROM tasks WHERE is_archived=1)"
        )
        cur = self._con.execute("DELETE FROM tasks WHERE is_archived=1")
        self._con.commit()
        return cur.rowcount

    # ── per-day task queries ──────────────────────────────
    def get_tasks_created_on(self, date_str: str) -> list:
        rows = self._con.execute(
            f"SELECT {_TASK_COLS} FROM tasks "
            "WHERE DATE(created_at, 'localtime') = ?",
            (date_str,)
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def get_tasks_completed_on(self, date_str: str) -> list:
        rows = self._con.execute(
            f"SELECT {_TASK_COLS} FROM tasks "
            "WHERE is_done = 1 AND completed_at IS NOT NULL "
            "AND DATE(completed_at, 'localtime') = ?",
            (date_str,)
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def get_tasks_with_deadline_on(self, date_str: str) -> list:
        rows = self._con.execute(
            f"SELECT {_TASK_COLS} FROM tasks "
            "WHERE is_archived=0 AND deadline_at IS NOT NULL "
            "AND DATE(deadline_at, 'localtime') = ? "
            "ORDER BY deadline_at",
            (date_str,)
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    # ── event log ────────────────────────────────────────
    def log_event(self, task_id: int, event_type: str) -> None:
        self._con.execute(
            "INSERT INTO task_events(task_id, event_type, ts) VALUES (?, ?, ?)",
            (task_id, event_type, self._now_iso())
        )
        self._con.commit()

    # ── priority / pin / recurrence ──────────────────────
    def set_priority(self, task_id: int, priority: int) -> None:
        now = self._now_iso()
        self._con.execute(
            "UPDATE tasks SET priority=?, updated_at=? WHERE id=?",
            (priority, now, task_id)
        )
        self._con.commit()

    def set_pinned(self, task_id: int, is_pinned: bool) -> None:
        now = self._now_iso()
        self._con.execute(
            "UPDATE tasks SET is_pinned=?, updated_at=? WHERE id=?",
            (1 if is_pinned else 0, now, task_id)
        )
        self._con.commit()

    def set_recurrence(self, task_id: int, recurrence: str | None) -> None:
        now = self._now_iso()
        self._con.execute(
            "UPDATE tasks SET recurrence=?, updated_at=? WHERE id=?",
            (recurrence, now, task_id)
        )
        self._con.commit()

    # ── subtasks ─────────────────────────────────────────
    def add_subtask(self, task_id: int, title: str) -> int:
        title = (title or "").strip()
        now = self._now_iso()
        max_order = self._con.execute(
            "SELECT COALESCE(MAX(sort_order), -1) FROM subtasks WHERE task_id=?", (task_id,)
        ).fetchone()[0]
        cur = self._con.execute(
            "INSERT INTO subtasks(task_id, title, is_done, sort_order, created_at) VALUES (?,?,0,?,?)",
            (task_id, title, max_order + 1, now)
        )
        self._con.commit()
        return int(cur.lastrowid)

    def list_subtasks(self, task_id: int) -> list:
        rows = self._con.execute(
            "SELECT id, task_id, title, is_done, sort_order "
            "FROM subtasks WHERE task_id=? ORDER BY sort_order",
            (task_id,)
        ).fetchall()
        return [
            {"id": r[0], "task_id": r[1], "title": r[2],
             "is_done": bool(r[3]), "sort_order": r[4]}
            for r in rows
        ]

    def set_subtask_done(self, subtask_id: int, is_done: bool) -> None:
        self._con.execute(
            "UPDATE subtasks SET is_done=? WHERE id=?", (1 if is_done else 0, subtask_id)
        )
        self._con.commit()

    def update_subtask_title(self, subtask_id: int, title: str) -> None:
        self._con.execute(
            "UPDATE subtasks SET title=? WHERE id=?", (title.strip(), subtask_id)
        )
        self._con.commit()

    def delete_subtask(self, subtask_id: int) -> None:
        self._con.execute("DELETE FROM subtasks WHERE id=?", (subtask_id,))
        self._con.commit()

    def delete_subtasks_for_task(self, task_id: int) -> None:
        self._con.execute("DELETE FROM subtasks WHERE task_id=?", (task_id,))
        self._con.commit()

    def reorder_subtasks(self, id_order: list[int]) -> None:
        for pos, sub_id in enumerate(id_order):
            self._con.execute(
                "UPDATE subtasks SET sort_order=? WHERE id=?", (pos, sub_id)
            )
        self._con.commit()

    def subtask_counts_all(self) -> dict[int, tuple[int, int]]:
        rows = self._con.execute(
            "SELECT task_id, "
            "  SUM(CASE WHEN is_done THEN 1 ELSE 0 END), "
            "  COUNT(*) "
            "FROM subtasks GROUP BY task_id"
        ).fetchall()
        return {r[0]: (int(r[1]), int(r[2])) for r in rows}

    # ── tags / ordering ──────────────────────────────────
    def set_tags(self, task_id: int, tags: str) -> None:
        self._con.execute("UPDATE tasks SET tags=? WHERE id=?", (tags.strip(), task_id))
        self._con.commit()

    def reorder_tasks(self, id_order: list[int]) -> None:
        cur = self._con.cursor()
        for pos, task_id in enumerate(id_order):
            cur.execute("UPDATE tasks SET sort_order=? WHERE id=?", (pos, task_id))
        self._con.commit()

    # ── export ───────────────────────────────────────────
    def export_tasks(self) -> list:
        return self.list_tasks()
