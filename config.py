# OneDrive Filepath for shared repository
ONEDRIVE_ROOT = (r"C:\Users\lburkardt\OneDrive - MonettMetalsUS1" )

# // =======================================================
# // Global Variables - declare constant variables
# // =======================================================
class Columns:
    COL_HOLD = "Hold"
    COL_SCHEDULED = "Scheduled"
    COL_DUE_DATE = "Due Date"
    COL_JOB_NUMBER = "Job Number"
    COL_MOLDS_NEEDED = "Molds Needed"
    COL_POUR_WEIGHT = "Pour Weight"
    COL_JOB_TYPE = "Job Type"
    COL_ALLOY = "Alloy"
    COL_CAST_TYPE = "Casting Type"
# change as needed

# Daily Molds limits, change as needed.
class DailyMoldLimits:
    MAX_L_MOLDS_PER_DAY = 30
    MAX_F_MOLDS_PER_DAY = 3