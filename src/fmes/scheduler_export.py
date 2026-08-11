"""
Export logic for Foundry Management and Execution System (FMES).

Builds structured export blocks from daily schedules and writes two output
workbooks:
    Mold Schedule.xlsx  – per-day tables with job details, extension sizes, and heat numbers.
    Heat Summary.xlsx   – melt-plan summary, daily totals, planner worksheet,
                          and row-level heat-plan detail.
"""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment
from openpyxl.styles import Border, Font, Side
from openpyxl.styles import PatternFill
import pandas as pd

from .config import Columns


def _ensure_output_parent(output_file):
    """Create the destination parent directory when it does not already exist."""
    output_path = Path(output_file)
    if output_path.parent and not output_path.parent.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)


def _normalize_due_date(value):
    """Return a date object from value, an empty string for NaN, or the raw value if unparseable."""
    if pd.isna(value):
        return ""

    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return value

    return parsed.date()


def _normalize_date_value(value):
    """Return normalized pandas Timestamp date value or NaT."""
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return pd.NaT
    return pd.Timestamp(parsed).normalize()


def _target_pour_date(due_date, target_days=14):
    """Return the target pour date that satisfies the minimum lead-time goal."""
    if pd.isna(due_date):
        return pd.NaT
    return due_date - pd.Timedelta(days=target_days)


def _planner_risk_for_buffer(buffer_days):
    """Return planner-facing risk status and diagnostic text for pour buffer."""
    if buffer_days is None:
        return "UNKNOWN", "No due date available"
    if buffer_days < 14:
        return "AT RISK", "Pour is less than 14 days before due"
    if buffer_days < 21:
        return "WATCH", "Pour is within a narrow due-date buffer window"
    return "ON TRACK", "Pour meets the minimum 14-day due buffer"


def _apply_11x17_portrait_layout(ws):
    """Apply print settings optimized for 11x17 portrait output."""
    ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
    ws.page_setup.paperSize = ws.PAPERSIZE_TABLOID
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.print_options.horizontalCentered = True
    ws.page_margins.left = 0.25
    ws.page_margins.right = 0.25
    ws.page_margins.top = 0.5
    ws.page_margins.bottom = 0.5


def build_job_shipping_report_rows(
    schedule_data_frame,
    mold_schedule_frame,
    mold_day_dates,
    pour_day_dates,
    cleaning_days=14,
):
    """Build job-level shipping outlook rows from backfilled mold/pour assignments."""
    if schedule_data_frame is None or schedule_data_frame.empty:
        return []

    base = schedule_data_frame.copy()
    base[Columns.COL_DUE_DATE] = base[Columns.COL_DUE_DATE].apply(_normalize_date_value)

    planned_molds = (
        base.groupby(Columns.COL_JOB_NUMBER, dropna=False)["Molds for EXT"]
        .sum()
        .rename("Planned Molds")
    )
    due_dates = (
        base.groupby(Columns.COL_JOB_NUMBER, dropna=False)[Columns.COL_DUE_DATE]
        .min()
        .rename("Due Date")
    )

    job_summary = pd.concat([planned_molds, due_dates], axis=1).reset_index()

    if mold_schedule_frame is None or mold_schedule_frame.empty:
        job_summary["Scheduled Molds"] = 0
        job_summary["Mold Day"] = pd.NA
        job_summary["Pour Day"] = pd.NA
    else:
        assigned = mold_schedule_frame.copy()
        assigned_molds = (
            assigned.groupby(Columns.COL_JOB_NUMBER, dropna=False)["Molds for EXT"]
            .sum()
            .rename("Scheduled Molds")
        )
        mold_day = (
            assigned.groupby(Columns.COL_JOB_NUMBER, dropna=False)["Schedule Day"]
            .min()
            .rename("Mold Day")
        )
        pour_day = (
            assigned.groupby(Columns.COL_JOB_NUMBER, dropna=False)["Pour Schedule Day"]
            .max()
            .rename("Pour Day")
        )
        assigned_summary = pd.concat([assigned_molds, mold_day, pour_day], axis=1).reset_index()
        job_summary = job_summary.merge(
            assigned_summary,
            on=Columns.COL_JOB_NUMBER,
            how="left",
        )
        job_summary["Scheduled Molds"] = job_summary["Scheduled Molds"].fillna(0)

    def _resolve_day_date(day_value, day_map):
        try:
            day_key = int(day_value)
        except (TypeError, ValueError):
            return pd.NaT
        return _normalize_date_value(day_map.get(day_key, {}).get("date", pd.NaT))

    job_summary["Mold Date"] = job_summary["Mold Day"].apply(lambda value: _resolve_day_date(value, mold_day_dates))
    job_summary["Pour Date"] = job_summary["Pour Day"].apply(lambda value: _resolve_day_date(value, pour_day_dates))
    job_summary["Expected Ship Date"] = job_summary["Pour Date"].apply(
        lambda pour_date: pour_date + pd.Timedelta(days=cleaning_days) if not pd.isna(pour_date) else pd.NaT
    )

    job_summary["Ship Buffer Days"] = [
        int((due_date - expected_ship).days)
        if not pd.isna(due_date) and not pd.isna(expected_ship)
        else None
        for due_date, expected_ship in zip(job_summary["Due Date"], job_summary["Expected Ship Date"])
    ]

    def _schedule_status(row):
        planned = float(row.get("Planned Molds", 0) or 0)
        scheduled = float(row.get("Scheduled Molds", 0) or 0)
        if scheduled <= 0:
            return "Not Yet Scheduled"
        if scheduled + 1e-9 < planned:
            return "Partially Scheduled"
        return "Scheduled"

    def _on_time_status(row):
        status = row.get("Schedule Status", "")
        buffer_days = row.get("Ship Buffer Days", None)
        if status == "Not Yet Scheduled":
            return "NOT SCHEDULED"
        if buffer_days is None:
            return "UNKNOWN"
        return "YES" if buffer_days >= 0 else "NO"

    job_summary["Schedule Status"] = job_summary.apply(_schedule_status, axis=1)
    job_summary["On-Time"] = job_summary.apply(_on_time_status, axis=1)

    job_summary = job_summary.sort_values(
        by=["Schedule Status", Columns.COL_DUE_DATE, Columns.COL_JOB_NUMBER],
        ascending=[True, True, True],
        na_position="last",
    )

    rows = []
    for _, row in job_summary.iterrows():
        rows.append(
            {
                "Job Number": row.get(Columns.COL_JOB_NUMBER, ""),
                "Schedule Status": row.get("Schedule Status", ""),
                "Planned Molds": int(row.get("Planned Molds", 0) or 0),
                "Scheduled Molds": int(row.get("Scheduled Molds", 0) or 0),
                "Mold Day": int(row["Mold Day"]) if pd.notna(row.get("Mold Day", pd.NA)) else "",
                "Mold Date": _normalize_due_date(row.get("Mold Date", "")),
                "Pour Day": int(row["Pour Day"]) if pd.notna(row.get("Pour Day", pd.NA)) else "",
                "Pour Date": _normalize_due_date(row.get("Pour Date", "")),
                "Expected Ship Date": _normalize_due_date(row.get("Expected Ship Date", "")),
                "Due Date": _normalize_due_date(row.get("Due Date", "")),
                "Ship Buffer Days": row.get("Ship Buffer Days", ""),
                "On-Time": row.get("On-Time", ""),
            }
        )

    return rows


