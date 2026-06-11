import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

JOB_FIELDS = [
    'company', 'job_title', 'location', 'salary', 'description', 'source', 'skills'
]


def _normalize_text(value):
    if not value:
        return ''
    return ' '.join(value.split())


def _get_meta_content(soup, attr_name, keys):
    for key in keys:
        if attr_name == 'property':
            tag = soup.find('meta', property=key)
        else:
            tag = soup.find('meta', attrs={attr_name: key})
        if tag and tag.get('content'):
            return _normalize_text(tag['content'])
    return ''


def _parse_jsonld(soup):
    def walk(value):
        if isinstance(value, list):
            for item in value:
                found = walk(item)
                if found:
                    return found
        elif isinstance(value, dict):
            type_value = value.get('@type', '')
            if isinstance(type_value, list):
                type_value = ' '.join(str(t) for t in type_value)
            if str(type_value).lower().replace(' ', '') in ('jobposting', 'job'):
                return value
            for key in ('jobPosting', 'job_posting'):
                if isinstance(value.get(key), dict):
                    return value[key]
            for key in ('@graph', 'mainEntity', 'hasPart'):
                found = walk(value.get(key))
                if found:
                    return found
        return {}

    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            payload = json.loads(raw.strip())
        except json.JSONDecodeError:
            try:
                payload = json.loads(raw.strip().rstrip(';'))
            except json.JSONDecodeError:
                continue
        found = walk(payload)
        if found:
            return found
        if isinstance(payload, dict):
            return payload
    return {}


def _jsonld_text(value):
    if isinstance(value, dict):
        return _normalize_text(value.get('name') or value.get('value') or value.get('@value') or '')
    if isinstance(value, list):
        return _normalize_text(', '.join(_jsonld_text(item) for item in value if _jsonld_text(item)))
    return _normalize_text(str(value or ''))


def _extract_employment_type_from_jsonld(item):
    location_type = _jsonld_text(item.get('jobLocationType'))
    if location_type.upper() == 'TELECOMMUTE':
        return 'Remote'
    employment = _jsonld_text(item.get('employmentType') or '')
    employment_map = {
        'FULL_TIME': 'Full-time',
        'PART_TIME': 'Part-time',
        'CONTRACTOR': 'Contract',
        'TEMPORARY': 'Temporary',
        'INTERN': 'Internship',
    }
    return employment_map.get(employment.upper(), employment)


def _extract_description_from_jsonld(item):
    descr = item.get('description') or item.get('responsibilities') or item.get('qualifications') or ''
    if isinstance(descr, list):
        descr = ' '.join(_jsonld_text(part) for part in descr)
    return _normalize_text(BeautifulSoup(str(descr), 'html.parser').get_text(separator=' ', strip=True))


def _parse_salary_value(value):
    if isinstance(value, dict):
        min_value = value.get('minValue') or value.get('min_value')
        max_value = value.get('maxValue') or value.get('max_value')
        unit = value.get('unitText') or value.get('unit_text') or ''
        if min_value and max_value:
            return _normalize_text(f"{min_value} - {max_value} {unit}")
        if value.get('value'):
            return _normalize_text(f"{value.get('value')} {unit}")
        return _jsonld_text(value)
    return _jsonld_text(value)


def _extract_jsonld_job_fields(item):
    if not item:
        return {}
    return {
        'job_title': _clean_linkedin_title(_jsonld_text(item.get('title') or item.get('name'))),
        'company': _extract_company_from_jsonld(item),
        'location': _extract_location_from_jsonld(item),
        'salary': _extract_salary_from_jsonld(item),
        'description': _extract_description_from_jsonld(item),
        'work_type': _extract_employment_type_from_jsonld(item),
        'skills': _extract_skills(item, _extract_description_from_jsonld(item)),
    }


def _parse_next_data(soup):
    script = soup.select_one('script#__NEXT_DATA__')
    if not script:
        return {}
    try:
        return json.loads(script.string or script.get_text())
    except json.JSONDecodeError:
        return {}


