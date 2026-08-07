"""Melt planning helpers for FMES heat grouping."""

import pandas as pd

from alloy_compatibility import (
    ALLOY_COMPATIBILITY_GROUP_COLUMN,
    ALLOY_COMPATIBILITY_MATCH_ALL_COLUMN,
    ALLOY_COMPATIBILITY_SPECIFIC_COLUMN,
    can_alloy_share_heat_with,
)
from config import Columns


MAX_PLANNED_HEATS_PER_DAY = 5
RESERVED_HEAT_SLOT_COUNT = 1
MAX_TOTAL_HEAT_SLOTS_PER_DAY = MAX_PLANNED_HEATS_PER_DAY + RESERVED_HEAT_SLOT_COUNT
HEAT_WEIGHT_LIMIT_LBS = 2300


def _summarize_heat_rows(day, heat_number, heat_df, max_planned_heats_per_day):
    """Build one melt-plan summary row for a grouped heat."""
    first_row = heat_df.iloc[0]
    jobs = []
    extensions = []

    for _, row in heat_df.iterrows():
        job_number = str(row.get(Columns.COL_JOB_NUMBER, "") or "").strip()
        ext = str(row.get("EXT", "") or "").strip()
        if job_number and job_number not in jobs:
            jobs.append(job_number)
        if job_number:
            extensions.append(f"{job_number}-{ext}" if ext else job_number)

    return {
        "Schedule Day": day,
        "Heat #": heat_number,
        "Heat Slot": heat_number if heat_number <= max_planned_heats_per_day else "",
        "Heat Status": "Planned" if heat_number <= max_planned_heats_per_day else "Overflow",
        "Anchor Alloy": str(first_row.get(Columns.COL_ALLOY, "") or "").strip(),
        "Compatibility Group": str(first_row.get(ALLOY_COMPATIBILITY_GROUP_COLUMN, "") or "").strip(),
        "Total Weight (lbs)": float(heat_df["Total Weight per EXT"].fillna(0).sum()),
        "Total Molds": float(heat_df["Molds for EXT"].fillna(0).sum()),
        "Jobs": ", ".join(jobs),
        "Extensions": ", ".join(extensions),
    }


def Build_Melt_Schedule(
    schedule_df,
    max_planned_heats_per_day=MAX_PLANNED_HEATS_PER_DAY,
    reserved_heat_slot_count=RESERVED_HEAT_SLOT_COUNT,
    heat_weight_limit_lbs=HEAT_WEIGHT_LIMIT_LBS,
):
    """
    Build an initial melt schedule from day-assigned open-order extensions.

    Returns a dict keyed by schedule day with both row-level heat assignments and
    a summarized melt plan that reserves the final slot for exceptions.
    """
    if schedule_df.empty:
        return {}

    melt_schedule = {}

    for day in sorted(schedule_df["Schedule Day"].dropna().unique()):
        day_df = (
            schedule_df[schedule_df["Schedule Day"] == day]
            .copy()
            .sort_values(by=[Columns.COL_ALLOY, Columns.COL_JOB_NUMBER, "Extension_Seq"])
            .reset_index(drop=True)
        )

        planned_rows = assign_heat_numbers(day_df, heat_weight_limit_lbs=heat_weight_limit_lbs)

        summary_rows = []
        if not planned_rows.empty:
            for heat_number, heat_df in planned_rows.groupby("Heat #", sort=True):
                summary_rows.append(
                    _summarize_heat_rows(
                        day,
                        int(heat_number),
                        heat_df,
                        max_planned_heats_per_day,
                    )
                )

        for slot_offset in range(reserved_heat_slot_count):
            reserved_slot = max_planned_heats_per_day + slot_offset + 1
            summary_rows.append(
                {
                    "Schedule Day": day,
                    "Heat #": "",
                    "Heat Slot": reserved_slot,
                    "Heat Status": "Reserved",
                    "Anchor Alloy": "",
                    "Compatibility Group": "",
                    "Total Weight (lbs)": 0.0,
                    "Total Molds": 0.0,
                    "Jobs": "",
                    "Extensions": "",
                }
            )

        heat_summary = pd.DataFrame(summary_rows)
        overflow_heat_count = max(
            int(planned_rows["Heat #"].max()) - max_planned_heats_per_day,
            0,
        ) if not planned_rows.empty else 0

        melt_schedule[int(day)] = {
            "rows": planned_rows,
            "heat_summary": heat_summary,
            "planned_heat_count": min(
                int(planned_rows["Heat #"].max()) if not planned_rows.empty else 0,
                max_planned_heats_per_day,
            ),
            "overflow_heat_count": overflow_heat_count,
            "reserved_heat_slots": list(
                range(
                    max_planned_heats_per_day + 1,
                    max_planned_heats_per_day + reserved_heat_slot_count + 1,
                )
            ),
        }

    return melt_schedule


def _build_compatibility_map_from_frame(day_df):
    """Build a compatibility map from schedule row metadata when available."""
    compatibility_map = {}

    for _, row in day_df.iterrows():
        alloy = str(row.get(Columns.COL_ALLOY, "") or "").strip().upper()
        if not alloy:
            continue

        compatibility_map[alloy] = {
            ALLOY_COMPATIBILITY_GROUP_COLUMN: str(
                row.get(ALLOY_COMPATIBILITY_GROUP_COLUMN, alloy) or alloy
            ).strip(),
            ALLOY_COMPATIBILITY_MATCH_ALL_COLUMN: str(
                row.get(ALLOY_COMPATIBILITY_MATCH_ALL_COLUMN, "NO") or "NO"
            ).strip().upper(),
            ALLOY_COMPATIBILITY_SPECIFIC_COLUMN: str(
                row.get(ALLOY_COMPATIBILITY_SPECIFIC_COLUMN, "") or ""
            ).strip(),
        }

    return compatibility_map


def assign_heat_numbers(day_df, heat_weight_limit_lbs=HEAT_WEIGHT_LIMIT_LBS):
    """Assign per-day heat numbers using alloy compatibility and weight limits."""
    if day_df.empty:
        day_df["Heat #"] = []
        return day_df

    compatibility_map = _build_compatibility_map_from_frame(day_df)
    heat_numbers = []
    heat_number = 0
    current_heat_weight = 0.0
    heat_anchor_alloy = None

    for _, row in day_df.iterrows():
        alloy = str(row.get(Columns.COL_ALLOY, "") or "")
        row_weight = float(row.get("Total Weight per EXT", 0) or 0)
        row_weight = max(row_weight, 0)

        needs_new_heat = False
        if heat_anchor_alloy is None:
            needs_new_heat = True
        elif not can_alloy_share_heat_with(
            heat_anchor_alloy,
            alloy,
            compatibility_map=compatibility_map,
        ):
            needs_new_heat = True
        elif current_heat_weight + row_weight > heat_weight_limit_lbs:
            needs_new_heat = True

        if needs_new_heat:
            heat_number += 1
            heat_anchor_alloy = alloy
            current_heat_weight = 0.0

        current_heat_weight += row_weight
        heat_numbers.append(heat_number)

    day_df = day_df.copy()
    day_df["Heat #"] = heat_numbers
    return day_df