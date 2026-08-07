/*
Historical reporting draft for Foundry Management and Execution System (FMES).
Designed for date-only order entry data (no timestamp required).
Target platform: SQL Server.
*/

/*
Core assumptions:
1) Each order has a stable key: JobNumber plus optional Extension.
2) OrderEnteredDate is a DATE value from source system or feed.
3) OrderValueAtEntry should represent value at entry date for stable KPI reporting.
*/

/* ======================================================
   1) Run Metadata
   ====================================================== */
IF OBJECT_ID('dbo.SchedulerRun', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.SchedulerRun (
        RunId            BIGINT IDENTITY(1,1) PRIMARY KEY,
        RunDate          DATE NOT NULL,
        SourceName       NVARCHAR(100) NULL,
        RowCount         INT NULL,
        CreatedAt        DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_SchedulerRun_RunDate UNIQUE (RunDate)
    );
END;
GO

/* ======================================================
   2) Raw Daily Snapshot
   One row per order/extension seen in that run.
   ====================================================== */
IF OBJECT_ID('dbo.OrderSnapshot', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.OrderSnapshot (
        SnapshotId           BIGINT IDENTITY(1,1) PRIMARY KEY,
        RunId                BIGINT NOT NULL,
        RunDate              DATE NOT NULL,

        JobNumber            NVARCHAR(50) NOT NULL,
        Extension            NVARCHAR(10) NOT NULL DEFAULT '',

        OrderEnteredDate     DATE NULL,
        DueDate              DATE NULL,

        CustomerName         NVARCHAR(200) NULL,
        PartNumber           NVARCHAR(100) NULL,
        Alloy                NVARCHAR(50) NULL,
        CastingType          NVARCHAR(20) NULL,

        MoldsNeeded          DECIMAL(18, 2) NULL,
        MoldsForExt          DECIMAL(18, 2) NULL,

        OrderValueCurrent    DECIMAL(18, 2) NULL,

        CreatedAt            DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),

        CONSTRAINT FK_OrderSnapshot_RunId
            FOREIGN KEY (RunId) REFERENCES dbo.SchedulerRun(RunId),

        CONSTRAINT UQ_OrderSnapshot_Run_Order
            UNIQUE (RunId, JobNumber, Extension)
    );
END;
GO

CREATE INDEX IX_OrderSnapshot_RunDate
    ON dbo.OrderSnapshot (RunDate);
GO

CREATE INDEX IX_OrderSnapshot_EnteredDate
    ON dbo.OrderSnapshot (OrderEnteredDate);
GO

CREATE INDEX IX_OrderSnapshot_OrderKey
    ON dbo.OrderSnapshot (JobNumber, Extension);
GO

/* ======================================================
   3) Lifecycle Table
   One row per order/extension across history.
   ====================================================== */
IF OBJECT_ID('dbo.OrderLifecycle', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.OrderLifecycle (
        JobNumber              NVARCHAR(50) NOT NULL,
        Extension              NVARCHAR(10) NOT NULL DEFAULT '',

        FirstSeenDate          DATE NOT NULL,
        LastSeenDate           DATE NOT NULL,

        OrderEnteredDate       DATE NULL,

        OrderValueAtEntry      DECIMAL(18, 2) NULL,
        OrderValueLatest       DECIMAL(18, 2) NULL,

        LastDueDate            DATE NULL,
        LastCustomerName       NVARCHAR(200) NULL,
        LastPartNumber         NVARCHAR(100) NULL,

        IsActive               BIT NOT NULL DEFAULT 1,
        CreatedAt              DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        UpdatedAt              DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),

        CONSTRAINT PK_OrderLifecycle
            PRIMARY KEY (JobNumber, Extension)
    );
END;
GO

CREATE INDEX IX_OrderLifecycle_EnteredDate
    ON dbo.OrderLifecycle (OrderEnteredDate);
GO

/* ======================================================
   4) Upsert Lifecycle From Today Snapshot
   Run after loading dbo.OrderSnapshot for the day.
   ====================================================== */
CREATE OR ALTER PROCEDURE dbo.UpsertOrderLifecycleFromRun
    @RunId BIGINT
AS
BEGIN
    SET NOCOUNT ON;

    ;WITH src AS (
        SELECT
            s.JobNumber,
            s.Extension,
            s.RunDate,
            s.OrderEnteredDate,
            s.OrderValueCurrent,
            s.DueDate,
            s.CustomerName,
            s.PartNumber
        FROM dbo.OrderSnapshot s
        WHERE s.RunId = @RunId
    )
    MERGE dbo.OrderLifecycle AS tgt
    USING src
      ON tgt.JobNumber = src.JobNumber
     AND tgt.Extension = src.Extension
    WHEN MATCHED THEN
        UPDATE SET
            tgt.LastSeenDate = src.RunDate,
            tgt.OrderEnteredDate = COALESCE(tgt.OrderEnteredDate, src.OrderEnteredDate),
            tgt.OrderValueLatest = src.OrderValueCurrent,
            tgt.LastDueDate = src.DueDate,
            tgt.LastCustomerName = src.CustomerName,
            tgt.LastPartNumber = src.PartNumber,
            tgt.IsActive = 1,
            tgt.UpdatedAt = SYSUTCDATETIME()
    WHEN NOT MATCHED THEN
        INSERT (
            JobNumber,
            Extension,
            FirstSeenDate,
            LastSeenDate,
            OrderEnteredDate,
            OrderValueAtEntry,
            OrderValueLatest,
            LastDueDate,
            LastCustomerName,
            LastPartNumber,
            IsActive
        )
        VALUES (
            src.JobNumber,
            src.Extension,
            src.RunDate,
            src.RunDate,
            src.OrderEnteredDate,
            src.OrderValueCurrent,
            src.OrderValueCurrent,
            src.DueDate,
            src.CustomerName,
            src.PartNumber,
            1
        );
END;
GO

/* ======================================================
   5) KPI Queries Using DATE Windows
   ====================================================== */

/* Last calendar month entered orders and value */
DECLARE @StartLastMonth DATE = DATEFROMPARTS(YEAR(DATEADD(MONTH, -1, GETDATE())), MONTH(DATEADD(MONTH, -1, GETDATE())), 1);
DECLARE @StartThisMonth DATE = DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1);

