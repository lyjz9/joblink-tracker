"""
Browser-backed job scraper for company career pages and common ATS/job boards.

The extractor favors reliable signals in this order:
1. schema.org JobPosting / embedded app data
2. known applicant-tracking-system selectors
3. scoped job-page selectors
4. conservative text and URL fallbacks
"""
import asyncio
import re
from datetime import datetime
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from .scraper import (
    _clean_linkedin_title,
    _extract_jsonld_job_fields,
    _flatten_dict_strings,
    _get_meta_content,
    _normalize_text,
    _parse_jsonld,
    _parse_next_data,
)


JOB_BOARDS = {
    'linkedin': ['linkedin.com'],
    'indeed': ['indeed.com'],
    'glassdoor': ['glassdoor.com'],
    'ziprecruiter': ['ziprecruiter.com'],
    'greenhouse': ['greenhouse.io', 'greenhouse.com', 'boards.greenhouse.io'],
    'lever': ['lever.co', 'jobs.lever.co'],
    'workday': ['myworkdayjobs.com', 'wd1.myworkdayjobs.com', 'wd3.myworkdayjobs.com', 'wd5.myworkdayjobs.com'],
    'ashby': ['ashbyhq.com'],
    'smartrecruiters': ['smartrecruiters.com'],
    'workable': ['workable.com'],
    'bamboohr': ['bamboohr.com'],
    'icims': ['icims.com'],
}

SOURCE_LABELS = {
    'linkedin': 'LinkedIn',
    'indeed': 'Indeed',
    'glassdoor': 'Glassdoor',
    'ziprecruiter': 'ZipRecruiter',
    'greenhouse': 'Greenhouse',
    'lever': 'Lever',
    'workday': 'Workday',
    'ashby': 'Ashby',
    'smartrecruiters': 'SmartRecruiters',
    'workable': 'Workable',
    'bamboohr': 'BambooHR',
    'icims': 'iCIMS',
    'company_website': 'Company Website',
}

COMPANY_HOST_OVERRIDES = {
    'jobs.citi.com': 'Citi',
    'burberrycareers.com': 'Burberry',
    'careers.twosigma.com': 'Two Sigma',
    'hdr.taleo.net': 'HDR',
    'careers.paramount.com': 'Paramount',
    'paramount.com': 'Paramount',
    'cityjobs.nyc.gov': 'New York City',
}

FIELD_SELECTORS = {
    'job_title': [
        '[data-qa="job-title"]', '[data-testid="job-title"]', '[data-test="job-title"]',
        '[itemprop="title"]', 'h1[class*="title" i]', 'h1[class*="job" i]',
        '.posting-headline h2', '.posting-title h2', '.app-title', '.opening__title',
        '.job-title', '.job__title h1', 'h1',
    ],
    'company': [
        '[data-qa="company"]', '[data-testid="company"]', '[itemprop="hiringOrganization"]',
        '[data-testid="inlineHeader-companyName"]', '[data-company-name]',
        '[data-testid*="company" i]', 'a[data-tracking-control-name="public_jobs_topcard-org-name"]',
        '.topcard__org-name-link', '.top-card-layout__company-name',
        '.jobs-unified-top-card__company-name', '.job-details-jobs-unified-top-card__company-name',
        '.jobsearch-CompanyInfoContainer a', '.jobsearch-InlineCompanyRating-companyHeader a',
        '[class*="company-name" i]', '[class*="employer" i]', '.posting-company',
        '.top-card-layout__company-name', '.jobsearch-InlineCompanyRating-companyHeader',
    ],
    'location': [
        '[data-qa="location"]', '[data-testid="location"]', '[itemprop="jobLocation"]',
        '[data-testid="inlineHeader-companyLocation"]', '[data-testid="job-location"]',
        '[data-testid="jobsearch-JobInfoHeader-companyLocation"]',
        '[class*="job-location" i]', '.posting-categories',
        '.topcard__flavor--bullet', '.jobsearch-JobInfoHeader-subtitle div',
    ],
    'salary': [
        '[data-qa*="salary" i]', '[data-testid*="salary" i]', '[itemprop="baseSalary"]',
        '[class*="salary" i]', '[class*="compensation" i]', '[class*="pay" i]',
    ],
    'description': [
        '[data-qa="job-description"]', '[data-testid="job-description"]',
        '[itemprop="description"]', '#jobDescriptionText', '#content',
        '.job-description', '.job__description', '.posting-requirements',
        '.description', '.content', 'article', 'main',
    ],
}

ATS_HINTS = {
    'greenhouse': {
        'title': ['h1', 'h2.app-title', '.opening__title', '[data-qa="job-title"]'],
        'description': ['#content', '[data-qa="job-description"]', '.opening__description'],
    },
    'lever': {
        'title': ['.posting-headline h2', '.posting-title h2', 'h1'],
        'company': ['.main-header-logo img[alt]', '.posting-company'],
        'location': ['.posting-categories .location', '.sort-by-location', '.location'],
        'description': ['.section-wrapper', '.posting-page', '.content-wrapper'],
    },
    'ashby': {
        'title': ['h1', '[data-testid="job-title"]'],
        'location': ['[data-testid="job-location"]', '[class*="location" i]'],
        'description': ['[data-testid="job-description"]', 'main'],
    },
    'workday': {
        'title': ['h2[data-automation-id="jobPostingHeader"]', 'h1', 'h2'],
        'location': ['[data-automation-id="locations"]', '[data-automation-id="jobPostingLocation"]'],
        'description': ['[data-automation-id="jobPostingDescription"]', 'main'],
    },
    'smartrecruiters': {
        'title': ['h1', '[class*="job-title" i]'],
        'company': ['[class*="company" i]'],
        'location': ['[class*="location" i]'],
        'description': ['[class*="job-description" i]', 'section.job-sections', 'main'],
    },
}

