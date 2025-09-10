# New business models in SMB software development business

## Tutkimusaihe
Tarkastellaan uusia liiketoimintamalleja pienissä ja keskisuurissa ohjelmistoyrityksissä (Software Finland ry jäsenet, henkilöstömäärä ≤100).

## Otos
Yritykset: Software Finland ry jäsenet, henkilöstömäärä enintään 100.

## Käyttö
1. Lisää Google Custom Search API Key (tai Bing API Key) ympäristömuuttujaan `SEARCH_API_KEY`.
2. Asenna riippuvuudet:
   ```powershell
   pip install -r requirements.txt
   ```
3. Aja pipeline:
   ```powershell
   python pipeline/auto_research_pipeline.py
   ```

## Outputit
- `out/raw` — tallennetut lähteet (HTML/PDF)
- `out/meta` — metatiedot
- `out/logs` — lokitiedostot
- `out/csv` — CSV-exportit

## Replikoitavuus
- Query diary ja SHA256-hashit tallennetaan, jotta haku ja tulokset voidaan toistaa.

## Lisenssi
MIT
