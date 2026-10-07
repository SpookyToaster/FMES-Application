# Foundry Management and Execution System (FMES)

Author: Logan Burkardt  
Last Updated: 2026-10-07

## Status

FMES is considered complete for the current production scheduling and reporting workflow. The active scope covers live SQL synchronization, OOR-driven scheduling, workbook export, report-pack generation, and email distribution for the current operational process.

## Overview

FMES is a Windows-oriented Python application used to build and distribute production schedules from live SQL data or an existing Open Order Report (OOR) workbook. The project supports a full scheduling flow and an OOR-only workflow for quick rescheduling from existing workbook data.

Primary entrypoints:

- [run_scheduler.py](run_scheduler.py): full CLI launcher
- [run_oor_schedule.py](run_oor_schedule.py): OOR-only launcher
- [src/fmes/main.py](src/fmes/main.py): full run orchestration
- [src/fmes/oor_main.py](src/fmes/oor_main.py): OOR-only flow wrapper
- [src/fmes](src/fmes): core scheduling and reporting package

## Current Scope

FMES now delivers the following operational capability:

- Live SQL validation and data synchronization into the OOR
- OOR shipping table refresh and historical snapshot support
- Job filtering, mold scheduling, and capacity checks
- Mold input diagnostics, compatibility rules, and melt planning support
- Combined workbook export with summary and diagnostics sheets
- Report-pack generation for operational audiences
- Optional email delivery with audience-based recipient management
- Local configuration and Windows installer support for deployment

## Recent Completed Work

Recent project work has focused on stabilizing the scheduler and operational delivery layer, including:

- Shared network root configuration and local env loading for user-scoped credentials
- OOR sync and shipping-table refresh updates for workbook-based production runs
- Enhanced mold-input diagnostics and casting-per-mold derivation logic
- Production visibility summaries and report-pack exports
- Email send flow with Outlook/SMTP transport support and recipient settings persistence
- Windows prerequisite setup and installer packaging for deployment

## Runtime Flow

### Full scheduler flow

1. Resolve input source from `--source` or `SCHEDULER_INPUT_SOURCE` (default `sql`).
2. When using SQL mode, validate DB settings, sync live data into the OOR, and refresh the shipping table when available.
3. Read scheduler input from SQL or Excel and normalize rows.
4. Filter schedulable jobs.
5. Build scheduler rows and assign mold-day slots.
6. Generate export blocks and shipping outlook rows.
7. Write the combined Production Schedule Summary workbook.
8. Optionally generate report-pack artifacts.
9. Optionally send the report-pack email.

### OOR-only flow

- Forces Excel input mode.
- Skips SQL validation and SQL sync.
- Builds the schedule directly from the existing OOR workbook.

## SQL Mold Derivation Logic

Live scheduler rows are read from [src/fmes/db_io.py](src/fmes/db_io.py) using the dashboard SQL query layer.

Current casting-per-mold fallback precedence is:

1. `JCJobMaster.TOOLIMPRESSIONS`
2. `ICMaster.CASTINGSPERMOLD`
3. `ICPattern.PATTERNIMPRESSIONS`
4. BOM fallback only when BOM tool impressions are present and consistent
5. missing/unknown when no non-zero source is available

The scheduler emits a derivation label in the mold diagnostic layer:

- `JOBMASTER`
- `ICMASTER`
- `PATTERN`
- `BOM_CONSISTENT`
- `BOM_CONFLICT`
- `MISSING`

## Scheduling and Validation Rules

Eligibility filtering in [src/fmes/scheduler_filter.py](src/fmes/scheduler_filter.py):

- blank Job Number excluded
- Hold = YES excluded
- Job Type IFA/IFC excluded
- Casting Type I excluded
- Molds Needed <= 0 excluded

Mold-day assignment in [src/fmes/mold_console_schedule.py](src/fmes/mold_console_schedule.py):

- due-date driven ordering with compatibility-group tie-breaking
- max unique jobs per day controlled by `MOLD_SCHEDULE_MAX_JOBS_PER_DAY` (default 10)
- line molds: max 30/day total and max 6 per job/day
- floor molds: max 3/day total
- jobs can split across days as needed

The scheduler also writes mold-input diagnostics for non-OK rows when SQL data is used.

## Outputs

### Shared folder layout

FMES uses `S:\FMES` by default. The root can be changed with `FMES_SCHEDULE_ROOT` in the local `.env` file or process environment.

- Input workbooks and compatibility data are read from `S:\FMES\Input_Files`
- Generated workbooks, logs, backups, history, and report packs are written beneath `S:\FMES\Output_Files`

The mapped Windows share must be available to the user account running FMES.

### Combined workbook

Current combined workbook assembly is handled by [src/fmes/scheduler_export.py](src/fmes/scheduler_export.py) and includes:

- Overall Summary
- Melt Schedule
- Melt Diagnostics
- Mold Schedule
- Melt Summary
- Mold Summary
- Mold Input Diagnostics (when diagnostics rows exist)

### Report pack

