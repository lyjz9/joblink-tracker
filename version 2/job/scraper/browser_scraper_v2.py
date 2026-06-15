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


def _clean_value(value):
    value = _normalize_text(value)
    value = re.sub(r'^(job title|title|company|location|salary|compensation)\s*[:\-]\s*', '', value, flags=re.I)
    return value.strip(' |,-')


def _clean_company(value):
    value = _clean_value(value)
    if value.lower() in {'none', 'null', 'n/a', 'na'}:
        return ''
    value = re.sub(r'\s+\d+(?:\.\d+)?\s*(?:out of 5 stars?|stars?)?.*$', '', value, flags=re.I)
    known = {
        'fdmgroup': 'FDM Group',
        'fdm group': 'FDM Group',
        'nyulangone': 'NYU Langone Health',
        'nyu langone': 'NYU Langone Health',
        'nyu langone health': 'NYU Langone Health',
    }
    return known.get(value.lower(), value)


def _clean_location(value):
    value = _clean_value(value)
    if not value:
        return ''

    blocked_exact = {
        'clear text', 'permanent', 'full', 'full time', 'full-time', 'contract',
        'temporary', 'apply', 'posted', 'save job',
    }
    low_value = value.lower()
    if low_value.startswith('remote'):
        return 'Remote'
    if low_value.startswith('hybrid'):
        return 'Hybrid'
    city_state = re.search(rf'\b([A-Z][A-Za-z.\'-]+(?:\s+[A-Z][A-Za-z.\'-]+){{0,3}}),\s*({US_STATE})\b', value)
    if city_state:
        city = city_state.group(1).split()[-3:]
        return f"{' '.join(city)}, {city_state.group(2)}"

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
        return not any(term in value.lower() for term in blocked)
    if field == 'company':
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
    clean = []
    for match in LOCATION_RE.finditer(text or ''):
        loc = _clean_location(match.group(0))
        if loc and loc not in clean:
            clean.append(loc)
    return ', '.join(clean[:2])


def _extract_location_from_url(url):
    tokens = re.split(r'[-/_]+', unquote(urlparse(url).path).lower())
    states = set(US_STATE.strip('(?:)').lower().split('|'))
    state_index = next((i for i, token in enumerate(tokens) if token in states), None)
    if state_index is None or state_index == 0:
        return ''

    before_state = [token for token in tokens[:state_index] if token and token not in {'job', 'jobs', 'career', 'careers'}]
    if not before_state:
        return ''

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


def _extract_work_type(text):
    low = (text or '').lower()
    has_remote = 'remote' in low
    has_hybrid = 'hybrid' in low
    has_onsite = any(term in low for term in ('on-site', 'onsite', 'in-office', 'in office', 'in person', 'on site'))
    if has_hybrid or (has_remote and has_onsite):
        return 'Hybrid' if has_hybrid else 'Mix'
    if has_remote:
        return 'Remote'
    if has_onsite:
        return 'Onsite'
    return ''


def _normalize_work_type(value):
    low = _clean_value(value).lower()
    if not low:
        return ''
    if 'hybrid' in low:
        return 'Hybrid'
    if 'mix' in low:
        return 'Mix'
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
    meta_description = _get_meta_content(soup, 'property', ['og:description', 'twitter:description'])
    if not data['job_title'] and meta_title:
        data['job_title'] = meta_title
    if not data['description'] and meta_description:
        data['description'] = meta_description

    full_text = _normalize_text(soup.get_text(separator=' ', strip=True))
    if not data['salary']:
        data['salary'] = _extract_salary(full_text)
    if not data['location']:
        data['location'] = _extract_location_from_url(original_url) or _extract_location(full_text)
    data['salary'] = _extract_salary(data.get('salary', ''))
    work_type_source = ' '.join([data.get('location', ''), data.get('description', '')[:1200]])
    page_work_type = _extract_work_type(work_type_source)
    if page_work_type and data.get('work_type') in ('', 'Full-time', 'Part-time', 'Contract', 'Temporary', 'Internship'):
        data['work_type'] = page_work_type
    if not data['company']:
        data['company'] = _extract_company_from_text(full_text, platform)
    if not data['company']:
        data['company'] = _infer_company_from_url(url, platform)
    data['company'] = _clean_company(data['company'])
    data['location'] = _clean_location(data['location'])
    data['work_type'] = _normalize_work_type(data['work_type'])
    data['source'] = _source_label(platform)

    data['job_title'] = _clean_title(data['job_title'], data['company'])
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
