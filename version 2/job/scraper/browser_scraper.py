import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse
from .scraper import (
    _normalize_text, _parse_jsonld, _extract_location_from_jsonld,
    _extract_salary_from_jsonld, _extract_company_from_jsonld,
    _extract_skills, _clean_linkedin_title, _get_meta_content
)


def _detect_job_board(url):
    """Detect which job board the URL belongs to."""
    domain = urlparse(url).netloc.lower()
    
    if 'linkedin.com' in domain:
        return 'linkedin'
    elif 'indeed.com' in domain:
        return 'indeed'
    elif 'glassdoor.com' in domain:
        return 'glassdoor'
    elif 'ziprecruiter.com' in domain:
        return 'ziprecruiter'
    elif 'greenhouse.io' in domain:
        return 'greenhouse'
    elif 'oracle.com' in domain or 'oraclecloud.com' in domain:
        return 'oracle'
    else:
        return 'company_website'


def _extract_work_type(text):
    """Detect work type from job text."""
    if not text:
        return ''
    text_lower = text.lower()
    if 'remote' in text_lower:
        return 'Remote'
    elif 'hybrid' in text_lower:
        return 'Hybrid'
    elif 'onsite' in text_lower or 'on-site' in text_lower or 'in-office' in text_lower:
        return 'On-site'
    elif 'full-time' in text_lower or 'fulltime' in text_lower:
        return 'On-site'
    return ''


def _extract_location_from_text(text):
    """Extract location from combined text like 'Job Title, City, State'."""
    if not text:
        return ''
    # Match patterns like "New York, NY" or "San Francisco, CA"
    match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s+([A-Z]{2})', text)
    if match:
        return f"{match.group(1)}, {match.group(2)}"
    return ''


