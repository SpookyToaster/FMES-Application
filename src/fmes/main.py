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
from .report_email import send_report_pack_email
from .report_pack import write_reporting_pack
from .scheduler import schedule_molds
from .scheduler_export import export_combined_schedule_workbook


logger = logging.getLogger(__name__)

DEFAULT_MOLD_OUTPUT = str(Paths.COMBINED_SCHEDULE_OUTPUT)
DEFAULT_REPORT_PACK_OUTPUT = str(Paths.REPORT_PACK_DIR)


def _resolve_schedule_source():
    """Return the configured scheduler input source."""
    return os.getenv("SCHEDULER_INPUT_SOURCE", "sql").strip().lower()


def _parse_bool(raw_value: str | None, default: bool) -> bool:
    """Parse bool-like string values with default fallback."""
    if raw_value is None:
        return default

    normalized = str(raw_value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def resolve_send_report_email(send_report_email_flag: bool) -> bool:
    """Resolve whether report-pack email should be sent for this run.

    Priority order:
    1) Explicit CLI flag --send-report-email
    2) FMES_SEND_REPORT_EMAIL environment variable
    3) Default True when running as frozen executable, otherwise False
    """
    if send_report_email_flag:
        return True

    env_default = os.getenv("FMES_SEND_REPORT_EMAIL")
    if env_default is not None:
        return _parse_bool(env_default, default=False)

    return bool(getattr(sys, "frozen", False))


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
        "--report-pack-dir",
        default=None,
        help=(
            "Optional output directory for production visibility/report-pack artifacts "
            "(CSV + JSON)."
        ),
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


def run(
    output_file=DEFAULT_MOLD_OUTPUT,
    report_pack_dir=None,
    send_report_email=False,
    email_test_recipient=None,
    email_audiences=None,
    email_transport=None,
):
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
        mold_input_diagnostics_rows=schedule_result.get("mold_input_diagnostics_rows", []),
    )
    logger.info("      Saved: %s", output_file)

    report_pack_result = None
    if report_pack_dir or send_report_email:
        effective_report_pack_dir = report_pack_dir or DEFAULT_REPORT_PACK_OUTPUT
        logger.info("[5/5] Writing reporting pack artifacts...")
        report_pack_result = write_reporting_pack(
            schedule_result=schedule_result,
            output_dir=effective_report_pack_dir,
        )
        logger.info("      Reporting pack: %s", report_pack_result["output_dir"])

    email_result = None
    if send_report_email:
        logger.info("[6/6] Sending report-pack email...")
        email_result = send_report_pack_email(
            report_pack_result=report_pack_result,
            schedule_source=schedule_source,
            requested_audiences=email_audiences,
            test_recipient=email_test_recipient,
            transport=email_transport,
        )
        logger.info(
            "      Email sent to %s recipient(s): %s",
            email_result["recipient_count"],
            ", ".join(email_result["recipients"]),
        )

    return {
        "combined_output_file": output_file,
        "day_block_count": len(export_blocks),
        "report_pack": report_pack_result,
        "email": email_result,
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
        send_report_email = resolve_send_report_email(args.send_report_email)

        report_pack_dir = args.report_pack_dir
        if isinstance(report_pack_dir, str) and report_pack_dir.strip().lower() == "default":
            report_pack_dir = DEFAULT_REPORT_PACK_OUTPUT

        email_test_recipient = args.email_test_recipient
        if isinstance(email_test_recipient, str):
            email_test_recipient = email_test_recipient.strip() or None
        if not email_test_recipient:
            email_test_recipient = os.getenv("FMES_EMAIL_TEST_RECIPIENT", "").strip() or None

        result = run(
            output_file=args.output_file,
            report_pack_dir=report_pack_dir,
            send_report_email=send_report_email,
            email_test_recipient=email_test_recipient,
            email_audiences=args.email_audiences,
            email_transport=args.email_transport,
        )

        logger.info("=" * 60)
        logger.info("Scheduler run complete.")
        logger.info("Combined schedule workbook: %s", result["combined_output_file"])
        logger.info("Production days scheduled: %s", result["day_block_count"])
        if result.get("report_pack"):
            logger.info("Reporting pack directory: %s", result["report_pack"]["output_dir"])
        if result.get("email"):
            logger.info("Email recipients: %s", ", ".join(result["email"]["recipients"]))
        logger.info("=" * 60)
    except Exception:
        logger.exception("Scheduler run FAILED.")
        logger.error("See the log file under %s for details.", Paths.LOG_DIR)
        exit_code = 1

    _pause_before_exit(args.no_pause)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
