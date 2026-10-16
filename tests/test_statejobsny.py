from html import escape

import pytest
from bs4 import BeautifulSoup

from scraper.browser_scraper_v2 import (
    _detect_platform,
    _direct_html_result,
    _extract_from_soup,
    _public_result,
)
from scraper.result_quality import _quality_issues
from scraper.source_tracking import enrich_source_tracking


def vacancy_html(*, city="New York", agency="Criminal Justice Services, Division of",
                 title="Crime Analyst 1/Trainee - 227112", telecommuting="No",
                 due="10/25/2099", salary="From $69964 to $88970 Annually"):
    def row(label, value):
        return (
            f'<p class="row"><span class="leftCol"><a class="help" title="Help"></a>'
            f'{escape(label)}</span><span class="rightCol">{escape(value)}</span></p>'
        )

    return f"""
        <html><head><title>StateJobsNY - Public Information: Review Vacancy</title></head>
        <body><h1>Review Vacancy</h1><div id="vacancyDetails">
          {row('Applications Due', due)}{row('Vacancy ID', '227112')}
          <div id="information">
            {row('Agency', agency)}{row('Title', title)}
            {row('Salary Grade', '18')}{row('Salary Range', salary)}
          </div>
          <div id="schedule">{row('Telecommuting allowed?', telecommuting)}</div>
          <div id="location">{row('City', city)}{row('State', 'NY')}</div>
          <div id="jobspecifics">{row('Duties Description', 'Analyze crime data and reports.')}</div>
          <div id="contact">{row('City', 'Albany, NY')}{row('State', 'NY')}</div>
        </div><footer>NYS Department of Civil Service</footer></body></html>
    """


def parse(html, host="statejobsny.com", audience="public"):
    url = f"https://{host}/{audience}/vacancyDetailsView.cfm?id=227112"
    return _public_result(_extract_from_soup(BeautifulSoup(html, "html.parser"), url))


@pytest.mark.parametrize("host", ("statejobsny.com", "www.statejobsny.com", "statejobs.ny.gov"))
@pytest.mark.parametrize("audience", ("public", "employees"))
def test_statejobsny_reads_the_job_sections_instead_of_contact_details(host, audience):
    result = parse(vacancy_html(), host, audience)

    assert result["company"] == "Division of Criminal Justice Services"
    assert result["job_title"] == "Crime Analyst 1/Trainee"
    assert result["location"] == "New York, NY"
    assert result["work_type"] == "Onsite"
    assert result["salary"] == "$69964 - $88970 Annually"
    assert result["source"] == "StateJobsNY"
    assert enrich_source_tracking(result)["application_portal"] == "StateJobsNY"
    assert _quality_issues(result) == []


def test_statejobsny_telecommuting_flag_supports_hybrid_without_calling_it_remote():
    result = parse(vacancy_html(telecommuting="Yes", agency="Transportation, Department of", city="Albany"))

    assert result["company"] == "Department of Transportation"
    assert result["location"] == "Albany, NY"
    assert result["work_type"] == "Hybrid"


def test_statejobsny_does_not_replace_a_missing_worksite_with_the_contact_city():
    result = parse(vacancy_html(city=""))

    assert result["location"] == "n/a"
    assert "missing_location" in _quality_issues(result)


def test_statejobsny_does_not_replace_missing_agency_or_title_with_site_branding():
    result = parse(vacancy_html(agency="", title=""))

    assert result["company"] == "n/a"
    assert result["job_title"] == "n/a"
    assert {"missing_company", "missing_job_title"}.issubset(_quality_issues(result))


def test_statejobsny_archived_posting_with_a_past_deadline_is_expired():
    result = parse(vacancy_html(due="10/25/2000"))

    assert "expired" in result["error"]
    assert result["company"] == result["job_title"] == result["location"] == "n/a"


def test_statejobsny_keeps_title_numbers_that_are_not_the_vacancy_id():
    result = parse(vacancy_html(title="Data Analyst 1/Trainee 2 - 10156", due="Until Filled"))

    assert result["job_title"] == "Data Analyst 1/Trainee 2 - 10156"
    assert "error" not in result


def test_statejobsny_zero_salary_is_missing_instead_of_zero_pay():
    result = parse(vacancy_html(salary="From $0 to $0 Annually"))

    assert result["salary"] == "n/a"


def test_statejobsny_incomplete_page_is_an_error_instead_of_a_ready_shell():
    result = parse("<html><h1>Review Vacancy</h1><p>Vacancy details could not be loaded.</p></html>")

    assert "error" in result
    assert result["job_title"] == "n/a"


def test_statejobsny_removed_vacancy_has_an_unavailable_error():
    result = parse("<html><h1>Review Vacancy</h1><p>The vacancy you are looking for does not exist.</p></html>")

    assert "no longer available" in result["error"]
    assert result["company"] == result["job_title"] == result["location"] == "n/a"


def test_statejobsny_static_job_does_not_need_a_browser(monkeypatch):
    class Response:
        status_code = 200
        text = vacancy_html()
        url = "https://statejobsny.com/public/vacancyDetailsView.cfm?id=227112"

    monkeypatch.setattr("scraper.browser_scraper_v2.safe_requests_get", lambda *args, **kwargs: Response())

    result = _direct_html_result(Response.url)

    assert result["job_title"] == "Crime Analyst 1/Trainee"
    assert result["location"] == "New York, NY"


@pytest.mark.parametrize("url", (
    "https://statejobsny.com.example.org/public/vacancyDetailsView.cfm?id=227112",
    "https://notlinkedin.com/jobs/view/123",
))
def test_platform_detection_requires_a_real_domain_boundary(url):
    assert _detect_platform(url) == "company_website"
