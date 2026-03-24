"""Unit tests for domain model pure logic (no DB needed)."""
import pytest
from entities.finance.model import Goal


class TestGoalProgressPct:
    def test_normal(self):
        g = Goal(1, "New monitor", 45_000, 18_000, None, "#bf5af2", "₽", "2026-01-01")
        assert g.progress_pct == 40

    def test_zero_target_returns_zero(self):
        g = Goal(1, "X", 0, 100, None, "#0a84ff", "₽", "2026-01-01")
        assert g.progress_pct == 0

    def test_over_target_capped_at_100(self):
        g = Goal(1, "X", 1000, 2000, None, "#0a84ff", "₽", "2026-01-01")
        assert g.progress_pct == 100

    def test_exactly_reached(self):
        g = Goal(1, "X", 500, 500, None, "#0a84ff", "₽", "2026-01-01")
        assert g.progress_pct == 100

    def test_zero_saved(self):
        g = Goal(1, "X", 10_000, 0, None, "#0a84ff", "₽", "2026-01-01")
        assert g.progress_pct == 0

    def test_fractional_rounds_down(self):
        g = Goal(1, "X", 3, 1, None, "#0a84ff", "₽", "2026-01-01")
        assert g.progress_pct == 33  # int(1/3*100)


class TestGoalRemaining:
    def test_normal(self):
        g = Goal(1, "X", 120_000, 52_000, None, "#0a84ff", "₽", "2026-01-01")
        assert g.remaining == pytest.approx(68_000.0)

    def test_exactly_reached_returns_zero(self):
        g = Goal(1, "X", 1000, 1000, None, "#0a84ff", "₽", "2026-01-01")
        assert g.remaining == 0.0

    def test_over_target_returns_zero(self):
        g = Goal(1, "X", 1000, 1500, None, "#0a84ff", "₽", "2026-01-01")
        assert g.remaining == 0.0
