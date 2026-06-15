"""Debug ZipRecruiter, NACCHO, and FDM extraction."""
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def debug_page(url, name):
    print(f"\n{'='*80}")
    print(f"DEBUGGING: {name}")
    print(f"URL: {url[:80]}...")
    print(f"{'='*80}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(5000)
        
        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text()
        
        print(f"Page text length: {len(text)}")
        print(f"\n=== First 1500 chars ===")
        print(text[:1500])
        
        await browser.close()

urls = [
    ("ZipRecruiter", "https://www.ziprecruiter.com/jobseeker/home?lk=1ucHOHkTVPh6x6h8CLuzfg&jk=eyJsaXN0aW5nS2V5IjoiMXVjSE9Ia1RWUGg2eDZoOENMdXpmZyIsIm1hdGNoSWQiOiIwMTllOGE0OS00NDAzLTc5ZWUtYjZiMC0yZjc0NWU4NGZiNjMiLCJiaWRUcmFja2luZ0RhdGEiOiJBQUd3bW9zUHdEOU0xUFEyTkRtMk9zQXgtNHR6VkFqRmVyOXZFMUlvbDlEVDZZajVRZENxdnA1V3plWjJjeWxlaDFZbGpUWFppaFY2bFFuY1U1MCIsInNvdXJjZVBsYWNlbWVudElkIjo4Nzc0OH0%3D"),
    ("NACCHO", "https://careers.naccho.org/job/merchandising-internship-summer-2026-new-york-ny-8077bfe96651d4933b5f0c542029a0d1b?utm_campaign=google_jobs_apply&utm_source=google_jobs_apply&utm_medium=organic"),
    ("FDM", "https://careers.fdmgroup.com/vacancies/827/it-operations-practice.html"),
]

for name, url in urls:
    asyncio.run(debug_page(url, name))
