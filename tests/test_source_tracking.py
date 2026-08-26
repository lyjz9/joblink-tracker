from scraper.source_tracking import (
    application_portal_for_url,
    enrich_source_tracking,
)


def test_application_portal_is_inferred_from_the_actual_job_url():
    assert application_portal_for_url(
        "https://example.wd5.myworkdayjobs.com/en-US/jobs/job/Analyst_R123"
    ) == "Workday"
    assert application_portal_for_url(
        "https://jobs.ashbyhq.com/example/123"
    ) == "Ashby"
    assert application_portal_for_url(
        "https://careers.example.com/jobs/123"
    ) == "Company Website"
    assert application_portal_for_url(
        "https://blackrock.tal.net/vx/opp/12218/en-GB"
    ) == "TAL"
    assert application_portal_for_url(
        "https://job-boards.greenhouse.io/fanaticscollectibles/jobs/4363369009"
    ) == "Greenhouse"
    assert application_portal_for_url(
        "https://jobs.lever.co/nomadmktg/a949c205-eb76-4eeb-99be-4841d1e07dd5"
    ) == "Lever"
    assert application_portal_for_url(
        "https://www.builtinnyc.com/job/data-analyst/10804121"
    ) == "Built In NYC"
    assert application_portal_for_url(
        "https://hiringcafe.com/job/business-operations-analyst-hometap-boston-massachusetts-q3y3y9pl0rk2sdmy"
    ) == "Hiring Cafe"
    assert application_portal_for_url(
        "https://hiringcafe.com/job/task-associate-ulta-beauty-mobile-alabama-5zqvmbrvot7v5jsp"
    ) == "Hiring Cafe"


def test_result_uses_the_url_for_its_portal_and_removes_retired_discovery_data():
    job = enrich_source_tracking(
        {
            "job_link": "https://jobs.ashbyhq.com/example/123",
            "source": "LinkedIn",
        }
    )

    assert "found_on" not in job
    assert job["application_portal"] == "Ashby"
    assert job["source"] == "Ashby"
