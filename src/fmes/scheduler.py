"""
FMES scheduling entry point.

Orchestrates the full scheduling pipeline:
    1. Read the Open Order Report from Excel.
    2. Filter jobs eligible for mold scheduling.
    3. Expand jobs into extension-sized work chunks.
    4. Prioritize rows for review and scheduling by due date.
    5. Build a heat-first pour plan.
    6. Back-fill the mold schedule from planned heats.
    7. Map mold days to dates, then map pour days to the next production date.
    8. Return export blocks plus the planner data needed for heat exports.

Import schedule_molds() from fmes.main or tests.
"""

from datetime import datetime, timedelta
import logging
import os

import pandas as pd

from .config import Columns
from .scheduler_build import (
    assign_mold_days_from_heat_plan,
    build_schedule_dates,
    build_schedule_rows,
    print_bucket,
)
from .melt_planning import build_melt_schedule, prioritize_schedule_rows, shift_melt_schedule_days

from .scheduler_export import (
    build_daily_export_blocks,
    print_export_blocks,
)

from .scheduler_filter import mold_scheduler
from .scheduler_io import read_file, sync_open_order_report_with_sql


logger = logging.getLogger(__name__)


def schedule_molds():
    """
    Run the complete mold scheduling pipeline and return export blocks.

    Returns:
        dict: Contains mold export blocks plus mold/pour date maps.

    Raises:
        RuntimeError: If any pipeline stage fails.
    """
    try:
        schedule_source = os.getenv("SCHEDULER_INPUT_SOURCE", "sql").strip().lower()

        if schedule_source == "sql":
            logger.info("      Syncing Open Order Report with SQL data...")
            sync_result = sync_open_order_report_with_sql()
            logger.info(
                "      Synchronized %s rows from SQL.",
                sync_result["row_count"],
            )
            logger.info("      Backup: %s", sync_result["backup_path"])
            logger.info("      Historical OOR: %s", sync_result["historical_oor_path"])
            logger.info("      DB Snapshot: %s", sync_result["db_snapshot_path"])

            logger.info("      Reading scheduler input from SQL...")
            input_file = read_file(source="sql")
        elif schedule_source == "excel":
            logger.info("      Reading scheduler input from Excel...")
            input_file = read_file(source="excel")
        else:
            raise RuntimeError(
                f"Unsupported SCHEDULER_INPUT_SOURCE '{schedule_source}'. Use 'sql' or 'excel'."
            )

        logger.info("      Loaded %s open order rows.", len(input_file))

        logger.info("      Filtering jobs eligible for molding...")
        jobs_to_schedule = mold_scheduler(input_file)
        logger.info("      %s jobs selected for scheduling.", len(jobs_to_schedule))

        logger.info("      Expanding jobs into extensions...")
        schedule_rows = build_schedule_rows(jobs_to_schedule)
        logger.info("      %s extension rows created.", len(schedule_rows))

        schedule_data_frame = pd.DataFrame(schedule_rows)
        schedule_data_frame = (
            prioritize_schedule_rows(schedule_data_frame)
        )

        logger.info("      Building heat-first pour plan...")
        melt_schedule = build_melt_schedule(schedule_data_frame)

        planned_heat_rows = pd.concat(
            [day_plan["rows"] for day_plan in melt_schedule.values()],
            ignore_index=True,
        ) if melt_schedule else pd.DataFrame()

        logger.info("      Back-filling mold schedule from planned heats...")
        mold_schedule_frame, day_offset = assign_mold_days_from_heat_plan(planned_heat_rows)
        melt_schedule = shift_melt_schedule_days(melt_schedule, day_offset)

        logger.info(
            "Day Totals\n%s",
            mold_schedule_frame.groupby("Schedule Day")["Molds for EXT"].sum(),
        )
        logger.debug(
            "Back-filled mold rows\n%s",
            mold_schedule_frame[
                [
                    Columns.COL_JOB_NUMBER,
                    "EXT",
                    Columns.COL_ALLOY,
                    "Molds for EXT",
                    "Schedule Day",
                    "Pour Schedule Day",
                ]
            ],
        )

        print_bucket(mold_schedule_frame)

        mold_day_dates = build_schedule_dates(
            {day: pd.DataFrame() for day in sorted(mold_schedule_frame["Schedule Day"].unique())},
            datetime.today() + timedelta(days=1),
        )
        pour_day_dates = build_schedule_dates(
            {day: pd.DataFrame() for day in sorted(melt_schedule.keys())},
            datetime.today() + timedelta(days=2),
        )

        daily_schedules = {
            day: mold_schedule_frame[mold_schedule_frame["Schedule Day"] == day].copy()
            for day in sorted(mold_schedule_frame["Schedule Day"].unique())
        }
        export_blocks = build_daily_export_blocks(
            daily_schedules,
            mold_day_dates,
            pour_day_dates=pour_day_dates,
        )
        print_export_blocks(export_blocks)

        logger.info("      Schedule spans %s production day(s).", len(export_blocks))
        return {
            "export_blocks": export_blocks,
            "melt_schedule": melt_schedule,
            "mold_day_dates": mold_day_dates,
            "pour_day_dates": pour_day_dates,
        }
    except Exception as exc:
        raise RuntimeError("Schedule_Molds failed during orchestration") from exc

