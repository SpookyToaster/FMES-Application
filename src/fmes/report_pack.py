"""Reporting pack writer for operations visibility and communication scaffolding."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

import pandas as pd

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


def _build_distribution_manifest(report_paths: dict, audiences: tuple[str, ...]) -> dict:
    """Build audience-to-artifact mapping for future email automation."""
    return {
        "audiences": [
            {
                "audience": audience,
                "enabled": True,
                "recipients": [],
                "attachments": [
                    report_paths["summary_json"],
                    report_paths["job_shipping_csv"],
                    report_paths["attention_jobs_csv"],
                    report_paths["capacity_csv"],
                ],
            }
            for audience in audiences
        ]
    }


def write_reporting_pack(schedule_result: dict, output_dir: str | Path, audiences: tuple[str, ...] = DEFAULT_AUDIENCES) -> dict:
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

    report_paths = {
        "summary_json": str(summary_json_path),
        "job_shipping_csv": str(job_shipping_csv_path),
        "attention_jobs_csv": str(attention_csv_path),
        "capacity_csv": str(capacity_csv_path),
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
        "distribution_manifest": str(manifest_path),
    }
