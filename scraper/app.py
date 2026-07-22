import atexit
from functools import partial
from flask import Blueprint, Flask, current_app, request, jsonify, render_template, send_file
import hashlib
import hmac
import io
import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from werkzeug.middleware.proxy_fix import ProxyFix

from scraper.config import config_for_environment
from scraper.errors import register_error_handlers
from scraper.logging_config import configure_logging, register_request_logging
from scraper.runtime import (
    begin_runtime_shutdown,
    build_runtime,
    get_runtime,
    shutdown_runtime,
)
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
from scraper.job_queue import ScrapeCapacityFull
from scraper.job_routes import create_job_blueprint


web = Blueprint('web', __name__)


def create_app(environment=None, config_overrides=None):
    flask_app = Flask(__name__, template_folder='templates', static_folder='static')
    flask_app.config.from_object(config_for_environment(environment))
    if config_overrides:
        flask_app.config.update(config_overrides)
    _validate_production_config(flask_app)
    configure_logging(flask_app)

    if flask_app.config['TRUST_PROXY_HOPS']:
        trusted_hops = flask_app.config['TRUST_PROXY_HOPS']
        flask_app.wsgi_app = ProxyFix(
            flask_app.wsgi_app,
            x_for=trusted_hops,
            x_proto=trusted_hops,
            x_host=trusted_hops,
        )

    log_dir = Path(flask_app.config['LOG_DIR'])
    chromium_args = (
        ['--disable-dev-shm-usage']
        if flask_app.config['CHROMIUM_DISABLE_DEV_SHM_USAGE']
        else []
    )
    scrape = partial(
        _scrape_url,
        page_timeout_ms=flask_app.config['SCRAPE_PAGE_TIMEOUT_MS'],
        chromium_args=chromium_args,
        issue_log=log_dir / 'extraction_issues.jsonl',
        store_full_urls=flask_app.config['STORE_FULL_URLS'],
    )
    runtime = build_runtime(flask_app, scrape, chromium_args=chromium_args)
    flask_app.extensions['joblink_runtime'] = runtime

    flask_app.register_blueprint(web)
    flask_app.register_blueprint(create_job_blueprint(
        runtime.job_manager,
        max_links=flask_app.config['MAX_JOBS_PER_REQUEST'],
        rate_limited=_rate_limited,
        create_rate_limit=flask_app.config['RATE_LIMIT_JOB_CREATE'],
    ))
    register_request_logging(flask_app)
    register_error_handlers(flask_app)
    if flask_app.config['REGISTER_ATEXIT']:
        atexit.register(shutdown_runtime, flask_app, False)

    flask_app.logger.info(
        'application_started',
        extra={
            'event': 'application_started',
            'environment': flask_app.config['APP_ENV'],
            'browser_status': runtime.browser_status,
        },
    )
    return flask_app


def _validate_production_config(flask_app):
    production_secret = str(flask_app.config.get('SECRET_KEY') or '')
    if flask_app.config['IS_PRODUCTION'] and (
        len(production_secret) < 32
        or production_secret.casefold() in {
            'joblink-local-development-key', 'replace-me', 'change-me'
        }
    ):
        raise RuntimeError(
            'JOBLINK_SECRET_KEY must be a random value of at least 32 characters in production.'
        )

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
    runtime = get_runtime()
    client = request.remote_addr or 'unknown'
    now = time.time()
    cutoff = now - current_app.config['RATE_WINDOW_SECONDS']
    key = (scope, client)
    with runtime.request_history_lock:
        history = runtime.request_history[key]
        while history and history[0] < cutoff:
            history.popleft()
        if len(history) >= limit:
            return True
        history.append(now)

        if len(runtime.request_history) > 5000:
            stale_keys = [
                item for item, values in runtime.request_history.items()
                if not values or values[-1] < cutoff
            ]
            for stale_key in stale_keys:
                runtime.request_history.pop(stale_key, None)
    return False


def _scrape_url(
    url,
    *,
    page_timeout_ms=60000,
    chromium_args=None,
    issue_log=None,
    store_full_urls=False,
):
    if _is_monster_search_url(url):
        return _monster_guidance_result(url)

    result = {}
    terminal_error = False
    for attempt in range(2):
        result = parse_job_with_browser(
            url,
            timeout=page_timeout_ms,
            launch_args=chromium_args,
        )
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
    issues = _quality_issues(result)
    if 'job_search_page' in issues:
        for field in ('company', 'job_title', 'location', 'work_type', 'salary'):
            result[field] = 'n/a'
        result['error'] = 'This link opened a job search page instead of the original posting.'
        issues = sorted(set(_quality_issues(result) + ['job_search_page']))
    raw_error = result.get('error', '')
    if issues:
        _record_issue(
            url,
            result,
            issues,
            raw_error,
            issue_log=issue_log,
            store_full_urls=store_full_urls,
        )
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
        'error': "A Monster search page contains many jobs. Open the employer's own posting and use that link instead.",
        'review_issues': ['monster_search_page'],
        'review_notes': "Linc cannot turn a page full of Monster results into one accurate row. Use the employer's own job page instead.",
    }
    _annotate_result(result, url, result['review_issues'])
    return result




