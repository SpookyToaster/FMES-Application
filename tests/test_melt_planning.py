import sys
from pathlib import Path
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Columns
from melt_planning import Build_Melt_Schedule


class MeltPlanningTests(unittest.TestCase):
    def test_build_melt_schedule_reserves_slot_six(self):
        schedule_df = pd.DataFrame([
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "9001",
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

        melt_schedule = Build_Melt_Schedule(schedule_df)
        summary = melt_schedule[1]["heat_summary"]

        self.assertEqual(melt_schedule[1]["planned_heat_count"], 1)
        self.assertEqual(melt_schedule[1]["reserved_heat_slots"], [6])
        self.assertEqual(summary.iloc[0]["Heat Status"], "Planned")
        self.assertEqual(summary.iloc[-1]["Heat Slot"], 6)
        self.assertEqual(summary.iloc[-1]["Heat Status"], "Reserved")

    def test_build_melt_schedule_groups_compatible_astm_alloys(self):
        schedule_df = pd.DataFrame([
            {
                "Schedule Day": 1,
                Columns.COL_JOB_NUMBER: "9101",
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

        melt_schedule = Build_Melt_Schedule(schedule_df)
        planned_rows = melt_schedule[1]["rows"]

        self.assertEqual(planned_rows["Heat #"].tolist(), [1, 1])
        self.assertEqual(melt_schedule[1]["planned_heat_count"], 1)

    def test_build_melt_schedule_flags_overflow_after_five_planned_heats(self):
        rows = []
        for index in range(6):
            rows.append(
                {
                    "Schedule Day": 1,
                    Columns.COL_JOB_NUMBER: f"920{index}",
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

        melt_schedule = Build_Melt_Schedule(pd.DataFrame(rows))
        summary = melt_schedule[1]["heat_summary"]
        overflow_rows = summary[summary["Heat Status"] == "Overflow"]

        self.assertEqual(melt_schedule[1]["planned_heat_count"], 5)
        self.assertEqual(melt_schedule[1]["overflow_heat_count"], 1)
        self.assertEqual(len(overflow_rows), 1)
        self.assertEqual(int(overflow_rows.iloc[0]["Heat #"]), 6)


if __name__ == "__main__":
    unittest.main()