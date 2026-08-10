# Scheduler Session Context - 2026-08-10

## Current Direction

The scheduler is moving away from the earlier mold-first behavior and toward a heat-first planning flow with mold backfill.

The latest direction that appears more promising is:

1. Filter melt-planning input to jobs due within the next 10 weeks only.
2. Group incoming melt rows by alloy compatibility group first so heats are maximized within alloy groups.
3. Keep the fast iteration loop focused on targeted tests and non-export preview commands instead of full workbook exports.

## Business Rules In Effect

- Melt planning horizon: next 10 weeks only.
- Highest priority window: next 2 weeks.
- Planned heats per day: 5.
- Reserved heat slot: slot 6 stays open.
- Heat limits:
  - at or under 2300 lbs per heat when combining rows
  - at or under 10 molds per heat when combining rows
- Mold scheduling still backfills from planned heats.
- Molds must be made before pour.
- Molds should not sit more than 3 days before pour.
- L/F buckets do not determine heats.
- Casting type drives line/floor classification.

## What Changed In This Session

### 1. 10-week melt horizon

Updated melt input filtering from 56 days to 70 days.

Key code changes:
- `src/fmes/melt_planning.py`
  - `PRIORITY_REVIEW_WINDOW_DAYS = 70`
  - review window labels changed to `Next 10 Weeks` and `Outside 10 Weeks`
- `src/fmes/scheduler.py`
  - melt input filter still occurs before `build_melt_schedule(...)`
  - now filters rows where `Days Until Due <= 70`

### 2. Faster iteration workflow

Added a one-command targeted test runner:
- `run_fast_tests.ps1`

This runs only:
- `tests.test_melt_planning`
- `tests.test_scheduler_integration`
- `tests.test_mold_schedule_from_melt`

### 3. Alloy-group-first melt planning direction

The melt planning pipeline now explicitly reorders prioritized rows to maximize batching inside compatibility groups before heat assignment.

New behavior in `src/fmes/melt_planning.py`:
- `prioritize_schedule_rows(...)` now primarily sorts by priority and due date without prematurely interleaving by alloy group.
- `order_rows_for_alloy_grouping(...)` was added.
- `build_melt_schedule(...)` now does:
  1. `prioritize_schedule_rows(...)`
  2. `order_rows_for_alloy_grouping(...)`
  3. `assign_heat_numbers(...)`

Alloy grouping order logic:
- sort by planning priority rank
- then compatibility group
- then alloys marked `Compatible With ASTM Group = YES` first
- then alloy
- then due date
- then job number / extension sequence

Intent:
- make each compatibility group run together
- prefer broader anchor alloys first when possible
- improve same-group heat utilization before mold backfill starts

### 4. Live melt grouping preview command

Added:
- `run_heat_grouping_preview.py`

Purpose:
- inspect how current input is grouped into heats without needing full export files

It reports:
- eligible jobs
- extension rows before horizon
- extension rows inside the 70-day horizon
- alloy group totals
- heat summary by pour day
- detailed planned rows with group/alloy/heat/day

## Files Changed During This Session

- `src/fmes/melt_planning.py`
- `src/fmes/scheduler.py`
- `tests/test_melt_planning.py`
- `tests/test_scheduler_integration.py`
- `run_fast_tests.ps1`
- `run_heat_grouping_preview.py`
- `readme.md`

## Current Validation Status

### Targeted test command

```powershell
.\run_fast_tests.ps1
```

Latest result:
- 16 tests ran
- all passed

### Direct melt grouping preview command

```powershell
python.exe .\run_heat_grouping_preview.py --source excel --max-detail-rows 80
```

Latest result:
- exit code 0
- preview generated successfully from current Excel OOR

## Latest Live Data Snapshot From Preview

Using the current Excel source:

- Eligible jobs: 55
- Extension rows before horizon: 96
- Extension rows in <= 70-day horizon: 81

Selected alloy group totals from the preview:

- `CF8M`: 24 rows, 109 molds, 30207.95 lbs, 19 heats
- `A216 / WCB`: 19 rows, 57 molds, 29515.01 lbs, 16 heats
- `CA15 W`: 10 rows, 24 molds, 17504.88 lbs, 10 heats
- `CA40 W`: 9 rows, 38 molds, 15083.91 lbs, 8 heats
- `A148 / 130-115`: 4 rows, 20 molds, 7478.10 lbs, 4 heats

Observed from the preview:
- grouped runs are now clearly clustered by compatibility group/alloy across consecutive pour days
- the grouping behavior is much easier to inspect than before
- this appears to be a better planning direction than the prior approach

## Tests Added / Updated

### Added or updated for 10-week horizon

- `tests/test_scheduler_integration.py`
  - boundary coverage for 70-day include vs 71-day exclude
- `tests/test_melt_planning.py`
  - 70/71 day review-window boundary test

### Added for alloy grouping direction

- `tests/test_melt_planning.py`
  - test confirming a `Compatible With ASTM Group = YES` anchor is preferred so compatible rows can stay in one heat

## Useful Commands To Resume Quickly Tomorrow

### Run fast tests

```powershell
.\run_fast_tests.ps1
```

### Preview heat grouping from current Excel OOR

```powershell
python.exe .\run_heat_grouping_preview.py --source excel --max-detail-rows 80
```

### Run full scheduler if needed

```powershell
.\.venv\Scripts\python.exe run_scheduler.py
```

### Run heat-only export if needed

```powershell
.\.venv\Scripts\python.exe run_heat_schedule.py --source excel --heat-output-file "C:\Users\lburkardt\OneDrive - MonettMetalsUS1\Quality\Schedule\Output\Heat Summary.xlsx" --no-pause
```

## Recommended Next Step For Tomorrow

Use the grouping preview as the main inspection tool and answer this question next:

Does grouping by compatibility group maximize useful heats without causing poor due-date behavior inside each group?

Practical next checks:
- inspect whether overdue / near-due rows are ever delayed too much by same-group batching
- inspect whether large same-alloy jobs are monopolizing early pour days
- decide whether grouping should stay global across the horizon or be constrained inside smaller due-date bands
- if needed, add a second preview that summarizes by job and due date after grouping

## Resume Prompt Suggestion

If resuming tomorrow, a good restart prompt would be:

"Continue from Session_Context_2026-08-10.md. Keep the 10-week melt horizon. Use the alloy-group-first melt planning direction and inspect whether the grouped heats are still respecting due-date urgency. Prefer fast tests and grouping previews over full exports unless needed."
