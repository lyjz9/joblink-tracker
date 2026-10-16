from openpyxl import Workbook

from process_excel_links import APPLICATION_HEADERS, ensure_headers, header_map


def test_legacy_excel_workflow_preserves_old_columns_and_adds_found_on():
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Applications"
    worksheet.append([
        "Date Applied", "Company", "Job Title", "Job link", "Status",
        "Location", "Work Type", "Salary Range", "Follow-up", "Source",
    ])
    worksheet.append([
        "08/01/2026", "Example Company", "Analyst",
        "https://jobs.ashbyhq.com/example/123", "Applied", "New York, NY",
        "Hybrid", "n/a", "", "LinkedIn",
    ])

    ensure_headers(worksheet, APPLICATION_HEADERS)
    columns = header_map(worksheet)

    assert worksheet.cell(2, columns["source"]).value == "LinkedIn"
    assert "application portal" not in columns
    assert "found on" in columns
