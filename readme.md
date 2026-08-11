# Foundry Management and Execution System (FMES)

**Author:** Logan Burkardt  
**Last Updated:** August 10, 2026

---

## Overview

Foundry Management and Execution System (FMES) is a Python-based mold and pour planning tool that reads the Open Order Report, filters eligible jobs, expands them into extension rows, builds a heat-first pour plan, back-fills molding days from those heats, and exports formatted planner workbooks.

The program uses a `src/fmes` package layout. [run_scheduler.py](run_scheduler.py) is the operational entrypoint (also used by PyInstaller), [src/fmes/main.py](src/fmes/main.py) provides the CLI, [src/fmes/scheduler.py](src/fmes/scheduler.py) provides architectural logic, and the core work lives in dedicated modules for input, filtering, schedule building, and export.

---

## Status Snapshot

### Completed

- Modular refactor of mold scheduling logic into dedicated modules
- `src/fmes` package layout with snake_case module and function naming throughout
- Centralized path configuration in [src/fmes/config.py](src/fmes/config.py) (`SCHEDULE_ROOT` resolves from `FMES_SCHEDULE_ROOT` or OneDrive env vars; no hard-coded user paths)
- Dependency manifests ([pyproject.toml](pyproject.toml), [requirements.txt](requirements.txt)) and expanded [.gitignore](.gitignore)
- Structured logging: console plus monthly log file under `Quality\Schedule\Logs`
- Unit and integration test coverage for scheduling boundaries; live-DB tests separated into `tests/integration/`
- SQL scheduler input validation updated to allow blank Alloy while keeping strict required checks for key fields
- Local credential hardening using environment variables
- Startup environment validation utility for DB configuration
- SQL Server historical snapshot load pipeline with transform/upsert support
- DB metadata/query helpers in [src/fmes/db_io.py](src/fmes/db_io.py) for table and column discovery
- Trimmed Main dashboard report query (Job Number, Customer PO, quantities, ship date, value, pour/production fields) plus a full scheduler projection accessor
- ERP field mapping corrections: castings per mold sourced from `JCJobMaster.TOOLIMPRESSIONS` (the "# on" field); Total Pour WT derived from pour weight × molds when `POURQUANTITY` is unrecorded
- Production SQL report script in [Production_Report_Queries.sql](Production_Report_Queries.sql)
- Alloy compatibility reference CSV with directional co-pour rules (`Compatibility Group`, `Compatible With ASTM Group`, `Specific Compatible Alloys`)
- Initial melt schedule builder in [src/fmes/melt_planning.py](src/fmes/melt_planning.py) with the 5 planned + 1 reserved daily heat slot policy
- Excel export hardening: calcChain cleanup (no repair prompt) and native numeric cell writes for OOR sync

### In Progress

- SQL Server integration beyond reporting reads (write-back schedule persistence)
- Persistent schedule state between runs
- Refining the heat-first planning model so alloy-group batching and due-date urgency stay balanced
- Expanding planner-facing preview/diagnostic workflows so iteration can happen without full exports

### Not Started

- Melt, casting, and cleaning schedule pipelines
- Automated reporting and distribution
- Power BI data publication pipeline

---

## Current Structure

### Orchestration

- [run_scheduler.py](run_scheduler.py) is the canonical executable entrypoint (`python run_scheduler.py --source sql`).
- [src/fmes/main.py](src/fmes/main.py) provides the CLI, logging setup, and export calls.
- [src/fmes/scheduler.py](src/fmes/scheduler.py) coordinates the schedule-building pipeline as a library module.
- It loads input, filters jobs, builds extension rows, applies a 10-week melt-planning horizon, builds the heat-first plan, back-fills molding days from the planned heats, and returns the data needed for mold and heat exports.

### Module Boundaries

- [src/fmes/scheduler_io.py](src/fmes/scheduler_io.py) reads scheduler input (SQL or Excel) and syncs the Open Order Report workbook.
- [src/fmes/scheduler_filter.py](src/fmes/scheduler_filter.py) filters rows down to jobs eligible for molding.
- [src/fmes/scheduler_build.py](src/fmes/scheduler_build.py) expands jobs into extensions and back-fills molding days from the heat plan while enforcing molding capacity constraints.
- [src/fmes/scheduler_export.py](src/fmes/scheduler_export.py) builds export blocks, prints them, and writes the Excel schedule file.
- [src/fmes/scheduler_validation.py](src/fmes/scheduler_validation.py) validates SQL rows and writes missing-job audit logs.
- [src/fmes/alloy_compatibility.py](src/fmes/alloy_compatibility.py) loads the compatibility CSV and evaluates directional co-pour rules.
- [src/fmes/melt_planning.py](src/fmes/melt_planning.py) prioritizes due dates, applies alloy-group-first batching, assigns heat numbers, and builds the initial melt schedule (5 planned heats + 1 reserved slot).
- [src/fmes/workbook_sync.py](src/fmes/workbook_sync.py) performs OOXML-level workbook writes, snapshots, and calcChain cleanup.

