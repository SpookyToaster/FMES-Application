# Foundry Management and Execution System (FMES)

Author: Logan Burkardt  
Last Updated: 2026-08-28

## Overview

FMES is a Python scheduling tool that can:

- Sync live SQL data into Open Order Report.xlsx (OOR)
- Normalize scheduler input fields for consistent downstream processing
- Filter jobs eligible for mold scheduling
- Build mold-day assignments
- Export a combined Production Schedule Summary workbook

The source code is organized under [src/fmes](src/fmes).

## Entrypoints

- [run_scheduler.py](run_scheduler.py): full runtime path (SQL or Excel source)
- [run_oor_schedule.py](run_oor_schedule.py): OOR-only mode (forces Excel source, skips SQL sync)
- [src/fmes/main.py](src/fmes/main.py): CLI and orchestration entrypoint
- [src/fmes/oor_main.py](src/fmes/oor_main.py): OOR-only CLI wrapper

CLI option for full runs:

- --report-pack-dir <path>: optional directory to emit Phase 3/4 reporting artifacts
- --report-pack-dir default: uses Paths.REPORT_PACK_DIR
- --send-report-email: sends report-pack files via SMTP after successful run
- --email-test-recipient <email>: overrides manifest recipients for safe test sends
- --email-audiences production,order_entry,shipping: optional audience filter
- --email-transport smtp|outlook: choose SMTP or installed Outlook desktop transport (default: outlook)

## Current Runtime Flow

Full run path:

1. Resolve source from CLI or SCHEDULER_INPUT_SOURCE
2. If source is SQL: validate DB settings and sync OOR workbook from SQL
3. Read scheduler input data frame
4. Filter rows in [src/fmes/scheduler_filter.py](src/fmes/scheduler_filter.py)
5. Build scheduler rows in [src/fmes/scheduler_build.py](src/fmes/scheduler_build.py)
6. Assign mold schedule days in [src/fmes/mold_console_schedule.py](src/fmes/mold_console_schedule.py)
7. Build export blocks and shipping summary rows in [src/fmes/scheduler_export.py](src/fmes/scheduler_export.py)
8. Export combined workbook using [src/fmes/scheduler_export.py](src/fmes/scheduler_export.py)

## SQL Sync Behavior (OOR Update)

During SQL sync, [src/fmes/scheduler_io.py](src/fmes/scheduler_io.py) does all of the following:

- Creates backup and historical OOR snapshots
- Pulls live scheduler rows from [src/fmes/db_io.py](src/fmes/db_io.py)
- Validates required text fields (due date, customer, part, job)
- Normalizes rows before writing to OOR
- Writes OOR range F2:V* while preserving workbook metadata
- Writes OOR Column A Hold values directly from SQL "On Hold" data (YES/NO)
- Writes a SQL snapshot workbook for audit/comparison

Important normalization rule now active:

- If Quantity of Molds is zero/non-positive and both QTY Ordered and Castings Per Mold are present,
  Quantity of Molds is derived as ceiling(QTY Ordered / Castings Per Mold).

This derived value is now written to OOR Column N because sync writes normalized rows, not raw SQL rows.

## Scheduling Rules (Current)

Eligibility filter in [src/fmes/scheduler_filter.py](src/fmes/scheduler_filter.py):

- Exclude blank job number
- Exclude hold = YES
- Exclude Job Type IFA/IFC
- Exclude Casting Type I
- Exclude Molds Needed <= 0

Row construction in [src/fmes/scheduler_build.py](src/fmes/scheduler_build.py):

- Uses one row per eligible job in the current branch
- Sets Molds for EXT from Molds Needed
- Computes Total Weight per EXT from Pour Weight * Molds for EXT

Mold-day assignment in [src/fmes/mold_console_schedule.py](src/fmes/mold_console_schedule.py):

- Enforces max jobs per day
- Enforces per-day and per-job mold capacity rules
- Splits large jobs across days when needed

## Outputs

Primary output workbook:

- Production Schedule Summary.xlsx (default path resolved from [src/fmes/config.py](src/fmes/config.py))

Optional reporting pack output (when --report-pack-dir is provided):

- run_summary.json
- job_shipping_outlook.csv
- jobs_requiring_attention.csv
- daily_capacity_summary.csv
- report_pack.xlsx (formatted multi-sheet workbook)
- Open_Order_Report_Updated_YYYYMMDD_HHMMSS.xlsx (copied from current OOR)
- distribution_manifest.json

Email routing model:

- distribution_manifest.json stores audience entries with enabled, recipients, and attachments
- email attachments are intentionally limited to report_pack.xlsx and Open_Order_Report_Updated_*.xlsx
- default recipients include sliles@monettmetals.com, BRaub@monettmetals.com, and lburkardt@monettmetals.com
- send mode can use manifest recipients or a one-off test recipient override

SMTP environment variables (required for send mode):

- FMES_SMTP_HOST
- FMES_SMTP_PORT (default 587)
- FMES_SMTP_FROM
- FMES_SMTP_USERNAME (optional)
- FMES_SMTP_PASSWORD (required when username is set)
- FMES_SMTP_USE_STARTTLS (default true)

Outlook desktop transport:

- Use --email-transport outlook to send via signed-in Outlook desktop profile.
- Outlook is the default send transport when no override is provided.
- Requires Outlook desktop installed and configured on the machine.
- Requires pywin32 in the Python environment.
- Optional FMES_OUTLOOK_FROM can set SentOnBehalfOfName when needed.

Supporting artifacts from SQL sync:

- Backups of Open Order Report.xlsx
- Historical OOR snapshots
- Historical DB snapshot workbooks

## Logging

Logging is configured in [src/fmes/main.py](src/fmes/main.py):

- Console output for operator visibility
- Monthly log file under Paths.LOG_DIR (fmes_YYYY-MM.log)

## Testing

Run full unit test suite:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -q
```

Run fast focused suite:

```powershell
.\run_fast_tests.ps1
```

Current baseline after latest changes:

- 63 tests passing via unittest discovery

## Build and Packaging

Build versioned executable artifacts with:

```powershell
.\build_scheduler.ps1 -VersionLabel 0.70
```

Build output location pattern:

- %LOCALAPPDATA%\SchedulerProgram\PyInstaller\release_<VersionLabel>

Example for revision 0.70:

- Scheduler_0.70.exe
- SchedulerUpdateOnly_0.70.exe
- build-info.txt

## Email Send Example

Test-send report pack to one address:

```powershell
.venv\Scripts\python.exe run_scheduler.py --source sql --report-pack-dir default --send-report-email --email-test-recipient lburkardt@monettmetals.com --no-pause
```

Outlook desktop send example:

```powershell
.venv\Scripts\python.exe run_scheduler.py --source sql --report-pack-dir default --send-report-email --email-test-recipient lburkardt@monettmetals.com --email-transport outlook --no-pause
```

## Maintainer Notes

- Keep scheduler behavior deterministic and easy to trace in logs.
- Prefer removing stale branch comments over preserving historical architecture notes.
- Keep tests aligned to current runtime behavior, especially around SQL normalization and OOR writes.
- Treat hidden mutable global state as a maintenance risk; prefer per-run state.
