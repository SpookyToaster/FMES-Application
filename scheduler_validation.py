"""Validation and audit helpers for FMES scheduler inputs."""

from datetime import datetime
from pathlib import Path

import pandas as pd


REQUIRED_SQL_TEXT_COLUMNS = [
    "Due Date",
    "Customer Name",
    "Part Number",
    "Job Number",
]

MISSING_JOB_ID_LOG_DIR = Path(
    r"C:\Users\lburkardt\OneDrive - MonettMetalsUS1\Quality\Schedule"
)
MISSING_JOB_ID_LOG_PREFIX = "Missing_Job_ID_Removals"
MISSING_JOB_ID_LOG_RETENTION_FILES = 12


def validate_sql_rows(rows, required_columns=REQUIRED_SQL_TEXT_COLUMNS):
    """
    Validate that SQL rows are complete enough for overwrite and scheduling.

    Raises RuntimeError with a concise defect summary when required fields are
    missing so bad joins/mappings do not silently create invalid schedules.
    """
    if not rows:
        raise RuntimeError(
            "SQL scheduler input validation failed. No rows were returned after SQL join/mapping. "
            "No matching Job Number keys were found between the source datasets."
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return rows

    issues = []
    for column_name in required_columns:
        if column_name not in frame.columns:
            issues.append(f"missing column: {column_name}")
            continue

        series = frame[column_name]
        invalid_mask = series.isna() | (series.astype(str).str.strip() == "")
        invalid_count = int(invalid_mask.sum())
        if invalid_count:
            sample_jobs = []
            if "Job Number" in frame.columns:
                sample_jobs = (
                    frame.loc[invalid_mask, "Job Number"]
                    .astype(str)
                    .head(5)
                    .tolist()
                )
            issues.append(
                f"{column_name}: {invalid_count} blank rows"
                + (f" (sample jobs: {', '.join(sample_jobs)})" if sample_jobs else "")
            )

    if issues:
        raise RuntimeError(
            "SQL scheduler input validation failed. The live query is returning incomplete rows: "
            + "; ".join(issues)
            + ". Provide the Power Query relationship/join logic so the SQL source can be mapped correctly."
        )

    return rows


def append_missing_job_id_audit(cursor, source_label):
    """Append a timestamped audit block for open-order rows missing job IDs."""
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM dbo.OEDetail d
        INNER JOIN dbo.OEHEader h
            ON h.ORDERNUMBER = d.ORDERNUMBER
        WHERE NULLIF(
            LTRIM(RTRIM(COALESCE(NULLIF(d.JOBNUMBER, ''), NULLIF(h.JOBNUMBER, '')))),
            ''
        ) IS NULL;
        """
    )
    missing_count = int(cursor.fetchone()[0])

    cursor.execute(
        """
        SELECT TOP (10)
            h.ORDERNUMBER AS OrderNumber,
            d.LINENUMBER AS LineNumber,
            h.CUSTOMERNAME AS CustomerName,
            d.PRODUCTNUMBER AS PartNumber,
            d.JOBNUMBER AS DetailJobNumber,
            h.JOBNUMBER AS HeaderJobNumber
        FROM dbo.OEDetail d
        INNER JOIN dbo.OEHEader h
            ON h.ORDERNUMBER = d.ORDERNUMBER
        WHERE NULLIF(
            LTRIM(RTRIM(COALESCE(NULLIF(d.JOBNUMBER, ''), NULLIF(h.JOBNUMBER, '')))),
            ''
        ) IS NULL
        ORDER BY h.ORDERNUMBER, d.LINENUMBER;
        """
    )
    sample_rows = cursor.fetchall()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    separator = "=" * 90
    lines = [
        separator,
        f"Missing Job ID Audit | {timestamp}",
        f"Source: {source_label}",
        f"Rows removed by strict Job Number rule: {missing_count}",
    ]

    if sample_rows:
        lines.append("Sample rows (top 10):")
        for row in sample_rows:
            lines.append(
                "  "
                f"Order={row[0]} | Line={row[1]} | Customer={row[2]} | Part={row[3]} "
                f"| DetailJob={row[4]} | HeaderJob={row[5]}"
            )
    else:
        lines.append("Sample rows: none")

    lines.append("")
    log_path = _current_missing_job_id_log_path()
    _prune_missing_job_id_logs(MISSING_JOB_ID_LOG_RETENTION_FILES)
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write("\n".join(lines))


def _current_missing_job_id_log_path():
    """Return the monthly audit log path for missing job ID removals."""
    MISSING_JOB_ID_LOG_DIR.mkdir(parents=True, exist_ok=True)
    month_stamp = datetime.now().strftime("%Y-%m")
    return MISSING_JOB_ID_LOG_DIR / f"{MISSING_JOB_ID_LOG_PREFIX}_{month_stamp}.log"


def _prune_missing_job_id_logs(max_files):
    """Keep only the newest monthly log files to cap long-term disk growth."""
    if max_files <= 0:
        return

    log_files = sorted(MISSING_JOB_ID_LOG_DIR.glob(f"{MISSING_JOB_ID_LOG_PREFIX}_*.log"))
    overflow = len(log_files) - max_files
    if overflow <= 0:
        return

    for old_log in log_files[:overflow]:
        old_log.unlink(missing_ok=True)