def _extract_job_data_from_soup(soup, url, board_type):
    """Extract job data from HTML based on board type."""
    from datetime import datetime
    
    data = {
        'date_applied': datetime.now().strftime('%m/%d/%Y'),
        'company': '',
        'job_title': '',
        'job_link': url,
        'status': '',
        'location': '',
        'work_type': '',
        'salary': '',
        'follow_up': ''
    }
    
    # Try JSON-LD first (works across most sites)
    jsonld = _parse_jsonld(soup)
    if jsonld:
        data['job_title'] = _clean_linkedin_title(_normalize_text(jsonld.get('title') or jsonld.get('name') or ''))
        data['company'] = _extract_company_from_jsonld(jsonld)
        data['location'] = _extract_location_from_jsonld(jsonld)
        data['salary'] = _extract_salary_from_jsonld(jsonld)
        description = _normalize_text(jsonld.get('description') or '')
        data['work_type'] = _extract_work_type(description)
        if all([data['job_title'], data['company'], data['location']]):
            return data

    # Board-specific selectors
    selectors = {
        'linkedin': {
            'title': ['.top-card-layout__title', '.jobs-details-top-card__job-title', '.js-job-details-top-card__job-title', 'h1'],
            'company': ['.top-card-layout__company-name', '.jobs-details-top-card__company-name', '.js-job-details-top-card__company-name', '[data-testid="top-card-company-name"]'],
            'location': ['.topcard__flavor', '.jobs-details-top-card__location', '.js-job-details-top-card__location'],
            'description': ['.show-more-less-html__markup', '.description__text', '.js-job-details-module__content']
        },
        'indeed': {
            'title': ['h1[class*="jobTitle"]', '.jobsearch-JobTitle', 'h1'],
            'company': ['.css-1p0sjhy', '.jobsearch-InlineCompanyRating-companyHeader', '[data-company-name]'],
            'location': ['.jobsearch-JobMetadataHeader-location', '[data-testid="jobsearch-JobMetadataHeader-location"]'],
            'salary': ['[data-testid*="salary"]', '.salary-snippet'],
            'description': ['#jobDescriptionText', '.jobsearch-jobDescriptionText', '[id*="Description"]']
        },
        'glassdoor': {
            'title': ['.jobTitle', 'h1.jobTitle', 'h1'],
            'company': ['.employerName', '.css-m5e8em'],
            'location': ['.jobLocation', '.css-56kyx5'],
            'salary': ['.salaryEstimate', '.css-16x1e84'],
            'description': ['.jobDescription', '.description', '.css-1b3cque']
        },
        'greenhouse': {
            'title': ['h2.app-title', '.opening__title', '[data-qa="job-title"]', '.job__title .section-header', 'h1', 'h2'],
            'company': ['.company-name', '[data-qa="company"]', '.job__header'],
            'location': ['.job__title', '[data-qa="location"]', '.location', 'span.location'],
            'salary': ['[data-qa="salary"]', '.salary', '[data-qa="compensation"]', '.compensation'],
            'description': ['[data-qa="job-description"]', '.opening__description', '.job-content', '#content', '.description']
        },
        'ziprecruiter': {
            'title': ['h1.job_title', 'h1'],
            'company': ['.company_name', '[itemprop="hiringOrganization"]'],
            'location': ['.job_location', '[itemprop="jobLocation"]'],
            'salary': ['.salary_range', '[data-salary]'],
            'description': ['.job_description', '.description']
        },
        'oracle': {
            'title': ['h1', '[data-qa="job-title"]'],
            'company': ['.company-name', 'a[data-qa="company"]'],
            'location': ['[data-qa="location"]', '.location'],
            'salary': ['[data-qa="salary"]', '.salary'],
            'description': ['.job-description', '[data-qa="description"]']
        },
        'company_website': {
            'title': ['h1', 'h2', '[data-qa="job-title"]', '.job-title', '.job__title'],
            'company': ['[data-qa="company"]', '.company', '.company-name', '[itemprop="hiringOrganization"]'],
            'location': ['[data-qa="location"]', '.location', '.job-location', '[itemprop="jobLocation"]'],
            'salary': ['[data-qa="salary"]', '.salary', '.compensation', '[itemprop="baseSalary"]'],
            'description': ['[data-qa="job-description"]', '.job-description', '.description', '.content', 'article']
        }
    }

    board_selectors = selectors.get(board_type, {})

    # Extract title
    if not data['job_title']:
        for sel in board_selectors.get('title', []):
            elem = soup.select_one(sel)
            if elem and elem.get_text(strip=True):
                data['job_title'] = _normalize_text(elem.get_text(strip=True))
                break
        if not data['job_title']:
            data['job_title'] = _clean_linkedin_title(_get_meta_content(soup, 'property', ['og:title', 'twitter:title']))

    # Extract company from domain name (for company websites, NOT for Greenhouse/job boards)
    if not data['company'] and board_type == 'company_website':
        # Check if this is a Greenhouse job (has greenhouse in the domain)
        if 'greenhouse.io' not in url.lower():
            # Try from URL parameters first
            match = re.search(r'for=([^&]+)', url)
            if match:
                company_slug = match.group(1)
                data['company'] = company_slug.replace('-', ' ').replace('_', ' ').title()
            else:
                # Extract from domain (e.g., charliehealth.com -> Charlie Health)
                domain = urlparse(url).netloc.lower()
                domain = domain.replace('www.', '').replace('.com', '').replace('.io', '')
                if domain and domain not in ['greenhouse', 'careers']:
                    # Try to split camelCase or just title case it
                    spaced = re.sub(r'([a-z])([A-Z])', r'\1 \2', domain.replace('-', ' '))
                    data['company'] = spaced.title()
    
    # Extract company (general selectors for job boards)
    if not data['company']:
        for sel in board_selectors.get('company', []):
            elem = soup.select_one(sel)
            if elem:
                text = _normalize_text(elem.get_text(strip=True))
                if text and len(text) < 150:  # Avoid long text blocks
                    data['company'] = text
                    break
        
        # Fallback for LinkedIn: search for company in page text (often in referral section)
        if not data['company'] and board_type == 'linkedin':
            # Look for pattern "Company Name (TICKER)" in the page
            all_text = soup.get_text()
            match = re.search(r'([A-Z][a-zA-Z\s&\.]+\s+(?:Inc|LLC|Ltd|Corp|Company|Group|Bank|Holdings))\s*\([A-Z]+\)', all_text)
            if match:
                data['company'] = _normalize_text(match.group(1))

    # Extract location
    if not data['location']:
        for sel in board_selectors.get('location', []):
            elem = soup.select_one(sel)
            if elem:
                text = elem.get_text(strip=True)
                # For job__title, extract location from combined text
                if 'job__title' in (elem.get('class', []) or []):
                    # Extract the location part (e.g., "New York, NY" from "Job TitleNew York, NY")
                    extracted_loc = _extract_location_from_text(text)
                    if extracted_loc:
                        data['location'] = extracted_loc
                        break
                elif text and len(text) < 100:
                    data['location'] = _normalize_text(text)
                    break
        
        # If not found, search all text for location pattern
        if not data['location']:
            all_text = soup.get_text()
            extracted_loc = _extract_location_from_text(all_text)
            if extracted_loc:
                data['location'] = extracted_loc

    # Extract salary (pattern matching only - selectors often give just "USD")
    # Skip selector-based extraction to avoid matching just "USD"
    if not data['salary']:
        all_text = soup.get_text()
        # Look for salary ranges - order matters! Most specific first
        patterns = [
            r'\$[\d,]+ - \$[\d,]+',      # $40,000 - $50,000
            r'\$[\d,]+ and \$[\d,]+',    # $40,000 and $50,000
            r'\$\d+[kK] - \$\d+[kK]',    # $40k - $50k
            r'[\d,]+ - [\d,]+ USD',      # 40,000 - 50,000 USD
            r'[\d,]+ - [\d,]+ a year',   # 40,000 - 50,000 a year
            r'From \$[\d,]+',            # From $40,000
        ]
        
        for pattern in patterns:
            salary_match = re.search(pattern, all_text, re.IGNORECASE)
            if salary_match:
                data['salary'] = salary_match.group(0).strip()
                break

    # Extract description (for work type detection)
    description = ''
    for sel in board_selectors.get('description', []):
        elem = soup.select_one(sel)
        if elem and elem.get_text(strip=True):
            text = elem.get_text(separator=' ', strip=True)
            if len(text) > 100:
                description = _normalize_text(text)
                break

    # Detect work type from full page text
    if not data['work_type']:
        all_text = soup.get_text().lower()
        if 'remote' in all_text:
            data['work_type'] = 'Remote'
        elif 'hybrid' in all_text:
            data['work_type'] = 'Hybrid'
        elif 'on-site' in all_text or 'onsite' in all_text or 'in-office' in all_text or 'in person' in all_text:
            data['work_type'] = 'On-site'
        elif 'full-time' in all_text or 'fulltime' in all_text:
            data['work_type'] = 'On-site'

    return data


