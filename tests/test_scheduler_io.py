import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from openpyxl import Workbook, load_workbook
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduler_io import Read_File, SQL_MAIN_EXPORT_COLUMNS, Sync_Open_Order_Report_With_SQL


class SchedulerIOTests(unittest.TestCase):
    def test_read_file_strips_headers(self):
        frame = pd.DataFrame(columns=[" Job Number ", " Due Date "])

        with patch("scheduler_io.pd.read_excel", return_value=frame):
            result = Read_File("sample.xlsx")

        self.assertEqual(list(result.columns), ["Job Number", "Due Date"])

    def test_read_file_wraps_failures(self):
        with patch("scheduler_io.pd.read_excel", side_effect=FileNotFoundError("missing")):
            with self.assertRaises(RuntimeError) as context:
                Read_File(filepath="missing.xlsx", source="excel")

        self.assertIn("Failed to read schedule input", str(context.exception))

    def test_read_file_sql_normalizes_required_scheduler_columns(self):
        sql_rows = [
            {
                "Due Date": "2026-08-04",
                "Customer Name": "Customer",
                "Part Number": "P1",
                "Job Type": "JOB",
                "Job Number": "9001",
                "Alloy": "A",
                "Casting Type": "L",
                "Quantity of Molds": 10,
                "Castings Per Mold": 2,
                "Quantity of Cores": 1,
                "Pour Weight": 100,
                "Molds Completed": 3,
            }
        ]

        with patch("scheduler_io.get_main_dashboard_rows", return_value=sql_rows):
            frame = Read_File(source="sql")

        self.assertEqual(frame.iloc[0]["Molds Needed"], 7)
        self.assertEqual(frame.iloc[0]["Hold"], "NO")
        self.assertEqual(frame.iloc[0]["Scheduled"], "NO")

    def test_read_file_sql_wraps_failures(self):
        with patch("scheduler_io.get_main_dashboard_rows", side_effect=RuntimeError("db down")):
            with self.assertRaises(RuntimeError) as context:
                Read_File(source="sql")

        self.assertIn("Failed to read schedule input from SQL", str(context.exception))

    def test_sync_open_order_report_with_sql_writes_backup_history_and_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_path = temp_path / "Open Order Report.xlsx"
            backup_dir = temp_path / "Backups"
            hist_dir = temp_path / "Historical OORs"
            snap_dir = temp_path / "Historical DB Snapshots"

            workbook = Workbook()
            ws = workbook.active
            ws.title = "OOR"

            for idx in range(1, 23):
                ws.cell(row=1, column=idx).value = f"H{idx}"

            ws.cell(row=2, column=6).value = "old-f2"
            ws.cell(row=3, column=6).value = "old-f3"
            workbook.save(source_path)

            sql_rows = [
                {
                    "Due Date": "2026-08-04",
                    "Customer Name": "Customer A",
                    "Part Number": "P1",
                    "Job Type": "JOB",
                    "Job Number": "9001",
                    "Alloy": "A",
                    "Casting Type": "L",
                    "QTY Ordered": 10,
                    "Quantity of Molds": 5,
                    "Castings Per Mold": 2,
                    "Quantity of Cores": 1,
                    "Pour Weight": 100,
                    "Total Pour WT": 500,
                    "Total Value": 1000,
                    "Heat No Assigned": "H1",
                    "Castings Produced": 3,
                    "Molds Completed": 1,
                }
            ]

            with patch("scheduler_io.get_main_dashboard_rows", return_value=sql_rows):
                result = Sync_Open_Order_Report_With_SQL(
                    source_workbook_path=str(source_path),
                    backup_dir=str(backup_dir),
                    historical_oor_dir=str(hist_dir),
                    db_snapshot_dir=str(snap_dir),
                )

            self.assertEqual(result["row_count"], 1)
            self.assertTrue(Path(result["backup_path"]).exists())
            self.assertTrue(Path(result["historical_oor_path"]).exists())
            self.assertTrue(Path(result["db_snapshot_path"]).exists())

            synced_wb = load_workbook(source_path)
            synced_ws = synced_wb["OOR"]
            self.assertEqual(synced_ws.cell(row=2, column=6).value, "2026-08-04")
            self.assertEqual(synced_ws.cell(row=2, column=22).value, "1")
            self.assertIsNone(synced_ws.cell(row=3, column=6).value)
            synced_wb.close()

            snapshot_wb = load_workbook(result["db_snapshot_path"])
            snapshot_ws = snapshot_wb["SQL Snapshot"]
            header_values = [snapshot_ws.cell(row=1, column=i + 1).value for i in range(len(SQL_MAIN_EXPORT_COLUMNS))]
            self.assertEqual(header_values, SQL_MAIN_EXPORT_COLUMNS)
            snapshot_wb.close()


if __name__ == "__main__":
    unittest.main()