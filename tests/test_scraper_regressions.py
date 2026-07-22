from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup

from scraper.browser_scraper_v2 import (
    _blocked_page_error,
    _clean_title,
    _direct_html_result,
    _extract_from_soup,
    _extract_work_type,
    _greenhouse_api_result,
    _is_direct_html_candidate,
    _launch_browser,
    _normalize_work_type,
    _public_result,
)


REGRESSION_CASES = (
    {
        "name": "linkedin",
        "url": "https://www.linkedin.com/jobs/view/data-analyst-at-legacy-ai-tech-4434286893/",
        "html": """
            <html><head><title>Data Analyst | LinkedIn</title></head><body>
              <h1>Data Analyst</h1>
              <a data-tracking-control-name="public_jobs_topcard-org-name">Legacy AI Tech</a>
              <span class="topcard__flavor--bullet">New York, NY</span>
              <div class="description__job-criteria-text">Hybrid</div>
              <div class="show-more-less-html__markup">
                This hybrid role works with operations leaders and reporting teams.
                The base pay range is $70,000 - $85,000 per year, depending on experience.
                The analyst will maintain accurate reports and improve internal workflows.
              </div>
            </body></html>
        """,
        "expected": {
            "company": "Legacy AI Tech",
            "job_title": "Data Analyst",
            "location": "New York, NY",
            "work_type": "Hybrid",
            "salary": "$70,000 - $85,000 per year",
            "source": "LinkedIn",
        },
    },
    {
        "name": "achieve_test_prep",
        "url": "https://careers.achievetestprep.com/jobs/careers/424687000052441476/Project-Specialist---Remote?source=CareerSite",
        "html": """
            <html><head>
              <title>ACHIEVE TEST PREP - Project Specialist - Remote in Remote</title>
              <meta property="og:title" content="ACHIEVE TEST PREP - Project Specialist - Remote in Remote">
              <meta property="og:site_name" content="ACHIEVE TEST PREP">
            </head><body>
              <div data-testid="location">Remote</div>
              <main>
                This is a fully remote project specialist role. The specialist keeps
                projects organized, follows up on action items, prepares status updates,
                and works with several teams to keep deadlines and records accurate.
              </main>
            </body></html>
        """,
        "expected": {
            "company": "Achieve Test Prep",
            "job_title": "Project Specialist",
            "location": "Remote",
            "work_type": "Remote",
            "salary": "n/a",
            "source": "Company Website",
        },
    },
    {
        "name": "workday",
        "url": "https://thinkbrg.wd5.myworkdayjobs.com/BRG_External_Career_Site/job/Remote---USA/Data-Analyst_JR100906",
        "html": """
            <html><body>
              <h2 data-automation-id="jobPostingHeader">Data Analyst</h2>
              <div data-automation-id="locations">Remote - USA</div>
              <main data-automation-id="jobPostingDescription">
                This is a fully remote role supporting teams throughout the United States.
                The salary range is $80,000 - $95,000 per year. The analyst will build
                reliable reporting and explain findings to business partners.
              </main>
            </body></html>
        """,
        "expected": {
            "company": "BRG",
            "job_title": "Data Analyst",
            "location": "United States",
            "work_type": "Remote",
            "salary": "$80,000 - $95,000 per year",
            "source": "Workday",
        },
    },
    {
        "name": "greenhouse",
        "url": "https://job-boards.greenhouse.io/energysolutionsinternships/jobs/5142309007",
        "html": """
            <html><body>
              <h1>Project Management Intern</h1>
              <div data-qa="company">EnergySolutions</div>
              <div class="location">Oak Ridge, TN</div>
              <div class="salary">Pay range: $20 - $24 per hour</div>
              <div id="content">
                This is an onsite position working with project teams in Oak Ridge.
                The intern will organize project records, coordinate updates, and help
                prepare weekly status reports for the operations team.
              </div>
            </body></html>
        """,
        "expected": {
            "company": "EnergySolutions",
            "job_title": "Project Management Intern",
            "location": "Oak Ridge, TN",
            "work_type": "Onsite",
            "salary": "$20 - $24 per hour",
            "source": "Greenhouse",
        },
    },
    {
        "name": "greenhouse_internal_board_slug",
        "url": "https://job-boards.greenhouse.io/xapo61/jobs/7800947003",
        "html": """
            <html><head>
              <title>Job Application for Visual Designer Graduate (Remote - Work from Anywhere) at Xapo Bank</title>
            </head><body>
              <h1>Visual Designer Graduate (Remote - Work from Anywhere)</h1>
              <div class="location">Gibraltar - Remote</div>
              <div id="content">
                This is a full-time, 100% remote position. The graduate visual designer
                creates marketing assets, motion pieces, and other polished materials
                while collaborating with design and product teams around the world.
              </div>
            </body></html>
        """,
        "expected": {
            "company": "Xapo Bank",
            "job_title": "Visual Designer Graduate",
            "location": "Gibraltar",
            "work_type": "Remote",
            "salary": "n/a",
            "source": "Greenhouse",
        },
    },
    {
        "name": "lever",
        "url": "https://jobs.lever.co/simulmedia/52c56404-78f4-41be-a1a0-ef3ecd84993c",
        "html": """
            <html><body>
              <div class="posting-headline"><h2>Operations Associate</h2></div>
              <div class="posting-company">Simulmedia</div>
              <div class="posting-categories"><span class="location">New York, NY</span></div>
              <div class="salary">Compensation: $65,000 - $75,000 per year</div>
              <div class="section-wrapper">
                This hybrid role supports daily business operations in New York.
                The associate will coordinate requests, maintain documentation, and
                work with several teams to resolve routine operational issues.
              </div>
            </body></html>
        """,
        "expected": {
            "company": "Simulmedia",
            "job_title": "Operations Associate",
            "location": "New York, NY",
            "work_type": "Hybrid",
            "salary": "$65,000 - $75,000 per year",
            "source": "Lever",
        },
    },
    {
        "name": "ashby",
        "url": "https://jobs.ashbyhq.com/rho/18da5bcb-aabe-424e-a9d1-e2e1c5abc2b1",
        "html": """
            <html><body>
              <h1>Business Operations Associate</h1>
              <div data-testid="job-location">New York, NY</div>
              <div class="salary">Base salary: $75,000 - $90,000 per year</div>
              <main data-testid="job-description">
                This position follows a hybrid schedule in New York. The associate
                will improve operating processes, keep projects moving, and prepare
                clear updates for company leaders and cross-functional partners.
              </main>
            </body></html>
        """,
        "expected": {
            "company": "Rho",
            "job_title": "Business Operations Associate",
            "location": "New York, NY",
            "work_type": "Hybrid",
            "salary": "$75,000 - $90,000 per year",
            "source": "Ashby",
        },
    },
    {
        "name": "icims",
        "url": "https://careers-girlscouts.icims.com/jobs/2221/quality-control-analyst%2c-customer-support/job",
        "html": """
            <html><body>
              <h1>Quality Control Analyst, Customer Support</h1>
              <div data-testid="company">Girl Scouts of the USA</div>
              <div data-testid="location">New York, NY</div>
              <div class="salary">Salary range: $62,000 - $72,000 per year</div>
              <main>
                This is a hybrid position based in New York. The analyst reviews
                customer-support interactions, documents trends, and partners with
                team leaders to improve service quality and training materials.
              </main>
            </body></html>
        """,
        "expected": {
            "company": "Girl Scouts of the USA",
            "job_title": "Quality Control Analyst, Customer Support",
            "location": "New York, NY",
            "work_type": "Hybrid",
            "salary": "$62,000 - $72,000 per year",
            "source": "iCIMS",
        },
    },
    {
        "name": "taleo_company_site",
        "url": "https://hdr.taleo.net/careersection/ex/jobdetail.ftl?job=192857&lang=en",
        "html": """
            <html><body>
              <h1>Operations Analyst</h1>
              <div class="salary">Salary range: $68,000 - $82,000 per year</div>
              <main>
                Primary Location: United States-New York-New York Schedule: Full-time
                This is a hybrid role. The analyst will maintain operating reports,
                coordinate team requests, and help improve repeatable processes.
              </main>
            </body></html>
        """,
        "expected": {
            "company": "HDR",
            "job_title": "Operations Analyst",
            "location": "New York, NY",
            "work_type": "Hybrid",
            "salary": "$68,000 - $82,000 per year",
            "source": "Company Website",
        },
    },
    {
        "name": "company_json_ld",
        "url": "https://careers.twosigma.com/careers/JobDetail/New-York-New-York-United-States-HR-Insights-Analyst/13927",
        "html": """
            <html><head>
              <script type="application/ld+json">
                {
                  "@context": "https://schema.org",
                  "@type": "JobPosting",
                  "title": "HR Insights Analyst",
                  "hiringOrganization": {"name": "Two Sigma"},
                  "jobLocation": {
                    "@type": "Place",
                    "address": {
                      "addressLocality": "New York",
                      "addressRegion": "NY",
                      "addressCountry": "US"
                    }
                  },
                  "baseSalary": "$100,000 - $130,000 per year",
                  "employmentType": "FULL_TIME",
                  "description": "This hybrid role analyzes workforce information and presents useful findings to HR leaders. The analyst also maintains reporting definitions and validates recurring dashboards."
                }
              </script>
            </head><body><main><h1>HR Insights Analyst</h1></main></body></html>
        """,
        "expected": {
            "company": "Two Sigma",
            "job_title": "HR Insights Analyst",
            "location": "New York, NY",
            "work_type": "Hybrid",
            "salary": "$100,000 - $130,000 per year",
            "source": "Company Website",
        },
    },
    {
        "name": "simplyhired_in_person",
        "url": "https://www.simplyhired.com/job/7VLL49YcRe5kBoRmzA19GL5Yte_vFYJZvpUaUpGXRAUwoUJHoBPybA",
        "html": """
            <html><head><title>Operations Coordinator - Acme Logistics | Newark, NJ</title></head><body>
              <h1>Operations Coordinator</h1>
              <div>Work type: In-person</div>
              <div class="salary">Pay: $24 - $28 per hour</div>
              <main>
                This in-person position coordinates daily shipments in Newark.
                The coordinator updates schedules, communicates with drivers, and
                keeps customer and dispatch records complete and accurate.
              </main>
            </body></html>
        """,
        "expected": {
            "company": "Acme Logistics",
            "job_title": "Operations Coordinator",
            "location": "Newark, NJ",
            "work_type": "Onsite",
            "salary": "$24 - $28 per hour",
            "source": "SimplyHired",
        },
    },
    {
        "name": "breezy",
        "url": "https://american-logistics-authority.breezy.hr/p/2d08852c9336-freight-dispatcher-independent-contractor",
        "html": """
            <html><head><title>Freight Dispatcher at American Logistics Authority</title></head><body>
              <h1>American Logistics Authority</h1>
              <h1>Freight Dispatcher - Independent Contractor</h1>
              <ul><li class="location">United States</li><li class="salary-range">$1,800 - $4,500 per week</li></ul>
              <main>
                This is a fully remote independent-contractor role. Dispatchers
                coordinate freight, communicate with drivers, and maintain accurate
                shipment information while working from anywhere in the United States.
              </main>
            </body></html>
        """,
        "expected": {
            "company": "American Logistics Authority",
            "job_title": "Freight Dispatcher - Independent Contractor",
            "location": "United States",
            "work_type": "Remote",
            "salary": "$1,800 - $4,500 per week",
            "source": "Breezy",
        },
    },
)


