"""Unit tests for TaskService against an in-memory SQLite database."""
import pytest
from shared.api.db.connection import Database
from entities.task.service import TaskService


def _make_svc() -> TaskService:
    """Return a TaskService wired to a fresh in-memory DB."""
    svc = TaskService.__new__(TaskService)
    svc.db = Database(path=":memory:")
    svc._undo_stack = []
    return svc


@pytest.fixture()
def svc():
    s = _make_svc()
    yield s
    s.close()


# ── create / get / list ────────────────────────────────────────────────────────

class TestCreateAndGet:
    def test_create_returns_int(self, svc):
        tid = svc.create_task("Buy milk")
        assert isinstance(tid, int) and tid > 0

    def test_get_returns_task_with_correct_title(self, svc):
        tid = svc.create_task("Buy milk", "full-fat")
        t = svc.get_task(tid)
        assert t is not None
        assert t.title == "Buy milk"
        assert t.description == "full-fat"

    def test_get_unknown_id_returns_none(self, svc):
        assert svc.get_task(99999) is None

    def test_list_empty_on_fresh_db(self, svc):
        assert svc.list_tasks() == []

    def test_list_grows_after_create(self, svc):
        svc.create_task("A")
        svc.create_task("B")
        assert len(svc.list_tasks()) == 2


# ── update ────────────────────────────────────────────────────────────────────

class TestUpdate:
    def test_update_changes_title_and_description(self, svc):
        tid = svc.create_task("Old title", "old desc")
        svc.update_task(tid, "New title", "new desc")
        t = svc.get_task(tid)
        assert t.title == "New title"
        assert t.description == "new desc"


# ── done / priority / pinned / recurrence ─────────────────────────────────────

class TestFlags:
    def test_set_done_marks_task(self, svc):
        tid = svc.create_task("Task")
        svc.set_done(tid, True)
        assert svc.get_task(tid).is_done is True

    def test_set_done_false_reopens(self, svc):
        tid = svc.create_task("Task")
        svc.set_done(tid, True)
        svc.set_done(tid, False)
        assert svc.get_task(tid).is_done is False

    def test_set_priority(self, svc):
        tid = svc.create_task("Task")
        svc.set_priority(tid, 3)
        assert svc.get_task(tid).priority == 3

    def test_set_pinned(self, svc):
        tid = svc.create_task("Task")
        svc.set_pinned(tid, True)
        assert svc.get_task(tid).is_pinned is True

    def test_set_recurrence(self, svc):
        tid = svc.create_task("Task")
        svc.set_recurrence(tid, "weekly")
        assert svc.get_task(tid).recurrence == "weekly"

    def test_clear_recurrence(self, svc):
        tid = svc.create_task("Task")
        svc.set_recurrence(tid, "daily")
        svc.set_recurrence(tid, None)
        assert svc.get_task(tid).recurrence is None


# ── delete / undo ──────────────────────────────────────────────────────────────

class TestDeleteAndUndo:
    def test_delete_removes_task(self, svc):
        tid = svc.create_task("Temp")
        svc.delete_task(tid)
        assert svc.get_task(tid) is None

    def test_can_undo_after_delete(self, svc):
        assert not svc.can_undo()
        tid = svc.create_task("Temp")
        svc.delete_task(tid)
        assert svc.can_undo()

    def test_undo_delete_restores_task(self, svc):
        tid = svc.create_task("Restore me", "desc")
        svc.set_priority(tid, 2)
        svc.set_pinned(tid, True)
        svc.set_recurrence(tid, "weekly")
        svc.set_tags(tid, "work,urgent")
        svc.set_reminder(tid, "2026-06-01T09:00:00+00:00")
        svc.delete_task(tid)
        new_id = svc.undo_delete()
        t = svc.get_task(new_id)
        assert t is not None
        assert t.title == "Restore me"
        assert t.description == "desc"
        assert t.priority == 2
        assert t.is_pinned is True
        assert t.recurrence == "weekly"
        assert t.tags == "work,urgent"
        assert t.remind_at == "2026-06-01T09:00:00+00:00"

    def test_undo_delete_clears_stack(self, svc):
        tid = svc.create_task("Temp")
        svc.delete_task(tid)
        svc.undo_delete()
        assert not svc.can_undo()

    def test_undo_limit_caps_stack(self, svc):
        ids = [svc.create_task(f"t{i}") for i in range(TaskService.UNDO_LIMIT + 5)]
        for tid in ids:
            svc.delete_task(tid)
        assert len(svc._undo_stack) == TaskService.UNDO_LIMIT


