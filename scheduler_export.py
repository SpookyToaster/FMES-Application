from openpyxl import Workbook
from openpyxl.styles import Border, Font, Side
import pandas as pd

from config import Columns


def _normalize_due_date(value):
    if pd.isna(value):
        return ""

    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return value

    return parsed.date()


def Build_Daily_Export_Blocks(Daily_Schedules, Day_Dates):
    try:
        export_blocks = {}

        for day, df in Daily_Schedules.items():
            weight_total = df["Total Weight per EXT"].fillna(0).sum()
            mold_total = df["Molds for EXT"].fillna(0).sum()

            export_blocks[day] = {
                "date": Day_Dates[day]["date"],
                "weekday": Day_Dates[day]["weekday"],
                "rows": df[
                    [
                        Columns.COL_DUE_DATE,
                        "Customer Name",
                        "Part Number",
                        Columns.COL_JOB_NUMBER,
                        "EXT",
                        Columns.COL_ALLOY,
                        Columns.COL_CAST_TYPE,
                        "Quantity of Molds",
                        "Castings Per Mold",
                        "Quantity of Cores",
                        "Total Weight per EXT",
                        "Molds for EXT",
                    ]
                ].copy(),
                "weight_total": weight_total,
                "mold_total": mold_total,
            }

        return export_blocks
    except Exception as exc:
        raise RuntimeError("Failed while building export blocks") from exc


def Print_Export_Blocks(export_blocks):
    try:
        for day in export_blocks:
            print("\n" + "=" * 50)
            print(
                f"Mold Schedule    "
                f"{export_blocks[day]['date'].strftime('%m/%d/%Y')}    "
                f"{export_blocks[day]['weekday']}"
            )
            print("=" * 50)
            print(export_blocks[day]["rows"])
            print(f"\nTOTAL WEIGHT: {export_blocks[day]['weight_total']}")
            print(f"TOTAL MOLDS: {export_blocks[day]['mold_total']}")
    except Exception as exc:
        raise RuntimeError("Failed while printing export blocks") from exc


def Build_Excel_Rows(export_blocks):
    excel_rows = []

    for day in sorted(export_blocks.keys()):
        block = export_blocks[day]
        excel_rows.append(["Mold Schedule", block["date"].strftime("%m/%d/%Y"), block["weekday"]])
        excel_rows.append([
            "Due Date",
            "Customer Name",
            "Part Number",
            "Job Number",
            "EXT",
            "Alloy",
            "Mold Type",
            "Quantity of Molds",
            "Castings Per Mold",
            "Cores Per Mold",
            "Total Weight per EXT",
            "# of Molds for EXT",
        ])

        for _, row in block["rows"].iterrows():
            excel_rows.append([
                _normalize_due_date(row.get(Columns.COL_DUE_DATE, "")),
                row.get("Customer Name", ""),
                row.get("Part Number", ""),
                row.get(Columns.COL_JOB_NUMBER, ""),
                row.get("EXT", ""),
                row.get(Columns.COL_ALLOY, ""),
                row.get(Columns.COL_CAST_TYPE, ""),
                row.get("Quantity of Molds", ""),
                row.get("Castings Per Mold", ""),
                row.get("Quantity of Cores", ""),
                row.get("Total Weight per EXT", ""),
                row.get("Molds for EXT", ""),
            ])

        excel_rows.append(["TOTALS", "", "", "", "", "", "", "", "", "", block["weight_total"], block["mold_total"]])
        excel_rows.append([])

    return excel_rows


def Export_Mold_Schedule(Export_Blocks, output_file="Mold Schedule.xlsx"):
    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "Mold Schedule"
        current_row = 1

        thin = Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin"))
        bold = Font(bold=True)

        for day in sorted(Export_Blocks.keys()):
            block = Export_Blocks[day]

            ws.cell(current_row, 1, "Mold Schedule")
            ws.cell(current_row, 2, block["date"].strftime("%m/%d/%Y"))
            ws.cell(current_row, 4, block["weekday"])

            for col in range(1, 13):
                ws.cell(current_row, col).font = bold

            current_row += 2

            headers = [
                "Due Date",
                "Customer Name",
                "Part Number",
                "Job Number",
                "EXT",
                "Alloy",
                "Mold Type",
                "Quantity of Molds",
                "Castings Per Mold",
                "Cores Per Mold",
                "Total Weight per EXT",
                "# of Molds for EXT",
            ]

            for col_num, header in enumerate(headers, start=1):
                cell = ws.cell(current_row, col_num, header)
                cell.font = bold
                cell.border = thin

            current_row += 1

            for _, row in block["rows"].iterrows():
                values = [
                    _normalize_due_date(row.get(Columns.COL_DUE_DATE, "")),
                    row.get("Customer Name", ""),
                    row.get("Part Number", ""),
                    row.get(Columns.COL_JOB_NUMBER, ""),
                    row.get("EXT", ""),
                    row.get(Columns.COL_ALLOY, ""),
                    row.get(Columns.COL_CAST_TYPE, ""),
                    row.get("Quantity of Molds", ""),
                    row.get("Castings Per Mold", ""),
                    row.get("Quantity of Cores", ""),
                    row.get("Total Weight per EXT", ""),
                    row.get("Molds for EXT", ""),
                ]

                for col_num, value in enumerate(values, start=1):
                    cell = ws.cell(current_row, col_num, value)
                    cell.border = thin
                    if col_num == 1 and value != "":
                        cell.number_format = "m/d/yyyy"

                current_row += 1

            ws.cell(current_row, 1, "TOTALS")
            ws.cell(current_row, 11, block["weight_total"])
            ws.cell(current_row, 12, block["mold_total"])
            ws.cell(current_row, 1).font = bold
            ws.cell(current_row, 11).font = bold
            ws.cell(current_row, 12).font = bold
            current_row += 3

        widths = {"A": 12, "B": 30, "C": 25, "D": 15, "E": 6, "F": 15, "G": 12, "H": 15, "I": 15, "J": 15, "K": 18, "L": 15}

        for col, width in widths.items():
            ws.column_dimensions[col].width = width

        wb.save(output_file)
        print(f"Saved: {output_file}")
    except Exception as exc:
        raise RuntimeError(f"Failed while exporting mold schedule to {output_file}") from exc