def _record_issue(
    url,
    result,
    issues,
    raw_error='',
    *,
    issue_log=None,
    store_full_urls=None,
):
    path = Path(issue_log) if issue_log else get_runtime().issue_log
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        **_private_url_record(url, store_full_urls=store_full_urls),
        'issues': issues,
        'result': {
            key: _bounded_log_value(result.get(key, ''))
            for key in ('company', 'job_title', 'location', 'work_type', 'salary', 'source')
        },
        'technical_error': str(raw_error)[:2000],
    }
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + '\n')


def _bounded_log_value(value, limit=500):
    return str(value or '')[:limit]


def _private_url_record(url, store_full_urls=None):
    normalized = str(url or '').strip()
    record = {
        'domain': urlparse(normalized).hostname or '',
        'url_hash': hashlib.sha256(normalized.encode('utf-8')).hexdigest() if normalized else '',
    }
    if store_full_urls is None:
        store_full_urls = current_app.config['STORE_FULL_URLS']
    if store_full_urls:
        record['url'] = normalized
    return record


def _issues_access_allowed():
    if not current_app.config['EXPOSE_ISSUES']:
        return False
    expected = current_app.config.get('ADMIN_TOKEN', '')
    supplied = request.headers.get('X-JobLink-Admin', '')
    if expected:
        return hmac.compare_digest(expected, supplied)
    return not current_app.config['IS_PRODUCTION'] and request.remote_addr in {'127.0.0.1', '::1'}


@web.route('/api/issues')
def issues():
    path = get_runtime().issue_log
    if not _issues_access_allowed():
        return jsonify({'error': 'Not found.'}), 404
    if not path.exists():
        return jsonify([])
    with path.open('r', encoding='utf-8') as handle:
        records = [json.loads(line) for line in handle if line.strip()]
    return jsonify(records[-100:])


@web.route('/api/report-issue', methods=['POST'])
def report_issue():
    runtime = get_runtime()
    if _rate_limited('report-issue', current_app.config['RATE_LIMIT_FEEDBACK']):
        return jsonify({'error': 'Too many rows were flagged at once. Wait a few minutes and try again.'}), 429
    payload = request.get_json(silent=True) or {}
    job = payload.get('job') if isinstance(payload.get('job'), dict) else {}
    url = str(job.get('job_link') or payload.get('url') or '').strip()
    if not url:
        return jsonify({'error': 'Choose a job row to flag.'}), 400

    runtime.user_report_log.parent.mkdir(parents=True, exist_ok=True)
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
    if not current_app.config['STORE_FULL_URLS']:
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
    with runtime.user_report_log.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + '\n')
    return jsonify({'status': 'saved'})


@web.route('/api/feedback', methods=['POST'])
def beta_feedback():
    runtime = get_runtime()
    if _rate_limited('feedback', current_app.config['RATE_LIMIT_FEEDBACK']):
        return jsonify({'error': 'Too many feedback notes were saved at once. Wait a few minutes and try again.'}), 429
    payload = request.get_json(silent=True) or {}
    message = str(payload.get('message') or '').strip()
    if not message:
        return jsonify({'error': 'Write a short feedback note first.'}), 400

    feedback_type = str(payload.get('type') or 'general').strip().lower()
    if feedback_type not in {'general', 'bug', 'idea', 'confusing'}:
        feedback_type = 'general'

    runtime.beta_feedback_log.parent.mkdir(parents=True, exist_ok=True)
    record = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'type': feedback_type,
        'message': message[:3000],
        'page': urlparse(str(payload.get('page') or '')).path[:200],
        'job_count': payload.get('job_count', 0),
        'version': 'Linc Beta v0.1.0',
    }
    with runtime.beta_feedback_log.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + '\n')
    return jsonify({'status': 'saved'})


def _friendly_error(error, url=''):
    low = str(error or '').lower()
    if 'monster.com' in urlparse(url or '').netloc.lower():
        return "Monster blocks reliable access. Open the employer's own job page from Monster and use that link instead."
    if 'browser runtime unavailable' in low:
        return 'Linc could not start its browser. Restart Linc and try again. If it continues, reinstall the app.'
    if any(marker in low for marker in ('http 404', 'http 410', 'unavailable', 'general careers page', 'job search page')):
        return 'This posting is unavailable or has expired.'
    if any(marker in low for marker in ('blocked automated access', 'access denied', 'captcha')):
        return 'The website blocked automated access. Open the job page yourself, then use Linc Capture.'
    if any(marker in low for marker in ('timeout', 'timed out')):
        return 'The website took too long to respond. Try this job again.'
    if any(marker in low for marker in ('http 403', 'http 429', 'access denied', 'captcha')):
        return 'The website blocked automated access. Open the job page yourself, then use Linc Capture.'
    if 'cannot navigate to invalid url' in low:
        return 'The job link is not a valid web address.'
    return 'Linc could not read this posting. Try again or check the link yourself.'


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


