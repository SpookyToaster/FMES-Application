# Production Scheduler

**Author:** Logan Burkardt  
**Last Updated:** July 13, 2026 @ 12:41 PM

---

## Current Functionality

The scheduler currently:

- Reads **Open Order Report (OOR).xlsx**
- Identifies jobs ready for molding
- Automatically excludes:
  - On Hold jobs
  - Already Scheduled jobs
  - Jobs requiring 0 molds
  - Investment castings (`IFA`, `IFC`, `I`)

---

## Planned Development

### Scheduling
- Push mold schedule into daily production schedule
- Build Melt WIP schedule
- Build Casting/Cleaning WIP schedule

### Automation
- Automate database exports
- Consolidate file repositories into a single location

---

## Description

This application reads the **Open Order Report (OOR)**, filters jobs that are ready for molding, and builds a mold schedule while respecting daily mold capacity limits.

### Key Features

- Job filtering and qualification
- Schedule generation
- Daily mold capacity management
- Multi-extension job expansion
- Day assignment logic
- Schedule reporting by bucket

---

## Planned Refactor

### Target Project Structure

```text
scheduler/
│
├── Scheduler.py          # Main entry point
├── config.py             # Constants and settings
├── schedule_logic.py     # Filtering, splitting, day assignment
├── schedule_builder.py   # Daily schedule creation
├── exports.py            # Excel export functions
├── io_utils.py           # File reading utilities
└── models.py             # Data models (future)
```

---

## System Architecture

```text
Production ERP / MES
        │
        │ Nightly Refresh
        ▼
SQL Server 2022 (Reporting Copy)
        │
        ├── Python Scheduler
        │
        ├── Power BI
        │
        └── Ad Hoc Analysis
```

---

## Long-Term Vision

Move scheduling logic away from manually maintained spreadsheets and toward a centralized reporting database that supports:

- Automated schedule generation
- Production planning
- WIP tracking
- Reporting and analytics
- Power BI integration
- Reduced manual data entry