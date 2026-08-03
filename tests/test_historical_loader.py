import sys
from pathlib import Path
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from load_historical_snapshot import parse_run_date, validate_columns


class HistoricalLoaderTests(unittest.TestCase):
    def test_parse_run_date_valid(self):
        parsed = parse_run_date("2026-08-03")
        self.assertEqual(str(parsed), "2026-08-03")

    def test_parse_run_date_invalid(self):
        with self.assertRaises(RuntimeError) as context:
            parse_run_date("08/03/2026")

        self.assertIn("Expected YYYY-MM-DD", str(context.exception))

    def test_validate_columns_detects_missing(self):
        frame = pd.DataFrame({"Due Date": ["2026-08-03"]})

        with self.assertRaises(RuntimeError) as context:
            validate_columns(frame)

        self.assertIn("Missing required columns", str(context.exception))


if __name__ == "__main__":
    unittest.main()