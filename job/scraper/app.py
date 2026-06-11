from flask import Flask, request, jsonify, send_from_directory
import os
from scraper.scraper import parse_job_from_html
from scraper.browser_scraper_v2 import parse_job_with_browser
from export.exporter import export_jobs_to_xlsx

app = Flask(__name__)


def _merge_scrape_results(primary, fallback):
    merged = dict(primary or {})
    for key, value in (fallback or {}).items():
        if key == 'error':
            continue
        if value and not merged.get(key):
            merged[key] = value
    if merged.get('source') and not merged.get('job_link'):
        merged['job_link'] = merged['source']
    if merged.get('job_link') and not merged.get('source'):
        merged['source'] = merged['job_link']
    return merged

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/scrape', methods=['POST'])
def scrape():
    data = request.get_json() or {}
    url = data.get('url')
    if not url:
        return jsonify({'error': 'url required'}), 400
    
    # Try headless browser first (better for JS-heavy sites)
    result = parse_job_with_browser(url)
    
    # Fill any gaps with the faster requests parser.
    required = ['company', 'job_title', 'location']
    if 'error' in result or any(not result.get(field) for field in required):
        fallback = parse_job_from_html(url)
        result = _merge_scrape_results(result, fallback)
    
    return jsonify(result)

@app.route('/export', methods=['POST'])
def export():
    jobs = request.get_json() or []
    if not isinstance(jobs, list):
        return jsonify({'error': 'expected a list of job objects'}), 400
    out_path = export_jobs_to_xlsx(jobs)
    dirname = os.path.dirname(out_path)
    filename = os.path.basename(out_path)
    return send_from_directory(dirname, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
