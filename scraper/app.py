from collections import defaultdict, deque
from flask import Flask, request, jsonify, render_template, send_file
import ipaddress
import json
import os
import re
import socket
import time
from datetime import datetime
from urllib.parse import urlparse

from scraper.scraper import parse_job_from_html
from scraper.browser_scraper_v2 import parse_job_with_browser, _detect_platform, _source_label
from export.exporter import export_jobs_to_xlsx
from export.workbook_appender import append_jobs_to_workbook

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 12 * 1024 * 1024

RATE_LIMIT = 30
RATE_WINDOW_SECONDS = 10 * 60
request_history = defaultdict(deque)
ISSUE_LOG = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'extraction_issues.jsonl')


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
    match = re.search(r'https?://[^\s<>"\']+', str(url or ''), flags=re.I)
    if match:
        url = match.group(0).rstrip('.,;:!)]}')
    try:
        parsed = urlparse(str(url or '').strip())
    except ValueError:
        return None, 'Enter a valid job posting URL.'

    if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
        return None, 'Only http and https job links are supported.'
    if parsed.username or parsed.password:
        return None, 'Links containing usernames or passwords are not supported.'

    host = parsed.hostname.lower().rstrip('.')
    if host == 'localhost' or host.endswith('.local'):
        return None, 'Local and private network links are not allowed.'

    try:
        default_port = 443 if parsed.scheme == 'https' else 80
        addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or default_port)}
    except socket.gaierror:
        return None, 'The website address could not be found.'

    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            return None, 'Local and private network links are not allowed.'
    return parsed.geturl(), None


def _rate_limited(client):
    now = time.time()
    history = request_history[client]
    while history and history[0] < now - RATE_WINDOW_SECONDS:
        history.popleft()
    if len(history) >= RATE_LIMIT:
        return True
    history.append(now)
    return False


def _scrape_url(url):
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
        result['error'] = _friendly_error(raw_error)
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
        'useparallel',
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
    }
    notes = [labels.get(issue, issue.replace('_', ' ')) for issue in issues]
    return ' '.join(notes)


def _record_issue(url, result, issues, raw_error=''):
    os.makedirs(os.path.dirname(ISSUE_LOG), exist_ok=True)
    record = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'domain': urlparse(url).hostname or '',
        'url': url,
        'issues': issues,
        'result': {key: result.get(key, '') for key in ('company', 'job_title', 'location', 'work_type', 'salary', 'source')},
        'technical_error': str(raw_error)[:2000],
    }
    with open(ISSUE_LOG, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + '\n')


@app.route('/api/issues')
def issues():
    if not os.path.exists(ISSUE_LOG):
        return jsonify([])
    with open(ISSUE_LOG, 'r', encoding='utf-8') as handle:
        records = [json.loads(line) for line in handle if line.strip()]
    return jsonify(records[-100:])


def _friendly_error(error):
    low = str(error or '').lower()
    if any(marker in low for marker in ('http 404', 'http 410', 'unavailable', 'general careers page')):
        return 'This posting is unavailable or has expired.'
    if any(marker in low for marker in ('blocked automated access', 'access denied', 'captcha')):
        return 'The website blocked automated access to this posting.'
    if any(marker in low for marker in ('timeout', 'timed out')):
        return 'The website took too long to respond. Retry this job.'
    if any(marker in low for marker in ('http 403', 'http 429', 'access denied', 'captcha')):
        return 'The website blocked automated access to this posting.'
    if 'cannot navigate to invalid url' in low:
        return 'The job link is not a valid web address.'
    return 'The scraper could not read this posting. Retry it or review the link.'


def _public_scrape_result(result):
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


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/scrape', methods=['POST'])
def scrape():
    client = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()
    if _rate_limited(client):
        return jsonify({'error': 'Too many requests. Wait a few minutes and try again.'}), 429

    data = request.get_json() or {}
    url, validation_error = _validate_public_url(data.get('url'))
    if validation_error:
        return jsonify({'error': validation_error}), 400

    try:
        return jsonify(_scrape_url(url))
    except Exception as exc:
        app.logger.exception('Job scraping failed')
        return jsonify({'error': f'Could not process this job page: {exc}'}), 500

@app.route('/export', methods=['POST'])
def export():
    jobs = request.get_json() or []
    if not isinstance(jobs, list) or not jobs:
        return jsonify({'error': 'Add at least one job before exporting.'}), 400
    if len(jobs) > 100:
        return jsonify({'error': 'A maximum of 100 jobs can be exported at once.'}), 400
    out_path = export_jobs_to_xlsx(jobs)
    return send_file(
        os.path.abspath(out_path),
        as_attachment=True,
        download_name=os.path.basename(out_path),
    )


@app.route('/append-workbook', methods=['POST'])
def append_workbook():
    uploaded = request.files.get('workbook')
    if not uploaded or not uploaded.filename:
        return jsonify({'error': 'Choose an Excel tracker to update.'}), 400

    try:
        jobs = json.loads(request.form.get('jobs', '[]'))
    except json.JSONDecodeError:
        return jsonify({'error': 'The job results could not be read.'}), 400

    if not isinstance(jobs, list) or not jobs:
        return jsonify({'error': 'Extract at least one job before updating a tracker.'}), 400
    if len(jobs) > 100:
        return jsonify({'error': 'A maximum of 100 jobs can be added at once.'}), 400

    try:
        out_path, summary = append_jobs_to_workbook(uploaded, uploaded.filename, jobs)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        app.logger.exception('Workbook append failed')
        return jsonify({'error': f'Could not update this workbook: {exc}'}), 500

    response = send_file(
        os.path.abspath(out_path),
        as_attachment=True,
        download_name=os.path.basename(out_path),
    )
    response.headers['X-JobLink-Added'] = str(summary.get('added', 0))
    response.headers['X-JobLink-Skipped'] = str(summary.get('skipped', 0))
    response.headers['X-JobLink-Sheet'] = str(summary.get('sheet', ''))
    return response

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False, threaded=True)
