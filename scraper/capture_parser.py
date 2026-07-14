"""Parse full-page payloads sent by the local JobLink Capture extension."""

import json
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scraper.browser_scraper_v2 import (
    _clean_company,
    _clean_location,
    _clean_title,
    _clean_value,
    _detect_platform,
    _extract_contextual_salary,
    _extract_salary,
    _extract_work_type,
    _extract_url_hints,
    _reasonable,
    _source_label,
)
from scraper.result_quality import (
    _annotate_result,
    _missing,
    _public_scrape_result,
    _quality_issues,
    _review_notes,
)
from scraper.scraper import (
    _extract_jsonld_job_fields,
    _flatten_dict_strings,
    _get_meta_content,
    _normalize_text,
    _parse_jsonld,
    _parse_next_data,
)


def _capture_payload_has_content(payload):
    text = str(payload.get('text') or '').strip()
    if len(text) >= 20:
        return True
    html = str(payload.get('html') or '').strip()
    if len(html) >= 200:
        return True
    if isinstance(payload.get('meta'), dict) and any(str(value).strip() for value in payload.get('meta', {}).values()):
        return True
    if isinstance(payload.get('candidates'), dict) and any(payload.get('candidates', {}).values()):
        return True
    if isinstance(payload.get('jsonld'), list) and any(str(value).strip() for value in payload.get('jsonld', [])):
        return True
    if isinstance(payload.get('json_scripts'), list) and any(str(value).strip() for value in payload.get('json_scripts', [])):
        return True
    return False


def _parse_captured_page(payload):
    url = str(payload.get('url') or '').strip()
    title = _clean_capture_line(payload.get('title') or '')
    text = str(payload.get('text') or '')
    lines = _capture_lines(text)
    platform = _detect_platform(url)
    url_hints = _extract_url_hints(url, platform)
    soup = _capture_soup(payload)
    meta = payload.get('meta') if isinstance(payload.get('meta'), dict) else {}
    meta_text = _capture_meta_text(meta, soup)
    candidate_fields, candidate_text = _capture_candidate_fields(payload, title, lines)
    html_text = _capture_html_text(soup)
    script_text = _capture_json_script_text(payload)
    top_text = ' '.join(lines[:80])
    all_text = ' '.join(lines[:1200])
    rich_text = ' '.join(part for part in (meta_text, candidate_text, top_text, all_text, html_text, script_text) if part)
    evidence = {}

    result = {
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
    }

    for key, value in _capture_structured_fields(soup).items():
        _merge_capture_value(result, evidence, key, value, 'structured')

    for key in ('company', 'job_title', 'location'):
        if url_hints.get(key):
            _merge_capture_value(result, evidence, key, url_hints[key], 'url')

    for key, values in candidate_fields.items():
        for value in values:
            if _merge_capture_value(result, evidence, key, value, 'page_label'):
                break

    preferred_link = _capture_preferred_link(soup, url)
    if preferred_link:
        result['preferred_job_link'] = preferred_link

    title_job, title_company = _split_capture_title(title or _capture_meta_title(meta, soup))
    if title_job:
        _merge_capture_value(result, evidence, 'job_title', title_job, 'page_title')
    if title_company:
        _merge_capture_value(result, evidence, 'company', title_company, 'page_title')

    if _missing(result['job_title']):
        _merge_capture_value(result, evidence, 'job_title', _capture_meta_title(meta, soup), 'meta')
    if _missing(result['company']):
        _merge_capture_value(result, evidence, 'company', _capture_meta_company(meta, soup), 'meta')

    if _missing(result['job_title']):
        _merge_capture_value(result, evidence, 'job_title', _first_capture_title(lines), 'text')
    if _missing(result['company']):
        _merge_capture_value(result, evidence, 'company', _capture_company(lines, result['job_title'], title_company), 'text')
    if _missing(result['company']):
        _merge_capture_value(result, evidence, 'company', _capture_company(_capture_lines(html_text), result['job_title'], title_company), 'html')
    if platform == 'wellfound' and _missing(result['company']):
        _merge_capture_value(result, evidence, 'company', _capture_wellfound_company(rich_text, result['job_title']), 'text')

    if _missing(result['location']):
        _merge_capture_value(result, evidence, 'location', _capture_location(lines) or _capture_location(rich_text), 'text')
    if _missing(result['work_type']):
        _merge_capture_value(result, evidence, 'work_type', _capture_work_type(rich_text, url), 'text')
    if _missing(result['salary']):
        _merge_capture_value(result, evidence, 'salary', _capture_salary(rich_text), 'text')

    public = _public_scrape_result(result)
    public['field_options'] = {
        key: values[:6]
        for key, values in candidate_fields.items()
        if values and key in {'company', 'job_title', 'location', 'work_type', 'salary'}
    }
    issues = _quality_issues(public)
    issues.extend(_capture_review_issues(public, evidence))
    if issues:
        public['review_issues'] = sorted(set(issues))
        public['review_notes'] = _review_notes(public['review_issues'])
    public['capture_source'] = 'browser_button'
    public['capture_evidence'] = evidence
    _annotate_result(public, url, public.get('review_issues', []))
    return public


