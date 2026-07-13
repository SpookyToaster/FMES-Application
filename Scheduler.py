
# program status - updated 7-13-2026, 12:41pm - Logan Burkardt
# reads from OOR report
# successfully identifies which jobs are ready to mold, excluding Holds, Scheduled, and Molds needed = 0.
# need to push list of jobs into daily schedule next
# then build Mold WIP for Melt schedule
# then build Casting WIP for clean schedule
# then work to automated the database export and clean up file repos to one location

# // =======================================================
# // Imports
# // =======================================================

import pandas as pd

# may not need fuzzywuzzy as data export *should* be consistent. 
from fuzzywuzzy import process
import math
import string


# // =======================================================
# // Global Variables - declare constant variables
# // =======================================================
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
max_molds_per_day = 6

max_l_molds_per_day = 30
max_f_molds_per_day = 3

# dictionary to track job counts as the filtering
# incremented during mold scheduler
filtered_job_counts = {
    "blank":0,
    "hold":0,
    "scheduled":0,
    "job_type":0,
    "cast_type":0,
    "no_molds":0,
    "added":0,
}

# // =======================================================
# // Functions - Placeholder for refactoring into functions and classes
# // =======================================================

def Read_File(filepath = "C:\\Users\\lburkardt\\OneDrive - MonettMetalsUS1\\Quality\\Schedule\\Open Order Report.xlsx"):
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

def Mold_Scheduler(ReadyToMold):
    # Molds needed column

    jobs_to_schedule = []

    for row, job in ReadyToMold.iterrows():

        # Filter out blank rows
        if pd.isna(job[COL_JOB_NUMBER]): 
            filtered_job_counts["blank"] += 1
            continue
         
        # filter checks for On hold, already scheduled, or all molds completed, or if investment job by job type or cast type
        if str(job[COL_HOLD]).upper() == "YES":
            filtered_job_counts["hold"] += 1
            continue
        
        if str(job[COL_JOB_TYPE]) == "IFA":
            filtered_job_counts["job_type"] += 1
            continue

        if str(job[COL_JOB_TYPE]) == "IFC":
            filtered_job_counts["job_type"] += 1
            continue

        if str(job[COL_SCHEDULED]).upper() == "YES":
            filtered_job_counts["scheduled"] += 1
            continue

        if str(job[COL_CAST_TYPE]).upper() == "I":
            filtered_job_counts["cast_type"] += 1
            continue
            
        if job[COL_MOLDS_NEEDED] <= 0:
            filtered_job_counts["no_molds"] += 1
            continue
        
        # add jobs that made it through the filter to jobs to schedule list
        filtered_job_counts["added"] += 1
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

# calculate how many times we need to split a job (basically how many days to complete a job so we can assign extension letters)
def Calculate_Splits(job):
    
    molds_needed = math.ceil(job[COL_MOLDS_NEEDED])
    
    # round up mold count as we cannot produce partial molds
    daily_limit = Get_daily_mold_limit(job)
    
    splits = math.ceil(molds_needed / daily_limit)

    return splits

# prep job for push into daily mold schedule format
def Expand_Job(job):
    molds_needed = math.ceil(job[COL_MOLDS_NEEDED])

    splits = Calculate_Splits(job)

    extensions = get_extensions(splits)

    rows = []

    molds_remaining = molds_needed

    daily_limit = Get_daily_mold_limit(job)

    # find which is lesser, molds needed or max molds
    for ext in extensions:


        molds_for_ext = min(
            daily_limit, molds_remaining
        )

        row = job.copy()

        row["EXT"] = ext
        row["Molds for EXT"] = molds_for_ext
    
        row["Total Weight per EXT"] = (
            molds_for_ext *
            row[COL_POUR_WEIGHT]
        )

        rows.append(row)

        molds_remaining -= molds_for_ext

    return rows

# add jobs to list after splitting into extensions
def Build_Schedule_Rows(jobs_to_schedule):
    schedule_rows = []

    for job in jobs_to_schedule:
        expanded_rows = Expand_Job(job)

        schedule_rows.extend(expanded_rows)

    return schedule_rows

# test function to print out selected jobs to schedule to mold
def jobs_to_schedule_test():
    print("\nJobs selected for scheduling:")

    for job in Jobs_to_schedule:
        print(
            f"{job[COL_JOB_NUMBER]} | "
            f"{job['Customer Name']} | "
            f"Molds Needed: {job[COL_MOLDS_NEEDED]}"
        )

    print(f"\nTotal Jobs Selected: {len(Jobs_to_schedule)}")

# test function to print out selected jobs with extensions assigned.
def Scheduled_rows_test():
    
    for row in Schedule_rows:
        print(
            f"{row[COL_JOB_NUMBER]}"
            f"{row['EXT']} | "
            f"{row['Molds for EXT']} molds"
        )

# checks row for casting type and assigns limit per day that can be made
def Get_daily_mold_limit(job):
    pour_weight = job[COL_POUR_WEIGHT]

    if pour_weight > 300:
        return 3
    
    casting_type = str(job["Casting Type"]).upper()

    if casting_type == "F":
        return 3
    
    return 6


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

InputFile = Read_File()

Jobs_to_schedule = Mold_Scheduler(InputFile)

Schedule_rows = Build_Schedule_Rows(Jobs_to_schedule)

print(filtered_job_counts)

Schedule_Data_Frame = pd.DataFrame(Schedule_rows)

Schedule_Data_Frame = Schedule_Data_Frame.sort_values(
    by = [COL_ALLOY, COL_DUE_DATE, COL_JOB_NUMBER],
    ascending = [False,False, False]
)

print(Schedule_Data_Frame)


print("Press enter to exit...")