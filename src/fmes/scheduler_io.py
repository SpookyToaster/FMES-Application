"""
File I/O helpers for Foundry Management and Execution System (FMES).

Currently handles reading the Open Order Report Excel workbook that is
exported from the ERP system and placed in the shared OneDrive folder.
"""

import math
import logging
import os
from pathlib import Path
import shutil

import pandas as pd

from .alloy_compatibility import (
    DEFAULT_ALLOY_COMPATIBILITY_CSV_PATH,
    apply_alloy_compatibility,
    load_alloy_compatibility_map,
)
from .config import Columns, Paths
from .db_io import get_main_dashboard_scheduler_rows
from .scheduler_validation import validate_sql_rows
from .workbook_sync import (
    export_worksheet_values,
    save_sql_snapshot,
    sync_worksheet_values_from_workbook,
    write_sql_data_to_oor,
)


logger = logging.getLogger(__name__)


DEFAULT_OPEN_ORDER_REPORT_PATH = str(Paths.OPEN_ORDER_REPORT)

DEFAULT_BACKUP_DIR = str(Paths.BACKUP_DIR)

DEFAULT_HISTORICAL_OOR_DIR = str(Paths.HISTORICAL_OOR_DIR)

DEFAULT_DB_SNAPSHOT_DIR = str(Paths.DB_SNAPSHOT_DIR)
DEFAULT_SHIPPING_TABLE_WORKBOOK_PATH = str(Paths.SHIPPING_TABLE_WORKBOOK)
DEFAULT_SHIPPING_TABLE_SHEET_NAME = ""
DEFAULT_OOR_SHIPPING_TABLE_SHEET_NAME = "Shipped"

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
    shipping_table_workbook_path=DEFAULT_SHIPPING_TABLE_WORKBOOK_PATH,
    shipping_table_sheet_name=DEFAULT_SHIPPING_TABLE_SHEET_NAME,
    oor_shipping_table_sheet_name=DEFAULT_OOR_SHIPPING_TABLE_SHEET_NAME,
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
    try:
        export_worksheet_values(source_path, "OOR", historical_oor_path)
    except PermissionError as exc:
        raise RuntimeError(
            "Open Order Report workbook is locked by another process. "
            "Close the workbook (or disable sharing lock), then rerun. "
            "If you only need schedule/export from current workbook values, run OOR-only mode."
        ) from exc

    resolved_shipping_source_sheet = str(
        shipping_table_sheet_name or os.getenv("FMES_SHIPPING_TABLE_SOURCE_SHEET", "")
    ).strip() or None
    resolved_shipping_target_sheet = str(
        oor_shipping_table_sheet_name or os.getenv(
            "FMES_OOR_SHIPPING_TABLE_SHEET",
            DEFAULT_OOR_SHIPPING_TABLE_SHEET_NAME,
        )
    ).strip() or None

    shipping_sync = {
        "updated": False,
        "source_workbook": str(shipping_table_workbook_path),
        "source_sheet": resolved_shipping_source_sheet or "<active sheet>",
        "target_sheet": resolved_shipping_target_sheet or "",
        "row_count": 0,
        "column_count": 0,
        "reason": "skipped",
    }

    shipping_source_path = Path(shipping_table_workbook_path)
    if shipping_source_path.exists():
        try:
            shipping_result = sync_worksheet_values_from_workbook(
                target_workbook_path=source_path,
                target_sheet_name=resolved_shipping_target_sheet,
                source_workbook_path=shipping_source_path,
                source_sheet_name=resolved_shipping_source_sheet,
            )
            shipping_sync.update(
                {
                    "updated": True,
                    "row_count": int(shipping_result.get("row_count", 0)),
                    "column_count": int(shipping_result.get("column_count", 0)),
                    "source_sheet": str(
                        shipping_result.get("source_sheet", shipping_sync["source_sheet"])
                    ),
                    "target_sheet": str(
                        shipping_result.get("target_sheet", shipping_sync["target_sheet"])
                    ),
                    "reason": "updated",
                }
            )
            logger.info(
                "      Shipping Table refreshed from %s (%s rows).",
                shipping_source_path,
                shipping_sync["row_count"],
            )
        except RuntimeError as exc:
            shipping_sync["reason"] = "sheet_sync_failed"
            logger.warning("      Shipping Table refresh skipped: %s", exc)
    else:
        shipping_sync["reason"] = "source_missing"
        logger.warning(
            "      Shipping Table source workbook not found at %s; skipping refresh.",
            shipping_source_path,
        )

    sql_rows = get_main_dashboard_scheduler_rows()
    sql_rows = _exclude_rows_by_customer_name(sql_rows)
    sql_rows = validate_sql_rows(sql_rows)
    normalized_rows = _normalize_sql_rows(sql_rows).to_dict(orient="records")

    write_sql_data_to_oor(source_path, normalized_rows, SQL_MAIN_EXPORT_COLUMNS, sheet_name="OOR")

    db_snapshot_path = Path(db_snapshot_dir) / (
        f"DB-Snapshot-{timestamp.strftime('%Y-%m-%d_%H%M%S')}.xlsx"
    )
    save_sql_snapshot(normalized_rows, SQL_MAIN_EXPORT_COLUMNS, db_snapshot_path)

    return {
        "backup_path": str(backup_path),
        "historical_oor_path": str(historical_oor_path),
        "db_snapshot_path": str(db_snapshot_path),
        "row_count": len(normalized_rows),
        "shipping_table_sync": shipping_sync,
    }


