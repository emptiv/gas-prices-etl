import os
import re
from urllib.parse import urljoin
from pathlib import Path
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# target URL
URL = "https://doe.gov.ph/data-and-prices/liquid-fuels/retail-pump-prices/ncr-pump-prices"
BASE_DIR = Path("downloads")
CUTOFF_DATE = datetime(2023, 7, 21)

# headers to mimic a real browser request
HEADERS = {
  "User-Agent": (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
  )
}

MONTH_REGEX = re.compile(
  r'^(January|February|March|April|May|June|July|August|September|October|November|December|'
  r'Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)', re.I
)

def clean_filename(name: str) -> str:
  return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def parse_link_approx_date(year_str: str, month_str: str, link_text: str) -> datetime:
  try:
    year = int(year_str)
  except ValueError:
    return datetime.min

  day_match = re.search(r'\b(\d{1,2})\b', link_text)
  day = int(day_match.group(1)) if day_match else 1

  month_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*', link_text, re.I)
  target_month = month_match.group(1) if month_match else month_str

  for fmt in ("%b", "%B"):
    try:
      return datetime.strptime(f"{target_month} {day} {year}", f"{fmt} %d %Y")
    except ValueError:
      pass

  return datetime(year, 12, 31)

def fetch_rendered_html(url: str) -> str:
  print("launching browser to render JS...")
  with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=60000)

    try:
      page.wait_for_selector("table.lex-table, table", timeout=15000)
    except Exception:
      print("warning: timed out waiting for table selector.")

    html_content = page.content()
    browser.close()
    return html_content

def scrape_and_download():
  html = fetch_rendered_html(URL)
  soup = BeautifulSoup(html, "html.parser")

  table = soup.find("table", class_="lex-table") or soup.find("table")
  if not table:
    print("error: could not find the table containing PDF links.")
    return []

  print("table found! extracting links...")

  session = requests.Session()
  session.headers.update(HEADERS)
  downloaded_files: list[Path] = []
  processed_urls = set()

  rows = table.find_all("tr")

  for row in rows:
    cols = row.find_all("td")
    if len(cols) < 2:
      continue

    year_text = cols[0].get_text(strip=True)
    year_match = re.search(r'\b(20\d{2})\b', year_text)
    if not year_match:
      continue
    year = year_match.group(1)

    if int(year) < CUTOFF_DATE.year:
      continue

    top_ul = cols[1].find("ul")
    if not top_ul:
      continue

    current_month = "General"
    lis = top_ul.find_all("li")

    for li in lis:
      direct_text = "".join([
        item.strip() for item in li.contents if isinstance(item, str) and item.strip()
      ]).strip()

      if direct_text and MONTH_REGEX.match(direct_text):
        current_month = clean_filename(direct_text)

      pdf_links = li.find_all("a", href=True)
      for link in pdf_links:
        href = str(link.get("href", "")).strip()
        if not href:
          continue

        full_pdf_url = urljoin(URL, href)
        if full_pdf_url in processed_urls:
          continue
        processed_urls.add(full_pdf_url)

        raw_text = link.get_text(strip=True)
        link_text = clean_filename(raw_text)

        approx_date = parse_link_approx_date(year, current_month, link_text)
        if approx_date < CUTOFF_DATE:
          continue

        filename = f"{link_text}.pdf" if not link_text.lower().endswith(".pdf") else link_text

        target_dir = BASE_DIR / year / current_month
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / filename

        if file_path.exists() and file_path.stat().st_size > 0:
          print(f"skipping (already exists): {filename}")
          continue

        print(f"downloading: [{year} / {current_month}] -> {filename}")
        try:
          pdf_res = session.get(full_pdf_url, stream=True, timeout=20)
          pdf_res.raise_for_status()

          with open(file_path, "wb") as f:
            for chunk in pdf_res.iter_content(chunk_size=8192):
              if chunk:
                f.write(chunk)

          downloaded_files.append(file_path)

        except Exception as e:
          print(f"failed to download {full_pdf_url}: {e}")

  return downloaded_files

if __name__ == "__main__":
  scrape_and_download()