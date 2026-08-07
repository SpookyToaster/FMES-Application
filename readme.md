# Foundry Management and Execution System (FMES)

**Author:** Logan Burkardt  
**Last Updated:** August 7, 2026

---

## Overview

Foundry Management and Execution System (FMES) is a Python-based mold and pour planning tool that reads the Open Order Report, filters eligible jobs, expands them into schedule rows, assigns production days, and exports formatted schedule workbooks.

The program now uses a modular layout instead of a single monolithic script. [Main.py](Main.py) is the operational entrypoint, while [Scheduler.py](Scheduler.py) provides orchestration logic and the core work lives in dedicated modules for input, filtering, schedule building, and export.

---

## Status Snapshot

### Completed

- Modular refactor of mold scheduling logic into dedicated modules
- Merge conflict cleanup and stable orchestration entrypoint
- Unit and integration test coverage for scheduling boundaries
- SQL scheduler input validation updated to allow blank Alloy while keeping strict required checks for key fields
- Local credential hardening using environment variables
- Startup environment validation utility for DB configuration
- SQL Server historical snapshot load pipeline with transform/upsert support
- DB metadata/query helpers in [DB_IO.py](DB_IO.py) for table and column discovery
- Callable dashboard query methods in [DB_IO.py](DB_IO.py) for Orders and Main report datasets
- Main dashboard SQL mapping aligned to direct-source policy for molds/cores/pour fields (no cross-field derivations)
- Production SQL report script in [Production_Report_Queries.sql](Production_Report_Queries.sql)
- Alloy compatibility reference CSV scaffolded at `Quality\Schedule\compatibleAlloys\alloy_compatibility.csv`
- Scheduler input loader now attaches compatibility metadata columns from alloy CSV (`Compatibility Group`, `Compatibility Family`)

### In Progress

- SQL Server integration beyond reporting reads (write-back schedule persistence)
- Persistent schedule state between runs
- Melt-first planning redesign so molding and heat schedules are planned together

### Not Started

- Melt, casting, and cleaning schedule pipelines
- Automated reporting and distribution
- Power BI data publication pipeline

## Considerations

- Current greedy architecture encounters edge cases and multi-department optimization constraints. A design review for staged optimization (mold first, then melt) is still needed.

---

## Current Structure

### Orchestration

- [Main.py](Main.py) is the canonical executable entrypoint for DB/Excel input through export.
- [Scheduler.py](Scheduler.py) coordinates the schedule-building pipeline as a library module.
- It loads input, filters jobs, builds schedule rows, assigns days, groups by day, prints summaries, and exports the final workbook.

### Module Boundaries

- [scheduler_io.py](scheduler_io.py) reads the Open Order Report workbook.
- [scheduler_filter.py](scheduler_filter.py) filters rows down to jobs eligible for molding.
- [scheduler_build.py](scheduler_build.py) expands jobs into extensions, assigns days, and builds daily schedule views.
- [scheduler_export.py](scheduler_export.py) builds export blocks, prints them, and writes the Excel schedule file.

### Database & Reporting Modules

- [Database.py](Database.py) validates DB environment and opens SQL Server connections.
- [DB_IO.py](DB_IO.py) provides metadata helpers (`list_tables`, `list_columns`) and callable report data methods (`get_orders_dashboard_rows`, `get_main_dashboard_rows`).
- [load_historical_snapshot.py](load_historical_snapshot.py) loads ERP snapshot CSV data into SQL Server history tables.
- [Production_Report_Queries.sql](Production_Report_Queries.sql) contains production-ready SQL for Orders and Main dashboard column sets.

### Tests

- [tests/test_database.py](tests/test_database.py)
- [tests/test_DB_IO.py](tests/test_DB_IO.py)
- [tests/test_historical_loader.py](tests/test_historical_loader.py)
- [tests/test_scheduler_io.py](tests/test_scheduler_io.py)
- [tests/test_scheduler_filter.py](tests/test_scheduler_filter.py)
- [tests/test_scheduler_build.py](tests/test_scheduler_build.py)
- [tests/test_scheduler_export.py](tests/test_scheduler_export.py)
- [tests/test_scheduler_integration.py](tests/test_scheduler_integration.py)

