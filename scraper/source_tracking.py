"""Normalize application portals while retaining the legacy ``source`` alias."""

from __future__ import annotations

from urllib.parse import urlparse

from scraper.browser_scraper_v2 import _detect_platform, _source_label


PORTAL_DOMAIN_LABELS = (
    ("builtinnyc.com", "Built In NYC"),
    ("hiringcafe.com", "Hiring Cafe"),
    ("joinhandshake.com", "Handshake"),
    ("oraclecloud.com", "Oracle Recruiting"),
    ("taleo.net", "Taleo"),
    ("tal.net", "TAL"),
    ("eploy.net", "Eploy"),
    ("eightfold.ai", "Eightfold"),
    ("successfactors.com", "SAP SuccessFactors"),
)

KNOWN_PORTAL_LABELS = {
    label.casefold(): label
    for label in {
        "Company Website",
        "Built In NYC",
        "Hiring Cafe",
        "Greenhouse",
        "Lever",
        "Workday",
        "Ashby",
        "SmartRecruiters",
        "Workable",
        "BambooHR",
        "Dayforce",
        "iCIMS",
        "Breezy",
        "Jobvite",
        "Oracle Recruiting",
        "Taleo",
        "TAL",
        "Eploy",
        "Eightfold",
        "SAP SuccessFactors",
        "Handshake",
        "LinkedIn",
        "Indeed",
        "Glassdoor",
        "ZipRecruiter",
        "Monster",
        "Wellfound",
        "Upwork",
        "SimplyHired",
        "Dice",
        "Google Jobs",
        "Jooble",
    }
}


def normalize_source_label(value: object) -> str:
    """Normalize portal labels, including values from legacy ``Source`` cells."""
    text = " ".join(str(value or "").split()).strip()
    if not text or text.casefold() in {"auto", "auto from link"}:
        return ""
    if text.casefold() in {"n/a", "na", "none", "null"}:
        return ""
    return KNOWN_PORTAL_LABELS.get(text.casefold(), text[:80])


def application_portal_for_url(url: object, legacy_source: object = "") -> str:
    text = str(url or "").strip()
    try:
        host = (urlparse(text).hostname or "").casefold().removeprefix("www.")
    except ValueError:
        host = ""

    if host:
        platform = _detect_platform(text)
        detected = _source_label(platform)
        if detected != "Company Website":
            return detected
        for domain, label in PORTAL_DOMAIN_LABELS:
            if host == domain or host.endswith(f".{domain}"):
                return label
        return "Company Website"

    return normalize_source_label(legacy_source) or "Company Website"


def enrich_source_tracking(result: dict, url: object = "") -> dict:
    """Return portal-only job data and discard the retired discovery field."""
    enriched = dict(result or {})
    enriched.pop("found_on", None)
    job_url = str(url or enriched.get("job_link") or "").strip()
    legacy_source = enriched.get("source", "")
    portal = normalize_source_label(enriched.get("application_portal"))
    detected_portal = application_portal_for_url(job_url, legacy_source)
    if not portal or (portal == "Company Website" and detected_portal != portal):
        portal = detected_portal

    enriched["application_portal"] = portal
    # Keep the internal alias while older sessions and reliability code migrate.
    enriched["source"] = portal
    return enriched
