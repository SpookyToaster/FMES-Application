from datetime import datetime, timedelta

import pandas as pd

from config import Columns
from scheduler_build import (
    Assign_days,
    Build_Daily_Schedules,
    Build_Schedule_Dates,
    Build_Schedule_Rows,
    print_bucket,
)

from scheduler_export import (
    Build_Daily_Export_Blocks,
    Export_Heat_Summary,
    Export_Mold_Schedule,
    Print_Export_Blocks,
)

from scheduler_filter import Mold_Scheduler
from scheduler_io import Read_File


def Schedule_Molds():
    try:
        input_file = Read_File()
        jobs_to_schedule = Mold_Scheduler(input_file)
        schedule_rows = Build_Schedule_Rows(jobs_to_schedule)

        schedule_data_frame = pd.DataFrame(schedule_rows)
        schedule_data_frame = (
            schedule_data_frame
            .sort_values(
                by=[
                    Columns.COL_ALLOY,
                    Columns.COL_DUE_DATE,
                    Columns.COL_JOB_NUMBER,
                    "Extension_Seq",
                ],
                ascending=[False, False, False, True],
            )
            .reset_index(drop=True)
        )

        schedule_data_frame = Assign_days(schedule_data_frame)

        print("\nDay Totals")
        print(schedule_data_frame.groupby("Schedule Day")["Molds for EXT"].sum())
        print(
            schedule_data_frame[
                [
                    Columns.COL_JOB_NUMBER,
                    "EXT",
                    Columns.COL_ALLOY,
                    "Molds for EXT",
                    "Schedule Day",
                ]
            ]
        )

        print_bucket(schedule_data_frame)

        daily_schedules = Build_Daily_Schedules(schedule_data_frame)
        day_dates = Build_Schedule_Dates(
            daily_schedules,
            datetime.today() + timedelta(days=1),
        )
        export_blocks = Build_Daily_Export_Blocks(daily_schedules, day_dates)
        Print_Export_Blocks(export_blocks)

        return export_blocks
    except Exception as exc:
        raise RuntimeError("Schedule_Molds failed during orchestration") from exc


if __name__ == "__main__":
    export_blocks = Schedule_Molds()

    output_file = (
        r"C:\Users\lburkardt\OneDrive - MonettMetalsUS1"
        r"\Quality\Schedule\Output\Mold Schedule.xlsx"
    )

    heat_summary_output_file = (
        r"C:\Users\lburkardt\OneDrive - MonettMetalsUS1"
        r"\Quality\Schedule\Output\Heat Summary.xlsx"
    )

    Export_Mold_Schedule(export_blocks, output_file)
    Export_Heat_Summary(export_blocks, heat_summary_output_file)