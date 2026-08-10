"""
FMES scheduling entry point.

Orchestrates the full scheduling pipeline:
  1. Read the Open Order Report from Excel.
  2. Filter jobs eligible for mold scheduling.
  3. Expand jobs into extension-sized work chunks.
  4. Assign each chunk to a production day respecting daily mold capacity.
  5. Attach calendar dates (skipping weekends) and heat numbers.
  6. Export the result to Mold Schedule.xlsx and Heat Summary.xlsx.

Import Schedule_Molds() from Main.py or tests.
"""

from datetime import datetime, timedelta
import os

import pandas as pd

from config import Columns
from scheduler_build import (
    assign_days,
    build_daily_schedules,
    build_schedule_dates,
    build_schedule_rows,
    print_bucket,
)

from scheduler_export import (
    build_daily_export_blocks,
    print_export_blocks,
)

from scheduler_filter import mold_scheduler
from scheduler_io import read_file, sync_open_order_report_with_sql


def schedule_molds():
    """
    Run the complete mold scheduling pipeline and return export blocks.

    Returns:
        dict: Keyed by schedule day (int). Each value contains:
              'date', 'weekday', 'rows' (DataFrame), 'weight_total', 'mold_total'.

    Raises:
        RuntimeError: If any pipeline stage fails.
    """
    try:
        schedule_source = os.getenv("SCHEDULER_INPUT_SOURCE", "sql").strip().lower()

        if schedule_source == "sql":
            sync_result = sync_open_order_report_with_sql()
            print(
                "Synchronized Open Order Report from SQL "
                f"({sync_result['row_count']} rows)."
            )
            print(f"Backup: {sync_result['backup_path']}")
            print(f"Historical OOR: {sync_result['historical_oor_path']}")
            print(f"DB Snapshot: {sync_result['db_snapshot_path']}")

            input_file = read_file(source="sql")
        elif schedule_source == "excel":
            input_file = read_file(source="excel")
        else:
            raise RuntimeError(
                f"Unsupported SCHEDULER_INPUT_SOURCE '{schedule_source}'. Use 'sql' or 'excel'."
            )

        jobs_to_schedule = mold_scheduler(input_file)
        schedule_rows = build_schedule_rows(jobs_to_schedule)

        schedule_data_frame = pd.DataFrame(schedule_rows)
        schedule_data_frame = (
            schedule_data_frame
            .sort_values(
                by=[
                    Columns.COL_ALLOY,
                    Columns.COL_DUE_DATE,
                    Columns.COL_JOB_NUMBER,
                    "Extension_Seq",
                ],
                ascending=[False, False, False, True],
            )
            .reset_index(drop=True)
        )

        schedule_data_frame = assign_days(schedule_data_frame)

        print("\nDay Totals")
        print(schedule_data_frame.groupby("Schedule Day")["Molds for EXT"].sum())
        print(
            schedule_data_frame[
                [
                    Columns.COL_JOB_NUMBER,
                    "EXT",
                    Columns.COL_ALLOY,
                    "Molds for EXT",
                    "Schedule Day",
                ]
            ]
        )

        print_bucket(schedule_data_frame)

        daily_schedules = build_daily_schedules(schedule_data_frame)
        day_dates = build_schedule_dates(
            daily_schedules,
            datetime.today() + timedelta(days=1),
        )
        export_blocks = build_daily_export_blocks(daily_schedules, day_dates)
        print_export_blocks(export_blocks)

        return export_blocks
    except Exception as exc:
        raise RuntimeError("Schedule_Molds failed during orchestration") from exc

