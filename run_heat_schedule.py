"""Launcher for the FMES heat-only scheduler (dev runs)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from fmes.main import heat_main


if __name__ == "__main__":
    raise SystemExit(heat_main())