def build_daily_export_blocks(Daily_Schedules, Day_Dates, pour_day_dates=None):
    """
    Combine daily schedule DataFrames with their calendar dates into export blocks.

    Each block contains the subset of columns written to Excel plus pre-computed
    weight and mold totals used for the TOTALS row.

    Returns:
        dict mapping day number (int) -> {
            'date', 'weekday', 'rows' (DataFrame), 'weight_total', 'mold_total'
        }
    """
    try:
        export_blocks = {}

        for day, df in Daily_Schedules.items():
            df = df.copy()
            if "Heat #" not in df.columns:
                df["Heat #"] = ""

            mold_day = Day_Dates[day]

            def _resolve_pour_day_value(row):
                pour_day = row.get("Pour Schedule Day", "")
                if pd.isna(pour_day):
                    return ""
                try:
                    return int(pour_day)
                except (TypeError, ValueError):
                    return ""

            df["Pour Schedule Day"] = df.apply(_resolve_pour_day_value, axis=1)
            if pour_day_dates is None:
                df["Pour Date"] = ""
                df["Pour Weekday"] = ""
            else:
                df["Pour Date"] = df["Pour Schedule Day"].apply(
                    lambda pour_day: pour_day_dates.get(pour_day, {}).get("date", "") if pour_day != "" else ""
                )
                df["Pour Weekday"] = df["Pour Schedule Day"].apply(
                    lambda pour_day: pour_day_dates.get(pour_day, {}).get("weekday", "") if pour_day != "" else ""
                )

            df["Mold Date"] = mold_day["date"]
            df["Mold Weekday"] = mold_day["weekday"]

            due_dates = df[Columns.COL_DUE_DATE].apply(_normalize_date_value)
            pour_dates = df["Pour Date"].apply(_normalize_date_value)
            df["Pour Buffer Days"] = [
                int((due_date - pour_date).days)
                if not pd.isna(due_date) and not pd.isna(pour_date)
                else None
                for due_date, pour_date in zip(due_dates, pour_dates)
            ]

            risk_status = df["Pour Buffer Days"].apply(_planner_risk_for_buffer)
            df["Due Buffer Status"] = risk_status.apply(lambda pair: pair[0])
            df["Planner Diagnostic"] = risk_status.apply(lambda pair: pair[1])

            weight_total = df["Total Weight per EXT"].fillna(0).sum()
            mold_total = df["Molds for EXT"].fillna(0).sum()

            export_blocks[day] = {
                "date": Day_Dates[day]["date"],
                "weekday": Day_Dates[day]["weekday"],
                "rows": df[
                    [
                        Columns.COL_DUE_DATE,
                        "Customer Name",
                        "Part Number",
                        Columns.COL_JOB_NUMBER,
                        "EXT",
                        Columns.COL_ALLOY,
                        Columns.COL_CAST_TYPE,
                        "Quantity of Molds",
                        "Castings Per Mold",
                        "Quantity of Cores",
                        "Total Weight per EXT",
                        "Molds for EXT",
                        "Heat #",
                        "Pour Schedule Day",
                        "Pour Date",
                        "Pour Weekday",
                        "Pour Buffer Days",
                        "Due Buffer Status",
                        "Planner Diagnostic",
                    ]
                ].copy(),
                "weight_total": weight_total,
                "mold_total": mold_total,
            }

        return export_blocks
    except Exception as exc:
        raise RuntimeError("Failed while building export blocks") from exc


def print_export_blocks(export_blocks):
    """Print a formatted console preview of all export blocks."""
    try:
        for day in export_blocks:
            print("\n" + "=" * 50)
            print(
                f"Mold Schedule    "
                f"{export_blocks[day]['date'].strftime('%m/%d/%Y')}    "
                f"{export_blocks[day]['weekday']}"
            )
            print("=" * 50)
            print(export_blocks[day]["rows"])
            print(f"\nTOTAL WEIGHT: {export_blocks[day]['weight_total']}")
            print(f"TOTAL MOLDS: {export_blocks[day]['mold_total']}")
    except Exception as exc:
        raise RuntimeError("Failed while printing export blocks") from exc


