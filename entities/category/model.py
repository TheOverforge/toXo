from dataclasses import dataclass


@dataclass
class Category:
    """Category/folder for organizing tasks."""
    id: int
    name: str
    color: str              # hex color, e.g. "#0a84ff"
    sort_order: int         # position in list (for drag&drop sorting)
    created_at: str         # ISO timestamp UTC
    task_count: int = 0     # virtual field, filled when loading from DB
