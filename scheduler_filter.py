"""
Job filtering logic for Foundry Management and Execution System (FMES).

Filters the raw Open Order Report down to only the jobs that should be
scheduled for mold production on the upcoming days.

Exclusion rules (applied in order):
  - Blank job number
  - Hold flag = YES
  - Job type in [IFA, IFC]  (investment/flask jobs, not mold-poured)
  - Casting type = I        (investment casting)
  - Molds Needed <= 0

The module-level filtered_job_counts dict accumulates counts across calls
for diagnostic reporting.
"""

import pandas as pd

from config import Columns


filtered_job_counts = {
    "blank": 0,
    "hold": 0,
    "job_type": 0,
    "cast_type": 0,
    "no_molds": 0,
    "added": 0,
}


def Mold_Scheduler(ReadyToMold):
    """
    Filter a DataFrame of open orders down to jobs eligible for mold scheduling.

    Args:
        ReadyToMold: pandas DataFrame from the Open Order Report (sheet 'OOR').

    Returns:
        list of Series – one entry per job row that passed all filters.

    Raises:
        RuntimeError: Wraps any unexpected exception.
    """
    try:
        jobs_to_schedule = []

        for _, job in ReadyToMold.iterrows():
            if pd.isna(job[Columns.COL_JOB_NUMBER]):
                filtered_job_counts["blank"] += 1
                continue

            if str(job[Columns.COL_HOLD]).upper() == "YES":
                filtered_job_counts["hold"] += 1
                continue

            if str(job[Columns.COL_JOB_TYPE]).upper() in ["IFA", "IFC"]:
                filtered_job_counts["job_type"] += 1
                continue

            if str(job[Columns.COL_CAST_TYPE]).upper() == "I":
                filtered_job_counts["cast_type"] += 1
                continue

            if job[Columns.COL_MOLDS_NEEDED] <= 0:
                filtered_job_counts["no_molds"] += 1
                continue

            filtered_job_counts["added"] += 1
            jobs_to_schedule.append(job)

        return jobs_to_schedule
    except Exception as exc:
        raise RuntimeError("Failed while filtering jobs for mold scheduling") from exc


def jobs_to_schedule_test(jobs_to_schedule):
    """Print a diagnostic list of jobs selected for scheduling (manual debug helper)."""
    print("\nJobs selected for scheduling:")

    for job in jobs_to_schedule:
        print(
            f"{job[Columns.COL_JOB_NUMBER]} | "
            f"{job['Customer Name']} | "
            f"Molds Needed: {job[Columns.COL_MOLDS_NEEDED]}"
        )

    print(f"\nTotal Jobs Selected: {len(jobs_to_schedule)}")


def scheduled_rows_test(schedule_rows):
    """Print expanded extension rows (manual debug helper)."""
    for row in schedule_rows:
        print(
            f"{row[Columns.COL_JOB_NUMBER]}"
            f"{row['EXT']} | "
            f"{row['Molds for EXT']} molds"
        )
