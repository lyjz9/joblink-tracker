from collections import defaultdict, deque
from flask import Flask, request, jsonify, render_template, send_file
import hashlib
import hmac
import io
import json
import os
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from werkzeug.middleware.proxy_fix import ProxyFix

from scraper.config import JobLinkConfig
from scraper.security import validate_public_url, validate_workbook_upload

from scraper.scraper import parse_job_from_html
from scraper.browser_scraper_v2 import (
    parse_job_with_browser,
    _detect_platform,
    _source_label,
)
from export.exporter import export_jobs_to_xlsx
from export.workbook_appender import append_jobs_to_workbook
from scraper.result_quality import (
    _annotate_result,
    _missing,
    _public_scrape_result,
    _quality_issues,
    _review_notes,
)
from scraper.capture_parser import _capture_payload_has_content, _parse_captured_page
from scraper.job_queue import BackgroundJobManager, ScrapeCapacityFull
from scraper.job_routes import create_job_blueprint

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


job_manager = BackgroundJobManager(
    _scrape_url,
    max_workers=app.config['SCRAPE_WORKERS'],
    max_pending_jobs=app.config['MAX_PENDING_JOBS'],
    ttl_seconds=app.config['JOB_TTL_SECONDS'],
    sync_wait_seconds=app.config['SCRAPE_CAPACITY_WAIT_SECONDS'],
)
app.register_blueprint(create_job_blueprint(
    job_manager,
    max_links=app.config['MAX_JOBS_PER_REQUEST'],
    rate_limited=_rate_limited,
    create_rate_limit=app.config['RATE_LIMIT_JOB_CREATE'],
))


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
    return jsonify({'status': 'ok', 'scraper': job_manager.stats()})


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
        return jsonify(job_manager.run_sync(url))
    except ScrapeCapacityFull:
        return jsonify({'error': 'The scraper is busy. Wait for a running job to finish.'}), 503
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