def _flatten_dict_strings(value, keys=None):
    if keys is None:
        keys = {}
    if isinstance(value, dict):
        for key, item in value.items():
            low = str(key).lower()
            if isinstance(item, (str, int, float)) and item:
                keys.setdefault(low, []).append(_normalize_text(str(item)))
            else:
                _flatten_dict_strings(item, keys)
    elif isinstance(value, list):
        for item in value:
            _flatten_dict_strings(item, keys)
    return keys


def _extract_location_from_jsonld(item):
    location = ''
    if not item:
        return location
    job_location = item.get('jobLocation', item)
    if isinstance(job_location, list):
        locations = []
        for place in job_location:
            found = _extract_location_from_jsonld(place)
            if found:
                locations.append(found)
        return _normalize_text(', '.join(locations))
    if isinstance(job_location, dict):
        if 'address' in job_location and isinstance(job_location['address'], dict):
            addr = job_location['address']
            location = ', '.join([_jsonld_text(addr.get(k, '')).strip() for k in ('addressLocality', 'addressRegion', 'addressCountry') if addr.get(k)])
        elif job_location.get('address'):
            location = _jsonld_text(job_location['address'])
        elif job_location.get('name'):
            location = _jsonld_text(job_location['name'])
    elif job_location:
        location = _jsonld_text(job_location)
    return _normalize_text(location)


def _extract_salary_from_jsonld(item):
    salary = ''
    if not item:
        return salary
    base_salary = item.get('baseSalary') or item.get('salary')
    if isinstance(base_salary, dict):
        value = base_salary.get('value') or base_salary
        salary = _parse_salary_value(value)
        currency = base_salary.get('currency') or ''
        if currency and salary and currency not in salary:
            salary = f"{currency} {salary}"
        elif not salary:
            salary = currency
    elif isinstance(base_salary, str):
        salary = base_salary
    return _normalize_text(str(salary))


def _extract_company_from_jsonld(item):
    if not item:
        return ''
    company = item.get('hiringOrganization') or item.get('employer')
    if isinstance(company, dict):
        return _normalize_text(company.get('name', ''))
    return _normalize_text(str(company))


def _extract_skills(item, descr):
    skills = []
    skill_data = item.get('skills') or item.get('qualifications')
    if isinstance(skill_data, list):
        skills.extend([_normalize_text(s) for s in skill_data if isinstance(s, str)])
    elif isinstance(skill_data, str):
        skills.append(_normalize_text(skill_data))
    if descr:
        common_skills = ['python', 'javascript', 'react', 'aws', 'docker', 'sql', 'excel']
        dlow = descr.lower()
        for sk in common_skills:
            if sk in dlow and sk not in skills:
                skills.append(sk)
    return _normalize_text(', '.join(skills))


def _clean_linkedin_title(title):
    if not title:
        return ''
    title = re.sub(r'\s*\|\s*LinkedIn$', '', title, flags=re.IGNORECASE)
    return _normalize_text(title)


def _is_job_link(candidate):
    if not candidate or candidate.startswith('#') or candidate.lower().startswith('mailto:'):
        return False
    return bool(re.search(r'\b(job|jobs|careers|gh_jid|opening|position|vacancy)\b', candidate, flags=re.IGNORECASE))


def _discover_job_url(url, soup):
    canonical = soup.find('link', rel='canonical')
    if canonical and canonical.get('href'):
        canonical_url = urljoin(url, canonical['href'])
        if canonical_url != url:
            return canonical_url

    candidates = []
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        if not _is_job_link(href):
            continue
        absolute = urljoin(url, href)
        if absolute == url:
            continue
        candidates.append(absolute)

    if candidates:
        return candidates[0]
    return None


