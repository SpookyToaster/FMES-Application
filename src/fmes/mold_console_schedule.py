"""Console-first mold day scheduling for experimental logic development."""

import pandas as pd

from .config import Columns

ALLOY_GROUP_COLUMN = "Compatibility Group"


def build_mold_schedule_by_alloy_group(schedule_rows_df, max_jobs_per_day=10, reference_date=None):
    """Assign rows to mold schedule days with due-date priority and day limits.

    Rules:
    - Jobs can be split across multiple days based on production limits.
    - Jobs due within the next 8 weeks are greedily pulled forward first.
    - Rows are then ordered by due date, Compatibility Group, and job number.
    - Each day can include at most max_jobs_per_day unique job numbers.
    - Line molds (Casting Type L) are capped at 6 molds per job per day.
    - Line molds (Casting Type L) are capped at 30 molds total per day.
    - Floor molds (Casting Type F) are capped at 3 molds total per day.

    Returns:
        pandas.DataFrame with Schedule Day assigned.
    """
    if schedule_rows_df is None or schedule_rows_df.empty:
        empty = pd.DataFrame()
        empty["Schedule Day"] = pd.Series(dtype="int64")
        return empty

    max_jobs_per_day = max(int(max_jobs_per_day or 0), 1)

    planned = schedule_rows_df.copy()
    if ALLOY_GROUP_COLUMN not in planned.columns:
        planned[ALLOY_GROUP_COLUMN] = planned.get(Columns.COL_ALLOY, pd.Series("", index=planned.index)).fillna("")

    planned["_DueDateSort"] = pd.to_datetime(planned.get(Columns.COL_DUE_DATE, pd.Series(dtype="object")), errors="coerce")
    if reference_date is None:
        reference_timestamp = pd.Timestamp.today().normalize()
    else:
        reference_timestamp = pd.to_datetime(reference_date, errors="coerce")
        if pd.isna(reference_timestamp):
            reference_timestamp = pd.Timestamp.today().normalize()
        else:
            reference_timestamp = pd.Timestamp(reference_timestamp).normalize()

    greedy_cutoff = reference_timestamp + pd.Timedelta(weeks=8)
    planned["_GreedyPriority"] = (
        planned["_DueDateSort"].notna() & (planned["_DueDateSort"] <= greedy_cutoff)
    ).map({True: 0, False: 1})

    planned = planned.sort_values(
        by=["_GreedyPriority", "_DueDateSort", ALLOY_GROUP_COLUMN, Columns.COL_JOB_NUMBER],
        ascending=[True, True, True, True],
        na_position="last",
    ).reset_index(drop=True)

    pending_items = []
    for _, row in planned.iterrows():
        job_number = str(row.get(Columns.COL_JOB_NUMBER, "") or "").strip()
        if not job_number:
            continue

        molds_remaining = int(pd.to_numeric(row.get("Molds for EXT", 0), errors="coerce") or 0)
        if molds_remaining <= 0:
            continue

        cast_type = str(row.get(Columns.COL_CAST_TYPE, "L") or "L").strip().upper()
        pour_weight = float(pd.to_numeric(row.get(Columns.COL_POUR_WEIGHT, 0), errors="coerce") or 0)
        pending_items.append(
            {
                "row": row,
                "job_number": job_number,
                "cast_type": cast_type,
                "pour_weight": pour_weight,
                "remaining": molds_remaining,
            }
        )

    assigned_rows = []
    current_day = 1
    while any(item["remaining"] > 0 for item in pending_items):
        jobs_on_day = set()
        l_molds_by_job = {}
        l_molds_on_day = 0
        f_molds_on_day = 0
        made_progress = False

        for item in pending_items:
            if item["remaining"] <= 0:
                continue

            job_number = item["job_number"]
            cast_type = item["cast_type"]

            is_new_job = job_number not in jobs_on_day
            if is_new_job and len(jobs_on_day) >= max_jobs_per_day:
                continue

            if cast_type == "F":
                capacity_remaining = 3 - f_molds_on_day
            else:
                per_job_remaining = 6 - l_molds_by_job.get(job_number, 0)
                total_l_remaining = 30 - l_molds_on_day
                capacity_remaining = min(per_job_remaining, total_l_remaining)

            if capacity_remaining <= 0:
                continue

            molds_for_chunk = min(item["remaining"], capacity_remaining)
            if molds_for_chunk <= 0:
                continue

            jobs_on_day.add(job_number)

            row_for_day = item["row"].copy()
            row_for_day["Molds for EXT"] = int(molds_for_chunk)
            row_for_day["Total Weight per EXT"] = int(max(item["pour_weight"], 0) * molds_for_chunk)
            row_for_day["Schedule Day"] = current_day
            assigned_rows.append(row_for_day)

            item["remaining"] -= molds_for_chunk
            made_progress = True

            if cast_type == "F":
                f_molds_on_day += molds_for_chunk
            else:
                l_molds_by_job[job_number] = l_molds_by_job.get(job_number, 0) + molds_for_chunk
                l_molds_on_day += molds_for_chunk

        if not made_progress:
            # Advance to the next day when nothing else can fit today.
            current_day += 1
            continue

        current_day += 1

    if not assigned_rows:
        empty = planned.iloc[0:0].copy()
        empty["Schedule Day"] = pd.Series(dtype="int64")
        return empty

    assigned = pd.DataFrame(assigned_rows)
    return assigned.drop(columns=["_DueDateSort", "_GreedyPriority"], errors="ignore")


def print_mold_schedule_console(assigned_rows):
    """Print a compact console view of day-by-day mold scheduling."""
    if assigned_rows is None or assigned_rows.empty:
        print("No mold rows were scheduled.")
        return

    for day in sorted(pd.to_numeric(assigned_rows["Schedule Day"], errors="coerce").dropna().astype(int).unique()):
        day_rows = assigned_rows[pd.to_numeric(assigned_rows["Schedule Day"], errors="coerce") == day].copy()
        day_rows = day_rows.sort_values(
            by=[Columns.COL_ALLOY, Columns.COL_DUE_DATE, Columns.COL_JOB_NUMBER],
            ascending=[True, True, True],
            na_position="last",
        )
        molds = pd.to_numeric(day_rows.get("Molds for EXT", pd.Series(0, index=day_rows.index)), errors="coerce").fillna(0)
        pour_weight = pd.to_numeric(day_rows.get(Columns.COL_POUR_WEIGHT, pd.Series(0, index=day_rows.index)), errors="coerce").fillna(0)
        day_rows["Row Weight"] = (molds * pour_weight).round().astype(int)

        unique_jobs = day_rows[Columns.COL_JOB_NUMBER].astype(str).str.strip().nunique()
        total_molds = molds.sum()

        print("\n" + "=" * 56)
        print(f"Mold Schedule Day {day}")
        print("=" * 56)
        print(day_rows[[ALLOY_GROUP_COLUMN, Columns.COL_ALLOY, Columns.COL_JOB_NUMBER, Columns.COL_DUE_DATE, "Molds for EXT", "Row Weight"]].to_string(index=False))
        print(f"\nUnique Jobs: {unique_jobs}")
        print(f"Total Molds: {int(total_molds)}")