def build_excel_rows(export_blocks):
    """
    Flatten export_blocks into a list of row lists for simple sequential writing.

    Each day contributes: a header row, a column-label row, data rows, a TOTALS
    row, and one blank spacer row.

    This is an alternate representation used for verification and lightweight
    consumers; Export_Mold_Schedule writes directly from structured blocks.

    Returns:
        list of lists – each inner list represents one Excel row.
    """
    excel_rows = []

    for day in sorted(export_blocks.keys()):
        block = export_blocks[day]
        excel_rows.append(["Mold Schedule", block["date"].strftime("%m/%d/%Y"), block["weekday"]])
        excel_rows.append([
            "Due Date",
            "Customer Name",
            "Part Number",
            "Job Number",
            "EXT",
            "Alloy",
            "Mold Type",
            "Quantity of Molds",
            "Castings Per Mold",
            "Cores Per Mold",
            "Total Weight per EXT",
            "# of Molds for EXT",
            "Heat #",
        ])

        for _, row in block["rows"].iterrows():
            excel_rows.append([
                _normalize_due_date(row.get(Columns.COL_DUE_DATE, "")),
                row.get("Customer Name", ""),
                row.get("Part Number", ""),
                row.get(Columns.COL_JOB_NUMBER, ""),
                row.get("EXT", ""),
                row.get(Columns.COL_ALLOY, ""),
                row.get(Columns.COL_CAST_TYPE, ""),
                row.get("Quantity of Molds", ""),
                row.get("Castings Per Mold", ""),
                row.get("Quantity of Cores", ""),
                row.get("Total Weight per EXT", ""),
                row.get("Molds for EXT", ""),
                row.get("Heat #", ""),
            ])

        excel_rows.append(["TOTALS", "", "", "", "", "", "", "", "", "", block["weight_total"], block["mold_total"], ""])
        excel_rows.append([])

    return excel_rows


