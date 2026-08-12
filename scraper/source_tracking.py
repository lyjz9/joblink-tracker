"""Keep job discovery and application destinations as separate fields."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlparse

from scraper.browser_scraper_v2 import _detect_platform, _source_label


DISCOVERY_LABELS = {
    "LinkedIn",
    "Indeed",
    "Glassdoor",
    "ZipRecruiter",
    "Monster",
    "Wellfound",
    "Upwork",
    "SimplyHired",
    "Dice",
    "Handshake",
    "Google Jobs",
    "Jooble",
}

DISCOVERY_QUERY_ALIASES = (
    ("linkedin", "LinkedIn"),
    ("indeed", "Indeed"),
    ("glassdoor", "Glassdoor"),
    ("ziprecruiter", "ZipRecruiter"),
    ("monster", "Monster"),
    ("wellfound", "Wellfound"),
    ("angellist", "Wellfound"),
    ("upwork", "Upwork"),
    ("simplyhired", "SimplyHired"),
    ("dice", "Dice"),
    ("handshake", "Handshake"),
    ("google_jobs", "Google Jobs"),
    ("google jobs", "Google Jobs"),
    ("jooble", "Jooble"),
)

DISCOVERY_QUERY_KEYS = {
    "utm_source",
    "source",
    "src",
    "ref",
    "referrer",
    "lever-source",
    "__jvsd",
    "__jvst",
}

PORTAL_DOMAIN_LABELS = (
    ("joinhandshake.com", "Handshake"),
    ("oraclecloud.com", "Oracle Recruiting"),
    ("taleo.net", "Taleo"),
    ("eploy.net", "Eploy"),
    ("eightfold.ai", "Eightfold"),
    ("successfactors.com", "SAP SuccessFactors"),
)

KNOWN_LABELS = {
    label.casefold(): label
    for label in {
        *DISCOVERY_LABELS,
        "N/A",
        "Company Website",
        "Referral",
        "Other",
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
        "Eploy",
        "Eightfold",
        "SAP SuccessFactors",
    }
}


def normalize_source_label(value: object) -> str:
    text = " ".join(str(value or "").split()).strip()
    if not text or text.casefold() in {"auto", "auto from link"}:
        return ""
    if text.casefold() in {"n/a", "na", "none", "null"}:
        return "N/A"
    return KNOWN_LABELS.get(text.casefold(), text[:80])


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

    legacy = normalize_source_label(legacy_source)
    return legacy if legacy and legacy != "N/A" else "Company Website"


def found_on_for_url(
    url: object,
    selected: object = "",
    legacy_source: object = "",
) -> str:
    explicit = normalize_source_label(selected)
    if explicit:
        return explicit

    try:
        query_values = (
            str(value).casefold()
            for key, value in parse_qsl(urlparse(str(url or "")).query)
            if key.casefold() in DISCOVERY_QUERY_KEYS
        )
        for value in query_values:
            for marker, label in DISCOVERY_QUERY_ALIASES:
                if marker in value:
                    return label
            if value in {"careersite", "career site", "company website"}:
                return "Company Website"
    except ValueError:
        pass

    legacy = normalize_source_label(legacy_source)
    if legacy in DISCOVERY_LABELS:
        return legacy

    portal = application_portal_for_url(url, legacy_source)
    return portal if portal in DISCOVERY_LABELS else "N/A"


def enrich_source_tracking(
    result: dict,
    url: object = "",
    *,
    found_on: object = "",
) -> dict:
    enriched = dict(result or {})
    job_url = str(url or enriched.get("job_link") or "").strip()
    legacy_source = enriched.get("source", "")
    portal = normalize_source_label(enriched.get("application_portal"))
    if not portal or portal == "N/A":
        portal = application_portal_for_url(job_url, legacy_source)

    selected_found_on = normalize_source_label(found_on)
    stored_found_on = normalize_source_label(enriched.get("found_on"))
    discovery = selected_found_on or stored_found_on or found_on_for_url(
        job_url,
        legacy_source=legacy_source,
    )

    enriched["found_on"] = discovery
    enriched["application_portal"] = portal
    # Keep the legacy field while older sessions and reliability code migrate.
    enriched["source"] = portal
    return enriched
