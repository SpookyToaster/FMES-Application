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

        export_blocks = {
            1: {
                "date": pd.Timestamp("2026-08-04"),
                "weekday": "Tuesday",
                "rows": pd.DataFrame(),
                "weight_total": 0,
                "mold_total": 0,
            }
        }

        mold_schedule_rows = pd.DataFrame([
            {
                Columns.COL_JOB_NUMBER: "9001",
                Columns.COL_ALLOY: "A",
                "EXT": "",
                "Molds for EXT": 1,
                "Total Weight per EXT": 100,
                "Schedule Day": 1,
                "Pour Schedule Day": 2,
                "Heat #": 1,
            }
        ])

        with patch("fmes.scheduler.read_file", return_value=input_file), \
             patch("fmes.scheduler.sync_open_order_report_with_sql", return_value={"row_count": 1, "backup_path": "b", "historical_oor_path": "h", "db_snapshot_path": "s"}), \
             patch("fmes.scheduler.mold_scheduler", return_value=input_file.iloc[[0]]), \
             patch("fmes.scheduler.build_schedule_rows", return_value=input_file.iloc[[0]].assign(**{"EXT": "", "Extension_Seq": 0, "Molds for EXT": 1, "Total Weight per EXT": 100})), \
             patch("fmes.scheduler.prioritize_schedule_rows", side_effect=lambda df: df), \
             patch("fmes.scheduler.build_melt_schedule", return_value={1: {"rows": pd.DataFrame([{"Pour Schedule Day": 1, "Heat #": 1}])}}), \
             patch("fmes.scheduler.assign_mold_days_from_heat_plan", return_value=(mold_schedule_rows, 0)), \
             patch("fmes.scheduler.rebuild_melt_schedule_from_planned_rows", return_value=({2: {"rows": pd.DataFrame([{"Pour Schedule Day": 2, "Heat #": 1}])}}, mold_schedule_rows)), \
             patch("fmes.scheduler.build_schedule_dates", return_value={1: {"date": pd.Timestamp("2026-08-04"), "weekday": "Tuesday"}, 2: {"date": pd.Timestamp("2026-08-05"), "weekday": "Wednesday"}}), \
             patch("fmes.scheduler.build_daily_export_blocks", return_value=export_blocks), \
             patch("fmes.scheduler.print_export_blocks"), \
             patch("fmes.scheduler.print_bucket"):
            result = scheduler.schedule_molds()

        self.assertEqual(result["export_blocks"], export_blocks)
        self.assertIn("melt_schedule", result)
        self.assertEqual(result["mold_day_dates"][1]["weekday"], "Tuesday")
        self.assertEqual(result["pour_day_dates"][2]["weekday"], "Wednesday")

    def test_schedule_molds_backfills_melt_plan_rows_into_export_blocks(self):
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

        melt_plan_rows = pd.DataFrame([
            {
                Columns.COL_DUE_DATE: "2026-08-04",
                "Customer Name": "Customer",
                "Part Number": "P1",
                Columns.COL_JOB_NUMBER: "9001",
                "EXT": "A",
                Columns.COL_ALLOY: "A",
                Columns.COL_CAST_TYPE: "L",
                "Quantity of Molds": 1,
                "Castings Per Mold": 1,
                "Quantity of Cores": 0,
                "Total Weight per EXT": 100,
                "Molds for EXT": 1,
                "Pour Schedule Day": 1,
                "Heat #": 7,
            }
        ])

        mold_schedule_rows = melt_plan_rows.assign(**{"Schedule Day": 1, "Pour Schedule Day": 2})

        with patch("fmes.scheduler.read_file", return_value=input_file), \
             patch("fmes.scheduler.sync_open_order_report_with_sql", return_value={"row_count": 1, "backup_path": "b", "historical_oor_path": "h", "db_snapshot_path": "s"}), \
             patch("fmes.scheduler.mold_scheduler", return_value=input_file.iloc[[0]]), \
             patch("fmes.scheduler.build_schedule_rows", return_value=input_file.iloc[[0]].assign(**{"EXT": "", "Extension_Seq": 0, "Molds for EXT": 1, "Total Weight per EXT": 100})), \
             patch("fmes.scheduler.prioritize_schedule_rows", side_effect=lambda df: df), \
             patch("fmes.scheduler.build_melt_schedule", return_value={1: {"rows": melt_plan_rows}}), \
             patch("fmes.scheduler.assign_mold_days_from_heat_plan", return_value=(mold_schedule_rows, 0)), \
             patch("fmes.scheduler.rebuild_melt_schedule_from_planned_rows", return_value=({2: {"rows": melt_plan_rows.assign(**{"Pour Schedule Day": 2})}}, mold_schedule_rows)), \
             patch("fmes.scheduler.build_schedule_dates", return_value={1: {"date": pd.Timestamp("2026-08-04"), "weekday": "Tuesday"}, 2: {"date": pd.Timestamp("2026-08-05"), "weekday": "Wednesday"}}), \
             patch("fmes.scheduler.build_daily_export_blocks", return_value={}) as build_daily_export_blocks, \
             patch("fmes.scheduler.print_export_blocks"), \
             patch("fmes.scheduler.print_bucket"):
            scheduler.schedule_molds()

        backfilled_daily_schedules = build_daily_export_blocks.call_args.args[0]
        self.assertEqual(backfilled_daily_schedules[1].iloc[0]["Heat #"], 7)
        self.assertEqual(
            backfilled_daily_schedules[1].iloc[0][Columns.COL_JOB_NUMBER],
            "9001",
        )

    def test_schedule_molds_filters_to_ten_week_horizon_boundary(self):
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
             patch(
                 "fmes.scheduler.prioritize_schedule_rows",
                 side_effect=lambda df: df.assign(
                     **{"Days Until Due": [70, 71], "Planning Priority": ["Priority Review", "Standard"]}
                 ),
             ), \
             patch("fmes.scheduler.build_melt_schedule", return_value={}) as build_melt_schedule, \
             patch("fmes.scheduler.assign_mold_days_from_heat_plan", return_value=(pd.DataFrame(), 0)), \
             patch("fmes.scheduler.rebuild_melt_schedule_from_planned_rows", return_value=({}, pd.DataFrame())), \
             patch("fmes.scheduler.build_schedule_dates", return_value={}), \
             patch("fmes.scheduler.build_daily_export_blocks", return_value={}), \
             patch("fmes.scheduler.build_job_shipping_report_rows", return_value=[]), \
             patch("fmes.scheduler.print_export_blocks"), \
             patch("fmes.scheduler.print_bucket"):
            scheduler.schedule_molds()

        melt_input_df = build_melt_schedule.call_args.args[0]
        self.assertEqual(melt_input_df[Columns.COL_JOB_NUMBER].tolist(), ["9009"])

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

        mold_schedule_rows = pd.DataFrame([
            {
                Columns.COL_JOB_NUMBER: "9010",
                Columns.COL_ALLOY: "A",
                "EXT": "",
                "Molds for EXT": 1,
                "Total Weight per EXT": 100,
                "Schedule Day": 1,
                "Pour Schedule Day": 3,
                "Heat #": 1,
            }
        ])

        calendar = {
            1: {"date": pd.Timestamp("2026-08-11"), "weekday": "Tuesday"},
            2: {"date": pd.Timestamp("2026-08-12"), "weekday": "Wednesday"},
            3: {"date": pd.Timestamp("2026-08-13"), "weekday": "Thursday"},
        }

        with patch("fmes.scheduler.read_file", return_value=input_file), \
             patch("fmes.scheduler.sync_open_order_report_with_sql", return_value={"row_count": 1, "backup_path": "b", "historical_oor_path": "h", "db_snapshot_path": "s"}), \
             patch("fmes.scheduler.mold_scheduler", return_value=input_file.iloc[[0]]), \
             patch("fmes.scheduler.build_schedule_rows", return_value=input_file.iloc[[0]].assign(**{"EXT": "", "Extension_Seq": 0, "Molds for EXT": 1, "Total Weight per EXT": 100})), \
             patch("fmes.scheduler.prioritize_schedule_rows", side_effect=lambda df: df.assign(**{"Days Until Due": 1})), \
             patch("fmes.scheduler.build_melt_schedule", return_value={1: {"rows": pd.DataFrame([{"Pour Schedule Day": 1, "Heat #": 1}])}}), \
             patch("fmes.scheduler.assign_mold_days_from_heat_plan", return_value=(mold_schedule_rows, 0)), \
             patch("fmes.scheduler.rebuild_melt_schedule_from_planned_rows", return_value=({3: {"rows": mold_schedule_rows}}, mold_schedule_rows)), \
             patch("fmes.scheduler.build_schedule_dates", return_value=calendar) as build_schedule_dates, \
             patch("fmes.scheduler.build_daily_export_blocks", return_value={}), \
             patch("fmes.scheduler.build_job_shipping_report_rows", return_value=[]), \
             patch("fmes.scheduler.print_export_blocks"), \
             patch("fmes.scheduler.print_bucket"):
            result = scheduler.schedule_molds()

        calendar_days = sorted(build_schedule_dates.call_args.args[0].keys())
        self.assertEqual(calendar_days, [1, 2, 3])
        self.assertEqual(result["mold_day_dates"], {1: calendar[1]})
        self.assertEqual(result["pour_day_dates"], {3: calendar[3]})


if __name__ == "__main__":
    unittest.main()