def export_mold_schedule(Export_Blocks, output_file="Mold Schedule.xlsx", job_shipping_rows=None):
    """
    Write the mold schedule to an Excel workbook.

    Each production day occupies its own block of rows separated by two blank
    rows.  Column widths, bold headers, and thin borders are applied.

    Args:
        Export_Blocks: Output of Build_Daily_Export_Blocks.
        output_file:   Destination path for the workbook.
    """
    try:
        _ensure_output_parent(output_file)
        wb = Workbook()
        ws = wb.active
        ws.title = "Mold Schedule"
        current_row = 1

        thin = Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin"))
        bold = Font(bold=True)

        for day in sorted(Export_Blocks.keys()):
            block = Export_Blocks[day]

            ws.cell(current_row, 1, "Mold Schedule")
            ws.cell(current_row, 2, block["date"].strftime("%m/%d/%Y"))
            ws.cell(current_row, 4, block["weekday"])

            for col in range(1, 20):
                ws.cell(current_row, col).font = bold

            current_row += 2

            headers = [
                "Due Date",
                "Customer Name",
                "Part Number",
                "Job Number",
                "EXT",
                "Alloy",
                "Mold Type",
                "Quantity of Molds",
                "Castings Per Mold",
                "Cores Per Mold",
                "Total Weight per EXT",
                "# of Molds for EXT",
                "Heat #",
                "Pour Day",
                "Pour Date",
                "Pour Weekday",
                "Pour Buffer Days",
                "Due Buffer Status",
                "Planner Diagnostic",
            ]

            for col_num, header in enumerate(headers, start=1):
                cell = ws.cell(current_row, col_num, header)
                cell.font = bold
                cell.border = thin

            current_row += 1

            for _, row in block["rows"].iterrows():
                values = [
                    _normalize_due_date(row.get(Columns.COL_DUE_DATE, "")),
                    row.get("Customer Name", ""),
                    row.get("Part Number", ""),
                    row.get(Columns.COL_JOB_NUMBER, ""),
                    row.get("EXT", ""),
                    row.get(Columns.COL_ALLOY, ""),
                    row.get(Columns.COL_CAST_TYPE, ""),
                    row.get("Quantity of Molds", ""),
                    row.get("Castings Per Mold", ""),
                    row.get("Quantity of Cores", ""),
                    row.get("Total Weight per EXT", ""),
                    row.get("Molds for EXT", ""),
                    row.get("Heat #", ""),
                    row.get("Pour Schedule Day", ""),
                    _normalize_due_date(row.get("Pour Date", "")),
                    row.get("Pour Weekday", ""),
                    row.get("Pour Buffer Days", ""),
                    row.get("Due Buffer Status", ""),
                    row.get("Planner Diagnostic", ""),
                ]

                for col_num, value in enumerate(values, start=1):
                    cell = ws.cell(current_row, col_num, value)
                    cell.border = thin
                    if col_num in {1, 15} and value != "":
                        cell.number_format = "m/d/yyyy"
                    if col_num == 19:
                        cell.alignment = Alignment(wrap_text=True, vertical="top")

                current_row += 1

            ws.cell(current_row, 1, "TOTALS")
            ws.cell(current_row, 11, block["weight_total"])
            ws.cell(current_row, 12, block["mold_total"])
            ws.cell(current_row, 1).font = bold
            ws.cell(current_row, 11).font = bold
            ws.cell(current_row, 12).font = bold
            current_row += 3

        widths = {
            "A": 11,
            "B": 22,
            "C": 18,
            "D": 12,
            "E": 6,
            "F": 10,
            "G": 9,
            "H": 10,
            "I": 10,
            "J": 10,
            "K": 13,
            "L": 11,
            "M": 8,
            "N": 8,
            "O": 11,
            "P": 10,
            "Q": 8,
            "R": 12,
            "S": 34,
        }

        for col, width in widths.items():
            ws.column_dimensions[col].width = width

        _apply_11x17_portrait_layout(ws)

        if job_shipping_rows:
            ws_jobs = wb.create_sheet("Job Shipping Outlook")
            fill_green = PatternFill(fill_type="solid", start_color="C6EFCE", end_color="C6EFCE")
            fill_yellow = PatternFill(fill_type="solid", start_color="FFEB9C", end_color="FFEB9C")
            fill_orange = PatternFill(fill_type="solid", start_color="FCE4D6", end_color="FCE4D6")
            fill_red = PatternFill(fill_type="solid", start_color="FFC7CE", end_color="FFC7CE")
            fill_gray = PatternFill(fill_type="solid", start_color="E7E6E6", end_color="E7E6E6")

            headers = [
                "Job Number",
                "Schedule Status",
                "Planned Molds",
                "Scheduled Molds",
                "Mold Day",
                "Mold Date",
                "Pour Day",
                "Pour Date",
                "Expected Ship Date",
                "Due Date",
                "Ship Buffer Days",
                "On-Time",
            ]

            for col_num, header in enumerate(headers, start=1):
                cell = ws_jobs.cell(1, col_num, header)
                cell.font = bold
                cell.border = thin

            row_num = 2
            for row in job_shipping_rows:
                values = [
                    row.get("Job Number", ""),
                    row.get("Schedule Status", ""),
                    row.get("Planned Molds", ""),
                    row.get("Scheduled Molds", ""),
                    row.get("Mold Day", ""),
                    row.get("Mold Date", ""),
                    row.get("Pour Day", ""),
                    row.get("Pour Date", ""),
                    row.get("Expected Ship Date", ""),
                    row.get("Due Date", ""),
                    row.get("Ship Buffer Days", ""),
                    row.get("On-Time", ""),
                ]

                for col_num, value in enumerate(values, start=1):
                    cell = ws_jobs.cell(row_num, col_num, value)
                    cell.border = thin
                    if col_num in {6, 8, 9, 10} and value != "":
                        cell.number_format = "m/d/yyyy"

                schedule_status = str(row.get("Schedule Status", "")).strip().upper()
                on_time = str(row.get("On-Time", "")).strip().upper()
                buffer_value = row.get("Ship Buffer Days", None)

                if schedule_status == "SCHEDULED":
                    ws_jobs.cell(row_num, 2).fill = fill_green
                elif schedule_status == "PARTIALLY SCHEDULED":
                    ws_jobs.cell(row_num, 2).fill = fill_yellow
                elif schedule_status == "NOT YET SCHEDULED":
                    ws_jobs.cell(row_num, 2).fill = fill_orange

                if on_time == "YES":
                    ws_jobs.cell(row_num, 12).fill = fill_green
                elif on_time == "NO":
                    ws_jobs.cell(row_num, 12).fill = fill_red
                elif on_time == "NOT SCHEDULED":
                    ws_jobs.cell(row_num, 12).fill = fill_orange
                else:
                    ws_jobs.cell(row_num, 12).fill = fill_gray

                try:
                    if buffer_value is None or pd.isna(buffer_value):
                        ws_jobs.cell(row_num, 11).fill = fill_gray
                    else:
                        buffer_days = int(buffer_value)
                        if buffer_days < 0:
                            ws_jobs.cell(row_num, 11).fill = fill_red
                        elif buffer_days < 4:
                            ws_jobs.cell(row_num, 11).fill = fill_yellow
                        else:
                            ws_jobs.cell(row_num, 11).fill = fill_green
                except (TypeError, ValueError):
                    ws_jobs.cell(row_num, 11).fill = fill_gray

                row_num += 1

            widths = {
                "A": 12,
                "B": 18,
                "C": 12,
                "D": 13,
                "E": 9,
                "F": 11,
                "G": 9,
                "H": 11,
                "I": 14,
                "J": 11,
                "K": 14,
                "L": 10,
            }
            for col, width in widths.items():
                ws_jobs.column_dimensions[col].width = width

            _apply_11x17_portrait_layout(ws_jobs)

        wb.save(output_file)
        print(f"Saved: {output_file}")
    except Exception as exc:
        raise RuntimeError(f"Failed while exporting mold schedule to {output_file}") from exc