def _merge_capture_value(result, evidence, key, value, source):
    if key not in result or not _missing(result.get(key)):
        return False
    cleaned = _clean_capture_field(key, value)
    if not cleaned:
        return False
    result[key] = cleaned
    evidence[key] = source
    return True


def _clean_capture_field(key, value):
    value = _clean_value(value)
    if not value:
        return ''
    if key == 'company':
        value = _clean_upwork_client(value)
        if _capture_location(value):
            return ''
        value = _clean_company(value)
        return value if _reasonable('company', value) and _company_candidate(value) else ''
    if key == 'job_title':
        value = _clean_title(value)
        return value if _reasonable('job_title', value) else ''
    if key == 'location':
        value = _clean_location(value) or _capture_location(value)
        if value.lower() in {'remote', 'hybrid', 'onsite', 'on-site'}:
            return ''
        return value if _reasonable('location', value) else ''
    if key == 'work_type':
        return _capture_work_type(value)
    if key == 'salary':
        return _capture_salary(value)
    return value


def _capture_html_text(soup):
    if not soup:
        return ''
    clone = BeautifulSoup(str(soup), 'html.parser')
    for tag in clone(['script', 'style', 'noscript', 'svg']):
        tag.decompose()
    return _normalize_text(clone.get_text(' ', strip=True))[:300000]


def _capture_json_script_text(payload):
    scripts = payload.get('json_scripts') if isinstance(payload.get('json_scripts'), list) else []
    values = []
    for raw in scripts[:12]:
        text = str(raw or '')
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = None
        if parsed is not None:
            flat = _flatten_dict_strings(parsed)
            values.extend(value for items in flat.values() for value in items[:3])
        else:
            values.append(text[:20000])
    return _normalize_text(' '.join(values))[:300000]


def _capture_preferred_link(soup, page_url):
    if not soup:
        return ''
    platform = _detect_platform(page_url)
    if platform == 'company_website':
        return ''
    page_host = urlparse(page_url or '').netloc.lower().replace('www.', '')
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
        text = _clean_capture_line(anchor.get_text(' ', strip=True) or anchor.get('aria-label') or anchor.get('title') or '')
        if not text or not labels.search(text):
            continue
        absolute = urljoin(page_url, anchor.get('href') or '')
        parsed = urlparse(absolute)
        host = parsed.netloc.lower().replace('www.', '')
        if parsed.scheme not in {'http', 'https'} or not host or host == page_host:
            continue
        if any(host == blocked or host.endswith('.' + blocked) for blocked in blocked_hosts):
            continue
        return absolute
    return ''
