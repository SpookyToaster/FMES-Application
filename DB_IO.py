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


MAIN_DASHBOARD_LIVE_SQL = """
    ;WITH MainOpenOrders AS (
        SELECT
            UPPER(LTRIM(RTRIM(jm.JOBNUMBER))) AS JobNumber,
            TRY_CONVERT(date, jm.SCHEDULESDUEDATESTRING) AS DueDate,
            NULLIF(LTRIM(RTRIM(jm.CUSTOMERNAME)), '') AS CustomerName,
            NULLIF(LTRIM(RTRIM(jm.PRODUCTCODE)), '') AS PartNumber,
            NULLIF(LTRIM(RTRIM(jm.JOBTYPE)), '') AS JobType,
            NULLIF(LTRIM(RTRIM(ic.BASEMATERIAL)), '') AS Alloy,
            NULLIF(LTRIM(RTRIM(jm.USERDEFINED7)), '') AS CastingType,
            NULLIF(LTRIM(RTRIM(CONVERT(varchar(100), jm.HEATNUMBER))), '') AS MainHeatNoAssigned,
            CASE
                WHEN NULLIF(LTRIM(RTRIM(jm.JOBONHOLD)), '') = 'þ' THEN 'YES'
                WHEN NULLIF(LTRIM(RTRIM(jm.JOBONHOLD)), '') = 'o' THEN 'NO'
                ELSE 'NO'
            END AS OnHold,
            COALESCE(jm.QUANTITYREQUIRED, 0) AS QuantityOfCastings,
            COALESCE(
                TRY_CONVERT(decimal(18, 6), NULLIF(LTRIM(RTRIM(jm.USERDEFINED10)), '')),
                0
            ) AS CastingsPerMold,
            COALESCE(jm.MOLDSREQUIRED, 0) AS QuantityOfMolds,
            COALESCE(
                TRY_CONVERT(decimal(18, 6), NULLIF(LTRIM(RTRIM(jm.USERDEFINED6)), '')),
                0
            ) AS QuantityOfCores,
            COALESCE(
                TRY_CONVERT(
                    decimal(18, 6),
                    NULLIF(
                        LTRIM(RTRIM(REPLACE(REPLACE(CONVERT(varchar(100), jm.USERDEFINED5), ',', ''), '$', ''))),
                        ''
                    )
                ),
                0
            ) AS PourWeight,
            COALESCE(jm.POURQUANTITY, 0) AS TotalPourWT,
            COALESCE(jm.CONTRACTREVISEDAMOUNT, jm.CONTRACTORIGINALAMOUNT, 0) AS TotalValue,
            COALESCE(jm.QUANTITYPRODUCED, 0) AS CastingsProduced,
            COALESCE(jm.MOLDSPRODUCED, 0) AS MoldsCompleted
        FROM dbo.JCJobMaster jm
        LEFT JOIN dbo.ICMaster ic
            ON ic.PRODUCTCODE = jm.PRODUCTCODE
        WHERE NULLIF(LTRIM(RTRIM(jm.JOBNUMBER)), '') IS NOT NULL
          AND jm.JOBSTATUSFLAG = 'I'
    ),
    OpenOrdersAgg AS (
        SELECT
            UPPER(LTRIM(RTRIM(COALESCE(NULLIF(d.JOBNUMBER, ''), NULLIF(h.JOBNUMBER, ''))))) AS JobNumber,
            MAX(NULLIF(LTRIM(RTRIM(d.PRODUCTNUMBER)), '')) AS OpenPartNumber,
            MAX(NULLIF(LTRIM(RTRIM(d.JOBTYPE)), '')) AS OpenJobType,
            MAX(
                COALESCE(
                    -- ERP date storage can be mixed: ISO text, yyyymmdd text, or day offsets.
                    TRY_CONVERT(date, CONVERT(varchar(30), d.REQUIREDDATE), 126),
                    TRY_CONVERT(date, CONVERT(varchar(8), d.REQUIREDDATE), 112),
                    CASE
                        WHEN TRY_CONVERT(int, d.REQUIREDDATE) IS NOT NULL
                            THEN DATEADD(DAY, TRY_CONVERT(int, d.REQUIREDDATE), '1800-12-28')
                        ELSE NULL
                    END,
                    TRY_CONVERT(date, CONVERT(varchar(30), h.REQUIREDDATE), 126),
                    TRY_CONVERT(date, CONVERT(varchar(8), h.REQUIREDDATE), 112),
                    CASE
                        WHEN TRY_CONVERT(int, h.REQUIREDDATE) IS NOT NULL
                            THEN DATEADD(DAY, TRY_CONVERT(int, h.REQUIREDDATE), '1800-12-28')
                        ELSE NULL
                    END
                )
            ) AS OpenDueDate,
            SUM(COALESCE(d.QUANTITYORDERED, 0)) AS OpenQtyOrdered,
            SUM(COALESCE(d.EXTENDEDORDERVALUE, 0)) AS OpenTotalValue
        FROM dbo.OEDetail d
        INNER JOIN dbo.OEHEader h
            ON h.ORDERNUMBER = d.ORDERNUMBER
        WHERE COALESCE(NULLIF(d.JOBNUMBER, ''), NULLIF(h.JOBNUMBER, '')) IS NOT NULL
        GROUP BY
            UPPER(LTRIM(RTRIM(COALESCE(NULLIF(d.JOBNUMBER, ''), NULLIF(h.JOBNUMBER, '')))))
    ),
    HeatAgg AS (
        SELECT
            JobNumber,
            STRING_AGG(HeatNumber, ', ') WITHIN GROUP (
                ORDER BY COALESCE(TRY_CONVERT(bigint, HeatNumber), 0), HeatNumber
            ) AS HeatNumber
        FROM (
            SELECT
                UPPER(LTRIM(RTRIM(jh.JOBNUMBER))) AS JobNumber,
                NULLIF(LTRIM(RTRIM(CONVERT(varchar(50), jh.HEATNUMBER))), '') AS HeatNumber
            FROM dbo.JCHeatNumber jh
            WHERE NULLIF(LTRIM(RTRIM(jh.JOBNUMBER)), '') IS NOT NULL
              AND NULLIF(LTRIM(RTRIM(CONVERT(varchar(50), jh.HEATNUMBER))), '') IS NOT NULL
        ) all_heats
        GROUP BY JobNumber
    ),
    MainAndOrders AS (
        SELECT
            o.JobNumber AS JobNumber,
            COALESCE(m.DueDate, o.OpenDueDate) AS DueDate,
            m.CustomerName,
            COALESCE(m.PartNumber, o.OpenPartNumber) AS PartNumber,
            COALESCE(m.JobType, o.OpenJobType) AS JobType,
            COALESCE(m.Alloy, NULLIF(LTRIM(RTRIM(icAlt.BASEMATERIAL)), '')) AS Alloy,
            m.CastingType,
            COALESCE(m.OnHold, 'NO') AS OnHold,
            CASE
                WHEN o.OpenQtyOrdered IS NULL THEN m.QuantityOfCastings
                ELSE o.OpenQtyOrdered
            END AS QtyOrderedFinal,
            m.QuantityOfMolds,
            m.CastingsPerMold,
            m.QuantityOfCores,
            m.PourWeight,
            m.TotalPourWT,
            m.TotalValue,
            m.CastingsProduced,
            m.MoldsCompleted,
            m.MainHeatNoAssigned,
            h.HeatNumber,
            o.OpenTotalValue
        FROM OpenOrdersAgg o
        LEFT JOIN MainOpenOrders m
            ON o.JobNumber = m.JobNumber
        LEFT JOIN HeatAgg h
            ON h.JobNumber = o.JobNumber
        LEFT JOIN dbo.ICMaster icAlt
            ON icAlt.PRODUCTCODE = COALESCE(m.PartNumber, o.OpenPartNumber)
    )
    SELECT
        DueDate AS [Due Date],
        CustomerName AS [Customer Name],
        PartNumber AS [Part Number],
        JobType AS [Job Type],
        JobNumber AS [Job Number],
        Alloy AS [Alloy],
        CastingType AS [Casting Type],
        CAST(COALESCE(QtyOrderedFinal, 0) AS decimal(18, 4)) AS [QTY Ordered],
        CAST(COALESCE(QuantityOfMolds, 0) AS decimal(18, 4)) AS [Quantity of Molds],
        CAST(COALESCE(CastingsPerMold, 0) AS decimal(18, 4)) AS [Castings Per Mold],
        CAST(COALESCE(QuantityOfCores, 0) AS decimal(18, 4)) AS [Quantity of Cores],
        CAST(COALESCE(PourWeight, 0) AS decimal(18, 4)) AS [Pour Weight],
        CAST(COALESCE(TotalPourWT, 0) AS decimal(18, 4)) AS [Total Pour WT],
        CAST(COALESCE(OpenTotalValue, TotalValue, 0) AS decimal(18, 4)) AS [Total Value],
        COALESCE(MainHeatNoAssigned, HeatNumber, '') AS [Heat No Assigned],
        CAST(NULLIF(COALESCE(CastingsProduced, 0), 0) AS decimal(18, 4)) AS [Castings Produced],
        CAST(NULLIF(COALESCE(MoldsCompleted, 0), 0) AS decimal(18, 4)) AS [Molds Completed],
        OnHold AS [On Hold]
    FROM MainAndOrders
        WHERE DueDate IS NOT NULL
            AND DueDate >= '2000-01-01'
            AND NULLIF(LTRIM(RTRIM(CustomerName)), '') IS NOT NULL
            AND NULLIF(LTRIM(RTRIM(PartNumber)), '') IS NOT NULL
            AND NULLIF(LTRIM(RTRIM(JobNumber)), '') IS NOT NULL
    ORDER BY
        [Due Date],
        [Job Number];
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


def _table_exists(cursor, table_name, schema="dbo"):
    """Return True when a base table exists in the current database."""
    cursor.execute(
        """
        SELECT 1
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = ?
          AND TABLE_NAME = ?
          AND TABLE_TYPE = 'BASE TABLE';
        """,
        schema,
        table_name,
    )
    return cursor.fetchone() is not None


def _history_tables_available(cursor):
    """Return True when the historical scheduler snapshot tables are present."""
    return _table_exists(cursor, "SchedulerRun") and _table_exists(cursor, "OrderSnapshot")


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
    Return main dashboard rows using history tables when available, otherwise
    fall back to live OE header/detail tables.

    Args:
        run_id: SchedulerRun.RunId to target, or None for latest available run
            when history tables exist.
        start_due_date: Inclusive lower bound for DueDate, or None.
        end_due_date: Inclusive upper bound for DueDate, or None.

    Returns:
        List of dictionaries keyed by report column labels.
    """
    history_params = (run_id, start_due_date, start_due_date, end_due_date, end_due_date)
    # Date filtering for live OE fallback can be added later in Python to avoid
    # mixed SQL date/int storage edge cases across ERP schemas.

    connection = connect()
    try:
        cursor = connection.cursor()

        if _history_tables_available(cursor):
            try:
                cursor.execute(MAIN_DASHBOARD_SQL, *history_params)
            except Exception:
                # If history schema exists but query cannot execute, keep the app
                # usable by falling back to live report tables.
                cursor.execute(MAIN_DASHBOARD_LIVE_SQL)
        else:
            cursor.execute(MAIN_DASHBOARD_LIVE_SQL)

        rows = cursor.fetchall()
        return _rows_to_dicts(cursor, rows)
    finally:
        connection.close()


def get_connection():
    """Return an active SQL Server connection from the shared DB helper."""
    return connect()