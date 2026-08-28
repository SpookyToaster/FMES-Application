import json
import os
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fmes.report_email import (
    load_smtp_settings_from_env,
    send_report_pack_email,
)


class _FakeSmtp:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.started_tls = False
        self.logged_in = False
        self.sent_message = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def ehlo(self):
        return None

    def starttls(self):
        self.started_tls = True

    def login(self, username, password):
        self.logged_in = True

    def send_message(self, message):
        self.sent_message = message


class ReportEmailTests(unittest.TestCase):
    def test_load_smtp_settings_requires_host_and_from(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                load_smtp_settings_from_env()

    def test_send_report_pack_email_uses_test_recipient(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            a = temp_path / "a.csv"
            b = temp_path / "b.json"
            a.write_text("x\n1\n", encoding="utf-8")
            b.write_text("{}", encoding="utf-8")

            manifest = {
                "audiences": [
                    {
                        "audience": "production",
                        "enabled": True,
                        "recipients": ["prod@monettmetals.com"],
                        "attachments": [str(a), str(b)],
                    }
                ]
            }
            manifest_path = temp_path / "distribution_manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            report_pack_result = {"distribution_manifest": str(manifest_path)}
            fake_smtp = _FakeSmtp("smtp.example.com", 587)

            env = {
                "FMES_SMTP_HOST": "smtp.example.com",
                "FMES_SMTP_PORT": "587",
                "FMES_SMTP_FROM": "fmes@monettmetals.com",
                "FMES_SMTP_USE_STARTTLS": "1",
            }

            with patch.dict(os.environ, env, clear=False), patch("fmes.report_email.smtplib.SMTP", return_value=fake_smtp):
                result = send_report_pack_email(
                    report_pack_result=report_pack_result,
                    schedule_source="sql",
                    requested_audiences="production",
                    test_recipient="lburkardt@monettmetals.com",
                    transport="smtp",
                )

            self.assertEqual(result["recipient_count"], 1)
            self.assertEqual(result["recipients"], ["lburkardt@monettmetals.com"])
            self.assertEqual(result["attachment_count"], 2)
            self.assertTrue(fake_smtp.started_tls)
            self.assertIsNotNone(fake_smtp.sent_message)

    def test_send_report_pack_email_requires_recipients_without_test_override(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            attachment = temp_path / "a.csv"
            attachment.write_text("x\n1\n", encoding="utf-8")

            manifest = {
                "audiences": [
                    {
                        "audience": "production",
                        "enabled": True,
                        "recipients": [],
                        "attachments": [str(attachment)],
                    }
                ]
            }
            manifest_path = temp_path / "distribution_manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            env = {
                "FMES_SMTP_HOST": "smtp.example.com",
                "FMES_SMTP_PORT": "587",
                "FMES_SMTP_FROM": "fmes@monettmetals.com",
            }

            with patch.dict(os.environ, env, clear=False):
                with self.assertRaises(RuntimeError):
                    send_report_pack_email(
                        report_pack_result={"distribution_manifest": str(manifest_path)},
                        schedule_source="excel",
                        requested_audiences="production",
                    )

    def test_send_report_pack_email_uses_outlook_transport(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            attachment = temp_path / "report.csv"
            attachment.write_text("x\n1\n", encoding="utf-8")

            manifest = {
                "audiences": [
                    {
                        "audience": "production",
                        "enabled": True,
                        "recipients": ["prod@monettmetals.com"],
                        "attachments": [str(attachment)],
                    }
                ]
            }
            manifest_path = temp_path / "distribution_manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with patch("fmes.report_email._send_via_outlook") as send_outlook:
                result = send_report_pack_email(
                    report_pack_result={"distribution_manifest": str(manifest_path)},
                    schedule_source="excel",
                    requested_audiences="production",
                    test_recipient="lburkardt@monettmetals.com",
                    transport="outlook",
                )

            self.assertEqual(result["transport"], "outlook")
            self.assertEqual(result["recipient_count"], 1)
            send_outlook.assert_called_once()

    def test_send_report_pack_email_rejects_unknown_transport(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            attachment = temp_path / "report.csv"
            attachment.write_text("x\n1\n", encoding="utf-8")

            manifest = {
                "audiences": [
                    {
                        "audience": "production",
                        "enabled": True,
                        "recipients": ["prod@monettmetals.com"],
                        "attachments": [str(attachment)],
                    }
                ]
            }
            manifest_path = temp_path / "distribution_manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaises(RuntimeError):
                send_report_pack_email(
                    report_pack_result={"distribution_manifest": str(manifest_path)},
                    schedule_source="excel",
                    requested_audiences="production",
                    transport="invalid",
                )

    def test_send_report_pack_email_defaults_to_outlook_transport(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            attachment = temp_path / "report.csv"
            attachment.write_text("x\n1\n", encoding="utf-8")

            manifest = {
                "audiences": [
                    {
                        "audience": "production",
                        "enabled": True,
                        "recipients": ["prod@monettmetals.com"],
                        "attachments": [str(attachment)],
                    }
                ]
            }
            manifest_path = temp_path / "distribution_manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True), patch("fmes.report_email._send_via_outlook") as send_outlook:
                result = send_report_pack_email(
                    report_pack_result={"distribution_manifest": str(manifest_path)},
                    schedule_source="excel",
                    test_recipient="lburkardt@monettmetals.com",
                )

            self.assertEqual(result["transport"], "outlook")
            send_outlook.assert_called_once()


if __name__ == "__main__":
    unittest.main()
