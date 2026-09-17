# Foundry Management and Execution System (FMES)

Author: Logan Burkardt  
Last Updated: 2026-09-17

## Overview

FMES is a Python scheduling program. It supports two run modes:

- Full mode: pull live SQL data, update Open Order Report (OOR), schedule jobs, and export workbooks.
- OOR-only mode: skip SQL sync and build schedules from the existing OOR workbook.

Primary entrypoints:

- [run_scheduler.py](run_scheduler.py): full CLI launcher (source can be SQL or Excel)
- [run_oor_schedule.py](run_oor_schedule.py): OOR-only launcher (forces Excel source)
- [src/fmes/main.py](src/fmes/main.py): full run orchestration
- [src/fmes/oor_main.py](src/fmes/oor_main.py): OOR-only CLI wrapper

Core source package: [src/fmes](src/fmes)

## Runtime Flow

Full scheduler flow:

1. Resolve source from --source or SCHEDULER_INPUT_SOURCE (default sql).
2. If source is sql:
    - validate database configuration,
    - sync live SQL data into the OOR workbook,
    - refresh OOR Shipping Table sheet from Shipping Table.xlsx (when available).
3. Read scheduler input (SQL or Excel) and apply normalization.
4. Filter schedulable jobs.
5. Build scheduler rows and assign mold schedule days.
6. Build export blocks and job shipping outlook rows.
7. Write combined Production Schedule Summary workbook.
8. Optionally write report-pack artifacts.
9. Optionally send report-pack email.

OOR-only flow:

- Forces SCHEDULER_INPUT_SOURCE=excel.
- Skips SQL validation and SQL sync.
- Runs scheduling/export on the workbook contents already in OOR.

## SQL Mold Derivation Logic

Live SQL rows for scheduler input come from [src/fmes/db_io.py](src/fmes/db_io.py) using MAIN_DASHBOARD_LIVE_SQL.

Current castings-per-mold fallback precedence:

1. JCJobMaster.TOOLIMPRESSIONS
2. ICMaster.CASTINGSPERMOLD
3. ICPattern.PATTERNIMPRESSIONS
4. BOM fallback only when BOM tool impressions are present and consistent
5. missing/unknown when no non-zero source is available

The query also emits a derivation source label in Molds Derivation Source:

- JOBMASTER
- ICMASTER
- PATTERN
- BOM_CONSISTENT
- BOM_CONFLICT
- MISSING

Quantity of Molds is derived from QTY Ordered / effective Castings Per Mold when possible; otherwise it falls back to ERP molds required.

## Diagnostics and Validation

When source=sql, FMES builds mold input diagnostics from scheduler input and exports non-OK rows.

Diagnostic flags include:

- BOM_CONFLICT_NO_FALLBACK
- NO_EFFECTIVE_TOOL_IMPRESSIONS
- USED_PATTERN_FALLBACK
- USED_BOM_FALLBACK
- ERP_MOLDS_MISMATCH

These rows are exported into a Mold Input Diagnostics worksheet in mold/combined outputs.

## Scheduling Rules (Current)

Eligibility filtering in [src/fmes/scheduler_filter.py](src/fmes/scheduler_filter.py):

- blank Job Number excluded
- Hold = YES excluded
- Job Type IFA/IFC excluded
- Casting Type I excluded
- Molds Needed <= 0 excluded

Mold-day assignment in [src/fmes/mold_console_schedule.py](src/fmes/mold_console_schedule.py):

- due-date driven ordering with compatibility-group tie-breaking
- max unique jobs per day controlled by MOLD_SCHEDULE_MAX_JOBS_PER_DAY (default 10)
- line molds: max 30/day total and max 6 per job/day
- floor molds: max 3/day total
- jobs can split across days as needed

## Outputs

### Combined workbook

Default path:

- Paths.COMBINED_SCHEDULE_OUTPUT from [src/fmes/config.py](src/fmes/config.py)
- Typical file name: Production Schedule Summary.xlsx

Current combined workbook assembly is handled by [src/fmes/scheduler_export.py](src/fmes/scheduler_export.py) and includes:

