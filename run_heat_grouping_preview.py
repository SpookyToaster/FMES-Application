"""Preview prioritized alloy-group rows for the experimental scheduler branch."""

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, "src")

from fmes.config import Columns
from fmes.melt_planning import HIGHEST_PRIORITY_WINDOW_DAYS, PRIORITY_REVIEW_WINDOW_DAYS, prioritize_schedule_rows
from fmes.scheduler_build import build_schedule_rows
from fmes.scheduler_filter import mold_scheduler
from fmes.scheduler_io import read_file


def main():
    parser = argparse.ArgumentParser(description="Preview prioritized alloy-group rows.")
    parser.add_argument("--source", choices=["excel", "sql"], default="excel")
    parser.add_argument("--max-detail-rows", type=int, default=80)
    args = parser.parse_args()

    os.environ["SCHEDULER_INPUT_SOURCE"] = args.source

    input_df = read_file(source=args.source)
    eligible_jobs = mold_scheduler(input_df)
    schedule_rows = pd.DataFrame(build_schedule_rows(eligible_jobs))
    prioritized = prioritize_schedule_rows(schedule_rows)

    within_horizon = prioritized[
        prioritized["Days Until Due"].notna()
        & (prioritized["Days Until Due"] <= PRIORITY_REVIEW_WINDOW_DAYS)
    ].copy()

    print("=== Scheduler Priority Preview ===")
    print(f"Input source: {args.source}")
    print(f"Eligible jobs: {len(eligible_jobs)}")
    print(f"Scheduler rows before horizon: {len(prioritized)}")
    print(f"Rows in <= {PRIORITY_REVIEW_WINDOW_DAYS}-day horizon: {len(within_horizon)}")

    if within_horizon.empty:
        print("No rows in planning horizon.")
        return

    summary = (
        within_horizon.groupby(["Compatibility Group", Columns.COL_ALLOY, "Planning Priority"], dropna=False)
        .agg(
            rows=(Columns.COL_JOB_NUMBER, "count"),
            molds=("Molds for EXT", "sum"),
            weight_lbs=("Total Weight per EXT", "sum"),
            min_days_until_due=("Days Until Due", "min"),
        )
        .reset_index()
        .sort_values(["Planning Priority", "Compatibility Group", "weight_lbs"], ascending=[True, True, False])
    )

    print("\nAlloy Group Priority Summary:")
    print(summary.to_string(index=False))

    urgent_count = int((pd.to_numeric(within_horizon["Days Until Due"], errors="coerce") <= HIGHEST_PRIORITY_WINDOW_DAYS).sum())
    print(f"\nUrgent rows (<= {HIGHEST_PRIORITY_WINDOW_DAYS} days): {urgent_count}")

    detail_rows = min(args.max_detail_rows, len(within_horizon))
    print(f"\nDetailed Prioritized Rows (first {detail_rows}):")
    print(
        within_horizon[
            [
                "Planning Priority",
                "Review Window",
                "Days Until Due",
                "Compatibility Group",
                Columns.COL_ALLOY,
                Columns.COL_JOB_NUMBER,
                "Molds for EXT",
                "Total Weight per EXT",
                "EXT",
            ]
        ]
        .head(detail_rows)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