@pytest.mark.parametrize("case", REGRESSION_CASES, ids=lambda case: case["name"])
def test_saved_job_page_fields_do_not_regress(case):
    soup = BeautifulSoup(case["html"], "html.parser")
    result = _public_result(_extract_from_soup(soup, case["url"]))

    for field, expected in case["expected"].items():
        assert result[field] == expected, f"{case['name']} returned the wrong {field}"

    assert result["job_link"] == case["url"]
    assert result["work_type"] in {"Remote", "Hybrid", "Onsite", "n/a"}
    assert "description" not in result


def test_greenhouse_api_uses_canonical_company_instead_of_board_slug(monkeypatch):
    payload = {
        "company_name": "Xapo Bank",
        "title": "Visual Designer Graduate (Remote - Work from Anywhere)",
        "location": {"name": "Gibraltar - Remote"},
        "content": "<p>This is a full-time, 100% remote position.</p>",
    }

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return payload

    monkeypatch.setattr(
        "scraper.browser_scraper_v2.safe_requests_get",
        lambda *_args, **_kwargs: Response(),
    )

    result = _greenhouse_api_result(
        "https://job-boards.greenhouse.io/xapo61/jobs/7800947003"
    )

    assert result["company"] == "Xapo Bank"
    assert result["job_title"] == "Visual Designer Graduate"
    assert result["location"] == "Gibraltar"
    assert result["work_type"] == "Remote"


