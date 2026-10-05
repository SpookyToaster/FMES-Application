"""Load per-user settings before importing application modules."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def local_config_path() -> Path:
    """Return the per-user .env path outside the repository and shared drive."""
    local_app_data = os.getenv("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError("LOCALAPPDATA is not set; cannot locate the FMES local config file.")
    return Path(local_app_data) / "FMES Scheduler" / ".env"


def load_local_config() -> bool:
    """Load per-user settings, overriding inherited account environment values."""
    return load_dotenv(dotenv_path=local_config_path(), override=True)
