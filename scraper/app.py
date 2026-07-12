from collections import defaultdict, deque
from flask import Flask, request, jsonify, render_template, send_file
import hashlib
import hmac
import io
import json
import os
import re
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from werkzeug.middleware.proxy_fix import ProxyFix

from scraper.config import JobLinkConfig
from scraper.security import validate_public_url, validate_workbook_upload

from scraper.scraper import (
    parse_job_from_html,
    _extract_jsonld_job_fields,
    _flatten_dict_strings,
    _get_meta_content,
    _normalize_text,
    _parse_jsonld,
    _parse_next_data,
)
from scraper.browser_scraper_v2 import (
    parse_job_with_browser,
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
from export.exporter import export_jobs_to_xlsx
from export.workbook_appender import append_jobs_to_workbook

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config.from_object(JobLinkConfig)
production_secret = str(app.config.get('SECRET_KEY') or '')
if app.config['IS_PRODUCTION'] and (
    len(production_secret) < 32
    or production_secret.casefold() in {'joblink-local-development-key', 'replace-me', 'change-me'}
):
    raise RuntimeError('JOBLINK_SECRET_KEY must be a random value of at least 32 characters in production.')
if app.config['TRUST_PROXY_HOPS']:
    trusted_hops = app.config['TRUST_PROXY_HOPS']
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=trusted_hops,
        x_proto=trusted_hops,
        x_host=trusted_hops,
    )

request_history = defaultdict(deque)
request_history_lock = threading.Lock()
ISSUE_LOG = str(app.config['LOG_DIR'] / 'extraction_issues.jsonl')
USER_REPORT_LOG = str(app.config['LOG_DIR'] / 'user_reported_issues.jsonl')
BETA_FEEDBACK_LOG = str(app.config['LOG_DIR'] / 'beta_feedback.jsonl')
CAPTURED_JOBS = deque(maxlen=50)

RELIABILITY = {
    'greenhouse': ('Good', 'Usually has clean structured job data.'),
    'lever': ('Good', 'Usually has clean structured job data.'),
    'ashby': ('Good', 'Usually has clean structured job data.'),
    'workday': ('Good', 'Usually has structured job data, but some pages load slowly.'),
    'icims': ('Good', 'Usually works well after reading the embedded job frame.'),
    'breezy': ('Good', 'Usually has readable job details.'),
    'smartrecruiters': ('Good', 'Usually has clean structured job data.'),
    'company_website': ('Good', 'Company career pages are usually the best source.'),
    'linkedin': ('Okay', 'Often has title/company/location, but salary can be missing.'),
    'indeed': ('Okay', 'Often works, but page text can include extra location words.'),
    'glassdoor': ('Okay', 'Often works, but some pages block automation.'),
    'ziprecruiter': ('Okay', 'Can work, but reposts may include noisy page text.'),
    'simplyhired': ('Okay', 'Can work, but some pages redirect or hide details.'),
    'dice': ('Okay', 'Can work, but some pages block automation.'),
    'monster': ('Limited', 'Monster is unreliable. Use the employer/company link Monster opens instead.'),
    'wellfound': ('Limited', 'Often blocks direct scraping. Browser capture may need review.'),
    'upwork': ('Limited', 'Often blocks direct scraping and uses project-style fields.'),
}


def _merge_scrape_results(primary, fallback):
    merged = dict(primary or {})
    for key, value in (fallback or {}).items():
        if key in ('error', 'description', 'skills', 'ai_note'):
            continue
        if value and _missing(merged.get(key)):
            merged[key] = value
    if merged.get('source') and not merged.get('job_link'):
        merged['job_link'] = merged['source']
    if merged.get('job_link') and not merged.get('source'):
        merged['source'] = merged['job_link']
    if merged.get('source', '').startswith('http'):
        merged['source'] = _source_label(_detect_platform(merged.get('job_link') or merged.get('source')))
    return _public_scrape_result(merged)


def _missing(value):
    return str(value or '').strip().lower() in {'', 'n/a', 'none', 'null'}


def _validate_public_url(url):
    return validate_public_url(url)


def _rate_limited(scope, limit):
    client = request.remote_addr or 'unknown'
    now = time.time()
    cutoff = now - app.config['RATE_WINDOW_SECONDS']
    key = (scope, client)
    with request_history_lock:
        history = request_history[key]
        while history and history[0] < cutoff:
            history.popleft()
        if len(history) >= limit:
            return True
        history.append(now)

        if len(request_history) > 5000:
            stale_keys = [item for item, values in request_history.items() if not values or values[-1] < cutoff]
            for stale_key in stale_keys:
                request_history.pop(stale_key, None)
    return False


