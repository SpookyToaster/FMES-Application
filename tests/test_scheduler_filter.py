import sys
from pathlib import Path
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Columns
from scheduler_filter import Mold_Scheduler, filtered_job_counts


class SchedulerFilterTests(unittest.TestCase):
    def setUp(self):
        for key in filtered_job_counts:
            filtered_job_counts[key] = 0

    def test_mold_scheduler_filters_expected_rows(self):
        frame = pd.DataFrame([
            {Columns.COL_JOB_NUMBER: None, Columns.COL_HOLD: "NO", Columns.COL_JOB_TYPE: "", Columns.COL_SCHEDULED: "NO", Columns.COL_CAST_TYPE: "L", Columns.COL_MOLDS_NEEDED: 1},
            {Columns.COL_JOB_NUMBER: "1001", Columns.COL_HOLD: "YES", Columns.COL_JOB_TYPE: "", Columns.COL_SCHEDULED: "NO", Columns.COL_CAST_TYPE: "L", Columns.COL_MOLDS_NEEDED: 1},
            {Columns.COL_JOB_NUMBER: "1002", Columns.COL_HOLD: "NO", Columns.COL_JOB_TYPE: "IFA", Columns.COL_SCHEDULED: "NO", Columns.COL_CAST_TYPE: "L", Columns.COL_MOLDS_NEEDED: 1},
            {Columns.COL_JOB_NUMBER: "1003", Columns.COL_HOLD: "NO", Columns.COL_JOB_TYPE: "", Columns.COL_SCHEDULED: "YES", Columns.COL_CAST_TYPE: "L", Columns.COL_MOLDS_NEEDED: 1},
            {Columns.COL_JOB_NUMBER: "1004", Columns.COL_HOLD: "NO", Columns.COL_JOB_TYPE: "", Columns.COL_SCHEDULED: "NO", Columns.COL_CAST_TYPE: "I", Columns.COL_MOLDS_NEEDED: 1},
            {Columns.COL_JOB_NUMBER: "1005", Columns.COL_HOLD: "NO", Columns.COL_JOB_TYPE: "", Columns.COL_SCHEDULED: "NO", Columns.COL_CAST_TYPE: "L", Columns.COL_MOLDS_NEEDED: 0},
            {Columns.COL_JOB_NUMBER: "2000", Columns.COL_HOLD: "NO", Columns.COL_JOB_TYPE: "", Columns.COL_SCHEDULED: "NO", Columns.COL_CAST_TYPE: "L", Columns.COL_MOLDS_NEEDED: 2},
        ])

        result = Mold_Scheduler(frame)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][Columns.COL_JOB_NUMBER], "1003")
        self.assertEqual(result[1][Columns.COL_JOB_NUMBER], "2000")
        self.assertEqual(filtered_job_counts["added"], 2)
        self.assertEqual(filtered_job_counts["blank"], 1)


if __name__ == "__main__":
    unittest.main()