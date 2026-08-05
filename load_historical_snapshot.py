"""
Historical snapshot loader for the mold production scheduler.

Reads a combined ERP export CSV and loads it into the SQL Server history
tables used for reporting and trend analysis.

Pipeline (run in a single transaction):
  1. Insert a SchedulerRun row to record the load event.
  2. Bulk-insert all CSV rows as raw text into dbo.OrderSnapshotRaw.
  3. (Unless --skip-transform) Execute stored procedures to:
       a. Transform raw text into typed columns (dbo.TransformOrderSnapshotRaw).
       b. Upsert typed rows into the lifecycle table (dbo.UpsertOrderLifecycleFromRun).

Usage:
    python load_historical_snapshot.py --csv <path> [--run-date YYYY-MM-DD]
"""

import argparse
from datetime import date, datetime

import pandas as pd

from Database import connect, validate_database_environment


REQUIRED_COLUMNS = [
    "Due Date",
    "Customer Name",
    "Part Number",
    "Job Type",
    "Job Number",
    "Alloy",
    "Casting Type",
    "QTY Ordered",
    "Quantity of Molds",
    "Castings Per Mold",
    "Quantity of Cores",
    "Pour Weight",
    "Total Pour WT",
    "Total Value",
    "Heat No Assigned",
    "Castings Produced",
    "Molds Completed",
    "On Hold",
]


def parse_args():
    """Parse command-line arguments and return the parsed namespace."""
    parser = argparse.ArgumentParser(
        description="Load daily ERP export snapshot into SQL Server history tables."
    )
    parser.add_argument(
        "--csv",
        required=True,
        help="Path to combined ERP export CSV.",
    )
    parser.add_argument(
        "--run-date",
        default=date.today().isoformat(),
        help="Run date in YYYY-MM-DD format. Defaults to today.",
    )
    parser.add_argument(
        "--source-name",
        default="ERP_Combined_CSV",
        help="Source name recorded in SchedulerRun.",
    )
    parser.add_argument(
        "--skip-transform",
        action="store_true",
        help="Only load raw rows into dbo.OrderSnapshotRaw; skip transform/upsert steps.",
    )
    return parser.parse_args()


def validate_columns(frame):
    """Raise RuntimeError if any required column is absent from the DataFrame."""
    missing = [col for col in REQUIRED_COLUMNS if col not in frame.columns]
    if missing:
        raise RuntimeError(
            "CSV schema mismatch. Missing required columns: "
            + ", ".join(missing)
        )


def parse_run_date(run_date_text):
    """Parse a YYYY-MM-DD string into a date object, raising RuntimeError on bad input."""
    try:
        return datetime.strptime(run_date_text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise RuntimeError(
            f"Invalid --run-date '{run_date_text}'. Expected YYYY-MM-DD."
        ) from exc


def insert_scheduler_run(cursor, run_date, source_name, row_count):
    """
    Insert a row into dbo.SchedulerRun and return the generated RunId.

    Raises:
        RuntimeError: If SCOPE_IDENTITY() returns no result after the insert.
    """
    cursor.execute(
        """
        INSERT INTO dbo.SchedulerRun (RunDate, SourceName, RowCount)
        VALUES (?, ?, ?);
        """,
        run_date,
        source_name,
        row_count,
    )
    cursor.execute("SELECT CAST(SCOPE_IDENTITY() AS BIGINT);")
    result = cursor.fetchone()
    if not result:
        raise RuntimeError("Failed to retrieve RunId after insert into dbo.SchedulerRun.")
    return result[0]


def to_text(value):
    """Convert a DataFrame cell value to a stripped string, or None for NaN."""
    if pd.isna(value):
        return None
    return str(value).strip()


def insert_raw_snapshot_rows(cursor, run_id, frame):
    """
    Bulk-insert all rows from frame into dbo.OrderSnapshotRaw as raw text.

    Uses fast_executemany for performance.  Every cell value is converted to
    a stripped string via to_text() so the raw table preserves the original
    ERP export fidelity before any type conversions are applied.
    """
    insert_sql = """
        INSERT INTO dbo.OrderSnapshotRaw (
            RunId,
            DueDateRaw,
            CustomerNameRaw,
            PartNumberRaw,
            JobTypeRaw,
            JobNumberRaw,
            AlloyRaw,
            CastingTypeRaw,
            QtyOrderedRaw,
            QuantityOfMoldsRaw,
            CastingsPerMoldRaw,
            QuantityOfCoresRaw,
            PourWeightRaw,
            TotalPourWTRaw,
            TotalValueRaw,
            HeatNoAssignedRaw,
            CastingsProducedRaw,
            MoldsCompletedRaw,
            OnHoldRaw
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    rows = []
    for _, row in frame.iterrows():
        rows.append(
            (
                run_id,
                to_text(row["Due Date"]),
                to_text(row["Customer Name"]),
                to_text(row["Part Number"]),
                to_text(row["Job Type"]),
                to_text(row["Job Number"]),
                to_text(row["Alloy"]),
                to_text(row["Casting Type"]),
                to_text(row["QTY Ordered"]),
                to_text(row["Quantity of Molds"]),
                to_text(row["Castings Per Mold"]),
                to_text(row["Quantity of Cores"]),
                to_text(row["Pour Weight"]),
                to_text(row["Total Pour WT"]),
                to_text(row["Total Value"]),
                to_text(row["Heat No Assigned"]),
                to_text(row["Castings Produced"]),
                to_text(row["Molds Completed"]),
                to_text(row["On Hold"]),
            )
        )

    cursor.fast_executemany = True
    cursor.executemany(insert_sql, rows)


def run():
    args = parse_args()

    validate_database_environment()
    run_date = parse_run_date(args.run_date)

    try:
        frame = pd.read_csv(args.csv)
    except Exception as exc:
        raise RuntimeError(f"Failed to read CSV from {args.csv}") from exc

    validate_columns(frame)

    if frame.empty:
        raise RuntimeError("Input CSV is empty. Nothing to load.")

    connection = connect()

    try:
        cursor = connection.cursor()
        run_id = insert_scheduler_run(cursor, run_date, args.source_name, len(frame))
        insert_raw_snapshot_rows(cursor, run_id, frame)

        if not args.skip_transform:
            cursor.execute("EXEC dbo.TransformOrderSnapshotRaw @RunId = ?;", run_id)
            cursor.execute("EXEC dbo.UpsertOrderLifecycleFromRun @RunId = ?;", run_id)

        connection.commit()

        print(f"Load complete. RunId={run_id}, RowsLoaded={len(frame)}")
        if args.skip_transform:
            print("Transform/upsert steps were skipped.")
        else:
            print("Transform and lifecycle upsert executed successfully.")
    except Exception as exc:
        connection.rollback()
        raise RuntimeError(
            "Historical snapshot load failed. Transaction has been rolled back."
        ) from exc
    finally:
        connection.close()


if __name__ == "__main__":
    run()