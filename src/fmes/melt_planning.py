"""Melt planning helpers for FMES heat grouping."""

import pandas as pd

from .alloy_compatibility import (
    ALLOY_COMPATIBILITY_GROUP_COLUMN,
    ALLOY_COMPATIBILITY_MATCH_ALL_COLUMN,
    ALLOY_COMPATIBILITY_SPECIFIC_COLUMN,
    can_alloy_share_heat_with,
)
from .config import Columns


MAX_PLANNED_HEATS_PER_DAY = 5
RESERVED_HEAT_SLOT_COUNT = 1
MAX_TOTAL_HEAT_SLOTS_PER_DAY = MAX_PLANNED_HEATS_PER_DAY + RESERVED_HEAT_SLOT_COUNT
HEAT_WEIGHT_LIMIT_LBS = 2300
HEAT_MOLD_LIMIT = 10
HIGHEST_PRIORITY_WINDOW_DAYS = 14
PRIORITY_REVIEW_WINDOW_DAYS = 70


def _normalize_due_date(value):
    """Return normalized Timestamp for a due date value, or NaT when unavailable."""
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return pd.NaT
    return pd.Timestamp(parsed).normalize()


def _normalize_reference_date(reference_date=None):
    """Return the normalized reference date used for planning priority windows."""
    if reference_date is None:
        return pd.Timestamp.today().normalize()
    return pd.Timestamp(reference_date).normalize()


def _priority_metadata_for_due_date(due_date, reference_date):
    """Classify a due date into planning priority windows."""
    if pd.isna(due_date):
        return 2, "Standard", "Outside 10 Weeks", None

    days_until_due = int((due_date - reference_date).days)
    if days_until_due <= HIGHEST_PRIORITY_WINDOW_DAYS:
        return 0, "Highest Priority", "Next 2 Weeks", days_until_due
    if days_until_due <= PRIORITY_REVIEW_WINDOW_DAYS:
        return 1, "Priority Review", "Next 10 Weeks", days_until_due
    return 2, "Standard", "Outside 10 Weeks", days_until_due


def prioritize_schedule_rows(schedule_df, reference_date=None):
    """Annotate and sort schedule rows for review and scheduling priority."""
    if schedule_df.empty:
        prioritized = schedule_df.copy()
        prioritized["Planning Priority Rank"] = []
        prioritized["Planning Priority"] = []
        prioritized["Review Window"] = []
        prioritized["Days Until Due"] = []
        prioritized["Due Date Sort"] = []
        return prioritized

    reference_date = _normalize_reference_date(reference_date)
    prioritized = schedule_df.copy()
    prioritized["Due Date Sort"] = prioritized[Columns.COL_DUE_DATE].apply(_normalize_due_date)

    priority_rows = prioritized["Due Date Sort"].apply(
        lambda due_date: _priority_metadata_for_due_date(due_date, reference_date)
    )
    prioritized["Planning Priority Rank"] = priority_rows.apply(lambda value: value[0])
    prioritized["Planning Priority"] = priority_rows.apply(lambda value: value[1])
    prioritized["Review Window"] = priority_rows.apply(lambda value: value[2])
    prioritized["Days Until Due"] = priority_rows.apply(lambda value: value[3])

    if ALLOY_COMPATIBILITY_GROUP_COLUMN not in prioritized.columns:
        prioritized[ALLOY_COMPATIBILITY_GROUP_COLUMN] = prioritized[Columns.COL_ALLOY].fillna("")

    if "Extension_Seq" not in prioritized.columns:
        prioritized["Extension_Seq"] = 0

    prioritized = prioritized.sort_values(
        by=[
            "Planning Priority Rank",
            "Due Date Sort",
            Columns.COL_JOB_NUMBER,
            "Extension_Seq",
        ],
        ascending=[True, True, True, True],
        na_position="last",
    ).reset_index(drop=True)

    return prioritized


