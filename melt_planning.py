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