import os
import csv
import requests
import hashlib
from bs4 import BeautifulSoup
from datetime import datetime

API_KEY = os.getenv('SEARCH_API_KEY')
SEARCH_ENGINE_ID = os.getenv('SEARCH_ENGINE_ID')  # Google Custom Search
BING_ENDPOINT = os.getenv('BING_ENDPOINT')        # Bing API endpoint

COMPANIES_CSV = '../data/companies.csv'
OUTPUT_RAW = '../out/raw/'
OUTPUT_META = '../out/meta/'
OUTPUT_LOGS = '../out/logs/'
OUTPUT_CSV = '../out/csv/results.csv'

os.makedirs(OUTPUT_RAW, exist_ok=True)
os.makedirs(OUTPUT_META, exist_ok=True)
os.makedirs(OUTPUT_LOGS, exist_ok=True)
os.makedirs('../out/csv', exist_ok=True)

SEARCH_TYPE = os.getenv('SEARCH_TYPE', 'google')  # 'google' or 'bing'

# Helper: Save file with SHA256 hash
def save_with_hash(content, ext):
    h = hashlib.sha256(content).hexdigest()
    fname = f'{h}.{ext}'
    with open(os.path.join(OUTPUT_RAW, fname), 'wb') as f:
        f.write(content)
    return fname, h

# Helper: Google Custom Search
def google_search(query):
    url = f'https://www.googleapis.com/customsearch/v1'
    params = {
        'key': API_KEY,
        'cx': SEARCH_ENGINE_ID,
        'q': query,
        'num': 5
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json().get('items', [])

# Helper: Bing Search
def bing_search(query):
    url = BING_ENDPOINT
    headers = {'Ocp-Apim-Subscription-Key': API_KEY}
    params = {'q': query, 'count': 5}
    r = requests.get(url, headers=headers, params=params)
    r.raise_for_status()
    return r.json().get('webPages', {}).get('value', [])

# Helper: Download and hash HTML
def fetch_and_hash(url):
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    fname, h = save_with_hash(r.content, 'html')
    return fname, h, r.content

# Helper: Extract snippet
def extract_snippet(html, keywords):
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(separator=' ')
    for kw in keywords:
        idx = text.lower().find(kw.lower())
        if idx != -1:
            start = max(0, idx-100)
            end = min(len(text), idx+200)
            return text[start:end]
    return text[:300]

# Main pipeline
results = []
with open(COMPANIES_CSV, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        company = row['company']
        domain = row['domain']
        country = row['country']
        query = f"{company} site:{domain} business model"
        try:
            if SEARCH_TYPE == 'google':
                items = google_search(query)
            else:
                items = bing_search(query)
        except Exception as e:
            with open(os.path.join(OUTPUT_LOGS, 'errors.log'), 'a', encoding='utf-8') as log:
                log.write(f"{datetime.now()} {company}: {e}\n")
            continue
        for item in items:
            url = item.get('link') if SEARCH_TYPE == 'google' else item.get('url')
            title = item.get('title')
            snippet = item.get('snippet') if SEARCH_TYPE == 'google' else item.get('snippet', '')
            try:
                fname, h, html = fetch_and_hash(url)
                evidence = extract_snippet(html, ['business model', 'pricing', 'value'])
            except Exception as e:
                with open(os.path.join(OUTPUT_LOGS, 'errors.log'), 'a', encoding='utf-8') as log:
                    log.write(f"{datetime.now()} {company} {url}: {e}\n")
                continue
            results.append({
                'Company': company,
                'Country': country,
                'Website': domain,
                'SourceType': 'Web',
                'SourceTitle': title,
                'SourceURL': url,
                'SourceDate': datetime.now().date(),
                'EvidenceQuote': evidence,
                'ModelCategory': '',
                'RevenueMix': '',
                'PricingModel': '',
                'ProductizationLevel': '',
                'RiskSharingLevel': '',
                'DeliveryModel': '',
                'IP_OSS_Strategy': '',
                'Differentiators': '',
                'HardToCopyFactors': '',
                'ValueMechanisms': '',
                'CustomerSegments': '',
                'Geographies': '',
                'EvidenceStrength': '',
                'AnalystConfidence': '',
                'Notes': f"SHA256: {h}"
            })

# Export results
with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=[
        'Company','Country','Website','SourceType','SourceTitle','SourceURL','SourceDate','EvidenceQuote','ModelCategory','RevenueMix','PricingModel','ProductizationLevel','RiskSharingLevel','DeliveryModel','IP_OSS_Strategy','Differentiators','HardToCopyFactors','ValueMechanisms','CustomerSegments','Geographies','EvidenceStrength','AnalystConfidence','Notes'])
    writer.writeheader()
    writer.writerows(results)

# Log query diary
with open(os.path.join(OUTPUT_META, 'query_diary.log'), 'a', encoding='utf-8') as log:
    for row in results:
        log.write(f"{datetime.now()} {row['Company']} {row['SourceURL']} {row['Notes']}\n")