def _coerce_numeric(series_like):
    """Return numeric Series with NaN converted to 0."""
    return pd.to_numeric(series_like, errors="coerce").fillna(0)


def _derive_mold_quantity_from_ordered(frame, quantity_of_molds):
    """Backfill mold quantity from ordered castings when job master molds are zero."""
    if "QTY Ordered" not in frame.columns or "Castings Per Mold" not in frame.columns:
        return quantity_of_molds, pd.Series(False, index=frame.index)

    qty_ordered = _coerce_numeric(frame["QTY Ordered"])
    castings_per_mold = _coerce_numeric(frame["Castings Per Mold"])

    fallback_values = (qty_ordered / castings_per_mold.replace(0, pd.NA)).fillna(0)
    fallback_values = fallback_values.apply(
        lambda value: int(math.ceil(float(value))) if float(value) > 0 else 0
    )

    fallback_mask = (quantity_of_molds <= 0) & (castings_per_mold > 0) & (qty_ordered > 0)
    derived_quantity = quantity_of_molds.where(~fallback_mask, fallback_values)
    return derived_quantity, fallback_mask


def _log_mold_quantity_fallback_usage(frame, fallback_mask):
    """Emit an audit log for jobs that used fallback mold derivation."""
    fallback_count = int(fallback_mask.sum())
    if fallback_count <= 0:
        logger.info("      Mold quantity fallback applied to 0 jobs.")
        return

    if Columns.COL_JOB_NUMBER in frame.columns:
        sample_jobs = (
            frame.loc[fallback_mask, Columns.COL_JOB_NUMBER]
            .astype(str)
            .str.strip()
            .replace("", pd.NA)
            .dropna()
            .head(12)
            .tolist()
        )
    else:
        sample_jobs = []

    if sample_jobs:
        logger.info(
            "      Mold quantity fallback applied to %s jobs (sample: %s).",
            fallback_count,
            ", ".join(sample_jobs),
        )
    else:
        logger.info("      Mold quantity fallback applied to %s jobs.", fallback_count)


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
    quantity_of_molds, fallback_mask = _derive_mold_quantity_from_ordered(frame, quantity_of_molds)
    molds_completed = _coerce_numeric(frame["Molds Completed"])

    _log_mold_quantity_fallback_usage(frame, fallback_mask)

    frame["Quantity of Molds"] = quantity_of_molds
    frame["Molds Completed"] = molds_completed
    frame[Columns.COL_MOLDS_NEEDED] = (quantity_of_molds - molds_completed).clip(lower=0)

    if Columns.COL_HOLD not in frame.columns:
        if "On Hold" in frame.columns:
            frame[Columns.COL_HOLD] = frame["On Hold"]
        elif "OnHold" in frame.columns:
            frame[Columns.COL_HOLD] = frame["OnHold"]

    if Columns.COL_HOLD not in frame.columns:
        frame[Columns.COL_HOLD] = "NO"
    else:
        frame[Columns.COL_HOLD] = (
            frame[Columns.COL_HOLD]
            .fillna("NO")
            .astype(str)
            .str.strip()
            .str.upper()
            .replace({"Y": "YES", "N": "NO", "TRUE": "YES", "FALSE": "NO", "1": "YES", "0": "NO"})
        )
        frame[Columns.COL_HOLD] = frame[Columns.COL_HOLD].where(
            frame[Columns.COL_HOLD].isin({"YES", "NO"}),
            "NO",
        )

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


