# OneDrive Filepath for shared repository
ONEDRIVE_ROOT = (r"C:\Users\lburkardt\OneDrive - MonettMetalsUS1" )

# COLUMN HEADERS OF INCOMING DATA
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

# DAILY MOLDS LIMITS
class DailyMoldLimits:
    MAX_L_MOLDS_PER_DAY = 30
    MAX_F_MOLDS_PER_DAY = 3


# DATABASE CONFIGURATION FOR ODBC CONNECTION
class DatabaseConfig:
    ODBC_DRIVER = "ODBC Driver 17 for SQL Server"
    SERVER = "your_server_name"
    DATABASE = "your_database_name"
    USERNAME = "your_username"
    PASSWORD = "your_password"