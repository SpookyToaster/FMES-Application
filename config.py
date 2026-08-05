"""
Application-wide configuration constants.

Keep environment-specific paths (ONEDRIVE_ROOT) and tunable parameters
(DailyMoldLimits) here so they can be adjusted without touching business logic.
"""

# OneDrive root shared across all users running this scheduler
ONEDRIVE_ROOT = (r"C:\Users\lburkardt\OneDrive - MonettMetalsUS1" )


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


class DatabaseConfig:
    """
    ODBC connection parameters for the SQL Server history database.

    These values are placeholders.  In production the connection is driven
    by environment variables read in Database.py; this class is retained
    for reference only.
    """
    ODBC_DRIVER = "ODBC Driver 17 for SQL Server"
    SERVER = "your_server_name"
    DATABASE = "your_database_name"
    USERNAME = "your_username"
    PASSWORD = "your_password"