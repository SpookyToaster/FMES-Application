"""Alloy compatibility reference-data helpers for FMES."""

import pandas as pd

from .config import Columns, Paths


DEFAULT_ALLOY_COMPATIBILITY_CSV_PATH = str(Paths.ALLOY_COMPATIBILITY_CSV)

ALLOY_COMPATIBILITY_GROUP_COLUMN = "Compatibility Group"
ALLOY_COMPATIBILITY_MATCH_ALL_COLUMN = "Compatible With ASTM Group"
ALLOY_COMPATIBILITY_SPECIFIC_COLUMN = "Specific Compatible Alloys"


def _normalize_alloy_key(value):
    """Return normalized alloy key for lookup operations."""
    if value is None or pd.isna(value):
        return ""
    return str(value).strip().upper()


def _normalize_compatibility_flag(value, default=False):
    """Return True/False for common YES/NO style compatibility fields."""
    if value is None or pd.isna(value):
        return default

    normalized = str(value).strip().upper()
    if not normalized:
        return default

    return normalized in {"Y", "YES", "TRUE", "1"}


def _first_present_column(frame, candidates, required=False):
    """Return the first matching column name from candidates, or None."""
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate

    if required:
        raise RuntimeError(
            "Alloy compatibility CSV is missing required columns: "
            + ", ".join(candidates)
        )

    return None


def _normalize_specific_compatible_alloys(value):
    """Normalize comma-delimited specific alloy compatibility values."""
    if value is None or pd.isna(value):
        return ""

    normalized_values = []
    for item in str(value).split(","):
        alloy_code = _normalize_alloy_key(item)
        if alloy_code and alloy_code not in normalized_values:
            normalized_values.append(alloy_code)

    return ", ".join(normalized_values)


def load_alloy_compatibility_map(csv_path=DEFAULT_ALLOY_COMPATIBILITY_CSV_PATH):
    """Load alloy compatibility metadata keyed by alloy_code from CSV."""
    try:
        frame = pd.read_csv(csv_path)
    except FileNotFoundError:
        return {}
    except Exception as exc:
        raise RuntimeError(
            f"Failed to read alloy compatibility CSV from {csv_path}"
        ) from exc

    if frame.empty:
        return {}

    frame.columns = [str(col).strip() for col in frame.columns]
    alloy_code_column = _first_present_column(frame, ["alloy_code"], required=True)
    compatibility_group_column = _first_present_column(
        frame,
        ["compatibility_group", "astm_group", "astm_code"],
        required=True,
    )
    compatibility_all_column = _first_present_column(
        frame,
        ["Is_Compat_with_All", "is_compat_with_all", "compat_with_all", "compatible_with_all"],
        required=True,
    )
    specific_alloys_column = _first_present_column(
        frame,
        [
            "compatible_specific_alloys",
            "specific_compatible_alloys",
            "compatible_with_specific_alloys",
        ],
    )
    active_column = _first_present_column(frame, ["is_active", "active"])

    if active_column:
        active_mask = frame[active_column].apply(
            lambda value: _normalize_compatibility_flag(value, default=True)
        )
        active_rows = frame[active_mask]
    else:
        active_rows = frame

    compatibility_map = {}
    for _, row in active_rows.iterrows():
        alloy_code = _normalize_alloy_key(row.get(alloy_code_column))
        if not alloy_code:
            continue

        compatibility_group = str(row.get(compatibility_group_column, "")).strip()
        compatible_with_group = _normalize_compatibility_flag(
            row.get(compatibility_all_column),
            default=False,
        )
        specific_alloys = _normalize_specific_compatible_alloys(
            row.get(specific_alloys_column) if specific_alloys_column else ""
        )

        compatibility_map[alloy_code] = {
            ALLOY_COMPATIBILITY_GROUP_COLUMN: compatibility_group or alloy_code,
            ALLOY_COMPATIBILITY_MATCH_ALL_COLUMN: "YES" if compatible_with_group else "NO",
            ALLOY_COMPATIBILITY_SPECIFIC_COLUMN: specific_alloys,
        }

    return compatibility_map


def apply_alloy_compatibility(frame, compatibility_map):
    """Attach compatibility metadata columns based on Alloy values."""
    if frame.empty:
        frame[ALLOY_COMPATIBILITY_GROUP_COLUMN] = ""
        frame[ALLOY_COMPATIBILITY_MATCH_ALL_COLUMN] = ""
        frame[ALLOY_COMPATIBILITY_SPECIFIC_COLUMN] = ""
        return frame

    frame = frame.copy()

    alloy_series = frame.get(Columns.COL_ALLOY, pd.Series([""] * len(frame), index=frame.index))
    alloy_keys = alloy_series.apply(_normalize_alloy_key)

    def resolve_group(key):
        metadata = compatibility_map.get(key)
        if metadata:
            return metadata[ALLOY_COMPATIBILITY_GROUP_COLUMN]
        return key

    def resolve_match_all(key):
        metadata = compatibility_map.get(key)
        if metadata:
            return metadata[ALLOY_COMPATIBILITY_MATCH_ALL_COLUMN]
        return "NO"

    def resolve_specific_alloys(key):
        metadata = compatibility_map.get(key)
        if metadata:
            return metadata[ALLOY_COMPATIBILITY_SPECIFIC_COLUMN]
        return ""

    frame[ALLOY_COMPATIBILITY_GROUP_COLUMN] = alloy_keys.apply(resolve_group)
    frame[ALLOY_COMPATIBILITY_MATCH_ALL_COLUMN] = alloy_keys.apply(resolve_match_all)
    frame[ALLOY_COMPATIBILITY_SPECIFIC_COLUMN] = alloy_keys.apply(resolve_specific_alloys)
    return frame


def can_alloy_share_heat_with(
    anchor_alloy,
    candidate_alloy,
    compatibility_map=None,
    csv_path=DEFAULT_ALLOY_COMPATIBILITY_CSV_PATH,
):
    """
    Return True when candidate_alloy can be poured into a heat anchored by anchor_alloy.

    The rule is directional so stricter alloys can accept looser alloys without
    implying the reverse is also valid.
    """
    anchor_key = _normalize_alloy_key(anchor_alloy)
    candidate_key = _normalize_alloy_key(candidate_alloy)

    if not anchor_key or not candidate_key:
        return anchor_key == candidate_key and bool(anchor_key)

    if anchor_key == candidate_key:
        return True

    compatibility_map = compatibility_map or load_alloy_compatibility_map(csv_path)
    anchor_metadata = compatibility_map.get(anchor_key)
    candidate_metadata = compatibility_map.get(candidate_key)

    if not anchor_metadata or not candidate_metadata:
        return False

    anchor_group = anchor_metadata.get(ALLOY_COMPATIBILITY_GROUP_COLUMN, "")
    candidate_group = candidate_metadata.get(ALLOY_COMPATIBILITY_GROUP_COLUMN, "")
    if not anchor_group or anchor_group != candidate_group:
        return False

    if anchor_metadata.get(ALLOY_COMPATIBILITY_MATCH_ALL_COLUMN) == "YES":
        return True

    specific_alloys = {
        _normalize_alloy_key(value)
        for value in str(anchor_metadata.get(ALLOY_COMPATIBILITY_SPECIFIC_COLUMN, "")).split(",")
        if _normalize_alloy_key(value)
    }
    return candidate_key in specific_alloys