def build_heat_summary_rows(export_blocks, mold_schedule_frame=None):
    """
    Aggregate melt-plan summary rows into a dated export-friendly shape.

    Returns:
        list of dicts based on melt_schedule[day]['heat_summary'] plus schedule date metadata.
        When mold_schedule_frame is provided, includes planner-facing mold lead metrics.
    """
    summary_rows = []

    melt_schedule = export_blocks
    day_dates = None
    if isinstance(export_blocks, tuple):
        melt_schedule, day_dates = export_blocks

    if day_dates is None:
        raise RuntimeError("build_heat_summary_rows requires melt_schedule and day_dates")

    mold_lead_by_heat = {}
    if mold_schedule_frame is not None and not mold_schedule_frame.empty:
        lead_frame = mold_schedule_frame.copy()
        lead_frame["_MoldLeadDays"] = (
            pd.to_numeric(lead_frame.get("Pour Schedule Day"), errors="coerce")
            - pd.to_numeric(lead_frame.get("Schedule Day"), errors="coerce")
        )
        lead_frame = lead_frame[lead_frame["_MoldLeadDays"].notna()].copy()
        if not lead_frame.empty:
            grouped_lead = (
                lead_frame
                .groupby(["Pour Schedule Day", "Heat #"], dropna=False)
                .agg(
                    MaxMoldLeadDays=("_MoldLeadDays", "max"),
                    AvgMoldLeadDays=("_MoldLeadDays", "mean"),
                )
                .reset_index()
            )
            for _, lead_row in grouped_lead.iterrows():
                mold_lead_by_heat[(
                    int(lead_row["Pour Schedule Day"]),
                    lead_row["Heat #"],
                )] = {
                    "Max Mold Lead Days": int(round(float(lead_row["MaxMoldLeadDays"]))),
                    "Avg Mold Lead Days": round(float(lead_row["AvgMoldLeadDays"]), 1),
                }

    for day in sorted(melt_schedule.keys()):
        heat_summary = melt_schedule[day].get("heat_summary", pd.DataFrame()).copy()
        planned_rows = melt_schedule[day].get("rows", pd.DataFrame()).copy()
        if heat_summary.empty:
            continue

        block_date = day_dates[day]["date"]
        block_weekday = day_dates[day]["weekday"]

        heat_breakout_map = {}
        if not planned_rows.empty and "Heat #" in planned_rows.columns:
            for heat_number, heat_df in planned_rows.groupby("Heat #", sort=True):
                if pd.isna(heat_number) or heat_number == "":
                    continue

                detail_rows = []
                for _, planned_row in heat_df.iterrows():
                    job_number = str(planned_row.get(Columns.COL_JOB_NUMBER, "") or "").strip()
                    ext = str(planned_row.get("EXT", "") or "").strip()
                    due_date = _normalize_due_date(planned_row.get(Columns.COL_DUE_DATE, ""))
                    due_date_text = due_date.strftime("%m/%d/%Y") if hasattr(due_date, "strftime") else ""
                    molds_for_row = pd.to_numeric(
                        planned_row.get("Molds for EXT", 0),
                        errors="coerce",
                    )
                    molds_text = "" if pd.isna(molds_for_row) else str(int(molds_for_row))

                    job_label = f"{job_number}-{ext}" if job_number and ext else job_number
                    detail_rows.append(
                        f"{job_label} | Due {due_date_text} | Molds {molds_text}"
                    )

                heat_breakout_map[heat_number] = "; ".join(detail_rows)

        for _, row in heat_summary.iterrows():
            heat_number = row.get("Heat #", "")
            schedule_date = block_date.date() if hasattr(block_date, "date") else block_date
            earliest_due = _normalize_date_value(row.get("Earliest Due Date", ""))
            latest_due = _normalize_date_value(row.get("Latest Due Date", ""))
            schedule_ts = _normalize_date_value(schedule_date)
            due_buffer_days = None
            if not pd.isna(earliest_due) and not pd.isna(schedule_ts):
                due_buffer_days = int((earliest_due - schedule_ts).days)
            buffer_status, diagnostic = _planner_risk_for_buffer(due_buffer_days)
            lead_metrics = mold_lead_by_heat.get((int(day), heat_number), {})

            summary_rows.append(
                {
                    "Schedule Date": schedule_date,
                    "Weekday": block_weekday,
                    "Heat Slot": row.get("Heat Slot", ""),
                    "Heat #": heat_number,
                    "Heat Status": row.get("Heat Status", ""),
                    "Planning Priority": row.get("Planning Priority", ""),
                    "Review Window": row.get("Review Window", ""),
                    "Anchor Alloy": row.get("Anchor Alloy", ""),
                    "Compatibility Group": row.get("Compatibility Group", ""),
                    "Earliest Due Date": _normalize_due_date(row.get("Earliest Due Date", "")),
                    "Latest Due Date": _normalize_due_date(row.get("Latest Due Date", "")),
                    "Target Pour Date": _normalize_due_date(_target_pour_date(earliest_due)),
                    "Pour Buffer Days": due_buffer_days,
                    "Due Buffer Status": buffer_status,
                    "Total Weight (lbs)": float(row.get("Total Weight (lbs)", 0) or 0),
                    "Total Molds": float(row.get("Total Molds", 0) or 0),
                    "Rows in Heat": int(row.get("Rows in Heat", 0) or 0),
                    "Jobs": row.get("Jobs", ""),
                    "Extensions": row.get("Extensions", ""),
                    "Max Mold Lead Days": lead_metrics.get("Max Mold Lead Days", ""),
                    "Avg Mold Lead Days": lead_metrics.get("Avg Mold Lead Days", ""),
                    "Job Breakout": heat_breakout_map.get(heat_number, ""),
                    "Planner Diagnostic": diagnostic,
                }
            )

    return summary_rows


def build_heat_planner_rows(summary_rows):
    """Build planner-friendly rows including the blank reserved heat slot."""
    planner_rows = []

    for row in summary_rows:
        planner_rows.append(
            {
                "Schedule Date": row["Schedule Date"],
                "Weekday": row["Weekday"],
                "Heat Slot": row["Heat Slot"],
                "Heat Status": row["Heat Status"],
                "Heat #": row["Heat #"],
                "Planning Priority": row["Planning Priority"],
                "Review Window": row["Review Window"],
                "Anchor Alloy": row["Anchor Alloy"],
                "Compatibility Group": row["Compatibility Group"],
                "Earliest Due Date": row["Earliest Due Date"],
                "Latest Due Date": row["Latest Due Date"],
                "Target Pour Date": row["Target Pour Date"],
                "Pour Buffer Days": row["Pour Buffer Days"],
                "Due Buffer Status": row["Due Buffer Status"],
                "Total Weight (lbs)": row["Total Weight (lbs)"],
                "Total Molds": row["Total Molds"],
                "Jobs": row["Jobs"],
                "Extensions": row["Extensions"],
                "Max Mold Lead Days": row.get("Max Mold Lead Days", ""),
                "Avg Mold Lead Days": row.get("Avg Mold Lead Days", ""),
                "Planner Diagnostic": row["Planner Diagnostic"],
                "Manual Alloy": "",
                "Manual Weight (lbs)": "",
                "Manual Molds": "",
                "Planner Notes": "",
            }
        )

    return planner_rows


