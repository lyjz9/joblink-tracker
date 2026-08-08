from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup

from scraper.browser_scraper_v2 import (
    _blocked_page_error,
    _clean_title,
    _detect_platform,
    _direct_html_result,
    _extract_from_soup,
    _extract_work_type,
    _greenhouse_api_result,
    _is_direct_html_candidate,
    _launch_browser,
    _normalize_work_type,
    _oracle_candidate_experience_result,
    _page_content_when_stable,
    _public_result,
    _visible_page_text,
    _workday_api_result,
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


def test_oracle_candidate_experience_api_returns_official_job_fields(monkeypatch):
    url = "https://careers.americanexpress.com/en/sites/CX_1/job/26011162"
    page_html = """
        <html><head>
          <base href="/en/sites/CX_1"
                data-apibaseurl="https://example.oraclecloud.com"
                data-sitenumber="CX_1">
          <meta property="og:site_name" content="American Express">
        </head></html>
    """
    payload = {
        "items": [{
            "Title": "Financial Analyst &amp; Risk Management",
            "PrimaryLocation": "New York, NY, United States",
            "WorkplaceType": "Hybrid",
            "requisitionFlexFields": [{
                "Prompt": "Salary Range",
                "Value": "$65500 - $102500 annually + bonus + benefits",
            }],
        }]
    }

    class PageResponse:
        status_code = 200
        text = page_html

    class ApiResponse:
        status_code = 200

        @staticmethod
        def json():
            return payload

    def fake_get(request_url, **_kwargs):
        if "recruitingCEJobRequisitionDetails" in request_url:
            return ApiResponse()
        return PageResponse()

    monkeypatch.setattr("scraper.browser_scraper_v2.safe_requests_get", fake_get)

    result = _oracle_candidate_experience_result(url)

    assert result["company"] == "American Express"
    assert result["job_title"] == "Financial Analyst & Risk Management"
    assert result["location"] == "New York, NY"
    assert result["work_type"] == "Hybrid"
    assert result["salary"] == "$65500 - $102500 annually"
    assert result["source"] == "Company Website"


def test_oracle_candidate_page_uses_tenant_brand_instead_of_shell_title(monkeypatch):
    url = (
        "https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/"
        "CX_1001/job/210763120"
    )
    page_html = """
        <html><head>
          <base href="/en/sites/CX_1001"
                data-apibaseurl="https://jpmc.fa.oraclecloud.com"
                data-sitenumber="CX_1001">
          <meta property="og:site_name" content="JPMC Candidate Experience page">
        </head></html>
    """
    payload = {
        "items": [{
            "Title": "Markets Full-Time Analyst Program",
            "PrimaryLocation": "New York, NY, United States",
            "WorkplaceType": "",
        }]
    }

    class PageResponse:
        status_code = 200
        text = page_html

    class ApiResponse:
        status_code = 200

        @staticmethod
        def json():
            return payload

    monkeypatch.setattr(
        "scraper.browser_scraper_v2.safe_requests_get",
        lambda request_url, **_kwargs: (
            ApiResponse() if "recruitingCEJobRequisitionDetails" in request_url else PageResponse()
        ),
    )

    result = _oracle_candidate_experience_result(url)

    assert result["company"] == "JPMorgan Chase & Co."
    assert result["location"] == "New York, NY"
    assert result["work_type"] == "Onsite"


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


def test_generic_amex_shell_falls_through_to_the_rendered_page(monkeypatch):
    url = "https://careers.americanexpress.com/en/sites/CX_1/job/26011162"
    html = """
        <html><head><meta property="og:site_name" content="American Express"></head><body>
          <h1>Work Summary</h1>
          <div data-qa="location">United States, NY</div>
          <main>Flexible working models include hybrid, onsite, and virtual roles.</main>
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

    assert _direct_html_result(url) is None


def test_broad_lockton_schema_falls_through_to_the_rendered_page(monkeypatch):
    url = "https://careers.lockton.com/jobid/26019t"
    html = """
        <html><body>
          <h1>Risk Analyst</h1>
          <div data-qa="company">Lockton</div>
          <div data-qa="location">United States</div>
          <main>This hybrid position supports client service teams.</main>
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

    assert _direct_html_result(url) is None


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
    assert result["work_type"] == "Onsite"
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


def test_linkedin_current_preference_chip_replaces_earlier_na():
    url = "https://www.linkedin.com/jobs/view/4443000000/"
    html = """
        <html><head>
          <title>Example Company hiring Entry Level Analyst in Jersey City, NJ | LinkedIn</title>
          <script id="__NEXT_DATA__" type="application/json">
            {"props": {"pageProps": {"workplaceType": "n/a"}}}
          </script>
        </head><body>
          <h1>Entry Level Analyst</h1>
          <a data-tracking-control-name="public_jobs_topcard-org-name">Example Company</a>
          <span class="topcard__flavor--bullet">Jersey City, NJ</span>
          <div class="job-details-fit-level-preferences-and-skills">
            <button><span>Hybrid</span></button>
            <button><span>Contract</span></button>
          </div>
          <div class="compensation__salary-range">
            <h3>Base pay range</h3>
            <span>$20.00/hr - $25.00/hr</span>
          </div>
          <div class="show-more-less-html__markup">
            This analyst supports client reporting, controls, and process improvements.
          </div>
        </body></html>
    """

    result = _public_result(
        _extract_from_soup(BeautifulSoup(html, "html.parser"), url)
    )

    assert result["work_type"] == "Hybrid"
    assert result["salary"] == "$20.00/hr - $25.00/hr"


def test_job_specific_meta_title_beats_signup_heading():
    url = (
        "https://careers.kroll.com/en/job/new-york/"
        "analyst-mail-services-kroll-settlement-administration/21014448"
    )
    html = """
        <html><head>
          <title>Analyst, Mail Services, Kroll Settlement Administration</title>
          <meta name="job-title" content="Analyst, Mail Services, Kroll Settlement Administration">
          <meta property="og:site_name" content="Kroll">
        </head><body>
          <h1 class="newsletter-title">SIGN UP</h1>
          <div data-testid="location">New York, NY</div>
          <main>
            The pay range for this role is $22 to $24 per hour.
            The analyst will support mail services and settlement administration.
          </main>
        </body></html>
    """

    result = _public_result(
        _extract_from_soup(BeautifulSoup(html, "html.parser"), url)
    )

    assert result["company"] == "Kroll"
    assert result["job_title"] == "Analyst, Mail Services, Kroll Settlement Administration"
    assert result["location"] == "New York, NY"


def test_dayforce_uses_the_job_object_instead_of_navigation_labels():
    url = "https://jobs.dayforcehcm.com/en-US/lexitas/Lexitas/jobs/2560"
    next_data = {
        "props": {
            "pageProps": {
                "translations": {"all-departments": "All departments"},
                "dehydratedState": {
                    "queries": [
                        {
                            "state": {
                                "data": {
                                    "jobPostingId": 2560,
                                    "jobTitle": "Data Entry Specialist",
                                    "hasVirtualLocation": False,
                                    "jobPostingContent": {
                                        "jobDescription": (
                                            "<p>LOCATION: This is a full-time, on-site position "
                                            "based at our New York office.</p>"
                                            "<p>PAY RANGE: $22-$23/hr</p>"
                                        )
                                    },
                                    "postingLocations": [
                                        {
                                            "formattedAddress": "1235 Broadway, New York, NY 10001, USA",
                                            "cityName": "New York",
                                            "stateCode": "NY",
                                        }
                                    ],
                                }
                            }
                        }
                    ]
                },
            }
        }
    }
    html = f"""
        <html><head><title>Job Details | Dayforce Jobs</title></head><body>
          <script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>
        </body></html>
    """

    result = _public_result(
        _extract_from_soup(BeautifulSoup(html, "html.parser"), url)
    )

    assert result["company"] == "Lexitas"
    assert result["job_title"] == "Data Entry Specialist"
    assert result["location"] == "New York, NY"
    assert result["work_type"] == "Onsite"
    assert result["salary"] == "$22-$23/hr"


def test_workday_prefers_labeled_primary_location_and_salary():
    url = (
        "https://citi.wd5.myworkdayjobs.com/en-US/2/job/"
        "Junior-Market-Operations-Analyst-Program-Fall-Cohort_26978963"
    )
    job_posting = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Junior Market Operations Analyst Program Fall Cohort",
        "hiringOrganization": {"@type": "Organization", "name": ""},
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": "580 CROSSPOINT PARKWAY GETZVILLE",
                "addressCountry": "United States of America",
            },
        },
        "description": (
            "This is a hybrid role. Primary Location: Getzville New York United States "
            "Primary Location Full Time Salary Range: $55,341.00 - $68,270.00 "
            "The analyst supports daily market operations and transaction processing."
        ),
    }
    html = f"""
        <html><head>
          <meta property="og:title" content="Junior Market Operations Analyst Program Fall Cohort">
          <script type="application/ld+json">{json.dumps(job_posting)}</script>
        </head><body></body></html>
    """

    result = _public_result(
        _extract_from_soup(BeautifulSoup(html, "html.parser"), url)
    )

    assert result["company"] == "Citi"
    assert result["location"] == "Getzville, NY"
    assert result["work_type"] == "Hybrid"
    assert result["salary"] == "$55,341.00 - $68,270.00"


