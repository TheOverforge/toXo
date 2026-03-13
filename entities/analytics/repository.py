"""AnalyticsDbMixin — read-only aggregate queries for the analytics view."""
from __future__ import annotations


class AnalyticsDbMixin:
    """Mix-in that provides analytics/reporting queries.

    Expects the host class to supply:
      self._con — sqlite3.Connection
    """

    def get_completed_per_day(self, since_iso: str) -> list[tuple[str, int]]:
        rows = self._con.execute("""
            SELECT DATE(completed_at, 'localtime') AS d, COUNT(*) AS cnt
            FROM tasks
            WHERE is_done = 1
              AND completed_at IS NOT NULL
              AND completed_at >= ?
            GROUP BY d
            ORDER BY d
        """, (since_iso,)).fetchall()
        return [(r[0], r[1]) for r in rows]

    def get_created_vs_completed(self, since_iso: str) -> list[tuple[str, int, int]]:
        rows = self._con.execute("""
            WITH created AS (
                SELECT DATE(created_at, 'localtime') AS d, COUNT(*) AS cnt
                FROM tasks
                WHERE created_at >= ?
                GROUP BY d
            ),
            completed AS (
                SELECT DATE(completed_at, 'localtime') AS d, COUNT(*) AS cnt
                FROM tasks
                WHERE is_done = 1
                  AND completed_at IS NOT NULL
                  AND completed_at >= ?
                GROUP BY d
            ),
            dates AS (
                SELECT d FROM created
                UNION
                SELECT d FROM completed
            )
            SELECT dates.d, COALESCE(created.cnt, 0), COALESCE(completed.cnt, 0)
            FROM dates
            LEFT JOIN created ON dates.d = created.d
            LEFT JOIN completed ON dates.d = completed.d
            ORDER BY dates.d
        """, (since_iso, since_iso)).fetchall()
        return [(r[0], r[1], r[2]) for r in rows]

    def get_created_vs_completed_between(
        self, since_iso: str, until_iso: str
    ) -> list[tuple[str, int, int]]:
        rows = self._con.execute("""
            WITH created AS (
                SELECT DATE(created_at, 'localtime') AS d, COUNT(*) AS cnt
                FROM tasks
                WHERE created_at >= ? AND created_at < ?
                GROUP BY d
            ),
            completed AS (
                SELECT DATE(completed_at, 'localtime') AS d, COUNT(*) AS cnt
                FROM tasks
                WHERE is_done = 1
                  AND completed_at IS NOT NULL
                  AND completed_at >= ? AND completed_at < ?
                GROUP BY d
            ),
            dates AS (
                SELECT d FROM created
                UNION
                SELECT d FROM completed
            )
            SELECT dates.d, COALESCE(created.cnt, 0), COALESCE(completed.cnt, 0)
            FROM dates
            LEFT JOIN created ON dates.d = created.d
            LEFT JOIN completed ON dates.d = completed.d
            ORDER BY dates.d
        """, (since_iso, until_iso, since_iso, until_iso)).fetchall()
        return [(r[0], r[1], r[2]) for r in rows]

    def get_kpi(self, since_iso: str) -> dict:
        total_completed = self._con.execute(
            "SELECT COUNT(*) FROM tasks WHERE is_done = 1 AND completed_at >= ?",
            (since_iso,)
        ).fetchone()[0]

        period_tasks = self._con.execute(
            "SELECT COUNT(*) FROM tasks WHERE created_at >= ?", (since_iso,)
        ).fetchone()[0]
        period_done = self._con.execute(
            "SELECT COUNT(*) FROM tasks WHERE created_at >= ? AND is_done = 1",
            (since_iso,)
        ).fetchone()[0]

        completion_pct = round(period_done / period_tasks * 100, 1) if period_tasks > 0 else 0.0

        avg_row = self._con.execute("""
            SELECT AVG(
                (JULIANDAY(completed_at) - JULIANDAY(created_at)) * 24
            )
            FROM tasks
            WHERE is_done = 1
              AND completed_at IS NOT NULL
              AND completed_at >= ?
              AND created_at IS NOT NULL
        """, (since_iso,)).fetchone()
        avg_hours = round(avg_row[0], 1) if avg_row[0] is not None else 0.0

        streak = 0
        rows = self._con.execute("""
            SELECT DISTINCT DATE(completed_at, 'localtime') AS d
            FROM tasks
            WHERE is_done = 1 AND completed_at IS NOT NULL
            ORDER BY d DESC
        """).fetchall()
        if rows:
            from datetime import date, timedelta
            today = date.today()
            expected = today
            for (d_str,) in rows:
                try:
                    d = date.fromisoformat(d_str)
                except (ValueError, TypeError):
                    continue
                if d == expected:
                    streak += 1
                    expected -= timedelta(days=1)
                elif d < expected:
                    break

        return {
            "total_completed": total_completed,
            "completion_pct": completion_pct,
            "period_done": period_done,
            "period_tasks": period_tasks,
            "avg_hours": avg_hours,
            "streak": streak,
        }

    def get_status_distribution(self, since_iso: str) -> dict:
        total = self._con.execute(
            "SELECT COUNT(*) FROM tasks WHERE created_at >= ?", (since_iso,)
        ).fetchone()[0]
        done = self._con.execute(
            "SELECT COUNT(*) FROM tasks WHERE created_at >= ? AND is_done = 1",
            (since_iso,)
        ).fetchone()[0]
        return {"active": total - done, "done": done}

    def get_completed_by_weekday(self, since_iso: str) -> list[tuple[int, int]]:
        rows = self._con.execute("""
            SELECT CAST(strftime('%w', completed_at, 'localtime') AS INTEGER) AS dow, COUNT(*) AS cnt
            FROM tasks
            WHERE is_done = 1
              AND completed_at IS NOT NULL
              AND completed_at >= ?
            GROUP BY dow
            ORDER BY dow
        """, (since_iso,)).fetchall()
        result = {}
        for dow_sqlite, cnt in rows:
            dow_mon = (dow_sqlite - 1) % 7
            result[dow_mon] = result.get(dow_mon, 0) + cnt
        return [(k, result[k]) for k in sorted(result.keys())]

    def get_cumulative_completed(self, since_iso: str) -> list[tuple[str, int]]:
        rows = self._con.execute("""
            SELECT DATE(completed_at, 'localtime') AS d, COUNT(*) AS cnt
            FROM tasks
            WHERE is_done = 1
              AND completed_at IS NOT NULL
              AND completed_at >= ?
            GROUP BY d
            ORDER BY d
        """, (since_iso,)).fetchall()
        cumulative = []
        total = 0
        for d_str, cnt in rows:
            total += cnt
            cumulative.append((d_str, total))
        return cumulative

    def get_kpi_between(self, since_iso: str, until_iso: str) -> dict:
        total_completed = self._con.execute(
            "SELECT COUNT(*) FROM tasks WHERE is_done = 1 "
            "AND completed_at IS NOT NULL AND completed_at >= ? AND completed_at < ?",
            (since_iso, until_iso)
        ).fetchone()[0]

        avg_row = self._con.execute("""
            SELECT AVG(
                (JULIANDAY(completed_at) - JULIANDAY(created_at)) * 24
            )
            FROM tasks
            WHERE is_done = 1
              AND completed_at IS NOT NULL
              AND completed_at >= ? AND completed_at < ?
              AND created_at IS NOT NULL
        """, (since_iso, until_iso)).fetchone()
        avg_hours = round(avg_row[0], 1) if avg_row[0] is not None else 0.0

        return {
            "total_completed": total_completed,
            "avg_hours": avg_hours,
        }

    def get_max_streak(self) -> int:
        rows = self._con.execute("""
            SELECT DISTINCT DATE(completed_at, 'localtime') AS d
            FROM tasks
            WHERE is_done = 1 AND completed_at IS NOT NULL
            ORDER BY d
        """).fetchall()
        if not rows:
            return 0
        from datetime import date, timedelta
        max_s = 1
        cur_s = 1
        prev_d = date.fromisoformat(rows[0][0])
        for (d_str,) in rows[1:]:
            try:
                d = date.fromisoformat(d_str)
            except (ValueError, TypeError):
                continue
            if d == prev_d + timedelta(days=1):
                cur_s += 1
                if cur_s > max_s:
                    max_s = cur_s
            else:
                cur_s = 1
            prev_d = d
        return max_s
