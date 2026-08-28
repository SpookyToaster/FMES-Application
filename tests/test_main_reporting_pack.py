import sys
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fmes.main import run


class MainReportingPackTests(unittest.TestCase):
    def test_run_writes_reporting_pack_when_output_dir_is_provided(self):
        schedule_result = {
            "export_blocks": {},
            "melt_schedule": {1: {"rows": pd.DataFrame()}},
            "pour_day_dates": {1: {"date": pd.Timestamp("2026-08-04"), "weekday": "Tuesday"}},
            "job_shipping_rows": [],
            "mold_schedule_frame": pd.DataFrame(),
            "mold_day_dates": {},
        }

        with patch("fmes.main.schedule_molds", return_value=schedule_result), \
             patch("fmes.main.export_combined_schedule_workbook"), \
             patch("fmes.main.write_reporting_pack", return_value={"output_dir": "C:/tmp/report-pack"}) as write_reporting_pack:
            result = run(output_file="combined.xlsx", report_pack_dir="C:/tmp/report-pack")

        self.assertIsNotNone(result["report_pack"])
        write_reporting_pack.assert_called_once()

    def test_run_sends_email_when_enabled(self):
        schedule_result = {
            "export_blocks": {},
            "melt_schedule": {1: {"rows": pd.DataFrame()}},
            "pour_day_dates": {1: {"date": pd.Timestamp("2026-08-04"), "weekday": "Tuesday"}},
            "job_shipping_rows": [],
            "mold_schedule_frame": pd.DataFrame(),
            "mold_day_dates": {},
        }

        with patch("fmes.main.schedule_molds", return_value=schedule_result), \
             patch("fmes.main.export_combined_schedule_workbook"), \
             patch("fmes.main.write_reporting_pack", return_value={"output_dir": "C:/tmp/report-pack", "distribution_manifest": "C:/tmp/report-pack/distribution_manifest.json"}), \
             patch("fmes.main.send_report_pack_email", return_value={"recipient_count": 1, "recipients": ["lburkardt@monettmetals.com"]}) as send_report_pack_email:
            result = run(
                output_file="combined.xlsx",
                report_pack_dir="C:/tmp/report-pack",
                send_report_email=True,
                email_test_recipient="lburkardt@monettmetals.com",
                email_audiences="production",
                email_transport="outlook",
            )

        self.assertIsNotNone(result["email"])
        send_report_pack_email.assert_called_once()
        self.assertEqual(send_report_pack_email.call_args.kwargs["transport"], "outlook")


if __name__ == "__main__":
    unittest.main()
