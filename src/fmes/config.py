"""Application-wide configuration constants for shared schedule files."""

import os
from pathlib import Path


def _resolve_schedule_root():
    """Return the shared FMES folder root for this machine."""
    env_root = os.getenv("FMES_SCHEDULE_ROOT", "").strip()
    if env_root:
        return Path(env_root)

    return Path("S:/FMES")


def _resolve_shipping_table_workbook():
    """Return source workbook path for Shipping Table sync."""
    env_path = os.getenv("FMES_SHIPPING_TABLE_WORKBOOK", "").strip()
    if env_path:
        return Path(env_path)

    return INPUT_DIR / "Shipping Table.xlsx"


SCHEDULE_ROOT = _resolve_schedule_root()
INPUT_DIR = SCHEDULE_ROOT / "Input_Files"
OUTPUT_DIR = SCHEDULE_ROOT / "Output_Files"


class Paths:
    """Shared file locations derived from the FMES input and output folders."""
    OPEN_ORDER_REPORT = INPUT_DIR / "Open Order Report.xlsx"
    SHIPPING_TABLE_WORKBOOK = _resolve_shipping_table_workbook()
    BACKUP_DIR = OUTPUT_DIR / "Backups"
    HISTORICAL_OOR_DIR = OUTPUT_DIR / "Historical OORs"
    DB_SNAPSHOT_DIR = OUTPUT_DIR / "Historical DB Snapshots"
    ALLOY_COMPATIBILITY_CSV = INPUT_DIR / "compatibleAlloys" / "alloy_compatibility.csv"
    MISSING_JOB_ID_LOG_DIR = OUTPUT_DIR
    REPORT_PACK_DIR = OUTPUT_DIR / "Report Pack"
    MOLD_SCHEDULE_OUTPUT = OUTPUT_DIR / "Mold Schedule.xlsx"
    HEAT_SUMMARY_OUTPUT = OUTPUT_DIR / "Heat Summary.xlsx"
    COMBINED_SCHEDULE_OUTPUT = OUTPUT_DIR / "Production Schedule Summary.xlsx"
    LOG_DIR = OUTPUT_DIR / "Logs"


class Columns:
    """Canonical column header names as they appear in the Open Order Report."""
    COL_HOLD = "Hold"
    COL_SCHEDULED = "Scheduled"
    COL_DUE_DATE = "Due Date"
    COL_JOB_NUMBER = "Job Number"
    COL_MOLDS_NEEDED = "Molds Needed"
    COL_POUR_WEIGHT = "Pour Weight"
    COL_JOB_TYPE = "Job Type"
    COL_ALLOY = "Alloy"
    COL_CAST_TYPE = "Casting Type"


class DailyMoldLimits:
    """Maximum molds the foundry can produce per bucket type in a single day."""
    MAX_L_MOLDS_PER_DAY = 30   # Line (L) molds
    MAX_F_MOLDS_PER_DAY = 3    # Floor (F) molds