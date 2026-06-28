#!/usr/bin/env python
"""Return one scraped job as JSON for the Excel macro."""

import json
import sys
import time

from scraper.browser_scraper_v2 import parse_job_with_browser


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "One job URL is required."}))
        return 1

    result = {}
    for attempt in range(2):
        try:
            result = parse_job_with_browser(sys.argv[1])
        except Exception as exc:
            result = {"error": str(exc)}
        if not result.get("error"):
            break
        if attempt == 0:
            time.sleep(2)

    print(json.dumps(result, ensure_ascii=True))
    return 0 if not result.get("error") else 2


if __name__ == "__main__":
    raise SystemExit(main())