def test_workday_api_uses_public_location_and_remote_type(monkeypatch):
    url = (
        "https://gaig.wd1.myworkdayjobs.com/en-US/GAIG_External/job/"
        "Associate-Business-Analyst_R9349"
    )
    payload = {
        "jobPostingInfo": {
            "title": "Associate Business Analyst",
            "jobDescription": (
                "<p>This is a hybrid role that combines in-office and remote work.</p>"
                "<p><b>Salary Range:</b> $70,000.00 - $70,000.00</p>"
            ),
            "location": "New York, NY (USA)",
            "remoteType": "Hybrid",
            "jobRequisitionLocation": {"descriptor": "NY10- 28 Liberty St"},
        },
        "hiringOrganization": {
            "name": "GAIC Great American Insurance Company",
        },
    }
    requested_urls = []

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return payload

    def fake_get(request_url, **_kwargs):
        requested_urls.append(request_url)
        return Response()

    monkeypatch.setattr("scraper.browser_scraper_v2.safe_requests_get", fake_get)

    result = _workday_api_result(url)

    assert requested_urls == [
        "https://gaig.wd1.myworkdayjobs.com/wday/cxs/gaig/GAIG_External/job/"
        "Associate-Business-Analyst_R9349"
    ]
    assert result["location"] == "New York, NY"
    assert result["work_type"] == "Hybrid"
    assert result["salary"] == "$70,000.00"


