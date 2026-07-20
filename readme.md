# =======================================================
# Program Status
# Last Updated: 07-13-2026 12:41 PM
# Author: Logan Burkardt
#
# Current Functionality:
# - Reads Open Order Report (OOR).xlsx
# - Identifies jobs ready for molding
# - Excludes:
#     * On Hold jobs
#     * Already Scheduled jobs
#     * Jobs with 0 molds needed
#     * Investment castings (IFA, IFC, I)
#
# Planned Development:
# - Push mold schedule into daily production schedule
# - Build Melt WIP schedule
# - Build Casting/Cleaning WIP schedule
# - Automate database exports
# - Consolidate file repositories into a single location
# =======================================================


# =======================================================
# Description:
# This script reads the Open Order Report (OOR), filters jobs ready for molding,
# and builds a mold schedule while considering daily mold limits.
# It also provides functions to expand jobs into multiple extensions,
# assign schedule days, and print the schedule by bucket.
# =======================================================


# =======================================================
# Need to Refactor
# scheduler/
# │
# ├── Scheduler.py          # Main entry point only
# ├── config.py             # Constants and settings
# ├── schedule_logic.py     # Filtering, splitting, day assignment
# ├── schedule_builder.py   # Daily schedule creation
# ├── exports.py            # Excel export functions
# ├── io_utils.py           # File reading
# └── models.py             # Optional later