def order_rows_for_alloy_grouping(schedule_df):
    """Order prioritized rows to maximize batching within alloy compatibility groups."""
    if schedule_df.empty:
        return schedule_df.copy()

    ordered = schedule_df.copy()

    if ALLOY_COMPATIBILITY_GROUP_COLUMN not in ordered.columns:
        ordered[ALLOY_COMPATIBILITY_GROUP_COLUMN] = ordered[Columns.COL_ALLOY].fillna("")
    if ALLOY_COMPATIBILITY_MATCH_ALL_COLUMN not in ordered.columns:
        ordered[ALLOY_COMPATIBILITY_MATCH_ALL_COLUMN] = "NO"
    if "Extension_Seq" not in ordered.columns:
        ordered["Extension_Seq"] = 0

    ordered["_Compat_All_Rank"] = (
        ordered[ALLOY_COMPATIBILITY_MATCH_ALL_COLUMN]
        .astype(str)
        .str.strip()
        .str.upper()
        .apply(lambda value: 0 if value == "YES" else 1)
    )

    ordered = ordered.sort_values(
        by=[
            "Planning Priority Rank",
            ALLOY_COMPATIBILITY_GROUP_COLUMN,
            "_Compat_All_Rank",
            Columns.COL_ALLOY,
            "Due Date Sort",
            Columns.COL_JOB_NUMBER,
            "Extension_Seq",
        ],
        ascending=[True, True, True, True, True, True, True],
        na_position="last",
    ).reset_index(drop=True)

    return ordered.drop(columns=["_Compat_All_Rank"])


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

    due_dates = heat_df.get("Due Date Sort", pd.Series(dtype="datetime64[ns]"))
    valid_due_dates = due_dates.dropna()
    earliest_due_date = valid_due_dates.min().date() if not valid_due_dates.empty else ""
    latest_due_date = valid_due_dates.max().date() if not valid_due_dates.empty else ""
    priority_rank = int(heat_df["Planning Priority Rank"].min())
    priority_row = heat_df[heat_df["Planning Priority Rank"] == priority_rank].iloc[0]

    return {
        "Schedule Day": day,
        "Heat #": heat_number,
        "Heat Slot": heat_number if heat_number <= max_planned_heats_per_day else "",
        "Heat Status": "Planned" if heat_number <= max_planned_heats_per_day else "Overflow",
        "Anchor Alloy": str(first_row.get(Columns.COL_ALLOY, "") or "").strip(),
        "Compatibility Group": str(first_row.get(ALLOY_COMPATIBILITY_GROUP_COLUMN, "") or "").strip(),
        "Planning Priority": str(priority_row.get("Planning Priority", "") or "").strip(),
        "Review Window": str(priority_row.get("Review Window", "") or "").strip(),
        "Earliest Due Date": earliest_due_date,
        "Latest Due Date": latest_due_date,
        "Total Weight (lbs)": float(heat_df["Total Weight per EXT"].fillna(0).sum()),
        "Total Molds": float(heat_df["Molds for EXT"].fillna(0).sum()),
        "Rows in Heat": int(len(heat_df)),
        "Jobs": ", ".join(jobs),
        "Extensions": ", ".join(extensions),
    }