### Database & Reporting Modules

- [src/fmes/database.py](src/fmes/database.py) validates DB environment and opens SQL Server connections.
- [src/fmes/db_io.py](src/fmes/db_io.py) provides metadata helpers (`list_tables`, `list_columns`) and callable report data methods (`get_main_dashboard_rows`, `get_main_dashboard_scheduler_rows`).
- [src/fmes/load_historical_snapshot.py](src/fmes/load_historical_snapshot.py) loads ERP snapshot CSV data into SQL Server history tables.
- [Production_Report_Queries.sql](Production_Report_Queries.sql) contains production-ready SQL for Orders and Main dashboard column sets.

### Tests

Unit tests (no database required):

- [tests/test_database.py](tests/test_database.py)
- [tests/test_historical_loader.py](tests/test_historical_loader.py)
- [tests/test_scheduler_io.py](tests/test_scheduler_io.py)
- [tests/test_scheduler_filter.py](tests/test_scheduler_filter.py)
- [tests/test_scheduler_build.py](tests/test_scheduler_build.py)
- [tests/test_scheduler_export.py](tests/test_scheduler_export.py)
- [tests/test_melt_planning.py](tests/test_melt_planning.py)
- [tests/test_scheduler_integration.py](tests/test_scheduler_integration.py)

Integration tests (require live DB credentials; excluded from default discovery):

- [tests/integration/test_db_io.py](tests/integration/test_db_io.py)

---

## Current Behavior

### Input Processing

- Defaults to SQL-backed input using [src/fmes/db_io.py](src/fmes/db_io.py) `get_main_dashboard_scheduler_rows()` (full live projection for scheduling).
- `get_main_dashboard_rows()` provides the trimmed Job Number report projection for dashboards.
- Supports explicit source selection via `SCHEDULER_INPUT_SOURCE` (`sql` or `excel`).
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
- Filters melt-planning input to jobs due within the next 10 weeks.
- Prioritizes the next 2 weeks as highest priority, then the remaining 10-week horizon as priority review.
- Batches melt rows by alloy compatibility group before heat assignment so compatible alloys run together when possible.
- Caps grouped heats at 2300 lbs and 10 molds, while allowing a single oversize row to occupy its own heat when needed.
- Reserves heat slot 6 each day for remakes, drop-ins, and planner intervention.
- Back-fills molding days from planned heats while enforcing mold-before-pour and a maximum 3-day mold sit window.
- Uses casting type, not L/F bucket heuristics, to determine line vs floor capacity usage.

### Planning Direction (Draft)

- The active planning model is heat-first with mold backfill.
- Melt input is intentionally limited to the next 10 weeks so far-out jobs do not consume early heat capacity.
- Rows are grouped by alloy compatibility group before heat assignment to maximize useful heats within each alloy family.
- Due-date urgency still drives priority windows, and the next refinement step is balancing urgency against same-group batching when the two conflict.
- Alloy co-pour decisions are driven by reference data rather than hardcoded alloy checks.

### Alloy Compatibility Reference Data

- Source file: `Quality\Schedule\compatibleAlloys\alloy_compatibility.csv` (path resolved via `config.Paths`)
- Loader columns: `alloy_code`, `compatibility_group`, `Is_Compat_with_All`, `compatible_specific_alloys`, `is_active`
- Rules are directional: a stricter alloy can accept a looser one into its heat without implying the reverse.
- Scheduler input rows gain `Compatibility Group`, `Compatible With ASTM Group`, and `Specific Compatible Alloys` columns.

### Export Output

- Builds daily schedule blocks.
- Prints day-by-day mold totals.
- Exports a formatted workbook named `Mold Schedule.xlsx`.
- Exports `Heat Summary.xlsx` with:
        - `Heat Summary` sheet (planner day blocks by pour day / heat)
        - `Daily Heat Totals` sheet (heats/day + lbs/day + molds/day)
