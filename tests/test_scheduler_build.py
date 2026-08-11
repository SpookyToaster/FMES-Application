import sys
from pathlib import Path
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fmes.config import Columns
from fmes.scheduler_build import build_schedule_dates, build_schedule_rows, expand_job


class SchedulerBuildTests(unittest.TestCase):
    def test_expand_job_returns_single_row_with_no_extension(self):
        job = pd.Series(
            {
                Columns.COL_JOB_NUMBER: "3001",
                Columns.COL_MOLDS_NEEDED: 24,
                Columns.COL_POUR_WEIGHT: 200,
                Columns.COL_CAST_TYPE: "L",
                Columns.COL_ALLOY: "A",
            }
        )

        expanded = expand_job(job)

        self.assertEqual(len(expanded), 1)
        self.assertEqual(expanded[0]["EXT"], "")
        self.assertEqual(expanded[0]["Extension_Seq"], 0)
        self.assertEqual(expanded[0]["Molds for EXT"], 24)
        self.assertEqual(expanded[0]["Total Weight per EXT"], 4800)

    def test_build_schedule_rows_skips_zero_mold_jobs(self):
        jobs = [
            pd.Series(
                {
                    Columns.COL_JOB_NUMBER: "4001",
                    Columns.COL_MOLDS_NEEDED: 0,
                    Columns.COL_POUR_WEIGHT: 100,
                }
            ),
            pd.Series(
                {
                    Columns.COL_JOB_NUMBER: "4002",
                    Columns.COL_MOLDS_NEEDED: 2,
                    Columns.COL_POUR_WEIGHT: 100,
                }
            ),
        ]

        rows = build_schedule_rows(jobs)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][Columns.COL_JOB_NUMBER], "4002")
        self.assertEqual(rows[0]["Molds for EXT"], 2)

    def test_build_schedule_dates_skips_weekend(self):
        daily = {1: pd.DataFrame(), 2: pd.DataFrame(), 3: pd.DataFrame()}
        day_dates = build_schedule_dates(daily, pd.Timestamp("2026-08-14"))

        self.assertEqual(day_dates[1]["weekday"], "Friday")
        self.assertEqual(day_dates[2]["weekday"], "Monday")
        self.assertEqual(day_dates[3]["weekday"], "Tuesday")


if __name__ == "__main__":
    unittest.main()
