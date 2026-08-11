"""Runtime melt planning metadata for the experimental scheduler branch.

Legacy heat-assignment and backfill orchestration has been removed from this
module. The active runtime only needs due-date priority annotation/sorting and
shared planning constants used by reporting.
"""

import pandas as pd

from .config import Columns


# Shared planning targets retained for export/report context.
HIGHEST_PRIORITY_WINDOW_DAYS = 14
PRIORITY_REVIEW_WINDOW_DAYS = 70
DAILY_WEIGHT_TARGET_LBS = 10000
MAX_PLANNED_HEATS_PER_DAY = 5
HEAT_WEIGHT_LIMIT_LBS = 2300
HEAT_MOLD_LIMIT = 10

# Compatibility metadata column names remain stable for downstream exports.
ALLOY_COMPATIBILITY_GROUP_COLUMN = "Compatibility Group"
ALLOY_COMPATIBILITY_MATCH_ALL_COLUMN = "Compatibility Match All"


def _normalize_reference_date(reference_date=None):
    """Normalize reference date to midnight pandas Timestamp."""
    if reference_date is None:
        return pd.Timestamp.today().normalize()

    parsed = pd.to_datetime(reference_date, errors="coerce")
    if pd.isna(parsed):
        return pd.Timestamp.today().normalize()
    return pd.Timestamp(parsed).normalize()


def _normalize_due_date(value):
    """Normalize due date values to midnight pandas Timestamp or NaT."""
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return pd.NaT
    return pd.Timestamp(parsed).normalize()


def _priority_metadata_for_due_date(due_date, reference_date):
    """Classify a due date into priority windows."""
    if pd.isna(due_date):
        return 2, "Standard", "Outside 10 Weeks", None

    days_until_due = int((due_date - reference_date).days)
    if days_until_due <= HIGHEST_PRIORITY_WINDOW_DAYS:
        return 0, "Highest Priority", "Next 2 Weeks", days_until_due
    if days_until_due <= PRIORITY_REVIEW_WINDOW_DAYS:
        return 1, "Priority Review", "Next 10 Weeks", days_until_due
    return 2, "Standard", "Outside 10 Weeks", days_until_due


def prioritize_schedule_rows(schedule_df, reference_date=None):
    """Annotate and sort scheduler rows for due-date planning priority."""
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

    if ALLOY_COMPATIBILITY_MATCH_ALL_COLUMN not in prioritized.columns:
        prioritized[ALLOY_COMPATIBILITY_MATCH_ALL_COLUMN] = "NO"

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