def build_heat_daily_totals_rows(summary_rows):
    """
    Roll up heat summary rows to one row per production day.

    Returns:
        list of dicts with keys: Schedule Date, Weekday, Total Heats,
        Total Weight (lbs), Total Molds.
    """
    if not summary_rows:
        return []

    summary_df = pd.DataFrame(summary_rows)
    summary_df = summary_df[summary_df["Heat Status"] != "Reserved"].copy()
    if summary_df.empty:
        return []

    summary_df["Heat Status"] = summary_df["Heat Status"].fillna("")
    grouped = (
        summary_df
        .groupby(["Schedule Date", "Weekday"], dropna=False, sort=True)
        .agg(
            TotalHeats=("Heat #", "nunique"),
            PlannedHeats=("Heat Status", lambda values: int((values == "Planned").sum())),
            OverflowHeats=("Heat Status", lambda values: int((values == "Overflow").sum())),
            TotalWeightLbs=("Total Weight (lbs)", "sum"),
            TotalMolds=("Total Molds", "sum"),
            AtRiskHeats=("Due Buffer Status", lambda values: int((values == "AT RISK").sum())),
        )
        .reset_index()
    )

    daily_rows = []
    for _, row in grouped.iterrows():
        daily_rows.append(
            {
                "Schedule Date": row["Schedule Date"],
                "Weekday": row["Weekday"],
                "Total Heats": int(row["TotalHeats"]),
                "Planned Heats": int(row["PlannedHeats"]),
                "Overflow Heats": int(row["OverflowHeats"]),
                "Total Weight (lbs)": float(row["TotalWeightLbs"]),
                "Total Molds": float(row["TotalMolds"]),
                "At-Risk Heats": int(row["AtRiskHeats"]),
            }
        )

    return daily_rows


def build_heat_detail_rows(melt_schedule, day_dates):
    """Flatten per-row planned heat assignments for workbook export."""
    detail_rows = []

    for day in sorted(melt_schedule.keys()):
        day_plan = melt_schedule.get(day, {})
        planned_rows = day_plan.get("rows", pd.DataFrame()).copy()
        if planned_rows.empty:
            continue

        block_date = day_dates.get(day, {}).get("date", pd.NaT)
        schedule_date = block_date.date() if hasattr(block_date, "date") else block_date
        schedule_weekday = day_dates.get(day, {}).get("weekday", "")

        for _, row in planned_rows.iterrows():
            due_ts = _normalize_date_value(row.get(Columns.COL_DUE_DATE, pd.NaT))
            schedule_ts = _normalize_date_value(schedule_date)
            due_buffer_days = None
            if not pd.isna(due_ts) and not pd.isna(schedule_ts):
                due_buffer_days = int((due_ts - schedule_ts).days)

            row_weight = float(pd.to_numeric(row.get("Total Weight per EXT", 0), errors="coerce") or 0)
            row_molds = int(pd.to_numeric(row.get("Molds for EXT", 0), errors="coerce") or 0)

            detail_rows.append(
                {
                    "Schedule Date": schedule_date,
                    "Weekday": schedule_weekday,
                    "Pour Schedule Day": row.get("Pour Schedule Day", day),
                    "Heat #": row.get("Heat #", ""),
                    "Global Heat #": row.get("Global Heat #", ""),
                    "Planning Priority": row.get("Planning Priority", ""),
                    "Review Window": row.get("Review Window", ""),
                    "Days Until Due": row.get("Days Until Due", ""),
                    "Due Date": _normalize_due_date(row.get(Columns.COL_DUE_DATE, "")),
                    "Due Buffer Days": due_buffer_days,
                    "Compatibility Group": row.get("Compatibility Group", ""),
                    "Alloy": row.get(Columns.COL_ALLOY, ""),
                    "Job Number": row.get(Columns.COL_JOB_NUMBER, ""),
                    "EXT": row.get("EXT", ""),
                    "Extension_Seq": row.get("Extension_Seq", ""),
                    "Molds for EXT": row_molds,
                    "Total Weight per EXT": row_weight,
                }
            )

    return detail_rows