@web.route('/')
def index():
    return render_template('index.html')


@web.after_app_request
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
    if current_app.config['IS_PRODUCTION']:
        response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    return response


@web.route('/health')
def health():
    return jsonify({'status': 'ok', 'scraper': get_runtime().job_manager.stats()})


@web.route('/ready')
def ready():
    runtime = get_runtime()
    accepting = runtime.job_manager.is_accepting
    is_ready = accepting and runtime.browser_ready
    payload = {
        'status': 'ready' if is_ready else 'unavailable',
        'checks': {
            'queue': 'accepting' if accepting else 'shutting_down',
            'browser': runtime.browser_status,
        },
    }
    return jsonify(payload), 200 if is_ready else 503


@web.route('/api/capture-page', methods=['POST', 'OPTIONS'])
def capture_page():
    runtime = get_runtime()
    if not current_app.config['CAPTURE_ENABLED']:
        return _capture_response({
            'error': 'Browser capture is available only in the local Linc app.'
        }, 404)
    if request.method == 'OPTIONS':
        return _capture_response({'status': 'ok'})
    if _rate_limited('capture', current_app.config['RATE_LIMIT_CAPTURE']):
        return _capture_response({'error': 'Too many pages were captured at once. Wait a few minutes and try again.'}, 429)

    payload = request.get_json(silent=True) or request.form.to_dict()
    if not isinstance(payload, dict):
        return _capture_response({'error': 'Linc could not read that browser capture.'}, 400)

    if not _capture_payload_has_content(payload):
        return _capture_response({
            'error': 'The extension could not find the job details. Make sure the real posting is visible, then capture it again.',
        }, 400)

    job = _parse_captured_page(payload)
    runtime.captures.appendleft(job)
    return _capture_response({'job': job, 'count': len(runtime.captures)})


@web.route('/api/captures')
def captures():
    if not current_app.config['CAPTURE_ENABLED']:
        return jsonify({'error': 'Not found.'}), 404
    return jsonify({'jobs': list(get_runtime().captures)})


@web.route('/scrape', methods=['POST'])
def scrape():
    if _rate_limited('scrape', current_app.config['RATE_LIMIT_SCRAPE']):
        return jsonify({'error': 'Too many jobs were retried at once. Wait a few minutes and try again.'}), 429

    data = request.get_json() or {}
    url, validation_error = _validate_public_url(data.get('url'))
    if validation_error:
        return jsonify({'error': validation_error}), 400

    try:
        return jsonify(get_runtime().job_manager.run_sync(url))
    except ScrapeCapacityFull:
        return jsonify({'error': 'Linc is busy with another page. Wait for it to finish, then try again.'}), 503
    except Exception:
        current_app.logger.exception('Job scraping failed')
        return jsonify({'error': 'Linc could not read this job page.'}), 500


@web.route('/export', methods=['POST'])
def export():
    if _rate_limited('export', current_app.config['RATE_LIMIT_EXPORT']):
        return jsonify({'error': 'Too many Excel files were requested at once. Wait a few minutes and try again.'}), 429
    jobs = request.get_json() or []
    if not isinstance(jobs, list) or not jobs:
        return jsonify({'error': 'Add at least one job before exporting.'}), 400
    max_jobs = current_app.config['MAX_EXPORT_JOBS']
    if len(jobs) > max_jobs:
        return jsonify({'error': f'Export up to {max_jobs} jobs at a time.'}), 400
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


@web.route('/append-workbook', methods=['POST'])
def append_workbook():
    if _rate_limited('append-workbook', current_app.config['RATE_LIMIT_UPLOAD']):
        return jsonify({'error': 'Too many tracker updates were requested at once. Wait a few minutes and try again.'}), 429
    uploaded = request.files.get('workbook')
    if not uploaded or not uploaded.filename:
        return jsonify({'error': 'Choose an Excel tracker to update.'}), 400

    try:
        validate_workbook_upload(
            uploaded,
            uploaded.filename,
            max_uncompressed_bytes=current_app.config['MAX_WORKBOOK_UNCOMPRESSED_BYTES'],
            max_members=current_app.config['MAX_WORKBOOK_ARCHIVE_MEMBERS'],
        )
        jobs = json.loads(request.form.get('jobs', '[]'))
    except json.JSONDecodeError:
        return jsonify({'error': 'Linc could not read the rows you selected.'}), 400
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    if not isinstance(jobs, list) or not jobs:
        return jsonify({'error': 'Add at least one finished job before updating a tracker.'}), 400
    max_jobs = current_app.config['MAX_EXPORT_JOBS']
    if len(jobs) > max_jobs:
        return jsonify({'error': f'Add up to {max_jobs} jobs at a time.'}), 400

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
        current_app.logger.exception('Workbook append failed')
        return jsonify({'error': 'Linc could not update this workbook.'}), 500

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


def begin_shutdown(flask_app):
    begin_runtime_shutdown(flask_app)


def shutdown_app(flask_app, wait=False):
    shutdown_runtime(flask_app, wait=wait)


app = create_app()


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False, threaded=True)