def _scrape_url(url):
    if _is_monster_search_url(url):
        return _monster_guidance_result(url)

    result = {}
    terminal_error = False
    for attempt in range(2):
        result = parse_job_with_browser(url)
        error = str(result.get('error', '')).lower()
        terminal_error = any(marker in error for marker in (
            'http 404', 'http 410', 'unavailable', 'redirected to a general careers page',
            'blocked automated access', 'access denied', 'captcha',
        ))
        if not result.get('error') or terminal_error:
            break
        if attempt == 0:
            time.sleep(1.5)

    required = ('company', 'job_title', 'location')
    if terminal_error:
        result = _public_scrape_result(result)
    elif result.get('error') or any(_missing(result.get(field)) for field in required):
        try:
            fallback = parse_job_from_html(url)
        except Exception:
            fallback = {}
        merged = _merge_scrape_results(result, fallback)
        if not all(_missing(merged.get(field)) for field in ('company', 'job_title')):
            merged.pop('error', None)
        result = merged
    else:
        result = _public_scrape_result(result)
    raw_error = result.get('error', '')
    issues = _quality_issues(result)
    if issues:
        _record_issue(url, result, issues, raw_error)
        result['review_issues'] = issues
        result['review_notes'] = _review_notes(issues)
    if raw_error:
        result['error'] = _friendly_error(raw_error, url)
    _annotate_result(result, url, issues)
    return result


def _is_monster_search_url(url):
    parsed = urlparse(url or '')
    host = parsed.netloc.lower()
    return 'monster.com' in host and parsed.path.rstrip('/').lower() in {'/jobs/search', '/jobs'}


def _monster_guidance_result(url):
    result = {
        'date_applied': datetime.now().strftime('%m/%d/%Y'),
        'company': 'n/a',
        'job_title': 'n/a',
        'job_link': url,
        'status': '',
        'location': 'n/a',
        'work_type': 'n/a',
        'salary': 'n/a',
        'follow_up': '',
        'source': 'Monster',
        'error': 'Monster search pages are not supported. Open the employer or company job page from Monster and use that link instead.',
        'review_issues': ['monster_search_page'],
        'review_notes': 'Monster search pages show many jobs at once, so JobLink cannot turn them into one accurate tracker row. Use the employer/company job page link from Monster instead.',
    }
    _annotate_result(result, url, result['review_issues'])
    return result


def _quality_issues(result):
    issues = []
    for field in ('company', 'job_title', 'location'):
        if _missing(result.get(field)):
            issues.append(f'missing_{field}')
    company = str(result.get('company', '')).strip()
    location = str(result.get('location', '')).strip()
    work_type = str(result.get('work_type', '')).strip()
    if location.lower() in {'remote', 'hybrid', 'onsite', 'on-site'}:
        issues.append('location_looks_like_work_type')
    if company.lower() in {
        'early career', 'careers', 'jobs', 'job', 'app', 'embed', 'talent',
        'recruiting', 'monster', 'wellfound', 'jooble', 'naukri', 'talents',
        'useparallel', 'upwork', 'linkedin', 'indeed', 'glassdoor',
        'ziprecruiter', 'simplyhired', 'dice',
    }:
        issues.append('generic_company')
    title = str(result.get('job_title', '')).strip()
    if title.lower() in {'access denied', 'humans only', 'www.ziprecruiter.com', 'jooble.org', 'digitalhire'}:
        issues.append('generic_job_title')
    comparable_company = re.sub(r'\W+', '', company.lower())
    comparable_title = re.sub(r'\W+', '', title.lower())
    if comparable_company and comparable_company == comparable_title:
        issues.append('generic_job_title')
    if len(company) > 55 or re.search(r'\b(?:this position|company reserves|benefit programs|base salary|apply now|select how often)\b', company, flags=re.I):
        issues.append('company_looks_like_page_text')
    if len(location) > 70 or re.search(r'\b(?:posted|time type|apply|salary|experience|job segment|view all jobs)\b', location, flags=re.I):
        issues.append('location_looks_like_page_text')
    if work_type.lower() == 'mix':
        issues.append('invalid_work_type')
    if result.get('confidence') == 'Low':
        issues.append('low_confidence')
    if result.get('error'):
        issues.append('scrape_error')
    return sorted(set(issues))


