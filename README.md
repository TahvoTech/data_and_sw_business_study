
# Auto Research Pipeline (Public Sources)

This repository contains a reproducible scaffold to automate much of your study:
“New business models in SMB software development” using **public sources only**.

## What it does
- Generates reproducible search queries per company (Google CSE or Bing API), **restricted to company domains only**.
- Saves top URLs per query, with a **query diary** (JSON logs).
- Fetches each URL, stores raw HTML/PDF with **SHA256**.
- Extracts metadata (title, pubdate candidates) and short **evidence snippets** (≤280 chars).
- Emits a CSV per company compatible with your `public-sources-coding-template.csv`.

## Folder structure

out/
raw/ # raw html/pdf files
meta/ # per-URL metadata (json)
logs/ # per-query logs (json)
csv/ # per-company evidence csv

Always show details


## Requirements
- Python 3.10+
- `pip install -r requirements.txt` (you can create one with `requests`, `beautifulsoup4`)

## Environment variables
Choose one search backend:

**Google Custom Search**

export GOOGLE_API_KEY=your_key
export GOOGLE_CX=your_custom_search_engine_id

Always show details


## Usage
1. Prepare `companies.csv` with columns: `company,domain,country,notes`  
   See the example provided.
2. Run:

python auto_research_pipeline.py /path/to/companies.csv

Always show details
3. Inspect outputs in `out/`.

## Customization
- Edit `QUERY_TEMPLATES` to add/remove queries (Finnish/English).
- Edit `EVIDENCE_KEYWORDS` for snippet extraction.
- Add allow/deny lists for hosts and file extensions.
- If you have headcount or membership columns, filter in `main()`.
- To restrict searches to company sites, ensure all target domains are listed in your Google CSE.

## Ethics & compliance
- Use **public sources** only.
- Respect `robots.txt` and site terms.
- Keep the **query diary** and hashes for reproducibility.
- Human-in-the-loop: review and approve each evidence row before analysis.

## Next steps
- Consolidate per-company CSVs into a master file.
- Manually code `ModelCategory`, `PricingModel`, etc.
- Use your analysis notebook to create charts/tables for the paper.
testiu