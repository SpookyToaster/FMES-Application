"""
Application entrypoint for Foundry Management and Execution System (FMES).

This module provides the primary command that runs the current end-to-end flow:
  1) Validate DB settings when SQL source is used.
  2) Sync SQL data into Open Order Report artifacts (handled inside Scheduler).
    3) Build mold and melt schedule data.
    4) Export Production Schedule Summary workbook.
"""

import argparse
import logging
import os
import sys
from datetime import datetime

from .config import Paths
from .database import validate_database_environment
from .scheduler import schedule_molds
from .scheduler_export import export_combined_schedule_workbook


logger = logging.getLogger(__name__)

DEFAULT_MOLD_OUTPUT = str(Paths.COMBINED_SCHEDULE_OUTPUT)


def _resolve_schedule_source():
    """Return the configured scheduler input source."""
    return os.getenv("SCHEDULER_INPUT_SOURCE", "sql").strip().lower()


def setup_logging():
    """Console shows plain readable messages; the monthly file keeps full detail."""
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    handlers = [console_handler]

    try:
        Paths.LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = Paths.LOG_DIR / f"fmes_{datetime.now():%Y-%m}.log"
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        handlers.append(file_handler)
    except OSError:
        pass  # Console-only logging when the shared folder is unavailable.

    logging.basicConfig(level=logging.INFO, handlers=handlers)


def parse_args():
    """Parse CLI args for source/run control and output locations."""
    parser = argparse.ArgumentParser(
        description="Run full FMES workflow from DB/Excel source through export."
    )
    parser.add_argument(
        "--source",
        choices=["sql", "excel"],
        default=None,
        help="Input source override (defaults to SCHEDULER_INPUT_SOURCE or sql).",
    )
    parser.add_argument(
        "--output-file",
        default=DEFAULT_MOLD_OUTPUT,
        help="Output path for combined schedule workbook.",
    )
    parser.add_argument(
        "--no-pause",
        action="store_true",
        help="Exit immediately instead of waiting for Enter (for automation).",
    )
    return parser.parse_args()


def run(output_file=DEFAULT_MOLD_OUTPUT):
    """
    Execute full scheduler run and export one combined workbook.

    Returns:
        dict with combined output file path and number of day blocks exported.
    """
    schedule_source = _resolve_schedule_source()

    logger.info("=" * 60)
    logger.info("FMES Scheduler starting (source: %s)", schedule_source.upper())
    logger.info("=" * 60)

    if schedule_source == "sql":
        logger.info("[1/4] Checking database configuration...")
        validate_database_environment()
        logger.info("      Database configuration OK.")
    else:
        logger.info("[1/4] Skipping database check (Excel source).")

    logger.info("[2/4] Building mold schedule...")
    schedule_result = schedule_molds()
    export_blocks = schedule_result["export_blocks"]

    logger.info("[3/4] Building combined workbook data...")
    logger.info("[4/4] Writing Combined Schedule workbook...")
    export_combined_schedule_workbook(
        export_blocks,
        schedule_result["melt_schedule"],
        schedule_result["pour_day_dates"],
        output_file,
        job_shipping_rows=schedule_result.get("job_shipping_rows", []),
        mold_schedule_frame=schedule_result.get("mold_schedule_frame", None),
        mold_day_dates=schedule_result.get("mold_day_dates", None),
    )
    logger.info("      Saved: %s", output_file)

    return {
        "combined_output_file": output_file,
        "day_block_count": len(export_blocks),
    }


def _pause_before_exit(no_pause):
    """Hold the console open for double-click exe runs so output stays visible."""
    if no_pause:
        return
    if not getattr(sys, "frozen", False):
        return
    try:
        input("\nPress Enter to close this window...")
    except EOFError:
        pass


def main():
    """CLI entrypoint."""
    setup_logging()
    args = parse_args()

    if args.source:
        os.environ["SCHEDULER_INPUT_SOURCE"] = args.source

    exit_code = 0
    try:
        result = run(output_file=args.output_file)

        logger.info("=" * 60)
        logger.info("Scheduler run complete.")
        logger.info("Combined schedule workbook: %s", result["combined_output_file"])
        logger.info("Production days scheduled: %s", result["day_block_count"])
        logger.info("=" * 60)
    except Exception:
        logger.exception("Scheduler run FAILED.")
        logger.error("See the log file under %s for details.", Paths.LOG_DIR)
        exit_code = 1

    _pause_before_exit(args.no_pause)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