def _review_notes(issues):
    labels = {
        'missing_company': 'Company is missing.',
        'missing_job_title': 'Job title is missing.',
        'missing_location': 'Location is missing.',
        'location_looks_like_work_type': 'Location may be a work type instead of a place.',
        'generic_company': 'Company name looks too generic.',
        'generic_job_title': 'Job title looks like a blocked or generic page.',
        'company_looks_like_page_text': 'Company may be copied from page text.',
        'location_looks_like_page_text': 'Location may include extra page text.',
        'invalid_work_type': 'Work type should be Remote, Hybrid, Onsite, or n/a.',
        'scrape_error': 'The scraper hit an error.',
        'captured_page_review': 'Captured pages can include extra site text; review these fields.',
        'capture_low_confidence': 'Captured fields were not found in a clear job header or label.',
        'monster_search_page': 'Monster search pages show many jobs at once. Use the employer/company link from Monster instead.',
        'low_confidence': 'Extraction confidence is low.',
    }
    notes = [labels.get(issue, issue.replace('_', ' ')) for issue in issues]
    return ' '.join(notes)


def _review_details(issues):
    detail_map = {
        'missing_company': ('Company missing', 'Company', 'Open the posting and fill in the employer name.'),
        'missing_job_title': ('Job title missing', 'Job title', 'Open the posting and fill in the role title.'),
        'missing_location': ('Location missing', 'Location', 'Fill in the location if the posting shows one.'),
        'location_looks_like_work_type': ('Location looks wrong', 'Location', 'Move Remote/Hybrid/Onsite to Work Type and enter the actual place if listed.'),
        'generic_company': ('Company too generic', 'Company', 'Replace the job-board name with the real employer.'),
        'generic_job_title': ('Title too generic', 'Job title', 'Replace blocked-page text with the real role title.'),
        'company_looks_like_page_text': ('Company has extra text', 'Company', 'Keep only the employer name.'),
        'location_looks_like_page_text': ('Location has extra text', 'Location', 'Keep only the city/state/country.'),
        'invalid_work_type': ('Work type invalid', 'Work Type', 'Use Remote, Hybrid, Onsite, or n/a.'),
        'scrape_error': ('Scrape failed', 'Link', 'Retry, use browser capture, or edit the fields and click the check.'),
        'captured_page_review': ('Captured page needs review', 'Captured row', 'Review fields because captured pages can include extra site text.'),
        'capture_low_confidence': ('Capture confidence low', 'Captured row', 'Use the suggestions or edit the fields manually.'),
        'monster_search_page': ('Monster unsupported', 'Link', 'Use the employer/company job page that Monster opens.'),
        'low_confidence': ('Low confidence', 'Row', 'Review the row before saving.'),
    }
    return [
        {'code': issue, 'label': detail_map.get(issue, (issue.replace('_', ' ').title(), 'Row', 'Review this row.'))[0],
         'field': detail_map.get(issue, ('', 'Row', ''))[1],
         'action': detail_map.get(issue, ('', 'Row', 'Review this row.'))[2]}
        for issue in issues
    ]


def _reliability_for(url, source=''):
    platform = _detect_platform(url or '')
    if platform == 'company_website':
        source_key = re.sub(r'[^a-z0-9]+', '', str(source or '').lower())
        source_lookup = {
            'linkedin': 'linkedin', 'indeed': 'indeed', 'glassdoor': 'glassdoor',
            'ziprecruiter': 'ziprecruiter', 'monster': 'monster', 'wellfound': 'wellfound',
            'upwork': 'upwork', 'simplyhired': 'simplyhired', 'dice': 'dice',
            'greenhouse': 'greenhouse', 'lever': 'lever', 'workday': 'workday',
            'ashby': 'ashby', 'icims': 'icims', 'breezy': 'breezy',
            'smartrecruiters': 'smartrecruiters',
        }
        platform = source_lookup.get(source_key, platform)
    label, note = RELIABILITY.get(platform, RELIABILITY['company_website'])
    return {'level': label, 'note': note}


def _confidence_for(result, issues):
    score = 95
    source_reliability = (result.get('source_reliability') or {}).get('level') or ''
    if source_reliability == 'Limited':
        score -= 18
    elif source_reliability == 'Okay':
        score -= 8
    if result.get('capture_source'):
        score -= 8
    penalties = {
        'missing_company': 18,
        'missing_job_title': 22,
        'missing_location': 16,
        'generic_company': 16,
        'generic_job_title': 18,
        'company_looks_like_page_text': 18,
        'location_looks_like_page_text': 14,
        'location_looks_like_work_type': 14,
        'invalid_work_type': 10,
        'captured_page_review': 8,
        'capture_low_confidence': 15,
        'scrape_error': 28,
        'monster_search_page': 35,
    }
    for issue in issues:
        score -= penalties.get(issue, 8)
    score = max(0, min(100, score))
    if result.get('error'):
        level = 'Low'
    elif score >= 82:
        level = 'High'
    elif score >= 58:
        level = 'Medium'
    else:
        level = 'Low'
    return level, score


