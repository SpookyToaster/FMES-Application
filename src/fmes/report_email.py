"""Email delivery helpers for FMES report packs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
import json
import mimetypes
import os
from pathlib import Path
import smtplib


@dataclass
class SmtpSettings:
    """SMTP settings loaded from environment variables."""

    host: str
    port: int
    from_address: str
    username: str
    password: str
    use_starttls: bool


def _parse_bool(raw_value: str | None, default: bool) -> bool:
    """Parse bool-like environment values with a default fallback."""
    if raw_value is None:
        return default

    normalized = str(raw_value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def load_smtp_settings_from_env() -> SmtpSettings:
    """Load SMTP settings from environment variables and validate required values."""
    host = os.getenv("FMES_SMTP_HOST", "").strip()
    if not host:
        raise RuntimeError("FMES_SMTP_HOST is required to send report emails.")

    from_address = os.getenv("FMES_SMTP_FROM", "").strip()
    if not from_address:
        raise RuntimeError("FMES_SMTP_FROM is required to send report emails.")

    raw_port = os.getenv("FMES_SMTP_PORT", "587").strip()
    try:
        port = int(raw_port)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("FMES_SMTP_PORT must be a valid integer.") from exc

    username = os.getenv("FMES_SMTP_USERNAME", "").strip()
    password = os.getenv("FMES_SMTP_PASSWORD", "")

    if username and not password:
        raise RuntimeError(
            "FMES_SMTP_PASSWORD is required when FMES_SMTP_USERNAME is provided."
        )

    use_starttls = _parse_bool(os.getenv("FMES_SMTP_USE_STARTTLS"), default=True)

    return SmtpSettings(
        host=host,
        port=port,
        from_address=from_address,
        username=username,
        password=password,
        use_starttls=use_starttls,
    )


def _load_manifest(path: str | Path) -> dict:
    """Load report-pack distribution manifest JSON."""
    manifest_path = Path(path)
    if not manifest_path.exists():
        raise RuntimeError(f"Distribution manifest not found at {manifest_path}")

    with manifest_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _normalize_audiences(requested_audiences: str | None, manifest: dict) -> list[str]:
    """Resolve requested audiences or default to all enabled audiences."""
    configured = [
        str(item.get("audience", "")).strip()
        for item in manifest.get("audiences", [])
        if str(item.get("audience", "")).strip()
    ]

    if not requested_audiences:
        return configured

    requested = [value.strip() for value in requested_audiences.split(",") if value.strip()]
    unknown = sorted(set(requested) - set(configured))
    if unknown:
        raise RuntimeError(
            "Unknown email audience(s): " + ", ".join(unknown)
        )

    return requested


def _resolve_attachments_and_recipients(manifest: dict, audiences: list[str]) -> tuple[list[str], list[str]]:
    """Return unique attachment paths and recipient addresses for selected audiences."""
    attachment_paths: list[str] = []
    recipients: list[str] = []

    for audience in manifest.get("audiences", []):
        audience_name = str(audience.get("audience", "")).strip()
        if audience_name not in audiences:
            continue
        if not bool(audience.get("enabled", True)):
            continue

        for attachment in audience.get("attachments", []):
            candidate = str(attachment).strip()
            if candidate and candidate not in attachment_paths:
                attachment_paths.append(candidate)

        for recipient in audience.get("recipients", []):
            candidate = str(recipient).strip()
            if candidate and candidate not in recipients:
                recipients.append(candidate)

    return attachment_paths, recipients


def _build_email_message(
    from_address: str,
    recipients: list[str],
    schedule_source: str,
    selected_audiences: list[str],
    attachment_paths: list[str],
) -> EmailMessage:
    """Build an email message with report-pack attachments."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    subject = f"FMES Report Pack | {timestamp}"

    body_lines = [
        "FMES report pack generated.",
        "",
        f"Source: {schedule_source.upper()}",
        f"Audiences: {', '.join(selected_audiences) if selected_audiences else 'none'}",
        f"Attachment count: {len(attachment_paths)}",
    ]

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_address
    message["To"] = ", ".join(recipients)
    message.set_content("\n".join(body_lines))

    for attachment_path in attachment_paths:
        file_path = Path(attachment_path)
        if not file_path.exists():
            continue

        mime_type, _ = mimetypes.guess_type(file_path.name)
        if mime_type:
            maintype, subtype = mime_type.split("/", 1)
        else:
            maintype, subtype = "application", "octet-stream"

        with file_path.open("rb") as handle:
            message.add_attachment(
                handle.read(),
                maintype=maintype,
                subtype=subtype,
                filename=file_path.name,
            )

    return message


def send_report_pack_email(
    report_pack_result: dict,
    schedule_source: str,
    requested_audiences: str | None = None,
    test_recipient: str | None = None,
) -> dict:
    """Send report-pack artifacts by email via SMTP.

    When test_recipient is provided, all selected audience attachments are sent to
    that single recipient regardless of manifest recipient lists.
    """
    manifest = _load_manifest(report_pack_result.get("distribution_manifest", ""))
    selected_audiences = _normalize_audiences(requested_audiences, manifest)
    attachment_paths, recipients = _resolve_attachments_and_recipients(manifest, selected_audiences)

    if test_recipient:
        recipients = [str(test_recipient).strip()]

    if not recipients:
        raise RuntimeError(
            "No email recipients resolved. Provide --email-test-recipient or add recipients in distribution_manifest.json."
        )

    if not attachment_paths:
        raise RuntimeError("No report-pack attachments resolved for the selected audiences.")

    smtp_settings = load_smtp_settings_from_env()
    message = _build_email_message(
        from_address=smtp_settings.from_address,
        recipients=recipients,
        schedule_source=schedule_source,
        selected_audiences=selected_audiences,
        attachment_paths=attachment_paths,
    )

    with smtplib.SMTP(smtp_settings.host, smtp_settings.port) as smtp:
        smtp.ehlo()
        if smtp_settings.use_starttls:
            smtp.starttls()
            smtp.ehlo()
        if smtp_settings.username:
            smtp.login(smtp_settings.username, smtp_settings.password)
        smtp.send_message(message)

    return {
        "recipient_count": len(recipients),
        "recipients": recipients,
        "audiences": selected_audiences,
        "attachment_count": len(attachment_paths),
        "attachments": attachment_paths,
    }
