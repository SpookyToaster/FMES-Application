"""Reporting pack writer for operations visibility and communication scaffolding."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import shutil

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
import pandas as pd

from .config import Paths
from .production_visibility import (
    build_attention_jobs_rows,
    build_daily_capacity_rows,
    build_job_status_summary,
)


DEFAULT_AUDIENCES = (
    "production",
    "order_entry",
    "shipping",
)

DEFAULT_EMAIL_RECIPIENTS = (
    "sliles@monettmetals.com",
    "BRaub@monettmetals.com",
    "lburkardt@monettmetals.com",
)

TITLE_FILL = PatternFill(fill_type="solid", start_color="1F4E78", end_color="1F4E78")
HEADER_FILL = PatternFill(fill_type="solid", start_color="D9E2F3", end_color="D9E2F3")
ALT_ROW_FILL = PatternFill(fill_type="solid", start_color="F8FBFF", end_color="F8FBFF")
THIN_BORDER = Border(
    left=Side(style="thin", color="D9D9D9"),
    right=Side(style="thin", color="D9D9D9"),
    top=Side(style="thin", color="D9D9D9"),
    bottom=Side(style="thin", color="D9D9D9"),
)


def _ensure_directory(path: str | Path) -> Path:
    """Create output directory and return resolved Path."""
    output_path = Path(path)
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path


def _write_rows_csv(path: Path, rows: list[dict], columns: list[str] | None = None) -> None:
    """Write rows to CSV with optional fixed column order."""
    frame = pd.DataFrame(rows)

    if columns is not None:
        for column_name in columns:
            if column_name not in frame.columns:
                frame[column_name] = ""
        frame = frame[columns]

    frame.to_csv(path, index=False)


def _auto_fit_columns(ws, min_width=10, max_width=48):
    """Auto-fit worksheet columns within a readable width range."""
    for column_index in range(1, ws.max_column + 1):
        max_len = 0
        col_letter = get_column_letter(column_index)
        for row_index in range(1, ws.max_row + 1):
            cell = ws.cell(row=row_index, column=column_index)
            value = "" if cell.value is None else str(cell.value)
            max_len = max(max_len, len(value))
        ws.column_dimensions[col_letter].width = max(min_width, min(max_len + 2, max_width))


def _coerce_excel_value(value):
    """Convert unsupported cell values into readable text for Excel output."""
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, sort_keys=True)
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return value


def _write_formatted_table_sheet(ws, title: str, frame: pd.DataFrame) -> None:
    """Write a DataFrame to a worksheet with readable planner-facing formatting."""
    column_count = max(1, len(frame.columns))
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=column_count)
    title_cell = ws.cell(1, 1, title)
    title_cell.font = Font(bold=True, color="FFFFFF", size=13)
    title_cell.fill = TITLE_FILL
    title_cell.alignment = Alignment(horizontal="center", vertical="center")

    ws.cell(2, 1, "Generated On")
    ws.cell(2, 2, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    ws.cell(2, 1).font = Font(bold=True)

    header_row = 4
    for col_idx, column_name in enumerate(frame.columns, start=1):
        header_cell = ws.cell(header_row, col_idx, str(column_name))
        header_cell.font = Font(bold=True)
        header_cell.fill = HEADER_FILL
        header_cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        header_cell.border = THIN_BORDER

    data_start_row = header_row + 1
    for row_offset, row_values in enumerate(frame.itertuples(index=False, name=None), start=0):
        target_row = data_start_row + row_offset
        apply_alt_fill = (row_offset % 2) == 1
        for col_idx, value in enumerate(row_values, start=1):
            converted_value = _coerce_excel_value(value)
            cell = ws.cell(target_row, col_idx, converted_value)
            cell.border = THIN_BORDER
            if apply_alt_fill:
                cell.fill = ALT_ROW_FILL
            if isinstance(converted_value, (int, float)):
                cell.number_format = "#,##0.00" if isinstance(converted_value, float) else "#,##0"

    ws.freeze_panes = "A5"
    if len(frame.columns) > 0:
        ws.auto_filter.ref = f"A4:{ws.cell(row=max(4, ws.max_row), column=column_count).coordinate}"
    ws.row_dimensions[1].height = 24
    ws.row_dimensions[4].height = 20
    _auto_fit_columns(ws)


def _write_reporting_pack_workbook(path: Path, run_summary: dict, job_shipping_rows: list[dict], attention_rows: list[dict], capacity_rows: list[dict]) -> None:
    """Create one formatted Excel workbook containing all report-pack tables."""
    workbook = Workbook()
    active_sheet = workbook.active
    if active_sheet is not None:
        workbook.remove(active_sheet)

    summary_rows = [{"Metric": key, "Value": value} for key, value in run_summary.items()]
    summary_frame = pd.DataFrame(summary_rows)
    job_shipping_frame = pd.DataFrame(job_shipping_rows)
    attention_frame = pd.DataFrame(attention_rows)
    capacity_frame = pd.DataFrame(capacity_rows)

    sheet_specs = [
        ("Run Summary", "Run Summary", summary_frame),
        ("Shipping Outlook", "Job Shipping Outlook", job_shipping_frame),
        ("Attention", "Jobs Requiring Attention", attention_frame),
        ("Capacity", "Daily Capacity Summary", capacity_frame),
    ]

    for sheet_name, title, frame in sheet_specs:
        if frame.empty:
            frame = pd.DataFrame([{"Info": "No rows"}])
        ws = workbook.create_sheet(sheet_name)
        _write_formatted_table_sheet(ws, title, frame)

    workbook.save(path)


def _copy_updated_open_order_workbook(output_dir: Path, source_workbook_path: str | Path) -> str | None:
    """Copy the current OOR workbook into report-pack output for email distribution."""
    source_path = Path(source_workbook_path)
    if not source_path.exists():
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = output_dir / f"Open_Order_Report_Updated_{timestamp}.xlsx"
    try:
        shutil.copy2(source_path, destination)
    except PermissionError as exc:
        raise RuntimeError(
            "Unable to copy updated Open Order Report for report-pack attachments. "
            "Close the workbook and rerun."
        ) from exc
    return str(destination)


def _build_distribution_manifest(report_paths: dict, audiences: tuple[str, ...]) -> dict:
    """Build audience-to-artifact mapping for future email automation."""
    base_attachments = [
        report_paths["report_pack_workbook"],
    ]
    if report_paths.get("open_order_workbook"):
        base_attachments.append(report_paths["open_order_workbook"])

    return {
        "audiences": [
            {
                "audience": audience,
                "enabled": True,
                "recipients": list(DEFAULT_EMAIL_RECIPIENTS),
                "attachments": list(base_attachments),
            }
            for audience in audiences
        ]
    }


def write_reporting_pack(
    schedule_result: dict,
    output_dir: str | Path,
    audiences: tuple[str, ...] = DEFAULT_AUDIENCES,
    open_order_report_path: str | Path = Paths.OPEN_ORDER_REPORT,
) -> dict:
    """Write reporting artifacts for operations and communication workflows."""
    output_path = _ensure_directory(output_dir)

    job_shipping_rows = schedule_result.get("job_shipping_rows", [])
    export_blocks = schedule_result.get("export_blocks", {})
    melt_schedule = schedule_result.get("melt_schedule", {})

    status_summary = build_job_status_summary(job_shipping_rows)
    attention_rows = build_attention_jobs_rows(job_shipping_rows)
    capacity_rows = build_daily_capacity_rows(export_blocks, melt_schedule)

    run_summary = {
        "generated_on": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "day_block_count": int(len(export_blocks)),
        "status_summary": status_summary,
        "attention_job_count": int(len(attention_rows)),
        "capacity_day_count": int(len(capacity_rows)),
    }

    summary_json_path = output_path / "run_summary.json"
    with summary_json_path.open("w", encoding="utf-8") as handle:
        json.dump(run_summary, handle, indent=2)

    job_shipping_csv_path = output_path / "job_shipping_outlook.csv"
    _write_rows_csv(job_shipping_csv_path, list(job_shipping_rows))

    attention_csv_path = output_path / "jobs_requiring_attention.csv"
    _write_rows_csv(
        attention_csv_path,
        attention_rows,
        columns=[
            "Job Number",
            "Customer Name",
            "Schedule Status",
            "Planned Molds",
            "Scheduled Molds",
            "Expected Ship Date",
            "Due Date",
            "Ship Buffer Days",
            "On-Time",
        ],
    )

    capacity_csv_path = output_path / "daily_capacity_summary.csv"
    _write_rows_csv(
        capacity_csv_path,
        capacity_rows,
        columns=[
            "Day",
            "Mold Rows",
            "Molds Scheduled",
            "Mold Weight (lbs)",
            "Melt Rows",
            "Heats Planned",
            "Melt Weight (lbs)",
        ],
    )

    report_pack_workbook_path = output_path / "report_pack.xlsx"
    _write_reporting_pack_workbook(
        report_pack_workbook_path,
        run_summary,
        list(job_shipping_rows),
        attention_rows,
        capacity_rows,
    )

    open_order_workbook_copy = _copy_updated_open_order_workbook(
        output_dir=output_path,
        source_workbook_path=open_order_report_path,
    )

    report_paths = {
        "summary_json": str(summary_json_path),
        "job_shipping_csv": str(job_shipping_csv_path),
        "attention_jobs_csv": str(attention_csv_path),
        "capacity_csv": str(capacity_csv_path),
        "report_pack_workbook": str(report_pack_workbook_path),
        "open_order_workbook": open_order_workbook_copy,
    }

    manifest = _build_distribution_manifest(report_paths, audiences)
    manifest_path = output_path / "distribution_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    return {
        "output_dir": str(output_path),
        "summary_json": str(summary_json_path),
        "job_shipping_csv": str(job_shipping_csv_path),
        "attention_jobs_csv": str(attention_csv_path),
        "capacity_csv": str(capacity_csv_path),
        "report_pack_workbook": str(report_pack_workbook_path),
        "open_order_workbook": open_order_workbook_copy,
        "distribution_manifest": str(manifest_path),
    }
