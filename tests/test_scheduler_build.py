import sys
from pathlib import Path
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Columns
from scheduler_build import Assign_days, Build_Daily_Schedules, Build_Schedule_Dates, Build_Schedule_Rows, Calculate_Splits, Expand_Job, get_extensions


class SchedulerBuildTests(unittest.TestCase):
    def test_get_extensions_and_expand_job(self):
        job = pd.Series({
            Columns.COL_JOB_NUMBER: "3001",
            Columns.COL_MOLDS_NEEDED: 24,
            Columns.COL_POUR_WEIGHT: 200,
            Columns.COL_CAST_TYPE: "L",
            Columns.COL_ALLOY: "A",
        })

        self.assertEqual(get_extensions(1), [""])
        self.assertEqual(Calculate_Splits(job), 3)

        expanded = Expand_Job(job)
        self.assertEqual(len(expanded), 3)
        self.assertEqual(expanded[0]["EXT"], "A")
        self.assertEqual(expanded[1]["EXT"], "B")
        self.assertEqual(expanded[-1]["EXT"], "L")
        self.assertEqual([row["Molds for EXT"] for row in expanded], [10, 10, 4])

    def test_assign_days_and_daily_schedules(self):
        schedule_rows = Build_Schedule_Rows([
            pd.Series({
                Columns.COL_JOB_NUMBER: "4001",
                Columns.COL_MOLDS_NEEDED: 2,
                Columns.COL_POUR_WEIGHT: 100,
                Columns.COL_CAST_TYPE: "L",
                Columns.COL_ALLOY: "A",
                Columns.COL_DUE_DATE: "2026-08-04",
                "Part Number": "P1",
                "Customer Name": "Customer",
                "Quantity of Molds": 1,
                "Castings Per Mold": 1,
                "Quantity of Cores": 0,
            })
        ])

        frame = pd.DataFrame(schedule_rows)
        framed = Assign_days(frame)

        self.assertIn("Schedule Day", framed.columns)
        self.assertEqual(int(framed.iloc[0]["Schedule Day"]), 1)

        daily_schedules = Build_Daily_Schedules(framed)
        self.assertEqual(list(daily_schedules.keys()), [1])

        day_dates = Build_Schedule_Dates(daily_schedules, pd.Timestamp("2026-08-03"))
        self.assertIn(1, day_dates)

    def test_expand_job_preserves_remaining_extensions_after_partial_completion(self):
        job = pd.Series({
            Columns.COL_JOB_NUMBER: "5001",
            Columns.COL_MOLDS_NEEDED: 14,
            "Molds Completed": 10,
            Columns.COL_POUR_WEIGHT: 200,
            Columns.COL_CAST_TYPE: "L",
            Columns.COL_ALLOY: "A",
        })

        expanded = Expand_Job(job)

        self.assertEqual([row["EXT"] for row in expanded], ["B", "L"])
        self.assertEqual([row["Molds for EXT"] for row in expanded], [10, 4])

    def test_assign_days_splits_extension_across_days(self):
        schedule_df = pd.DataFrame([
            {
                Columns.COL_JOB_NUMBER: "6001",
                Columns.COL_POUR_WEIGHT: 150,
                Columns.COL_CAST_TYPE: "L",
                Columns.COL_ALLOY: "A",
                "Part Number": "P1",
                "EXT": "A",
                "Extension_Seq": 0,
                "Molds for EXT": 10,
                "Total Weight per EXT": 1500,
            }
        ])

        assigned = Assign_days(schedule_df)
        self.assertEqual([int(v) for v in assigned["Schedule Day"].tolist()], [1, 2])
        self.assertEqual(assigned["EXT"].tolist(), ["A", "A"])
        self.assertEqual([int(v) for v in assigned["Molds for EXT"].tolist()], [6, 4])

    def test_partial_completion_and_multi_day_extensions_work_together(self):
        job = pd.Series({
            Columns.COL_JOB_NUMBER: "7001",
            Columns.COL_MOLDS_NEEDED: 14,
            "Molds Completed": 10,
            Columns.COL_POUR_WEIGHT: 200,
            Columns.COL_CAST_TYPE: "L",
            Columns.COL_ALLOY: "A",
            "Part Number": "P7",
        })

        expanded = Expand_Job(job)
        self.assertEqual([row["EXT"] for row in expanded], ["B", "L"])
        self.assertEqual([int(row["Molds for EXT"]) for row in expanded], [10, 4])

        assigned = Assign_days(pd.DataFrame(expanded))
        self.assertEqual(assigned["EXT"].tolist(), ["B", "B", "L", "L"])
        self.assertEqual([int(v) for v in assigned["Schedule Day"].tolist()], [1, 2, 2, 3])
        self.assertEqual([int(v) for v in assigned["Molds for EXT"].tolist()], [6, 4, 2, 2])

    def test_daily_schedules_assign_heat_numbers_by_alloy_and_weight_limit(self):
        schedule_df = pd.DataFrame([
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "8001",
                Columns.COL_ALLOY: "LEW15",
                "Total Weight per EXT": 600,
                "Molds for EXT": 2,
            },
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "8002",
                Columns.COL_ALLOY: "LEW15",
                "Total Weight per EXT": 600,
                "Molds for EXT": 2,
            },
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "8003",
                Columns.COL_ALLOY: "MN STEEL",
                "Total Weight per EXT": 500,
                "Molds for EXT": 1,
            },
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "8004",
                Columns.COL_ALLOY: "WCB",
                "Total Weight per EXT": 1500,
                "Molds for EXT": 3,
            },
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "8005",
                Columns.COL_ALLOY: "WCB",
                "Total Weight per EXT": 1000,
                "Molds for EXT": 2,
            },
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "8006",
                Columns.COL_ALLOY: "WCB",
                "Total Weight per EXT": 800,
                "Molds for EXT": 2,
            },
        ])

        daily_schedules = Build_Daily_Schedules(schedule_df)
        day1 = daily_schedules[1]

        self.assertIn("Heat #", day1.columns)
        self.assertEqual(day1["Heat #"].tolist(), [1, 1, 2, 3, 4, 4])

    def test_daily_schedules_group_compatible_astm_alloys_together(self):
        schedule_df = pd.DataFrame([
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "8101",
                Columns.COL_ALLOY: "80-40",
                "Compatibility Group": "A148",
                "Compatible With ASTM Group": "YES",
                "Specific Compatible Alloys": "",
                "Total Weight per EXT": 800,
                "Molds for EXT": 2,
            },
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "8102",
                Columns.COL_ALLOY: "150-135",
                "Compatibility Group": "A148",
                "Compatible With ASTM Group": "YES",
                "Specific Compatible Alloys": "",
                "Total Weight per EXT": 900,
                "Molds for EXT": 2,
            },
        ])

        daily_schedules = Build_Daily_Schedules(schedule_df)
        day1 = daily_schedules[1]

        self.assertEqual(day1["Heat #"].tolist(), [1, 1])


if __name__ == "__main__":
    unittest.main()