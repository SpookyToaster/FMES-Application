/*
Production report queries for Monett dashboards.

Query 1: Orders dashboard fields from OE header/detail tables.
Query 2: Main dashboard fields from latest (or selected) OrderSnapshot run.
*/

/* ======================================================
   Query 1 - Monett Orders Dashboard
   ====================================================== */

DECLARE @OrdersStartDate DATE = NULL;
DECLARE @OrdersEndDate   DATE = NULL;

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
WHERE (@OrdersStartDate IS NULL OR h.ORDERDATE >= @OrdersStartDate)
  AND (@OrdersEndDate IS NULL OR h.ORDERDATE < DATEADD(DAY, 1, @OrdersEndDate))
ORDER BY
    h.ORDERDATE,
    h.ORDERNUMBER,
    d.LINENUMBER;


/* ======================================================
   Query 2 - Monett Main Dashboard
   ====================================================== */

DECLARE @RunId BIGINT = NULL;      -- NULL = latest available run
DECLARE @MainStartDueDate DATE = NULL;
DECLARE @MainEndDueDate   DATE = NULL;

;WITH TargetRun AS (
    SELECT COALESCE(@RunId, MAX(RunId)) AS RunId
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
WHERE (@MainStartDueDate IS NULL OR s.DueDate >= @MainStartDueDate)
  AND (@MainEndDueDate IS NULL OR s.DueDate < DATEADD(DAY, 1, @MainEndDueDate))
ORDER BY
    s.DueDate,
    s.JobNumber;
