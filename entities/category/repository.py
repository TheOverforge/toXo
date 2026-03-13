"""CategoryDbMixin — category CRUD and task-category assignment methods."""
from __future__ import annotations

_TASK_COLS = "id, title, description, is_done, created_at, completed_at, updated_at, priority, category_id, remind_at, remind_shown, deadline_at, deadline_notified, is_pinned, recurrence, tags, sort_order, is_archived"
_CATEGORY_COLS = "id, name, color, sort_order, created_at"


class CategoryDbMixin:
    """Mix-in that provides category-related DB methods.

    Expects the host class to supply:
      self._con       — sqlite3.Connection
      self._now_iso() — UTC ISO timestamp string
      self._row_to_task() — from TaskDbMixin
    """

    # ── row helper ───────────────────────────────────────
    def _row_to_category(self, r):
        from entities.category.model import Category
        return Category(
            id=r[0],
            name=r[1],
            color=r[2],
            sort_order=r[3],
            created_at=r[4],
            task_count=0,
        )

    # ── category CRUD ────────────────────────────────────
    def add_category(self, name: str, color: str) -> int:
        name = name.strip()
        if not name:
            raise ValueError("Category name cannot be empty")
        max_order = self._con.execute(
            "SELECT COALESCE(MAX(sort_order), -1) FROM categories"
        ).fetchone()[0]
        now = self._now_iso()
        cur = self._con.execute(
            "INSERT INTO categories(name, color, sort_order, created_at) VALUES (?, ?, ?, ?)",
            (name, color, max_order + 1, now)
        )
        self._con.commit()
        return int(cur.lastrowid)

    def list_categories(self):
        rows = self._con.execute(
            f"SELECT {_CATEGORY_COLS} FROM categories ORDER BY sort_order"
        ).fetchall()
        categories = [self._row_to_category(r) for r in rows]
        for cat in categories:
            cat.task_count = self._con.execute(
                "SELECT COUNT(*) FROM tasks WHERE category_id = ?", (cat.id,)
            ).fetchone()[0]
        return categories

    def get_category(self, category_id: int):
        row = self._con.execute(
            f"SELECT {_CATEGORY_COLS} FROM categories WHERE id=?", (category_id,)
        ).fetchone()
        if not row:
            return None
        cat = self._row_to_category(row)
        cat.task_count = self._con.execute(
            "SELECT COUNT(*) FROM tasks WHERE category_id = ?", (cat.id,)
        ).fetchone()[0]
        return cat

    def update_category(self, category_id: int, name: str, color: str) -> None:
        name = name.strip()
        if not name:
            raise ValueError("Category name cannot be empty")
        self._con.execute(
            "UPDATE categories SET name=?, color=? WHERE id=?",
            (name, color, category_id)
        )
        self._con.commit()

    def delete_category(self, category_id: int) -> None:
        self._con.execute(
            "UPDATE tasks SET category_id = NULL WHERE category_id = ?",
            (category_id,)
        )
        self._con.execute("DELETE FROM categories WHERE id=?", (category_id,))
        self._con.commit()

    def reorder_categories(self, category_ids: list[int]) -> None:
        for i, cat_id in enumerate(category_ids):
            self._con.execute(
                "UPDATE categories SET sort_order=? WHERE id=?", (i, cat_id)
            )
        self._con.commit()

    def set_task_category(self, task_id: int, category_id: int | None) -> None:
        now = self._now_iso()
        self._con.execute(
            "UPDATE tasks SET category_id=?, updated_at=? WHERE id=?",
            (category_id, now, task_id)
        )
        self._con.commit()

    def count_tasks_in_category(self, category_id: int | None) -> int:
        if category_id is None:
            return self._con.execute(
                "SELECT COUNT(*) FROM tasks WHERE category_id IS NULL"
            ).fetchone()[0]
        return self._con.execute(
            "SELECT COUNT(*) FROM tasks WHERE category_id = ?", (category_id,)
        ).fetchone()[0]

    def list_tasks_by_category(self, category_id: int | None):
        if category_id is None:
            rows = self._con.execute(
                f"SELECT {_TASK_COLS} FROM tasks WHERE category_id IS NULL"
            ).fetchall()
        else:
            rows = self._con.execute(
                f"SELECT {_TASK_COLS} FROM tasks WHERE category_id = ?", (category_id,)
            ).fetchall()
        return [self._row_to_task(r) for r in rows]
