import json
import sys
from pathlib import Path
import tempfile
import unittest

from openpyxl import Workbook
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fmes.report_pack import write_reporting_pack


class ReportPackTests(unittest.TestCase):
    def test_write_reporting_pack_outputs_expected_files(self):
        schedule_result = {
            "export_blocks": {
                1: {
                    "rows": pd.DataFrame([{"Job Number": "5001"}]),
                    "mold_total": 2,
                    "weight_total": 600,
                }
            },
            "melt_schedule": {
                1: {
                    "rows": pd.DataFrame([
                        {"Heat #": 1, "Total Weight per EXT": 600},
                    ])
                }
            },
            "job_shipping_rows": [
                {
                    "Job Number": "5001",
                    "Customer Name": "Customer",
                    "Schedule Status": "Scheduled",
                    "Planned Molds": 2,
                    "Scheduled Molds": 2,
                    "Expected Ship Date": "2026-08-19",
                    "Due Date": "2026-08-20",
                    "Ship Buffer Days": 1,
                    "On-Time": "YES",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            oor_source = Path(temp_dir) / "Open Order Report.xlsx"
            Workbook().save(oor_source)

            result = write_reporting_pack(
                schedule_result,
                temp_dir,
                open_order_report_path=str(oor_source),
            )

            self.assertTrue(Path(result["summary_json"]).exists())
            self.assertTrue(Path(result["job_shipping_csv"]).exists())
            self.assertTrue(Path(result["attention_jobs_csv"]).exists())
            self.assertTrue(Path(result["capacity_csv"]).exists())
            self.assertTrue(Path(result["report_pack_workbook"]).exists())
            self.assertTrue(Path(result["distribution_manifest"]).exists())
            self.assertTrue(Path(result["open_order_workbook"]).exists())

            with Path(result["summary_json"]).open("r", encoding="utf-8") as handle:
                summary = json.load(handle)
            self.assertEqual(summary["day_block_count"], 1)
            self.assertEqual(summary["status_summary"]["Total Jobs"], 1)

            with Path(result["distribution_manifest"]).open("r", encoding="utf-8") as handle:
                manifest = json.load(handle)
            self.assertEqual(len(manifest["audiences"]), 3)
            self.assertEqual(
                manifest["audiences"][0]["recipients"],
                [
                    "sliles@monettmetals.com",
                    "BRaub@monettmetals.com",
                    "lburkardt@monettmetals.com",
                ],
            )
            first_audience_attachments = manifest["audiences"][0]["attachments"]
            self.assertEqual(len(first_audience_attachments), 2)
            self.assertNotIn(result["job_shipping_csv"], first_audience_attachments)
            self.assertNotIn(result["attention_jobs_csv"], first_audience_attachments)
            self.assertNotIn(result["capacity_csv"], first_audience_attachments)
            self.assertNotIn(result["summary_json"], first_audience_attachments)
            self.assertIn(result["report_pack_workbook"], first_audience_attachments)
            self.assertIn(result["open_order_workbook"], first_audience_attachments)


if __name__ == "__main__":
    unittest.main()