def test_custom_career_page_can_use_direct_html_without_browser(monkeypatch):
    url = (
        "https://careers.achievetestprep.com/jobs/careers/424687000052441476/"
        "Project-Specialist---Remote?source=CareerSite"
    )
    html = """
        <html><head>
          <title>ACHIEVE TEST PREP - Project Specialist - Remote in Remote</title>
          <meta property="og:title" content="ACHIEVE TEST PREP - Project Specialist - Remote in Remote">
          <meta property="og:site_name" content="ACHIEVE TEST PREP">
        </head><body>
          <div data-testid="location">Remote</div>
          <main>This is a fully remote project specialist position.</main>
        </body></html>
    """

    class Response:
        status_code = 200
        text = html

        def __init__(self):
            self.url = url

    monkeypatch.setattr(
        "scraper.browser_scraper_v2.safe_requests_get",
        lambda *_args, **_kwargs: Response(),
    )

    result = _direct_html_result(url)

    assert result["company"] == "Achieve Test Prep"
    assert result["job_title"] == "Project Specialist"
    assert result["location"] == "Remote"
    assert result["work_type"] == "Remote"
    assert result["salary"] == "n/a"


def test_indeed_posting_can_use_direct_html_without_browser(monkeypatch):
    url = "https://www.indeed.com/viewjob?jk=f4d6c2bbde0e1092"
    html = """
        <html><head>
          <title>Data and Inventory Specialist TEMP - New York, NY - Indeed.com</title>
        </head><body>
          <h1>Data and Inventory Specialist TEMP</h1>
          <a data-testid="inlineHeader-companyName">Seaport Entertainment Group</a>
          <div data-testid="jobsearch-JobInfoHeader-companyLocation">New York, NY 10038</div>
          <div data-testid="salaryInfoAndJobType">$23 - $25 an hour</div>
          <div id="jobDescriptionText">
            The specialist maintains inventory records and supports the data team.
          </div>
        </body></html>
    """

    class Response:
        status_code = 200
        text = html

        def __init__(self):
            self.url = url

    monkeypatch.setattr(
        "scraper.browser_scraper_v2.safe_requests_get",
        lambda *_args, **_kwargs: Response(),
    )

    result = _direct_html_result(url)

    assert result["company"] == "Seaport Entertainment Group"
    assert result["job_title"] == "Data and Inventory Specialist TEMP"
    assert result["location"] == "New York, NY"
    assert result["work_type"] == "n/a"
    assert result["salary"] == "$23 - $25 an hour"
    assert result["source"] == "Indeed"


