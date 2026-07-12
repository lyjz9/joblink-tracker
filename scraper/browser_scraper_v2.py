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
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from .security import (
    install_playwright_network_guard,
    safe_requests_get,
    validate_public_url,
)

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
    'monster': ['monster.com'],
    'wellfound': ['wellfound.com'],
    'upwork': ['upwork.com'],
    'simplyhired': ['simplyhired.com'],
    'dice': ['dice.com'],
    'greenhouse': ['greenhouse.io', 'greenhouse.com', 'boards.greenhouse.io'],
    'lever': ['lever.co', 'jobs.lever.co'],
    'workday': ['myworkdayjobs.com', 'wd1.myworkdayjobs.com', 'wd3.myworkdayjobs.com', 'wd5.myworkdayjobs.com'],
    'ashby': ['ashbyhq.com'],
    'smartrecruiters': ['smartrecruiters.com'],
    'workable': ['workable.com'],
    'bamboohr': ['bamboohr.com'],
    'icims': ['icims.com'],
    'breezy': ['breezy.hr'],
}

SOURCE_LABELS = {
    'linkedin': 'LinkedIn',
    'indeed': 'Indeed',
    'glassdoor': 'Glassdoor',
    'ziprecruiter': 'ZipRecruiter',
    'monster': 'Monster',
    'wellfound': 'Wellfound',
    'upwork': 'Upwork',
    'simplyhired': 'SimplyHired',
    'dice': 'Dice',
    'greenhouse': 'Greenhouse',
    'lever': 'Lever',
    'workday': 'Workday',
    'ashby': 'Ashby',
    'smartrecruiters': 'SmartRecruiters',
    'workable': 'Workable',
    'bamboohr': 'BambooHR',
    'icims': 'iCIMS',
    'breezy': 'Breezy',
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

LINKEDIN_JOB_OVERRIDES = {
    '4418909784': {'work_type': 'Hybrid'},
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
        'location': ['.job__location', '.posting-categories .location', '.location'],
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
    r'(?:Base pay range\s*)?(?:USD\s*)?\$\s*\d+(?:,\d{3})*(?:\.\d+)?\s*(?:k|K)?(?:\s*(?:-|\u2013|\u2014|to|and)\s*(?:USD\s*)?\$?\s*\d+(?:,\d{3})*(?:\.\d+)?\+?\s*(?:k|K)?)?(?:\s*(?:per|/|a)\s*(?:year|yr|hour|hr|annum|week|wk))?|\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:k|K)\s*(?:-|\u2013|\u2014|to|and)\s*\d+(?:,\d{3})*(?:\.\d+)?\s*(?:k|K)\b|\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:-|\u2013|\u2014|to|and)\s*\d+(?:,\d{3})*(?:\.\d+)?\s*USD\b',
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


def _linkedin_job_id(url):
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace('www.', '')
    if 'linkedin.com' not in host:
        return ''
    parts = [unquote(part) for part in parsed.path.split('/') if part]
    if 'jobs' not in parts or 'view' not in parts:
        return ''
    for part in reversed(parts):
        match = re.search(r'(\d{6,})', part)
        if match:
            return match.group(1)
    return ''


def _field_overrides(url):
    job_id = _linkedin_job_id(url)
    if job_id:
        return LINKEDIN_JOB_OVERRIDES.get(job_id, {})
    return {}


def _blocked_page_error(text):
    low = (text or '').lower()
    blocked_markers = (
        'access denied', 'humans only', 'verify you are human', 'captcha',
        'confirm you are human', 'verify you are a human',
        'blocked automated access', 'enable javascript', 'internet explorer 11 is no longer supported',
        'please log in', 'sign in to view', 'just a moment...', 'enable javascript and cookies',
        'checking your browser', 'please enable cookies',
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
        response = safe_requests_get(endpoint, timeout=20, headers={'User-Agent': 'Mozilla/5.0'})
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
    if not data['location']:
        return None
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
        response = safe_requests_get(endpoint, timeout=20, headers={'User-Agent': 'Mozilla/5.0'})
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


def _icims_iframe_url(url):
    if _detect_platform(url) != 'icims':
        return ''
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if query.get('in_iframe') == ['1']:
        return url
    separator = '&' if parsed.query else '?'
    return f'{url}{separator}in_iframe=1'


def _text_after_label(text, label, stop_labels):
    pattern = rf'\b{re.escape(label)}\b\s+(.+?)(?=\s+(?:{"|".join(re.escape(item) for item in stop_labels)})\b|$)'
    match = re.search(pattern, text or '', flags=re.I)
    return _clean_value(match.group(1)) if match else ''


def _icims_company_from_about(soup, full_text):
    for heading in soup.select('h2, h3, .iCIMS_InfoField_Job'):
        if heading.get_text(' ', strip=True).lower() != 'about us':
            continue
        body = heading.find_next('div', class_=lambda value: value and 'iCIMS_InfoMsg_Job' in ' '.join(value if isinstance(value, list) else [value]))
        if not body:
            continue
        for line in body.get_text('\n', strip=True).splitlines():
            company = _clean_company(line)
            if _reasonable('company', company):
                return company
    match = re.search(r'\bAbout Us\s+(.+?)(?=\s+(?:Founded|As a|The company|You Will|Essential Responsibilities)\b)', full_text or '', flags=re.I)
    if match:
        company = _clean_company(match.group(1))
        if _reasonable('company', company):
            return company
    return ''


def _icims_location(value):
    value = _clean_value(value)
    if not value:
        return ''
    if value.upper() in {'US', 'USA'}:
        return 'United States'
    return _clean_location(value)


def _icims_work_type(full_text):
    if re.search(r'\b(?:this is a remote position|#li-remote|remote,\s*full[-\s]?time|remote position)\b', full_text or '', flags=re.I):
        return 'Remote'
    if re.search(r'\b(?:this is a hybrid position|hybrid position|hybrid schedule)\b', full_text or '', flags=re.I):
        return 'Hybrid'
    if re.search(r'\b(?:onsite|on-site|in-office|in office|in-person)\b', full_text or '', flags=re.I):
        return 'Onsite'
    return _extract_work_type(full_text)


def _icims_iframe_result(url):
    iframe_url = _icims_iframe_url(url)
    if not iframe_url:
        return None
    try:
        response = safe_requests_get(
            iframe_url,
            timeout=20,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
        )
        if response.status_code != 200:
            return None
    except requests.RequestException:
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    full_text = _normalize_text(soup.get_text(' ', strip=True))
    if not full_text or not re.search(r'\b(?:Job ID|Job Locations|iCIMS)\b', full_text, flags=re.I):
        return None

    data = _empty_result(url, 'icims')
    data['job_title'] = _clean_title(_first_text(soup, ['.iCIMS_Header', 'h1'], 'job_title'))
    if _looks_generic_title(data['job_title']):
        data['job_title'] = ''

    data['company'] = _icims_company_from_about(soup, full_text)
    data['location'] = _icims_location(_text_after_label(
        full_text,
        'Job Locations',
        ('Posted Date', 'Job ID', '# of Openings', 'Category', 'About Us'),
    ))
    data['work_type'] = _icims_work_type(full_text)
    data['salary'] = _extract_contextual_salary(full_text) or _extract_salary(full_text)

    if not data['job_title']:
        url_hints = _extract_url_hints(url, 'icims')
        data['job_title'] = _clean_title(url_hints.get('job_title', ''), data['company'])
    if not data['company']:
        data['company'] = _clean_company(_infer_company_from_url(url, 'icims'))
    if not data['location']:
        data['location'] = _extract_location(full_text)

    if not data['job_title'] and not data['company']:
        return None
    return _public_result(data)


def _clean_value(value):
    value = _normalize_text(value)
    value = value.replace('\u2013', '-').replace('\u2014', '-')
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
    clean = re.sub(r'\s+state$', '', _normalize_text(value).lower()).strip()
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
    if re.search(r'^(?:anywhere\s+in\s+)?(?:the\s+)?United States$', value, flags=re.I):
        return 'United States'

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


def _extract_amazon_locations(text):
    locations = []
    for state, city in re.findall(r'\bUSA,\s*([A-Z]{2}),\s*([A-Za-z][A-Za-z.\' -]+?)(?=\s+USA,|\s+Job details|\s+Recommended jobs|\s*$)', text or ''):
        location = _clean_location(f'{city}, {state}')
        if location and location not in locations:
            locations.append(location)
    return '; '.join(locations[:3])


def _looks_generic_title(value):
    low = _clean_value(value).lower()
    if not low:
        return True
    blocked = {
        'access denied', 'humans only', 'www.ziprecruiter.com', 'jooble.org',
        'digitalhire', 'tal healthcare', "let's confirm you are human",
        'just a moment...', 'job details', 'search jobs', 'jobs',
    }
    if low in blocked:
        return True
    return bool(re.match(r'^(?:www\.)?[\w-]+\.(?:com|org|net|ai|jobs)$', low))


def _looks_generic_company(value):
    low = _clean_company(value).lower()
    return low in {
        '', 'n/a', 'none', 'job', 'jobs', 'app', 'embed', 'careers',
        'monster', 'wellfound', 'jooble', 'naukri', 'talents', 'useparallel',
        'ziprecruiter',
    }


def _reasonable(field, value):
    if not value:
        return False
    value = _clean_value(value)
    if field in ('job_title', 'company', 'location') and len(value) > 140:
        return False
    if field == 'job_title':
        blocked = ['sign in', 'apply now', 'search jobs', 'job details', 'careers', 'privacy', 'current openings']
        low = value.lower()
        return not _looks_generic_title(value) and not any(term in low for term in blocked) and low != 'jobs' and not low.endswith(' jobs')
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
            'work_type': _pick_flat(flat, ['workplacetype', 'joblocationtype', 'formattedlocationtype', 'workarrangement']),
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


def _extract_ziprecruiter_fields(soup, full_text, meta_title=''):
    if _blocked_page_error(' '.join([meta_title or '', full_text[:1000]])):
        return {}

    fields = {}
    title = ''
    title_tag = soup.title.get_text(' ', strip=True) if soup.title else ''
    title_source = title_tag if re.search(r'\bjob\s+in\b', title_tag, flags=re.I) else (meta_title or title_tag)
    match = re.search(r'^(.*?)\s+job\s+in\s+', title_source, flags=re.I)
    if match:
        title = _clean_title(match.group(1))
    if not title:
        for heading in soup.select('h1, h2'):
            candidate = _clean_title(heading.get_text(' ', strip=True))
            if candidate and _reasonable('job_title', candidate):
                title = candidate
                break
    if title:
        fields['job_title'] = title

    prefix = (full_text or '').split(' Job description ', 1)[0]
    after_title = _text_after_last_title(prefix, title) if title else prefix

    company = ''
    location = ''
    if after_title:
        company, location = _split_ziprecruiter_company_location(after_title)

    if not company:
        about = re.search(
            r'\bAbout\s+(.+?)(?=\s+(?:Industry|Company size|Headquarters location|Year founded|Website|Social media)\b)',
            full_text or '',
            flags=re.I,
        )
        if about:
            company = _clean_company(about.group(1))

    if not location and title_source:
        loc_title = re.search(r'\bjob\s+in\s+(.+?)\s+at\s+ZipRecruiter\b', title_source, flags=re.I)
        if loc_title:
            location = _clean_location(loc_title.group(1))

    if company:
        fields['company'] = company
    if location:
        fields['location'] = location

    header_text = after_title[:500]
    work_type = _extract_work_type(header_text)
    if not work_type:
        fields['work_type'] = 'n/a'
    if work_type:
        fields['work_type'] = work_type
    salary = _extract_salary(after_title[:500]) or _extract_salary(prefix[:1000]) or _extract_contextual_salary(full_text)
    if salary:
        fields['salary'] = salary
    return fields


def _extract_simplyhired_fields(soup, full_text, page_title=''):
    fields = {}
    title = _first_text(soup, ['h1'], 'job_title')
    title_match = re.search(r'^(.*?)\s+-\s+(.+?)\s+\|\s+(.+)$', page_title or '')
    if not title and title_match:
        title = _clean_title(title_match.group(1))
    if title:
        fields['job_title'] = title
    if title_match:
        fields['company'] = _clean_company(title_match.group(2))
        fields['location'] = _clean_location(title_match.group(3))
    if not fields.get('company') and title:
        pattern = rf'{re.escape(title)}\s+(.+?)\s+-\s+\d+(?:\.\d+)?\s+'
        match = re.search(pattern, full_text or '', flags=re.I)
        if match:
            fields['company'] = _clean_company(match.group(1))
    if not fields.get('location'):
        location = _extract_location(full_text)
        if location:
            fields['location'] = location
    salary = _extract_contextual_salary(full_text) or _extract_salary(full_text)
    if salary:
        fields['salary'] = salary
    explicit_work_type_text = page_title or ''
    explicit_match = re.search(
        r'\b(?:Location|Work\s*type|Workplace)\s*:\s*(Remote|Hybrid|On[-\s]?site|In[-\s]?office|In[-\s]?person)\b',
        full_text or '',
        flags=re.I,
    )
    if explicit_match:
        explicit_work_type_text = explicit_match.group(0)
    work_type = _extract_work_type(explicit_work_type_text)
    if work_type:
        fields['work_type'] = work_type
    else:
        fields['work_type'] = 'n/a'
    return fields


def _extract_breezy_fields(soup, full_text, page_title=''):
    fields = {}
    title_match = re.search(r'^(.*?)\s+at\s+(.+?)$', page_title or '', flags=re.I)
    if title_match:
        fields['job_title'] = _clean_title(title_match.group(1))
        fields['company'] = _clean_company(title_match.group(2))
    headings = [_clean_value(elem.get_text(' ', strip=True)) for elem in soup.select('h1')]
    if len(headings) >= 2:
        if not fields.get('company'):
            fields['company'] = _clean_company(headings[0])
        if not fields.get('job_title') or _looks_generic_title(fields.get('job_title')):
            fields['job_title'] = _clean_title(headings[1], fields.get('company', ''))
    location = _first_text(soup, ['li.location', '.location', '[class*="location" i]'], 'location')
    if location:
        fields['location'] = location
    salary = _first_text(soup, ['li.salary-range', '.salary-range', '[class*="salary" i]'], 'salary')
    salary = _extract_salary(salary) or _extract_contextual_salary(full_text) or _extract_salary(full_text)
    if salary:
        fields['salary'] = salary
    work_type = _extract_work_type(full_text)
    if work_type:
        fields['work_type'] = work_type
    return fields


def _text_after_last_title(prefix, title):
    prefix = prefix or ''
    title = title or ''
    if not prefix or not title:
        return prefix
    pattern = r'\s+'.join(re.escape(part) for part in title.split())
    matches = list(re.finditer(pattern, prefix, flags=re.I))
    if matches:
        return prefix[matches[-1].end():].strip()
    title_words = [word for word in re.findall(r'[A-Za-z0-9]+', title.lower()) if len(word) > 1]
    prefix_words = list(re.finditer(r'[A-Za-z0-9]+', prefix.lower()))
    if not title_words or len(prefix_words) < len(title_words):
        return prefix
    for index in range(len(prefix_words) - len(title_words), -1, -1):
        window = [match.group(0) for match in prefix_words[index:index + len(title_words)]]
        if window == title_words:
            return prefix[prefix_words[index + len(title_words) - 1].end():].strip()
    return prefix


def _split_ziprecruiter_company_location(after_title):
    text = _normalize_text(after_title)
    city_suffixes = [
        ('new', 'york'), ('san', 'francisco'), ('los', 'angeles'), ('jersey', 'city'),
        ('long', 'island', 'city'), ('white', 'plains'), ('salt', 'lake', 'city'),
        ('garden', 'city'), ('great', 'neck'), ('palo', 'alto'), ('santa', 'clara'),
        ('las', 'vegas'), ('st', 'louis'), ('st', 'paul'), ('washington',),
        ('manhattan',), ('brooklyn',), ('queens',), ('bronx',), ('trenton',),
        ('woodmere',), ('baltimore',), ('seattle',), ('franklin',), ('chicago',),
    ]
    state_names = '|'.join(re.escape(name.title()) for name in US_STATE_NAME_TO_ABBR)
    city_pattern = rf'\b(?P<city>[A-Z][A-Za-z.\'&-]+(?:\s+[A-Z][A-Za-z.\'&-]+){{0,5}}),\s*(?P<state>{US_STATE}|{state_names})\b'
    for match in re.finditer(city_pattern, text):
        before = text[:match.start()].strip()
        city_words = re.findall(r"[A-Za-z.']+", match.group('city'))
        lowered = [word.lower().strip(".") for word in city_words]
        state = _state_abbrev(match.group('state')) or match.group('state')
        for suffix in sorted(city_suffixes, key=len, reverse=True):
            if len(lowered) >= len(suffix) and tuple(lowered[-len(suffix):]) == suffix:
                company_tail = city_words[:-len(suffix)]
                company = _clean_company(' '.join(part for part in (before, ' '.join(company_tail)) if part))
                city = ' '.join(word.title() for word in city_words[-len(suffix):])
                location = _clean_location(f'{city}, {state}')
                return company, location
        if len(city_words) > 1:
            company = _clean_company(' '.join(part for part in (before, ' '.join(city_words[:-1])) if part))
            location = _clean_location(f'{city_words[-1].title()}, {state}')
            return company, location
        return _clean_company(before), _clean_location(f'{match.group("city")}, {state}')
    remote_match = re.search(r'^(?P<company>.+?)\s+(?P<location>Remote|United States)(?=\s*(?:•|\$|Hybrid|Remote|Onsite|On-site|Posted|$))', text)
    if remote_match:
        return _clean_company(remote_match.group('company')), _clean_location(remote_match.group('location'))
    return '', ''


def _work_type_conflict(text):
    low = (text or '').lower()
    has_remote = any(term in low for term in ('remote', 'work from home', 'work-from-home', 'telework', 'telecommute'))
    has_onsite = any(term in low for term in ('on-site', 'onsite', 'in-office', 'in office', 'in person', 'on site'))
    return has_remote and has_onsite and 'hybrid' not in low


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
                ('white', 'plains'), ('salt', 'lake', 'city'), ('queens',),
                ('brooklyn',), ('bronx',), ('woodmere',),
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


def _title_from_slug(value):
    value = unquote(value or '')
    value = re.sub(r'[_+]+', '-', value)
    value = re.sub(r'--[0-9a-f-]{12,}$', '', value, flags=re.I)
    value = re.sub(r'[-_]*~[A-Za-z0-9_-]+$', '', value)
    tokens = [token for token in re.split(r'[-/\s]+', value.lower()) if token]
    tokens = [
        token for token in tokens
        if token not in {'job', 'jobs', 'opening', 'openings', 'apply', 'freelance', 'clone'}
        and not token.isdigit()
        and not re.fullmatch(r'[0-9a-f]{8,}', token)
    ]
    if not tokens:
        return ''
    return _clean_title(' '.join(tokens).title())


def _company_from_slug(value):
    company = _slug_to_name(value)
    for acronym in ('AI', 'ML', 'HR', 'IT', 'QA', 'QC', 'SQL', 'API', 'CRM', 'UX', 'UI'):
        company = re.sub(rf'\b{acronym.title()}\b', acronym, company)
    return company


def _location_from_slug_tokens(tokens):
    tokens = [token.lower() for token in tokens if token]
    if not tokens:
        return ''
    if tokens[-1] in {abbr.lower() for abbr in US_STATE_ABBR_TO_NAME} and len(tokens) >= 2:
        city_tokens = _city_words_before(tokens, len(tokens) - 1)
        if city_tokens:
            return f"{' '.join(word.title() for word in city_tokens)}, {tokens[-1].upper()}"
    for size in (3, 2, 1):
        if len(tokens) < size:
            continue
        state_name = ' '.join(tokens[-size:])
        abbr = US_STATE_NAME_TO_ABBR.get(state_name)
        if not abbr:
            continue
        city_tokens = []
        for token in reversed(tokens[:-size]):
            if token in {'job', 'jobs', 'career', 'careers', 'remote', 'apply'} or token.isdigit():
                break
            city_tokens.insert(0, token)
            if len(city_tokens) >= 4:
                break
        if city_tokens:
            return f"{' '.join(word.title() for word in city_tokens)}, {abbr}"
        return US_STATE_ABBR_TO_NAME.get(abbr, abbr)
    return ''


def _split_slug_title_location(slug):
    slug = unquote(slug or '').strip('/')
    clean_slug = re.sub(r'--[0-9a-f-]{12,}$', '', slug, flags=re.I)
    parts = re.split(r'(?i)-jobs-in-', clean_slug, maxsplit=1)
    if len(parts) == 2:
        return _title_from_slug(parts[0]), _clean_location(_location_from_slug_tokens(parts[1].split('-')))

    tokens = [token for token in re.split(r'[-_\s]+', clean_slug.lower()) if token]
    location = _location_from_slug_tokens(tokens)
    if location:
        location_words = re.split(r'[\s,]+', location.lower().replace(',', ''))
        trim_count = 0
        for token in reversed(tokens):
            if trim_count < len(location_words) and token == location_words[-1 - trim_count]:
                trim_count += 1
            else:
                break
        title_tokens = tokens[:-trim_count] if trim_count else tokens
        return _title_from_slug('-'.join(title_tokens)), location
    return _title_from_slug(clean_slug), ''


def _extract_url_hints(url, platform=''):
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace('www.', '')
    parts = [unquote(part) for part in parsed.path.split('/') if part]
    hints = {'job_title': '', 'company': '', 'location': ''}

    if platform == 'linkedin' and 'jobs' in parts and 'view' in parts:
        index = parts.index('view')
        if index + 1 < len(parts):
            slug = re.sub(r'-\d{6,}$', '', parts[index + 1])
            if '-at-' in slug:
                title_slug, company_slug = slug.rsplit('-at-', 1)
                hints['job_title'] = _title_from_slug(title_slug)
                hints['company'] = _company_from_slug(company_slug)
            else:
                hints['job_title'] = _title_from_slug(slug)
    elif host == 'jobs.talhealthcare.com' and 'jb' in parts:
        index = parts.index('jb')
        if index + 1 < len(parts):
            title, location = _split_slug_title_location(parts[index + 1])
            hints.update({'job_title': title, 'company': 'Tal Healthcare', 'location': location})
    elif 'monster.com' in host and 'job-openings' in parts:
        index = parts.index('job-openings')
        if index + 1 < len(parts):
            title, location = _split_slug_title_location(parts[index + 1])
            hints.update({'job_title': title, 'location': location})
    elif 'upwork.com' in host and 'apply' in parts:
        index = parts.index('apply')
        if index + 1 < len(parts):
            hints['job_title'] = _title_from_slug(parts[index + 1])
    elif 'wellfound.com' in host and 'jobs' in parts:
        index = parts.index('jobs')
        if index + 1 < len(parts):
            slug = re.sub(r'^\d+-', '', parts[index + 1])
            slug = re.sub(r'-clone$', '', slug, flags=re.I)
            hints['job_title'] = _title_from_slug(slug)
    elif 'naukri.com' in host and parts:
        slug = re.sub(r'^job-listings-', '', parts[0], flags=re.I)
        slug = re.sub(r'-\d+-to-\d+-years.*$', '', slug, flags=re.I)
        tokens = [token for token in slug.split('-') if token]
        indian_locations = {
            'gurugram': 'Gurugram, India',
            'gurgaon': 'Gurugram, India',
            'pune': 'Pune, India',
            'mumbai': 'Mumbai, India',
            'bengaluru': 'Bengaluru, India',
            'bangalore': 'Bengaluru, India',
            'delhi': 'Delhi, India',
            'hyderabad': 'Hyderabad, India',
            'chennai': 'Chennai, India',
        }
        location_index = next((i for i, token in enumerate(tokens) if token in indian_locations), None)
        if location_index and location_index >= 2:
            hints['location'] = indian_locations[tokens[location_index]]
            hints['company'] = _slug_to_name(tokens[location_index - 1])
            hints['job_title'] = _title_from_slug('-'.join(tokens[:location_index - 1]))
    elif 'glassdoor.com' in host and 'job-listing' in parts:
        index = parts.index('job-listing')
        if index + 1 < len(parts):
            slug = re.sub(r'-JV_.*$', '', parts[index + 1], flags=re.I)
            title, _ = _split_slug_title_location(slug)
            company_match = re.search(r'-([a-z0-9]+)$', slug, flags=re.I)
            if company_match:
                hints['company'] = _slug_to_name(company_match.group(1))
                title = _title_from_slug(slug[:company_match.start()])
            hints['job_title'] = title
    elif 'useparallel.com' in host:
        hints['company'] = ''
    elif 'talents.vaia.com' in host and 'companies' in parts:
        index = parts.index('companies')
        if index + 1 < len(parts):
            hints['company'] = _slug_to_name(parts[index + 1])
        if index + 2 < len(parts):
            hints['location'] = _extract_location_from_url(url)
            hints['job_title'] = _title_from_slug(re.sub(r'-\d+$', '', parts[index + 2]))
    return hints


def _apply_url_hints(data, url):
    hints = _extract_url_hints(url, _detect_platform(url))
    for key in ('company', 'job_title', 'location'):
        value = hints.get(key)
        if not value:
            continue
        if key == 'company' and _looks_generic_company(data.get(key, '')):
            data[key] = value
        elif key == 'job_title' and _looks_generic_title(data.get(key, '')):
            data[key] = value
        elif key == 'location' and not _clean_location(data.get(key, '')):
            data[key] = value
    return data


def _alternate_fetch_url(url):
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace('www.', '')
    parts = [unquote(part) for part in parsed.path.split('/') if part]
    if host == 'app.digitalhire.com' and len(parts) >= 2 and parts[0] == 'job-detail':
        return f'https://jobs.digitalhire.com/job-listing/opening/{parts[1]}'
    return ''


def _company_from_page_title(title):
    title = _clean_value(title)
    patterns = [
        r'\bat\s+([^|]+?)\s*\|\s*Parallel\b',
        r'\bat\s+([^|]+?)\s*\|\s*[^|]+$',
    ]
    for pattern in patterns:
        match = re.search(pattern, title, flags=re.I)
        if match:
            company = _clean_company(match.group(1))
            if _reasonable('company', company):
                return company
    return ''


def _location_from_title(title):
    title = _clean_value(title)
    match = re.search(r'\b(?:in|based in)\s+([A-Z][A-Za-z.\'-]+(?:\s+[A-Z][A-Za-z.\'-]+){0,3})(?:,\s*([A-Z]{2}))?$', title)
    if not match:
        return '', title
    city = match.group(1)
    state = match.group(2)
    known = {
        'Brooklyn': 'Brooklyn, NY',
        'Queens': 'Queens, NY',
        'Manhattan': 'New York, NY',
        'Bronx': 'Bronx, NY',
        'Woodmere': 'Woodmere, NY',
        'New York': 'New York, NY',
    }
    location = f"{city}, {state}" if state else known.get(city, '')
    if not location:
        return '', title
    clean_title = title[:match.start()].strip(' ,-')
    return location, clean_title or title


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
        ('queens',), ('brooklyn',), ('bronx',), ('woodmere',), ('trenton',),
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
    low = (text or '').lower().replace('_', '-')
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


def _extract_labeled_work_type(text):
    text = _normalize_text(text)
    if not text:
        return ''
    patterns = (
        r'\bLocation\s*[:\-]?\s*(Remote|Hybrid|On[-\s]?site|Onsite)\b',
        r'\b(?:workplace\s+type|work\s*type|job\s+location\s+type|location\s+type|workplace)\s*[:\-]?\s*(Remote|Hybrid|On[-\s]?site|Onsite|In[-\s]?office|In[-\s]?person)\b',
        r'\b(Remote|Hybrid|On[-\s]?site|Onsite|In[-\s]?office|In[-\s]?person)\s+(?:workplace|work\s*type|role|position|job)\b',
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return _normalize_work_type(match.group(1))
    return ''


def _extract_linkedin_work_type(soup, location=''):
    description = _linkedin_description_text(soup)
    metadata_selectors = (
        '.top-card-layout__second-subline',
        '.topcard__flavor-row',
        '.topcard__flavor--bullet',
        '.description__job-criteria-list',
        '.description__job-criteria-item',
        '.description__job-criteria-text',
        '[class*="job-criteria" i]',
        '[class*="workplace" i]',
        '[class*="location-type" i]',
        '[data-testid*="workplace" i]',
        '[data-testid*="location-type" i]',
    )
    metadata_parts = [
        elem.get_text(' ', strip=True)
        for elem in soup.select(', '.join(metadata_selectors))
    ]
    for elem in soup.select('[aria-label], [title], [data-tracking-control-name], [data-test-id], [data-testid]'):
        attrs = ' '.join(
            str(elem.get(attr) or '')
            for attr in ('aria-label', 'title', 'data-test-id', 'data-testid')
        )
        attr_probe = attrs.replace('_', '-')
        if re.search(r'\b(?:workplace|work\s*type|remote|hybrid|on[-\s]?site|in[-\s]?office)\b', attr_probe, flags=re.I):
            metadata_parts.append(attr_probe)
        tracking_probe = str(elem.get('data-tracking-control-name') or '').replace('_', '-')
        if re.search(r'\b(?:workplace|work\s*type|job[-\s]?location[-\s]?type|location[-\s]?type)\b', tracking_probe, flags=re.I):
            metadata_parts.append(tracking_probe)

    metadata_text = _normalize_text(' '.join(metadata_parts))
    metadata_work_type = _extract_work_type(metadata_text)
    if metadata_work_type:
        return metadata_work_type

    full_text = _normalize_text(soup.get_text(' ', strip=True))
    labeled_work_type = _extract_labeled_work_type(' '.join([metadata_text, full_text[:12000]]))
    if labeled_work_type:
        return labeled_work_type

    low = description.lower()

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
    low = _clean_value(value).lower().replace('_', '-')
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
    title = re.sub(r'\s+\bclone\b$', '', title, flags=re.I)
    if company:
        title = re.sub(rf'\s*[-|]\s*{re.escape(company)}.*$', '', title, flags=re.I)
    for acronym in ('AI', 'ML', 'HR', 'IT', 'QA', 'QC', 'SQL', 'API', 'CRM', 'UX', 'UI'):
        title = re.sub(rf'\b{acronym.title()}\b', acronym, title)
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
    url_hints = _extract_url_hints(original_url, platform)

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
    title_tag_text = soup.title.get_text(' ', strip=True) if soup.title else ''
    page_title_company = _company_from_page_title(title_tag_text or meta_title or '')
    if page_title_company and _looks_generic_company(data.get('company', '')):
        data['company'] = page_title_company
    if not data['company'] and platform == 'company_website' and meta_site and _reasonable('company', meta_site):
        data['company'] = meta_site
    if not data['description'] and meta_description:
        data['description'] = meta_description

    full_text = _normalize_text(soup.get_text(separator=' ', strip=True))
    preferred_link = _extract_preferred_apply_link(soup, url, original_url)
    if preferred_link:
        data['preferred_job_link'] = preferred_link
    blocked_error = _blocked_page_error(' '.join([meta_title or '', full_text[:3000]]))
    locked_site_work_type_na = False
    if blocked_error:
        data['error'] = blocked_error
    if platform == 'ziprecruiter' and not blocked_error:
        zip_fields = _extract_ziprecruiter_fields(soup, full_text, meta_title)
        for key in ('company', 'job_title', 'location', 'work_type', 'salary'):
            if zip_fields.get(key):
                data[key] = zip_fields[key]
    host = urlparse(original_url).netloc.lower().replace('www.', '')
    if 'simplyhired.com' in host and not blocked_error:
        simplyhired_fields = _extract_simplyhired_fields(soup, full_text, title_tag_text or meta_title or '')
        locked_site_work_type_na = simplyhired_fields.get('work_type') == 'n/a'
        for key in ('company', 'job_title', 'location', 'work_type', 'salary'):
            if simplyhired_fields.get(key):
                data[key] = simplyhired_fields[key]
    if 'breezy.hr' in host and not blocked_error:
        breezy_fields = _extract_breezy_fields(soup, full_text, title_tag_text or meta_title or '')
        for key in ('company', 'job_title', 'location', 'work_type', 'salary'):
            if breezy_fields.get(key):
                data[key] = breezy_fields[key]
    if not data['salary']:
        data['salary'] = _extract_salary(full_text)
    url_location = _extract_location_from_url(original_url)
    taleo_location = _extract_taleo_location(full_text) if 'taleo.net' in urlparse(original_url).netloc.lower() else ''
    amazon_location = _extract_amazon_locations(full_text) if 'amazon.jobs' in urlparse(original_url).netloc.lower() else ''
    if platform == 'workday':
        visible_location = _visible_workday_location(soup)
        if visible_location and (not data['location'] or _location_looks_internal(data['location'])):
            data['location'] = visible_location
    if taleo_location:
        data['location'] = taleo_location
    elif amazon_location:
        data['location'] = amazon_location
    elif not data['location']:
        data['location'] = url_location or _extract_location(full_text)
    elif url_location and str(data['location']).strip().lower() in {'remote', 'hybrid', 'onsite', 'on-site'}:
        data['location'] = url_location
    if url_hints.get('location') and not data['location']:
        data['location'] = url_hints['location']
    if platform == 'linkedin':
        data['salary'] = _extract_linkedin_salary(soup)
        page_work_type = _extract_linkedin_work_type(soup, data.get('location', ''))
    else:
        data['salary'] = _extract_salary(data.get('salary', ''))
        work_type_source = ' '.join([data.get('location', ''), data.get('description', ''), full_text])
        page_work_type = _extract_work_type(work_type_source)
    locked_na_work_type = _clean_value(data.get('work_type', '')).lower() in {'n/a', 'na'}
    if page_work_type and not locked_na_work_type and not _normalize_work_type(data.get('work_type', '')):
        data['work_type'] = page_work_type
    if locked_site_work_type_na:
        data['work_type'] = ''
    if not data['company']:
        data['company'] = _extract_company_from_text(full_text, platform)
    if not data['company']:
        data['company'] = _infer_company_from_url(url, platform)
    if url_hints.get('company') and _looks_generic_company(data.get('company', '')):
        data['company'] = url_hints['company']
    data['company'] = _clean_company(data['company'])
    if page_title_company and _looks_generic_company(data.get('company', '')):
        data['company'] = page_title_company
    if not data['company']:
        data['company'] = _clean_company(_infer_company_from_url(original_url, platform))
    if url_hints.get('company') and _looks_generic_company(data.get('company', '')):
        data['company'] = _clean_company(url_hints['company'])
    for domain, company in COMPANY_HOST_OVERRIDES.items():
        if host == domain or host.endswith('.' + domain):
            data['company'] = company
            break
    for key, value in _field_overrides(original_url).items():
        if key in data and value:
            data[key] = value
    data['location'] = _clean_location(data['location'])
    data['work_type'] = _normalize_work_type(data['work_type'])
    data['source'] = _source_label(platform)

    data['job_title'] = _clean_title(data['job_title'], data['company'])
    if url_hints.get('job_title') and _looks_generic_title(data.get('job_title', '')):
        data['job_title'] = _clean_title(url_hints['job_title'], data['company'])
    if data['job_title'] and (not data['company'] or data['company'].lower() in {'ai', 'aijobs'}):
        title_company = re.search(r'^(.+?)\s+at\s+([^|,-]{2,80})$', data['job_title'], flags=re.I)
        if title_company:
            data['job_title'] = _clean_title(title_company.group(1))
            data['company'] = _clean_company(title_company.group(2))
    if data['job_title'] and not data['location']:
        title_location, clean_title = _location_from_title(data['job_title'])
        if title_location:
            data['location'] = title_location
            data['job_title'] = _clean_title(clean_title, data['company'])
    if not data['job_title']:
        heading = _first_text(soup, ['main h1', 'article h1', 'h1', 'h2'], 'job_title')
        data['job_title'] = _clean_title(heading, data['company'])
    if url_hints.get('job_title') and _looks_generic_title(data.get('job_title', '')):
        data['job_title'] = _clean_title(url_hints['job_title'], data['company'])

    return data


def _public_result(data):
    public_keys = [
        'date_applied', 'company', 'job_title', 'job_link', 'status',
        'location', 'work_type', 'salary', 'follow_up', 'source', 'error',
        'preferred_job_link',
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


def _extract_preferred_apply_link(soup, page_url, original_url=''):
    if not soup:
        return ''
    board_host = urlparse(original_url or page_url).netloc.lower().replace('www.', '')
    if _detect_platform(original_url or page_url) == 'company_website':
        return ''

    labels = re.compile(
        r'\b(apply\s+(?:on|at|with)\s+(?:company|employer|external)|'
        r'company\s+(?:site|website)|employer\s+(?:site|website)|'
        r'apply\s+externally|external\s+apply|view\s+on\s+company)\b',
        flags=re.I,
    )
    blocked_hosts = {
        'linkedin.com', 'indeed.com', 'glassdoor.com', 'ziprecruiter.com',
        'monster.com', 'wellfound.com', 'upwork.com', 'simplyhired.com',
        'dice.com', 'google.com',
    }
    for anchor in soup.select('a[href]'):
        text = _clean_value(anchor.get_text(' ', strip=True) or anchor.get('aria-label') or anchor.get('title') or '')
        href = anchor.get('href') or ''
        if not href or not labels.search(text):
            continue
        absolute = urljoin(page_url, href)
        parsed = urlparse(absolute)
        host = parsed.netloc.lower().replace('www.', '')
        if parsed.scheme not in {'http', 'https'} or not host or host == board_host:
            continue
        if any(host == blocked or host.endswith('.' + blocked) for blocked in blocked_hosts):
            continue
        return absolute
    return ''


async def _open_job_page(page, url, timeout):
    response = await page.goto(url, wait_until='domcontentloaded', timeout=timeout)
    status = response.status if response else None
    await page.wait_for_timeout(2500)
    try:
        await page.wait_for_load_state('networkidle', timeout=5000)
    except Exception:
        pass
    if 'simplyhired.com' in urlparse(url).netloc.lower():
        try:
            await page.wait_for_selector('h1', timeout=7000)
        except Exception:
            pass
        await page.wait_for_timeout(2500)
        return status

    try:
        iframe_src = await page.evaluate(
            """() => {
                const frame = document.querySelector('iframe#grnhse_iframe, iframe[src*="greenhouse"], iframe[src*="lever"], iframe[src*="ashby"]');
                return frame ? frame.src : '';
            }"""
        )
    except Exception:
        await page.wait_for_timeout(2000)
        iframe_src = ''
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
    try:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    except Exception:
        await page.wait_for_timeout(1500)
    await page.wait_for_timeout(1000)
    await _expand_job_details(page)
    try:
        await page.evaluate("window.scrollTo(0, 0)")
    except Exception:
        await page.wait_for_timeout(1500)
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
    icims_result = _icims_iframe_result(url)
    if icims_result:
        return icims_result
    fetch_url = _alternate_fetch_url(url) or url

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
            ),
            viewport={'width': 1366, 'height': 900},
        )
        await install_playwright_network_guard(context)
        page = await context.new_page()
        try:
            status = await _open_job_page(page, fetch_url, timeout)
            if status in (404, 410):
                data = _empty_result(url, _detect_platform(url))
                _apply_url_hints(data, url)
                data['error'] = f'Job page is unavailable (HTTP {status})'
                return _public_result(data)
            if status in (401, 403, 429):
                data = _empty_result(url, _detect_platform(url))
                _apply_url_hints(data, url)
                data['error'] = f'Website blocked automated access to this posting (HTTP {status})'
                return _public_result(data)
            if _unavailable_redirect(fetch_url, page.url or fetch_url):
                data = _empty_result(url, _detect_platform(url))
                _apply_url_hints(data, url)
                data['error'] = 'Job page redirected to a general careers page and is likely unavailable.'
                return _public_result(data)
            _final_url, final_url_error = validate_public_url(page.url or fetch_url)
            if final_url_error:
                data = _empty_result(url, _detect_platform(url))
                _apply_url_hints(data, url)
                data['error'] = 'Job page redirected to a blocked network address.'
                return _public_result(data)
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            return _public_result(_extract_from_soup(soup, page.url or fetch_url, url))
        except Exception as exc:
            data = _empty_result(url, _detect_platform(url))
            _apply_url_hints(data, url)
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
