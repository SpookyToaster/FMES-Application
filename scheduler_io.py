"""
File I/O helpers for the mold production scheduler.

Currently handles reading the Open Order Report Excel workbook that is
exported from the ERP system and placed in the shared OneDrive folder.
"""

from datetime import datetime
from pathlib import Path
import shutil

from openpyxl import Workbook, load_workbook
import pandas as pd

from config import Columns
from DB_IO import get_main_dashboard_rows


DEFAULT_OPEN_ORDER_REPORT_PATH = (
    r"C:\Users\lburkardt\OneDrive - MonettMetalsUS1"
    r"\Quality\Schedule\Open Order Report.xlsx"
)

DEFAULT_BACKUP_DIR = (
    r"C:\Users\lburkardt\OneDrive - MonettMetalsUS1"
    r"\Quality\Schedule\Backups"
)

DEFAULT_HISTORICAL_OOR_DIR = (
    r"C:\Users\lburkardt\OneDrive - MonettMetalsUS1"
    r"\Quality\Schedule\Historical OORs"
)

DEFAULT_DB_SNAPSHOT_DIR = (
    r"C:\Users\lburkardt\OneDrive - MonettMetalsUS1"
    r"\Quality\Schedule\Historical DB Snapshots"
)

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


def _to_plain_text(value):
    """Return plain-text cell value for workbook writes without touching formatting."""
    if pd.isna(value):
        return ""

    if isinstance(value, (datetime, pd.Timestamp)):
        return value.strftime("%Y-%m-%d")

    return str(value)


def _next_incremented_path(directory, stem, suffix=".xlsx"):
    """Return first available path using an incremented numeric suffix."""
    directory = Path(directory)
    index = 1

    while True:
        candidate = directory / f"{stem}_{index:03d}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _export_worksheet_values(source_workbook_path, sheet_name, output_path):
    """Export raw worksheet values into a standalone workbook."""
    source_wb = load_workbook(source_workbook_path, data_only=True)
    try:
        if sheet_name not in source_wb.sheetnames:
            raise RuntimeError(f"Worksheet '{sheet_name}' was not found.")

        source_ws = source_wb[sheet_name]

        new_wb = Workbook()
        new_ws = new_wb.active
        new_ws.title = sheet_name

        for row in source_ws.iter_rows(
            min_row=1,
            max_row=source_ws.max_row,
            min_col=1,
            max_col=source_ws.max_column,
            values_only=True,
        ):
            new_ws.append(list(row))

        new_wb.save(output_path)
    finally:
        source_wb.close()


def _write_sql_data_to_oor(source_workbook_path, sql_rows, sheet_name="OOR"):
    """Overwrite OOR data values in range F:V from row 2 downward using plain text."""
    wb = load_workbook(source_workbook_path)
    try:
        if sheet_name not in wb.sheetnames:
            raise RuntimeError(f"Worksheet '{sheet_name}' was not found.")

        ws = wb[sheet_name]

        start_row = 2
        start_col = 6   # F
        end_col = 22    # V
        max_existing_row = ws.max_row

        # Clear old values in F2:V(last existing row) without touching styles.
        if max_existing_row >= start_row:
            for row_idx in range(start_row, max_existing_row + 1):
                for col_idx in range(start_col, end_col + 1):
                    ws.cell(row=row_idx, column=col_idx).value = None

        # Write SQL values as plain text.
        for offset, sql_row in enumerate(sql_rows):
            row_idx = start_row + offset
            for col_offset, col_name in enumerate(SQL_MAIN_EXPORT_COLUMNS):
                col_idx = start_col + col_offset
                ws.cell(row=row_idx, column=col_idx).value = _to_plain_text(sql_row.get(col_name, ""))

        wb.save(source_workbook_path)
    finally:
        wb.close()


def _save_sql_snapshot(sql_rows, output_path):
    """Save SQL rows to a standalone snapshot workbook for day-to-day diffing."""
    wb = Workbook()
    ws = wb.active
    ws.title = "SQL Snapshot"

    ws.append(SQL_MAIN_EXPORT_COLUMNS)
    for row in sql_rows:
        ws.append([_to_plain_text(row.get(col, "")) for col in SQL_MAIN_EXPORT_COLUMNS])

    wb.save(output_path)


def Sync_Open_Order_Report_With_SQL(
    source_workbook_path=DEFAULT_OPEN_ORDER_REPORT_PATH,
    backup_dir=DEFAULT_BACKUP_DIR,
    historical_oor_dir=DEFAULT_HISTORICAL_OOR_DIR,
    db_snapshot_dir=DEFAULT_DB_SNAPSHOT_DIR,
    run_id=None,
    start_due_date=None,
    end_due_date=None,
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

    timestamp = datetime.now()

    backup_path = _next_incremented_path(backup_dir, source_path.stem)
    shutil.copy2(source_path, backup_path)

    historical_oor_path = _next_incremented_path(
        historical_oor_dir,
        f"OOR-{timestamp.strftime('%Y-%m-%d')}",
    )
    _export_worksheet_values(source_path, "OOR", historical_oor_path)

    sql_rows = get_main_dashboard_rows(
        run_id=run_id,
        start_due_date=start_due_date,
        end_due_date=end_due_date,
    )
    sql_rows = _exclude_rows_by_customer_name(sql_rows)

    _write_sql_data_to_oor(source_path, sql_rows, sheet_name="OOR")

    db_snapshot_path = Path(db_snapshot_dir) / (
        f"DB-Snapshot-{timestamp.strftime('%Y-%m-%d_%H%M%S')}.xlsx"
    )
    _save_sql_snapshot(sql_rows, db_snapshot_path)

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


def Read_File(
    filepath=DEFAULT_OPEN_ORDER_REPORT_PATH,
    source="excel",
    run_id=None,
    start_due_date=None,
    end_due_date=None,
):
    """
    Read scheduler input from either Excel or SQL and return it as a DataFrame.

    Strips leading/trailing whitespace from column headers so downstream
    column lookups are not affected by inconsistent ERP exports.

    Args:
        filepath: Excel path used when source="excel".
        source:   "excel" or "sql".
        run_id:   Optional SchedulerRun.RunId used when source="sql".
        start_due_date: Optional inclusive lower bound (source="sql").
        end_due_date:   Optional inclusive upper bound (source="sql").

    Returns:
        pandas DataFrame with scheduler-compatible columns.

    Raises:
        RuntimeError: If source read fails or source is invalid.
    """
    try:
        if source == "excel":
            imported_file = pd.read_excel(filepath, sheet_name="OOR")
            imported_file.columns = imported_file.columns.str.strip()
            return imported_file

        if source == "sql":
            raw_rows = get_main_dashboard_rows(
                run_id=run_id,
                start_due_date=start_due_date,
                end_due_date=end_due_date,
            )
            raw_rows = _exclude_rows_by_customer_name(raw_rows)
            return _normalize_sql_rows(raw_rows)

        raise RuntimeError(f"Unsupported input source '{source}'. Use 'excel' or 'sql'.")
    except Exception as exc:
        if source == "excel":
            raise RuntimeError(
                f"Failed to read schedule input from {filepath} (sheet 'OOR')"
            ) from exc

        if source == "sql":
            raise RuntimeError("Failed to read schedule input from SQL main dashboard query") from exc

        raise
