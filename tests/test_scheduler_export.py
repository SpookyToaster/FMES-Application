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
from fmes.scheduler_export import build_daily_export_blocks, build_excel_rows, build_heat_daily_totals_rows, build_heat_summary_rows, export_heat_summary, export_mold_schedule


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

    def test_build_heat_summary_rows_groups_by_day_and_heat(self):
        frame = pd.DataFrame([
            {
                Columns.COL_DUE_DATE: "2026-08-04",
                Columns.COL_ALLOY: "LEW15",
                "Total Weight per EXT": 600,
                "Molds for EXT": 2,
                "Heat #": 1,
            },
            {
                Columns.COL_DUE_DATE: "2026-08-04",
                Columns.COL_ALLOY: "LEW15",
                "Total Weight per EXT": 600,
                "Molds for EXT": 2,
                "Heat #": 1,
            },
            {
                Columns.COL_DUE_DATE: "2026-08-04",
                Columns.COL_ALLOY: "MN STEEL",
                "Total Weight per EXT": 500,
                "Molds for EXT": 1,
                "Heat #": 2,
            },
        ])

        export_blocks = {
            1: {
                "date": pd.Timestamp("2026-08-04"),
                "weekday": "Tuesday",
                "rows": frame,
                "weight_total": 1700,
                "mold_total": 5,
            }
        }

        summary = build_heat_summary_rows(export_blocks)
        self.assertEqual(len(summary), 2)
        self.assertEqual(summary[0]["Heat #"], 1)
        self.assertEqual(summary[0]["Alloy"], "LEW15")
        self.assertEqual(summary[0]["Total Weight (lbs)"], 1200.0)
        self.assertEqual(summary[0]["Total Molds"], 4.0)
        self.assertEqual(summary[1]["Heat #"], 2)
        self.assertEqual(summary[1]["Alloy"], "MN STEEL")

    def test_export_heat_summary_writes_file(self):
        frame = pd.DataFrame([
            {
                Columns.COL_DUE_DATE: "2026-08-04",
                Columns.COL_ALLOY: "LEW15",
                "Total Weight per EXT": 600,
                "Molds for EXT": 2,
                "Heat #": 1,
            },
            {
                Columns.COL_DUE_DATE: "2026-08-04",
                Columns.COL_ALLOY: "LEW15",
                "Total Weight per EXT": 400,
                "Molds for EXT": 1,
                "Heat #": 2,
            }
        ])

        export_blocks = {
            1: {
                "date": pd.Timestamp("2026-08-04"),
                "weekday": "Tuesday",
                "rows": frame,
                "weight_total": 600,
                "mold_total": 2,
            }
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "heat_summary.xlsx"
            export_heat_summary(export_blocks, str(output_file))
            self.assertTrue(output_file.exists())

            wb = load_workbook(output_file)
            ws = wb["Heat Summary"]
            self.assertEqual(ws.cell(1, 1).value, "Schedule Date")
            self.assertEqual(ws.cell(1, 3).value, "Heat #")
            self.assertEqual(ws.cell(2, 3).value, 1)
            self.assertEqual(ws.cell(2, 4).value, "LEW15")

            ws_daily = wb["Daily Heat Totals"]
            self.assertEqual(ws_daily.cell(1, 1).value, "Schedule Date")
            self.assertEqual(ws_daily.cell(1, 3).value, "Total Heats")
            self.assertEqual(ws_daily.cell(2, 3).value, 2)
            self.assertEqual(ws_daily.cell(2, 4).value, 1000)

    def test_build_heat_daily_totals_rows(self):
        summary_rows = [
            {
                "Schedule Date": pd.Timestamp("2026-08-04").date(),
                "Weekday": "Tuesday",
                "Heat #": 1,
                "Alloy": "LEW15",
                "Total Weight (lbs)": 600.0,
                "Total Molds": 2.0,
                "Rows in Heat": 1,
            },
            {
                "Schedule Date": pd.Timestamp("2026-08-04").date(),
                "Weekday": "Tuesday",
                "Heat #": 2,
                "Alloy": "WCB",
                "Total Weight (lbs)": 900.0,
                "Total Molds": 3.0,
                "Rows in Heat": 2,
            },
        ]

        daily_rows = build_heat_daily_totals_rows(summary_rows)
        self.assertEqual(len(daily_rows), 1)
        self.assertEqual(daily_rows[0]["Total Heats"], 2)
        self.assertEqual(daily_rows[0]["Total Weight (lbs)"], 1500.0)
        self.assertEqual(daily_rows[0]["Total Molds"], 5.0)

    def test_export_heat_summary_wraps_save_failures(self):
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
                export_heat_summary(export_blocks, "locked_heat.xlsx")

        self.assertIn("Failed while exporting heat summary", str(context.exception))


if __name__ == "__main__":
    unittest.main()