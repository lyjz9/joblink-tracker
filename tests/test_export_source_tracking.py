from openpyxl import load_workbook

from export.exporter import HEADERS, export_jobs_to_xlsx


def test_new_tracker_exports_discovery_source_without_the_application_portal(tmp_path):
    output_path = export_jobs_to_xlsx([{
        "company": "Example Company",
        "job_title": "Analyst",
        "job_link": "https://jobs.ashbyhq.com/example/123",
        "source": "LinkedIn",
        "found_on": "LinkedIn",
    }], outdir=tmp_path)

    worksheet = load_workbook(output_path).active
    assert [cell.value for cell in worksheet[1]] == HEADERS
    assert "Application Portal" not in HEADERS
    assert "Job ID" not in HEADERS
    assert worksheet.cell(2, HEADERS.index("Found On") + 1).value == "LinkedIn"
