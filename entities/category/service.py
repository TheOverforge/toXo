from __future__ import annotations

from typing import Optional

from shared.api.db.connection import Database
from entities.category.model import Category


class CategoryService:
    """Service for managing task categories."""

    def __init__(self, db: Database):
        self.db = db

    def list_categories(self) -> list[Category]:
        """Get all categories with task counts, sorted by sort_order."""
        return self.db.list_categories()

    def get_category(self, category_id: int) -> Optional[Category]:
        """Get category by ID."""
        return self.db.get_category(category_id)

    def create_category(self, name: str, color: str) -> int:
        """Create new category."""
        return self.db.add_category(name, color)

    def update_category(self, category_id: int, name: str, color: str) -> None:
        """Update category name and color."""
        self.db.update_category(category_id, name, color)

    def delete_category(self, category_id: int) -> None:
        """Delete category. Tasks in this category will have category_id = NULL."""
        self.db.delete_category(category_id)

    def reorder_categories(self, category_ids: list[int]) -> None:
        """Update order of categories (for drag&drop)."""
        self.db.reorder_categories(category_ids)

    def set_task_category(self, task_id: int, category_id: int | None) -> None:
        """Set category for task."""
        self.db.set_task_category(task_id, category_id)

    def count_tasks(self, category_id: int | None) -> int:
        """Count tasks in category (None = without category)."""
        return self.db.count_tasks_in_category(category_id)
