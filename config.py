"""
Application-wide configuration constants.

Keep tunable parameters (DailyMoldLimits) here so they can be adjusted
without touching business logic.
"""


class Columns:
    """Canonical column header names as they appear in the Open Order Report."""
    COL_HOLD = "Hold"
    COL_SCHEDULED = "Scheduled"
    COL_DUE_DATE = "Due Date"
    COL_JOB_NUMBER = "Job Number"
    COL_MOLDS_NEEDED = "Molds Needed"
    COL_POUR_WEIGHT = "Pour Weight"
    COL_JOB_TYPE = "Job Type"
    COL_ALLOY = "Alloy"
    COL_CAST_TYPE = "Casting Type"


class DailyMoldLimits:
    """Maximum molds the foundry can produce per bucket type in a single day."""
    MAX_L_MOLDS_PER_DAY = 30   # Line (L) molds
    MAX_F_MOLDS_PER_DAY = 3    # Floor (F) molds