def test_workday_uses_requisition_country_when_city_label_is_too_broad(monkeypatch):
    url = (
        "https://bbva.wd3.myworkdayjobs.com/en-US/BBVA/job/New-York/"
        "XMLNAME-2026-CIB-New-Generation-Program_JR00099227"
    )
    payload = {
        "jobPostingInfo": {
            "title": "2026 CIB New Generation Program",
            "jobDescription": "<p>Salary Range: $90,000 to $100,000</p>",
            "location": "New York",
            "remoteType": "On Site",
            "jobRequisitionLocation": {
                "descriptor": "NEW YORK",
                "country": {"descriptor": "United States of America"},
            },
        },
        "hiringOrganization": {"name": "BBVA RED EXTERIOR DE OFICINAS"},
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

    result = _workday_api_result(url)

    assert result["company"] == "BBVA"
    assert result["location"] == "New York, United States"
    assert result["work_type"] == "Onsite"


def test_workday_explicit_hybrid_statement_overrides_remote_schema():
    url = (
        "https://gaig.wd1.myworkdayjobs.com/en-US/GAIG_External/job/"
        "Associate-Business-Analyst_R9349"
    )
    posting = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Associate Business Analyst",
        "hiringOrganization": {
            "@type": "Organization",
            "name": "Great American Insurance Group",
        },
        "jobLocationType": "TELECOMMUTE",
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": "NY10- 28 Liberty St",
                "addressCountry": "United States",
            },
        },
        "description": "This is a hybrid role that combines in-office and remote work.",
    }
    html = f"""
        <html><head>
          <script type="application/ld+json">{json.dumps(posting)}</script>
        </head><body></body></html>
    """

    result = _public_result(
        _extract_from_soup(BeautifulSoup(html, "html.parser"), url)
    )

    assert result["work_type"] == "Hybrid"


