import sys
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import Scheduler
from config import Columns


class SchedulerIntegrationTests(unittest.TestCase):
    def test_schedule_molds_orchestrates_pipeline(self):
        input_file = pd.DataFrame([
            {
                Columns.COL_JOB_NUMBER: "9001",
                Columns.COL_HOLD: "NO",
                Columns.COL_JOB_TYPE: "",
                Columns.COL_SCHEDULED: "NO",
                Columns.COL_CAST_TYPE: "L",
                Columns.COL_MOLDS_NEEDED: 1,
                Columns.COL_POUR_WEIGHT: 100,
                Columns.COL_ALLOY: "A",
                Columns.COL_DUE_DATE: "2026-08-04",
                "Part Number": "P1",
                "Customer Name": "Customer",
                "Quantity of Molds": 1,
                "Castings Per Mold": 1,
                "Quantity of Cores": 0,
            }
        ])

        export_blocks = {
            1: {
                "date": pd.Timestamp("2026-08-04"),
                "weekday": "Tuesday",
                "rows": pd.DataFrame(),
                "weight_total": 0,
                "mold_total": 0,
            }
        }

        with patch("Scheduler.Read_File", return_value=input_file), \
               patch("Scheduler.Sync_Open_Order_Report_With_SQL", return_value={"row_count": 1, "backup_path": "b", "historical_oor_path": "h", "db_snapshot_path": "s"}), \
             patch("Scheduler.Mold_Scheduler", return_value=input_file.iloc[[0]]), \
             patch("Scheduler.Build_Schedule_Rows", return_value=input_file.iloc[[0]].assign(**{"EXT": "", "Extension_Seq": 0, "Molds for EXT": 1, "Total Weight per EXT": 100})), \
             patch("Scheduler.Assign_days", side_effect=lambda df: df.assign(**{"Schedule Day": 1})), \
             patch("Scheduler.Build_Daily_Schedules", return_value={1: pd.DataFrame()}), \
             patch("Scheduler.Build_Schedule_Dates", return_value={1: {"date": pd.Timestamp("2026-08-04"), "weekday": "Tuesday"}}), \
             patch("Scheduler.Build_Daily_Export_Blocks", return_value=export_blocks), \
             patch("Scheduler.Print_Export_Blocks"), \
             patch("Scheduler.print_bucket"):
            result = Scheduler.Schedule_Molds()

        self.assertEqual(result, export_blocks)


if __name__ == "__main__":
    unittest.main()