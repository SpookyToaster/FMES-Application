import sys
from pathlib import Path
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fmes.config import Columns
from fmes.melt_planning import build_melt_schedule, prioritize_schedule_rows


class MeltPlanningTests(unittest.TestCase):
    def test_prioritize_schedule_rows_orders_due_windows_before_alloy_grouping(self):
        schedule_df = pd.DataFrame([
            {
                Columns.COL_JOB_NUMBER: "9303",
                Columns.COL_DUE_DATE: "2026-11-15",
                Columns.COL_ALLOY: "WCB",
                "Compatibility Group": "A216",
                "Extension_Seq": 0,
            },
            {
                Columns.COL_JOB_NUMBER: "9302",
                Columns.COL_DUE_DATE: "2026-09-05",
                Columns.COL_ALLOY: "80-40",
                "Compatibility Group": "A148",
                "Extension_Seq": 0,
            },
            {
                Columns.COL_JOB_NUMBER: "9301",
                Columns.COL_DUE_DATE: "2026-08-18",
                Columns.COL_ALLOY: "150-135",
                "Compatibility Group": "A148",
                "Extension_Seq": 0,
            },
        ])

        prioritized = prioritize_schedule_rows(
            schedule_df,
            reference_date="2026-08-10",
        )

        self.assertEqual(prioritized[Columns.COL_JOB_NUMBER].tolist(), ["9301", "9302", "9303"])
        self.assertEqual(prioritized["Planning Priority"].tolist(), ["Highest Priority", "Priority Review", "Standard"])

    def test_build_melt_schedule_reserves_slot_six(self):
        schedule_df = pd.DataFrame([
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "9001",
                Columns.COL_DUE_DATE: "2026-08-12",
                Columns.COL_ALLOY: "WCB",
                "Compatibility Group": "A216",
                "Compatible With ASTM Group": "YES",
                "Specific Compatible Alloys": "",
                "Total Weight per EXT": 1000,
                "Molds for EXT": 4,
                "Extension_Seq": 0,
                "EXT": "A",
            }
        ])

        melt_schedule = build_melt_schedule(schedule_df, reference_date="2026-08-10")
        summary = melt_schedule[1]["heat_summary"]

        self.assertEqual(melt_schedule[1]["planned_heat_count"], 1)
        self.assertEqual(melt_schedule[1]["reserved_heat_slots"], [6])
        self.assertEqual(summary.iloc[0]["Heat Status"], "Planned")
        self.assertEqual(summary.iloc[-1]["Heat Slot"], 6)
        self.assertEqual(summary.iloc[-1]["Heat Status"], "Reserved")
        self.assertEqual(summary.iloc[0]["Planning Priority"], "Highest Priority")

    def test_build_melt_schedule_groups_compatible_astm_alloys(self):
        schedule_df = pd.DataFrame([
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "9101",
                Columns.COL_DUE_DATE: "2026-08-20",
                Columns.COL_ALLOY: "80-40",
                "Compatibility Group": "A148",
                "Compatible With ASTM Group": "YES",
                "Specific Compatible Alloys": "",
                "Total Weight per EXT": 800,
                "Molds for EXT": 2,
                "Extension_Seq": 0,
                "EXT": "A",
            },
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "9102",
                Columns.COL_DUE_DATE: "2026-08-21",
                Columns.COL_ALLOY: "150-135",
                "Compatibility Group": "A148",
                "Compatible With ASTM Group": "YES",
                "Specific Compatible Alloys": "",
                "Total Weight per EXT": 900,
                "Molds for EXT": 2,
                "Extension_Seq": 1,
                "EXT": "B",
            },
        ])

        melt_schedule = build_melt_schedule(schedule_df, reference_date="2026-08-10")
        planned_rows = melt_schedule[1]["rows"]

        self.assertEqual(planned_rows["Heat #"].tolist(), [1, 1])
        self.assertEqual(melt_schedule[1]["planned_heat_count"], 1)

    def test_build_melt_schedule_starts_new_heat_when_mold_limit_is_exceeded(self):
        schedule_df = pd.DataFrame([
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "9151",
                Columns.COL_DUE_DATE: "2026-08-15",
                Columns.COL_ALLOY: "80-40",
                "Compatibility Group": "A148",
                "Compatible With ASTM Group": "YES",
                "Specific Compatible Alloys": "",
                "Total Weight per EXT": 800,
                "Molds for EXT": 6,
                "Extension_Seq": 0,
                "EXT": "A",
            },
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "9152",
                Columns.COL_DUE_DATE: "2026-08-16",
                Columns.COL_ALLOY: "150-135",
                "Compatibility Group": "A148",
                "Compatible With ASTM Group": "YES",
                "Specific Compatible Alloys": "",
                "Total Weight per EXT": 700,
                "Molds for EXT": 5,
                "Extension_Seq": 1,
                "EXT": "B",
            },
        ])

        melt_schedule = build_melt_schedule(schedule_df, reference_date="2026-08-10")
        planned_rows = melt_schedule[1]["rows"]

        self.assertEqual(planned_rows["Heat #"].tolist(), [1, 2])

    def test_build_melt_schedule_prioritizes_due_date_inside_two_weeks(self):
        schedule_df = pd.DataFrame([
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "9181",
                Columns.COL_DUE_DATE: "2026-08-11",
                Columns.COL_ALLOY: "WCB",
                "Compatibility Group": "G1",
                "Compatible With ASTM Group": "NO",
                "Specific Compatible Alloys": "",
                "Total Weight per EXT": 700,
                "Molds for EXT": 2,
                "Extension_Seq": 0,
                "EXT": "A",
            },
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "9182",
                Columns.COL_DUE_DATE: "2026-08-18",
                Columns.COL_ALLOY: "WCB",
                "Compatibility Group": "G1",
                "Compatible With ASTM Group": "YES",
                "Specific Compatible Alloys": "",
                "Total Weight per EXT": 700,
                "Molds for EXT": 2,
                "Extension_Seq": 1,
                "EXT": "B",
            },
        ])

        melt_schedule = build_melt_schedule(schedule_df, reference_date="2026-08-10")
        planned_rows = melt_schedule[1]["rows"]

        self.assertEqual(melt_schedule[1]["planned_heat_count"], 1)
        self.assertEqual(planned_rows["Heat #"].tolist(), [1, 1])
        self.assertEqual(planned_rows.iloc[0][Columns.COL_JOB_NUMBER], "9181")

    def test_build_melt_schedule_optimizes_non_urgent_rows_for_heat_fill(self):
        schedule_df = pd.DataFrame([
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "9501",
                Columns.COL_DUE_DATE: "2026-09-10",
                Columns.COL_ALLOY: "WCB",
                "Compatibility Group": "A216",
                "Compatible With ASTM Group": "YES",
                "Specific Compatible Alloys": "",
                "Total Weight per EXT": 1300,
                "Molds for EXT": 2,
                "Extension_Seq": 0,
                "EXT": "A",
            },
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "9502",
                Columns.COL_DUE_DATE: "2026-09-11",
                Columns.COL_ALLOY: "WCB",
                "Compatibility Group": "A216",
                "Compatible With ASTM Group": "YES",
                "Specific Compatible Alloys": "",
                "Total Weight per EXT": 1000,
                "Molds for EXT": 2,
                "Extension_Seq": 1,
                "EXT": "B",
            },
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "9503",
                Columns.COL_DUE_DATE: "2026-09-12",
                Columns.COL_ALLOY: "WCB",
                "Compatibility Group": "A216",
                "Compatible With ASTM Group": "YES",
                "Specific Compatible Alloys": "",
                "Total Weight per EXT": 900,
                "Molds for EXT": 2,
                "Extension_Seq": 2,
                "EXT": "C",
            },
        ])

        melt_schedule = build_melt_schedule(schedule_df, reference_date="2026-08-10")
        planned_rows = melt_schedule[1]["rows"]
        heat_totals = (
            planned_rows.groupby("Heat #")["Total Weight per EXT"].sum().to_dict()
        )

        self.assertEqual(melt_schedule[1]["planned_heat_count"], 2)
        self.assertEqual(heat_totals.get(1), 2300)
        self.assertEqual(heat_totals.get(2), 900)

    def test_build_melt_schedule_keeps_flexible_rows_due_order_before_group_efficiency(self):
        schedule_df = pd.DataFrame([
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "9701",
                Columns.COL_DUE_DATE: "2026-09-01",  # 22 days from 2026-08-10
                Columns.COL_ALLOY: "ALLOY-Z",
                "Compatibility Group": "Z-GROUP",
                "Compatible With ASTM Group": "NO",
                "Specific Compatible Alloys": "",
                "Total Weight per EXT": 1200,
                "Molds for EXT": 2,
                "Extension_Seq": 0,
                "EXT": "A",
            },
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "9702",
                Columns.COL_DUE_DATE: "2026-10-09",  # 60 days from 2026-08-10
                Columns.COL_ALLOY: "ALLOY-A",
                "Compatibility Group": "A-GROUP",
                "Compatible With ASTM Group": "NO",
                "Specific Compatible Alloys": "",
                "Total Weight per EXT": 1200,
                "Molds for EXT": 2,
                "Extension_Seq": 1,
                "EXT": "B",
            },
        ])

        melt_schedule = build_melt_schedule(schedule_df, reference_date="2026-08-10")
        planned_rows = melt_schedule[1]["rows"]

        self.assertEqual(planned_rows.iloc[0][Columns.COL_JOB_NUMBER], "9701")
        self.assertTrue(planned_rows.iloc[0]["Days Until Due"] < planned_rows.iloc[1]["Days Until Due"])

    def test_build_melt_schedule_allows_single_row_weight_over_limit(self):
        schedule_df = pd.DataFrame([
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "9161",
                Columns.COL_DUE_DATE: "2026-08-11",
                Columns.COL_ALLOY: "WCB",
                "Compatibility Group": "A216",
                "Compatible With ASTM Group": "YES",
                "Specific Compatible Alloys": "",
                "Total Weight per EXT": 2600,
                "Molds for EXT": 1,
                "Extension_Seq": 0,
                "EXT": "A",
            },
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "9162",
                Columns.COL_DUE_DATE: "2026-08-12",
                Columns.COL_ALLOY: "WCB",
                "Compatibility Group": "A216",
                "Compatible With ASTM Group": "YES",
                "Specific Compatible Alloys": "",
                "Total Weight per EXT": 200,
                "Molds for EXT": 1,
                "Extension_Seq": 1,
                "EXT": "B",
            },
        ])

        melt_schedule = build_melt_schedule(schedule_df, reference_date="2026-08-10")
        planned_rows = melt_schedule[1]["rows"]

        self.assertEqual(planned_rows["Heat #"].tolist(), [1, 2])

    def test_build_melt_schedule_spills_sixth_heat_to_next_pour_day(self):
        rows = []
        for index in range(6):
            rows.append(
                {
                    "Schedule Day": 1,
                    Columns.COL_JOB_NUMBER: f"920{index}",
                    Columns.COL_DUE_DATE: f"2026-08-{11 + index:02d}",
                    Columns.COL_ALLOY: f"ALLOY-{index}",
                    "Compatibility Group": f"GROUP-{index}",
                    "Compatible With ASTM Group": "NO",
                    "Specific Compatible Alloys": "",
                    "Total Weight per EXT": 500,
                    "Molds for EXT": 1,
                    "Extension_Seq": index,
                    "EXT": chr(65 + index),
                }
            )

        melt_schedule = build_melt_schedule(pd.DataFrame(rows), reference_date="2026-08-10")

        self.assertEqual(melt_schedule[1]["planned_heat_count"], 5)
        self.assertEqual(melt_schedule[1]["overflow_heat_count"], 0)
        self.assertEqual(melt_schedule[2]["planned_heat_count"], 1)
        self.assertEqual(melt_schedule[2]["rows"].iloc[0]["Heat #"], 1)

    def test_build_melt_schedule_starts_new_day_after_daily_weight_target(self):
        rows = []
        for index in range(5):
            rows.append(
                {
                    "Schedule Day": 1,
                    Columns.COL_JOB_NUMBER: f"960{index}",
                    Columns.COL_DUE_DATE: f"2026-09-{10 + index:02d}",
                    Columns.COL_ALLOY: f"ALLOY-{index}",
                    "Compatibility Group": f"GROUP-{index}",
                    "Compatible With ASTM Group": "NO",
                    "Specific Compatible Alloys": "",
                    "Total Weight per EXT": 2600,
                    "Molds for EXT": 1,
                    "Extension_Seq": index,
                    "EXT": chr(65 + index),
                }
            )

        melt_schedule = build_melt_schedule(pd.DataFrame(rows), reference_date="2026-08-10")

        self.assertEqual(melt_schedule[1]["planned_heat_count"], 4)
        self.assertEqual(melt_schedule[2]["planned_heat_count"], 1)
        self.assertEqual(melt_schedule[2]["rows"].iloc[0]["Heat #"], 1)

    def test_prioritize_schedule_rows_uses_ten_week_boundary(self):
        schedule_df = pd.DataFrame([
            {
                Columns.COL_JOB_NUMBER: "9401",
                Columns.COL_DUE_DATE: "2026-10-19",  # 70 days after 2026-08-10
                Columns.COL_ALLOY: "WCB",
                "Compatibility Group": "A216",
                "Extension_Seq": 0,
            },
            {
                Columns.COL_JOB_NUMBER: "9402",
                Columns.COL_DUE_DATE: "2026-10-20",  # 71 days after 2026-08-10
                Columns.COL_ALLOY: "WCB",
                "Compatibility Group": "A216",
                "Extension_Seq": 1,
            },
        ])

        prioritized = prioritize_schedule_rows(
            schedule_df,
            reference_date="2026-08-10",
        )

        by_job = prioritized.set_index(Columns.COL_JOB_NUMBER)
        self.assertEqual(by_job.loc["9401", "Review Window"], "Next 10 Weeks")
        self.assertEqual(by_job.loc["9402", "Review Window"], "Outside 10 Weeks")


if __name__ == "__main__":
    unittest.main()