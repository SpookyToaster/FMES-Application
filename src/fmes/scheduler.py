"""
FMES scheduling entry point.

Experimental orchestration pipeline for branch-level scheduling redesign:
    1. Read the Open Order Report from Excel.
    2. Filter jobs eligible for mold scheduling.
    3. Normalize jobs into scheduler rows.
    4. Seed export-facing data with no scheduling decisions.
    5. Keep Excel export formatting/report generation intact.

Import schedule_molds() from fmes.main or tests.
"""

from datetime import datetime, timedelta
import logging
import os

import pandas as pd

from .config import Columns
from .mold_console_schedule import build_mold_schedule_by_alloy_group
from .scheduler_build import (
    build_schedule_dates,
    build_schedule_rows,
)

from .scheduler_export import (
    build_daily_export_blocks,
    build_job_shipping_report_rows,
    print_export_blocks,
)

from .scheduler_filter import mold_scheduler
from .scheduler_io import read_file, sync_open_order_report_with_sql


logger = logging.getLogger(__name__)


def _resolve_max_jobs_per_day(default_value=10):
    """Return mold day job cap from env with a safe integer fallback."""
    raw_value = os.getenv("MOLD_SCHEDULE_MAX_JOBS_PER_DAY", str(default_value)).strip()
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError):
        return default_value
    return max(parsed, 1)


def _build_seed_melt_schedule_from_sorted_groups(sorted_rows):
    """Return a minimal melt schedule seeded directly from normalized rows."""
    if sorted_rows is None or sorted_rows.empty:
        return {}

    seed_rows = sorted_rows.copy()
    seed_rows["Pour Schedule Day"] = 1

    if "Heat #" not in seed_rows.columns:
        seed_rows["Heat #"] = 1
    if "Global Heat #" not in seed_rows.columns:
        seed_rows["Global Heat #"] = 1

    return {
        1: {
            "rows": seed_rows,
            "heat_summary": pd.DataFrame(),
        }
    }


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

        logger.info("      Normalizing jobs into scheduler rows...")
        schedule_rows = build_schedule_rows(jobs_to_schedule)
        logger.info("      %s scheduler rows created.", len(schedule_rows))

        schedule_data_frame = pd.DataFrame(schedule_rows).copy()

        max_jobs_per_day = _resolve_max_jobs_per_day()
        logger.info(
            "      Building mold day assignments (max jobs/day: %s)...",
            max_jobs_per_day,
        )
        mold_schedule_frame = build_mold_schedule_by_alloy_group(
            schedule_rows_df=schedule_data_frame,
            max_jobs_per_day=max_jobs_per_day,
        )

        if mold_schedule_frame.empty:
            logger.info("      No mold day assignments were produced.")
            melt_schedule = _build_seed_melt_schedule_from_sorted_groups(schedule_data_frame)
            mold_days = []
        else:
            if "Pour Schedule Day" not in mold_schedule_frame.columns:
                mold_schedule_frame["Pour Schedule Day"] = pd.to_numeric(
                    mold_schedule_frame.get("Schedule Day"),
                    errors="coerce",
                )
            else:
                mold_schedule_frame["Pour Schedule Day"] = pd.to_numeric(
                    mold_schedule_frame["Pour Schedule Day"],
                    errors="coerce",
                )

            mold_schedule_frame["Pour Schedule Day"] = mold_schedule_frame[
                "Pour Schedule Day"
            ].fillna(pd.to_numeric(mold_schedule_frame.get("Schedule Day"), errors="coerce"))

            if "Heat #" not in mold_schedule_frame.columns:
                mold_schedule_frame["Heat #"] = 1
            if "Global Heat #" not in mold_schedule_frame.columns:
                mold_schedule_frame["Global Heat #"] = 1

            mold_days = sorted(
                pd.to_numeric(
                    mold_schedule_frame["Schedule Day"],
                    errors="coerce",
                )
                .dropna()
                .astype(int)
                .unique()
                .tolist()
            )
            daily_schedules = {
                day: mold_schedule_frame[
                    pd.to_numeric(mold_schedule_frame["Schedule Day"], errors="coerce") == day
                ].copy()
                for day in mold_days
            }
            melt_schedule = {
                day: {
                    "rows": daily_schedules[day].copy(),
                    "heat_summary": pd.DataFrame(),
                }
                for day in mold_days
            }

        pour_days = sorted(int(day) for day in melt_schedule.keys())
        all_days = mold_days + pour_days
        if all_days:
            # One shared calendar keeps mold dates and pour dates consistent.
            calendar = build_schedule_dates(
                {day: pd.DataFrame() for day in range(1, max(all_days) + 1)},
                datetime.today() + timedelta(days=1),
            )
        else:
            calendar = {}
        mold_day_dates = {day: calendar[day] for day in mold_days}
        pour_day_dates = {day: calendar[day] for day in pour_days}

        daily_schedules = {
            day: mold_schedule_frame[
                pd.to_numeric(mold_schedule_frame["Schedule Day"], errors="coerce") == day
            ].copy()
            for day in mold_days
        }
        export_blocks = build_daily_export_blocks(
            daily_schedules,
            mold_day_dates,
            pour_day_dates=pour_day_dates,
        )
        job_shipping_rows = build_job_shipping_report_rows(
            schedule_data_frame,
            mold_schedule_frame,
            mold_day_dates,
            pour_day_dates,
        )
        print_export_blocks(export_blocks)

        logger.info("      Schedule spans %s production day(s).", len(export_blocks))
        return {
            "export_blocks": export_blocks,
            "melt_schedule": melt_schedule,
            "mold_schedule_frame": mold_schedule_frame,
            "mold_day_dates": mold_day_dates,
            "pour_day_dates": pour_day_dates,
            "job_shipping_rows": job_shipping_rows,
        }
    except Exception as exc:
        raise RuntimeError("Schedule_Molds failed during orchestration") from exc

