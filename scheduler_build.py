"""
Schedule-building logic for Foundry Management and Execution System (FMES).

Responsibilities:
  - Split individual jobs into extension-sized work chunks (Expand_Job).
  - Assign each chunk to a numbered production day while respecting
    per-day and per-job mold capacity limits (Assign_days).
  - Attach calendar dates to day numbers, skipping weekends (Build_Schedule_Dates).
  - Assign heat numbers within each day based on alloy changes and
    the 2,300-lb heat weight limit (Build_Daily_Schedules).
"""

import math
import string
from datetime import timedelta

import pandas as pd

from config import Columns, DailyMoldLimits
from melt_planning import HEAT_WEIGHT_LIMIT_LBS, assign_heat_numbers


EXTENSION_WEIGHT_LIMIT_LBS = 2300
EXTENSION_MOLD_LIMIT = 10
_EXTENSION_ALPHABET = [ch for ch in string.ascii_uppercase if ch != "L"]


def _safe_int(value, default=0):
    """Convert value to int via ceiling, returning default on NaN or conversion error."""
    try:
        if pd.isna(value):
            return default
        return int(math.ceil(float(value)))
    except (TypeError, ValueError):
        return default


def get_extensions(num_splits):
    """
    Generate extension labels for a job split into num_splits chunks.

    A single-chunk job has no label ("").  Multi-chunk jobs get alphabetical
    labels (A, B, C …) with the final chunk labeled "L" (Last).

    Examples:
        get_extensions(1) -> [""]
        get_extensions(3) -> ["A", "B", "L"]
    """
    if num_splits == 1:
        return [""]

    extensions = []

    def _label_for_index(index):
        """Return a rollover label (A..Z without L, then AA, AB, ...)."""
        if index < 0:
            raise ValueError("index must be non-negative")

        base = len(_EXTENSION_ALPHABET)
        value = index + 1
        label_parts = []

        while value > 0:
            value, remainder = divmod(value - 1, base)
            label_parts.append(_EXTENSION_ALPHABET[remainder])

        return "".join(reversed(label_parts))

    for i in range(num_splits - 1):
        extensions.append(_label_for_index(i))

    extensions.append("L")
    return extensions


def get_daily_mold_limit(job):
    """
    Return the maximum molds this job may contribute to a single production day.

    Floor jobs (casting type F) and heavy jobs (pour weight > 300 lbs) are
    limited to 3 molds per day.  All other line jobs are limited to 6.
    """
    pour_weight = job[Columns.COL_POUR_WEIGHT]

    if pour_weight > 300:
        return 3

    casting_type = str(job[Columns.COL_CAST_TYPE]).upper()

    if casting_type == "F":
        return 3

    return 6


