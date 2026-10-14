"""Small helpers for metadata that can be inferred without fetching a page."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, unquote, urlparse


def extract_job_id(url: object) -> str:
    """Extract a posting identifier from common ATS URL shapes."""
    try:
        parsed = urlparse(str(url or ""))
    except ValueError:
        return ""

    query = parse_qs(parsed.query)
    for key in ("jobId", "job_id", "job", "gh_jid", "requisitionId", "reqId"):
        for value in query.get(key, []):
            match = re.search(r"(?:JR|R)?\d{5,}", value, flags=re.I)
            if match:
                return match.group(0).upper()

    path = unquote(parsed.path)
    patterns = (
        r"(?:^|[_/-])(JR\d{5,})(?:$|[./_-])",
        r"/(?:jobs?/)(\d{6,})(?:/|$)",
        r"(?:^|/)([0-9a-f]{8}-[0-9a-f-]{27,})(?:/|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, path, flags=re.I)
        if match:
            return match.group(1).upper()
    return ""
