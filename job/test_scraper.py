#!/usr/bin/env python
"""Quick test script for job scraper - test one or more URLs."""
import sys
sys.path.insert(0, r'c:\Users\jzeng\Documents\job')

from scraper.browser_scraper_v2 import parse_job_with_browser

# Test URLs - add your URLs here
test_urls = [
    # Add your job URLs below, one per line
    # Example: "https://www.linkedin.com/jobs/view/...",
    # Example: "https://www.indeed.com/viewjob?jk=...",
]

if len(sys.argv) > 1:
    # Allow passing URL as command line argument
    test_urls = sys.argv[1:]

if not test_urls:
    print("Usage: python test_scraper.py <url1> [url2] [url3] ...")
    print("\nExample:")
    print('  python test_scraper.py "https://www.charliehealth.com/careers/current-openings?gh_jid=5742812004"')
    print("\nOr edit this file and add URLs to test_urls list.")
    sys.exit(1)

print("=" * 80)
print("JOB SCRAPER TESTER")
print("=" * 80)

for i, url in enumerate(test_urls, 1):
    print(f"\n[{i}/{len(test_urls)}] Testing: {url[:70]}...")
    print("-" * 80)
    try:
        result = parse_job_with_browser(url)
        
        # Show results
        success = True
        for key, value in result.items():
            if key == 'error':
                print(f"  ✗ ERROR: {value}")
                success = False
            elif value and value != '':
                print(f"  ✓ {key}: {value}")
        
        if success:
            print("\n  Status: SUCCESS")
        else:
            print("\n  Status: PARTIAL - Some fields missing")
            
    except Exception as e:
        print(f"  ✗ FAILED: {e}")

print("\n" + "=" * 80)
