import sys
from pathlib import Path
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fmes.config import Columns
from fmes.melt_planning import HIGHEST_PRIORITY_WINDOW_DAYS, PRIORITY_REVIEW_WINDOW_DAYS, prioritize_schedule_rows


class MeltPlanningTests(unittest.TestCase):
    def test_prioritize_schedule_rows_sets_priority_fields(self):
        schedule_df = pd.DataFrame(
            [
                {
                    Columns.COL_JOB_NUMBER: "5001",
                    Columns.COL_DUE_DATE: "2026-08-12",
                    Columns.COL_ALLOY: "LEW15",
                    "Molds for EXT": 2,
                    "Total Weight per EXT": 600,
                },
                {
                    Columns.COL_JOB_NUMBER: "5002",
                    Columns.COL_DUE_DATE: "2026-09-30",
                    Columns.COL_ALLOY: "WCB",
                    "Molds for EXT": 1,
                    "Total Weight per EXT": 500,
                },
            ]
        )

        prioritized = prioritize_schedule_rows(schedule_df, reference_date="2026-08-10")

        self.assertIn("Planning Priority Rank", prioritized.columns)
        self.assertIn("Planning Priority", prioritized.columns)
        self.assertIn("Review Window", prioritized.columns)
        self.assertIn("Days Until Due", prioritized.columns)
        self.assertIn("Due Date Sort", prioritized.columns)

        by_job = {row[Columns.COL_JOB_NUMBER]: row for _, row in prioritized.iterrows()}
        self.assertEqual(by_job["5001"]["Planning Priority"], "Highest Priority")
        self.assertEqual(by_job["5001"]["Days Until Due"], 2)
        self.assertEqual(by_job["5002"]["Planning Priority"], "Priority Review")

    def test_prioritize_schedule_rows_orders_by_rank_due_and_job(self):
        schedule_df = pd.DataFrame(
            [
                {
                    Columns.COL_JOB_NUMBER: "5003",
                    Columns.COL_DUE_DATE: "2026-08-20",
                    Columns.COL_ALLOY: "A",
                    "Extension_Seq": 1,
                },
                {
                    Columns.COL_JOB_NUMBER: "5002",
                    Columns.COL_DUE_DATE: "2026-08-20",
                    Columns.COL_ALLOY: "A",
                    "Extension_Seq": 0,
                },
                {
                    Columns.COL_JOB_NUMBER: "5001",
                    Columns.COL_DUE_DATE: "2026-08-11",
                    Columns.COL_ALLOY: "A",
                    "Extension_Seq": 0,
                },
            ]
        )

        prioritized = prioritize_schedule_rows(schedule_df, reference_date="2026-08-10")

        ordered_jobs = prioritized[Columns.COL_JOB_NUMBER].tolist()
        self.assertEqual(ordered_jobs[0], "5001")
        self.assertEqual(ordered_jobs[1:], ["5002", "5003"])

    def test_priority_window_constants_remain_expected(self):
        self.assertEqual(HIGHEST_PRIORITY_WINDOW_DAYS, 14)
        self.assertEqual(PRIORITY_REVIEW_WINDOW_DAYS, 70)


if __name__ == "__main__":
    unittest.main()