When `--report-pack-dir` is provided or email output is required, [src/fmes/report_pack.py](src/fmes/report_pack.py) writes:

- `run_summary.json`
- `job_shipping_outlook.csv`
- `jobs_requiring_attention.csv`
- `daily_capacity_summary.csv`
- `report_pack.xlsx`
- `Open_Order_Report_Updated_YYYYMMDD_HHMMSS.xlsx` (copy of the current OOR if available)
- `distribution_manifest.json`

### SQL sync artifacts

During SQL sync, [src/fmes/scheduler_io.py](src/fmes/scheduler_io.py) also writes:

- OOR backup copy
- historical OOR snapshot
- historical DB snapshot workbook

## Email and Reporting Behavior

Email dispatch is implemented in [src/fmes/report_email.py](src/fmes/report_email.py).

Current behavior:

- interactive frozen-app launches prompt for recipients before scheduling
- recipient updates are stored in `%LOCALAPPDATA%\FMES Scheduler\settings.json`
- credentials remain in a separate local `.env` instead of the repo or shared folder
- a one-run recipient override can be passed on the command line
- `--no-pause` skips the interactive prompt for automated runs
- default transport is `outlook`; `smtp` is also supported via `--email-transport`
- `distribution_manifest.json` drives recipients and attachments for configured audiences

Send precedence in the main CLI flows:

1. explicit `--send-report-email`
2. `FMES_SEND_REPORT_EMAIL` environment variable
3. default `True` for frozen executable runs, `False` for normal Python CLI runs

## CLI Usage

### Full scheduler

```powershell
.venv\Scripts\python.exe run_scheduler.py --source sql --output-file "C:\Path\Production Schedule Summary.xlsx"
```

### OOR-only scheduler

```powershell
.venv\Scripts\python.exe run_oor_schedule.py --output-file "C:\Path\Production Schedule Summary.xlsx"
```

### Common options

- `--source sql|excel` (full scheduler only)
- `--output-file <path>`
- `--report-pack-dir <path|default>`
- `--send-report-email`
- `--email-test-recipient <email>`
- `--email-audiences production,order_entry,shipping`
- `--email-transport smtp|outlook`
- `--no-pause`

## Environment Variables

Database and SQL:

- `DB_DRIVER`
- `DB_SERVER`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_CONNECTION_STRING` (optional alternative)

Pathing and source behavior:

- `FMES_SCHEDULE_ROOT`
- `SCHEDULER_INPUT_SOURCE`
- `FMES_SHIPPING_TABLE_WORKBOOK`
- `FMES_SHIPPING_TABLE_SOURCE_SHEET`
- `FMES_OOR_SHIPPING_TABLE_SHEET`

Email:

- `FMES_SEND_REPORT_EMAIL`
- `FMES_EMAIL_TEST_RECIPIENT`
- `FMES_EMAIL_TRANSPORT`
- `FMES_OUTLOOK_FROM`
- `FMES_SMTP_HOST`
- `FMES_SMTP_PORT`
- `FMES_SMTP_FROM`
- `FMES_SMTP_USERNAME`
- `FMES_SMTP_PASSWORD`
- `FMES_SMTP_USE_STARTTLS`

Copy [.env.example](.env.example) to `%LOCALAPPDATA%\FMES Scheduler\.env` for both source runs and installed executables. This keeps credentials outside the repository and the shared `S:\FMES` folder. Values in this local file override inherited Windows environment variables, and the file is not tracked by Git.

## Build and Packaging

Build versioned executables:

```powershell
.\build_scheduler.ps1 -VersionLabel 0.83
```

Artifacts are emitted to:

- `%LOCALAPPDATA%\SchedulerProgram\PyInstaller\release_<VersionLabel>`

### Windows installer

Installer sources:

- [installer/SchedulerInstaller.iss](installer/SchedulerInstaller.iss)
- [installer/FirstRun-Checklist.txt](installer/FirstRun-Checklist.txt)
- [build_installer.ps1](build_installer.ps1)

Build installer:

```powershell
.\build_installer.ps1
```

### Prerequisite setup helper

Build a Windows helper for installing the ODBC driver and creating/opening the per-user local config:

```powershell
.\build_fmes_prerequisite_setup.ps1 -VersionLabel 0.90
```

## Testing

Run full unittest discovery:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Run the focused fast test suite:

```powershell
.\run_fast_tests.ps1
```

## Roadmap Notes

The project is considered complete for the current operational scope. Future ideas remain possible, but they are intentionally tracked as notes rather than active roadmap phases:

- persistent schedule state and WIP tracking
- expanded department-level scheduling for casting and cleaning
- BI / Power BI integration and historical KPI reporting
- automated cert-print validation
- additional ERP and optimization work

## Troubleshooting Notes

- If the Open Order Report workbook is open or locked, SQL sync can fail during export or copy operations; close the workbook and rerun.
- If Outlook transport is selected, Outlook desktop and `pywin32` are required.
- If SMTP transport is selected, the required `FMES_SMTP_*` variables must be present.
