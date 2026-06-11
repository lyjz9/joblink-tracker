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

FIELD_SELECTORS = {
    'job_title': [
        '[data-qa="job-title"]', '[data-testid="job-title"]', '[data-test="job-title"]',
        '[itemprop="title"]', 'h1[class*="title" i]', 'h1[class*="job" i]',
        '.posting-headline h2', '.posting-title h2', '.app-title', '.opening__title',
        '.job-title', '.job__title h1', 'h1',
    ],
    'company': [
        '[data-qa="company"]', '[data-testid="company"]', '[itemprop="hiringOrganization"]',
        '[class*="company-name" i]', '[class*="employer" i]', '.posting-company',
        '.top-card-layout__company-name', '.jobsearch-InlineCompanyRating-companyHeader',
    ],
    'location': [
        '[data-qa="location"]', '[data-testid="location"]', '[itemprop="jobLocation"]',
        '[class*="job-location" i]', '[class*="location" i]', '.posting-categories',
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
LOCATION_RE = re.compile(
    rf'\b(?:Remote|Hybrid|United States|US|USA|[A-Z][A-Za-z.\'-]+(?:\s+[A-Z][A-Za-z.\'-]+){{0,3}},\s*(?:{US_STATE}|United States|USA|Canada|UK|[A-Z][a-z]+))\b'
)
SALARY_RE = re.compile(
    r'(?:USD\s*)?\$?\b\d{2,3}(?:,\d{3})*(?:\.\d+)?\s*(?:k|K)?\s*(?:-|to|and)\s*(?:USD\s*)?\$?\d{2,3}(?:,\d{3})*(?:\.\d+)?\s*(?:k|K)?(?:\s*(?:per|/)\s*(?:year|yr|hour|hr|annum))?|\$\d{2,3}(?:,\d{3})+\+?',
    re.IGNORECASE,
)


def _empty_result(url):
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
        'skills': '',
        'source': url,
        'description': '',
        'ai_note': '',
    }


def _detect_platform(url, soup=None):
    host = urlparse(url).netloc.lower()
    for board, domains in JOB_BOARDS.items():
        if any(domain in host for domain in domains):
            return board
    if soup:
        html = str(soup)[:200000].lower()
        for board in ('greenhouse', 'lever', 'ashby', 'workday', 'smartrecruiters', 'workable', 'icims'):
            if board in html:
                return board
    return 'company_website'


def _clean_value(value):
    value = _normalize_text(value)
    value = re.sub(r'^(job title|title|company|location|salary|compensation)\s*[:\-]\s*', '', value, flags=re.I)
    return value.strip(' |,-')


def _reasonable(field, value):
    if not value:
        return False
    value = _clean_value(value)
    if field in ('job_title', 'company', 'location') and len(value) > 140:
        return False
    if field == 'job_title':
        blocked = ['sign in', 'apply now', 'search jobs', 'job details', 'careers', 'privacy']
        return not any(term in value.lower() for term in blocked)
    if field == 'company':
        return value.lower() not in {'careers', 'jobs', 'job search', 'apply'}
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


def _extract_location(text):
    matches = [_clean_value(match.group(0)) for match in LOCATION_RE.finditer(text or '')]
    clean = []
    for match in matches:
        if match.lower() not in {'apply', 'posted'} and match not in clean:
            clean.append(match)
    return ', '.join(clean[:3])


def _extract_work_type(text):
    low = (text or '').lower()
    if 'hybrid' in low:
        return 'Hybrid'
    if 'remote' in low:
        return 'Remote'
    if any(term in low for term in ('on-site', 'onsite', 'in-office', 'in office', 'in person')):
        return 'On-site'
    return ''


def _infer_company_from_url(url, platform):
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace('www.', '')
    path_parts = [unquote(part) for part in parsed.path.split('/') if part]
    query = parse_qs(parsed.query)

    if platform == 'greenhouse':
        if 'for' in query and query['for']:
            return _slug_to_name(query['for'][0])
        if 'boards.greenhouse.io' in host and path_parts:
            return _slug_to_name(path_parts[0])
    if platform == 'lever' and path_parts:
        return _slug_to_name(path_parts[0])
    if platform == 'ashby' and len(path_parts) > 1:
        return _slug_to_name(path_parts[1])
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
    return _normalize_text(slug.title())


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


def _extract_from_soup(soup, url):
    for tag in soup(['script', 'style', 'noscript', 'svg']):
        tag.decompose()

    platform = _detect_platform(url, soup)
    data = _empty_result(url)

    for candidate in _find_json_candidates(soup):
        _merge(data, candidate)

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
    meta_description = _get_meta_content(soup, 'property', ['og:description', 'twitter:description'])
    if not data['job_title'] and meta_title:
        data['job_title'] = meta_title
    if not data['description'] and meta_description:
        data['description'] = meta_description

    full_text = _normalize_text(soup.get_text(separator=' ', strip=True))
    if not data['salary']:
        data['salary'] = _extract_salary(full_text)
    if not data['location']:
        data['location'] = _extract_location(full_text)
    page_work_type = _extract_work_type(' '.join([data.get('location', ''), data.get('description', ''), full_text[:3000]]))
    if page_work_type and data.get('work_type') in ('', 'Full-time', 'Part-time', 'Contract', 'Temporary', 'Internship'):
        data['work_type'] = page_work_type
    if not data['company']:
        data['company'] = _infer_company_from_url(url, platform)

    data['job_title'] = _clean_title(data['job_title'], data['company'])
    if not data['job_title']:
        heading = _first_text(soup, ['main h1', 'article h1', 'h1', 'h2'], 'job_title')
        data['job_title'] = _clean_title(heading, data['company'])

    missing = [label for key, label in (
        ('company', 'company'),
        ('job_title', 'job title'),
        ('location', 'location'),
    ) if not data.get(key)]
    if missing:
        data['ai_note'] = 'Missing: ' + ', '.join(missing)
    return data


async def _open_job_page(page, url, timeout):
    await page.goto(url, wait_until='domcontentloaded', timeout=timeout)
    await page.wait_for_timeout(2500)

    iframe_src = await page.evaluate(
        """() => {
            const frame = document.querySelector('iframe#grnhse_iframe, iframe[src*="greenhouse"], iframe[src*="lever"], iframe[src*="ashby"]');
            return frame ? frame.src : '';
        }"""
    )
    if iframe_src:
        await page.goto(iframe_src, wait_until='domcontentloaded', timeout=timeout)
        await page.wait_for_timeout(2000)

    for selector in ['[data-qa="job-title"]', '[data-testid="job-title"]', '#jobDescriptionText', 'main', 'h1']:
        try:
            await page.wait_for_selector(selector, timeout=2500)
            break
        except Exception:
            continue

    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(1000)
    await page.evaluate("window.scrollTo(0, 0)")
    await page.wait_for_timeout(500)


async def scrape_job_with_browser(url, timeout=60000):
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
            await _open_job_page(page, url, timeout)
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            return _extract_from_soup(soup, page.url or url)
        except Exception as exc:
            data = _empty_result(url)
            data['error'] = str(exc)
            data['ai_note'] = 'Scrape failed before extraction.'
            return data
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
