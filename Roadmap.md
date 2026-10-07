# FMES Roadmap

**Status:** Complete for the current operational scope.

## Current Program Status

The FMES scheduling application is considered complete for the active production workflow. It now provides a stable pipeline for SQL/OOR-driven scheduling, workbook export, production visibility summaries, and report-pack/email distribution.

## Completed Scope

- Modular scheduling architecture under [src/fmes](src/fmes)
- Live SQL input, OOR refresh, and workbook synchronization
- Mold scheduling logic, validation, diagnostics, and export generation
- Melt planning and production visibility rollups
- Report-pack generation for operational consumption
- Email delivery with local recipient management and audience targeting
- Windows build, installer, and prerequisite setup tooling
- Automated validation coverage for configuration, export, and reporting behavior

## Notes / Deferred Ideas

These items are not active roadmap work for the current release, but they remain reasonable future enhancements if the program expands beyond the present scheduling and reporting scope:

- Persistent schedule state and tracked WIP progression
- Expanded cast/clean department scheduling and production status tracking
- Power BI or analytics publishing for historical metrics
- Automated cert printing workflow validation
- Additional ERP integration and optimization opportunities

## Recommendation

Treat the project as feature-complete for the current operating model. Future work should be handled as isolated enhancement items rather than active roadmap phases.