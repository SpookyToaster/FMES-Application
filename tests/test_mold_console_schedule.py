import io
import sys
from pathlib import Path
import unittest
from contextlib import redirect_stdout

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fmes.config import Columns
from fmes.mold_console_schedule import build_mold_schedule_by_alloy_group, print_mold_schedule_console


class MoldConsoleScheduleTests(unittest.TestCase):
    def test_caps_total_line_molds_to_thirty_per_day(self):
        rows = []
        for i in range(6):
            rows.append(
                {
                    Columns.COL_JOB_NUMBER: f"L{i + 1:03d}",
                    Columns.COL_ALLOY: "A",
                    "Compatibility Group": "GROUP-A",
                    Columns.COL_CAST_TYPE: "L",
                    Columns.COL_DUE_DATE: "2026-08-20",
                    "Molds for EXT": 6,
                    Columns.COL_POUR_WEIGHT: 10,
                }
            )

        assigned = build_mold_schedule_by_alloy_group(pd.DataFrame(rows), max_jobs_per_day=10)
        line_by_day = assigned.groupby("Schedule Day")["Molds for EXT"].sum().to_dict()

        self.assertEqual(line_by_day, {1: 30, 2: 6})

    def test_combined_daily_limit_is_thirty_three(self):
        rows = []
        for i in range(5):
            rows.append(
                {
                    Columns.COL_JOB_NUMBER: f"L{i + 1:03d}",
                    Columns.COL_ALLOY: "A",
                    "Compatibility Group": "GROUP-A",
                    Columns.COL_CAST_TYPE: "L",
                    Columns.COL_DUE_DATE: "2026-08-20",
                    "Molds for EXT": 6,
                    Columns.COL_POUR_WEIGHT: 10,
                }
            )
        rows.append(
            {
                Columns.COL_JOB_NUMBER: "Z100",
                Columns.COL_ALLOY: "A",
                "Compatibility Group": "GROUP-A",
                Columns.COL_CAST_TYPE: "F",
                Columns.COL_DUE_DATE: "2026-08-20",
                "Molds for EXT": 4,
                Columns.COL_POUR_WEIGHT: 10,
            }
        )

        assigned = build_mold_schedule_by_alloy_group(pd.DataFrame(rows), max_jobs_per_day=10)
        molds_by_day = assigned.groupby("Schedule Day")["Molds for EXT"].sum().to_dict()
        day_one_floor = assigned[(assigned["Schedule Day"] == 1) & (assigned[Columns.COL_CAST_TYPE] == "F")]

        self.assertEqual(molds_by_day[1], 33)
        self.assertEqual(int(day_one_floor["Molds for EXT"].sum()), 3)

    def test_floor_job_does_not_block_line_fill_to_thirty_three(self):
        rows = []
        rows.append(
            {
                Columns.COL_JOB_NUMBER: "A100",
                Columns.COL_ALLOY: "A",
                "Compatibility Group": "GROUP-A",
                Columns.COL_CAST_TYPE: "F",
                Columns.COL_DUE_DATE: "2026-08-20",
                "Molds for EXT": 5,
                Columns.COL_POUR_WEIGHT: 10,
            }
        )
        for i in range(5):
            rows.append(
                {
                    Columns.COL_JOB_NUMBER: f"L{i + 1:03d}",
                    Columns.COL_ALLOY: "A",
                    "Compatibility Group": "GROUP-A",
                    Columns.COL_CAST_TYPE: "L",
                    Columns.COL_DUE_DATE: "2026-08-20",
                    "Molds for EXT": 6,
                    Columns.COL_POUR_WEIGHT: 10,
                }
            )

        assigned = build_mold_schedule_by_alloy_group(pd.DataFrame(rows), max_jobs_per_day=10)
        molds_by_day = assigned.groupby("Schedule Day")["Molds for EXT"].sum().to_dict()
        day_one_floor = assigned[(assigned["Schedule Day"] == 1) & (assigned[Columns.COL_CAST_TYPE] == "F")]
        day_one_line = assigned[(assigned["Schedule Day"] == 1) & (assigned[Columns.COL_CAST_TYPE] == "L")]

        self.assertEqual(molds_by_day[1], 33)
        self.assertEqual(int(day_one_floor["Molds for EXT"].sum()), 3)
        self.assertEqual(int(day_one_line["Molds for EXT"].sum()), 30)

    def test_greedy_priority_pulls_within_eight_weeks_first(self):
        rows = pd.DataFrame(
            [
                {
                    Columns.COL_JOB_NUMBER: "LONG",
                    Columns.COL_ALLOY: "A",
                    "Compatibility Group": "GROUP-A",
                    Columns.COL_CAST_TYPE: "L",
                    Columns.COL_DUE_DATE: "2026-12-15",
                    "Molds for EXT": 1,
                },
                {
                    Columns.COL_JOB_NUMBER: "SOON",
                    Columns.COL_ALLOY: "A",
                    "Compatibility Group": "GROUP-A",
                    Columns.COL_CAST_TYPE: "L",
                    Columns.COL_DUE_DATE: "2026-09-10",
                    "Molds for EXT": 1,
                },
            ]
        )

        assigned = build_mold_schedule_by_alloy_group(
            rows,
            max_jobs_per_day=10,
            reference_date="2026-08-01",
        )
        ordered_jobs = assigned[Columns.COL_JOB_NUMBER].tolist()

        self.assertEqual(ordered_jobs, ["SOON", "LONG"])

    def test_splits_line_molds_across_days_with_per_job_cap(self):
        rows = pd.DataFrame(
            [
                {
                    Columns.COL_JOB_NUMBER: "L100",
                    Columns.COL_ALLOY: "A",
                    "Compatibility Group": "GROUP-A",
                    Columns.COL_CAST_TYPE: "L",
                    Columns.COL_DUE_DATE: "2026-08-20",
                    "Molds for EXT": 14,
                    Columns.COL_POUR_WEIGHT: 10,
                }
            ]
        )

        assigned = build_mold_schedule_by_alloy_group(rows, max_jobs_per_day=10)
        by_day = assigned.groupby("Schedule Day")["Molds for EXT"].sum().to_dict()

        self.assertEqual(by_day, {1: 6, 2: 6, 3: 2})
        self.assertEqual(int(assigned["Molds for EXT"].sum()), 14)

    def test_splits_floor_molds_by_daily_total_cap(self):
        rows = pd.DataFrame(
            [
                {
                    Columns.COL_JOB_NUMBER: "F100",
                    Columns.COL_ALLOY: "A",
                    "Compatibility Group": "GROUP-A",
                    Columns.COL_CAST_TYPE: "F",
                    Columns.COL_DUE_DATE: "2026-08-20",
                    "Molds for EXT": 2,
                    Columns.COL_POUR_WEIGHT: 10,
                },
                {
                    Columns.COL_JOB_NUMBER: "F200",
                    Columns.COL_ALLOY: "A",
                    "Compatibility Group": "GROUP-A",
                    Columns.COL_CAST_TYPE: "F",
                    Columns.COL_DUE_DATE: "2026-08-20",
                    "Molds for EXT": 2,
                    Columns.COL_POUR_WEIGHT: 10,
                },
            ]
        )

        assigned = build_mold_schedule_by_alloy_group(rows, max_jobs_per_day=10)
        molds_by_day = assigned.groupby("Schedule Day")["Molds for EXT"].sum().to_dict()

        self.assertEqual(molds_by_day, {1: 3, 2: 1})
        self.assertEqual(int(assigned["Molds for EXT"].sum()), 4)

    def test_max_ten_unique_jobs_per_day(self):
        rows = []
        for i in range(12):
            rows.append(
                {
                    Columns.COL_JOB_NUMBER: f"J{i + 1:04d}",
                    Columns.COL_ALLOY: "A",
                    "Compatibility Group": "GROUP-A",
                    Columns.COL_DUE_DATE: "2026-08-20",
                    "Molds for EXT": 1,
                }
            )

        assigned = build_mold_schedule_by_alloy_group(pd.DataFrame(rows), max_jobs_per_day=10)

        day1 = assigned[assigned["Schedule Day"] == 1]
        day2 = assigned[assigned["Schedule Day"] == 2]

        self.assertEqual(day1[Columns.COL_JOB_NUMBER].nunique(), 10)
        self.assertEqual(day2[Columns.COL_JOB_NUMBER].nunique(), 2)
        self.assertEqual(len(assigned), 12)

    def test_orders_by_due_date_then_alloy_group(self):
        rows = pd.DataFrame(
            [
                {
                    Columns.COL_JOB_NUMBER: "B2",
                    Columns.COL_ALLOY: "B",
                    "Compatibility Group": "GROUP-B",
                    Columns.COL_DUE_DATE: "2026-08-22",
                    "Molds for EXT": 1,
                },
                {
                    Columns.COL_JOB_NUMBER: "A1",
                    Columns.COL_ALLOY: "A",
                    "Compatibility Group": "GROUP-A",
                    Columns.COL_DUE_DATE: "2026-08-25",
                    "Molds for EXT": 1,
                },
                {
                    Columns.COL_JOB_NUMBER: "A0",
                    Columns.COL_ALLOY: "A",
                    "Compatibility Group": "GROUP-A",
                    Columns.COL_DUE_DATE: "2026-08-20",
                    "Molds for EXT": 1,
                },
            ]
        )

        assigned = build_mold_schedule_by_alloy_group(rows, max_jobs_per_day=10)
        ordered_jobs = assigned[Columns.COL_JOB_NUMBER].tolist()

        self.assertEqual(ordered_jobs, ["A0", "B2", "A1"])
        self.assertTrue((assigned["Schedule Day"] == 1).all())

    def test_print_mold_schedule_console_includes_totals(self):
        rows = pd.DataFrame(
            [
                {
                    "Schedule Day": 1,
                    Columns.COL_JOB_NUMBER: "J0001",
                    Columns.COL_ALLOY: "A",
                    "Compatibility Group": "GROUP-A",
                    Columns.COL_DUE_DATE: "2026-08-20",
                    "Molds for EXT": 3,
                    Columns.COL_POUR_WEIGHT: 10,
                }
            ]
        )

        stream = io.StringIO()
        with redirect_stdout(stream):
            print_mold_schedule_console(rows)

        output = stream.getvalue()
        self.assertIn("Mold Schedule Day 1", output)
        self.assertIn("Row Weight", output)
        self.assertIn("30", output)
        self.assertIn("Unique Jobs: 1", output)
        self.assertIn("Total Molds: 3", output)


if __name__ == "__main__":
    unittest.main()