- Overall Summary
- Melt Schedule
- Melt Diagnostics
- Mold Schedule
- Melt Summary
- Mold Summary
- Mold Input Diagnostics (when diagnostics rows exist)

### Report pack (optional)

When --report-pack-dir is provided (or when email sending requires report-pack output), [src/fmes/report_pack.py](src/fmes/report_pack.py) writes:

- run_summary.json
- job_shipping_outlook.csv
- jobs_requiring_attention.csv
- daily_capacity_summary.csv
- report_pack.xlsx
- Open_Order_Report_Updated_YYYYMMDD_HHMMSS.xlsx (copy of current OOR if available)
- distribution_manifest.json

### SQL sync artifacts

During SQL sync, [src/fmes/scheduler_io.py](src/fmes/scheduler_io.py) also writes:

- OOR backup copy
- historical OOR snapshot
- historical DB snapshot workbook

## Email Behavior

Email send path is implemented in [src/fmes/report_email.py](src/fmes/report_email.py).

Send decision precedence in full/OOR CLI:

1. explicit --send-report-email
2. FMES_SEND_REPORT_EMAIL environment variable
3. default True for frozen executable runs, False for normal Python CLI runs

Transport:

- default: outlook
- options: smtp or outlook via --email-transport

Manifest-driven behavior:

- recipients and attachments come from distribution_manifest.json
- when --email-test-recipient is provided, it overrides manifest recipients
- attachment policy is intentionally narrowed to report_pack.xlsx and copied Open_Order_Report_Updated_*.xlsx

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

- --source sql|excel (full scheduler only)
- --output-file <path>
- --report-pack-dir <path|default>
- --send-report-email
- --email-test-recipient <email>
- --email-audiences production,order_entry,shipping
- --email-transport smtp|outlook
- --no-pause

## Environment Variables

Database and SQL:

- DB_DRIVER
- DB_SERVER
- DB_NAME
- DB_USER
- DB_PASSWORD
- DB_CONNECTION_STRING (optional alternative)

Pathing and source behavior:

- FMES_SCHEDULE_ROOT (overrides shared schedule root)
- SCHEDULER_INPUT_SOURCE (sql|excel default override)
- FMES_SHIPPING_TABLE_WORKBOOK
- FMES_SHIPPING_TABLE_SOURCE_SHEET
- FMES_OOR_SHIPPING_TABLE_SHEET

Email:

- FMES_SEND_REPORT_EMAIL
- FMES_EMAIL_TEST_RECIPIENT
- FMES_EMAIL_TRANSPORT
- FMES_OUTLOOK_FROM
- FMES_SMTP_HOST
- FMES_SMTP_PORT
- FMES_SMTP_FROM
- FMES_SMTP_USERNAME
- FMES_SMTP_PASSWORD
- FMES_SMTP_USE_STARTTLS

Reference template: [.env.example](.env.example)

## Testing

Run full unittest discovery:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Run fast focused tests:

```powershell
.\run_fast_tests.ps1
```

## Build and Packaging

Build versioned executables:

```powershell
.\build_scheduler.ps1 -VersionLabel 0.83
```

Artifacts are emitted to:

- %LOCALAPPDATA%\SchedulerProgram\PyInstaller\release_<VersionLabel>

Each release folder contains:

- Scheduler_<VersionLabel>.exe
- SchedulerUpdateOnly_<VersionLabel>.exe
- build-info.txt

### Windows installer (Inno Setup)

Installer sources:

- [installer/SchedulerInstaller.iss](installer/SchedulerInstaller.iss)
- [installer/FirstRun-Checklist.txt](installer/FirstRun-Checklist.txt)
- [build_installer.ps1](build_installer.ps1)

Build installer:

```powershell
.\build_installer.ps1
```

Default behavior:

- uses newest release_* folder under %LOCALAPPDATA%\SchedulerProgram\PyInstaller
- outputs FMES_Scheduler_Setup_<label>.exe in that release folder

## Troubleshooting Notes

- If Open Order Report.xlsx is open/locked, SQL sync can fail when exporting or copying workbook artifacts. Close the workbook and rerun.
- If Outlook transport is selected, Outlook desktop and pywin32 are required.
- If SMTP transport is selected, required FMES_SMTP_* variables must be present.
