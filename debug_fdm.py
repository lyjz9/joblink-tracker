"""Deep debug FDM page."""
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re

async def debug_fdm():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://careers.fdmgroup.com/vacancies/827/it-operations-practice.html', wait_until='domcontentloaded')
        await page.wait_for_timeout(8000)
        
        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text()
        
        print(f"Total page text length: {len(text)}")
        
        # Search for key terms
        search_terms = ['IT Operations', 'Practice', 'FDM', 'Consultant', 'Saved', 'As an']
        for term in search_terms:
            if term in text:
                idx = text.find(term)
                print(f"\nFound '{term}' at position {idx}")
                print(f"Context: ...{text[max(0, idx-100):idx+150]}...")
            else:
                print(f"\n'{term}' NOT found")
        
        # Get first 4000 chars
        print("\n" + "="*80)
        print("FIRST 4000 CHARS:")
        print("="*80)
        print(text[:4000])
        
        await browser.close()

asyncio.run(debug_fdm())
