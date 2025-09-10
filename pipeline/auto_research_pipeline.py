
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto-research pipeline for public-source evidence collection
Target: SMB software companies (e.g., Software Finland ry members, headcount <= 100)
Author: (your name)
License: MIT

Overview
--------
Given a CSV of companies (name + domain), the script will:
1) Generate reproducible search queries (Google Custom Search API or Bing Web Search API).
2) Retrieve top-N URLs per query.
3) Filter & normalize URLs (same host, de-dup, blocklists, media types).
4) Fetch HTML/PDF for each URL, store to disk with SHA256 hash.
5) Extract metadata (title, published date candidates), and short evidence snippets (<=280 chars) around keywords.
6) Emit a unified CSV ready for coding (compatible with your "public-sources-coding-template.csv").
7) Create a search log (query diary) for replicability.

Notes
-----
- You must provide API keys via environment variables:
    * GOOGLE_API_KEY, GOOGLE_CX   (for Google Custom Search)   OR
    * BING_API_KEY                (for Bing Web Search v7)
- Respect robots.txt and terms of service.
- This is a template: adapt keyword lists & filters to your study focus.
"""

import csv
import hashlib
import html
import io
import json
import os
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# Load environment variables from .env file
from pathlib import Path
env_path = Path("../.env")
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if line.strip() and not line.startswith('#') and '=' in line:
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

# ------------------------ Config ------------------------

OUTPUT_DIR = Path("../out")  # will be created in CWD
RAW_DIR = OUTPUT_DIR / "raw"           # raw HTML/PDF
META_DIR = OUTPUT_DIR / "meta"         # metadata JSON
LOG_DIR = OUTPUT_DIR / "logs"          # query diaries
CSV_DIR = OUTPUT_DIR / "csv"           # consolidated CSVs

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
for d in (RAW_DIR, META_DIR, LOG_DIR, CSV_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Queries per company (edit as needed)
QUERY_TEMPLATES = [
    # Services/products
    'site:{domain} services OR tuotteet OR palvelut',
    # Pricing
    'site:{domain} pricing OR hinnoittelu OR arvopohjainen OR tulosperusteinen',
    # Blog/news
    'site:{domain} blog OR uutiset OR ajankohtaista OR news',
    # References/case studies
    'site:{domain} references OR referenssit OR asiakastarinat OR case study',
    # Careers/jobs
    'site:{domain} careers OR urat OR jobs OR rekry OR työpaikat',
    # SaaS/productized/hybrid
    '{company} SaaS OR tuote OR tuotteistus OR productized OR hybrid OR niche',
    # Outcome/value-based pricing
    '{company} outcome pricing OR value-based pricing OR tulospohjainen hinnoittelu OR arvopohjainen',
    # Venture studio/portfolio
    '{company} venture studio OR portfolio OR portfolioyhtiö',
    # API/platform/open source
    '{company} APIOps OR API strategy OR platform OR open source OR avoin lähdekoodi',
    # Growth/scalable/automation/innovation
    '{company} growth OR kasvu OR scalable OR skaalautuva OR automation OR automaatio OR innovation OR innovaatiot',
    # Customer segment/delivery model/value mechanism
    '{company} customer segment OR asiakassegmentti OR delivery model OR toimitusmalli OR value mechanism OR arvomekanismi',
]

# Keywords for snippet extraction (edit as needed)
EVIDENCE_KEYWORDS = [
    # English
    'SaaS','subscription','product','productized','pricing','value-based','outcome','equity','revenue share',
    'managed service','SRE','APIOps','API','platform','venture','accelerator','nearshore','broker','transparent',
    'consulting','hybrid','niche','recurring','IP','open source','differentiator','customer segment','geography',
    'risk sharing','delivery model','value mechanism','case study','reference','portfolio','growth','scalable','automation',
    # Finnish
    'tuote','tuotteistus','palvelu','palvelut','hinnoittelu','arvo','arvopohjainen','tulosperusteinen','osakkuus','liikevaihto',
    'hallinnoitu palvelu','asiakastarina','referenssi','alusta','avoin lähdekoodi','kilpailuetu','asiakassegmentti','toimiala',
    'riskinjako','toimitusmalli','arvomekanismi','kasvu','skaalautuva','automaatio','yritystarina','sijoittaja','portfolio','innovaatiot'
]

MAX_URLS_PER_QUERY = 10
REQUEST_TIMEOUT = 20  # seconds
SLEEP_BETWEEN_QUERIES = 1.2  # polite pause

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PublicResearchBot/1.0; +https://example.org/methods)"
}

# Optional host allow/deny
HOST_DENY = {'facebook.com', 'twitter.com', 'x.com'}
EXT_DENY = {'.jpg','.jpeg','.png','.gif','.svg','.webp','.ico','.mp3','.mp4','.zip','.rar','.7z','.doc','.docx','.xls','.xlsx'}

# ------------------------ Data classes ------------------------

@dataclass
class SearchHit:
    company: str
    query: str
    rank: int
    title: str
    url: str
    source: str  # google|bing
    fetched_at: str

@dataclass
class SourceRecord:
    Company: str
    Country: str
    Website: str
    SourceType: str
    SourceTitle: str
    SourceURL: str
    SourceDate: str
    EvidenceQuote: str
    ModelCategory: str
    RevenueMix: str
    PricingModel: str
    ProductizationLevel: int
    RiskSharingLevel: int
    DeliveryModel: str
    IP_OSS_Strategy: str
    Differentiators: str
    HardToCopyFactors: str
    ValueMechanisms: str
    CustomerSegments: str
    Geographies: str
    EvidenceStrength: int
    AnalystConfidence: int
    Notes: str

# ------------------------ Utils ------------------------

def sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()

def sanitize_filename(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9._-]+', '_', name)[:200]

def is_allowed_url(u: str) -> bool:
    try:
        p = urlparse(u)
        if not p.scheme.startswith('http'):
            return False
        if any(p.netloc.endswith(h) for h in HOST_DENY):
            return False
        if any(p.path.lower().endswith(ext) for ext in EXT_DENY):
            return False
        return True
    except Exception:
        return False

def guess_source_type(url: str) -> str:
    host = urlparse(url).netloc
    if 'linkedin.com' in host: return 'LinkedIn'
    if 'github.com' in host: return 'GitHub'
    if 'hilma' in host or 'hankintailmoitukset' in host: return 'Public procurement'
    if 'prh.fi' in host or 'ytj.fi' in host: return 'Registry'
    return 'Website'

def extract_pubdate(soup: BeautifulSoup) -> str:
    # Heuristics: meta tags, time tags, schema.org
    candidates = []
    metas = soup.find_all('meta')
    for m in metas:
        for k in ('article:published_time','og:updated_time','date','dc.date','dc.date.issued','publication_date'):
            if m.get('property') == k or m.get('name') == k:
                val = m.get('content') or ''
                if val:
                    candidates.append(val.strip())
    # <time datetime="...">
    for t in soup.find_all('time'):
        dt = t.get('datetime') or t.get_text()
        dt = dt.strip()
        if dt:
            candidates.append(dt)
    # pick the most ISO-looking
    for c in candidates:
        if re.match(r'\d{4}-\d{2}-\d{2}', c):
            return c[:10]
    return ''

def extract_snippets(text: str, keywords: List[str], max_len: int = 280, max_snips: int = 3) -> List[str]:
    snips = []
    low = text.lower()
    for kw in keywords:
        pos = low.find(kw.lower())
        if pos != -1:
            start = max(0, pos - 160)
            end = min(len(text), pos + 160)
            chunk = ' '.join(text[start:end].split())
            if len(chunk) > max_len:
                chunk = chunk[:max_len-1] + '…'
            if chunk not in snips:
                snips.append(chunk)
            if len(snips) >= max_snips:
                break
    return snips

# ------------------------ Search backends ------------------------

def test_google_api() -> bool:
    """Test if Google API keys are working"""
    api_key = os.getenv('GOOGLE_API_KEY')
    cx = os.getenv('GOOGLE_CX')
    
    print(f"[TEST] GOOGLE_API_KEY: {'✓ Set' if api_key else '✗ Missing'}")
    print(f"[TEST] GOOGLE_CX: {'✓ Set' if cx else '✗ Missing'}")
    
    if not api_key or not cx:
        print("[TEST] Missing API keys, search will not work")
        return False
    
    try:
        # Test with a simple query
        url = 'https://www.googleapis.com/customsearch/v1'
        params = {'q': 'test', 'key': api_key, 'cx': cx, 'num': 1}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        items = data.get('items', [])
        print(f"[TEST] API test successful - found {len(items)} results")
        return True
    except Exception as e:
        print(f"[TEST] API test failed: {e}")
        return False

def google_search(query: str) -> List[Tuple[str,str]]:
    api_key = os.getenv('GOOGLE_API_KEY')
    cx = os.getenv('GOOGLE_CX')
    if not api_key or not cx:
        return []
    url = 'https://www.googleapis.com/customsearch/v1'
    params = {'q': query, 'key': api_key, 'cx': cx, 'num': 10}
    r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    items = data.get('items', [])
    return [(it.get('title','').strip(), it.get('link','').strip()) for it in items]

def bing_search(query: str) -> List[Tuple[str,str]]:
    api_key = os.getenv('BING_API_KEY')
    if not api_key:
        return []
    url = 'https://api.bing.microsoft.com/v7.0/search'
    headers = {"Ocp-Apim-Subscription-Key": api_key}
    params = {'q': query, 'count': 10, 'responseFilter': 'Webpages'}
    r = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    items = (data.get('webPages') or {}).get('value', [])
    return [(it.get('name','').strip(), it.get('url','').strip()) for it in items]

def run_searches(company: str, domain: str) -> List[SearchHit]:
    hits = []
    source = 'google' if os.getenv('GOOGLE_API_KEY') else ('bing' if os.getenv('BING_API_KEY') else 'none')
    for tmpl in QUERY_TEMPLATES:
        q = tmpl.format(company=company, domain=domain)
        results: List[Tuple[str,str]] = []
        if source == 'google':
            results = google_search(q)
        elif source == 'bing':
            results = bing_search(q)
        else:
            # No API keys; skip but still log intended queries
            results = []
        ts = datetime.utcnow().isoformat()
        qlog = LOG_DIR / f"{sanitize_filename(company)}_{sha256_bytes(q.encode())[:8]}.json"
        qlog.write_text(json.dumps({"company": company, "query": q, "timestamp_utc": ts, "engine": source, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
        for rank, (title, url) in enumerate(results, start=1):
            if not is_allowed_url(url):
                continue
            hits.append(SearchHit(company=company, query=q, rank=rank, title=title, url=url, source=source, fetched_at=ts))
        time.sleep(SLEEP_BETWEEN_QUERIES)
    return hits

# ------------------------ Fetch ------------------------

def fetch_url(url: str) -> Tuple[bytes, Dict[str,str]]:
    r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    content = r.content
    info = {
        "status_code": str(r.status_code),
        "final_url": r.url,
        "content_type": r.headers.get("Content-Type",""),
        "fetched_at_utc": datetime.utcnow().isoformat(),
    }
    return content, info

def parse_html(content: bytes) -> Tuple[str,str,str]:
    soup = BeautifulSoup(content, 'html.parser')
    title = (soup.title.string or "").strip() if soup.title else ""
    pubdate = extract_pubdate(soup)
    # visible text (rough)
    for tag in soup(['script','style','noscript']):
        tag.decompose()
    text = soup.get_text(separator=' ', strip=True)
    text = re.sub(r'\s+', ' ', text)
    return title, pubdate, text

# ------------------------ Main pipeline ------------------------


def process_company(row: Dict[str,str]) -> None:
    company = row.get('company','').strip()
    domain = row.get('domain','').strip()
    country = row.get('country','FI')
    if not company or not domain:
        print(f"[SKIP] Invalid row: {row}")
        return

    print(f"[INFO] Searching: {company} ({domain})")
    hits = run_searches(company, domain)

    # De-dup by URL
    seen = set()
    hits = [h for h in hits if not (h.url in seen or seen.add(h.url))]

    csv_rows: List[Dict[str,str]] = []

    for h in hits[:MAX_URLS_PER_QUERY * len(QUERY_TEMPLATES)]:
        try:
            content, info = fetch_url(h.url)
        except Exception as e:
            print(f"[WARN] Fetch failed: {h.url} -> {e}")
            continue

        sha = sha256_bytes(content)
        host = urlparse(h.url).netloc
        ext = Path(urlparse(h.url).path).suffix.lower()
        is_pdf = ('pdf' in info.get('content_type','').lower()) or ext == '.pdf'

        # Save raw
        raw_name = sanitize_filename(f"{company}_{host}_{sha}.{'pdf' if is_pdf else 'html'}")
        RAW_DIR.joinpath(raw_name).write_bytes(content)

        # Parse HTML only (ignore PDFs for snippet extraction here)
        title, pubdate, text = ("","", "")
        if not is_pdf:
            title, pubdate, text = parse_html(content)
        meta = {
            "company": company,
            "query": h.query,
            "rank": h.rank,
            "title": title or h.title,
            "url": h.url,
            "final_url": info.get('final_url', h.url),
            "host": host,
            "pubdate": pubdate,
            "content_type": info.get('content_type',''),
            "sha256": sha,
            "fetched_at_utc": info.get('fetched_at_utc',''),
            "is_pdf": is_pdf
        }
        META_DIR.joinpath(sanitize_filename(f"{company}_{host}_{sha}.json")).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        # Evidence snippets
        snippets = extract_snippets(text, EVIDENCE_KEYWORDS, max_len=280, max_snips=3) if text else []

        # Emit CSV rows for each snippet (or one empty evidence row if none)
        if not snippets:
            snippets = [""]

        for snip in snippets:
            csv_rows.append({
                "Company": company,
                "Country": country,
                "Website": f"https://{domain}",
                "SourceType": guess_source_type(h.url),
                "SourceTitle": title or h.title,
                "SourceURL": h.url,
                "SourceDate": pubdate,
                "EvidenceQuote": snip,
                "ModelCategory": "",  # to be coded manually later
                "RevenueMix": "",
                "PricingModel": "",
                "ProductizationLevel": 0,
                "RiskSharingLevel": 0,
                "DeliveryModel": "",
                "IP_OSS_Strategy": "",
                "Differentiators": "",
                "HardToCopyFactors": "",
                "ValueMechanisms": "",
                "CustomerSegments": "",
                "Geographies": "",
                "EvidenceStrength": 3 if snip else 2,
                "AnalystConfidence": 2,
                "Notes": ""
            })

    # Write consolidated CSV for this company
    out_csv = CSV_DIR / f"{sanitize_filename(company)}_evidence.csv"
    fieldnames = [
        "Company","Country","Website","SourceType","SourceTitle","SourceURL","SourceDate","EvidenceQuote",
        "ModelCategory","RevenueMix","PricingModel","ProductizationLevel","RiskSharingLevel","DeliveryModel",
        "IP_OSS_Strategy","Differentiators","HardToCopyFactors","ValueMechanisms","CustomerSegments","Geographies",
        "EvidenceStrength","AnalystConfidence","Notes"
    ]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in csv_rows:
            w.writerow(r)

    print(f"[DONE] {company}: {len(csv_rows)} evidence rows -> {out_csv}")

def main(companies_csv: str):
    # Test API keys first
    if not test_google_api():
        print("[ERROR] Google API test failed. Please check your API keys.")
        return
    
    # Read companies
    with open(companies_csv, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Optional pre-filter: enforce headcount <=100 (if a 'headcount' column exists)
    # rows = [r for r in rows if r.get('headcount') and int(r['headcount']) <= 100]

    for row in rows:
        process_company(row)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python auto_research_pipeline.py /path/to/companies.csv")
        sys.exit(1)
    main(sys.argv[1])