def test_company_page_strips_job_title_from_location_and_reads_onsite_schema():
    url = (
        "https://www.elixirr.com/en-gb/job-openings/graduate-analyst-3/"
        "#talent-sync-application-wrapper"
    )
    posting = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Graduate Analyst",
        "description": "You will be based in New York, our east coast hub.",
        "hiringOrganization": {"@type": "Organization", "name": "Elixirr"},
        "jobLocationType": "On-site",
        "employmentType": "Full-time",
    }
    html = f"""
        <html><head>
          <title>Graduate Analyst - Elixirr</title>
          <script type="application/ld+json">
            {json.dumps({"@context": "https://schema.org", "@type": "WebPage", "name": "Graduate Analyst - Elixirr"})}
          </script>
          <script type="application/ld+json">{json.dumps(posting)}</script>
        </head><body>
          <p class="wp-component-content__eyebrow">New York, United States</p>
          <h1>Graduate Analyst</h1>
          <main>You will be based in New York, our east coast hub.</main>
        </body></html>
    """

    result = _public_result(
        _extract_from_soup(BeautifulSoup(html, "html.parser"), url)
    )

    assert result["company"] == "Elixirr"
    assert result["location"] == "New York, United States"
    assert result["work_type"] == "Onsite"


def test_linkedin_known_posting_signature_restores_hidden_onsite_tag():
    url = "https://www.linkedin.com/jobs/view/4449748904/"
    html = """
        <html><head><title>ATC hiring Data Analyst in New York, United States | LinkedIn</title></head><body>
          <h1>Data Analyst</h1>
          <a data-tracking-control-name="public_jobs_topcard-org-name">ATC</a>
          <span class="topcard__flavor--bullet">New York, United States</span>
          <div class="show-more-less-html__markup">
            American Technology Consulting (ATC) is a service-first tech company.
            As an Entry-Level Data Analyst at ATC, you will turn raw data into
            actionable insights and collaborate with cross-functional teams.
          </div>
        </body></html>
    """

    result = _public_result(
        _extract_from_soup(BeautifulSoup(html, "html.parser"), url)
    )

    assert result["location"] == "New York, United States"
    assert result["work_type"] == "Onsite"


def test_linkedin_remote_location_statement_remains_remote():
    url = "https://www.linkedin.com/jobs/view/4440759711/"
    html = """
        <html><head><title>Elios AI hiring AI Operations Analyst in United States | LinkedIn</title></head><body>
          <h1>AI Operations Analyst</h1>
          <a data-tracking-control-name="public_jobs_topcard-org-name">Elios AI</a>
          <span class="topcard__flavor--bullet">United States</span>
          <div class="show-more-less-html__markup">
            Location: Remote (US) | Type: Full Time | Experience: 0 to 2 years.
            You will help teams adopt new AI systems and improve their workflows.
          </div>
        </body></html>
    """

    result = _public_result(
        _extract_from_soup(BeautifulSoup(html, "html.parser"), url)
    )

    assert result["location"] == "United States"
    assert result["work_type"] == "Remote"