- Supports non-export planning inspection through `run_heat_grouping_preview.py` for alloy-group and heat batching review.

### Database Reporting Behavior

- Supports SQL metadata discovery directly from Python through [src/fmes/db_io.py](src/fmes/db_io.py).
- Supports callable Main dashboard extraction from the latest (or selected) `OrderSnapshot` run joined to OE order data by Job Number.
- Castings per mold reads live from `JCJobMaster.TOOLIMPRESSIONS` because it is a near-static product attribute; snapshots may lag.
- Total Pour WT falls back to pour weight × quantity of molds when the ERP `POURQUANTITY` has not been recorded yet.
- Supports operational SQL execution from [Production_Report_Queries.sql](Production_Report_Queries.sql) for direct SSMS usage.

### Open Order Report Sync Workflow

When running with `SCHEDULER_INPUT_SOURCE=sql`, [src/fmes/scheduler.py](src/fmes/scheduler.py) calls [src/fmes/scheduler_io.py](src/fmes/scheduler_io.py) `sync_open_order_report_with_sql()` before scheduling:

- Backs up `Open Order Report.xlsx` to `...\Quality\Schedule\Backups` using an incremented filename.
- Exports the current `OOR` sheet values to `...\Quality\Schedule\Historical OORs\OOR-YYYY-MM-DD_###.xlsx`.
- Overwrites `OOR` worksheet values in range `F2:V*` with current SQL data as plain text only (formatting unchanged).
- Writes a SQL snapshot workbook to `...\Quality\Schedule\Historical DB Snapshots` for day-over-day comparison.

---

## Runtime Flow

```text
SQL main dashboard (or Open Order Report.xlsx)
        │
        ▼
read_file()
        │
        ▼
Apply Alloy Compatibility Mapping
        │
        ▼
mold_scheduler()
        │
        ▼
build_schedule_rows()
        │
        ▼
prioritize_schedule_rows()
        │
        ▼
apply 10-week melt horizon
        │
        ▼
seed melt rows from prioritized alloy groups
        │
        ▼
build_schedule_dates()
        │
        ▼
build_daily_export_blocks()
        │
        ▼
export_mold_schedule() + export_heat_summary()
```

---

## Error Handling

The public entry points now wrap failures in contextual `RuntimeError` messages so problems are easier to trace during debugging.

- File load failures report the input workbook and sheet.
- Filtering failures report the scheduling stage.
- Build and export failures identify the step that failed.
- [src/fmes/scheduler.py](src/fmes/scheduler.py) also guards the full orchestration path.
- [src/fmes/database.py](src/fmes/database.py) validates DB environment configuration and reports missing variables clearly.
- Runs log to the console and to a monthly file at `Quality\Schedule\Logs\fmes_YYYY-MM.log`.

Use `python -m fmes.check_db_env` (from `src/`) before running DB-dependent tasks.

---

## Validation

Run the test suite from the project folder:

```bash
.venv\Scripts\python.exe -m unittest discover -s tests -t . -p "test_*.py"
```

For fast planning iterations (no full export run), use:

```powershell
.\run_fast_tests.ps1
```

This runs only:

- `tests.test_melt_planning`
- `tests.test_scheduler_integration`
- `tests.test_mold_schedule_from_melt`

To preview how melt input rows are grouped into alloy-based heats (without export), run:

```powershell
.venv\Scripts\python.exe run_heat_grouping_preview.py --source excel --max-detail-rows 80
```

Current working verification for fast planning iteration:

- `.\run_fast_tests.ps1`
- `python.exe .\run_heat_grouping_preview.py --source excel --max-detail-rows 80`

The current suite covers:

- database environment validation
- file loading
- filtering rules
- job expansion and day assignment
- melt planning heat grouping (5 planned + 1 reserved slot, compatibility grouping, overflow)
- export block generation and workbook writing
- end-to-end orchestration

Live-DB integration tests run separately: `python tests/integration/test_db_io.py`

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

The current codebase is structured so additional schedule types can be added later, but the immediate focus is improving the heat-first planning model rather than expanding to brand-new schedule types.

Planned next steps still align with the roadmap:

- validate alloy-group-first batching against due-date urgency on live OOR data
- improve planner-facing diagnostics and preview tooling before full export runs
- persistent schedule management
- work-in-progress tracking
- historical schedule analysis

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