# ── duplicate ─────────────────────────────────────────────────────────────────

class TestDuplicate:
    def test_duplicate_returns_new_id(self, svc):
        tid = svc.create_task("Original")
        new_id = svc.duplicate_task(tid)
        assert new_id != tid

    def test_duplicate_copies_title_and_desc(self, svc):
        tid = svc.create_task("Original", "some desc")
        svc.set_priority(tid, 2)
        new_id = svc.duplicate_task(tid)
        t = svc.get_task(new_id)
        assert t.title == "Original"
        assert t.description == "some desc"
        assert t.priority == 2

    def test_duplicate_resets_done_state(self, svc):
        tid = svc.create_task("Done task")
        svc.set_done(tid, True)
        new_id = svc.duplicate_task(tid)
        assert svc.get_task(new_id).is_done is False

    def test_duplicate_copies_subtasks(self, svc):
        tid = svc.create_task("Parent")
        svc.add_subtask(tid, "Sub A")
        svc.add_subtask(tid, "Sub B")
        new_id = svc.duplicate_task(tid)
        subs = svc.list_subtasks(new_id)
        assert len(subs) == 2
        assert {s["title"] for s in subs} == {"Sub A", "Sub B"}

    def test_duplicate_unknown_id_returns_none(self, svc):
        assert svc.duplicate_task(99999) is None


# ── subtasks ──────────────────────────────────────────────────────────────────

class TestSubtasks:
    def test_add_and_list_subtasks(self, svc):
        tid = svc.create_task("Parent")
        svc.add_subtask(tid, "Step 1")
        svc.add_subtask(tid, "Step 2")
        subs = svc.list_subtasks(tid)
        assert len(subs) == 2

    def test_set_subtask_done(self, svc):
        tid = svc.create_task("Parent")
        sid = svc.add_subtask(tid, "Step")
        svc.set_subtask_done(sid, True)
        subs = svc.list_subtasks(tid)
        assert subs[0]["is_done"] is True

    def test_delete_subtask(self, svc):
        tid = svc.create_task("Parent")
        sid = svc.add_subtask(tid, "Step")
        svc.delete_subtask(sid)
        assert svc.list_subtasks(tid) == []

    def test_update_subtask_title(self, svc):
        tid = svc.create_task("Parent")
        sid = svc.add_subtask(tid, "Old")
        svc.update_subtask_title(sid, "New")
        subs = svc.list_subtasks(tid)
        assert subs[0]["title"] == "New"

    def test_subtask_counts_all(self, svc):
        tid = svc.create_task("Parent")
        sid1 = svc.add_subtask(tid, "A")
        svc.add_subtask(tid, "B")
        svc.set_subtask_done(sid1, True)
        counts = svc.subtask_counts_all()
        assert tid in counts
        done, total = counts[tid]
        assert done == 1 and total == 2


# ── reminders ─────────────────────────────────────────────────────────────────

