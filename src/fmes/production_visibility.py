"""Production visibility summaries derived from scheduler outputs."""

from __future__ import annotations

from typing import Iterable

import pandas as pd


def _rows_to_frame(rows: Iterable[dict] | None) -> pd.DataFrame:
    """Return a DataFrame for row dictionaries or an empty frame."""
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(list(rows)).copy()


def build_job_status_summary(job_shipping_rows: Iterable[dict] | None) -> dict:
    """Return high-level schedule and on-time status counts."""
    frame = _rows_to_frame(job_shipping_rows)
    if frame.empty:
        return {
            "Total Jobs": 0,
            "Scheduled Jobs": 0,
            "Partially Scheduled Jobs": 0,
            "Not Yet Scheduled Jobs": 0,
            "On-Time Yes": 0,
            "On-Time No": 0,
            "On-Time Not Scheduled": 0,
            "On-Time Unknown": 0,
        }

    schedule_status = frame.get("Schedule Status", pd.Series("", index=frame.index)).fillna("").astype(str).str.strip().str.upper()
    on_time_status = frame.get("On-Time", pd.Series("", index=frame.index)).fillna("").astype(str).str.strip().str.upper()

    return {
        "Total Jobs": int(len(frame)),
        "Scheduled Jobs": int((schedule_status == "SCHEDULED").sum()),
        "Partially Scheduled Jobs": int((schedule_status == "PARTIALLY SCHEDULED").sum()),
        "Not Yet Scheduled Jobs": int((schedule_status == "NOT YET SCHEDULED").sum()),
        "On-Time Yes": int((on_time_status == "YES").sum()),
        "On-Time No": int((on_time_status == "NO").sum()),
        "On-Time Not Scheduled": int((on_time_status == "NOT SCHEDULED").sum()),
        "On-Time Unknown": int((on_time_status == "UNKNOWN").sum()),
    }


def build_attention_jobs_rows(job_shipping_rows: Iterable[dict] | None, buffer_warning_days: int = 4) -> list[dict]:
    """Return jobs that need planner attention soonest."""
    frame = _rows_to_frame(job_shipping_rows)
    if frame.empty:
        return []

    schedule_status = frame.get("Schedule Status", pd.Series("", index=frame.index)).fillna("").astype(str).str.strip().str.upper()
    on_time_status = frame.get("On-Time", pd.Series("", index=frame.index)).fillna("").astype(str).str.strip().str.upper()
    ship_buffer = pd.to_numeric(frame.get("Ship Buffer Days", pd.Series(dtype="float64")), errors="coerce")

    attention_mask = (
        (schedule_status != "SCHEDULED")
        | (on_time_status == "NO")
        | (ship_buffer.notna() & (ship_buffer < buffer_warning_days))
    )

    if not attention_mask.any():
        return []

    selected_columns = [
        "Job Number",
        "Customer Name",
        "Schedule Status",
        "Planned Molds",
        "Scheduled Molds",
        "Expected Ship Date",
        "Due Date",
        "Ship Buffer Days",
        "On-Time",
    ]

    for column_name in selected_columns:
        if column_name not in frame.columns:
            frame[column_name] = ""

    attention_frame = frame.loc[attention_mask, selected_columns].copy()
    attention_frame["__BufferSort"] = pd.to_numeric(attention_frame["Ship Buffer Days"], errors="coerce").fillna(999999)

    attention_frame = attention_frame.sort_values(
        by=["Schedule Status", "__BufferSort", "Job Number"],
        ascending=[True, True, True],
        na_position="last",
    ).drop(columns=["__BufferSort"])

    return attention_frame.to_dict(orient="records")


def build_daily_capacity_rows(export_blocks: dict, melt_schedule: dict) -> list[dict]:
    """Return one capacity row per day across mold and melt views."""
    all_days = sorted(set(export_blocks.keys()) | set(melt_schedule.keys()))
    rows = []

    for day in all_days:
        mold_block = export_blocks.get(day, {})
        melt_block = melt_schedule.get(day, {})

        mold_rows = mold_block.get("rows", pd.DataFrame())
        melt_rows = melt_block.get("rows", pd.DataFrame())

        mold_total = int(round(float(mold_block.get("mold_total", 0) or 0)))
        mold_weight = float(mold_block.get("weight_total", 0) or 0)

        melt_weight = float(pd.to_numeric(melt_rows.get("Total Weight per EXT", pd.Series(dtype="float64")), errors="coerce").fillna(0).sum()) if not melt_rows.empty else 0.0

        if melt_rows.empty or "Heat #" not in melt_rows.columns:
            heat_count = 0
        else:
            heat_values = melt_rows["Heat #"]
            heat_count = int(
                pd.Series(heat_values)
                .dropna()
                .astype(str)
                .str.strip()
                .replace("", pd.NA)
                .dropna()
                .nunique()
            )

        rows.append(
            {
                "Day": int(day),
                "Mold Rows": int(len(mold_rows)) if hasattr(mold_rows, "__len__") else 0,
                "Molds Scheduled": mold_total,
                "Mold Weight (lbs)": round(mold_weight, 2),
                "Melt Rows": int(len(melt_rows)) if hasattr(melt_rows, "__len__") else 0,
                "Heats Planned": heat_count,
                "Melt Weight (lbs)": round(melt_weight, 2),
            }
        )

    return rows
