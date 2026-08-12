import sys
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fmes import scheduler
from fmes.config import Columns


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

        with patch("fmes.scheduler.read_file", return_value=input_file), \
             patch("fmes.scheduler.sync_open_order_report_with_sql", return_value={"row_count": 1, "backup_path": "b", "historical_oor_path": "h", "db_snapshot_path": "s"}), \
             patch("fmes.scheduler.mold_scheduler", return_value=input_file.iloc[[0]]), \
             patch("fmes.scheduler.build_schedule_rows", return_value=input_file.iloc[[0]].assign(**{"EXT": "", "Extension_Seq": 0, "Molds for EXT": 1, "Total Weight per EXT": 100})), \
             patch("fmes.scheduler.build_schedule_dates", return_value={1: {"date": pd.Timestamp("2026-08-04"), "weekday": "Tuesday"}}), \
             patch("fmes.scheduler.build_daily_export_blocks", return_value={}), \
             patch("fmes.scheduler.build_job_shipping_report_rows", return_value=[]), \
             patch("fmes.scheduler.print_export_blocks"):
            result = scheduler.schedule_molds()

        self.assertEqual(result["export_blocks"], {})
        self.assertIn("melt_schedule", result)
        self.assertEqual(result["mold_day_dates"][1]["weekday"], "Tuesday")
        self.assertEqual(result["pour_day_dates"][1]["weekday"], "Tuesday")
        self.assertEqual(result["melt_schedule"][1]["rows"].iloc[0][Columns.COL_JOB_NUMBER], "9001")

    def test_schedule_molds_seeds_melt_rows_from_prioritized_schedule(self):
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

        with patch("fmes.scheduler.read_file", return_value=input_file), \
             patch("fmes.scheduler.sync_open_order_report_with_sql", return_value={"row_count": 1, "backup_path": "b", "historical_oor_path": "h", "db_snapshot_path": "s"}), \
             patch("fmes.scheduler.mold_scheduler", return_value=input_file.iloc[[0]]), \
             patch("fmes.scheduler.build_schedule_rows", return_value=input_file.iloc[[0]].assign(**{"EXT": "", "Extension_Seq": 0, "Molds for EXT": 1, "Total Weight per EXT": 100})), \
             patch("fmes.scheduler.build_schedule_dates", return_value={1: {"date": pd.Timestamp("2026-08-04"), "weekday": "Tuesday"}}), \
             patch("fmes.scheduler.build_daily_export_blocks", return_value={}), \
             patch("fmes.scheduler.build_job_shipping_report_rows", return_value=[]), \
             patch("fmes.scheduler.print_export_blocks"):
            result = scheduler.schedule_molds()

        seeded_rows = result["melt_schedule"][1]["rows"]
        self.assertEqual(seeded_rows.iloc[0][Columns.COL_JOB_NUMBER], "9001")
        self.assertEqual(int(seeded_rows.iloc[0]["Pour Schedule Day"]), 1)

    def test_schedule_molds_keeps_all_normalized_rows_for_shipping_context(self):
        input_file = pd.DataFrame([
            {
                Columns.COL_JOB_NUMBER: "9009",
                Columns.COL_HOLD: "NO",
                Columns.COL_JOB_TYPE: "",
                Columns.COL_SCHEDULED: "NO",
                Columns.COL_CAST_TYPE: "L",
                Columns.COL_MOLDS_NEEDED: 1,
                Columns.COL_POUR_WEIGHT: 100,
                Columns.COL_ALLOY: "A",
                Columns.COL_DUE_DATE: "2026-10-19",
                "Part Number": "P9",
                "Customer Name": "Customer",
                "Quantity of Molds": 1,
                "Castings Per Mold": 1,
                "Quantity of Cores": 0,
            },
            {
                Columns.COL_JOB_NUMBER: "9010",
                Columns.COL_HOLD: "NO",
                Columns.COL_JOB_TYPE: "",
                Columns.COL_SCHEDULED: "NO",
                Columns.COL_CAST_TYPE: "L",
                Columns.COL_MOLDS_NEEDED: 1,
                Columns.COL_POUR_WEIGHT: 100,
                Columns.COL_ALLOY: "A",
                Columns.COL_DUE_DATE: "2026-10-20",
                "Part Number": "P10",
                "Customer Name": "Customer",
                "Quantity of Molds": 1,
                "Castings Per Mold": 1,
                "Quantity of Cores": 0,
            },
        ])

        schedule_rows_df = pd.DataFrame([
            {
                Columns.COL_JOB_NUMBER: "9009",
                Columns.COL_CAST_TYPE: "L",
                Columns.COL_POUR_WEIGHT: 100,
                Columns.COL_ALLOY: "A",
                Columns.COL_DUE_DATE: "2026-10-19",
                "EXT": "",
                "Extension_Seq": 0,
                "Molds for EXT": 1,
                "Total Weight per EXT": 100,
            },
            {
                Columns.COL_JOB_NUMBER: "9010",
                Columns.COL_CAST_TYPE: "L",
                Columns.COL_POUR_WEIGHT: 100,
                Columns.COL_ALLOY: "A",
                Columns.COL_DUE_DATE: "2026-10-20",
                "EXT": "",
                "Extension_Seq": 0,
                "Molds for EXT": 1,
                "Total Weight per EXT": 100,
            },
        ])

        with patch("fmes.scheduler.read_file", return_value=input_file), \
             patch("fmes.scheduler.sync_open_order_report_with_sql", return_value={"row_count": 1, "backup_path": "b", "historical_oor_path": "h", "db_snapshot_path": "s"}), \
             patch("fmes.scheduler.mold_scheduler", return_value=input_file.iloc[[0]]), \
             patch("fmes.scheduler.build_schedule_rows", return_value=schedule_rows_df), \
             patch("fmes.scheduler.build_schedule_dates", return_value={1: {"date": pd.Timestamp("2026-08-11"), "weekday": "Tuesday"}}), \
             patch("fmes.scheduler.build_daily_export_blocks", return_value={}), \
             patch("fmes.scheduler.build_job_shipping_report_rows", return_value=[]) as build_job_shipping_report_rows, \
             patch("fmes.scheduler.print_export_blocks"):
            scheduler.schedule_molds()

        filtered_df = build_job_shipping_report_rows.call_args.args[0]
        self.assertEqual(filtered_df[Columns.COL_JOB_NUMBER].tolist(), ["9009", "9010"])

    def test_schedule_molds_uses_one_calendar_for_mold_and_pour_days(self):
        input_file = pd.DataFrame([
            {
                Columns.COL_JOB_NUMBER: "9010",
                Columns.COL_HOLD: "NO",
                Columns.COL_JOB_TYPE: "",
                Columns.COL_SCHEDULED: "NO",
                Columns.COL_CAST_TYPE: "L",
                Columns.COL_MOLDS_NEEDED: 1,
                Columns.COL_POUR_WEIGHT: 100,
                Columns.COL_ALLOY: "A",
                Columns.COL_DUE_DATE: "2026-08-04",
                "Part Number": "P10",
                "Customer Name": "Customer",
                "Quantity of Molds": 1,
                "Castings Per Mold": 1,
                "Quantity of Cores": 0,
            }
        ])

        calendar = {
            1: {"date": pd.Timestamp("2026-08-11"), "weekday": "Tuesday"},
        }

        with patch("fmes.scheduler.read_file", return_value=input_file), \
             patch("fmes.scheduler.sync_open_order_report_with_sql", return_value={"row_count": 1, "backup_path": "b", "historical_oor_path": "h", "db_snapshot_path": "s"}), \
             patch("fmes.scheduler.mold_scheduler", return_value=input_file.iloc[[0]]), \
             patch("fmes.scheduler.build_schedule_rows", return_value=input_file.iloc[[0]].assign(**{"EXT": "", "Extension_Seq": 0, "Molds for EXT": 1, "Total Weight per EXT": 100})), \
             patch("fmes.scheduler.build_schedule_dates", return_value=calendar) as build_schedule_dates, \
             patch("fmes.scheduler.build_daily_export_blocks", return_value={}), \
             patch("fmes.scheduler.build_job_shipping_report_rows", return_value=[]), \
             patch("fmes.scheduler.print_export_blocks"):
            result = scheduler.schedule_molds()

        calendar_days = sorted(build_schedule_dates.call_args.args[0].keys())
        self.assertEqual(calendar_days, [1])
        self.assertEqual(result["mold_day_dates"], {1: calendar[1]})
        self.assertEqual(result["pour_day_dates"], {1: calendar[1]})


if __name__ == "__main__":
    unittest.main()