def build_melt_schedule(
    schedule_df,
    max_planned_heats_per_day=MAX_PLANNED_HEATS_PER_DAY,
    reserved_heat_slot_count=RESERVED_HEAT_SLOT_COUNT,
    heat_weight_limit_lbs=HEAT_WEIGHT_LIMIT_LBS,
    heat_mold_limit=HEAT_MOLD_LIMIT,
    reference_date=None,
):
    """
    Build an initial heat-first melt schedule from open-order extensions.

    Returns a dict keyed by pour schedule day with both row-level heat assignments
    and a summarized melt plan that reserves the final slot for exceptions.
    """
    if schedule_df.empty:
        return {}

    reference_date = _normalize_reference_date(reference_date)
    planned_rows = prioritize_schedule_rows(schedule_df, reference_date=reference_date)
    planned_rows = order_rows_for_alloy_grouping(planned_rows)
    planned_rows = assign_heat_numbers(
        planned_rows,
        heat_weight_limit_lbs=heat_weight_limit_lbs,
        heat_mold_limit=heat_mold_limit,
    )

    if planned_rows.empty:
        return {}

    planned_rows = planned_rows.rename(columns={"Heat #": "Global Heat #"}).copy()
    heat_groups = list(planned_rows.groupby("Global Heat #", sort=True).groups.keys())
    pour_day_by_global_heat = {}
    heat_slot_by_global_heat = {}

    for group_index, global_heat_number in enumerate(heat_groups, start=1):
        pour_day_by_global_heat[global_heat_number] = ((group_index - 1) // max_planned_heats_per_day) + 1
        heat_slot_by_global_heat[global_heat_number] = ((group_index - 1) % max_planned_heats_per_day) + 1

    planned_rows["Pour Schedule Day"] = planned_rows["Global Heat #"].map(pour_day_by_global_heat)
    planned_rows["Heat #"] = planned_rows["Global Heat #"].map(heat_slot_by_global_heat)
    planned_rows["Heat Slot"] = planned_rows["Heat #"]

    melt_schedule = {}
    for day in sorted(planned_rows["Pour Schedule Day"].dropna().unique()):
        day_rows = (
            planned_rows[planned_rows["Pour Schedule Day"] == day]
            .copy()
            .reset_index(drop=True)
        )

        summary_rows = []
        for heat_number, heat_df in day_rows.groupby("Heat #", sort=True):
            summary_rows.append(
                _summarize_heat_rows(
                    int(day),
                    int(heat_number),
                    heat_df,
                    max_planned_heats_per_day,
                )
            )

        for slot_offset in range(reserved_heat_slot_count):
            reserved_slot = max_planned_heats_per_day + slot_offset + 1
            summary_rows.append(
                {
                    "Schedule Day": int(day),
                    "Heat #": "",
                    "Heat Slot": reserved_slot,
                    "Heat Status": "Reserved",
                    "Anchor Alloy": "",
                    "Compatibility Group": "",
                    "Planning Priority": "",
                    "Review Window": "",
                    "Earliest Due Date": "",
                    "Latest Due Date": "",
                    "Total Weight (lbs)": 0.0,
                    "Total Molds": 0.0,
                    "Rows in Heat": 0,
                    "Jobs": "",
                    "Extensions": "",
                }
            )

        melt_schedule[int(day)] = {
            "rows": day_rows,
            "heat_summary": pd.DataFrame(summary_rows),
            "planned_heat_count": int(day_rows["Heat #"].nunique()),
            "overflow_heat_count": 0,
            "reserved_heat_slots": list(
                range(
                    max_planned_heats_per_day + 1,
                    max_planned_heats_per_day + reserved_heat_slot_count + 1,
                )
            ),
        }

    return melt_schedule


def shift_melt_schedule_days(melt_schedule, day_offset):
    """Shift pour schedule day keys and row metadata by day_offset."""
    if not melt_schedule or day_offset == 0:
        return melt_schedule

    shifted = {}
    for day, plan in melt_schedule.items():
        new_day = int(day) + int(day_offset)
        shifted_rows = plan.get("rows", pd.DataFrame()).copy()
        if not shifted_rows.empty and "Pour Schedule Day" in shifted_rows.columns:
            shifted_rows["Pour Schedule Day"] = shifted_rows["Pour Schedule Day"] + int(day_offset)

        shifted_summary = plan.get("heat_summary", pd.DataFrame()).copy()
        if not shifted_summary.empty and "Schedule Day" in shifted_summary.columns:
            shifted_summary["Schedule Day"] = shifted_summary["Schedule Day"] + int(day_offset)

        shifted[new_day] = {
            **plan,
            "rows": shifted_rows,
            "heat_summary": shifted_summary,
        }

    return shifted


def rebuild_melt_schedule_from_planned_rows(
    allocated_rows,
    max_planned_heats_per_day=MAX_PLANNED_HEATS_PER_DAY,
    reserved_heat_slot_count=RESERVED_HEAT_SLOT_COUNT,
):
    """
    Rebuild the melt schedule after mold back-fill may have moved pour days.

    Returns:
        tuple[dict, pd.DataFrame]: melt schedule keyed by final pour day, and
        the allocated rows with heat numbers renumbered per final pour day.
    """
    if allocated_rows is None or allocated_rows.empty:
        return {}, pd.DataFrame()

    frame = allocated_rows.copy()
    if "Original Pour Schedule Day" not in frame.columns:
        frame["Original Pour Schedule Day"] = frame["Pour Schedule Day"]
    if "Planning Priority Rank" not in frame.columns:
        frame["Planning Priority Rank"] = 2
    if "Due Date Sort" not in frame.columns:
        if Columns.COL_DUE_DATE in frame.columns:
            frame["Due Date Sort"] = frame[Columns.COL_DUE_DATE].apply(_normalize_due_date)
        else:
            frame["Due Date Sort"] = pd.NaT

    heat_keys = (
        frame[["Pour Schedule Day", "Original Pour Schedule Day", "Heat #"]]
        .drop_duplicates()
        .sort_values(["Pour Schedule Day", "Original Pour Schedule Day", "Heat #"])
    )
    slot_map = {}
    slot_counters = {}
    for _, key_row in heat_keys.iterrows():
        day = int(key_row["Pour Schedule Day"])
        slot_counters[day] = slot_counters.get(day, 0) + 1
        slot_map[
            (day, key_row["Original Pour Schedule Day"], key_row["Heat #"])
        ] = slot_counters[day]

    frame["Heat #"] = frame.apply(
        lambda row: slot_map[
            (int(row["Pour Schedule Day"]), row["Original Pour Schedule Day"], row["Heat #"])
        ],
        axis=1,
    )
    frame["Heat Slot"] = frame["Heat #"]

    melt_schedule = {}
    for day in sorted(int(value) for value in frame["Pour Schedule Day"].unique()):
        day_rows = frame[frame["Pour Schedule Day"] == day].copy().reset_index(drop=True)

        summary_rows = []
        for heat_number, heat_df in day_rows.groupby("Heat #", sort=True):
            summary_rows.append(
                _summarize_heat_rows(day, int(heat_number), heat_df, max_planned_heats_per_day)
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
                    "Planning Priority": "",
                    "Review Window": "",
                    "Earliest Due Date": "",
                    "Latest Due Date": "",
                    "Total Weight (lbs)": 0.0,
                    "Total Molds": 0.0,
                    "Rows in Heat": 0,
                    "Jobs": "",
                    "Extensions": "",
                }
            )

        melt_schedule[day] = {
            "rows": day_rows,
            "heat_summary": pd.DataFrame(summary_rows),
            "planned_heat_count": int(day_rows["Heat #"].nunique()),
            "overflow_heat_count": 0,
            "reserved_heat_slots": list(
                range(
                    max_planned_heats_per_day + 1,
                    max_planned_heats_per_day + reserved_heat_slot_count + 1,
                )
            ),
        }

    return melt_schedule, frame


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


