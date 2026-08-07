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

from Database import validate_database_environment
from Scheduler import Schedule_Molds
from scheduler_export import Export_Heat_Summary, Export_Mold_Schedule


DEFAULT_MOLD_OUTPUT = (
    r"C:\Users\lburkardt\OneDrive - MonettMetalsUS1"
    r"\Quality\Schedule\Output\Mold Schedule.xlsx"
)

DEFAULT_HEAT_OUTPUT = (
    r"C:\Users\lburkardt\OneDrive - MonettMetalsUS1"
    r"\Quality\Schedule\Output\Heat Summary.xlsx"
)


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
        "--run-id",
        type=int,
        default=None,
        help="Optional Scheduler run id (used when source=sql and history tables exist).",
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

    export_blocks = Schedule_Molds()
    Export_Mold_Schedule(export_blocks, output_file)
    Export_Heat_Summary(export_blocks, heat_output_file)

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

    if args.run_id is not None:
        os.environ["SCHEDULER_RUN_ID"] = str(args.run_id)

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
