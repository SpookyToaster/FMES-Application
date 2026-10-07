import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fmes import config, local_config


class SchedulePathTests(unittest.TestCase):
    def test_default_schedule_root_uses_fmes_network_folder(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(config._resolve_schedule_root(), Path("S:/FMES"))

    def test_schedule_root_environment_override_is_honored(self):
        with patch.dict(os.environ, {"FMES_SCHEDULE_ROOT": r"R:\Schedules"}, clear=True):
            self.assertEqual(config._resolve_schedule_root(), Path(r"R:\Schedules"))

    def test_unc_schedule_root_environment_override_is_honored(self):
        with patch.dict(
            os.environ,
            {"FMES_SCHEDULE_ROOT": r"\\fileserver\production\FMES"},
            clear=True,
        ):
            self.assertEqual(
                config._resolve_schedule_root(),
                Path(r"\\fileserver\production\FMES"),
            )

    def test_default_paths_use_input_and_output_folders(self):
        root = config.SCHEDULE_ROOT
        self.assertEqual(config.Paths.OPEN_ORDER_REPORT, root / "Input_Files" / "Open Order Report.xlsx")
        self.assertEqual(config.Paths.SHIPPING_TABLE_WORKBOOK, root / "Input_Files" / "Shipping Table.xlsx")
        self.assertEqual(config.Paths.COMBINED_SCHEDULE_OUTPUT, root / "Output_Files" / "Production Schedule Summary.xlsx")
        self.assertEqual(config.Paths.REPORT_PACK_DIR, root / "Output_Files" / "Report Pack")


class LocalConfigTests(unittest.TestCase):
    def test_local_config_requires_local_app_data(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "LOCALAPPDATA is not set"):
                local_config.local_config_path()

    def test_local_config_uses_user_local_app_data(self):
        with patch.dict(
            os.environ,
            {"LOCALAPPDATA": r"C:\Users\Operator\AppData\Local"},
            clear=True,
        ):
            self.assertEqual(
                local_config.local_config_path(),
                Path(r"C:\Users\Operator\AppData\Local\FMES Scheduler\.env"),
            )

    def test_local_env_overrides_account_environment(self):
        with patch("fmes.local_config.load_dotenv", return_value=True) as load_dotenv:
            self.assertTrue(local_config.load_local_config())

        load_dotenv.assert_called_once_with(
            dotenv_path=local_config.local_config_path(),
            override=True,
        )


if __name__ == "__main__":
    unittest.main()
