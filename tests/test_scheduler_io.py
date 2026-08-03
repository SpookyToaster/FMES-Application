import sys
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduler_io import Read_File


class SchedulerIOTests(unittest.TestCase):
    def test_read_file_strips_headers(self):
        frame = pd.DataFrame(columns=[" Job Number ", " Due Date "])

        with patch("scheduler_io.pd.read_excel", return_value=frame):
            result = Read_File("sample.xlsx")

        self.assertEqual(list(result.columns), ["Job Number", "Due Date"])

    def test_read_file_wraps_failures(self):
        with patch("scheduler_io.pd.read_excel", side_effect=FileNotFoundError("missing")):
            with self.assertRaises(RuntimeError) as context:
                Read_File("missing.xlsx")

        self.assertIn("Failed to read schedule input", str(context.exception))


if __name__ == "__main__":
    unittest.main()