def _capture_candidate_fields(payload, page_title, lines):
    candidates = payload.get('candidates') if isinstance(payload.get('candidates'), dict) else {}
    fields = {key: [] for key in ('company', 'job_title', 'location', 'work_type', 'salary')}
    focused_text = []

    headings = [str(item) for item in candidates.get('headings', []) if item]
    for heading in headings[:30]:
        job, company = _split_capture_title(heading)
        _add_capture_candidate(fields, 'job_title', job or heading)
        _add_capture_candidate(fields, 'company', company)
    title_job, title_company = _split_capture_title(page_title)
    _add_capture_candidate(fields, 'job_title', title_job)
    _add_capture_candidate(fields, 'company', title_company)

    for pair in candidates.get('labelPairs', [])[:220]:
        if not isinstance(pair, dict):
            continue
        label = _clean_capture_line(pair.get('label'))
        value = str(pair.get('value') or '')
        key = _capture_key_from_label(label)
        if not key:
            continue
        extracted = _capture_value_after_label(value, label)
        _add_capture_candidate(fields, key, extracted)
        focused_text.append(f'{label}: {extracted}')

    for block in candidates.get('headerBlocks', [])[:45]:
        block_lines = _capture_lines(block)
        if not block_lines:
            continue
        focused_text.append(' '.join(block_lines[:24]))
        _add_capture_candidate(fields, 'job_title', _first_capture_title(block_lines))
        _add_capture_candidate(fields, 'company', _capture_company(block_lines, fields['job_title'][0] if fields['job_title'] else ''))
        _add_capture_candidate(fields, 'location', _capture_location(block_lines))
        _add_capture_candidate(fields, 'work_type', _capture_work_type(' '.join(block_lines[:50])))
        _add_capture_candidate(fields, 'salary', _capture_salary(' '.join(block_lines[:80])))

    keyword_lines = [str(item) for item in candidates.get('keywordLines', []) if item]
    keyword_text = ' '.join(keyword_lines[:120])
    focused_text.append(keyword_text)
    _add_capture_candidate(fields, 'location', _capture_location(keyword_lines))
    _add_capture_candidate(fields, 'work_type', _capture_work_type(keyword_text))
    _add_capture_candidate(fields, 'salary', _capture_salary(keyword_text))

    # A few blocked boards put the best header in the first readable lines.
    header_lines = lines[:40]
    _add_capture_candidate(fields, 'job_title', _first_capture_title(header_lines))
    _add_capture_candidate(fields, 'company', _capture_company(header_lines, fields['job_title'][0] if fields['job_title'] else ''))
    _add_capture_candidate(fields, 'location', _capture_location(header_lines))

    return fields, ' '.join(part for part in focused_text if part)


def _add_capture_candidate(fields, key, value):
    if not value or key not in fields:
        return
    cleaned = _clean_capture_field(key, value)
    if not cleaned:
        return
    if cleaned.lower() not in {item.lower() for item in fields[key]}:
        fields[key].append(cleaned)


def _capture_key_from_label(label):
    low = _clean_capture_line(label).lower()
    if not low:
        return ''
    if any(term in low for term in ('pay type', 'employment type', 'job type', 'project type')):
        return 'work_type'
    if any(term in low for term in ('salary', 'compensation', 'base pay', 'pay range', 'budget', 'hourly', 'fixed-price', 'fixed price', 'rate')):
        return 'salary'
    if any(term in low for term in ('work type', 'workplace', 'job location type', 'remote', 'remote job', 'hybrid')):
        return 'work_type'
    if 'location' in low or 'office' in low:
        return 'location'
    if any(term in low for term in ('company', 'client', 'employer', 'organization', 'hiring company')):
        return 'company'
    if any(term in low for term in ('job title', 'position title', 'role title')):
        return 'job_title'
    return ''


def _capture_value_after_label(value, label):
    label_text = _clean_capture_line(label)
    raw_lines = [_clean_capture_line(line) for line in re.split(r'[\r\n]+', str(value or ''))]
    raw_lines = [line for line in raw_lines if line and not _capture_noise(line)]
    for index, line in enumerate(raw_lines):
        if label_text and line.lower() == label_text.lower() and index + 1 < len(raw_lines):
            return raw_lines[index + 1]
        if label_text and line.lower().startswith(label_text.lower()):
            remainder = line[len(label_text):].strip(' :-|')
            if remainder:
                return remainder
    text = _clean_capture_line(value)
    if not text:
        return ''
    if label_text and text.lower().startswith(label_text.lower()):
        text = text[len(label_text):].strip(' :-|')
    parts = [part.strip() for part in re.split(r'\s*(?:\n|\||;|•|·)\s*', text) if part.strip()]
    if parts:
        return parts[0]
    return text


def _capture_review_issues(result, evidence):
    issues = []
    required = ('company', 'job_title', 'location')
    noisy_sources = {'text', 'meta', 'page_title', 'html'}
    if any(evidence.get(field) in noisy_sources for field in required if not _missing(result.get(field))):
        issues.append('captured_page_review')
    if any(not evidence.get(field) for field in required):
        issues.append('capture_low_confidence')
    return issues


def _capture_lines(text):
    seen = set()
    lines = []
    for raw in re.split(r'[\r\n]+', str(text or '')):
        line = _clean_capture_line(raw)
        key = line.lower()
        if not line or key in seen or _capture_noise(line):
            continue
        seen.add(key)
        lines.append(line)
    return lines

