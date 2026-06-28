import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

url = 'https://www.charliehealth.com/careers/current-openings?gh_jid=5742812004'
resp = requests.get(url, headers={'User-Agent': 'JobTrackerBot/1.0'})
print('status', resp.status_code)
soup = BeautifulSoup(resp.text, 'html.parser')
print('title', soup.title.string if soup.title else '')
link = soup.find('link', rel='canonical')
print('canonical', link['href'] if link else None)
print('links:')
for a in soup.find_all('a', href=True):
    href = a['href']
    if re.search(r'\b(job|jobs|careers|gh_jid|opening|position|vacancy)\b', href, flags=re.I):
        print(urljoin(url, href))
