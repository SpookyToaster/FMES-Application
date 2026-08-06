# Roadmap

**Last Updated:** August 6, 2026

## Vision

The long-term goal is to evolve this application from a spreadsheet-based mold scheduler into a production planning and visibility platform.

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

- Mold scheduling pipeline refactored into modular files
- Orchestration flow stabilized in [Scheduler.py](Scheduler.py)
- Boundary test suite added for IO, filtering, building, export, integration, and DB environment checks
- Credential handling moved to local environment variables
- DB startup environment validator added in [check_db_env.py](check_db_env.py)
- Historical snapshot SQL schema and loader pipeline implemented ([HistoricalReporting_ERP_Exact.sql](HistoricalReporting_ERP_Exact.sql), [load_historical_snapshot.py](load_historical_snapshot.py))
- DB metadata discovery and dashboard data access methods implemented in [DB_IO.py](DB_IO.py)
- Production-ready dashboard SQL query pack added in [Production_Report_Queries.sql](Production_Report_Queries.sql)

### In Progress

- DB report read layer is implemented; application-level orchestration of automated dashboard refresh/export is still in progress
- Error handling is present across scheduling and DB entrypoints, with room for centralized logging
- Schedule persistence model is still not in use for run-to-run carryforward

### Open Gaps

- Persistent schedule state
- Production WIP tracking
- Automated reporting and BI publishing

---

## Phase 1 - Refactoring & Foundation

### Status: Complete (with targeted follow-ups)

### Code Organization

- Completed: split scheduler into logical modules
- Partially completed: centralize configuration and constants
- Completed: implement core database access layer for configuration, metadata, and report retrieval
- Partially completed: improve error handling
- Not started: structured application logging

### Data Infrastructure

- Partially completed: establish historical reporting tables and lifecycle upsert path
- Completed: create production query definitions for Orders/Main dashboard data sets
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

- Build melt scheduling logic
- Track melt work-in-progress

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

1. Add SQL Server schedule run-state tables and write path for each scheduler execution.
2. Preserve prior run assignments to reduce schedule churn between runs.
3. Wire [DB_IO.py](DB_IO.py) dashboard methods into scheduled exports/distribution and add structured logging for DB and pipeline stages.