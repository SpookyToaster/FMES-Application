/*
Historical reporting schema aligned to the current ERP export structure.
Target platform: SQL Server.

Source sample columns:
Due Date, Customer Name, Part Number, Job Type, Job Number, Alloy, Casting Type,
QTY Ordered, Quantity of Molds, Castings Per Mold, Quantity of Cores,
Pour Weight, Total Pour WT, Total Value, Heat No Assigned, Castings Produced,
Molds Completed, On Hold
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
        CreatedAt        DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;
GO

CREATE INDEX IF NOT EXISTS IX_SchedulerRun_RunDate
ON dbo.SchedulerRun (RunDate);
GO

/* ======================================================
   2) Raw Snapshot Table (all text, shape matches export)
   ====================================================== */
IF OBJECT_ID('dbo.OrderSnapshotRaw', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.OrderSnapshotRaw (
        SnapshotRawId          BIGINT IDENTITY(1,1) PRIMARY KEY,
        RunId                  BIGINT NOT NULL,

        DueDateRaw             NVARCHAR(100) NULL,
        CustomerNameRaw        NVARCHAR(255) NULL,
        PartNumberRaw          NVARCHAR(255) NULL,
        JobTypeRaw             NVARCHAR(50) NULL,
        JobNumberRaw           NVARCHAR(100) NULL,
        AlloyRaw               NVARCHAR(100) NULL,
        CastingTypeRaw         NVARCHAR(50) NULL,
        QtyOrderedRaw          NVARCHAR(100) NULL,
        QuantityOfMoldsRaw     NVARCHAR(100) NULL,
        CastingsPerMoldRaw     NVARCHAR(100) NULL,
        QuantityOfCoresRaw     NVARCHAR(100) NULL,
        PourWeightRaw          NVARCHAR(100) NULL,
        TotalPourWTRaw         NVARCHAR(100) NULL,
        TotalValueRaw          NVARCHAR(100) NULL,
        HeatNoAssignedRaw      NVARCHAR(255) NULL,
        CastingsProducedRaw    NVARCHAR(100) NULL,
        MoldsCompletedRaw      NVARCHAR(100) NULL,
        OnHoldRaw              NVARCHAR(20) NULL,

        CreatedAt              DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),

        CONSTRAINT FK_OrderSnapshotRaw_RunId
            FOREIGN KEY (RunId) REFERENCES dbo.SchedulerRun(RunId)
    );
END;
GO

CREATE INDEX IF NOT EXISTS IX_OrderSnapshotRaw_RunId
ON dbo.OrderSnapshotRaw (RunId);
GO

/* ======================================================
   3) Typed Snapshot Table
   ====================================================== */
IF OBJECT_ID('dbo.OrderSnapshot', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.OrderSnapshot (
        SnapshotId             BIGINT IDENTITY(1,1) PRIMARY KEY,
        RunId                  BIGINT NOT NULL,
        RunDate                DATE NOT NULL,

        JobNumber              NVARCHAR(100) NOT NULL,
        Extension              NVARCHAR(10) NOT NULL DEFAULT '',

        DueDate                DATE NULL,
        OrderEnteredDate       DATE NULL,

        CustomerName           NVARCHAR(255) NULL,
        PartNumber             NVARCHAR(255) NULL,
        JobType                NVARCHAR(50) NULL,
        Alloy                  NVARCHAR(100) NULL,
        CastingType            NVARCHAR(50) NULL,

        QtyOrdered             DECIMAL(18, 4) NULL,
        QuantityOfMolds        DECIMAL(18, 4) NULL,
        CastingsPerMold        DECIMAL(18, 4) NULL,
        QuantityOfCores        DECIMAL(18, 4) NULL,
        PourWeight             DECIMAL(18, 4) NULL,
        TotalPourWT            DECIMAL(18, 4) NULL,

        TotalValue             DECIMAL(18, 2) NULL,
        HeatNoAssigned         NVARCHAR(255) NULL,
        CastingsProduced       DECIMAL(18, 4) NULL,
        MoldsCompleted         DECIMAL(18, 4) NULL,
        OnHold                 NVARCHAR(20) NULL,

        CreatedAt              DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),

        CONSTRAINT FK_OrderSnapshot_RunId
            FOREIGN KEY (RunId) REFERENCES dbo.SchedulerRun(RunId),

        CONSTRAINT UQ_OrderSnapshot_Run_Order
            UNIQUE (RunId, JobNumber, Extension)
    );
