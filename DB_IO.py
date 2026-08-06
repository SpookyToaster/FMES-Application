"""Database input/output functions."""

from Database import connect


ORDERS_DASHBOARD_SQL = """
    SELECT
        h.ORDERNUMBER AS [Order Number],
        d.LINENUMBER AS [Line],
        h.CUSTOMERCODE AS [Customer],
        h.CUSTOMERNAME AS [Customer Name],
        h.CUSTOMERPO AS [Customer PO],
        h.CURRENCY AS [Currency],
        d.PRODUCTNUMBER AS [Part Number],
        d.DESCRIPTION AS [Description],
        d.SHIPPINGUOM AS [UOM],
        COALESCE(NULLIF(d.JOBNUMBER, ''), NULLIF(h.JOBNUMBER, '')) AS [Job Number],
        d.JOBTYPE AS [Job Type],
        d.QUANTITYORDERED AS [Quantity Ordered],
        d.PIECESSHIPPEDTODATE AS [Quantity Shipped To Date],
        d.ALLOCATEDPIECES AS [Allocated Quantity],
        d.ORDERPRICE AS [Unit Price],
        d.EXTENDEDORDERVALUE AS [Total Value],
        h.ORDERDATE AS [Order Date],
        h.SHIPDATE AS [Ship Date],
        COALESCE(d.REQUIREDDATE, h.REQUIREDDATE) AS [Required Date]
    FROM dbo.OEHEader h
    INNER JOIN dbo.OEDetail d
        ON d.ORDERNUMBER = h.ORDERNUMBER
    WHERE (? IS NULL OR h.ORDERDATE >= ?)
      AND (? IS NULL OR h.ORDERDATE < DATEADD(DAY, 1, ?))
    ORDER BY
        h.ORDERDATE,
        h.ORDERNUMBER,
        d.LINENUMBER;
"""


MAIN_DASHBOARD_SQL = """
    ;WITH TargetRun AS (
        SELECT COALESCE(?, MAX(RunId)) AS RunId
        FROM dbo.SchedulerRun
    )
    SELECT
        s.DueDate AS [Due Date],
        s.CustomerName AS [Customer Name],
        s.PartNumber AS [Part Number],
        s.JobType AS [Job Type],
        s.JobNumber AS [Job Number],
        s.Alloy AS [Alloy],
        s.CastingType AS [Casting Type],
        s.QtyOrdered AS [QTY Ordered],
        s.QuantityOfMolds AS [Quantity of Molds],
        s.CastingsPerMold AS [Castings Per Mold],
        s.QuantityOfCores AS [Quantity of Cores],
        s.PourWeight AS [Pour Weight],
        s.TotalPourWT AS [Total Pour WT],
        s.TotalValue AS [Total Value],
        s.HeatNoAssigned AS [Heat No Assigned],
        s.CastingsProduced AS [Castings Produced],
        s.MoldsCompleted AS [Molds Completed]
    FROM dbo.OrderSnapshot s
    INNER JOIN TargetRun tr
        ON tr.RunId = s.RunId
    WHERE (? IS NULL OR s.DueDate >= ?)
      AND (? IS NULL OR s.DueDate < DATEADD(DAY, 1, ?))
    ORDER BY
        s.DueDate,
        s.JobNumber;
"""


def list_tables(schema="dbo", include_views=False):
    """
    Return table metadata from INFORMATION_SCHEMA for the target schema.

    Args:
        schema: SQL schema name (defaults to dbo).
        include_views: If True, includes views in addition to base tables.

    Returns:
        List of dictionaries with keys: schema, name, type.
    """
    table_types = ["BASE TABLE"]
    if include_views:
        table_types.append("VIEW")

    placeholders = ", ".join("?" for _ in table_types)
    sql = f"""
        SELECT
            TABLE_SCHEMA,
            TABLE_NAME,
            TABLE_TYPE
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = ?
          AND TABLE_TYPE IN ({placeholders})
        ORDER BY TABLE_NAME;
    """

    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(sql, schema, *table_types)
        rows = cursor.fetchall()
    finally:
        connection.close()

    return [
        {
            "schema": row[0],
            "name": row[1],
            "type": row[2],
        }
        for row in rows
    ]


def print_tables(schema="dbo", include_views=False):
    """Print tables (and optionally views) in a readable list format."""
    entries = list_tables(schema=schema, include_views=include_views)

    if not entries:
        print(f"No objects found in schema '{schema}'.")
        return

    print(f"Objects in schema '{schema}':")
    for entry in entries:
        print(f"- {entry['name']} ({entry['type']})")


def list_columns(table_name, schema="dbo"):
    """
    Return column metadata for a table in ordinal order.

    Args:
        table_name: Target table name.
        schema: SQL schema name (defaults to dbo).

    Returns:
        List of dictionaries with keys: schema, table, name, type, nullable, ordinal.
    """
    sql = """
        SELECT
            TABLE_SCHEMA,
            TABLE_NAME,
            COLUMN_NAME,
            DATA_TYPE,
            IS_NULLABLE,
            ORDINAL_POSITION
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = ?
          AND TABLE_NAME = ?
        ORDER BY ORDINAL_POSITION;
    """

    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(sql, schema, table_name)
        rows = cursor.fetchall()
    finally:
        connection.close()

    return [
        {
            "schema": row[0],
            "table": row[1],
            "name": row[2],
            "type": row[3],
            "nullable": row[4],
            "ordinal": row[5],
        }
        for row in rows
    ]


def _rows_to_dicts(cursor, rows):
    """Convert pyodbc rows to dictionaries keyed by selected column labels."""
    column_names = [column[0] for column in cursor.description]
    return [dict(zip(column_names, row)) for row in rows]


def get_orders_dashboard_rows(start_date=None, end_date=None):
    """
    Return orders dashboard rows from OE header/detail tables.

    Args:
        start_date: Inclusive lower bound for ORDERDATE, or None.
        end_date: Inclusive upper bound for ORDERDATE, or None.

    Returns:
        List of dictionaries keyed by report column labels.
    """
    params = (start_date, start_date, end_date, end_date)

    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(ORDERS_DASHBOARD_SQL, *params)
        rows = cursor.fetchall()
        return _rows_to_dicts(cursor, rows)
    finally:
        connection.close()


def get_main_dashboard_rows(run_id=None, start_due_date=None, end_due_date=None):
    """
    Return main dashboard rows from OrderSnapshot for one run (or latest run).

    Args:
        run_id: SchedulerRun.RunId to target, or None for latest available run.
        start_due_date: Inclusive lower bound for DueDate, or None.
        end_due_date: Inclusive upper bound for DueDate, or None.

    Returns:
        List of dictionaries keyed by report column labels.
    """
    params = (run_id, start_due_date, start_due_date, end_due_date, end_due_date)

    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(MAIN_DASHBOARD_SQL, *params)
        rows = cursor.fetchall()
        return _rows_to_dicts(cursor, rows)
    finally:
        connection.close()


def get_connection():
    """Return an active SQL Server connection from the shared DB helper."""
    return connect()