def test_linkedin_posting_can_use_direct_html_without_browser(monkeypatch):
    url = "https://www.linkedin.com/jobs/view/4430000000/"
    html = """
        <html><head><title>Operations Analyst | LinkedIn</title></head><body>
          <h1>Operations Analyst</h1>
          <a data-tracking-control-name="public_jobs_topcard-org-name">Example Company</a>
          <span class="topcard__flavor--bullet">New York, NY</span>
          <div class="description__job-criteria-text">Hybrid</div>
          <div class="show-more-less-html__markup">
            This hybrid analyst role supports reporting and operating processes.
          </div>
        </body></html>
    """

    class Response:
        status_code = 200
        text = html

        def __init__(self):
            self.url = url

    monkeypatch.setattr(
        "scraper.browser_scraper_v2.safe_requests_get",
        lambda *_args, **_kwargs: Response(),
    )

    result = _direct_html_result(url)

    assert result["company"] == "Example Company"
    assert result["job_title"] == "Operations Analyst"
    assert result["location"] == "New York, NY"
    assert result["work_type"] == "Hybrid"
    assert result["source"] == "LinkedIn"


@pytest.mark.parametrize(
    "url",
    (
        "https://www.linkedin.com/jobs/search/?keywords=analyst",
        "https://www.indeed.com/jobs?q=analyst",
        "https://www.glassdoor.com/Job/new-york-analyst-jobs-SRCH_IL.0,8.htm",
        "https://example.com/careers",
    ),
)
def test_direct_html_fallback_rejects_job_search_pages(url):
    assert not _is_direct_html_candidate(url)


