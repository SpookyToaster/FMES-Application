# FMES Roadmap

**Last Updated:** August 10, 2026

## Vision

The long-term goal is to evolve Foundry Management and Execution System (FMES) from a spreadsheet-based mold scheduler into a production planning and visibility platform.

### Objectives

- Generate and manage mold schedules
- Track WIP across production departments
- Maintain schedule history
- Support production reporting
- Integrate with SQL Server
- Publish data to Power BI
- Distribute reports automatically to users

## Guiding Principle

Do not optimize for the perfect schedule.

Optimize for:

- Stability
- Recoverability
- Ease of execution
- Minimal planner intervention

Production conditions will change daily. The system should adapt rather than attempting to predict perfectly.

---

## Current Program Status

### Completed

- Mold scheduling pipeline refactored into modular files under the `src/fmes` package (snake_case naming throughout)
- Orchestration flow stabilized in [src/fmes/scheduler.py](src/fmes/scheduler.py) with [run_scheduler.py](run_scheduler.py) as the entrypoint
- Configuration centralized in [src/fmes/config.py](src/fmes/config.py): single `SCHEDULE_ROOT` with env-var override; no hard-coded user paths
- Dependency manifests ([pyproject.toml](pyproject.toml), [requirements.txt](requirements.txt)) and build-artifact `.gitignore` coverage
- Structured logging (console + monthly file under `Quality\Schedule\Logs`)
- Boundary test suite for IO, filtering, building, export, melt planning, integration, and DB environment checks; live-DB tests split into `tests/integration/`
- SQL scheduler input validation adjusted to allow blank Alloy while maintaining strict required-field checks for critical scheduling columns
- Credential handling moved to local environment variables
- Historical snapshot SQL schema and loader pipeline implemented ([HistoricalReporting_ERP_Exact.sql](HistoricalReporting_ERP_Exact.sql), [src/fmes/load_historical_snapshot.py](src/fmes/load_historical_snapshot.py))
- DB metadata discovery and dashboard data access methods implemented in [src/fmes/db_io.py](src/fmes/db_io.py), including a trimmed Job Number report projection and a full scheduler projection
- ERP field mapping corrections: castings per mold from `JCJobMaster.TOOLIMPRESSIONS`; Total Pour WT derived when `POURQUANTITY` is unrecorded
- Production-ready dashboard SQL query pack added in [Production_Report_Queries.sql](Production_Report_Queries.sql)
- Alloy compatibility master data with directional co-pour rules, integrated into scheduler input
- Initial melt schedule builder ([src/fmes/melt_planning.py](src/fmes/melt_planning.py)) implementing the 5 planned + 1 reserved heat slot policy with overflow flagging
- Excel export hardening: calcChain cleanup and native numeric cell writes
- Dead-code cleanup pass (unused modules, placeholder configs, duplicate constants removed)

### In Progress

- Schedule persistence model is still not in use for run-to-run carryforward
- Planning model refinement in progress: heat-first with mold backfill, 10-week melt horizon, alloy-group-first batching, and planner preview tooling
- Due-date-vs-grouping tradeoff review is in progress against live OOR data before further optimization

### Open Gaps

- Persistent schedule state
- Production WIP tracking
- Automated reporting and BI publishing

---

## Phase 1 - Refactoring & Foundation

### Status: Complete

### Code Organization

- Completed: split scheduler into logical modules (`src/fmes` package layout)
- Completed: centralize configuration and constants ([src/fmes/config.py](src/fmes/config.py))
- Completed: implement core database access layer for configuration, metadata, and report retrieval
- Completed: consistent error wrapping across public entrypoints
- Completed: structured application logging (console + monthly file)

### Data Infrastructure

- Partially completed: establish historical reporting tables and lifecycle upsert path
- Completed: create production query definitions for the Main dashboard data set
- Not started: migrate scheduler run-state storage and scheduling decisions to SQL Server

---

## Phase 2 - Persistent Scheduling

### Status: Not Started

### Persistent Schedule State

#### Problem

The current scheduler generates a point-in-time schedule based solely on the current Open Order Report (OOR). Each run starts from scratch and does not consider:

- Previously scheduled work
- Jobs already released to production
- Work currently in progress (WIP)
- Existing schedule commitments

This can result in unnecessary schedule changes between runs.

#### Goal

Transform the scheduler from a static schedule generator into a persistent scheduling system that maintains state between runs.

#### Desired Behavior

Example schedule:

| Job | Extension | Scheduled Day |
|------|-----------|--------------|
| 1001 | A | Monday |
| 1001 | B | Tuesday |
| 1001 | C | Wednesday |

When the scheduler runs again on Tuesday:

- Recognize that Job 1001 has already been scheduled
- Preserve existing schedule assignments
- Avoid rescheduling started or completed work
- Schedule only new demand or legitimate schedule changes

#### Planned Capabilities

- Track scheduled job extensions
- Track released, started, and completed work
- Preserve prior scheduling decisions
- Maintain schedule history
- Minimize schedule churn between runs
- Support frozen scheduling windows

#### Proposed Implementation

Store schedule information in SQL Server using tables similar to:

```text
ScheduleRun
------------
RunID
RunDateTime

ScheduledJob
------------
JobNumber
Extension
ScheduledDate
Status
CreatedRunID
LastModified
```

---

## Phase 3 - Production Visibility

### Status: Not Started

### Daily Production Schedule Integration

- Push mold schedule into daily production scheduling process
- Improve production planning visibility

### Melt WIP Schedule

- Partially completed: melt planning is now part of the active orchestration path, using a 10-week horizon, 5 planned heats + 1 reserved contingency slot, alloy compatibility grouping, and mold backfill
- Remaining: validate grouping quality against due-date urgency, improve planner diagnostics, and track melt work-in-progress explicitly

### Alloy Chemistry Compatibility

- Completed: CSV master data (not hardcoded conditions) defines directional co-pour compatibility groups.
- Keep compatibility immutable by default, with controlled additive updates as new alloys are introduced.
- Remaining: validate unmapped alloys into an exception path to avoid silent pour-mix errors.

### Casting & Cleaning WIP Schedule

- Build casting schedule
- Build cleaning schedule
- Track job progression through production departments

### Production Status Tracking

- Monitor WIP across departments
- Improve schedule-to-production visibility

---

## Phase 4 - Reporting & Communication

### Status: Not Started

### Automated Reporting

- Generate and distribute scheduled reports
- Reduce manual report creation

### Email Distribution System

- Send reports to subscribed users
- Support configurable distribution lists
- Manage user-specific report preferences

### Preference Management

- Store user preferences in SQL Server
- Allow users to update preferences through email responses

---

## Phase 5 - Analytics & Business Intelligence

### Status: Not Started

### Power BI Integration

- Publish scheduling and production data
- Create centralized reporting datasets

### Historical Analytics

- Schedule history reporting
- Capacity utilization analysis
- Production KPI dashboards
- Trend analysis and forecasting

---

## Future Opportunities

- Automated database exports
- Consolidation of file repositories
- ERP integration enhancements
- Production performance metrics
- Advanced scheduling optimization

---

## Next 3 Priorities

1. Validate the current 10-week, alloy-group-first heat planner against live due-date behavior and refine the batching rules where urgency is harmed.
2. Preserve prior run assignments to reduce schedule churn between runs.
3. Expand planner diagnostics and alloy compatibility guardrails (group validation, unknown-alloy exceptions, preview/report integration).