US_STATE = r'(?:A[LKZR]|C[AOT]|D[CE]|FL|GA|HI|I[ADLN]|K[SY]|LA|M[ADEINOST]|N[CDEHJMVY]|O[HKR]|PA|RI|S[CD]|T[NX]|UT|V[AIT]|W[AIVY])'
US_STATE_NAME_TO_ABBR = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
    'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
    'district of columbia': 'DC', 'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI',
    'idaho': 'ID', 'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA',
    'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME',
    'maryland': 'MD', 'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN',
    'mississippi': 'MS', 'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE',
    'nevada': 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM',
    'new york': 'NY', 'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH',
    'oklahoma': 'OK', 'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI',
    'south carolina': 'SC', 'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX',
    'utah': 'UT', 'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA',
    'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY',
}
US_STATE_ABBR_TO_NAME = {abbr: name.title() for name, abbr in US_STATE_NAME_TO_ABBR.items()}
LOCATION_RE = re.compile(
    rf'\b(?:Remote|Hybrid|United States|US|USA|[A-Z][A-Za-z.\'-]+(?:\s+[A-Z][A-Za-z.\'-]+){{0,3}},\s*(?:{US_STATE}|United States|USA|Canada|UK|[A-Z][a-z]+))\b'
)
SALARY_RE = re.compile(
    r'(?:Base pay range\s*)?(?:USD\s*)?\$\s*\d+(?:,\d{3})*(?:\.\d+)?\s*(?:k|K)?(?:\s*(?:-|to|and)\s*(?:USD\s*)?\$?\s*\d+(?:,\d{3})*(?:\.\d+)?\s*(?:k|K)?)?(?:\s*(?:per|/)\s*(?:year|yr|hour|hr|annum))?|\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:k|K)\s*(?:-|to|and)\s*\d+(?:,\d{3})*(?:\.\d+)?\s*(?:k|K)\b|\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:-|to|and)\s*\d+(?:,\d{3})*(?:\.\d+)?\s*USD\b',
    re.IGNORECASE,
)


def _empty_result(url, platform='company_website'):
    return {
        'date_applied': datetime.now().strftime('%m/%d/%Y'),
        'company': '',
        'job_title': '',
        'job_link': url,
        'status': '',
        'location': '',
        'work_type': '',
        'salary': '',
        'follow_up': '',
        'source': _source_label(platform),
        'description': '',
    }


def _detect_platform(url, soup=None):
    host = urlparse(url).netloc.lower()
    if any(host == domain or host.endswith('.' + domain) for domain in COMPANY_HOST_OVERRIDES):
        return 'company_website'
    for board, domains in JOB_BOARDS.items():
        if any(domain in host for domain in domains):
            return board
    if soup:
        html = str(soup)[:200000].lower()
        for board in ('greenhouse', 'lever', 'ashby', 'workday', 'smartrecruiters', 'workable', 'icims'):
            if board in html:
                return board
    return 'company_website'


def _source_label(platform):
    return SOURCE_LABELS.get(platform, 'Company Website')


def _blocked_page_error(text):
    low = (text or '').lower()
    blocked_markers = (
        'access denied', 'humans only', 'verify you are human', 'captcha',
        'confirm you are human',
        'blocked automated access', 'enable javascript', 'internet explorer 11 is no longer supported',
        'please log in', 'sign in to view',
    )
    if any(marker in low for marker in blocked_markers):
        return 'Website blocked automated access to this posting.'
    return ''