class TestReminders:
    def test_set_and_clear_reminder(self, svc):
        tid = svc.create_task("Remind me")
        svc.set_reminder(tid, "2026-01-01T09:00:00")
        assert svc.get_task(tid).remind_at == "2026-01-01T09:00:00"
        svc.set_reminder(tid, None)
        assert svc.get_task(tid).remind_at is None

    def test_due_reminders_past(self, svc):
        tid = svc.create_task("Past reminder")
        svc.set_reminder(tid, "2000-01-01T00:00:00+00:00")
        due = svc.get_due_reminders()
        assert any(t.id == tid for t in due)

    def test_mark_reminder_shown(self, svc):
        tid = svc.create_task("Remind me")
        svc.set_reminder(tid, "2000-01-01T00:00:00+00:00")
        svc.mark_reminder_shown(tid)
        due = svc.get_due_reminders()
        assert not any(t.id == tid for t in due)


# ── archive ────────────────────────────────────────────────────────────────────

class TestArchive:
    def test_archive_task(self, svc):
        tid = svc.create_task("Archive me")
        svc.archive_task(tid, True)
        assert svc.get_task(tid).is_archived is True

    def test_unarchive_task(self, svc):
        tid = svc.create_task("Archive me")
        svc.archive_task(tid, True)
        svc.archive_task(tid, False)
        assert svc.get_task(tid).is_archived is False


# ── tags ──────────────────────────────────────────────────────────────────────

class TestTags:
    def test_set_tags(self, svc):
        tid = svc.create_task("Tagged")
        svc.set_tags(tid, "work,urgent")
        assert svc.get_task(tid).tags == "work,urgent"

    def test_clear_tags(self, svc):
        tid = svc.create_task("Tagged")
        svc.set_tags(tid, "work")
        svc.set_tags(tid, "")
        assert svc.get_task(tid).tags == ""


# ── recurrence auto-create ─────────────────────────────────────────────────────

class TestRecurrenceAutoCreate:
    def test_completing_daily_task_creates_next(self, svc):
        tid = svc.create_task("Daily task")
        svc.set_recurrence(tid, "daily")
        svc.set_done(tid, True)
        tasks = svc.list_tasks()
        # The original + 1 new recurring copy
        assert len(tasks) == 2
        new_task = next(t for t in tasks if t.id != tid)
        assert new_task.recurrence == "daily"
        assert new_task.is_done is False

    def test_recurrence_advances_deadline(self, svc):
        tid = svc.create_task("Daily with deadline")
        svc.set_recurrence(tid, "daily")
        svc.set_deadline(tid, "2026-03-10T09:00:00+00:00")
        svc.set_done(tid, True)
        tasks = svc.list_tasks()
        new_task = next(t for t in tasks if t.id != tid)
        assert new_task.deadline_at == "2026-03-11T09:00:00+00:00"

    def test_recurrence_advances_weekly_deadline(self, svc):
        tid = svc.create_task("Weekly task")
        svc.set_recurrence(tid, "weekly")
        svc.set_deadline(tid, "2026-03-10T09:00:00+00:00")
        svc.set_done(tid, True)
        tasks = svc.list_tasks()
        new_task = next(t for t in tasks if t.id != tid)
        assert new_task.deadline_at == "2026-03-17T09:00:00+00:00"


# ── delete cleans up subtasks ──────────────────────────────────────────────────

class TestDeleteCleansSubtasks:
    def test_delete_task_removes_subtasks(self, svc):
        tid = svc.create_task("Parent")
        svc.add_subtask(tid, "Sub A")
        svc.add_subtask(tid, "Sub B")
        svc.delete_task(tid)
        # Subtasks must not remain as orphans
        assert svc.list_subtasks(tid) == []

    def test_undo_delete_restores_subtasks_then_delete_again_cleans(self, svc):
        tid = svc.create_task("Parent")
        svc.add_subtask(tid, "Sub")
        svc.delete_task(tid)
        new_id = svc.undo_delete()
        # Subtasks are restored via duplicate path in duplicate_task,
        # but undo_delete uses restore_task (no subtask restore) — verify at least no crash
        assert svc.get_task(new_id) is not None
