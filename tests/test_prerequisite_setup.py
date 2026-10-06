import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from installer.setup_fmes import ensure_local_config, local_config_path
from fmes.email_prompt import (
    _valid_email_address,
)
from fmes.local_settings import (
    DEFAULT_EMAIL_RECIPIENTS,
    load_email_recipients,
    local_settings_path,
    save_email_recipients,
)


class PrerequisiteSetupTests(unittest.TestCase):
    def test_local_config_path_uses_local_app_data(self):
        self.assertEqual(
            local_config_path(r"C:\Users\Operator\AppData\Local"),
            Path(r"C:\Users\Operator\AppData\Local\FMES Scheduler\.env"),
        )

    def test_local_settings_path_is_separate_from_credentials(self):
        self.assertEqual(
            local_settings_path(),
            local_config_path().with_name("settings.json"),
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

    def test_missing_settings_uses_builtin_recipient_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(
                load_email_recipients(Path(directory) / "settings.json"),
                list(DEFAULT_EMAIL_RECIPIENTS),
            )

    def test_recipient_settings_save_and_load_without_touching_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            config_path = folder / ".env"
            settings_path = folder / "settings.json"
            config_path.write_text("DB_PASSWORD=keep-this\n", encoding="utf-8")

            save_email_recipients(
                ["one@example.com", "two@example.com", "one@example.com"],
                settings_file=settings_path,
            )

            self.assertEqual(
                load_email_recipients(settings_path),
                ["one@example.com", "two@example.com"],
            )
            self.assertEqual(config_path.read_text(encoding="utf-8"), "DB_PASSWORD=keep-this\n")
            self.assertEqual(
                settings_path.read_text(encoding="utf-8"),
                '{\n  "email_recipients": [\n    "one@example.com",\n    "two@example.com"\n  ]\n}\n',
            )

    def test_empty_recipient_list_can_be_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "settings.json"
            save_email_recipients([], settings_file=settings_path)
            self.assertEqual(load_email_recipients(settings_path), [])

    def test_invalid_recipient_settings_raise_clear_error(self):
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "settings.json"
            settings_path.write_text('{"email_recipients": "not-a-list"}', encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "must contain an email_recipients list"):
                load_email_recipients(settings_path)

    def test_malformed_recipient_settings_raise_clear_error(self):
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "settings.json"
            settings_path.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Could not read FMES user settings"):
                load_email_recipients(settings_path)

    def test_recipient_address_validation(self):
        self.assertTrue(_valid_email_address("user@example.com"))
        self.assertFalse(_valid_email_address("not-an-email"))
        self.assertFalse(_valid_email_address("user @example.com"))


if __name__ == "__main__":
    unittest.main()
