"""
File I/O helpers for Foundry Management and Execution System (FMES).

Currently handles reading the Open Order Report Excel workbook that is
exported from the ERP system and placed in the shared OneDrive folder.
"""

from pathlib import Path
import shutil

import pandas as pd

from alloy_compatibility import (
    DEFAULT_ALLOY_COMPATIBILITY_CSV_PATH,
    apply_alloy_compatibility,
    load_alloy_compatibility_map,
)
from config import Columns, Paths
from DB_IO import get_main_dashboard_scheduler_rows
from scheduler_validation import validate_sql_rows
from workbook_sync import (
    export_worksheet_values,
    save_sql_snapshot,
    write_sql_data_to_oor,
)


DEFAULT_OPEN_ORDER_REPORT_PATH = str(Paths.OPEN_ORDER_REPORT)

DEFAULT_BACKUP_DIR = str(Paths.BACKUP_DIR)

DEFAULT_HISTORICAL_OOR_DIR = str(Paths.HISTORICAL_OOR_DIR)

DEFAULT_DB_SNAPSHOT_DIR = str(Paths.DB_SNAPSHOT_DIR)

SQL_MAIN_EXPORT_COLUMNS = [
    "Due Date",
    "Customer Name",
    "Part Number",
    "Job Type",
    "Job Number",
    "Alloy",
    "Casting Type",
    "QTY Ordered",
    "Quantity of Molds",
    "Castings Per Mold",
    "Quantity of Cores",
    "Pour Weight",
    "Total Pour WT",
    "Total Value",
    "Heat No Assigned",
    "Castings Produced",
    "Molds Completed",
]

EXCLUDED_CUSTOMER_NAMES = {"MONETT"}
def _ensure_directory(path):
    """Create path (and parents) when missing."""
    Path(path).mkdir(parents=True, exist_ok=True)


def _exclude_rows_by_customer_name(rows, excluded_names=EXCLUDED_CUSTOMER_NAMES):
    """Return rows excluding records whose Customer Name matches excluded_names."""
    normalized_exclusions = {str(name).strip().upper() for name in excluded_names}

    filtered = []
    for row in rows:
        customer_name = str(row.get("Customer Name", "")).strip().upper()
        if customer_name in normalized_exclusions:
            continue
        filtered.append(row)

    return filtered


def _next_incremented_path(directory, stem, suffix=".xlsx"):
    """Return first available path using an incremented numeric suffix."""
    directory = Path(directory)
    index = 1

    while True:
        candidate = directory / f"{stem}_{index:03d}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def sync_open_order_report_with_sql(
    source_workbook_path=DEFAULT_OPEN_ORDER_REPORT_PATH,
    backup_dir=DEFAULT_BACKUP_DIR,
    historical_oor_dir=DEFAULT_HISTORICAL_OOR_DIR,
    db_snapshot_dir=DEFAULT_DB_SNAPSHOT_DIR,
):
    """
    Sync Open Order Report workbook artifacts with current SQL main-dashboard data.

    Steps:
      1) Backup source workbook to incremented file in backup_dir.
      2) Export current OOR worksheet values to historical OOR workbook.
      3) Overwrite OOR values in F2:V* using SQL rows as plain text.
      4) Save SQL rows to a dated snapshot workbook.

    Returns:
        dict with file paths and row_count written.
    """
    source_path = Path(source_workbook_path)
    if not source_path.exists():
        raise RuntimeError(f"Open Order Report workbook was not found at {source_workbook_path}")

    _ensure_directory(backup_dir)
    _ensure_directory(historical_oor_dir)
    _ensure_directory(db_snapshot_dir)

    timestamp = pd.Timestamp.now().to_pydatetime()

    backup_path = _next_incremented_path(backup_dir, source_path.stem)
    shutil.copy2(source_path, backup_path)

    historical_oor_path = _next_incremented_path(
        historical_oor_dir,
        f"OOR-{timestamp.strftime('%Y-%m-%d')}",
    )
    export_worksheet_values(source_path, "OOR", historical_oor_path)

    sql_rows = get_main_dashboard_scheduler_rows()
    sql_rows = _exclude_rows_by_customer_name(sql_rows)
    sql_rows = validate_sql_rows(sql_rows)

    write_sql_data_to_oor(source_path, sql_rows, SQL_MAIN_EXPORT_COLUMNS, sheet_name="OOR")

    db_snapshot_path = Path(db_snapshot_dir) / (
        f"DB-Snapshot-{timestamp.strftime('%Y-%m-%d_%H%M%S')}.xlsx"
    )
    save_sql_snapshot(sql_rows, SQL_MAIN_EXPORT_COLUMNS, db_snapshot_path)

    return {
        "backup_path": str(backup_path),
        "historical_oor_path": str(historical_oor_path),
        "db_snapshot_path": str(db_snapshot_path),
        "row_count": len(sql_rows),
    }