def _capture_soup(payload):
    html = str(payload.get('html') or '')
    parts = [html[:1200000]]
    jsonld = payload.get('jsonld') if isinstance(payload.get('jsonld'), list) else []
    for raw in jsonld[:20]:
        if raw:
            parts.append(f'<script type="application/ld+json">{raw}</script>')
    next_data = str(payload.get('next_data') or '')
    if next_data and '__NEXT_DATA__' not in html:
        parts.append(f'<script id="__NEXT_DATA__" type="application/json">{next_data}</script>')
    combined = '\n'.join(part for part in parts if part)
    return BeautifulSoup(combined, 'html.parser') if combined else None


def _capture_structured_fields(soup):
    if not soup:
        return {}

    fields = {}
    jsonld_fields = _extract_jsonld_job_fields(_parse_jsonld(soup))
    for key, value in jsonld_fields.items():
        value = _clean_value(value)
        if value and key in {'company', 'job_title', 'location', 'salary', 'work_type'}:
            fields[key] = value

    flat = _flatten_dict_strings(_parse_next_data(soup))
    flat_values = ' '.join(value for values in flat.values() for value in values[:3])
    flat_map = {
        'job_title': ('jobtitle', 'job_title', 'positiontitle', 'title', 'name'),
        'company': ('companyname', 'company', 'hiringorganization', 'organization', 'employer', 'clientname'),
        'location': ('joblocation', 'location', 'addresslocality', 'addressregion', 'city', 'state', 'country'),
        'salary': ('salary', 'salaryrange', 'compensation', 'basepay', 'payrange', 'pay'),
        'work_type': ('workplacetype', 'joblocationtype', 'worktype', 'remote', 'hybrid'),
    }
    for key, keys in flat_map.items():
        if _missing(fields.get(key)):
            picked = _capture_pick_flat(flat, keys)
            if picked:
                fields[key] = picked

    if _missing(fields.get('salary')):
        fields['salary'] = _extract_contextual_salary(flat_values) or _extract_salary(flat_values)
    if _missing(fields.get('work_type')):
        fields['work_type'] = _extract_work_type(flat_values)
    fields['work_type'] = _normalize_capture_work_type(fields.get('work_type'))
    return {key: value for key, value in fields.items() if value}


def _capture_pick_flat(flat, keys):
    for key in keys:
        for value in flat.get(key, []):
            value = _clean_value(value)
            if 2 <= len(value) <= 180:
                return value
    for flat_key, values in flat.items():
        if any(key in flat_key for key in keys):
            for value in values:
                value = _clean_value(value)
                if 2 <= len(value) <= 180:
                    return value
    return ''


def _capture_meta_text(meta, soup):
    values = []
    if isinstance(meta, dict):
        values.extend(str(value) for value in meta.values() if value)
    if soup:
        values.extend(
            _get_meta_content(soup, attr, keys)
            for attr, keys in (
                ('property', ('og:title', 'og:description', 'og:site_name')),
                ('name', ('title', 'description', 'twitter:title', 'twitter:description')),
            )
        )
    return _normalize_text(' '.join(value for value in values if value))


def _capture_meta_title(meta, soup):
    for key in ('og:title', 'twitter:title', 'title'):
        value = _clean_capture_line((meta or {}).get(key, ''))
        if value:
            return _split_capture_title(value)[0] or value
    if soup and soup.title:
        value = _clean_capture_line(soup.title.get_text(' ', strip=True))
        return _split_capture_title(value)[0] or value
    return ''


def _capture_meta_company(meta, soup):
    for key in ('og:site_name', 'twitter:site', 'application-name'):
        value = _clean_capture_line((meta or {}).get(key, ''))
        if _company_candidate(value):
            return value.lstrip('@')
    if soup:
        value = _get_meta_content(soup, 'property', ('og:site_name',))
        if _company_candidate(value):
            return value
    return ''


def _normalize_capture_work_type(value):
    if not value:
        return ''
    explicit = _extract_work_type(value)
    if explicit:
        return explicit
    low = _clean_value(value).lower()
    if low in {'remote', 'remote job', 'worldwide'}:
        return 'Remote'
    if low in {'hybrid'}:
        return low.title()
    if low in {'onsite', 'on-site', 'in-office', 'in person', 'in-person'}:
        return 'Onsite'
    return ''


def _capture_work_type(value, url=''):
    text = _clean_value(value)
    explicit = _normalize_capture_work_type(text)
    if explicit:
        return explicit
    low = text.lower()
    if re.search(r'\b(?:remote job|work remotely|worldwide|anywhere)\b', low):
        return 'Remote'
    if 'upwork.com' in urlparse(url or '').netloc.lower() and re.search(r'\b(?:freelance|contract|client|proposal|connects)\b', low):
        return 'Remote'
    return ''

