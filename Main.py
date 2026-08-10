"""
Application entrypoint for Foundry Management and Execution System (FMES).

Main.py provides one command that runs the full end-to-end flow:
  1) Validate DB settings when SQL source is used.
  2) Sync SQL data into Open Order Report artifacts (handled inside Scheduler).
  3) Build mold schedule blocks.
  4) Export Mold Schedule and Heat Summary workbooks.
"""

import argparse
import os

from config import Paths
from Database import validate_database_environment
from Scheduler import schedule_molds
from scheduler_export import export_heat_summary, export_mold_schedule


DEFAULT_MOLD_OUTPUT = str(Paths.MOLD_SCHEDULE_OUTPUT)

DEFAULT_HEAT_OUTPUT = str(Paths.HEAT_SUMMARY_OUTPUT)


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
    return parser.parse_args()


def run(output_file=DEFAULT_MOLD_OUTPUT, heat_output_file=DEFAULT_HEAT_OUTPUT):
    """
    Execute full scheduler run and export workbooks.

    Returns:
        dict with output file paths and number of day blocks exported.
    """
    schedule_source = os.getenv("SCHEDULER_INPUT_SOURCE", "sql").strip().lower()

    if schedule_source == "sql":
        validate_database_environment()

    export_blocks = schedule_molds()
    export_mold_schedule(export_blocks, output_file)
    export_heat_summary(export_blocks, heat_output_file)

    return {
        "mold_output_file": output_file,
        "heat_output_file": heat_output_file,
        "day_block_count": len(export_blocks),
    }


def main():
    """CLI entrypoint."""
    args = parse_args()

    if args.source:
        os.environ["SCHEDULER_INPUT_SOURCE"] = args.source

    result = run(
        output_file=args.output_file,
        heat_output_file=args.heat_output_file,
    )

    print("Scheduler run complete.")
    print(f"Mold schedule: {result['mold_output_file']}")
    print(f"Heat summary: {result['heat_output_file']}")
    print(f"Day blocks exported: {result['day_block_count']}")


if __name__ == "__main__":
    main()