SELECT
    COUNT(*) AS OrdersEnteredLastMonth,
    SUM(COALESCE(OrderValueAtEntry, 0)) AS ValueEnteredLastMonth
FROM dbo.OrderLifecycle
WHERE OrderEnteredDate >= @StartLastMonth
  AND OrderEnteredDate < @StartThisMonth;
GO

/* Last calendar week (Monday through Sunday) */
SET DATEFIRST 1;
DECLARE @Today DATE = CAST(GETDATE() AS DATE);
DECLARE @StartThisWeek DATE = DATEADD(DAY, 1 - DATEPART(WEEKDAY, @Today), @Today);
DECLARE @StartLastWeek DATE = DATEADD(DAY, -7, @StartThisWeek);

SELECT
    COUNT(*) AS OrdersEnteredLastWeek,
    SUM(COALESCE(OrderValueAtEntry, 0)) AS ValueEnteredLastWeek
FROM dbo.OrderLifecycle
WHERE OrderEnteredDate >= @StartLastWeek
  AND OrderEnteredDate < @StartThisWeek;
GO

/* Previous day */
DECLARE @Yesterday DATE = DATEADD(DAY, -1, CAST(GETDATE() AS DATE));

SELECT
    COUNT(*) AS OrdersEnteredYesterday,
    SUM(COALESCE(OrderValueAtEntry, 0)) AS ValueEnteredYesterday
FROM dbo.OrderLifecycle
WHERE OrderEnteredDate = @Yesterday;
GO

/* Month-over-month comparison */
DECLARE @Start2MonthsAgo DATE = DATEFROMPARTS(YEAR(DATEADD(MONTH, -2, GETDATE())), MONTH(DATEADD(MONTH, -2, GETDATE())), 1);

SELECT
    CASE
        WHEN OrderEnteredDate >= @StartLastMonth AND OrderEnteredDate < @StartThisMonth
            THEN 'LastMonth'
        WHEN OrderEnteredDate >= @Start2MonthsAgo AND OrderEnteredDate < @StartLastMonth
            THEN 'TwoMonthsAgo'
    END AS Period,
    COUNT(*) AS OrdersEntered,
    SUM(COALESCE(OrderValueAtEntry, 0)) AS ValueEntered
FROM dbo.OrderLifecycle
WHERE OrderEnteredDate >= @Start2MonthsAgo
  AND OrderEnteredDate < @StartThisMonth
GROUP BY
    CASE
        WHEN OrderEnteredDate >= @StartLastMonth AND OrderEnteredDate < @StartThisMonth
            THEN 'LastMonth'
        WHEN OrderEnteredDate >= @Start2MonthsAgo AND OrderEnteredDate < @StartLastMonth
            THEN 'TwoMonthsAgo'
    END;
GO

/* ======================================================
   6) Suggested Report Sentence Query
   ====================================================== */
DECLARE @Count INT;
DECLARE @Value DECIMAL(18,2);

SELECT
    @Count = COUNT(*),
    @Value = SUM(COALESCE(OrderValueAtEntry, 0))
FROM dbo.OrderLifecycle
WHERE OrderEnteredDate >= @StartLastMonth
  AND OrderEnteredDate < @StartThisMonth;

SELECT CONCAT(
    FORMAT(@Count, 'N0'),
    ' orders entered in the last calendar month, at a value of $',
    FORMAT(COALESCE(@Value, 0), 'N2'),
    '.'
) AS ReportLine;
GO

/*
Integration note for Python load process later:
1) Insert one row into dbo.SchedulerRun per run date.
2) Bulk insert run rows into dbo.OrderSnapshot.
3) Execute dbo.UpsertOrderLifecycleFromRun @RunId = <current run id>.
4) Execute KPI query/procedure for report output.
*/