def export_heat_summary(melt_schedule, day_dates, output_file="Heat Summary.xlsx", mold_schedule_frame=None):
    """
    Write the heat summary workbook.

    Sheet 1 "Heat Summary"          – day-block melt schedule layout.
    Sheet 2 "Daily Heat Totals"     – one row per day with aggregate counts.
    Sheet 3 "Due Buffer Compliance" – 14-day target compliance diagnostics.
    Sheet 4 "Heat Planner"          – planner-facing worksheet with manual fill columns.
    Sheet 5 "Detailed Plan Rows"    – row-level planned heats with due-date context.

    Args:
        melt_schedule: Output of build_melt_schedule.
        day_dates:     Output of Build_Schedule_Dates.
        output_file:   Destination path for the workbook.
    """
    try:
        _ensure_output_parent(output_file)
        wb = Workbook()
        ws = wb.active
        ws.title = "Heat Summary"

        headers = [
            "Schedule Date",
            "Weekday",
            "Heat Slot",
            "Heat #",
            "Heat Status",
            "Planning Priority",
            "Review Window",
            "Anchor Alloy",
            "Compatibility Group",
            "Earliest Due Date",
            "Latest Due Date",
            "Target Pour Date",
            "Pour Buffer Days",
            "Due Buffer Status",
            "Total Weight (lbs)",
            "Total Molds",
            "Rows in Heat",
            "Jobs",
            "Extensions",
            "Max Mold Lead Days",
            "Avg Mold Lead Days",
            "Job Breakout",
            "Planner Diagnostic",
        ]

        bold = Font(bold=True)
        thin = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )

        summary_rows = build_heat_summary_rows((melt_schedule, day_dates), mold_schedule_frame=mold_schedule_frame)
        current_row = 1

        summary_df = pd.DataFrame(summary_rows)
        if not summary_df.empty:
            grouped = summary_df.groupby(["Schedule Date", "Weekday"], sort=True)
            for (schedule_date, weekday), day_df in grouped:
                ws.cell(current_row, 1, "Melt Schedule")
                ws.cell(current_row, 2, schedule_date)
                ws.cell(current_row, 4, weekday)
                ws.cell(current_row, 2).number_format = "m/d/yyyy"
                for col in range(1, len(headers) + 1):
                    ws.cell(current_row, col).font = bold

                current_row += 2

                for col_num, header in enumerate(headers, start=1):
                    cell = ws.cell(current_row, col_num, header)
                    cell.font = bold
                    cell.border = thin

                current_row += 1

                for _, row in day_df.iterrows():
                    values = [
                        row["Schedule Date"],
                        row["Weekday"],
                        row["Heat Slot"],
                        row["Heat #"],
                        row["Heat Status"],
                        row["Planning Priority"],
                        row["Review Window"],
                        row["Anchor Alloy"],
                        row["Compatibility Group"],
                        row["Earliest Due Date"],
                        row["Latest Due Date"],
                        row["Target Pour Date"],
                        row["Pour Buffer Days"],
                        row["Due Buffer Status"],
                        row["Total Weight (lbs)"],
                        row["Total Molds"],
                        row["Rows in Heat"],
                        row["Jobs"],
                        row["Extensions"],
                        row.get("Max Mold Lead Days", ""),
                        row.get("Avg Mold Lead Days", ""),
                        row["Job Breakout"],
                        row["Planner Diagnostic"],
                    ]

                    for col_num, value in enumerate(values, start=1):
                        cell = ws.cell(current_row, col_num, value)
                        cell.border = thin
                        if col_num in {1, 10, 11, 12} and value != "":
                            cell.number_format = "m/d/yyyy"
                        if col_num == 15:
                            cell.number_format = "#,##0.00"
                        if col_num == 16:
                            cell.number_format = "#,##0"
                        if col_num in {22, 23}:
                            cell.alignment = Alignment(wrap_text=True, vertical="top")

                    current_row += 1

                ws.cell(current_row, 1, "TOTALS")
                ws.cell(current_row, 15, float(day_df["Total Weight (lbs)"].sum()))
                ws.cell(current_row, 16, float(day_df["Total Molds"].sum()))
                ws.cell(current_row, 1).font = bold
                ws.cell(current_row, 15).font = bold
                ws.cell(current_row, 16).font = bold
                current_row += 3

        widths = {
            "A": 11,
            "B": 11,
            "C": 8,
            "D": 7,
            "E": 11,
            "F": 13,
            "G": 12,
            "H": 10,
            "I": 12,
            "J": 10,
            "K": 10,
            "L": 10,
            "M": 9,
            "N": 11,
            "O": 12,
            "P": 10,
            "Q": 9,
            "R": 16,
            "S": 18,
            "T": 14,
            "U": 14,
            "V": 30,
            "W": 26,
        }

        for col, width in widths.items():
            ws.column_dimensions[col].width = width

        _apply_11x17_portrait_layout(ws)

        ws_daily = wb.create_sheet("Daily Heat Totals")
        daily_headers = [
            "Schedule Date",
            "Weekday",
            "Total Heats",
            "Planned Heats",
            "Overflow Heats",
            "At-Risk Heats",
            "Total Weight (lbs)",
            "Total Molds",
        ]

        for col_num, header in enumerate(daily_headers, start=1):
            cell = ws_daily.cell(1, col_num, header)
            cell.font = bold
            cell.border = thin

        daily_rows = build_heat_daily_totals_rows(summary_rows)
        current_row = 2

        for row in daily_rows:
            values = [
                row["Schedule Date"],
                row["Weekday"],
                row["Total Heats"],
                row["Planned Heats"],
                row["Overflow Heats"],
                row["At-Risk Heats"],
                row["Total Weight (lbs)"],
                row["Total Molds"],
            ]

            for col_num, value in enumerate(values, start=1):
                cell = ws_daily.cell(current_row, col_num, value)
                cell.border = thin
                if col_num == 1 and value != "":
                    cell.number_format = "m/d/yyyy"
                if col_num == 7:
                    cell.number_format = "#,##0.00"
                if col_num == 8:
                    cell.number_format = "#,##0"

            current_row += 1

        daily_widths = {
            "A": 14,
            "B": 12,
            "C": 12,
            "D": 12,
            "E": 13,
            "F": 13,
            "G": 18,
            "H": 12,
        }

        for col, width in daily_widths.items():
            ws_daily.column_dimensions[col].width = width

        _apply_11x17_portrait_layout(ws_daily)

        ws_compliance = wb.create_sheet("Due Buffer Compliance")
        compliance_headers = [
            "Schedule Date",
            "Weekday",
            "Heat #",
            "Anchor Alloy",
            "Earliest Due Date",
            "Target Pour Date",
            "Pour Buffer Days",
            "Due Buffer Status",
            "Planner Diagnostic",
        ]

        for col_num, header in enumerate(compliance_headers, start=1):
            cell = ws_compliance.cell(1, col_num, header)
            cell.font = bold
            cell.border = thin

        compliance_rows = [
            row for row in summary_rows
            if str(row.get("Heat Status", "")) != "Reserved"
        ]
        current_row = 2

        for row in compliance_rows:
            values = [
                row["Schedule Date"],
                row["Weekday"],
                row["Heat #"],
                row["Anchor Alloy"],
                row["Earliest Due Date"],
                row["Target Pour Date"],
                row["Pour Buffer Days"],
                row["Due Buffer Status"],
                row["Planner Diagnostic"],
            ]
            for col_num, value in enumerate(values, start=1):
                cell = ws_compliance.cell(current_row, col_num, value)
                cell.border = thin
                if col_num in {1, 5, 6} and value != "":
                    cell.number_format = "m/d/yyyy"
                if col_num == 9:
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
            current_row += 1

        compliance_widths = {
            "A": 14,
            "B": 12,
            "C": 8,
            "D": 12,
            "E": 14,
            "F": 14,
            "G": 12,
            "H": 14,
            "I": 34,
        }

        for col, width in compliance_widths.items():
            ws_compliance.column_dimensions[col].width = width

        _apply_11x17_portrait_layout(ws_compliance)

        ws_planner = wb.create_sheet("Heat Planner")
        planner_headers = [
            "Schedule Date",
            "Weekday",
            "Heat Slot",
            "Heat Status",
            "Heat #",
            "Planning Priority",
            "Review Window",
            "Anchor Alloy",
            "Compatibility Group",
            "Earliest Due Date",
            "Latest Due Date",
            "Target Pour Date",
            "Pour Buffer Days",
            "Due Buffer Status",
            "Total Weight (lbs)",
            "Total Molds",
            "Jobs",
            "Extensions",
            "Max Mold Lead Days",
            "Avg Mold Lead Days",
            "Planner Diagnostic",
            "Manual Alloy",
            "Manual Weight (lbs)",
            "Manual Molds",
            "Planner Notes",
        ]

        for col_num, header in enumerate(planner_headers, start=1):
            cell = ws_planner.cell(1, col_num, header)
            cell.font = bold
            cell.border = thin

        planner_rows = build_heat_planner_rows(summary_rows)
        current_row = 2

        for row in planner_rows:
            values = [
                row["Schedule Date"],
                row["Weekday"],
                row["Heat Slot"],
                row["Heat Status"],
                row["Heat #"],
                row["Planning Priority"],
                row["Review Window"],
                row["Anchor Alloy"],
                row["Compatibility Group"],
                row["Earliest Due Date"],
                row["Latest Due Date"],
                row["Target Pour Date"],
                row["Pour Buffer Days"],
                row["Due Buffer Status"],
                row["Total Weight (lbs)"],
                row["Total Molds"],
                row["Jobs"],
                row["Extensions"],
                row.get("Max Mold Lead Days", ""),
                row.get("Avg Mold Lead Days", ""),
                row["Planner Diagnostic"],
                row["Manual Alloy"],
                row["Manual Weight (lbs)"],
                row["Manual Molds"],
                row["Planner Notes"],
            ]

            for col_num, value in enumerate(values, start=1):
                cell = ws_planner.cell(current_row, col_num, value)
                cell.border = thin
                if col_num in {1, 10, 11, 12} and value != "":
                    cell.number_format = "m/d/yyyy"
                if col_num in {15, 21} and value != "":
                    cell.number_format = "#,##0.00"
                if col_num in {16, 22} and value != "":
                    cell.number_format = "#,##0"
                if col_num in {22, 27}:
                    cell.alignment = Alignment(wrap_text=True, vertical="top")

            current_row += 1

        planner_widths = {
            "A": 14,
            "B": 12,
            "C": 10,
            "D": 12,
            "E": 8,
            "F": 18,
            "G": 15,
            "H": 15,
            "I": 18,
            "J": 14,
            "K": 14,
            "L": 14,
            "M": 12,
            "N": 14,
            "O": 18,
            "P": 12,
            "Q": 24,
            "R": 28,
            "S": 14,
            "T": 14,
            "U": 30,
            "V": 15,
            "W": 18,
            "X": 14,
            "Y": 28,
        }

        for col, width in planner_widths.items():
            ws_planner.column_dimensions[col].width = width

        _apply_11x17_portrait_layout(ws_planner)

        ws_detail = wb.create_sheet("Detailed Plan Rows")
        detail_headers = [
            "Schedule Date",
            "Weekday",
            "Pour Schedule Day",
            "Heat #",
            "Global Heat #",
            "Planning Priority",
            "Review Window",
            "Days Until Due",
            "Due Date",
            "Due Buffer Days",
            "Compatibility Group",
            "Alloy",
            "Job Number",
            "EXT",
            "Extension_Seq",
            "Molds for EXT",
            "Total Weight per EXT",
        ]

        for col_num, header in enumerate(detail_headers, start=1):
            cell = ws_detail.cell(1, col_num, header)
            cell.font = bold
            cell.border = thin

        detail_rows = build_heat_detail_rows(melt_schedule, day_dates)
        current_row = 2

        for row in detail_rows:
            values = [
                row["Schedule Date"],
                row["Weekday"],
                row["Pour Schedule Day"],
                row["Heat #"],
                row["Global Heat #"],
                row["Planning Priority"],
                row["Review Window"],
                row["Days Until Due"],
                row["Due Date"],
                row["Due Buffer Days"],
                row["Compatibility Group"],
                row["Alloy"],
                row["Job Number"],
                row["EXT"],
                row["Extension_Seq"],
                row["Molds for EXT"],
                row["Total Weight per EXT"],
            ]

            for col_num, value in enumerate(values, start=1):
                cell = ws_detail.cell(current_row, col_num, value)
                cell.border = thin
                if col_num in {1, 9} and value != "":
                    cell.number_format = "m/d/yyyy"
                if col_num == 17 and value != "":
                    cell.number_format = "#,##0.00"
                if col_num == 16 and value != "":
                    cell.number_format = "#,##0"

            current_row += 1

        detail_widths = {
            "A": 14,
            "B": 12,
            "C": 14,
            "D": 8,
            "E": 10,
            "F": 18,
            "G": 14,
            "H": 12,
            "I": 12,
            "J": 12,
            "K": 18,
            "L": 12,
            "M": 12,
            "N": 8,
            "O": 12,
            "P": 12,
            "Q": 18,
        }

        for col, width in detail_widths.items():
            ws_detail.column_dimensions[col].width = width

        _apply_11x17_portrait_layout(ws_detail)

        wb.save(output_file)
        print(f"Saved: {output_file}")
    except Exception as exc:
        raise RuntimeError(f"Failed while exporting heat summary to {output_file}") from exc