END;
GO

CREATE INDEX IF NOT EXISTS IX_OrderSnapshot_RunDate
ON dbo.OrderSnapshot (RunDate);
GO

CREATE INDEX IF NOT EXISTS IX_OrderSnapshot_OrderKey
ON dbo.OrderSnapshot (JobNumber, Extension);
GO

CREATE INDEX IF NOT EXISTS IX_OrderSnapshot_OrderEnteredDate
ON dbo.OrderSnapshot (OrderEnteredDate);
GO

/* ======================================================
   4) Lifecycle Table
   ====================================================== */
IF OBJECT_ID('dbo.OrderLifecycle', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.OrderLifecycle (
        JobNumber              NVARCHAR(100) NOT NULL,
        Extension              NVARCHAR(10) NOT NULL DEFAULT '',

        FirstSeenDate          DATE NOT NULL,
        LastSeenDate           DATE NOT NULL,

        /*
           Primary business entry date for KPI use.
           If ERP does not provide this yet, we fallback to DueDate during upsert.
        */
        OrderEnteredDate       DATE NULL,

        OrderValueAtEntry      DECIMAL(18, 2) NULL,
        OrderValueLatest       DECIMAL(18, 2) NULL,

        LastDueDate            DATE NULL,
        LastCustomerName       NVARCHAR(255) NULL,
        LastPartNumber         NVARCHAR(255) NULL,
        LastJobType            NVARCHAR(50) NULL,
        LastAlloy              NVARCHAR(100) NULL,
        LastCastingType        NVARCHAR(50) NULL,
        LastOnHold             NVARCHAR(20) NULL,

        IsActive               BIT NOT NULL DEFAULT 1,
        CreatedAt              DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        UpdatedAt              DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),

        CONSTRAINT PK_OrderLifecycle
            PRIMARY KEY (JobNumber, Extension)
    );
END;
GO

CREATE INDEX IF NOT EXISTS IX_OrderLifecycle_EnteredDate
ON dbo.OrderLifecycle (OrderEnteredDate);
GO

/* ======================================================
   5) Transform Raw -> Typed Snapshot for a run
   ====================================================== */
CREATE OR ALTER PROCEDURE dbo.TransformOrderSnapshotRaw
    @RunId BIGINT