def test_browser_launch_uses_installed_edge_when_bundled_chromium_is_missing():
    calls = []
    edge_browser = object()

    class Chromium:
        async def launch(self, **options):
            calls.append(options)
            if options.get("channel") == "msedge":
                return edge_browser
            raise RuntimeError("browser missing")

    browser = asyncio.run(
        _launch_browser(
            SimpleNamespace(chromium=Chromium()),
            ["--disable-dev-shm-usage"],
        )
    )

    assert browser is edge_browser
    assert calls == [
        {"headless": True, "args": ["--disable-dev-shm-usage"]},
        {
            "channel": "msedge",
            "headless": True,
            "args": ["--disable-dev-shm-usage"],
        },
    ]


@pytest.mark.parametrize(
    ("title", "company", "expected"),
    (
        (
            "ACHIEVE TEST PREP - Project Specialist - Remote in Remote",
            "Achieve Test Prep",
            "Project Specialist",
        ),
        (
            "Visual Designer Graduate (Remote - Work from Anywhere)",
            "Xapo Bank",
            "Visual Designer Graduate",
        ),
        ("Data Analyst - Hybrid", "", "Data Analyst"),
        ("Remote Sensing Analyst", "", "Remote Sensing Analyst"),
    ),
)
def test_title_cleanup_removes_only_trailing_work_arrangements(title, company, expected):
    assert _clean_title(title, company) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("Remote", "Remote"),
        ("hybrid schedule", "Hybrid"),
        ("on-site position", "Onsite"),
        ("in-office role", "Onsite"),
        ("in-person position", "Onsite"),
        ("full-time position", ""),
    ),
)
def test_work_type_normalization_is_explicit(value, expected):
    assert _normalize_work_type(value) == expected


def test_conflicting_remote_and_onsite_text_is_not_guessed():
    assert _extract_work_type("Remote work is unavailable; this role is onsite.") == ""


@pytest.mark.parametrize(
    "page_text",
    (
        "Verify you are human before continuing",
        "Checking your browser before accessing this page",
        "Access denied: automated requests are blocked",
    ),
)
def test_blocked_pages_receive_a_clear_error(page_text):
    assert _blocked_page_error(page_text) == "Website blocked automated access to this posting."
