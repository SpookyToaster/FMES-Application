"""
File I/O helpers for the mold production scheduler.

Currently handles reading the Open Order Report Excel workbook that is
exported from the ERP system and placed in the shared OneDrive folder.
"""

import pandas as pd


def Read_File(filepath="C:\\Users\\lburkardt\\OneDrive - MonettMetalsUS1\\Quality\\Schedule\\Open Order Report.xlsx"):
    """
    Read the Open Order Report Excel file and return it as a DataFrame.

    Strips leading/trailing whitespace from column headers so downstream
    column lookups are not affected by inconsistent ERP exports.

    Args:
        filepath: Absolute path to the Excel workbook.  Defaults to the
                  standard OneDrive location.

    Returns:
        pandas DataFrame containing all rows from the 'OOR' sheet.

    Raises:
        RuntimeError: If the file cannot be read (missing, locked, wrong format).
    """
    try:
        imported_file = pd.read_excel(filepath, sheet_name="OOR")
        imported_file.columns = imported_file.columns.str.strip()
        return imported_file
    except Exception as exc:
        raise RuntimeError(
            f"Failed to read schedule input from {filepath} (sheet 'OOR')"
        ) from exc
