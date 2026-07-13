# imports

import pandas as pd

# may not need fuzzywuzzy as data export *should* be consistent. 
from fuzzywuzzy import process
import math
import string

# =============================================
# Program outline

# Raw Excel Data
#     ↓

# Filter Jobs
#     ↓

# Split Jobs
#     ↓

# Assign Weekdays
#     ↓

# Build Schedule Rows
#     ↓

# Schedule DataFrame
#     ↓

# Apply Formatting
#     ↓

# Export Excel

# =============================================

# // =======================================================
# // Global Variables - declare constant variables
# // =======================================================
COL_HOLD = "Hold"
COL_SCHEDULED = "Scheduled"
COL_DUE_DATE = "Due Date"
COL_JOB_NUMBER = "Job Number"
COL_MOLDS_NEEDED = "Molds Needed"
COL_POUR_WEIGHT = "Pour Weight"

# change as needed
max_molds_per_day = 6

# // =======================================================
# // Functions - Placeholder for refactoring into functions and classes
# // =======================================================


def ReadFile(filepath = "C:\\Users\\lburkardt\\OneDrive - MonettMetalsUS1\\Quality\\Schedule\\Open Order Report.xlsx"):
    # // Read input from file for list of ready to schedule jobs
    # File 
    ImportedFile = pd.read_excel(filepath, sheet_name="OOR")

    # remove trailing and leading white space
    ImportedFile.columns = ImportedFile.columns.str.strip()

    #test print
    # print(ImportedFile)  

    return(ImportedFile)

# // =======================================================
# // Scheduling Module - Prep and Mold
# // =======================================================

# if on hold, do not schedule
# maybe if not on hold, generate list of schedulable jobs? 

def MoldScheduler(ReadyToMold):
    # Molds needed column

    jobs_to_schedule = []

    for row, job in ReadyToMold.iterrows():

        # Filter out blank rows
        if pd.isna(job[COL_JOB_NUMBER]): 
            continue
        # filter checks for On hold, already scheduled, or all molds completed
        if str(job[COL_HOLD]).upper() == "YES":
            continue

        if str(job[COL_SCHEDULED]).upper() == "YES":
            continue

        if job[COL_MOLDS_NEEDED] <= 0:
            continue
        
        jobs_to_schedule.append(job)


    return jobs_to_schedule
        
# function to assign extension letter based on 
def get_extensions(num_splits):
    if num_splits == 1:
         return ["L"]
    
    # create list to assign extensions for that specific job - will need called for each row?
    extensions = []

    alphabet = list(string.ascii_uppercase)

    for i in range(num_splits - 1):
        extensions.append(alphabet[i])

    extensions.append("L")

    return extensions



def Calculate_Splits(job):
    # round up mold count as we cannot produce partial molds
    molds_needed = math.ceil(job[COL_MOLDS_NEEDED])

    splits = math.ceil(molds_needed / max_molds_per_day)

    return splits

# // Manage list of jobs by categories so like-alloys can be scheduled together

# // check list of requirements for each day and add new next job line if it will not exceed requirements

# // if job exceeds single day requirements for itself then 

# // if exceeding requirements schedule on the following weekday

# // export when complete

# // =======================================================
# // Scheduling Module - Melt
# // =======================================================
# def MeltScheduler():
#     for i in MoldsCompleted:
#         if #cell == 0 molds left:
#             # put in list for pouring
#         else continue
            


# // If job has been scheduled and mold shows complete, but no heat number assigned. Show ready to pour

# // If ready to pour, read into list

# // for item in list add to ready-to-pour schedule

# // =======================================================
# // Cleaning Schedule
# // =======================================================
# def CleanScheduler():
#     for i in CastingsCreated():
#         if #cell == heat number
#             # put in list for pouring
#         else continue

# If heat number assigned, but not shipped, show on cleaning schedule sorted by due date.


# =======================================================
# Main Program Entry
# =======================================================

InputFile = ReadFile()

Jobs_to_schedule = MoldScheduler(InputFile)

print("\nJobs selected for scheduling:")

for job in Jobs_to_schedule:
    print(
        f"{job[COL_JOB_NUMBER]} | "
        f"{job['Customer Name']} | "
        f"Molds Needed: {job[COL_MOLDS_NEEDED]}"
    )

print(f"\nTotal Jobs Selected: {len(Jobs_to_schedule)}")

print("Press enter to exit...")