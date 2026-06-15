#!/usr/bin/env python
"""Quick test script for the job scraper."""
import sys

sys.path.insert(0, r'C:\Users\jzeng\Documents\job')

from scraper.browser_scraper_v2 import parse_job_with_browser


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
print("JOB SCRAPER TESTER")
print("=" * 80)

for i, url in enumerate(test_urls, 1):
    print(f"\n[{i}/{len(test_urls)}] Testing: {url[:70]}...")
    print("-" * 80)
    try:
        result = parse_job_with_browser(url)
        success = True

        if result.get('error'):
            print(f"  ERROR: {result['error']}")
            success = False

        for key in DISPLAY_FIELDS:
            value = result.get(key, '')
            if value:
                print(f"  OK {key}: {value}")

        if success:
            print("\n  Status: SUCCESS")
        else:
            print("\n  Status: PARTIAL - Some fields missing")

    except Exception as exc:
        print(f"  FAILED: {exc}")

print("\n" + "=" * 80)
