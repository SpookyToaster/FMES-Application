"""OOR-only CLI entrypoint for FMES schedule generation."""

import argparse
import logging
import os

from .main import DEFAULT_MOLD_OUTPUT, _pause_before_exit, run, setup_logging


logger = logging.getLogger(__name__)


def parse_args():
    """Parse CLI args for OOR-only schedule generation."""
    parser = argparse.ArgumentParser(
        description=(
            "Build the schedule from the existing Open Order Report workbook "
            "without SQL synchronization."
        )
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


def main():
    """Run scheduler in OOR-only mode (forces Excel input source)."""
    setup_logging()
    args = parse_args()

    # Force Excel/OOR input so SQL sync and DB validation are skipped.
    os.environ["SCHEDULER_INPUT_SOURCE"] = "excel"

    exit_code = 0
    try:
        result = run(output_file=args.output_file)

        logger.info("=" * 60)
        logger.info("OOR-only scheduler run complete.")
        logger.info("Combined schedule workbook: %s", result["combined_output_file"])
        logger.info("Production days scheduled: %s", result["day_block_count"])
        logger.info("=" * 60)
    except Exception:
        logger.exception("OOR-only scheduler run FAILED.")
        exit_code = 1

    _pause_before_exit(args.no_pause)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
