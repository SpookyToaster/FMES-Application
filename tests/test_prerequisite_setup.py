import tempfile
import unittest
from pathlib import Path

from installer.setup_fmes import ensure_local_config, local_config_path


class PrerequisiteSetupTests(unittest.TestCase):
    def test_local_config_path_uses_local_app_data(self):
        self.assertEqual(
            local_config_path(r"C:\Users\Operator\AppData\Local"),
            Path(r"C:\Users\Operator\AppData\Local\FMES Scheduler\.env"),
        )

    def test_ensure_local_config_copies_template_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / ".env.example"
            config = root / "profile" / ".env"
            template.write_text("DB_NAME=example\n", encoding="utf-8")

            self.assertTrue(ensure_local_config(config, template))
            self.assertEqual(config.read_text(encoding="utf-8"), "DB_NAME=example\n")

            config.write_text("DB_NAME=private\n", encoding="utf-8")
            self.assertFalse(ensure_local_config(config, template))
            self.assertEqual(config.read_text(encoding="utf-8"), "DB_NAME=private\n")

    def test_ensure_local_config_reports_missing_template(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(FileNotFoundError):
                ensure_local_config(root / "profile" / ".env", root / "missing.env")


if __name__ == "__main__":
    unittest.main()
