"""
Application entrypoint for Foundry Management and Execution System (FMES).

Main.py provides one command that runs the full end-to-end flow:
  1) Validate DB settings when SQL source is used.
  2) Sync SQL data into Open Order Report artifacts (handled inside Scheduler).
  3) Build mold schedule blocks.
  4) Export Mold Schedule and Heat Summary workbooks.
"""

import argparse
import logging
import os
import sys
from datetime import datetime

from .config import Paths
from .database import validate_database_environment
from .scheduler import schedule_molds
from .scheduler_export import export_heat_summary, export_mold_schedule


logger = logging.getLogger(__name__)

DEFAULT_MOLD_OUTPUT = str(Paths.MOLD_SCHEDULE_OUTPUT)

DEFAULT_HEAT_OUTPUT = str(Paths.HEAT_SUMMARY_OUTPUT)


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
        help="Output path for Mold Schedule workbook.",
    )
    parser.add_argument(
        "--heat-output-file",
        default=DEFAULT_HEAT_OUTPUT,
        help="Output path for Heat Summary workbook.",
    )
    parser.add_argument(
        "--no-pause",
        action="store_true",
        help="Exit immediately instead of waiting for Enter (for automation).",
    )
    return parser.parse_args()


def run(output_file=DEFAULT_MOLD_OUTPUT, heat_output_file=DEFAULT_HEAT_OUTPUT):
    """
    Execute full scheduler run and export workbooks.

    Returns:
        dict with output file paths and number of day blocks exported.
    """
    schedule_source = os.getenv("SCHEDULER_INPUT_SOURCE", "sql").strip().lower()

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

    logger.info("[3/4] Writing Mold Schedule workbook...")
    export_mold_schedule(export_blocks, output_file)
    logger.info("      Saved: %s", output_file)

    logger.info("[4/4] Writing Heat Summary workbook...")
    export_heat_summary(
        schedule_result["melt_schedule"],
        schedule_result["day_dates"],
        heat_output_file,
    )
    logger.info("      Saved: %s", heat_output_file)

    return {
        "mold_output_file": output_file,
        "heat_output_file": heat_output_file,
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
        result = run(
            output_file=args.output_file,
            heat_output_file=args.heat_output_file,
        )

        logger.info("=" * 60)
        logger.info("Scheduler run complete.")
        logger.info("Mold schedule: %s", result["mold_output_file"])
        logger.info("Heat summary: %s", result["heat_output_file"])
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
