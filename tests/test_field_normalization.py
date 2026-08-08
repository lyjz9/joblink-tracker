import pytest

from scraper.browser_scraper_v2 import _public_result
from scraper.field_normalization import (
    normalize_location_display,
    normalize_salary_display,
)
from scraper.result_quality import _public_scrape_result


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("NEW YORK, NY", "New York, NY"),
        ("WASHINGTON, DC", "Washington, DC"),
        ("CITY OF INDUSTRY, CA", "City of Industry, CA"),
        ("MCKINNEY, TX", "McKinney, TX"),
        ("SEOUL, SOUTH KOREA", "Seoul, South Korea"),
        ("NEW YORK, United States", "New York, United States"),
        ("Remote - USA", "Remote - USA"),
        ("McLean, VA", "McLean, VA"),
    ),
)
def test_location_display_normalization(value, expected):
    assert normalize_location_display(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("Base pay range $20.00/hr - $25.00/hr", "$20.00/hr - $25.00/hr"),
        ("Salary range: $70,000 - $85,000 per year", "$70,000 - $85,000 per year"),
        ("Annual base salary: USD 80,000 - USD 95,000", "USD 80,000 - USD 95,000"),
        ("Pay: $24 - $28 per hour", "$24 - $28 per hour"),
        ("USD $20.00/hr - $25.00/hr", "USD $20.00/hr - $25.00/hr"),
        ("Base pay is competitive", ""),
        ("20-20", "20"),
        ("$20/hour - $20/hour", "$20/hour"),
        ("$20 - $20 per hour", "$20 per hour"),
        ("Base pay range $20 - $20 per hour", "$20 per hour"),
        ("$20.00/hr - $20/hr", "$20.00/hr"),
        ("$70,000 - $70,000 per year", "$70,000 per year"),
        ("20K - 20K", "20K"),
        ("USD $20/hour - USD $20/hour", "USD $20/hour"),
        ("$20/hour - $25/hour", "$20/hour - $25/hour"),
        ("$20/hour - $20/year", "$20/hour - $20/year"),
        ("USD $20/hour - CAD $20/hour", "USD $20/hour - CAD $20/hour"),
    ),
)
def test_salary_display_normalization(value, expected):
    assert normalize_salary_display(value) == expected


@pytest.mark.parametrize(
    "clean_result",
    (_public_result, _public_scrape_result),
    ids=("browser_result", "shared_result"),
)
def test_public_results_normalize_location_and_salary(clean_result):
    result = clean_result({
        "company": "Example Company",
        "job_title": "Operations Analyst",
        "location": "NEW YORK, NY",
        "salary": "Base pay range $20.00/hr - $25.00/hr",
    })

    assert result["location"] == "New York, NY"
    assert result["work_type"] == "Onsite"
    assert result["salary"] == "$20.00/hr - $25.00/hr"


@pytest.mark.parametrize(
    "clean_result",
    (_public_result, _public_scrape_result),
    ids=("browser_result", "shared_result"),
)
@pytest.mark.parametrize("work_type", ("", "n/a"))
def test_complete_public_results_default_unspecified_work_type_to_onsite(
    clean_result,
    work_type,
):
    result = clean_result({
        "company": "Example Company",
        "job_title": "Operations Analyst",
        "location": "New York, NY",
        "work_type": work_type,
    })

    assert result["work_type"] == "Onsite"


@pytest.mark.parametrize(
    "clean_result",
    (_public_result, _public_scrape_result),
    ids=("browser_result", "shared_result"),
)
@pytest.mark.parametrize(
    "overrides",
    (
        {"company": "n/a"},
        {"job_title": "n/a"},
        {"location": "n/a"},
        {"error": "This posting could not be read."},
    ),
)
def test_incomplete_or_failed_results_keep_unspecified_work_type_na(
    clean_result,
    overrides,
):
    payload = {
        "company": "Example Company",
        "job_title": "Operations Analyst",
        "location": "New York, NY",
        "work_type": "",
    }
    payload.update(overrides)

    result = clean_result(payload)

    assert result["work_type"] == "n/a"


def test_salary_label_without_an_amount_becomes_na():
    result = _public_scrape_result({
        "company": "Example Company",
        "job_title": "Operations Analyst",
        "location": "New York, NY",
        "salary": "Base pay is competitive",
    })

    assert result["salary"] == "n/a"
