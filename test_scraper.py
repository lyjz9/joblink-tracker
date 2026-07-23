#!/usr/bin/env python
"""Quick test script for the job scraper."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scraper.browser_scraper_v2 import parse_job_with_browser
from scraper.result_quality import _quality_issues, _review_notes


DISPLAY_FIELDS = [
    'date_applied',
    'company',
    'job_title',
    'job_link',
    'status',
    'location',
    'work_type',
    'salary',
    'follow_up',
    'source',
]


test_urls = []

if len(sys.argv) > 1:
    test_urls = sys.argv[1:]

if not test_urls:
    print("Usage: python test_scraper.py <url1> [url2] [url3] ...")
    print("\nExample:")
    print('  python test_scraper.py "https://www.indeed.com/viewjob?jk=..."')
    sys.exit(1)

print("=" * 80)
print("Linc scraper check")
print("=" * 80)

for i, url in enumerate(test_urls, 1):
    print(f"\n[{i}/{len(test_urls)}] Testing: {url[:70]}...")
    print("-" * 80)
    try:
        result = parse_job_with_browser(url)
        success = True
        issues = _quality_issues(result)

        if result.get('error'):
            print(f"  ERROR: {result['error']}")
            success = False

        for key in DISPLAY_FIELDS:
            value = result.get(key, '')
            if value:
                print(f"  OK {key}: {value}")

        if success and not issues:
            print("\n  Status: Ready")
        else:
            note = _review_notes(issues) if issues else "Some fields are missing."
            print(f"\n  Status: Review - {note}")

    except Exception as exc:
        print(f"  Could not scrape: {exc}")

print("\n" + "=" * 80)
