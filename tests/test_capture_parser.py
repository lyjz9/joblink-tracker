from scraper.capture_parser import _parse_captured_page


def test_linkedin_capture_prefers_the_visible_work_type_tag():
    payload = {
        "url": "https://www.linkedin.com/jobs/view/4443000000/",
        "title": "Entry Level Analyst | LinkedIn",
        "text": (
            "Entry Level Analyst\n"
            "Phyton Talent Advisors\n"
            "Jersey City, NJ\n"
            "$20/hr - $25/hr\n"
            "Hybrid\n"
            "Contract\n"
            "Similar jobs\n"
            "Remote Operations Analyst\n"
            "On-site Data Analyst"
        ),
        "candidates": {
            "headings": ["Entry Level Analyst"],
            "workTypeTags": ["Hybrid"],
            "labelPairs": [
                {"label": "Company", "value": "Phyton Talent Advisors"},
                {"label": "Location", "value": "Jersey City, NJ"},
                {"label": "Base pay", "value": "$20/hr - $25/hr"},
            ],
            "headerBlocks": [],
            "keywordLines": ["Hybrid", "Remote Operations Analyst", "On-site Data Analyst"],
        },
        "html": "<html><body><main><h1>Entry Level Analyst</h1></main></body></html>",
    }

    result = _parse_captured_page(payload)

    assert result["company"] == "Phyton Talent Advisors"
    assert result["job_title"] == "Entry Level Analyst"
    assert result["location"] == "Jersey City, NJ"
    assert result["work_type"] == "Hybrid"
    assert result["capture_evidence"]["work_type"] == "page_tag"
    assert "linkedin_work_type_hidden" not in result["review_issues"]