---

## Current Behavior

### Input Processing

- Defaults to SQL-backed input using [DB_IO.py](DB_IO.py) `get_main_dashboard_rows()`.
- Falls back to the Open Order Report Excel file when SQL input is empty for the selected run.
- Supports explicit source selection via `SCHEDULER_INPUT_SOURCE` (`sql` or `excel`).
- Supports optional SQL run selection via `SCHEDULER_RUN_ID`.
- Strips whitespace from Excel column headers after loading.
- Filters out rows that are not eligible for molding.
- Uses modular orchestration to run each scheduling stage.

### Scheduling Rules

- Skips blank jobs.
- Skips jobs on hold.
- Keeps scheduled jobs that still have molds remaining.
- Skips investment cast jobs (`IFA`, `IFC`, and cast type `I`).
- Skips jobs requiring zero or fewer molds.
- Splits jobs into extensions based on a 2300 lb cap and a 10 mold cap per extension.
- Preserves extension continuity after partial completion by consuming completed molds from earliest extensions first.
- Assigns each schedule row to days while respecting line/floor per-job daily limits (6/3), and allows an extension to span multiple days when needed.
- Assigns per-day heat numbers based on alloy continuity and 2300 lb maximum per heat.

### Planning Direction (Draft)

- Shift from mold-only greedy planning to melt-first planning with mold backfill.
- Daily heat policy target is 5 planned heats plus 1 reserved placeholder heat for remakes, drop-ins, and late substitutions.
- Extensions remain the core planning unit and should stay intact through heat grouping whenever possible.
- Alloy co-pour decisions are moving to a reference-data model instead of hardcoded alloy checks.

### Alloy Compatibility Reference Data

- Source file: `C:\Users\lburkardt\OneDrive - MonettMetalsUS1\Quality\Schedule\compatibleAlloys\alloy_compatibility.csv`
- Current columns:
        - `alloy_code`
        - `compatibility_group`
        - `family_tag`
        - `is_active`
        - `source_rule`
        - `notes`
- Seed rules currently included:
        - `WCC` and `WCB` share A216 compatibility group.
        - `130-115` is seeded under a `70-30` family tag/group A148 for future related alloys.

### Export Output

- Builds daily schedule blocks.
- Prints day-by-day mold totals.
- Exports a formatted workbook named `Mold Schedule.xlsx`.
- Exports `Heat Summary.xlsx` with:
        - `Heat Summary` sheet (date + heat + alloy + lbs + molds)
        - `Daily Heat Totals` sheet (heats/day + lbs/day + molds/day)

### Database Reporting Behavior

- Supports SQL metadata discovery directly from Python through [DB_IO.py](DB_IO.py).
- Supports callable Orders dashboard extraction from OE header/detail tables.
- Supports callable Main dashboard extraction from the latest (or selected) `OrderSnapshot` run.
- Uses direct-source values for mold/core/pour outputs in Main dashboard extraction; derived formulas are intentionally excluded so manual Excel calculations stay authoritative.
- Supports operational SQL execution from [Production_Report_Queries.sql](Production_Report_Queries.sql) for direct SSMS usage.

### Open Order Report Sync Workflow

When running with `SCHEDULER_INPUT_SOURCE=sql`, [Scheduler.py](Scheduler.py) now calls [scheduler_io.py](scheduler_io.py) `Sync_Open_Order_Report_With_SQL()` before scheduling:

- Backs up `Open Order Report.xlsx` to `...\Quality\Schedule\Backups` using an incremented filename.
- Exports the current `OOR` sheet values to `...\Quality\Schedule\Historical OORs\OOR-YYYY-MM-DD_###.xlsx`.
- Overwrites `OOR` worksheet values in range `F2:V*` with current SQL data as plain text only (formatting unchanged).
- Writes a SQL snapshot workbook to `...\Quality\Schedule\Historical DB Snapshots` for day-over-day comparison.

