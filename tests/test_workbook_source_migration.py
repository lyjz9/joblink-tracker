from __future__ import annotations

import io

from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.table import Table, TableStyleInfo

from export.workbook_appender import append_jobs_to_workbook


def test_legacy_source_column_is_split_and_excel_table_is_extended(tmp_path):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Applications"
    worksheet.append([
        "Date Applied", "Company", "Job Title", "Job link", "Status",
        "Location", "Work Type", "Salary Range", "Follow-up", "Source",
    ])
    worksheet.append([
        "08/01/2026", "Example Company", "Analyst",
        "https://example.wd5.myworkdayjobs.com/job/Analyst_R123",
        "Applied", "New York, NY", "Hybrid", "n/a", "", "LinkedIn",
    ])
    table = Table(displayName="ApplicationsTable", ref="A1:J2")
    table.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2",
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=True,
        showColumnStripes=False,
    )
    worksheet.add_table(table)
    source = io.BytesIO()
    workbook.save(source)
    source.seek(0)

    output_path, _summary = append_jobs_to_workbook(
        source,
        "legacy.xlsx",
        [],
        outdir=tmp_path,
    )
    migrated = load_workbook(output_path)
    worksheet = migrated["Applications"]
    headers = {
        cell.value: cell.column
        for cell in worksheet[1]
        if cell.value
    }

    assert "Source" not in headers
    assert worksheet.cell(2, headers["Found On"]).value == "LinkedIn"
    assert worksheet.cell(2, headers["Application Portal"]).value == "Workday"
    assert worksheet.tables["ApplicationsTable"].ref == "A1:K2"
