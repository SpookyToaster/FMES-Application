"""
Schedule-building helpers for the experimental scheduler branch.

Current responsibilities:
- Normalize jobs into scheduler-ready rows.
- Build a weekday-only calendar mapping for schedule day numbers.
"""

import math
from datetime import timedelta

import pandas as pd

from .config import Columns


def _safe_int(value, default=0):
    """Convert value to int via ceiling, returning default on NaN or conversion error."""
    try:
        if pd.isna(value):
            return default
        return int(math.ceil(float(value)))
    except (TypeError, ValueError):
        return default


def expand_job(job):
    """
    Build a single scheduler row for one job (no extension splitting).

    This branch intentionally removes extension chunking. The returned row keeps
    compatible export columns so report formatting code continues to work.
    """
    try:
        molds_needed = _safe_int(job[Columns.COL_MOLDS_NEEDED], default=0)
        if molds_needed <= 0:
            return []

        row = job.copy()
        row["EXT"] = ""
        row["Extension_Seq"] = 0
        row["Molds for EXT"] = molds_needed
        pour_weight = float(row.get(Columns.COL_POUR_WEIGHT, 0) or 0)
        row["Total Weight per EXT"] = molds_needed * max(pour_weight, 0)
        return [row]
    except Exception as exc:
        raise RuntimeError(
            f"Failed while expanding job {job.get(Columns.COL_JOB_NUMBER, '<unknown>')}"
        ) from exc


def build_schedule_rows(jobs_to_schedule):
    """Build scheduler rows for every eligible job."""
    try:
        schedule_rows = []
        for job in jobs_to_schedule:
            schedule_rows.extend(expand_job(job))
        return schedule_rows
    except Exception as exc:
        raise RuntimeError("Failed while building schedule rows") from exc


def build_schedule_dates(daily_schedules, start_date):
    """
    Map each schedule day number to a real calendar date, skipping weekends.

    Args:
        daily_schedules: Dict keyed by day number.
        start_date: datetime for the first production day.

    Returns:
        dict mapping day number -> {"date": date, "weekday": weekday name}.
    """
    try:
        day_dates = {}
        current_date = start_date

        for day in sorted(daily_schedules.keys()):
            while current_date.weekday() > 4:
                current_date += timedelta(days=1)

            day_dates[day] = {"date": current_date, "weekday": current_date.strftime("%A")}
            current_date += timedelta(days=1)

        return day_dates
    except Exception as exc:
        raise RuntimeError("Failed while building schedule dates") from exc