def _coerce_numeric(series_like):
    """Return numeric Series with NaN converted to 0."""
    return pd.to_numeric(series_like, errors="coerce").fillna(0)


def _normalize_sql_rows(raw_rows):
    """
    Normalize SQL dashboard rows into the schema expected by the scheduler.

    The SQL source provides total molds and completed molds.  The scheduler
    expects "Molds Needed" as remaining molds, so we derive it as:
        max(Quantity of Molds - Molds Completed, 0)
    """
    frame = pd.DataFrame(raw_rows)

    if frame.empty:
        return frame

    frame.columns = frame.columns.str.strip()

    if "Molds Completed" not in frame.columns:
        frame["Molds Completed"] = 0

    if "Quantity of Molds" not in frame.columns:
        frame["Quantity of Molds"] = 0

    quantity_of_molds = _coerce_numeric(frame["Quantity of Molds"])
    molds_completed = _coerce_numeric(frame["Molds Completed"])

    frame["Quantity of Molds"] = quantity_of_molds
    frame["Molds Completed"] = molds_completed
    frame[Columns.COL_MOLDS_NEEDED] = (quantity_of_molds - molds_completed).clip(lower=0)

    if Columns.COL_HOLD not in frame.columns:
        frame[Columns.COL_HOLD] = "NO"
    else:
        frame[Columns.COL_HOLD] = frame[Columns.COL_HOLD].fillna("NO")

    if Columns.COL_SCHEDULED not in frame.columns:
        frame[Columns.COL_SCHEDULED] = "NO"
    else:
        frame[Columns.COL_SCHEDULED] = frame[Columns.COL_SCHEDULED].fillna("NO")

    for required_col in [
        Columns.COL_DUE_DATE,
        Columns.COL_JOB_NUMBER,
        Columns.COL_POUR_WEIGHT,
        Columns.COL_JOB_TYPE,
        Columns.COL_ALLOY,
        Columns.COL_CAST_TYPE,
        "Customer Name",
        "Part Number",
        "Castings Per Mold",
        "Quantity of Cores",
    ]:
        if required_col not in frame.columns:
            frame[required_col] = ""

    return frame


def read_file(
    filepath=DEFAULT_OPEN_ORDER_REPORT_PATH,
    source="excel",
    alloy_compatibility_csv_path=DEFAULT_ALLOY_COMPATIBILITY_CSV_PATH,
):
    """
    Read scheduler input from either Excel or SQL and return it as a DataFrame.

    Strips leading/trailing whitespace from column headers so downstream
    column lookups are not affected by inconsistent ERP exports.

    Args:
        filepath: Excel path used when source="excel".
        source:   "excel" or "sql".

    Returns:
        pandas DataFrame with scheduler-compatible columns.

    Raises:
        RuntimeError: If source read fails or source is invalid.
    """
    try:
        compatibility_map = load_alloy_compatibility_map(alloy_compatibility_csv_path)

        if source == "excel":
            imported_file = pd.read_excel(filepath, sheet_name="OOR")
            imported_file.columns = imported_file.columns.str.strip()
            return apply_alloy_compatibility(imported_file, compatibility_map)

        if source == "sql":
            raw_rows = get_main_dashboard_scheduler_rows()
            raw_rows = _exclude_rows_by_customer_name(raw_rows)
            raw_rows = validate_sql_rows(raw_rows)
            normalized = _normalize_sql_rows(raw_rows)
            return apply_alloy_compatibility(normalized, compatibility_map)

        raise RuntimeError(f"Unsupported input source '{source}'. Use 'excel' or 'sql'.")
    except Exception as exc:
        if source == "excel":
            raise RuntimeError(
                f"Failed to read schedule input from {filepath} (sheet 'OOR')"
            ) from exc

        if source == "sql":
            raise RuntimeError(
                f"Failed to read schedule input from SQL main dashboard query: {exc}"
            ) from exc

        raise
