from __future__ import annotations

import calendar as _cal
from datetime import datetime, timedelta, timezone

from shared.api.db.connection import Database


class AnalyticsService:
    def __init__(self, db: Database):
        self._db = db

    @staticmethod
    def _since_iso(days: int) -> str:
        """Calendar-based period start (local midnight → UTC).

        days=1 → today 00:00 local
        days=7 → 7 calendar days incl. today (today-6) 00:00 local
        """
        local_midnight = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        start = local_midnight - timedelta(days=days - 1)
        start_utc = start.astimezone(timezone.utc)
        return start_utc.isoformat(timespec="seconds")

    def completed_per_day(self, days: int = 30) -> list[tuple[str, int]]:
        return self._db.get_completed_per_day(self._since_iso(days))

    def created_vs_completed(self, days: int = 30) -> list[tuple[str, int, int]]:
        return self._db.get_created_vs_completed(self._since_iso(days))

    def kpi(self, days: int = 30) -> dict:
        return self._db.get_kpi(self._since_iso(days))

    def kpi_with_delta(self, days: int = 7) -> dict:
        """Current KPI + delta vs previous equivalent period."""
        current = self.kpi(days)

        # Previous period: [today - 2*days, today - days)
        prev_start = self._since_iso(2 * max(days, 1))
        prev_end = self._since_iso(days)
        prev = self._db.get_kpi_between(prev_start, prev_end)

        done_delta = current["total_completed"] - prev["total_completed"]

        # avg delta only meaningful when prev had completions
        prev_has_avg = prev["avg_hours"] > 0
        avg_delta_hours = round(current["avg_hours"] - prev["avg_hours"], 1)

        max_streak = self._db.get_max_streak()

        return {
            **current,
            "done_delta": done_delta,
            "avg_delta_hours": avg_delta_hours,
            "max_streak": max_streak,
            "prev_has_avg": prev_has_avg,
        }

    def status_distribution(self, days: int = 30) -> dict:
        return self._db.get_status_distribution(self._since_iso(days))

    def completed_by_weekday(self, days: int = 30) -> list[tuple[int, int]]:
        return self._db.get_completed_by_weekday(self._since_iso(days))

    def cumulative_completed(self, days: int = 30) -> list[tuple[str, int]]:
        return self._db.get_cumulative_completed(self._since_iso(days))

    def tasks_for_day(self, date_str: str) -> dict:
        """Return {'created': [...], 'completed': [...]} for a specific local date."""
        return {
            "created": self._db.get_tasks_created_on(date_str),
            "completed": self._db.get_tasks_completed_on(date_str),
        }

    def tasks_with_deadline_on(self, date_str: str) -> list:
        """Tasks (non-archived) with deadline on the given local date (YYYY-MM-DD)."""
        return self._db.get_tasks_with_deadline_on(date_str)

    def month_data(self, year: int, month: int) -> dict[str, tuple[int, int]]:
        """Returns {date_str: (created, completed)} for every active day in the month."""
        start_local = datetime(year, month, 1)
        start_utc = start_local.astimezone(timezone.utc)
        since = start_utc.isoformat(timespec="seconds")

        last_day = _cal.monthrange(year, month)[1]
        end_local = datetime(year, month, last_day) + timedelta(days=1)
        end_utc = end_local.astimezone(timezone.utc)
        until = end_utc.isoformat(timespec="seconds")

        rows = self._db.get_created_vs_completed_between(since, until)
        return {d: (cr, co) for d, cr, co in rows}
