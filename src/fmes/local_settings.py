"""Per-user non-secret FMES settings."""

import json
import os
from pathlib import Path
import tempfile

from .local_config import local_config_path


DEFAULT_EMAIL_RECIPIENTS = (
    "sliles@monettmetals.com",
    "BRaub@monettmetals.com",
    "lburkardt@monettmetals.com",
)


def local_settings_path() -> Path:
    """Return the path for writable per-user settings, separate from credentials."""
    return local_config_path().with_name("settings.json")


def load_email_recipients(settings_file: str | Path | None = None) -> list[str]:
    """Load persisted recipients, or built-in defaults when no settings file exists."""
    path = Path(settings_file) if settings_file else local_settings_path()
    if not path.exists():
        return list(DEFAULT_EMAIL_RECIPIENTS)

    try:
        with path.open("r", encoding="utf-8") as handle:
            settings = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read FMES user settings from {path}.") from exc

    recipients = settings.get("email_recipients") if isinstance(settings, dict) else None
    if not isinstance(recipients, list) or any(not isinstance(item, str) for item in recipients):
        raise RuntimeError(
            f"FMES user settings at {path} must contain an email_recipients list."
        )

    return list(dict.fromkeys(item.strip() for item in recipients if item.strip()))


def save_email_recipients(
    recipients: list[str],
    settings_file: str | Path | None = None,
) -> None:
    """Atomically save a non-secret recipient list in per-user settings."""
    normalized = list(dict.fromkeys(item.strip() for item in recipients if item.strip()))
    path = Path(settings_file) if settings_file else local_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump({"email_recipients": normalized}, handle, indent=2)
            handle.write("\n")
        os.replace(temporary_path, path)
    except OSError as exc:
        raise OSError(f"Could not save FMES user settings to {path}.") from exc
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
