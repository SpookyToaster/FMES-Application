# Roadmap

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

---

## Phase 1 - Refactoring & Foundation

### Code Organization

- Split scheduler into logical modules
- Centralize configuration and constants
- Implement a database abstraction layer
- Improve logging and error handling

### Data Infrastructure

- Migrate scheduler data storage to SQL Server
- Establish reporting tables
- Create foundational database views

---

## Phase 2 - Persistent Scheduling

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