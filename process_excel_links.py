#!/usr/bin/env python
"""Process pending job links from an Excel workbook."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

INPUT_HEADERS = [
    "Job Link",
    "Source",
    "Notes",
    "Process Status",
    "Processed At",
    "Error Message",
]

APPLICATION_HEADERS = [
    "Date Applied",
    "Company",
    "Job Title",
    "Job link",
    "Status",
    "Location",
    "Work Type",
    "Salary Range",
    "Follow-up",
    "Source",
]

SHEET_WIDTHS = {
    "Input": [70, 20, 35, 24, 22, 55],
    "Applications": [15, 26, 38, 70, 18, 28, 16, 24, 15, 22],
}


def normalize_header(value: object) -> str:
    return str(value or "").strip().casefold()


def header_map(worksheet) -> dict[str, int]:
    return {
        normalize_header(cell.value): cell.column
        for cell in worksheet[1]
        if cell.value
    }


def ensure_headers(worksheet, headers: list[str]) -> None:
    existing = header_map(worksheet)
    for column, header in enumerate(headers, 1):
        if normalize_header(header) not in existing:
            worksheet.cell(row=1, column=column, value=header)
    worksheet.freeze_panes = "A2"
    if worksheet.tables:
        worksheet.auto_filter.ref = None
    else:
        worksheet.auto_filter.ref = f"A1:{worksheet.cell(1, len(headers)).coordinate}"
    worksheet.row_dimensions[1].height = 24
    widths = SHEET_WIDTHS.get(worksheet.title, [])
    for column, header in enumerate(headers, 1):
        cell = worksheet.cell(row=1, column=column)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
        cell.alignment = Alignment(horizontal="center", vertical="center")
        if column <= len(widths):
            worksheet.column_dimensions[cell.column_letter].width = widths[column - 1]


def get_or_create_sheet(workbook, name: str, headers: list[str]):
    if name in workbook.sheetnames:
        worksheet = workbook[name]
    elif name == "Applications":
        worksheet = next(
            (
                sheet
                for sheet in workbook.worksheets
                if "job link" in header_map(sheet)
            ),
            None,
        )
        if worksheet is None:
            worksheet = workbook.create_sheet(name)
        else:
            worksheet.title = name
    else:
        worksheet = workbook.create_sheet(name)
    ensure_headers(worksheet, headers)
    return worksheet


def clean_url(value: object) -> str:
    return str(value or "").strip()


def existing_job_links(worksheet) -> set[str]:
    columns = header_map(worksheet)
    link_column = columns.get("job link")
    if not link_column:
        return set()
    links = set()
    for row in range(2, worksheet.max_row + 1):
        cell = worksheet.cell(row=row, column=link_column)
        link = clean_url(cell.hyperlink.target if cell.hyperlink else cell.value)
        if link:
            links.add(link)
    return links


def excel_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    for pattern in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            pass
    return date.today()


def result_status(result: dict) -> str:
    if result.get("error"):
        return "Error"
    required = ("company", "job_title", "location")
    if any(str(result.get(key, "")).strip().casefold() in {"", "n/a"} for key in required):
        return "Needs Manual Review"
    return "Done"


def append_application(worksheet, result: dict, original_url: str) -> None:
    applied = excel_date(result.get("date_applied"))
    follow_up = result.get("follow_up", "")
    values = {
        "date applied": applied,
        "company": result.get("company", "n/a"),
        "job title": result.get("job_title", "n/a"),
        "job link": result.get("job_link") or original_url,
        "status": result.get("status", ""),
        "location": result.get("location", "n/a"),
        "work type": result.get("work_type", "n/a"),
        "salary range": result.get("salary", "n/a"),
        "follow-up": follow_up,
        "source": result.get("source", "Company Website"),
    }
    columns = header_map(worksheet)
    link_column = columns.get("job link")
    new_row = next(
        (
            row
            for row in range(2, worksheet.max_row + 1)
            if not clean_url(worksheet.cell(row=row, column=link_column).value)
        ),
        worksheet.max_row + 1,
    )
    for header, value in values.items():
        column = columns.get(header)
        if column:
            worksheet.cell(row=new_row, column=column, value=value)
    if link_column:
        link_cell = worksheet.cell(row=new_row, column=link_column)
        link_cell.value = "Open job"
        link_cell.hyperlink = original_url
        link_cell.style = "Hyperlink"
    for header in ("date applied", "follow-up"):
        column = columns.get(header)
        if column:
            worksheet.cell(row=new_row, column=column).number_format = "mm/dd/yyyy"


def process_workbook(path: Path) -> tuple[int, int, int]:
    keep_vba = path.suffix.casefold() == ".xlsm"
    workbook = load_workbook(path, keep_vba=keep_vba)
    applications = get_or_create_sheet(workbook, "Applications", APPLICATION_HEADERS)
    input_sheet = get_or_create_sheet(workbook, "Input", INPUT_HEADERS)

    input_columns = header_map(input_sheet)
    known_links = existing_job_links(applications)
    processed = duplicates = errors = 0
    scraper = None

    for row in range(2, input_sheet.max_row + 1):
        link = clean_url(input_sheet.cell(row, input_columns["job link"]).value)
        status = str(input_sheet.cell(row, input_columns["process status"]).value or "").strip()
        if not link or status.casefold() not in {"", "pending"}:
            continue

        if link in known_links:
            input_sheet.cell(row, input_columns["process status"], "Duplicate")
            input_sheet.cell(row, input_columns["processed at"], datetime.now())
            duplicates += 1
            continue

        try:
            if scraper is None:
                from scraper.browser_scraper_v2 import parse_job_with_browser

                scraper = parse_job_with_browser
            result = scraper(link)
            status = result_status(result)
            if status != "Error":
                append_application(applications, result, link)
                known_links.add(link)
                processed += 1
            else:
                errors += 1
            input_sheet.cell(row, input_columns["process status"], status)
            input_sheet.cell(row, input_columns["processed at"], datetime.now())
            input_sheet.cell(row, input_columns["error message"], result.get("error", ""))
        except Exception as exc:
            input_sheet.cell(row, input_columns["process status"], "Error")
            input_sheet.cell(row, input_columns["processed at"], datetime.now())
            input_sheet.cell(row, input_columns["error message"], str(exc))
            errors += 1

        workbook.save(path)

    workbook.save(path)
    return processed, duplicates, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Process pending job links from Excel.")
    parser.add_argument("workbook", help="Path to the .xlsx or .xlsm tracker workbook")
    args = parser.parse_args()
    workbook_path = Path(args.workbook).expanduser().resolve()
    if not workbook_path.exists():
        print(f"Workbook not found: {workbook_path}")
        return 1

    processed, duplicates, errors = process_workbook(workbook_path)
    print(f"Finished: {processed} added, {duplicates} duplicate, {errors} error.")
    return 0 if errors == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
