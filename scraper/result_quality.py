"""Result normalization, review reasons, and confidence metadata."""

import re

from scraper.browser_scraper_v2 import _detect_platform


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


def _missing(value):
    return str(value or '').strip().lower() in {'', 'n/a', 'none', 'null'}


def _looks_like_job_search_title(value):
    title = re.sub(r'\s+', ' ', str(value or '')).strip()
    return bool(re.match(
        r'^\d[\d,]*\+?\s+.{2,120}\s+jobs?\s+in\s+.{2,120}$',
        title,
        flags=re.I,
    ))


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
    if _looks_like_job_search_title(title):
        issues.append('job_search_page')
    comparable_company = re.sub(r'\W+', '', company.lower())
    comparable_title = re.sub(r'\W+', '', title.lower())
    if (
        not _missing(company)
        and not _missing(title)
        and comparable_company == comparable_title
    ):
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
        'job_search_page': 'The posting redirected to a job search page, so its fields cannot be trusted.',
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
        'job_search_page': ('Posting unavailable', 'Link', 'Open the link and enter the original job details manually if the posting is still visible.'),
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
        'job_search_page': 42,
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