def get_extension_mold_limit(job):
    """
    Return the maximum molds allowed in a single extension for this job.

    Calculated as the lesser of EXTENSION_MOLD_LIMIT (10) and the number of
    molds whose combined pour weight fits within EXTENSION_WEIGHT_LIMIT_LBS
    (2,300 lbs).  Always at least 1.
    """
    pour_weight = float(job.get(Columns.COL_POUR_WEIGHT, 0) or 0)

    if pour_weight <= 0:
        max_by_weight = EXTENSION_MOLD_LIMIT
    else:
        max_by_weight = int(EXTENSION_WEIGHT_LIMIT_LBS // pour_weight)
        max_by_weight = max(max_by_weight, 1)

    return min(max_by_weight, EXTENSION_MOLD_LIMIT)


def _build_remaining_extension_plan(total_molds, completed_molds, extension_limit):
    """
    Build the list of extensions still needed after accounting for completed molds.

    The full job is divided into extension-sized chunks labeled by get_extensions().
    Any chunk that is already fully covered by completed_molds is skipped.  The
    first partially completed chunk is trimmed to its remaining count.

    Returns:
        list of (seq, ext_label, molds_remaining) tuples.
    """
    total_molds = max(total_molds, 0)
    completed_molds = max(completed_molds, 0)

    if total_molds <= 0:
        return []

    total_splits = math.ceil(total_molds / extension_limit)
    extensions = get_extensions(total_splits)

    chunk_sizes = []
    molds_remaining = total_molds
    for _ in extensions:
        chunk = min(extension_limit, molds_remaining)
        chunk_sizes.append(chunk)
        molds_remaining -= chunk

    remaining_plan = []
    molds_completed_left = completed_molds

    for seq, ext in enumerate(extensions):
        chunk_size = chunk_sizes[seq]

        if molds_completed_left >= chunk_size:
            molds_completed_left -= chunk_size
            continue

        remaining_for_ext = chunk_size - molds_completed_left
        molds_completed_left = 0

        if remaining_for_ext > 0:
            remaining_plan.append((seq, ext, remaining_for_ext))

    return remaining_plan


def expand_job(job):
    """
    Expand a single job into one or more extension rows ready for day assignment.

    Each returned row is a copy of the original job dict augmented with:
      EXT               – extension label ("", "A", "B", … "L")
      Extension_Seq     – zero-based ordinal position of this extension
      Molds for EXT     – mold count assigned to this extension
      Total Weight per EXT – combined pour weight for this extension

    Raises:
        RuntimeError: Wraps any unexpected exception with the job number.
    """
    try:
        molds_needed = _safe_int(job[Columns.COL_MOLDS_NEEDED], default=0)
        molds_completed = _safe_int(job.get("Molds Completed", 0), default=0)
        extension_limit = get_extension_mold_limit(job)
        total_molds = molds_needed + molds_completed

        extension_plan = _build_remaining_extension_plan(
            total_molds=total_molds,
            completed_molds=molds_completed,
            extension_limit=extension_limit,
        )

        rows = []
        molds_remaining = molds_needed

        for seq, ext, planned_molds in extension_plan:
            if molds_remaining <= 0:
                break

            molds_for_ext = min(planned_molds, molds_remaining)
            if molds_for_ext <= 0:
                continue

            row = job.copy()
            row["EXT"] = ext
            row["Extension_Seq"] = seq
            row["Molds for EXT"] = molds_for_ext
            pour_weight = float(row.get(Columns.COL_POUR_WEIGHT, 0) or 0)
            row["Total Weight per EXT"] = molds_for_ext * max(pour_weight, 0)
            rows.append(row)
            molds_remaining -= molds_for_ext

        return rows
    except Exception as exc:
        raise RuntimeError(
            f"Failed while expanding job {job.get(Columns.COL_JOB_NUMBER, '<unknown>')}"
        ) from exc


def build_schedule_rows(jobs_to_schedule):
    """
    Expand every job in jobs_to_schedule into extension rows.

    Args:
        jobs_to_schedule: Iterable of job dicts (one per row from the filtered DataFrame).

    Returns:
        list of dicts – all extension rows for all jobs combined.
    """
    try:
        schedule_rows = []

        for job in jobs_to_schedule:
            schedule_rows.extend(expand_job(job))

        return schedule_rows
    except Exception as exc:
        raise RuntimeError("Failed while building schedule rows") from exc


def is_f_job(job):
    """Return True if the job belongs in the floor (F) mold bucket."""
    if job[Columns.COL_POUR_WEIGHT] > 300:
        return True

    return str(job[Columns.COL_CAST_TYPE]).upper() == "F"


def assign_days(schedule_df):
    """
    Assign each extension row to a numbered production day.

    Iterates rows in their sorted order and greedily fills the current day.
    When a day is full (either the global bucket cap or the per-job daily cap
    is reached) the algorithm advances to the next day.  A single extension
    may be split across multiple days.

    Adds a 'Schedule Day' column (1-based int) to each allocated row.

    Returns:
        DataFrame of allocated rows with 'Schedule Day' populated.
    """
    try:
        day_usage = {}
        job_last_day = {}
        job_usage = {}
        allocated_rows = []

        for _, row in schedule_df.iterrows():
            molds_remaining = _safe_int(row.get("Molds for EXT", 0), default=0)
            if molds_remaining <= 0:
                continue

            bucket = "F" if is_f_job(row) else "L"
            job_num = row[Columns.COL_JOB_NUMBER]
            day = job_last_day.get(job_num, 1)
            per_job_daily_limit = get_daily_mold_limit(row)

            while molds_remaining > 0:
                if day not in day_usage:
                    day_usage[day] = {"L": 0, "F": 0}

                if day not in job_usage:
                    job_usage[day] = {}

                if job_num not in job_usage[day]:
                    job_usage[day][job_num] = {"L": 0, "F": 0}

                capacity = (
                    DailyMoldLimits.MAX_F_MOLDS_PER_DAY
                    if bucket == "F"
                    else DailyMoldLimits.MAX_L_MOLDS_PER_DAY
                )

                available_day_capacity = capacity - day_usage[day][bucket]
                available_job_capacity = per_job_daily_limit - job_usage[day][job_num][bucket]
                molds_for_day = min(
                    molds_remaining,
                    available_day_capacity,
                    available_job_capacity,
                )

                if molds_for_day > 0:
                    row_for_day = row.copy()
                    row_for_day["Molds for EXT"] = molds_for_day
                    pour_weight = float(row.get(Columns.COL_POUR_WEIGHT, 0) or 0)
                    row_for_day["Total Weight per EXT"] = molds_for_day * max(pour_weight, 0)
                    row_for_day["Schedule Day"] = day
                    allocated_rows.append(row_for_day)

                    day_usage[day][bucket] += molds_for_day
                    job_usage[day][job_num][bucket] += molds_for_day
                    job_last_day[job_num] = day
                    molds_remaining -= molds_for_day

                if molds_remaining > 0:
                    # Spill remaining molds for this extension into the next day.
                    day += 1

        return pd.DataFrame(allocated_rows)
    except Exception as exc:
        raise RuntimeError("Failed while assigning schedule days") from exc


def print_bucket(Schedule_Data_Frame):
    """Print a per-day summary of L and F mold counts versus daily limits."""
    for day in sorted(Schedule_Data_Frame["Schedule Day"].unique()):
        day_rows = Schedule_Data_Frame[Schedule_Data_Frame["Schedule Day"] == day]
        l_molds = day_rows[~day_rows.apply(is_f_job, axis=1)]["Molds for EXT"].sum()
        f_molds = day_rows[day_rows.apply(is_f_job, axis=1)]["Molds for EXT"].sum()

        print(
            f"Day {day}: "
            f"L={l_molds}/{DailyMoldLimits.MAX_L_MOLDS_PER_DAY}, "
            f"F={f_molds}/{DailyMoldLimits.MAX_F_MOLDS_PER_DAY}"
        )


def build_daily_schedules(Schedule_Data_Frame):
    """
    Group the allocated schedule by day and assign heat numbers within each day.

    Rows within a day are sorted by alloy then job number.  A new heat starts
    whenever the alloy changes or adding the next row's weight would exceed
    HEAT_WEIGHT_LIMIT_LBS (2,300 lbs).

    Returns:
        dict mapping day number (int) -> DataFrame with a 'Heat #' column added.
    """
    try:
        daily_schedules = {}

        for day in sorted(Schedule_Data_Frame["Schedule Day"].unique()):
            day_df = (
                Schedule_Data_Frame[Schedule_Data_Frame["Schedule Day"] == day]
                .copy()
                .sort_values(by=[Columns.COL_ALLOY, Columns.COL_JOB_NUMBER])
            )
            daily_schedules[day] = assign_heat_numbers(day_df)

        return daily_schedules
    except Exception as exc:
        raise RuntimeError("Failed while building daily schedules") from exc


def build_schedule_dates(daily_schedules, start_date):
    """
    Map each schedule day number to a real calendar date, skipping weekends.

    Args:
        daily_schedules: Dict keyed by day number (output of Build_Daily_Schedules).
        start_date:      datetime for the first production day (typically tomorrow).

    Returns:
        dict mapping day number -> {'date': date, 'weekday': weekday name string}.
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
