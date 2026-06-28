#!/usr/bin/env python
"""Debug script to inspect iframe content."""

import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def debug_greenhouse_iframe(url):
    """Debug Greenhouse iframe content."""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Get iframe URL
            iframe_src = await page.evaluate("""
                () => {
                    const iframe = document.querySelector('iframe#grnhse_iframe');
                    return iframe ? iframe.src : null;
                }
            """)
            
            print(f"Found iframe: {iframe_src}\n")
            
            if iframe_src:
                await page.goto(iframe_src, wait_until='networkidle', timeout=30000)
                await page.wait_for_timeout(3000)
            
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Show all text with class names and data attributes
            print("=== All major elements ===\n")
            for elem in soup.find_all(['div', 'section', 'p', 'span', 'h1', 'h2', 'h3']):
                text = elem.get_text(strip=True)
                if text and len(text) > 20 and len(text) < 300:
                    classes = ' '.join(elem.get('class', []))
                    data_attrs = {k: v for k, v in elem.attrs.items() if k.startswith('data-')}
                    if classes or data_attrs:
                        print(f"Text: {text[:100]}")
                        if classes:
                            print(f"  Class: {classes}")
                        if data_attrs:
                            print(f"  Data: {data_attrs}")
                        print()
            
        finally:
            await browser.close()

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python debug_scraper.py <url>")
        sys.exit(1)
    
    url = sys.argv[1]
    asyncio.run(debug_greenhouse_iframe(url))
