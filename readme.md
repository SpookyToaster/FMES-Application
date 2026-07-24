# Production Scheduler

**Author:** Logan Burkardt  
**Last Updated:** July 24, 2026

---

## Overview

Production Scheduler is a Python-based manufacturing scheduling tool that generates mold schedules from the Open Order Report (OOR).

The application filters and prioritizes work ready for molding while enforcing daily mold capacity limits. The goal is to replace manual scheduling processes with a repeatable, data-driven workflow.

---

## Current Functionality

### Data Processing

- Reads **Open Order Report (OOR).xlsx**
- Identifies jobs ready for molding
- Expands jobs into required mold extensions
- Assigns jobs to available production days

### Automatic Exclusions

The scheduler automatically excludes:

- On Hold jobs
- Already Scheduled jobs
- Jobs requiring zero molds
- Investment castings (`IFA`, `IFC`, `I`)

### Scheduling Features

- Job qualification and filtering
- Mold schedule generation
- Daily mold capacity management
- Multi-extension job handling
- Schedule bucket assignment
- Schedule reporting and export

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

## Business Objective

The scheduler provides a centralized and repeatable method for planning molding operations while reducing manual effort, spreadsheet maintenance, and scheduling inconsistencies.

Key objectives include:

- Improving schedule accuracy
- Increasing production visibility
- Reducing manual planning effort
- Supporting future production reporting
- Providing a foundation for WIP tracking and analytics

---

## Technology Stack

- Python
- SQL Server 2022
- ODBC Connectivity
- Excel-Based Inputs
- Power BI Reporting

---

## Future Direction

The long-term vision is to evolve the scheduler into a production planning and visibility platform that supports:

- Persistent schedule management
- Work-in-progress (WIP) tracking
- Melt, Casting, and Cleaning schedules
- Historical schedule analysis
- Automated reporting and notifications
- Power BI dashboards and analytics

For planned enhancements and development priorities, see **ROADMAP.md**.