def _capture_salary(value):
    text = _clean_value(value)
    if not text:
        return ''
    money = _extract_contextual_salary(text) or _extract_salary(text)
    if money:
        return _salary_with_nearby_equity(text, money)
    budget = re.search(
        r'\b(?:budget|hourly|fixed[-\s]?price|rate)\b.{0,80}?'
        r'(\$\s*\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:-|\u2013|\u2014|to)\s*\$?\s*\d+(?:,\d{3})*(?:\.\d+)?)?(?:\s*/?\s*(?:hr|hour|wk|week|yr|year))?)',
        text,
        flags=re.I,
    )
    if budget:
        return _clean_value(budget.group(1))
    return ''


def _salary_with_nearby_equity(text, salary):
    salary = _clean_value(salary)
    if not salary:
        return ''
    start = text.lower().find(salary.lower())
    window = text if start < 0 else text[start:start + 260]
    equity = re.search(
        r'(\d+(?:\.\d+)?\s*%\s*(?:-|\u2013|\u2014|to)\s*\d+(?:\.\d+)?\s*%|\d+(?:\.\d+)?\s*%)\s*(?:equity|stock options?|options?)?',
        window,
        flags=re.I,
    )
    if equity and equity.group(1) not in salary:
        label = ' equity' if not re.search(r'\b(?:equity|stock|options?)\b', equity.group(0), flags=re.I) else ''
        return _clean_value(f'{salary} + {equity.group(1)}{label}')
    return salary


def _clean_upwork_client(value):
    text = _clean_capture_line(value)
    text = re.sub(r'^(?:client|posted by|hiring client)\s*[:\-]?\s*', '', text, flags=re.I).strip()
    text = re.sub(r'\b(?:payment verified|client rating|member since|spent|hires|jobs posted)\b.*$', '', text, flags=re.I).strip(' ,;-')
    if text.lower() in {'client', 'upwork client', 'payment verified'}:
        return ''
    return text


def _capture_wellfound_company(text, job_title=''):
    text = _clean_value(text)
    job_title = _clean_capture_line(job_title)
    if not text:
        return ''

    title_pattern = re.escape(job_title) if job_title else r'[A-Z][A-Za-z0-9&,\- ]{4,120}'
    for pattern in (
        rf'{title_pattern}\s+at\s+([^|•·,\n]{{2,80}})',
        r'\bCompany\s*[:\-]\s*([^|•·,\n]{2,80})',
        r'\bHiring company\s*[:\-]\s*([^|•·,\n]{2,80})',
    ):
        match = re.search(pattern, text, flags=re.I)
        if match and _company_candidate(match.group(1)):
            return _clean_capture_line(match.group(1))

    lines = _capture_lines(text)
    for index, line in enumerate(lines[:160]):
        if job_title and line.lower() == job_title.lower():
            for offset in (1, 2, -1, -2):
                pos = index + offset
                if 0 <= pos < len(lines) and _company_candidate(lines[pos]):
                    return lines[pos]
        if re.fullmatch(r'(?:Actively Hiring|Recently Posted|Early Stage|Growing Fast)', line, flags=re.I):
            continue
        if index + 1 < len(lines) and re.search(r'\b(?:founder|recruiter|hiring manager|talent)\b', lines[index + 1], flags=re.I):
            if _company_candidate(line):
                return line
    return ''


