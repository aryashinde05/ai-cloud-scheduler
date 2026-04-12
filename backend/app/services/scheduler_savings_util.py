"""Helpers to estimate $ saved per scheduled stop from stop/start times and hourly rate."""

from __future__ import annotations

import os
from typing import Any, Optional


def off_hours_between_stop_and_start(stop_time: str, start_time: str) -> float:
    """
    Hours the instance is off after a stop event until the next scheduled start
    (same pattern as cron: stop at stop_time, start at start_time next cycle).
    """
    sm = _to_minutes(stop_time)
    em = _to_minutes(start_time)
    if em <= sm:
        mins = 24 * 60 - sm + em
    else:
        mins = em - sm
    return round(mins / 60.0, 4)


def _to_minutes(t: str) -> int:
    parts = (t or "00:00").strip().split(":")
    h = int(parts[0]) if parts else 0
    m = int(parts[1]) if len(parts) > 1 else 0
    return (h % 24) * 60 + (m % 60)


def resolve_hourly_usd(row: Optional[Any]) -> float:
    hourly = getattr(row, "estimated_hourly_usd", None) if row is not None else None
    if hourly is not None and float(hourly) > 0:
        return float(hourly)
    return float(os.getenv("SCHEDULER_DEFAULT_HOURLY_USD", "0.08"))


def estimated_savings_for_schedule_stop(row: Any) -> float:
    h = off_hours_between_stop_and_start(row.stop_time, row.start_time)
    hourly = resolve_hourly_usd(row)
    return round(h * hourly, 4)


def estimated_monthly_for_schedule(row: Any) -> float:
    """Rough projected monthly $ if every off-hour night is saved (pattern-aware)."""
    h = off_hours_between_stop_and_start(row.stop_time, row.start_time)
    hourly = resolve_hourly_usd(row)
    pat = (getattr(row, "days_pattern", None) or "all").lower().strip()
    if pat == "weekdays":
        nights = 22.0
    elif pat == "weekends":
        nights = 8.0
    else:
        nights = 30.0
    return round(h * nights * hourly, 2)