AS
BEGIN
    SET NOCOUNT ON;

    DELETE FROM dbo.OrderSnapshot
    WHERE RunId = @RunId;

    INSERT INTO dbo.OrderSnapshot (
        RunId,
        RunDate,
        JobNumber,
        Extension,
        DueDate,
        OrderEnteredDate,
        CustomerName,
        PartNumber,
        JobType,
        Alloy,
        CastingType,
        QtyOrdered,
        QuantityOfMolds,
        CastingsPerMold,
        QuantityOfCores,
        PourWeight,
        TotalPourWT,
        TotalValue,
        HeatNoAssigned,
        CastingsProduced,
        MoldsCompleted,
        OnHold
    )
    SELECT
        sr.RunId,
        sr.RunDate,
        NULLIF(LTRIM(RTRIM(raw.JobNumberRaw)), ''),
        '',
        TRY_CONVERT(DATE, raw.DueDateRaw),
        NULL,
        NULLIF(LTRIM(RTRIM(raw.CustomerNameRaw)), ''),
        NULLIF(LTRIM(RTRIM(raw.PartNumberRaw)), ''),
        NULLIF(LTRIM(RTRIM(raw.JobTypeRaw)), ''),
        NULLIF(LTRIM(RTRIM(raw.AlloyRaw)), ''),
        NULLIF(LTRIM(RTRIM(raw.CastingTypeRaw)), ''),
        TRY_CONVERT(DECIMAL(18,4), raw.QtyOrderedRaw),
        TRY_CONVERT(DECIMAL(18,4), raw.QuantityOfMoldsRaw),
        TRY_CONVERT(DECIMAL(18,4), raw.CastingsPerMoldRaw),
        TRY_CONVERT(DECIMAL(18,4), raw.QuantityOfCoresRaw),
        TRY_CONVERT(DECIMAL(18,4), raw.PourWeightRaw),
        TRY_CONVERT(DECIMAL(18,4), raw.TotalPourWTRaw),
        TRY_CONVERT(DECIMAL(18,2), REPLACE(REPLACE(raw.TotalValueRaw, '$', ''), ',', '')),
        NULLIF(LTRIM(RTRIM(raw.HeatNoAssignedRaw)), ''),
        TRY_CONVERT(DECIMAL(18,4), raw.CastingsProducedRaw),
        TRY_CONVERT(DECIMAL(18,4), raw.MoldsCompletedRaw),
        UPPER(NULLIF(LTRIM(RTRIM(raw.OnHoldRaw)), ''))
    FROM dbo.OrderSnapshotRaw raw
    INNER JOIN dbo.SchedulerRun sr
        ON sr.RunId = raw.RunId
    WHERE raw.RunId = @RunId
      AND NULLIF(LTRIM(RTRIM(raw.JobNumberRaw)), '') IS NOT NULL;
END;
GO

/* ======================================================
   6) Upsert Lifecycle from Typed Snapshot
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
            /* Fallback until ERP OrderEnteredDate is available */
            COALESCE(s.OrderEnteredDate, s.DueDate) AS EntryDateForReporting,
            s.TotalValue,
            s.DueDate,
            s.CustomerName,
            s.PartNumber,
            s.JobType,
            s.Alloy,
            s.CastingType,
            s.OnHold
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
            tgt.OrderEnteredDate = COALESCE(tgt.OrderEnteredDate, src.EntryDateForReporting),
            tgt.OrderValueLatest = src.TotalValue,
            tgt.LastDueDate = src.DueDate,
            tgt.LastCustomerName = src.CustomerName,
            tgt.LastPartNumber = src.PartNumber,
            tgt.LastJobType = src.JobType,
            tgt.LastAlloy = src.Alloy,
            tgt.LastCastingType = src.CastingType,
            tgt.LastOnHold = src.OnHold,
            tgt.IsActive = CASE WHEN src.OnHold = 'YES' THEN 0 ELSE 1 END,
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
            LastJobType,
            LastAlloy,
            LastCastingType,
            LastOnHold,
            IsActive
        )
        VALUES (
            src.JobNumber,
            src.Extension,
            src.RunDate,
            src.RunDate,
            src.EntryDateForReporting,
            src.TotalValue,
            src.TotalValue,
            src.DueDate,
            src.CustomerName,
            src.PartNumber,
            src.JobType,
            src.Alloy,
            src.CastingType,
            src.OnHold,
            CASE WHEN src.OnHold = 'YES' THEN 0 ELSE 1 END
        );
END;
GO

/* ======================================================
   7) KPI queries (date-only windows)
   ====================================================== */

/* Last calendar month */
DECLARE @StartLastMonth DATE = DATEFROMPARTS(YEAR(DATEADD(MONTH, -1, GETDATE())), MONTH(DATEADD(MONTH, -1, GETDATE())), 1);
DECLARE @StartThisMonth DATE = DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1);

SELECT
    COUNT(*) AS OrdersEnteredLastMonth,
    SUM(COALESCE(OrderValueAtEntry, 0)) AS ValueEnteredLastMonth
FROM dbo.OrderLifecycle
WHERE OrderEnteredDate >= @StartLastMonth
  AND OrderEnteredDate < @StartThisMonth;
GO

/* Report sentence */
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