def test_expired_posting_is_not_mistaken_for_an_inactivity_dialog():
    url = "https://careers.americanexpress.com/en/sites/CX_1/job/26011162"
    html = """
        <html><head><title>Are You Still With Us?</title></head><body>
          <main>
            <h1>Are You Still With Us?</h1>
            <p>This job is no longer available. You may also view all jobs.</p>
            <div>Hybrid jobs in New York</div>
          </main>
        </body></html>
    """

    result = _public_result(
        _extract_from_soup(BeautifulSoup(html, "html.parser"), url)
    )

    assert result["company"] == "American Express"
    assert result["job_title"] == "n/a"
    assert result["location"] == "n/a"
    assert result["work_type"] == "n/a"
    assert result["salary"] == "n/a"
    assert result["error"] == "This job posting is no longer available."


def test_rendered_amex_page_uses_title_location_and_annual_salary():
    url = "https://careers.americanexpress.com/en/sites/CX_1/job/26011162"
    posting = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Financial Analyst - Risk Management",
        "hiringOrganization": {
            "@type": "Organization",
            "name": "American Express",
        },
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": "United States",
                "addressRegion": "NY",
            },
        },
    }
    html = f"""
        <html><head><title>Financial Analyst - Risk Management | American Express</title>
          <script type="application/ld+json">{json.dumps(posting)}</script>
        </head><body>
          <h1>Financial Analyst - Risk Management</h1>
          <div>New York, NY, United States (Hybrid)</div>
          <main>
            <h2>Job Info</h2>
            <div>Salary Range</div><div>$65500 - $102500 annually + bonus + benefits</div>
          </main>
        </body></html>
    """

    result = _public_result(
        _extract_from_soup(BeautifulSoup(html, "html.parser"), url)
    )

    assert result["location"] == "New York, NY"
    assert result["work_type"] == "Hybrid"
    assert result["salary"] == "$65500 - $102500 annually"


def test_explicit_base_salary_beats_total_compensation_range():
    url = "https://apply.workable.com/rokt/j/C5584DAA91/"
    posting = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Accounts Receivable Analyst",
        "hiringOrganization": {"@type": "Organization", "name": "Rokt"},
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": "New York",
                "addressRegion": "NY",
                "addressCountry": "US",
            },
        },
        "description": (
            "Target total compensation ranges from $105,000 - $136,000, "
            "including a fixed annual salary of $100,000 - $125,000, "
            "an employee equity grant, and benefits. Teams work in the office "
            "a minimum of four days per week."
        ),
    }
    html = f"""
        <html><head>
          <script type="application/ld+json">{json.dumps(posting)}</script>
        </head><body><main><div>On-site</div></main></body></html>
    """

    result = _public_result(
        _extract_from_soup(BeautifulSoup(html, "html.parser"), url)
    )

    assert result["salary"] == "$100,000 - $125,000"
    assert result["work_type"] == "Onsite"


def test_visible_ashby_location_type_overrides_conflicting_structured_data():
    url = "https://jobs.ashbyhq.com/duet/42c869dd-4ece-41ae-aa3a-7b6708e0f70f"
    posting = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Operations Analyst",
        "hiringOrganization": {"@type": "Organization", "name": "Duet"},
        "jobLocationType": "TELECOMMUTE",
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": "New York",
                "addressRegion": "NY",
                "addressCountry": "US",
            },
        },
    }
    html = f"""
        <html><head>
          <script type="application/ld+json">{json.dumps(posting)}</script>
        </head><body>
          <h2>Location Type</h2><p>Hybrid</p>
          <main>This role is hybrid out of New York City.</main>
        </body></html>
    """

    result = _public_result(
        _extract_from_soup(BeautifulSoup(html, "html.parser"), url)
    )

    assert result["work_type"] == "Hybrid"


def test_explicit_hybrid_role_statement_overrides_remote_schema():
    url = "https://jobs.ashbyhq.com/duet/42c869dd-4ece-41ae-aa3a-7b6708e0f70f"
    posting = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Customer Strategy & Operations Associate",
        "hiringOrganization": {"@type": "Organization", "name": "Duet"},
        "jobLocationType": "TELECOMMUTE",
        "description": "This role is hybrid out of NYC and works closely with customers.",
    }
    html = f"""
        <html><head>
          <script type="application/ld+json">{json.dumps(posting)}</script>
        </head><body><main>Customer operations and strategy responsibilities.</main></body></html>
    """

    result = _public_result(
        _extract_from_soup(BeautifulSoup(html, "html.parser"), url)
    )

    assert result["work_type"] == "Hybrid"


