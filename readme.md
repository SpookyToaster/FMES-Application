# Production Scheduler

**Author:** Logan Burkardt  
**Last Updated:** August 3, 2026

---

## Overview

Production Scheduler is a Python-based mold scheduling tool that reads the Open Order Report, filters eligible jobs, expands them into schedule rows, assigns production days, and exports a formatted mold schedule workbook.

The program now uses a modular layout instead of a single monolithic script. [Scheduler.py](Scheduler.py) is the orchestration entrypoint, while the core work lives in dedicated modules for input, filtering, schedule building, and export.

---

## Status Snapshot

### Completed

- Modular refactor of mold scheduling logic into dedicated modules
- Merge conflict cleanup and stable orchestration entrypoint
- Unit and integration test coverage for scheduling boundaries
- Local credential hardening using environment variables
- Startup environment validation utility for DB configuration

### In Progress

- SQL Server integration beyond basic connection setup
- Persistent schedule state between runs

### Not Started

- Melt, casting, and cleaning schedule pipelines
- Automated reporting and distribution
- Power BI data publication pipeline

---

## Current Structure

### Orchestration

- [Scheduler.py](Scheduler.py) coordinates the full scheduling pipeline.
- It loads input, filters jobs, builds schedule rows, assigns days, groups by day, prints summaries, and exports the final workbook.

### Module Boundaries

- [scheduler_io.py](scheduler_io.py) reads the Open Order Report workbook.
- [scheduler_filter.py](scheduler_filter.py) filters rows down to jobs eligible for molding.
- [scheduler_build.py](scheduler_build.py) expands jobs into extensions, assigns days, and builds daily schedule views.
- [scheduler_export.py](scheduler_export.py) builds export blocks, prints them, and writes the Excel schedule file.

### Tests

- [tests/test_database.py](tests/test_database.py)
- [tests/test_scheduler_io.py](tests/test_scheduler_io.py)
- [tests/test_scheduler_filter.py](tests/test_scheduler_filter.py)
- [tests/test_scheduler_build.py](tests/test_scheduler_build.py)
- [tests/test_scheduler_export.py](tests/test_scheduler_export.py)
- [tests/test_scheduler_integration.py](tests/test_scheduler_integration.py)

---

## Current Behavior

### Input Processing

- Reads the Open Order Report from the configured Excel file.
- Strips whitespace from column headers after loading.
- Filters out rows that are not eligible for molding.
- Uses modular orchestration to run each scheduling stage.

### Scheduling Rules

- Skips blank jobs.
- Skips jobs on hold.
- Skips jobs already scheduled.
- Skips investment cast jobs (`IFA`, `IFC`, and cast type `I`).
- Skips jobs requiring zero or fewer molds.
- Splits large jobs into extensions based on the daily mold limit.
- Assigns each schedule row to a day while respecting bucket capacity and per-part daily limits.

### Export Output

- Builds daily schedule blocks.
- Prints day-by-day mold totals.
- Exports a formatted Excel workbook named `Mold Schedule.xlsx`.

---

## Runtime Flow

```text
Open Order Report.xlsx
        │
        ▼
Read_File()
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
python -m unittest discover -s tests -p "test_*.py"
```

The current suite covers:

- database environment validation
- file loading
- filtering rules
- job expansion and day assignment
- export block generation and workbook writing
- end-to-end orchestration

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

For development priorities, see [Roadmap.md](Roadmap.md).