def _annotate_result(result, url='', issues=None):
    job_url = url or result.get('job_link') or ''
    reliability = _reliability_for(job_url, result.get('source', ''))
    result['source_reliability'] = reliability
    result['source_reliability_label'] = reliability['level']
    result['source_reliability_note'] = reliability['note']
    issues = sorted(set(issues or result.get('review_issues') or []))
    result['review_issues'] = issues
    result['review_details'] = _review_details(issues)
    confidence, score = _confidence_for(result, issues)
    result['confidence'] = confidence
    result['confidence_score'] = score
    if not result.get('review_notes') and issues:
        result['review_notes'] = _review_notes(issues)
    if result.get('preferred_job_link'):
        result['preferred_job_link_note'] = 'Employer/company job page found. This is usually better than the job-board link.'
    return result


def _record_issue(url, result, issues, raw_error=''):
    os.makedirs(os.path.dirname(ISSUE_LOG), exist_ok=True)
    record = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        **_private_url_record(url),
        'issues': issues,
        'result': {
            key: _bounded_log_value(result.get(key, ''))
            for key in ('company', 'job_title', 'location', 'work_type', 'salary', 'source')
        },
        'technical_error': str(raw_error)[:2000],
    }
    with open(ISSUE_LOG, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + '\n')


def _bounded_log_value(value, limit=500):
    return str(value or '')[:limit]


def _private_url_record(url):
    normalized = str(url or '').strip()
    record = {
        'domain': urlparse(normalized).hostname or '',
        'url_hash': hashlib.sha256(normalized.encode('utf-8')).hexdigest() if normalized else '',
    }
    if app.config['STORE_FULL_URLS']:
        record['url'] = normalized
    return record


def _issues_access_allowed():
    if not app.config['EXPOSE_ISSUES']:
        return False
    expected = app.config.get('ADMIN_TOKEN', '')
    supplied = request.headers.get('X-JobLink-Admin', '')
    if expected:
        return hmac.compare_digest(expected, supplied)
    return not app.config['IS_PRODUCTION'] and request.remote_addr in {'127.0.0.1', '::1'}


@app.route('/api/issues')
def issues():
    if not _issues_access_allowed():
        return jsonify({'error': 'Not found.'}), 404
    if not os.path.exists(ISSUE_LOG):
        return jsonify([])
    with open(ISSUE_LOG, 'r', encoding='utf-8') as handle:
        records = [json.loads(line) for line in handle if line.strip()]
    return jsonify(records[-100:])


@app.route('/api/report-issue', methods=['POST'])
def report_issue():
    if _rate_limited('report-issue', app.config['RATE_LIMIT_FEEDBACK']):
        return jsonify({'error': 'Too many reports. Wait a few minutes and try again.'}), 429
    payload = request.get_json(silent=True) or {}
    job = payload.get('job') if isinstance(payload.get('job'), dict) else {}
    url = str(job.get('job_link') or payload.get('url') or '').strip()
    if not url:
        return jsonify({'error': 'No job row was provided.'}), 400

    os.makedirs(os.path.dirname(USER_REPORT_LOG), exist_ok=True)
    job_record = {
        key: _bounded_log_value(job.get(key, ''), 1000)
        for key in (
            'date_applied', 'company', 'job_title', 'job_link', 'location',
            'work_type', 'salary', 'source', 'status', 'manual',
            'source_reliability_label', 'source_reliability_note',
            'confidence', 'confidence_score', 'error', 'review_notes',
            'preferred_job_link',
        )
    }
    if not app.config['STORE_FULL_URLS']:
        job_record['job_link'] = ''
        job_record['preferred_job_link'] = ''

    record = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        **_private_url_record(url),
        'status': payload.get('status') or '',
        'note': str(payload.get('note') or '')[:1000],
        'job': job_record,
        'review_issues': [
            _bounded_log_value(item, 100)
            for item in (job.get('review_issues') or [])[:20]
        ],
    }
    with open(USER_REPORT_LOG, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + '\n')
    return jsonify({'status': 'saved'})