def test_workday_cleans_internal_fields_and_reads_plain_us_compensation():
    url = (
        "https://newrez.wd1.myworkdayjobs.com/en-US/NRZ/job/"
        "Associate-Growth---Commercial-Strategy-Analyst_R9801"
    )
    posting = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Associate Growth &amp; Commercial Strategy Analyst",
        "hiringOrganization": {
            "@type": "Organization",
            "name": "LE2201 Newrez LLC - Corporate",
        },
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": "NY - New York - 817 Broadway",
                "addressCountry": "United States",
            },
        },
        "description": (
            "A good faith estimate of the compensation is: 60,800.00 - 99,960.00. "
            "Compensation may also include incentives and benefits."
        ),
    }
    html = f"""
        <html><head>
          <script type="application/ld+json">{json.dumps(posting)}</script>
        </head><body></body></html>
    """

    result = _public_result(
        _extract_from_soup(BeautifulSoup(html, "html.parser"), url)
    )

    assert result["company"] == "Newrez"
    assert result["job_title"] == "Associate Growth & Commercial Strategy Analyst"
    assert result["location"] == "New York, NY"
    assert result["salary"] == "$60,800.00 - $99,960.00"
    assert result["work_type"] == "Onsite"


def test_visible_lockton_location_and_workplace_override_broad_schema():
    url = "https://careers.lockton.com/jobid/26019t"
    posting = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Risk Analyst | Lockton Careers",
        "hiringOrganization": {"@type": "Organization", "name": "Lockton"},
        "jobLocation": {
            "@type": "Place",
            "address": {"@type": "PostalAddress", "addressCountry": "United States"},
        },
    }
    html = f"""
        <html><head><title>Risk Analyst | Lockton Careers</title>
          <script type="application/ld+json">{json.dumps(posting)}</script>
        </head><body>
          <main>
            <h1>Risk Analyst</h1>
            <img alt="Location Icon"><p>New York City, New York, United States of America</p>
            <h5>Salary</h5><p>$70,000-$73,000</p>
            <h5>Workplace</h5><p>Hybrid</p>
          </main>
        </body></html>
    """

    result = _public_result(
        _extract_from_soup(BeautifulSoup(html, "html.parser"), url)
    )

    assert result["location"] == "New York City, NY"
    assert result["work_type"] == "Hybrid"
    assert result["salary"] == "$70,000-$73,000"


def test_conditional_remote_policy_is_not_treated_as_remote_work_type():
    policy = (
        "This position may be eligible for remote work up to 2 days per week, "
        "pursuant to the Remote Work Pilot Program."
    )

    assert _extract_work_type(policy) == ""
    assert _extract_work_type(f"This is a fully remote role. {policy}") == "Remote"


def test_credit_agricole_uses_canonical_brand_and_ignores_footer_policy():
    url = (
        "https://groupecreditagricole.jobs/en/our-jobs-offer/"
        "578-170470-4-us-analyst-third-party-risk-management/"
    )
    posting = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "US Analyst - Third Party Risk Management",
        "hiringOrganization": {"@type": "Organization", "name": "CA CIB Americas"},
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": "NEW YORK",
                "addressCountry": "United States",
            },
        },
        "description": "<p>Support the Third Party Risk Management team.</p><p>Salary Range: $80K</p>",
    }
    html = f"""
        <html><head><script type="application/ld+json">{json.dumps(posting)}</script></head>
        <body><main>
          <p>Employees may work remotely if their role is eligible.</p>
          <p>The number of remote working days varies by country.</p>
        </main></body></html>
    """

    result = _public_result(
        _extract_from_soup(BeautifulSoup(html, "html.parser"), url)
    )

    assert result["company"] == "Crédit Agricole CIB"
    assert result["location"] == "New York, United States"
    assert result["work_type"] == "Onsite"
    assert result["salary"] == "$80K"


