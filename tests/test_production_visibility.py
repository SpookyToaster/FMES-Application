import sys
from pathlib import Path
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fmes.production_visibility import (
    build_attention_jobs_rows,
    build_daily_capacity_rows,
    build_job_status_summary,
)


class ProductionVisibilityTests(unittest.TestCase):
    def test_build_job_status_summary_counts(self):
        rows = [
            {"Job Number": "A", "Schedule Status": "Scheduled", "On-Time": "YES"},
            {"Job Number": "B", "Schedule Status": "Partially Scheduled", "On-Time": "NO"},
            {"Job Number": "C", "Schedule Status": "Not Yet Scheduled", "On-Time": "NOT SCHEDULED"},
            {"Job Number": "D", "Schedule Status": "Scheduled", "On-Time": "UNKNOWN"},
        ]

        summary = build_job_status_summary(rows)

        self.assertEqual(summary["Total Jobs"], 4)
        self.assertEqual(summary["Scheduled Jobs"], 2)
        self.assertEqual(summary["Partially Scheduled Jobs"], 1)
        self.assertEqual(summary["Not Yet Scheduled Jobs"], 1)
        self.assertEqual(summary["On-Time Yes"], 1)
        self.assertEqual(summary["On-Time No"], 1)
        self.assertEqual(summary["On-Time Not Scheduled"], 1)
        self.assertEqual(summary["On-Time Unknown"], 1)

    def test_build_attention_jobs_rows_flags_expected_jobs(self):
        rows = [
            {
                "Job Number": "A",
                "Customer Name": "Customer A",
                "Schedule Status": "Scheduled",
                "Planned Molds": 2,
                "Scheduled Molds": 2,
                "Expected Ship Date": "2026-08-20",
                "Due Date": "2026-08-25",
                "Ship Buffer Days": 5,
                "On-Time": "YES",
            },
            {
                "Job Number": "B",
                "Customer Name": "Customer B",
                "Schedule Status": "Partially Scheduled",
                "Planned Molds": 4,
                "Scheduled Molds": 1,
                "Expected Ship Date": "2026-08-21",
                "Due Date": "2026-08-23",
                "Ship Buffer Days": 2,
                "On-Time": "NO",
            },
        ]

        attention = build_attention_jobs_rows(rows, buffer_warning_days=4)

        self.assertEqual(len(attention), 1)
        self.assertEqual(attention[0]["Job Number"], "B")

    def test_build_daily_capacity_rows_aggregates_per_day(self):
        export_blocks = {
            1: {
                "rows": pd.DataFrame([{"Job Number": "5001"}]),
                "mold_total": 3,
                "weight_total": 750,
            }
        }
        melt_schedule = {
            1: {
                "rows": pd.DataFrame([
                    {"Heat #": 1, "Total Weight per EXT": 400},
                    {"Heat #": 2, "Total Weight per EXT": 500},
                ])
            }
        }

        rows = build_daily_capacity_rows(export_blocks, melt_schedule)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Day"], 1)
        self.assertEqual(rows[0]["Molds Scheduled"], 3)
        self.assertEqual(rows[0]["Heats Planned"], 2)
        self.assertEqual(rows[0]["Melt Weight (lbs)"], 900.0)


if __name__ == "__main__":
    unittest.main()