def _greenhouse_api_result(url):
    if _detect_platform(url) != 'greenhouse':
        return None

    parsed = urlparse(url)
    parts = [unquote(part) for part in parsed.path.split('/') if part]
    query = parse_qs(parsed.query)
    board = parts[0] if parts else ''
    job_id = ''
    if 'jobs' in parts:
        index = parts.index('jobs')
        if index + 1 < len(parts):
            job_id = re.sub(r'\D', '', parts[index + 1])
    if not board and query.get('for'):
        board = query['for'][0]
    if not job_id and query.get('token'):
        job_id = re.sub(r'\D', '', query['token'][0])
    if not board or not job_id:
        return None

    endpoint = f'https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}?content=true'
    try:
        response = requests.get(endpoint, timeout=20, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code != 200:
            return None
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None

    data = _empty_result(url, 'greenhouse')
    company = _clean_company(payload.get('company_name') or _slug_to_name(board))
    company = re.sub(r'\s+Internships?$', '', company, flags=re.I).strip()
    location = _clean_location((payload.get('location') or {}).get('name', ''))
    content_text = _normalize_text(BeautifulSoup(payload.get('content') or '', 'html.parser').get_text(' ', strip=True))
    title = _clean_title(payload.get('title', ''), company)
    title = re.sub(
        r'\s*[-|]\s*(?:Fully\s+)?(?:Remote|Hybrid|Onsite|On-site)(?:\s*[-,]\s*(?:US|USA|United States))?$',
        '',
        title,
        flags=re.I,
    ).strip()

    data.update({
        'company': company,
        'job_title': title,
        'location': location,
        'work_type': _extract_work_type(' '.join([location, payload.get('title', ''), content_text])),
        'salary': _extract_salary(content_text),
        'source': 'Greenhouse',
    })
    return _public_result(data)


def _smartrecruiters_api_result(url):
    if _detect_platform(url) != 'smartrecruiters':
        return None

    parsed = urlparse(url)
    parts = [unquote(part) for part in parsed.path.split('/') if part]
    if len(parts) < 2:
        return None
    company_slug = parts[0]
    posting_id = re.sub(r'[^A-Za-z0-9-]', '', parts[1])
    if not company_slug or not posting_id:
        return None

    endpoint = f'https://api.smartrecruiters.com/v1/companies/{company_slug}/postings/{posting_id}'
    try:
        response = requests.get(endpoint, timeout=20, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code != 200:
            return None
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None

    data = _empty_result(url, 'smartrecruiters')
    company = _clean_company((payload.get('company') or {}).get('name') or company_slug)
    location_data = payload.get('location') or {}
    location = _clean_location(location_data.get('fullLocation') or ', '.join(
        part for part in (
            location_data.get('city'),
            location_data.get('region'),
            location_data.get('country'),
        ) if part
    ))
    sections = ((payload.get('jobAd') or {}).get('sections') or {})
    section_text = ' '.join(
        BeautifulSoup(str(section.get('text') or ''), 'html.parser').get_text(' ', strip=True)
        for section in sections.values()
        if isinstance(section, dict)
    )
    work_type = ''
    if location_data.get('hybrid'):
        work_type = 'Hybrid'
    elif location_data.get('remote'):
        work_type = 'Remote'
    else:
        work_type = _extract_work_type(section_text)

    data.update({
        'company': company,
        'job_title': _clean_title(payload.get('name', ''), company),
        'location': location,
        'work_type': work_type,
        'salary': _extract_contextual_salary(section_text) or _extract_salary(section_text),
        'source': 'SmartRecruiters',
    })
    return _public_result(data)


def _clean_value(value):
    value = _normalize_text(value)
    value = re.sub(r'^(job title|title|company|location|salary|compensation)\s*[:\-]\s*', '', value, flags=re.I)
    return value.strip(' |,-')


def _clean_company(value):
    value = _clean_value(value)
    if value.lower() in {'none', 'null', 'n/a', 'na', 'job', 'jobs', 'app', 'embed'}:
        return ''
    if not re.search(r'[A-Za-z0-9]', value) or value.strip() in {'©', '(c)'}:
        return ''
    value = re.sub(r'\s+\d+(?:\.\d+)?\s*(?:out of 5 stars?|stars?)?.*$', '', value, flags=re.I)
    value = re.sub(r'^©\s*\d{4}\s*', '', value).strip()
    value = re.sub(r',?\s+all rights reserved.*$', '', value, flags=re.I).strip()
    value = re.sub(r'\s+Careers$', '', value, flags=re.I).strip()
    if re.search(r'\b(?:MS\s+Smith\s+Barney|Morgan\s+Stanley)\b', value, flags=re.I):
        return 'Morgan Stanley'
    known = {
        'burberry': 'Burberry',
        'burberrycareers': 'Burberry',
        'fdmgroup': 'FDM Group',
        'fdm group': 'FDM Group',
        'le001 berkeley research group, llc': 'BRG',
        'berkeley research group, llc': 'BRG',
        'thinkbrg': 'BRG',
        'twosigma': 'Two Sigma',
        'two sigma': 'Two Sigma',
        'ms': 'Morgan Stanley',
        'morgan stanley': 'Morgan Stanley',
        'pnc': 'PNC',
        'alphasights': 'AlphaSights',
        'nyulangone': 'NYU Langone Health',
        'nyu langone': 'NYU Langone Health',
        'nyu langone health': 'NYU Langone Health',
    }
    return known.get(value.lower(), value)


def _state_abbrev(value):
    clean = _normalize_text(value).lower()
    if clean.upper() in US_STATE_ABBR_TO_NAME:
        return clean.upper()
    return US_STATE_NAME_TO_ABBR.get(clean, '')


def _state_name(value):
    clean = _normalize_text(value)
    abbr = _state_abbrev(clean)
    if abbr:
        return US_STATE_ABBR_TO_NAME.get(abbr, clean.title())
    return clean


def _remote_region_location(value):
    match = re.search(
        r'\bRemote\s*(?:[-,/]|\s+in\s+)?\s*(USA|US|United States|[A-Z]{2}|[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})\b',
        value,
    )
    if not match:
        return ''
    region = _clean_value(match.group(1))
    if region.lower() in {'usa', 'us', 'united states'}:
        return 'United States'
    abbr = _state_abbrev(region)
    return US_STATE_ABBR_TO_NAME.get(abbr, '') if abbr else ''


def _clean_location(value):
    value = _clean_value(value)
    if not value:
        return ''

    value = re.sub(r'^locations?\s*\([^)]*\)?\s*[:\-]?\s*', '', value, flags=re.I)
    value = re.sub(r'^locations?\s*[:\-]\s*', '', value, flags=re.I)
    value = re.sub(r'^(?:for|in|based\s+in|located\s+in)\s+', '', value, flags=re.I)
    value = re.sub(r'\bKorea,\s*Republic of\b', 'South Korea', value, flags=re.I)
    value = re.sub(r'\bNYC\b', 'New York, NY', value)
    value = re.sub(r'\s+', ' ', value).strip()

    remote_region = _remote_region_location(value)
    if remote_region:
        return remote_region

    city_full_state = re.search(
        r'\b([A-Z][A-Za-z.\'-]+(?:\s+[A-Z][A-Za-z.\'-]+){0,3}),\s*'
        r'([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})\s*(?:\((?:US-)?([A-Z]{2})\))?\s*,\s*(?:US|USA|United States)\b',
        value,
    )
    if city_full_state:
        state = city_full_state.group(3) or _state_abbrev(city_full_state.group(2))
        if state:
            return f"{city_full_state.group(1)}, {state}"

    blocked_exact = {
        'clear text', 'permanent', 'full', 'full time', 'full-time', 'contract',
        'temporary', 'apply', 'posted', 'save job',
    }
    low_value = value.lower()
    if low_value.startswith('remote'):
        return 'Remote'
    if low_value.startswith('hybrid'):
        return 'Hybrid'

    countries = (
        'South Korea', 'United Kingdom', 'United States', 'Canada', 'Mexico',
        'Australia', 'India', 'Japan', 'Singapore', 'Germany', 'France',
        'Ireland', 'Poland', 'Spain', 'Italy', 'Brazil', 'Netherlands',
    )
    country_pattern = '|'.join(re.escape(country) for country in countries)
    international = re.search(rf'([^|;\n]+?),\s*({country_pattern})\b', value, flags=re.I)
    if international:
        parts = [part.strip() for part in international.group(1).split(',') if part.strip()]
        country = next((name for name in countries if name.lower() == international.group(2).lower()), international.group(2))
        if parts:
            city = parts[0]
            region = parts[-1] if len(parts) > 1 else ''
            if region.lower() == city.lower():
                region = ''
            return ', '.join(part for part in (city, region, country) if part)
    city_state = re.search(rf'\b([A-Z][A-Za-z.\'-]+(?:\s+[A-Z][A-Za-z.\'-]+){{0,3}}),\s*({US_STATE})\b', value)
    if city_state:
        city = city_state.group(1).split()[-3:]
        return f"{' '.join(city)}, {city_state.group(2)}"
    city_state_no_comma = re.search(
        rf'\b([A-Z][A-Za-z.\'-]+(?:\s+[A-Z][A-Za-z.\'-]+){{0,2}})\s+({US_STATE})(?:\s+\d+)?\b',
        value,
    )
    if city_state_no_comma:
        city = city_state_no_comma.group(1).split()[-3:]
        return f"{' '.join(city)}, {city_state_no_comma.group(2)}"

    pieces = re.split(r'\s*(?:\||;|/|\n|•|·)\s*', value)
    clean = []
    for piece in pieces:
        piece = _clean_value(piece)
        if not piece or piece.lower() in blocked_exact:
            continue
        if piece.lower() in {'remote', 'hybrid', 'united states', 'usa', 'us', 'all locations'}:
            clean.append(piece)
            continue
        city_state = re.search(rf'\b([A-Z][A-Za-z.\'-]+(?:\s+[A-Z][A-Za-z.\'-]+){{0,3}}),\s*({US_STATE})\b', piece)
        if city_state:
            city = city_state.group(1).split()[-3:]
            clean.append(f"{' '.join(city)}, {city_state.group(2)}")
            continue
        city_full_state = re.search(
            r'\b([A-Z][A-Za-z.\'-]+(?:\s+[A-Z][A-Za-z.\'-]+){0,3}),\s*'
            r'([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})\s*(?:\((?:US-)?([A-Z]{2})\))?\s*,\s*(?:US|USA|United States)\b',
            piece,
        )
        if city_full_state:
            state = city_full_state.group(3) or _state_abbrev(city_full_state.group(2))
            if state:
                clean.append(f"{city_full_state.group(1)}, {state}")
                continue
        if re.search(r'\b[A-Z][a-z]+,\s*(?:United States|USA|Canada|UK)\b', piece):
            clean.append(piece)

    unique = []
    for item in clean:
        if item not in unique:
            unique.append(item)
    return ', '.join(unique[:2])


def _reasonable(field, value):
    if not value:
        return False
    value = _clean_value(value)
    if field in ('job_title', 'company', 'location') and len(value) > 140:
        return False
    if field == 'job_title':
        blocked = ['sign in', 'apply now', 'search jobs', 'job details', 'careers', 'privacy', 'current openings']
        low = value.lower()
        return not any(term in low for term in blocked) and low != 'jobs' and not low.endswith(' jobs')
    if field == 'company':
        low = value.lower()
        blocked_exact = {'careers', 'jobs', 'job search', 'apply', 'privacy', 'cookies'}
        blocked_phrases = {
            'select how often', 'benefit programs', 'company reserves',
            'this position', 'base salary',
        }
        if low in blocked_exact or any(term in low for term in blocked_phrases):
            return False
        return _clean_company(value).lower() not in {'careers', 'jobs', 'job search', 'apply'}
    if field == 'location':
        return bool(_clean_location(value))
    if field == 'salary':
        return bool(SALARY_RE.search(value)) or '$' in value
    return True


def _first_text(soup, selectors, field=''):
    for selector in selectors:
        for elem in soup.select(selector):
            if elem.name == 'img' and elem.get('alt'):
                text = elem.get('alt')
            else:
                text = elem.get_text(separator=' ', strip=True)
            text = _clean_value(text)
            if field == 'company':
                text = _clean_company(text)
            elif field == 'location':
                text = _clean_location(text)
            if _reasonable(field, text):
                return text
    return ''


def _best_description(soup):
    for selector in FIELD_SELECTORS['description']:
        elem = soup.select_one(selector)
        if elem:
            text = _normalize_text(elem.get_text(separator=' ', strip=True))
            if len(text) > 120:
                return text
    text = _normalize_text(soup.get_text(separator=' ', strip=True))
    return text[:4000] if len(text) > 120 else ''


def _linkedin_description_text(soup):
    for selector in (
        '.show-more-less-html__markup',
        '.description__text',
        '[class*="job-description" i]',
        '[data-testid="job-description"]',
    ):
        elem = soup.select_one(selector)
        if elem:
            text = _normalize_text(elem.get_text(separator=' ', strip=True))
            if len(text) > 80:
                return text
    return ''


def _find_json_candidates(soup):
    candidates = []
    jsonld = _parse_jsonld(soup)
    if jsonld:
        candidates.append(_extract_jsonld_job_fields(jsonld))
    next_data = _parse_next_data(soup)
    if next_data:
        flat = _flatten_dict_strings(next_data)
        candidates.append({
            'job_title': _pick_flat(flat, ['title', 'jobtitle', 'job_title', 'name']),
            'company': _pick_flat(flat, ['company', 'companyname', 'organization', 'department']),
            'location': _pick_flat(flat, ['location', 'joblocation', 'city']),
            'salary': _pick_flat(flat, ['salary', 'compensation', 'pay']),
            'description': _pick_flat(flat, ['description', 'jobdescription']),
        })
    return candidates


def _pick_flat(flat, keys):
    for key in keys:
        values = flat.get(key, [])
        for value in values:
            if value and 2 <= len(value) <= 5000:
                return value
    for key, values in flat.items():
        if any(token in key for token in keys):
            for value in values:
                if value and 2 <= len(value) <= 5000:
                    return value
    return ''


def _extract_salary(text):
    match = SALARY_RE.search(text or '')
    return _clean_value(match.group(0)) if match else ''


def _extract_contextual_salary(text):
    text = text or ''
    salary_terms = (
        'salary', 'pay', 'compensation', 'base pay', 'hourly', 'wage',
        'rate', 'range', 'per hour', '/hr', '/yr', 'per year',
    )
    blocked_terms = ('asset', 'assets', 'revenue', 'budget', 'funding')
    for match in SALARY_RE.finditer(text):
        start, end = match.span()
        context = text[max(0, start - 120):min(len(text), end + 160)].lower()
        if any(term in context for term in salary_terms) and not any(term in context for term in blocked_terms):
            return _clean_value(match.group(0))
    return ''


def _extract_location(text):
    clean = []
    for match in LOCATION_RE.finditer(text or ''):
        loc = _clean_location(match.group(0))
        if loc and loc not in clean:
            clean.append(loc)
    return ', '.join(clean[:2])


def _extract_location_from_url(url):
    tokens = re.split(r'[-/_]+', unquote(urlparse(url).path).lower())
    tokens = [token for token in tokens if token]
    boroughs = {
        'queens': 'Queens, NY',
        'brooklyn': 'Brooklyn, NY',
        'manhattan': 'New York, NY',
        'bronx': 'Bronx, NY',
    }
    for token, location in boroughs.items():
        if token in tokens:
            return location
    if 'staten' in tokens and 'island' in tokens:
        return 'Staten Island, NY'
    known_cities = {
        'baltimore': 'Baltimore, MD',
    }
    for token, location in known_cities.items():
        if token in tokens:
            return location

    states = set(US_STATE.strip('(?:)').lower().split('|'))
    state_index = next((i for i, token in enumerate(tokens) if token in states), None)
    if state_index is not None and state_index > 0:
        before_state = [token for token in tokens[:state_index] if token and token not in {'job', 'jobs', 'career', 'careers'}]
        if before_state:
            multi_word_cities = [
                ('new', 'york'), ('san', 'francisco'), ('san', 'jose'), ('los', 'angeles'),
                ('jersey', 'city'), ('long', 'island', 'city'), ('new', 'brunswick'),
                ('white', 'plains'), ('salt', 'lake', 'city'),
            ]
            city_words = before_state[-1:]
            for city in multi_word_cities:
                if tuple(before_state[-len(city):]) == city:
                    city_words = list(city)
                    break

            return f"{' '.join(word.title() for word in city_words)}, {tokens[state_index].upper()}"

    full_state_location = _extract_full_state_location_from_tokens(tokens)
    if full_state_location:
        return full_state_location

    remote_location = _extract_remote_location_from_tokens(tokens)
    if remote_location:
        return remote_location

    return ''


def _state_match_ending_at(tokens, end_index):
    for size in (3, 2, 1):
        start = end_index - size
        if start < 0:
            continue
        name = ' '.join(tokens[start:end_index])
        abbr = US_STATE_NAME_TO_ABBR.get(name)
        if abbr:
            return start, end_index, abbr
    return None


def _city_words_before(tokens, end_index):
    blocked = {
        'job', 'jobs', 'career', 'careers', 'jobdetail', 'detail', 'open',
        'role', 'roles', 'remote',
    }
    before = [token for token in tokens[:end_index] if token and token not in blocked and not token.isdigit()]
    if not before:
        return []
    multi_word_cities = [
        ('new', 'york'), ('san', 'francisco'), ('san', 'jose'), ('los', 'angeles'),
        ('jersey', 'city'), ('long', 'island', 'city'), ('new', 'brunswick'),
        ('white', 'plains'), ('salt', 'lake', 'city'), ('garden', 'city'),
    ]
    for city in multi_word_cities:
        if tuple(before[-len(city):]) == city:
            return list(city)
    return before[-1:]


def _extract_full_state_location_from_tokens(tokens):
    for index in range(len(tokens) - 1):
        if tokens[index:index + 2] != ['united', 'states']:
            continue
        state_match = _state_match_ending_at(tokens, index)
        if not state_match:
            continue
        state_start, _, abbr = state_match
        city_words = _city_words_before(tokens, state_start)
        if city_words:
            return f"{' '.join(word.title() for word in city_words)}, {abbr}"
        return US_STATE_ABBR_TO_NAME.get(abbr, abbr)
    return ''


def _extract_remote_location_from_tokens(tokens):
    if 'remote' not in tokens:
        return ''
    index = tokens.index('remote') + 1
    for end in range(min(len(tokens), index + 3), index, -1):
        name = ' '.join(tokens[index:end])
        abbr = US_STATE_NAME_TO_ABBR.get(name)
        if abbr:
            return US_STATE_ABBR_TO_NAME.get(abbr, name.title())
    if index < len(tokens) and tokens[index] in {'usa', 'us'}:
        return 'United States'
    return ''


def _clean_taleo_location(value):
    value = _clean_value(value)
    match = re.search(r'\b(?:Primary\s+)?Location\s*:\s*([A-Za-z]+)-([A-Za-z]+(?:\s+[A-Za-z]+)*)-([A-Za-z]+(?:\s+[A-Za-z]+)*)\b', value, flags=re.I)
    if not match:
        match = re.search(r'\b(United States|USA|US)-([A-Za-z]+(?:\s+[A-Za-z]+)*)-([A-Za-z]+(?:\s+[A-Za-z]+)*)\b', value, flags=re.I)
    if not match:
        return ''
    state = _state_abbrev(match.group(2))
    city = _normalize_text(match.group(3)).title()
    if state and city:
        return f"{city}, {state}"
    return ''


def _extract_taleo_location(text):
    text = text or ''
    patterns = [
        r'Primary\s+Location\s*:\s*[^:]+?(?=\s+(?:Industry|Schedule|Employee Status|BusinessClass|Job Posting)\s*:|$)',
        r'\bUnited States-[A-Za-z]+(?:\s+[A-Za-z]+)*-[A-Za-z]+(?:\s+[A-Za-z]+)*\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            location = _clean_taleo_location(match.group(0))
            if location:
                return location
    return ''


def _visible_workday_location(soup):
    for selector in ('[data-automation-id="locations"]', '[data-automation-id="jobPostingLocation"]'):
        for elem in soup.select(selector):
            location = _clean_location(elem.get_text(' ', strip=True))
            if location:
                return location
    return ''


def _location_looks_internal(value):
    text = _clean_value(value)
    return bool(re.search(r'\b[A-Z]{2,}\d*\s*[-_][A-Za-z]', text)) or text.lower().startswith('locations ')

def _extract_work_type(text):
    low = (text or '').lower()
    has_remote = any(term in low for term in (
        'remote', 'work from home', 'work-from-home', 'telework', 'telecommute',
        'virtual position', 'virtual role',
    ))
    has_hybrid = any(term in low for term in (
        'hybrid', 'flexible workplace', 'flexible work arrangement',
    ))
    has_onsite = any(term in low for term in (
        'on-site', 'onsite', 'in-office', 'in office', 'in person', 'on site',
        'office-based', 'office based',
    ))
    if has_hybrid:
        return 'Hybrid'
    if has_remote and has_onsite:
        return ''
    if has_remote:
        return 'Remote'
    if has_onsite:
        return 'Onsite'
    return ''


def _extract_linkedin_work_type(soup, location=''):
    description = _linkedin_description_text(soup)
    top_text = _normalize_text(' '.join(
        elem.get_text(' ', strip=True)
        for elem in soup.select('.top-card-layout__second-subline, .topcard__flavor-row, .topcard__flavor--bullet')
    ))
    source = ' '.join([top_text, description])
    low = source.lower()

    if re.search(r'\bhybrid\b', low):
        return 'Hybrid'
    if re.search(
        r'\b(?:fully\s+remote|remote\s+(?:role|position|job|opportunity)|work\s+remotely|work\s+from\s+home|telecommute)\b',
        low,
    ):
        return 'Remote'
    if re.search(
        r'\b(?:on[-\s]?site\s+(?:role|position|job)|in[-\s]?office|office[-\s]?based|based\s+out\s+of|based\s+in)\b',
        low,
    ):
        return 'Onsite'
    return ''


def _extract_linkedin_salary(soup):
    description_salary = _extract_contextual_salary(_linkedin_description_text(soup))
    if description_salary:
        return description_salary
    for selector in FIELD_SELECTORS['salary']:
        for elem in soup.select(selector):
            salary = _extract_contextual_salary(elem.get_text(' ', strip=True))
            if salary:
                return salary
    return ''


def _normalize_work_type(value):
    low = _clean_value(value).lower()
    if not low:
        return ''
    if 'hybrid' in low:
        return 'Hybrid'
    if 'remote' in low or 'telecommute' in low:
        return 'Remote'
    if any(term in low for term in ('on-site', 'onsite', 'on site', 'in-office', 'in office', 'in person')):
        return 'Onsite'
    return ''


def _infer_company_from_url(url, platform):
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace('www.', '')
    path_parts = [unquote(part) for part in parsed.path.split('/') if part]
    query = parse_qs(parsed.query)

    if 'talents.vaia.com' in host and len(path_parts) >= 2 and path_parts[0] == 'companies':
        return _slug_to_name(path_parts[1])
    if platform == 'greenhouse':
        if 'for' in query and query['for']:
            return _slug_to_name(query['for'][0])
        if 'boards.greenhouse.io' in host and path_parts:
            return _slug_to_name(path_parts[0])
    if platform == 'lever' and path_parts:
        return _slug_to_name(path_parts[0])
    if platform == 'ashby' and path_parts:
        return _slug_to_name(path_parts[0])
    if platform == 'workday':
        host_part = host.split('.')[0]
        return _slug_to_name(host_part.replace('wd1-', '').replace('wd3-', '').replace('wd5-', ''))

    blocked = {'jobs', 'careers', 'boards', 'apply', 'job-boards', 'job'}
    parts = host.split('.')
    company_host = parts[0]
    if company_host in blocked and len(parts) > 2:
        company_host = parts[-3] if parts[-2] in {'co', 'com'} and len(parts) > 3 else parts[-2]
    if company_host not in blocked and not any(domain in host for domains in JOB_BOARDS.values() for domain in domains):
        return _slug_to_name(company_host)
    return ''


def _slug_to_name(slug):
    slug = re.sub(r'(?i)(careers|jobs|inc|llc)$', '', slug)
    slug = re.sub(r'[_\-]+', ' ', slug).strip()
    return _clean_company(_normalize_text(slug.title()))


def _extract_company_from_text(text, platform=''):
    if not text:
        return ''
    patterns = [
        r'Direct message the job poster from\s+(.+?)(?=\s+[A-Z][a-z]+\s+[A-Z][a-z]+|\s+View|\s+Follow|\s+About|\s+Apply|$)',
        r'(?:Company|Employer)\s*[:\-]\s*(.+?)(?=\s+(?:Location|Job|Salary|Apply)|$)',
        r'Apply for this job at\s+(.+?)(?=\s|$)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            company = _clean_company(match.group(1))
            if _reasonable('company', company):
                return company
    return ''


def _clean_title(title, company=''):
    title = _clean_linkedin_title(_clean_value(title))
    title = re.sub(r'\s*[-|]\s*(Careers|Jobs|LinkedIn|Indeed).*$','', title, flags=re.I)
    if company:
        title = re.sub(rf'\s*[-|]\s*{re.escape(company)}.*$', '', title, flags=re.I)
    return title.strip()


def _merge(data, candidate):
    for key, value in candidate.items():
        if key not in data or key == 'source':
            continue
        if not data.get(key) and _reasonable(key, str(value)):
            data[key] = _clean_value(str(value))


def _extract_from_soup(soup, url, original_url=None):
    original_url = original_url or url
    platform = _detect_platform(original_url, soup)
    data = _empty_result(original_url, platform)

    for candidate in _find_json_candidates(soup):
        _merge(data, candidate)

    for tag in soup(['script', 'style', 'noscript', 'svg']):
        tag.decompose()

    ats = ATS_HINTS.get(platform, {})
    selector_map = {
        'job_title': ats.get('title', []) + FIELD_SELECTORS['job_title'],
        'company': ats.get('company', []) + FIELD_SELECTORS['company'],
        'location': ats.get('location', []) + FIELD_SELECTORS['location'],
        'salary': FIELD_SELECTORS['salary'],
        'description': ats.get('description', []) + FIELD_SELECTORS['description'],
    }

    for field in ('job_title', 'company', 'location', 'salary'):
        if not data[field]:
            data[field] = _first_text(soup, selector_map[field], field)

    if not data['description']:
        data['description'] = _best_description(soup)

    meta_title = _get_meta_content(soup, 'property', ['og:title', 'twitter:title']) or _get_meta_content(soup, 'name', ['title'])
    meta_site = _get_meta_content(soup, 'property', ['og:site_name'])
    meta_description = _get_meta_content(soup, 'property', ['og:description', 'twitter:description'])
    if not data['job_title'] and meta_title:
        data['job_title'] = meta_title
    if not data['company'] and platform == 'company_website' and meta_site and _reasonable('company', meta_site):
        data['company'] = meta_site
    if not data['description'] and meta_description:
        data['description'] = meta_description

    full_text = _normalize_text(soup.get_text(separator=' ', strip=True))
    blocked_error = _blocked_page_error(' '.join([meta_title or '', full_text[:3000]]))
    if blocked_error:
        data['error'] = blocked_error
    if not data['salary']:
        data['salary'] = _extract_salary(full_text)
    url_location = _extract_location_from_url(original_url)
    taleo_location = _extract_taleo_location(full_text) if 'taleo.net' in urlparse(original_url).netloc.lower() else ''
    if platform == 'workday':
        visible_location = _visible_workday_location(soup)
        if visible_location and (not data['location'] or _location_looks_internal(data['location'])):
            data['location'] = visible_location
    if taleo_location:
        data['location'] = taleo_location
    elif not data['location']:
        data['location'] = url_location or _extract_location(full_text)
    elif url_location and str(data['location']).strip().lower() in {'remote', 'hybrid', 'onsite', 'on-site'}:
        data['location'] = url_location
    if platform == 'linkedin':
        data['salary'] = _extract_linkedin_salary(soup)
        page_work_type = _extract_linkedin_work_type(soup, data.get('location', ''))
    else:
        data['salary'] = _extract_salary(data.get('salary', ''))
        work_type_source = ' '.join([data.get('location', ''), data.get('description', ''), full_text])
        page_work_type = _extract_work_type(work_type_source)
    if page_work_type and not _normalize_work_type(data.get('work_type', '')):
        data['work_type'] = page_work_type
    if not data['company']:
        data['company'] = _extract_company_from_text(full_text, platform)
    if not data['company']:
        data['company'] = _infer_company_from_url(url, platform)
    data['company'] = _clean_company(data['company'])
    if not data['company']:
        data['company'] = _clean_company(_infer_company_from_url(original_url, platform))
    host = urlparse(original_url).netloc.lower().replace('www.', '')
    for domain, company in COMPANY_HOST_OVERRIDES.items():
        if host == domain or host.endswith('.' + domain):
            data['company'] = company
            break
    data['location'] = _clean_location(data['location'])
    data['work_type'] = _normalize_work_type(data['work_type'])
    data['source'] = _source_label(platform)

    data['job_title'] = _clean_title(data['job_title'], data['company'])
    if data['job_title'] and (not data['company'] or data['company'].lower() in {'ai', 'aijobs'}):
        title_company = re.search(r'^(.+?)\s+at\s+([^|,-]{2,80})$', data['job_title'], flags=re.I)
        if title_company:
            data['job_title'] = _clean_title(title_company.group(1))
            data['company'] = _clean_company(title_company.group(2))
    if not data['job_title']:
        heading = _first_text(soup, ['main h1', 'article h1', 'h1', 'h2'], 'job_title')
        data['job_title'] = _clean_title(heading, data['company'])

    return data


def _public_result(data):
    public_keys = [
        'date_applied', 'company', 'job_title', 'job_link', 'status',
        'location', 'work_type', 'salary', 'follow_up', 'source', 'error',
    ]
    defaults = {
        'company': 'n/a',
        'job_title': 'n/a',
        'location': 'n/a',
        'work_type': 'n/a',
        'salary': 'n/a',
        'source': 'Company Website',
    }
    result = {}
    for key in public_keys:
        value = data.get(key, '')
        if key in defaults and not value:
            value = defaults[key]
        if value:
            result[key] = value
    return result


async def _open_job_page(page, url, timeout):
    response = await page.goto(url, wait_until='domcontentloaded', timeout=timeout)
    status = response.status if response else None
    await page.wait_for_timeout(2500)

    iframe_src = await page.evaluate(
        """() => {
            const frame = document.querySelector('iframe#grnhse_iframe, iframe[src*="greenhouse"], iframe[src*="lever"], iframe[src*="ashby"]');
            return frame ? frame.src : '';
        }"""
    )
    if iframe_src:
        response = await page.goto(iframe_src, wait_until='domcontentloaded', timeout=timeout)
        status = response.status if response else status
        await page.wait_for_timeout(2000)

    for selector in ['[data-qa="job-title"]', '[data-testid="job-title"]', '#jobDescriptionText', 'main', 'h1']:
        try:
            await page.wait_for_selector(selector, timeout=2500)
            break
        except Exception:
            continue

    await _expand_job_details(page)
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(1000)
    await _expand_job_details(page)
    await page.evaluate("window.scrollTo(0, 0)")
    await page.wait_for_timeout(500)
    return status


async def _expand_job_details(page):
    try:
        clicked = await page.evaluate(
            """() => {
                const labels = [
                    /show\\s+more/i, /read\\s+more/i, /see\\s+more/i, /view\\s+more/i,
                    /more\\s+details/i, /full\\s+description/i, /job\\s+description/i,
                    /show\\s+full/i, /expand/i
                ];
                const blocked = /apply|save|share|sign\\s*in|log\\s*in|subscribe|alert|cookie|privacy/i;
                const candidates = Array.from(document.querySelectorAll(
                    'button, a, summary, [role="button"], [aria-expanded="false"]'
                ));
                let count = 0;
                for (const elem of candidates) {
                    const style = window.getComputedStyle(elem);
                    const rect = elem.getBoundingClientRect();
                    if (style.visibility === 'hidden' || style.display === 'none' || rect.width === 0 || rect.height === 0) {
                        continue;
                    }
                    const text = (elem.innerText || elem.textContent || elem.getAttribute('aria-label') || '').trim();
                    if (!text || text.length > 120 || blocked.test(text)) {
                        continue;
                    }
                    if (labels.some(pattern => pattern.test(text))) {
                        elem.click();
                        count += 1;
                        if (count >= 8) break;
                    }
                }
                for (const detail of document.querySelectorAll('details:not([open])')) {
                    detail.open = true;
                    count += 1;
                }
                return count;
            }"""
        )
        if clicked:
            await page.wait_for_timeout(1200)
    except Exception:
        pass


def _unavailable_redirect(original_url, final_url):
    original = urlparse(original_url)
    final = urlparse(final_url)
    platform = _detect_platform(original_url)
    original_parts = [part for part in original.path.split('/') if part]
    final_parts = [part for part in final.path.split('/') if part]

    if platform == 'lever' and len(original_parts) >= 2 and len(final_parts) <= 1:
        return True
    if platform == 'greenhouse' and '/jobs/' in original.path and '/jobs/' not in final.path:
        return True
    if '/job/' in original.path and final.path.rstrip('/').lower().endswith('/careers'):
        return True
    return 'error=true' in final.query.lower()


async def scrape_job_with_browser(url, timeout=60000):
    greenhouse_result = _greenhouse_api_result(url)
    if greenhouse_result:
        return greenhouse_result
    smartrecruiters_result = _smartrecruiters_api_result(url)
    if smartrecruiters_result:
        return smartrecruiters_result

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
            ),
            viewport={'width': 1366, 'height': 900},
        )
        page = await context.new_page()
        try:
            status = await _open_job_page(page, url, timeout)
            if status in (404, 410):
                data = _empty_result(url, _detect_platform(url))
                data['error'] = f'Job page is unavailable (HTTP {status})'
                return _public_result(data)
            if _unavailable_redirect(url, page.url or url):
                data = _empty_result(url, _detect_platform(url))
                data['error'] = 'Job page redirected to a general careers page and is likely unavailable.'
                return _public_result(data)
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            return _public_result(_extract_from_soup(soup, page.url or url, url))
        except Exception as exc:
            data = _empty_result(url, _detect_platform(url))
            data['error'] = str(exc)
            return _public_result(data)
        finally:
            await context.close()
            await browser.close()


def parse_job_with_browser(url):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(scrape_job_with_browser(url))
