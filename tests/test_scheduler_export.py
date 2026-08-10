import sys
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from openpyxl import load_workbook
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fmes.config import Columns
from fmes.scheduler_export import build_daily_export_blocks, build_excel_rows, build_heat_daily_totals_rows, build_heat_planner_rows, build_heat_summary_rows, export_heat_summary, export_mold_schedule


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

        blocks = build_daily_export_blocks(daily_schedules, day_dates)
        excel_rows = build_excel_rows(blocks)

        self.assertEqual(blocks[1]["weight_total"], 25)
        self.assertEqual(blocks[1]["mold_total"], 2)
        self.assertGreater(len(excel_rows), 0)
        self.assertEqual(excel_rows[1][-1], "Heat #")

    def test_export_mold_schedule_writes_file(self):
        frame = pd.DataFrame([
            {
                Columns.COL_DUE_DATE: "2026-08-04 00:00:00",
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
                "Heat #": 1,
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
            export_mold_schedule(export_blocks, str(output_file))
            self.assertTrue(output_file.exists())

            wb = load_workbook(output_file)
            ws = wb["Mold Schedule"]
            due_date_cell = ws.cell(4, 1)
            self.assertIsInstance(due_date_cell.value, datetime)
            self.assertEqual(due_date_cell.value.date().isoformat(), "2026-08-04")
            self.assertEqual(due_date_cell.value.time().isoformat(), "00:00:00")
            self.assertEqual(due_date_cell.number_format, "m/d/yyyy")
            self.assertEqual(ws.cell(3, 13).value, "Heat #")
            self.assertEqual(ws.cell(4, 13).value, 1)

    def test_export_mold_schedule_creates_missing_parent_directory(self):
        export_blocks = {
            1: {
                "date": pd.Timestamp("2026-08-04"),
                "weekday": "Tuesday",
                "rows": pd.DataFrame([
                    {
                        Columns.COL_DUE_DATE: "2026-08-04 00:00:00",
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
                        "Heat #": 1,
                    }
                ]),
                "weight_total": 25,
                "mold_total": 2,
            }
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "nested" / "mold_schedule.xlsx"
            export_mold_schedule(export_blocks, str(output_file))
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

        with patch("fmes.scheduler_export.Workbook.save", side_effect=PermissionError("locked")):
            with self.assertRaises(RuntimeError) as context:
                export_mold_schedule(export_blocks, "locked.xlsx")

        self.assertIn("Failed while exporting mold schedule", str(context.exception))

    def test_build_heat_summary_rows_uses_melt_plan_summary(self):
        heat_summary = pd.DataFrame([
            {
                "Heat Slot": 1,
                "Heat #": 1,
                "Heat Status": "Planned",
                "Planning Priority": "Highest Priority",
                "Review Window": "Next 2 Weeks",
                "Anchor Alloy": "LEW15",
                "Compatibility Group": "A216",
                "Earliest Due Date": pd.Timestamp("2026-08-04").date(),
                "Latest Due Date": pd.Timestamp("2026-08-04").date(),
                "Total Weight (lbs)": 1200,
                "Total Molds": 4,
                "Rows in Heat": 2,
                "Jobs": "5001",
                "Extensions": "5001-A, 5001-B",
            },
            {
                "Heat Slot": 6,
                "Heat #": "",
                "Heat Status": "Reserved",
                "Planning Priority": "",
                "Review Window": "",
                "Anchor Alloy": "",
                "Compatibility Group": "",
                "Earliest Due Date": "",
                "Latest Due Date": "",
                "Total Weight (lbs)": 0,
                "Total Molds": 0,
                "Rows in Heat": 0,
                "Jobs": "",
                "Extensions": "",
            },
        ])

        melt_schedule = {
            1: {
                "heat_summary": heat_summary,
                "rows": pd.DataFrame([
                    {
                        Columns.COL_DUE_DATE: "2026-08-04",
                        Columns.COL_JOB_NUMBER: "5001",
                        "EXT": "A",
                        "Molds for EXT": 2,
                        "Heat #": 1,
                    },
                    {
                        Columns.COL_DUE_DATE: "2026-08-05",
                        Columns.COL_JOB_NUMBER: "5001",
                        "EXT": "B",
                        "Molds for EXT": 2,
                        "Heat #": 1,
                    },
                ]),
            }
        }
        day_dates = {1: {"date": pd.Timestamp("2026-08-04"), "weekday": "Tuesday"}}

        summary = build_heat_summary_rows((melt_schedule, day_dates))
        self.assertEqual(len(summary), 2)
        self.assertEqual(summary[0]["Heat Slot"], 1)
        self.assertEqual(summary[0]["Heat #"], 1)
        self.assertEqual(summary[0]["Anchor Alloy"], "LEW15")
        self.assertEqual(summary[0]["Total Weight (lbs)"], 1200.0)
        self.assertEqual(summary[0]["Total Molds"], 4.0)
        self.assertEqual(
            summary[0]["Job Breakout"],
            "5001-A | Due 08/04/2026 | Molds 2; 5001-B | Due 08/05/2026 | Molds 2",
        )
        self.assertEqual(summary[1]["Heat Status"], "Reserved")

    def test_build_heat_planner_rows_keeps_reserved_slot_blank_for_manual_fill(self):
        summary_rows = [
            {
                "Schedule Date": pd.Timestamp("2026-08-04").date(),
                "Weekday": "Tuesday",
                "Heat Slot": 6,
                "Heat #": "",
                "Heat Status": "Reserved",
                "Planning Priority": "",
                "Review Window": "",
                "Anchor Alloy": "",
                "Compatibility Group": "",
                "Earliest Due Date": "",
                "Latest Due Date": "",
                "Total Weight (lbs)": 0.0,
                "Total Molds": 0.0,
                "Rows in Heat": 0,
                "Jobs": "",
                "Extensions": "",
            }
        ]

        planner_rows = build_heat_planner_rows(summary_rows)
        self.assertEqual(planner_rows[0]["Heat Slot"], 6)
        self.assertEqual(planner_rows[0]["Manual Alloy"], "")
        self.assertEqual(planner_rows[0]["Planner Notes"], "")

    def test_export_heat_summary_writes_file(self):
        melt_schedule = {
            1: {
                "heat_summary": pd.DataFrame([
                    {
                        "Heat Slot": 1,
                        "Heat #": 1,
                        "Heat Status": "Planned",
                        "Planning Priority": "Highest Priority",
                        "Review Window": "Next 2 Weeks",
                        "Anchor Alloy": "LEW15",
                        "Compatibility Group": "A216",
                        "Earliest Due Date": pd.Timestamp("2026-08-04").date(),
                        "Latest Due Date": pd.Timestamp("2026-08-04").date(),
                        "Total Weight (lbs)": 600,
                        "Total Molds": 2,
                        "Rows in Heat": 1,
                        "Jobs": "5001",
                        "Extensions": "5001-A",
                    },
                    {
                        "Heat Slot": "",
                        "Heat #": 2,
                        "Heat Status": "Overflow",
                        "Planning Priority": "Highest Priority",
                        "Review Window": "Next 2 Weeks",
                        "Anchor Alloy": "LEW15",
                        "Compatibility Group": "A216",
                        "Earliest Due Date": pd.Timestamp("2026-08-04").date(),
                        "Latest Due Date": pd.Timestamp("2026-08-04").date(),
                        "Total Weight (lbs)": 400,
                        "Total Molds": 1,
                        "Rows in Heat": 1,
                        "Jobs": "5002",
                        "Extensions": "5002-B",
                    },
                    {
                        "Heat Slot": 6,
                        "Heat #": "",
                        "Heat Status": "Reserved",
                        "Planning Priority": "",
                        "Review Window": "",
                        "Anchor Alloy": "",
                        "Compatibility Group": "",
                        "Earliest Due Date": "",
                        "Latest Due Date": "",
                        "Total Weight (lbs)": 0,
                        "Total Molds": 0,
                        "Rows in Heat": 0,
                        "Jobs": "",
                        "Extensions": "",
                    },
                ]),
                "rows": pd.DataFrame([
                    {
                        Columns.COL_DUE_DATE: "2026-08-04",
                        Columns.COL_JOB_NUMBER: "5001",
                        "EXT": "A",
                        "Molds for EXT": 2,
                        "Heat #": 1,
                    },
                    {
                        Columns.COL_DUE_DATE: "2026-08-04",
                        Columns.COL_JOB_NUMBER: "5002",
                        "EXT": "B",
                        "Molds for EXT": 1,
                        "Heat #": 2,
                    },
                ]),
            }
        }
        day_dates = {1: {"date": pd.Timestamp("2026-08-04"), "weekday": "Tuesday"}}

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "heat_summary.xlsx"
            export_heat_summary(melt_schedule, day_dates, str(output_file))
            self.assertTrue(output_file.exists())

            wb = load_workbook(output_file)
            ws = wb["Heat Summary"]
            self.assertEqual(ws.cell(1, 1).value, "Schedule Date")
            self.assertEqual(ws.cell(1, 3).value, "Heat Slot")
            self.assertEqual(ws.cell(2, 3).value, 1)
            self.assertEqual(ws.cell(2, 8).value, "LEW15")
            self.assertEqual(ws.cell(1, 17).value, "Job Breakout")
            self.assertEqual(
                ws.cell(2, 17).value,
                "5001-A | Due 08/04/2026 | Molds 2",
            )

            ws_daily = wb["Daily Heat Totals"]
            self.assertEqual(ws_daily.cell(1, 1).value, "Schedule Date")
            self.assertEqual(ws_daily.cell(1, 3).value, "Total Heats")
            self.assertEqual(ws_daily.cell(2, 3).value, 2)
            self.assertEqual(ws_daily.cell(2, 4).value, 1)
            self.assertEqual(ws_daily.cell(2, 5).value, 1)
            self.assertEqual(ws_daily.cell(2, 6).value, 1000)

            ws_planner = wb["Heat Planner"]
            self.assertEqual(ws_planner.cell(1, 16).value, "Manual Alloy")
            self.assertEqual(ws_planner.cell(4, 3).value, 6)
            self.assertEqual(ws_planner.cell(4, 16).value, None)

    def test_export_heat_summary_creates_missing_parent_directory(self):
        melt_schedule = {
            1: {
                "heat_summary": pd.DataFrame(),
                "rows": pd.DataFrame(),
            }
        }
        day_dates = {1: {"date": pd.Timestamp("2026-08-04"), "weekday": "Tuesday"}}

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "nested" / "heat_summary.xlsx"
            export_heat_summary(melt_schedule, day_dates, str(output_file))
            self.assertTrue(output_file.exists())

    def test_build_heat_daily_totals_rows(self):
        summary_rows = [
            {
                "Schedule Date": pd.Timestamp("2026-08-04").date(),
                "Weekday": "Tuesday",
                "Heat Slot": 1,
                "Heat #": 1,
                "Heat Status": "Planned",
                "Anchor Alloy": "LEW15",
                "Total Weight (lbs)": 600.0,
                "Total Molds": 2.0,
                "Rows in Heat": 1,
            },
            {
                "Schedule Date": pd.Timestamp("2026-08-04").date(),
                "Weekday": "Tuesday",
                "Heat Slot": "",
                "Heat #": 2,
                "Heat Status": "Overflow",
                "Anchor Alloy": "WCB",
                "Total Weight (lbs)": 900.0,
                "Total Molds": 3.0,
                "Rows in Heat": 2,
            },
            {
                "Schedule Date": pd.Timestamp("2026-08-04").date(),
                "Weekday": "Tuesday",
                "Heat Slot": 6,
                "Heat #": "",
                "Heat Status": "Reserved",
                "Anchor Alloy": "",
                "Total Weight (lbs)": 0.0,
                "Total Molds": 0.0,
                "Rows in Heat": 0,
            },
        ]

        daily_rows = build_heat_daily_totals_rows(summary_rows)
        self.assertEqual(len(daily_rows), 1)
        self.assertEqual(daily_rows[0]["Total Heats"], 2)
        self.assertEqual(daily_rows[0]["Planned Heats"], 1)
        self.assertEqual(daily_rows[0]["Overflow Heats"], 1)
        self.assertEqual(daily_rows[0]["Total Weight (lbs)"], 1500.0)
        self.assertEqual(daily_rows[0]["Total Molds"], 5.0)

    def test_export_heat_summary_wraps_save_failures(self):
        melt_schedule = {
            1: {
                "heat_summary": pd.DataFrame(),
            }
        }
        day_dates = {1: {"date": pd.Timestamp("2026-08-04"), "weekday": "Tuesday"}}

        with patch("fmes.scheduler_export.Workbook.save", side_effect=PermissionError("locked")):
            with self.assertRaises(RuntimeError) as context:
                export_heat_summary(melt_schedule, day_dates, "locked_heat.xlsx")

        self.assertIn("Failed while exporting heat summary", str(context.exception))


if __name__ == "__main__":
    unittest.main()