@app.route('/api/feedback', methods=['POST'])
def beta_feedback():
    if _rate_limited('feedback', app.config['RATE_LIMIT_FEEDBACK']):
        return jsonify({'error': 'Too much feedback was sent. Wait a few minutes and try again.'}), 429
    payload = request.get_json(silent=True) or {}
    message = str(payload.get('message') or '').strip()
    if not message:
        return jsonify({'error': 'Feedback message is required.'}), 400

    feedback_type = str(payload.get('type') or 'general').strip().lower()
    if feedback_type not in {'general', 'bug', 'idea', 'confusing'}:
        feedback_type = 'general'

    os.makedirs(os.path.dirname(BETA_FEEDBACK_LOG), exist_ok=True)
    record = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'type': feedback_type,
        'message': message[:3000],
        'page': urlparse(str(payload.get('page') or '')).path[:200],
        'job_count': payload.get('job_count', 0),
        'version': 'JobLink Beta v0.1',
    }
    with open(BETA_FEEDBACK_LOG, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + '\n')
    return jsonify({'status': 'saved'})


def _friendly_error(error, url=''):
    low = str(error or '').lower()
    if 'monster.com' in urlparse(url or '').netloc.lower():
        return 'Monster blocks reliable job-detail scraping. Open the employer or company job page from Monster and use that link instead.'
    if any(marker in low for marker in ('http 404', 'http 410', 'unavailable', 'general careers page')):
        return 'This posting is unavailable or has expired.'
    if any(marker in low for marker in ('blocked automated access', 'access denied', 'captcha')):
        return 'The website blocked automated access. Open the job page yourself, then use JobLink Capture.'
    if any(marker in low for marker in ('timeout', 'timed out')):
        return 'The website took too long to respond. Retry this job.'
    if any(marker in low for marker in ('http 403', 'http 429', 'access denied', 'captcha')):
        return 'The website blocked automated access. Open the job page yourself, then use JobLink Capture.'
    if 'cannot navigate to invalid url' in low:
        return 'The job link is not a valid web address.'
    return 'The scraper could not read this posting. Retry it or review the link.'


def _capture_response(payload, status=200):
    response = jsonify(payload)
    response.status_code = status
    origin = request.headers.get('Origin', '')
    allowed_local_origins = {
        'http://127.0.0.1:5050',
        'http://localhost:5050',
        'http://127.0.0.1:5000',
        'http://localhost:5000',
    }
    if origin.startswith('chrome-extension://') or origin in allowed_local_origins:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Vary'] = 'Origin'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    response.headers['Access-Control-Allow-Private-Network'] = 'true'
    response.headers['Access-Control-Max-Age'] = '86400'
    return response


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


def _public_scrape_result(result):
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
    clean = {}
    for key in public_keys:
        value = result.get(key, '')
        if key in defaults and not value:
            value = defaults[key]
        if value:
            clean[key] = value
    return clean

@app.route('/')
def index():
    return render_template('index.html')


@app.after_request
def add_security_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
    response.headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
    response.headers.setdefault(
        'Content-Security-Policy',
        "default-src 'self'; script-src 'self' https://unpkg.com; style-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; "
        "frame-ancestors 'none'; form-action 'self'",
    )
    if request.path.startswith('/api/') or request.path in {'/scrape', '/export', '/append-workbook'}:
        response.headers.setdefault('Cache-Control', 'no-store')
    if app.config['IS_PRODUCTION']:
        response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    return response


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({'error': 'The upload is larger than the allowed limit.'}), 413


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


@app.route('/api/capture-page', methods=['POST', 'OPTIONS'])
def capture_page():
    if not app.config['CAPTURE_ENABLED']:
        return _capture_response({
            'error': 'Browser capture is available only in the local JobLink app.'
        }, 404)
    if request.method == 'OPTIONS':
        return _capture_response({'status': 'ok'})
    if _rate_limited('capture', app.config['RATE_LIMIT_CAPTURE']):
        return _capture_response({'error': 'Too many captures. Wait a few minutes and try again.'}, 429)

    payload = request.get_json(silent=True) or request.form.to_dict()
    if not isinstance(payload, dict):
        return _capture_response({'error': 'The captured page could not be read.'}, 400)

    if not _capture_payload_has_content(payload):
        return _capture_response({
            'error': 'The extension could not read the job details. Make sure the real job posting is visible, then capture again.',
        }, 400)

    job = _parse_captured_page(payload)
    CAPTURED_JOBS.appendleft(job)
    return _capture_response({'job': job, 'count': len(CAPTURED_JOBS)})