def parse_job_from_html(url):
    """Fetch URL and attempt to extract job fields using metadata and heuristics."""
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "JobTrackerBot/1.0"})
    except Exception as e:
        return {'error': str(e)}
    if r.status_code != 200:
        return {'error': f'HTTP {r.status_code}'}
    soup = BeautifulSoup(r.text, 'html.parser')

    fallback_url = _discover_job_url(url, soup)
    if fallback_url and fallback_url != url:
        try:
            r = requests.get(fallback_url, timeout=10, headers={"User-Agent": "JobTrackerBot/1.0"})
            if r.status_code == 200:
                url = fallback_url
                soup = BeautifulSoup(r.text, 'html.parser')
        except Exception:
            pass

    data = {}

    jsonld = _parse_jsonld(soup)
    if jsonld:
        data['job_title'] = _clean_linkedin_title(_normalize_text(jsonld.get('title') or jsonld.get('name') or ''))
        data['company'] = _extract_company_from_jsonld(jsonld)
        data['location'] = _extract_location_from_jsonld(jsonld)
        data['salary'] = _extract_salary_from_jsonld(jsonld)
        data['description'] = _normalize_text(jsonld.get('description') or '')
        data['skills'] = _extract_skills(jsonld, data['description'])
    else:
        data['job_title'] = ''
        data['company'] = ''
        data['location'] = ''
        data['salary'] = ''
        data['description'] = ''
        data['skills'] = ''

    if not data.get('job_title'):
        data['job_title'] = _clean_linkedin_title(_get_meta_content(soup, 'property', ['og:title', 'twitter:title']) or _get_meta_content(soup, 'name', ['title']))
    if not data.get('description'):
        data['description'] = _get_meta_content(soup, 'property', ['og:description', 'twitter:description'])
    if not data.get('company'):
        company_selectors = [
            '.company', '.jobcompany', '[itemprop=hiringOrganization]', '.company-name',
            '.topcard__org-name-link', '.artdeco-entity-lockup__subtitle', '.top-card-layout__company-url',
            '.jobs-unified-top-card__company-name'
        ]
        for sel in company_selectors:
            found = soup.select_one(sel)
            if found and found.get_text(strip=True):
                data['company'] = _normalize_text(found.get_text(strip=True))
                break
    if not data.get('location'):
        location_selectors = [
            '.location', '[itemprop=jobLocation]', '.job-location', '.topcard__flavor--bullet',
            '.jobs-unified-top-card__bullet', '.jobs-unified-top-card__location'
        ]
        for sel in location_selectors:
            found = soup.select_one(sel)
            if found and found.get_text(strip=True):
                data['location'] = _normalize_text(found.get_text(strip=True))
                break
    if not data.get('salary'):
        salary_selectors = ['.salary', '.compensation', '[data-test-salary]', '.salaryText']
        for sel in salary_selectors:
            found = soup.select_one(sel)
            if found and found.get_text(strip=True):
                data['salary'] = _normalize_text(found.get_text(strip=True))
                break
    if not data.get('description'):
        desc_container = (soup.find('div', {'class': 'job-description'}) or
                          soup.find('div', {'id': 'job-description'}) or
                          soup.find('div', {'class': 'description'}) or
                          soup.find('section', {'class': 'description'}))
        if desc_container:
            data['description'] = _normalize_text(desc_container.get_text(separator=' ', strip=True))
        else:
            p = None
            for pp in soup.find_all('p'):
                if len(pp.get_text(strip=True)) > 200:
                    p = pp
                    break
            data['description'] = _normalize_text(p.get_text(separator=' ', strip=True)) if p else ''
    if not data.get('skills'):
        data['skills'] = _extract_skills({}, data.get('description', ''))

    data['source'] = url
    return data


def scrape_jobboard_api_example(api_name, identifier, api_key=None):
    """Placeholder for job-board API integration.
    Implement LinkedIn/Indeed/other API client code here.
    """
    raise NotImplementedError('Add job-board API integration for ' + api_name)
