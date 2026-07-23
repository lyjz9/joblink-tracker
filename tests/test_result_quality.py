from __future__ import annotations

import scraper.app as app_module
from scraper.browser_scraper_v2 import _looks_generic_title
from scraper.result_quality import _annotate_result, _quality_issues


LINKEDIN_URL = "https://www.linkedin.com/jobs/view/4433291582/"
SEARCH_TITLE = "430,000+ Analyst Jobs in United States"


def _search_page_result():
    return {
        "date_applied": "07/13/2026",
        "company": "Wing",
        "job_title": SEARCH_TITLE,
        "job_link": LINKEDIN_URL,
        "location": "Palo Alto, CA",
        "work_type": "Remote",
        "salary": "$140,000",
        "source": "LinkedIn",
    }


def test_aggregate_job_search_heading_is_generic():
    assert _looks_generic_title(SEARCH_TITLE) is True
    assert _looks_generic_title("Senior Data Analyst") is False


def test_job_search_heading_forces_low_confidence_review():
    result = _search_page_result()
    issues = _quality_issues(result)

    assert "job_search_page" in issues
    _annotate_result(result, LINKEDIN_URL, issues)
    assert result["confidence"] == "Low"
    assert result["confidence_score"] < 58


def test_missing_company_and_title_are_not_reported_as_matching_text():
    issues = _quality_issues({
        "company": "n/a",
        "job_title": "n/a",
        "location": "n/a",
    })

    assert "missing_company" in issues
    assert "missing_job_title" in issues
    assert "generic_job_title" not in issues


def test_linkedin_missing_work_type_is_sent_for_review():
    result = {
        "company": "Example Company",
        "job_title": "Operations Analyst",
        "job_link": LINKEDIN_URL,
        "location": "New York, NY",
        "work_type": "n/a",
        "salary": "n/a",
        "source": "LinkedIn",
    }

    issues = _quality_issues(result)
    _annotate_result(result, LINKEDIN_URL, issues)

    assert "linkedin_work_type_hidden" in issues
    assert result["confidence"] == "Medium"
    assert result["review_details"][0]["action"]


def test_scrape_discards_fields_from_redirected_search_page(monkeypatch, tmp_path):
    monkeypatch.setattr(
        app_module,
        "parse_job_with_browser",
        lambda *_args, **_kwargs: _search_page_result(),
    )

    result = app_module._scrape_url(
        LINKEDIN_URL,
        issue_log=tmp_path / "issues.jsonl",
    )

    assert result["error"] == "This posting is unavailable or has expired."
    assert result["company"] == "n/a"
    assert result["job_title"] == "n/a"
    assert result["location"] == "n/a"
    assert result["work_type"] == "n/a"
    assert result["salary"] == "n/a"
    assert "job_search_page" in result["review_issues"]
