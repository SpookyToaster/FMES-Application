import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Columns
from scheduler_export import Build_Daily_Export_Blocks, Build_Excel_Rows, Export_Mold_Schedule


class SchedulerExportTests(unittest.TestCase):
    def test_build_export_blocks_and_excel_rows(self):
        frame = pd.DataFrame([
            {
                Columns.COL_DUE_DATE: "2026-08-04",
                "Customer Name": "Customer",
                "Part Number": "P1",
                Columns.COL_JOB_NUMBER: "5001",
                "EXT": "",
                Columns.COL_ALLOY: "A",
                Columns.COL_CAST_TYPE: "L",
                "Quantity of Molds": 1,
                "Castings Per Mold": 1,
                "Quantity of Cores": 0,
                "Total Weight per EXT": 25,
                "Molds for EXT": 2,
            }
        ])

        daily_schedules = {1: frame}
        day_dates = {1: {"date": pd.Timestamp("2026-08-04"), "weekday": "Tuesday"}}

        blocks = Build_Daily_Export_Blocks(daily_schedules, day_dates)
        excel_rows = Build_Excel_Rows(blocks)

        self.assertEqual(blocks[1]["weight_total"], 25)
        self.assertEqual(blocks[1]["mold_total"], 2)
        self.assertGreater(len(excel_rows), 0)

    def test_export_mold_schedule_writes_file(self):
        frame = pd.DataFrame([
            {
                Columns.COL_DUE_DATE: "2026-08-04",
                "Customer Name": "Customer",
                "Part Number": "P1",
                Columns.COL_JOB_NUMBER: "5001",
                "EXT": "",
                Columns.COL_ALLOY: "A",
                Columns.COL_CAST_TYPE: "L",
                "Quantity of Molds": 1,
                "Castings Per Mold": 1,
                "Quantity of Cores": 0,
                "Total Weight per EXT": 25,
                "Molds for EXT": 2,
            }
        ])

        export_blocks = {
            1: {
                "date": pd.Timestamp("2026-08-04"),
                "weekday": "Tuesday",
                "rows": frame,
                "weight_total": 25,
                "mold_total": 2,
            }
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "mold_schedule.xlsx"
            Export_Mold_Schedule(export_blocks, str(output_file))
            self.assertTrue(output_file.exists())

    def test_export_mold_schedule_wraps_save_failures(self):
        export_blocks = {
            1: {
                "date": pd.Timestamp("2026-08-04"),
                "weekday": "Tuesday",
                "rows": pd.DataFrame(),
                "weight_total": 0,
                "mold_total": 0,
            }
        }

        with patch("scheduler_export.Workbook.save", side_effect=PermissionError("locked")):
            with self.assertRaises(RuntimeError) as context:
                Export_Mold_Schedule(export_blocks, "locked.xlsx")

        self.assertIn("Failed while exporting mold schedule", str(context.exception))


if __name__ == "__main__":
    unittest.main()