from dataclasses import dataclass


@dataclass
class Task:
    id: int
    title: str
    description: str
    is_done: bool
    created_at: str              # ISO string
    completed_at: str | None = None   # when marked done
    updated_at: str | None = None     # last edit timestamp
    priority: int = 0                 # 0=none, 1=low, 2=med, 3=high
    category_id: int | None = None    # category/folder for organizing tasks
    remind_at: str | None = None      # UTC ISO datetime for reminder, or None
    remind_shown: bool = False        # True once the notification has been shown
    deadline_at: str | None = None   # UTC ISO datetime for deadline, or None
    deadline_notified: int = 0       # 0=none, 1=today shown, 2=overdue shown
    is_pinned: bool = False           # True = always sort to top
    recurrence: str | None = None    # None / "daily" / "weekly" / "monthly"
    tags: str = ""                    # comma-separated tag names, e.g. "работа,срочно"
    sort_order: int = 0               # manual sort position (lower = higher in list)
    is_archived: bool = False         # True = task is in the archive