import pandas as pd

from config import Columns


filtered_job_counts = {
    "blank": 0,
    "hold": 0,
    "scheduled": 0,
    "job_type": 0,
    "cast_type": 0,
    "no_molds": 0,
    "added": 0,
}


def Mold_Scheduler(ReadyToMold):
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
    print("\nJobs selected for scheduling:")

    for job in jobs_to_schedule:
        print(
            f"{job[Columns.COL_JOB_NUMBER]} | "
            f"{job['Customer Name']} | "
            f"Molds Needed: {job[Columns.COL_MOLDS_NEEDED]}"
        )

    print(f"\nTotal Jobs Selected: {len(jobs_to_schedule)}")


def scheduled_rows_test(schedule_rows):
    for row in schedule_rows:
        print(
            f"{row[Columns.COL_JOB_NUMBER]}"
            f"{row['EXT']} | "
            f"{row['Molds for EXT']} molds"
        )