async def scrape_job_with_browser(url, timeout=60000):
    """
    Scrape job listing using headless browser (Playwright).
    Handles JavaScript-heavy sites and multiple job boards.
    """
    board_type = _detect_job_board(url)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        try:
            # Use domcontentloaded instead of networkidle for faster loading
            await page.goto(url, wait_until='domcontentloaded', timeout=timeout)
            
            # Check for Greenhouse iframe
            iframe_src = await page.evaluate("""
                () => {
                    const iframe = document.querySelector('iframe#grnhse_iframe');
                    return iframe ? iframe.src : null;
                }
            """)
            
            if iframe_src:
                # Navigate to the iframe content directly
                await page.goto(iframe_src, wait_until='domcontentloaded', timeout=timeout)
            
            # Wait for job content
            load_selectors = [
                '[data-qa="job-title"]',
                '.opening__title',
                'h2.app-title',
                '.description'
            ]
            
            for selector in load_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=3000)
                    break
                except:
                    continue
            
            # Extra wait for dynamic content
            await page.wait_for_timeout(4000)
            
            # Try scrolling to trigger lazy loading
            await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)
            
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            data = _extract_job_data_from_soup(soup, url, board_type)
            return data
            
        except Exception as e:
            return {'error': str(e), 'job_link': url}
        finally:
            await context.close()
            await browser.close()


def parse_job_with_browser(url):
    """Synchronous wrapper for async browser scraper."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(scrape_job_with_browser(url))
