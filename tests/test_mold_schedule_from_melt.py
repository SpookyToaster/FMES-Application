import sys
from pathlib import Path
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fmes.config import Columns
from fmes.melt_planning import build_melt_schedule
from fmes.scheduler_build import assign_mold_days_from_heat_plan


class MoldScheduleFromMeltTests(unittest.TestCase):
    def test_backfilled_mold_schedule_preserves_melt_plan_mold_totals(self):
        schedule_rows = pd.DataFrame([
            {
                Columns.COL_JOB_NUMBER: "MS1001",
                Columns.COL_ALLOY: "LEW15",
                Columns.COL_CAST_TYPE: "L",
                Columns.COL_POUR_WEIGHT: 100,
                Columns.COL_DUE_DATE: "2026-08-20",
                "EXT": "A",
                "Extension_Seq": 0,
                "Molds for EXT": 8,
                "Total Weight per EXT": 800,
            },
            {
                Columns.COL_JOB_NUMBER: "MS1002",
                Columns.COL_ALLOY: "LEW15",
                Columns.COL_CAST_TYPE: "L",
                Columns.COL_POUR_WEIGHT: 100,
                Columns.COL_DUE_DATE: "2026-08-21",
                "EXT": "A",
                "Extension_Seq": 0,
                "Molds for EXT": 5,
                "Total Weight per EXT": 500,
            },
            {
                Columns.COL_JOB_NUMBER: "MS1003",
                Columns.COL_ALLOY: "WCB",
                Columns.COL_CAST_TYPE: "F",
                Columns.COL_POUR_WEIGHT: 350,
                Columns.COL_DUE_DATE: "2026-08-22",
                "EXT": "A",
                "Extension_Seq": 0,
                "Molds for EXT": 3,
                "Total Weight per EXT": 1050,
            },
        ])

        melt_schedule = build_melt_schedule(schedule_rows)
        planned_heat_rows = pd.concat(
            [day_plan["rows"] for day_plan in melt_schedule.values()],
            ignore_index=True,
        )

        assigned_mold_rows, _ = assign_mold_days_from_heat_plan(planned_heat_rows)

        planned_totals = (
            planned_heat_rows.groupby(
                [Columns.COL_JOB_NUMBER, "EXT", "Pour Schedule Day", "Heat #"],
                as_index=False,
            )["Molds for EXT"]
            .sum()
            .rename(columns={"Molds for EXT": "PlannedMolds"})
        )

        assigned_totals = (
            assigned_mold_rows.groupby(
                [Columns.COL_JOB_NUMBER, "EXT", "Pour Schedule Day", "Heat #"],
                as_index=False,
            )["Molds for EXT"]
            .sum()
            .rename(columns={"Molds for EXT": "AssignedMolds"})
        )

        comparison = planned_totals.merge(
            assigned_totals,
            on=[Columns.COL_JOB_NUMBER, "EXT", "Pour Schedule Day", "Heat #"],
            how="left",
        )

        self.assertTrue((comparison["PlannedMolds"] == comparison["AssignedMolds"]).all())

    def test_backfilled_mold_schedule_is_on_or_before_pour_day(self):
        schedule_rows = pd.DataFrame([
            {
                Columns.COL_JOB_NUMBER: "MS2001",
                Columns.COL_ALLOY: "LEW15",
                Columns.COL_CAST_TYPE: "L",
                Columns.COL_POUR_WEIGHT: 100,
                Columns.COL_DUE_DATE: "2026-08-20",
                "EXT": "A",
                "Extension_Seq": 0,
                "Molds for EXT": 9,
                "Total Weight per EXT": 900,
            },
            {
                Columns.COL_JOB_NUMBER: "MS2002",
                Columns.COL_ALLOY: "MN STEEL",
                Columns.COL_CAST_TYPE: "L",
                Columns.COL_POUR_WEIGHT: 200,
                Columns.COL_DUE_DATE: "2026-08-23",
                "EXT": "A",
                "Extension_Seq": 0,
                "Molds for EXT": 10,
                "Total Weight per EXT": 2000,
            },
            {
                Columns.COL_JOB_NUMBER: "MS2003",
                Columns.COL_ALLOY: "WCB",
                Columns.COL_CAST_TYPE: "F",
                Columns.COL_POUR_WEIGHT: 350,
                Columns.COL_DUE_DATE: "2026-08-24",
                "EXT": "A",
                "Extension_Seq": 0,
                "Molds for EXT": 4,
                "Total Weight per EXT": 1400,
            },
        ])

        melt_schedule = build_melt_schedule(schedule_rows)
        planned_heat_rows = pd.concat(
            [day_plan["rows"] for day_plan in melt_schedule.values()],
            ignore_index=True,
        )

        assigned_mold_rows, day_offset = assign_mold_days_from_heat_plan(planned_heat_rows)

        self.assertFalse(assigned_mold_rows.empty)
        self.assertGreaterEqual(day_offset, 0)
        self.assertTrue(
            (
                assigned_mold_rows["Schedule Day"]
                <= (assigned_mold_rows["Pour Schedule Day"] + day_offset)
            ).all()
        )


if __name__ == "__main__":
    unittest.main()