---

## Runtime Flow

```text
Open Order Report.xlsx
        │
        ▼
Read_File()
        │
        ▼
Apply Alloy Compatibility Mapping
        │
        ▼
Mold_Scheduler()
        │
        ▼
Build_Schedule_Rows()
        │
        ▼
Assign_days()
        │
        ▼
Build_Daily_Schedules()
        │
        ▼
Build_Schedule_Dates()
        │
        ▼
Build_Daily_Export_Blocks()
        │
        ▼
Print_Export_Blocks()
        │
        ▼
Export_Mold_Schedule()
```

---

## Error Handling

The public entry points now wrap failures in contextual `RuntimeError` messages so problems are easier to trace during debugging.

- File load failures report the input workbook and sheet.
- Filtering failures report the scheduling stage.
- Build and export failures identify the step that failed.
- [Scheduler.py](Scheduler.py) also guards the full orchestration path.
- [Database.py](Database.py) validates DB environment configuration and reports missing variables clearly.

Use [check_db_env.py](check_db_env.py) before running DB-dependent tasks.

---

## Validation

Run the test suite from the project folder:

```bash
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Current verification snapshot: 24 tests passing.

The current suite covers:

- database environment validation
- file loading
- filtering rules
- job expansion and day assignment
- export block generation and workbook writing
- end-to-end orchestration

Latest focused verification pass: 31 tests passing after scheduler IO and DB query updates.

---

## Build / Packaging

Build the executable from the project root with:

```powershell
.\build_scheduler.ps1
```

That script writes PyInstaller work/dist output to a local path under `%LOCALAPPDATA%\SchedulerProgram\PyInstaller`, which avoids OneDrive lock conflicts and removes the need to manage build folders manually.

To label a build, pass a version string or release tag:

```powershell
.\build_scheduler.ps1 -VersionLabel 1.0.0
```

That produces a versioned release folder plus a copy named like `Scheduler_1.0.0.exe`, along with a `build-info.txt` file for traceability.

If you need to run PyInstaller directly, use a fresh work/dist path each time:

```powershell
.venv\Scripts\python.exe -m PyInstaller Scheduler.spec --noconfirm --clean --workpath "build_$(Get-Date -Format yyyyMMdd_HHmmss)" --distpath "dist_$(Get-Date -Format yyyyMMdd_HHmmss)"
```

---

## Business Objective

The scheduler provides a repeatable method for planning molding operations while reducing manual effort, spreadsheet maintenance, and scheduling inconsistencies.

Key objectives include:

- improving schedule accuracy
- increasing production visibility
- reducing manual planning effort
- supporting future production reporting
- providing a foundation for WIP tracking and analytics

---

## Technology Stack

- Python
- pandas
- openpyxl
- pyodbc
- Excel-based inputs and outputs

## Security Notes

- Credentials are not stored in source files.
- Use local environment variables for DB settings.
- Keep real values out of git-tracked files.
- [.env.example](.env.example) contains placeholders only.

---

## Future Direction

The current codebase is structured so additional schedule types can be added later, such as melt or cleaning schedules, without reworking the mold scheduling pipeline.

Planned next steps still align with the roadmap:

- persistent schedule management
- work-in-progress tracking
- additional schedule types
- historical schedule analysis
- automated reporting and notifications

## FMES Evolution Plan

## Guiding Principle

Do not optimize for the perfect schedule.

Optimize for:

- Stability
- Recoverability
- Ease of execution
- Minimal planner intervention

Production conditions will change daily. The system should adapt rather than attempting to predict perfectly.

### Objective

Evolve the current mold scheduler from a static schedule generator into a production planning system that:

- Maintains schedule state between runs
- Tracks actual production completion
- Handles remakes and priority changes
- Generates melt schedules from real available work
- Minimizes schedule churn
- Produces schedules operators can execute with minimal planner intervention

Current scheduler successfully handles mold capacity constraints and extension scheduling. Future work should focus on schedule persistence, execution feedback, and melt planning.

For development priorities, see [Roadmap.md](Roadmap.md).