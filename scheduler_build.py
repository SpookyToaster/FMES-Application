import math
import string
from datetime import timedelta

import pandas as pd

from config import Columns, DailyMoldLimits


EXTENSION_WEIGHT_LIMIT_LBS = 2300
EXTENSION_MOLD_LIMIT = 10
HEAT_WEIGHT_LIMIT_LBS = 2300


def _safe_int(value, default=0):
    try:
        if pd.isna(value):
            return default
        return int(math.ceil(float(value)))
    except (TypeError, ValueError):
        return default


def get_extensions(num_splits):
    if num_splits == 1:
        return [""]

    extensions = []
    alphabet = list(string.ascii_uppercase)

    for i in range(num_splits - 1):
        extensions.append(alphabet[i])

    extensions.append("L")
    return extensions


def Get_daily_mold_limit(job):
    pour_weight = job[Columns.COL_POUR_WEIGHT]

    if pour_weight > 300:
        return 3

    casting_type = str(job[Columns.COL_CAST_TYPE]).upper()

    if casting_type == "F":
        return 3

    return 6


def Get_extension_mold_limit(job):
    pour_weight = float(job.get(Columns.COL_POUR_WEIGHT, 0) or 0)

    if pour_weight <= 0:
        max_by_weight = EXTENSION_MOLD_LIMIT
    else:
        max_by_weight = int(EXTENSION_WEIGHT_LIMIT_LBS // pour_weight)
        max_by_weight = max(max_by_weight, 1)

    return min(max_by_weight, EXTENSION_MOLD_LIMIT)


def Calculate_Splits(job):
    molds_needed = math.ceil(job[Columns.COL_MOLDS_NEEDED])
    extension_limit = Get_extension_mold_limit(job)
    return math.ceil(molds_needed / extension_limit)


def _build_remaining_extension_plan(total_molds, completed_molds, extension_limit):
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


def Expand_Job(job):
    try:
        molds_needed = _safe_int(job[Columns.COL_MOLDS_NEEDED], default=0)
        molds_completed = _safe_int(job.get("Molds Completed", 0), default=0)
        extension_limit = Get_extension_mold_limit(job)
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


def Build_Schedule_Rows(jobs_to_schedule):
    try:
        schedule_rows = []

        for job in jobs_to_schedule:
            schedule_rows.extend(Expand_Job(job))

        return schedule_rows
    except Exception as exc:
        raise RuntimeError("Failed while building schedule rows") from exc


def Is_F_Job(job):
    if job[Columns.COL_POUR_WEIGHT] > 300:
        return True

    return str(job[Columns.COL_CAST_TYPE]).upper() == "F"


def Assign_days(schedule_df):
    try:
        day_usage = {}
        job_last_day = {}
        job_usage = {}
        allocated_rows = []

        for _, row in schedule_df.iterrows():
            molds_remaining = _safe_int(row.get("Molds for EXT", 0), default=0)
            if molds_remaining <= 0:
                continue

            bucket = "F" if Is_F_Job(row) else "L"
            job_num = row[Columns.COL_JOB_NUMBER]
            day = job_last_day.get(job_num, 1)
            per_job_daily_limit = Get_daily_mold_limit(row)

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
                    day += 1

        print(day_usage)
        return pd.DataFrame(allocated_rows)
    except Exception as exc:
        raise RuntimeError("Failed while assigning schedule days") from exc


def print_bucket(Schedule_Data_Frame):
    for day in sorted(Schedule_Data_Frame["Schedule Day"].unique()):
        day_rows = Schedule_Data_Frame[Schedule_Data_Frame["Schedule Day"] == day]
        l_molds = day_rows[~day_rows.apply(Is_F_Job, axis=1)]["Molds for EXT"].sum()
        f_molds = day_rows[day_rows.apply(Is_F_Job, axis=1)]["Molds for EXT"].sum()

        print(
            f"Day {day}: "
            f"L={l_molds}/{DailyMoldLimits.MAX_L_MOLDS_PER_DAY}, "
            f"F={f_molds}/{DailyMoldLimits.MAX_F_MOLDS_PER_DAY}"
        )


def Build_Daily_Schedules(Schedule_Data_Frame):
    try:
        def assign_heat_numbers(day_df):
            if day_df.empty:
                day_df["Heat #"] = []
                return day_df

            heat_numbers = []
            heat_number = 0
            current_alloy = None
            current_heat_weight = 0.0

            for _, row in day_df.iterrows():
                alloy = str(row.get(Columns.COL_ALLOY, "") or "")
                row_weight = float(row.get("Total Weight per EXT", 0) or 0)
                row_weight = max(row_weight, 0)

                needs_new_heat = False

                if alloy != current_alloy:
                    needs_new_heat = True
                elif current_heat_weight + row_weight > HEAT_WEIGHT_LIMIT_LBS:
                    needs_new_heat = True

                if needs_new_heat:
                    heat_number += 1
                    current_alloy = alloy
                    current_heat_weight = 0.0

                current_heat_weight += row_weight
                heat_numbers.append(heat_number)

            day_df = day_df.copy()
            day_df["Heat #"] = heat_numbers
            return day_df

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


def Build_Schedule_Dates(daily_schedules, start_date):
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