def build_mold_input_diagnostics_rows(frame):
    """Return non-OK job diagnostics for mold quantity derivation inputs."""
    if frame is None or frame.empty:
        return []

    working = frame.copy()
    working.columns = working.columns.str.strip()

    quantity_of_molds = _coerce_numeric(
        working["Quantity of Molds"] if "Quantity of Molds" in working.columns else pd.Series(0, index=working.index)
    )
    qty_ordered = _coerce_numeric(
        working["QTY Ordered"] if "QTY Ordered" in working.columns else pd.Series(0, index=working.index)
    )
    castings_per_mold = _coerce_numeric(
        working["Castings Per Mold"] if "Castings Per Mold" in working.columns else pd.Series(0, index=working.index)
    )
    erp_molds_required = _coerce_numeric(
        working["ERP Molds Required"] if "ERP Molds Required" in working.columns else quantity_of_molds
    )

    if "Molds Calculated from Qty/Tool" in working.columns:
        molds_calculated = _coerce_numeric(working["Molds Calculated from Qty/Tool"])
    else:
        fallback_values = (qty_ordered / castings_per_mold.replace(0, pd.NA)).fillna(0)
        molds_calculated = fallback_values.apply(
            lambda value: int(math.ceil(float(value))) if float(value) > 0 else 0
        )

    mold_source = (
        working["Molds Derivation Source"]
        if "Molds Derivation Source" in working.columns
        else pd.Series("UNKNOWN", index=working.index)
    )
    mold_source = mold_source.fillna("UNKNOWN").astype(str).str.strip().str.upper()

    bom_tool_rows = _coerce_numeric(
        working["BOM Tool Rows"] if "BOM Tool Rows" in working.columns else pd.Series(0, index=working.index)
    )
    bom_distinct_tools = _coerce_numeric(
        working["BOM Distinct Tool Impressions"] if "BOM Distinct Tool Impressions" in working.columns else pd.Series(0, index=working.index)
    )
    bom_castings_per_mold = _coerce_numeric(
        working["BOM Castings Per Mold"] if "BOM Castings Per Mold" in working.columns else pd.Series(0, index=working.index)
    )

    diagnostic_flag = pd.Series("OK", index=working.index, dtype="object")
    diagnostic_flag.loc[mold_source == "BOM_CONFLICT"] = "BOM_CONFLICT_NO_FALLBACK"
    diagnostic_flag.loc[(diagnostic_flag == "OK") & (mold_source == "MISSING")] = "NO_EFFECTIVE_TOOL_IMPRESSIONS"
    diagnostic_flag.loc[(diagnostic_flag == "OK") & (mold_source == "BOM_CONSISTENT")] = "USED_BOM_FALLBACK"

    mismatch_mask = (
        (diagnostic_flag == "OK")
        & (molds_calculated > 0)
        & ((erp_molds_required - molds_calculated).abs() > 0.0001)
    )
    diagnostic_flag.loc[mismatch_mask] = "ERP_MOLDS_MISMATCH"

    delta_vs_erp = molds_calculated - erp_molds_required

    diagnostics = pd.DataFrame(
        {
            "Job Number": working.get(Columns.COL_JOB_NUMBER, pd.Series("", index=working.index)),
            "Customer Name": working.get("Customer Name", pd.Series("", index=working.index)),
            "Part Number": working.get("Part Number", pd.Series("", index=working.index)),
            "QTY Ordered": qty_ordered,
            "Castings Per Mold (Effective)": castings_per_mold,
            "Tool Impressions Source": mold_source,
            "BOM Castings Per Mold": bom_castings_per_mold,
            "BOM Tool Rows": bom_tool_rows,
            "BOM Distinct Tool Impressions": bom_distinct_tools,
            "ERP Molds Required": erp_molds_required,
            "Program Quantity of Molds": quantity_of_molds,
            "Molds Calculated from Qty/Tool": molds_calculated,
            "Delta (Calculated - ERP)": delta_vs_erp,
            "Molds Completed": _coerce_numeric(working.get("Molds Completed", pd.Series(0, index=working.index))),
            "Molds Needed": _coerce_numeric(working.get(Columns.COL_MOLDS_NEEDED, pd.Series(0, index=working.index))),
            "Diagnostic Flag": diagnostic_flag,
        }
    )

    diagnostics = diagnostics[diagnostics["Diagnostic Flag"] != "OK"].copy()
    if diagnostics.empty:
        return []

    severity_rank = {
        "BOM_CONFLICT_NO_FALLBACK": 0,
        "NO_EFFECTIVE_TOOL_IMPRESSIONS": 1,
        "USED_BOM_FALLBACK": 2,
        "ERP_MOLDS_MISMATCH": 3,
    }
    diagnostics["_sort_rank"] = diagnostics["Diagnostic Flag"].map(severity_rank).fillna(9)
    diagnostics = diagnostics.sort_values(by=["_sort_rank", "Job Number"], kind="stable")
    diagnostics = diagnostics.drop(columns=["_sort_rank"])
    return diagnostics.to_dict(orient="records")


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