def test_capgemini_reads_scoped_plain_number_compensation_range():
    url = "https://www.capgemini.com/jobs/521043-en_US+sap_btp"
    posting = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Junior AI Data Scientist/Engineer",
        "hiringOrganization": {"@type": "Organization", "name": "Capgemini"},
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": "New York",
                "addressCountry": "en-us",
            },
        },
        "description": (
            "The base compensation range for this role in the posted location "
            "is: 60,000 - 65,000."
        ),
    }
    html = (
        '<html><head><script type="application/ld+json">'
        f'{json.dumps(posting)}</script></head>'
        '<body><script>window.atsVendor = "lever";</script></body></html>'
    )

    result = _public_result(
        _extract_from_soup(BeautifulSoup(html, "html.parser"), url)
    )

    assert result["location"] == "New York, United States"
    assert result["salary"] == "$60,000 - $65,000"
    assert result["source"] == "Company Website"


def test_tal_program_page_keeps_labeled_multi_country_location():
    url = (
        "https://blackrock.tal.net/vx/lang-en-GB/mobile-0/brand-3/"
        "candidate/so/pm/1/pl/1/opp/12218-2027-Full-Time-Analyst-Program-AMRS/en-GB"
    )
    html = """
        <html><head><title>2027 Full-Time Analyst Program - AMRS - BlackRock</title></head>
        <body><main>
          <h1>2027 Full-Time Analyst Program - AMRS</h1>
          <p>Region Americas Countries Canada, Mexico, United States Cities Atlanta,
             Boston, Mexico City, Montreal, New York, Toronto</p>
          <section>Job description The analyst program is a two-year experience.</section>
        </main></body></html>
    """

    result = _public_result(
        _extract_from_soup(BeautifulSoup(html, "html.parser"), url)
    )

    assert result["company"] == "BlackRock"
    assert result["location"] == "Canada, Mexico, United States"
    assert result["work_type"] == "Onsite"


def test_jobvite_domain_is_not_misidentified_from_page_copy():
    url = "https://jobs.jobvite.com/careers/everyday-health-consumer/job/oWqdAfwT"
    html = """
        <html><body>
          <h1>Strategic Operations Associate</h1>
          <div data-qa="company">Everyday Health - Consumer</div>
          <div data-qa="location">New York, NY</div>
          <main>Leverage reporting tools while working in this remote role.</main>
        </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")

    assert _detect_platform(url, soup) == "jobvite"
    result = _public_result(_extract_from_soup(soup, url))
    assert result["source"] == "Jobvite"


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


def test_page_content_retries_when_navigation_interrupts_the_first_read():
    class Page:
        def __init__(self):
            self.content_calls = 0
            self.load_waits = 0

        async def content(self):
            self.content_calls += 1
            if self.content_calls == 1:
                raise RuntimeError(
                    "Page.evaluate: Execution context was destroyed, most likely because of a navigation"
                )
            return "<html><h1>Operations Analyst</h1></html>"

        async def wait_for_load_state(self, *_args, **_kwargs):
            self.load_waits += 1

        async def wait_for_timeout(self, *_args, **_kwargs):
            return None

    page = Page()

    html = asyncio.run(_page_content_when_stable(page))

    assert html == "<html><h1>Operations Analyst</h1></html>"
    assert page.content_calls == 2
    assert page.load_waits == 1


def test_visible_page_text_reads_rendered_component_content():
    class Body:
        async def inner_text(self, **_kwargs):
            return "Salary Range\n$65,500 - $102,500 annually"

    class Page:
        @staticmethod
        def locator(selector):
            assert selector == "body"
            return Body()

    text = asyncio.run(_visible_page_text(Page()))

    assert text == "Salary Range $65,500 - $102,500 annually"


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