def assign_heat_numbers(
    day_df,
    heat_weight_limit_lbs=HEAT_WEIGHT_LIMIT_LBS,
    heat_mold_limit=HEAT_MOLD_LIMIT,
):
    """Assign per-day heat numbers using alloy compatibility and weight limits."""
    if day_df.empty:
        day_df["Heat #"] = []
        return day_df

    compatibility_map = _build_compatibility_map_from_frame(day_df)
    heat_numbers = []
    heat_number = 0
    current_heat_weight = 0.0
    current_heat_molds = 0
    heat_anchor_alloy = None

    for _, row in day_df.iterrows():
        alloy = str(row.get(Columns.COL_ALLOY, "") or "")
        row_weight = float(row.get("Total Weight per EXT", 0) or 0)
        row_weight = max(row_weight, 0)
        row_molds = int(pd.to_numeric(row.get("Molds for EXT", 0), errors="coerce") or 0)
        row_molds = max(row_molds, 0)

        needs_new_heat = False
        if heat_anchor_alloy is None:
            needs_new_heat = True
        elif not can_alloy_share_heat_with(
            heat_anchor_alloy,
            alloy,
            compatibility_map=compatibility_map,
        ):
            needs_new_heat = True
        elif current_heat_weight > 0 and current_heat_weight + row_weight > heat_weight_limit_lbs:
            needs_new_heat = True
        elif current_heat_molds > 0 and current_heat_molds + row_molds > heat_mold_limit:
            needs_new_heat = True

        if needs_new_heat:
            heat_number += 1
            heat_anchor_alloy = alloy
            current_heat_weight = 0.0
            current_heat_molds = 0

        current_heat_weight += row_weight
        current_heat_molds += row_molds
        heat_numbers.append(heat_number)

    day_df = day_df.copy()
    day_df["Heat #"] = heat_numbers
    return day_df