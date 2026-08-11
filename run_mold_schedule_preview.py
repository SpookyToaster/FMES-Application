"""Console preview for experimental mold scheduling by alloy group."""

import argparse
import os
import sys
from datetime import datetime, timedelta

import pandas as pd

sys.path.insert(0, "src")

from fmes.config import Columns, Paths
from fmes.mold_console_schedule import build_mold_schedule_by_alloy_group, print_mold_schedule_console
from fmes.scheduler_build import build_schedule_dates, build_schedule_rows
from fmes.scheduler_export import build_daily_export_blocks, export_mold_schedule
from fmes.scheduler_filter import mold_scheduler
from fmes.scheduler_io import read_file


def main():
    parser = argparse.ArgumentParser(description="Preview mold day schedule by alloy groups.")
    parser.add_argument("--source", choices=["excel", "sql"], default="excel")
    parser.add_argument("--max-jobs-per-day", type=int, default=10)
    parser.add_argument("--output-file", default=str(Paths.MOLD_SCHEDULE_OUTPUT))
    args = parser.parse_args()

    os.environ["SCHEDULER_INPUT_SOURCE"] = args.source

    try:
        input_df = read_file(source=args.source)
        eligible_jobs = mold_scheduler(input_df)
        schedule_rows = pd.DataFrame(build_schedule_rows(eligible_jobs))

        assigned = build_mold_schedule_by_alloy_group(
            schedule_rows_df=schedule_rows,
            max_jobs_per_day=args.max_jobs_per_day,
        )

        print("=== Mold Schedule Preview (Console) ===")
        print(f"Input source: {args.source}")
        print(f"Eligible jobs: {len(eligible_jobs)}")
        print(f"Scheduler rows: {len(schedule_rows)}")

        if assigned.empty:
            print("No rows assigned.")
            return

        day_count = pd.to_numeric(assigned["Schedule Day"], errors="coerce").dropna().astype(int).nunique()
        print(f"Planned mold days: {day_count}")

        mold_days = sorted(pd.to_numeric(assigned["Schedule Day"], errors="coerce").dropna().astype(int).unique())
        day_calendar = build_schedule_dates(
            {day: pd.DataFrame() for day in mold_days},
            datetime.today() + timedelta(days=1),
        )
        mold_day_dates = {day: day_calendar[day] for day in mold_days}
        daily_schedules = {
            day: assigned[pd.to_numeric(assigned["Schedule Day"], errors="coerce") == day].copy()
            for day in mold_days
        }
        export_blocks = build_daily_export_blocks(daily_schedules, mold_day_dates)
        export_mold_schedule(export_blocks, output_file=args.output_file)

        print_mold_schedule_console(assigned)
        print(f"\nSaved mold schedule workbook: {args.output_file}")
    except Exception as exc:
        message = str(exc)
        print("Mold schedule preview failed.")
        print(message)
        if "Permission denied" in message or "Failed to read schedule input" in message:
            print("Hint: close Open Order Report.xlsx if it is open/locked, then retry.")
            print("Hint: you can also run with --source sql to avoid the Excel file lock path.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