@app.route('/api/captures')
def captures():
    if not app.config['CAPTURE_ENABLED']:
        return jsonify({'error': 'Not found.'}), 404
    return jsonify({'jobs': list(CAPTURED_JOBS)})


@app.route('/scrape', methods=['POST'])
def scrape():
    if _rate_limited('scrape', app.config['RATE_LIMIT_SCRAPE']):
        return jsonify({'error': 'Too many requests. Wait a few minutes and try again.'}), 429

    data = request.get_json() or {}
    url, validation_error = _validate_public_url(data.get('url'))
    if validation_error:
        return jsonify({'error': validation_error}), 400

    try:
        return jsonify(_scrape_url(url))
    except Exception:
        app.logger.exception('Job scraping failed')
        return jsonify({'error': 'The scraper could not process this job page.'}), 500

@app.route('/export', methods=['POST'])
def export():
    if _rate_limited('export', app.config['RATE_LIMIT_EXPORT']):
        return jsonify({'error': 'Too many exports. Wait a few minutes and try again.'}), 429
    jobs = request.get_json() or []
    if not isinstance(jobs, list) or not jobs:
        return jsonify({'error': 'Add at least one job before exporting.'}), 400
    max_jobs = app.config['MAX_EXPORT_JOBS']
    if len(jobs) > max_jobs:
        return jsonify({'error': f'A maximum of {max_jobs} jobs can be exported at once.'}), 400
    with tempfile.TemporaryDirectory(prefix='joblink-export-') as temp_dir:
        out_path = export_jobs_to_xlsx(jobs, outdir=temp_dir)
        workbook_bytes = Path(out_path).read_bytes()
        download_name = os.path.basename(out_path)
    return send_file(
        io.BytesIO(workbook_bytes),
        as_attachment=True,
        download_name=download_name,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


@app.route('/append-workbook', methods=['POST'])
def append_workbook():
    if _rate_limited('append-workbook', app.config['RATE_LIMIT_UPLOAD']):
        return jsonify({'error': 'Too many tracker updates. Wait a few minutes and try again.'}), 429
    uploaded = request.files.get('workbook')
    if not uploaded or not uploaded.filename:
        return jsonify({'error': 'Choose an Excel tracker to update.'}), 400

    try:
        validate_workbook_upload(
            uploaded,
            uploaded.filename,
            max_uncompressed_bytes=app.config['MAX_WORKBOOK_UNCOMPRESSED_BYTES'],
            max_members=app.config['MAX_WORKBOOK_ARCHIVE_MEMBERS'],
        )
        jobs = json.loads(request.form.get('jobs', '[]'))
    except json.JSONDecodeError:
        return jsonify({'error': 'The job results could not be read.'}), 400
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    if not isinstance(jobs, list) or not jobs:
        return jsonify({'error': 'Extract at least one job before updating a tracker.'}), 400
    max_jobs = app.config['MAX_EXPORT_JOBS']
    if len(jobs) > max_jobs:
        return jsonify({'error': f'A maximum of {max_jobs} jobs can be added at once.'}), 400

    try:
        duplicate_mode = request.form.get('duplicate_mode', 'skip')
        with tempfile.TemporaryDirectory(prefix='joblink-workbook-') as temp_dir:
            out_path, summary = append_jobs_to_workbook(
                uploaded,
                uploaded.filename,
                jobs,
                outdir=temp_dir,
                duplicate_mode=duplicate_mode,
            )
            workbook_bytes = Path(out_path).read_bytes()
            download_name = os.path.basename(out_path)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        app.logger.exception('Workbook append failed')
        return jsonify({'error': 'The server could not update this workbook.'}), 500

    suffix = Path(uploaded.filename).suffix.casefold()
    mimetype = (
        'application/vnd.ms-excel.sheet.macroEnabled.12'
        if suffix == '.xlsm'
        else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response = send_file(
        io.BytesIO(workbook_bytes),
        as_attachment=True,
        download_name=download_name,
        mimetype=mimetype,
    )
    response.headers['X-JobLink-Added'] = str(summary.get('added', 0))
    response.headers['X-JobLink-Skipped'] = str(summary.get('skipped', 0))
    response.headers['X-JobLink-Updated'] = str(summary.get('updated', 0))
    response.headers['X-JobLink-Sheet'] = str(summary.get('sheet', ''))
    return response

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False, threaded=True)
