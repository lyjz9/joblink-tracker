from scraper.source_tracking import (
    application_portal_for_url,
    enrich_source_tracking,
    found_on_for_url,
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


def test_found_on_uses_the_user_choice_or_a_job_board_url():
    workday = "https://example.wd5.myworkdayjobs.com/en-US/jobs/job/Analyst_R123"
    assert found_on_for_url(workday, "LinkedIn") == "LinkedIn"
    assert found_on_for_url(workday) == "N/A"
    assert found_on_for_url("https://www.linkedin.com/jobs/view/4443868424/") == "LinkedIn"


def test_found_on_uses_supported_tracking_parameters_without_guessing_unknown_values():
    assert found_on_for_url(
        "https://example.wd5.myworkdayjobs.com/job/Analyst_R123?source=LinkedIn"
    ) == "LinkedIn"
    assert found_on_for_url(
        "https://apply.workable.com/example/j/123/?utm_source=google_jobs_apply"
    ) == "Google Jobs"
    assert found_on_for_url(
        "https://careers.example.com/job/123?source=opaque-code"
    ) == "N/A"


def test_legacy_source_can_represent_discovery_while_url_sets_portal():
    job = enrich_source_tracking(
        {
            "job_link": "https://jobs.ashbyhq.com/example/123",
            "source": "LinkedIn",
        }
    )

    assert job["found_on"] == "LinkedIn"
    assert job["application_portal"] == "Ashby"
    assert job["source"] == "Ashby"