def _clean_capture_line(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip(' |')


def _capture_noise(line):
    low = line.lower()
    if len(line) > 180:
        return True
    exact = {
        'apply', 'apply now', 'save', 'sign in', 'log in', 'login', 'search',
        'jobs', 'job search', 'share this job', 'back to jobs', 'skip to main content',
        'privacy policy', 'terms of use', 'cookie policy',
    }
    if low in exact:
        return True
    return bool(re.search(r'\b(?:cookie|privacy|terms|newsletter|download our app|recommended jobs)\b', low))


def _split_capture_title(title):
    title = _clean_capture_line(title)
    title = re.sub(r'\s*\|\s*(?:Wellfound|Glassdoor|LinkedIn|Indeed|Dice\.com|ZipRecruiter).*$','', title, flags=re.I)
    match = re.search(r'^(.+?)\s+at\s+(.+?)$', title, flags=re.I)
    if match:
        return _clean_capture_line(match.group(1)), _clean_capture_line(match.group(2))
    match = re.search(r'^(.+?)\s+-\s+(.+?)(?:\s+\|\s+.+)?$', title)
    if match:
        first = _clean_capture_line(match.group(1))
        second = _clean_capture_line(match.group(2))
        if not re.search(r'\b[A-Z]{2}\b|Remote|Hybrid|On-site|Onsite', second, flags=re.I):
            return first, second
    return title if title and len(title) <= 120 else '', ''


def _first_capture_title(lines):
    blocked = re.compile(r'\b(?:job details|description|about|requirements|qualifications|benefits|company|search)\b', re.I)
    for line in lines[:30]:
        if 4 <= len(line) <= 120 and not blocked.search(line) and not _capture_location(line) and not _extract_salary(line):
            return line
    return ''


def _capture_company(lines, job_title='', title_company=''):
    if title_company:
        return title_company
    for index, line in enumerate(lines[:120]):
        if re.fullmatch(r'(?:company|employer|organization|hiring company)', line, flags=re.I):
            if index + 1 < len(lines) and _company_candidate(lines[index + 1]):
                return lines[index + 1]
        match = re.search(r'\b(?:company|employer|organization|hiring company)\s*[:\-]\s*(.+)$', line, flags=re.I)
        if match and _company_candidate(match.group(1)):
            return _clean_capture_line(match.group(1))
    if job_title:
        for index, line in enumerate(lines[:40]):
            if line == job_title and index + 1 < len(lines):
                candidate = lines[index + 1]
                if _company_candidate(candidate):
                    return candidate
            if line == job_title and index > 0:
                candidate = lines[index - 1]
                if _company_candidate(candidate):
                    return candidate
    for pattern in (
        r'\bCompany\s*[:\-]\s*([^|]{2,80})',
        r'\bEmployer\s*[:\-]\s*([^|]{2,80})',
        r'\bAbout\s+([^|]{2,80})',
    ):
        match = re.search(pattern, ' '.join(lines[:120]), flags=re.I)
        if match and _company_candidate(match.group(1)):
            return _clean_capture_line(match.group(1))
    return ''


def _company_candidate(value):
    low = _clean_capture_line(value).lower()
    if not low or low in {
        'remote', 'hybrid', 'onsite', 'on-site', 'full-time', 'part-time',
        'upwork', 'linkedin', 'indeed', 'glassdoor', 'ziprecruiter',
        'simplyhired', 'dice', 'monster', 'wellfound',
        'actively hiring', 'recently posted', 'early stage', 'growing fast',
        'founder', 'recruiter', 'hiring manager', 'talent',
    }:
        return False
    if re.search(r'\$|\b(?:posted|apply|location|salary|full-time|part-time|contract|equity|employees|founded|jobs)\b', low):
        return False
    return len(value) <= 80


def _capture_location(value):
    if isinstance(value, (list, tuple)):
        for line in value[:800]:
            location = _capture_location(line)
            if location:
                return location
        return ''

    text = str(value or '')
    match = re.search(
        r'\b([A-Z][A-Za-z.\'-]+(?:\s+[A-Z][A-Za-z.\'-]+){0,3}),\s*'
        r'(A[LKZR]|C[AOT]|D[CE]|FL|GA|HI|I[ADLN]|K[SY]|LA|M[ADEINOST]|N[CDEHJMVY]|O[HKR]|PA|RI|S[CD]|T[NX]|UT|V[AIT]|W[AIVY])\b',
        text,
    )
    if match:
        return f"{match.group(1)}, {match.group(2)}"
    states = (
        'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado',
        'Connecticut', 'Delaware', 'Florida', 'Georgia', 'Hawaii', 'Idaho',
        'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky', 'Louisiana',
        'Maine', 'Maryland', 'Massachusetts', 'Michigan', 'Minnesota',
        'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada',
        'New Hampshire', 'New Jersey', 'New Mexico', 'New York',
        'North Carolina', 'North Dakota', 'Ohio', 'Oklahoma', 'Oregon',
        'Pennsylvania', 'Rhode Island', 'South Carolina', 'South Dakota',
        'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia', 'Washington',
        'West Virginia', 'Wisconsin', 'Wyoming',
    )
    state_match = re.search(r'\b(' + '|'.join(re.escape(state) for state in states) + r')\b', text, flags=re.I)
    if state_match and re.search(r'\b(?:location|remote|state|usa|united states|based in)\b', text, flags=re.I):
        return state_match.group(1)
    if re.search(r'\bUnited States\b', text or '', flags=re.I):
        return 'United States'
    return ''
