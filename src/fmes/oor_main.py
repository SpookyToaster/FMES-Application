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
        "--report-pack-dir",
        default=None,
        help="Optional output directory for reporting pack artifacts (CSV + JSON).",
    )
    parser.add_argument(
        "--send-report-email",
        action="store_true",
        help="Send report-pack artifacts by configured email transport after run completion.",
    )
    parser.add_argument(
        "--email-test-recipient",
        default=None,
        help="Single recipient email for test sends (overrides manifest recipients).",
    )
    parser.add_argument(
        "--email-audiences",
        default=None,
        help="Comma-separated audiences to send (defaults to all in manifest).",
    )
    parser.add_argument(
        "--email-transport",
        choices=["smtp", "outlook"],
        default=None,
        help="Email transport override (smtp or outlook).",
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
        result = run(
            output_file=args.output_file,
            report_pack_dir=args.report_pack_dir,
            send_report_email=args.send_report_email,
            email_test_recipient=args.email_test_recipient,
            email_audiences=args.email_audiences,
            email_transport=args.email_transport,
        )

        logger.info("=" * 60)
        logger.info("OOR-only scheduler run complete.")
        logger.info("Combined schedule workbook: %s", result["combined_output_file"])
        logger.info("Production days scheduled: %s", result["day_block_count"])
        if result.get("report_pack"):
            logger.info("Reporting pack directory: %s", result["report_pack"]["output_dir"])
        if result.get("email"):
            logger.info("Email recipients: %s", ", ".join(result["email"]["recipients"]))
        logger.info("=" * 60)
    except Exception:
        logger.exception("OOR-only scheduler run FAILED.")
        exit_code = 1

    _pause_before_exit(args.no_pause)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
