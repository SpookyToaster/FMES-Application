import sys
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fmes import main


class HeatScheduleMainTests(unittest.TestCase):
    def test_run_heat_schedule_exports_only_heat_workbook(self):
        schedule_result = {
            "export_blocks": {
                1: {
                    "date": pd.Timestamp("2026-08-11"),
                    "weekday": "Tuesday",
                    "rows": pd.DataFrame(),
                    "weight_total": 0,
                    "mold_total": 0,
                }
            },
            "melt_schedule": {1: {"heat_summary": pd.DataFrame()}},
            "mold_schedule_frame": pd.DataFrame(),
            "mold_day_dates": {
                1: {"date": pd.Timestamp("2026-08-10"), "weekday": "Monday"}
            },
            "pour_day_dates": {
                1: {"date": pd.Timestamp("2026-08-11"), "weekday": "Tuesday"}
            },
        }

        with patch.dict("os.environ", {"SCHEDULER_INPUT_SOURCE": "sql"}, clear=False), \
             patch("fmes.main.validate_database_environment") as validate_database_environment, \
             patch("fmes.main.schedule_molds", return_value=schedule_result), \
               patch("fmes.main.export_heat_summary") as export_heat_summary:
            result = main.run_heat_schedule("heat_only.xlsx")

        validate_database_environment.assert_called_once_with()
        export_heat_summary.assert_called_once_with(
            schedule_result["melt_schedule"],
            schedule_result["pour_day_dates"],
            "heat_only.xlsx",
            mold_schedule_frame=schedule_result["mold_schedule_frame"],
            mold_day_dates=schedule_result["mold_day_dates"],
        )
        self.assertEqual(result["heat_output_file"], "heat_only.xlsx")
        self.assertEqual(result["day_block_count"], 1)

    def test_run_heat_schedule_skips_database_validation_for_excel_source(self):
        schedule_result = {
            "export_blocks": {},
            "melt_schedule": {},
            "mold_schedule_frame": pd.DataFrame(),
            "mold_day_dates": {},
            "pour_day_dates": {},
        }

        with patch.dict("os.environ", {"SCHEDULER_INPUT_SOURCE": "excel"}, clear=False), \
             patch("fmes.main.validate_database_environment") as validate_database_environment, \
             patch("fmes.main.schedule_molds", return_value=schedule_result), \
             patch("fmes.main.export_heat_summary"):
            result = main.run_heat_schedule("heat_only.xlsx")

        validate_database_environment.assert_not_called()
        self.assertEqual(result["day_block_count"], 0)


if __name__ == "__main__":
    unittest.main()