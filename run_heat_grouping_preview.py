"""Preview alloy-group heat batching from current scheduler input."""

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, "src")

from fmes.config import Columns
from fmes.melt_planning import PRIORITY_REVIEW_WINDOW_DAYS, build_melt_schedule, prioritize_schedule_rows
from fmes.scheduler_build import build_schedule_rows
from fmes.scheduler_filter import mold_scheduler
from fmes.scheduler_io import read_file


def _collect_planned_rows(melt_schedule):
    if not melt_schedule:
        return pd.DataFrame()
    return pd.concat([day_plan["rows"] for day_plan in melt_schedule.values()], ignore_index=True)


def main():
    parser = argparse.ArgumentParser(description="Preview alloy-group heat batching.")
    parser.add_argument("--source", choices=["excel", "sql"], default="excel")
    parser.add_argument("--max-detail-rows", type=int, default=60)
    args = parser.parse_args()

    os.environ["SCHEDULER_INPUT_SOURCE"] = args.source

    input_df = read_file(source=args.source)
    eligible_jobs = mold_scheduler(input_df)
    schedule_rows = pd.DataFrame(build_schedule_rows(eligible_jobs))
    prioritized = prioritize_schedule_rows(schedule_rows)

    melt_input = prioritized[
        prioritized["Days Until Due"].notna()
        & (prioritized["Days Until Due"] <= PRIORITY_REVIEW_WINDOW_DAYS)
    ].copy()

    melt_schedule = build_melt_schedule(melt_input)
    planned_rows = _collect_planned_rows(melt_schedule)

    print("=== Melt Grouping Preview ===")
    print(f"Input source: {args.source}")
    print(f"Eligible jobs: {len(eligible_jobs)}")
    print(f"Extension rows before horizon: {len(prioritized)}")
    print(f"Extension rows in <= {PRIORITY_REVIEW_WINDOW_DAYS}-day horizon: {len(melt_input)}")

    if planned_rows.empty:
        print("No planned melt rows after filtering.")
        return

    print("\nAlloy Group Totals (within horizon):")
    group_totals = (
        planned_rows.groupby(["Compatibility Group", Columns.COL_ALLOY], dropna=False)
        .agg(
            rows=(Columns.COL_JOB_NUMBER, "count"),
            molds=("Molds for EXT", "sum"),
            weight_lbs=("Total Weight per EXT", "sum"),
            heats=("Global Heat #", "nunique"),
        )
        .reset_index()
        .sort_values(["Compatibility Group", "weight_lbs", "molds"], ascending=[True, False, False])
    )
    print(group_totals.to_string(index=False))

    print("\nHeat Summary by Pour Day:")
    summary_frames = []
    for day in sorted(melt_schedule.keys()):
        heat_summary = melt_schedule[day].get("heat_summary", pd.DataFrame()).copy()
        if heat_summary.empty:
            continue
        planned_only = heat_summary[heat_summary["Heat Status"] == "Planned"].copy()
        if planned_only.empty:
            continue
        summary_frames.append(planned_only)

    if summary_frames:
        summary = pd.concat(summary_frames, ignore_index=True)
        print(
            summary[
                [
                    "Schedule Day",
                    "Heat #",
                    "Anchor Alloy",
                    "Compatibility Group",
                    "Rows in Heat",
                    "Total Weight (lbs)",
                    "Total Molds",
                    "Planning Priority",
                    "Review Window",
                ]
            ].to_string(index=False)
        )

    detail_rows = min(args.max_detail_rows, len(planned_rows))
    print(f"\nDetailed Planned Rows (first {detail_rows}):")
    print(
        planned_rows[
            [
                "Pour Schedule Day",
                "Heat #",
                "Global Heat #",
                "Compatibility Group",
                Columns.COL_ALLOY,
                Columns.COL_JOB_NUMBER,
                "EXT",
                "Molds for EXT",
                "Total Weight per EXT",
                "Days Until Due",
                "Review Window",
            ]
        ]
        .head(detail_rows)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
