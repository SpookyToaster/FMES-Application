import pandas as pd


def Read_File(filepath="C:\\Users\\lburkardt\\OneDrive - MonettMetalsUS1\\Quality\\Schedule\\Open Order Report.xlsx"):
    try:
        imported_file = pd.read_excel(filepath, sheet_name="OOR")
        imported_file.columns = imported_file.columns.str.strip()
        return imported_file
    except Exception as exc:
        raise RuntimeError(
            f"Failed to read schedule input from {filepath} (sheet 'OOR')"
        ) from exc
