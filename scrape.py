import os
import re
from urllib.parse import urljoin
from pathlib import Path
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# target URL
URL = "https://doe.gov.ph/articles/3142895--list-of-ncr-pump-prices"
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

def clean_filename(name: str) -> str:
  return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def parse_link_approx_date(year_str: str, link_text: str) -> datetime:
  try:
    year = int(year_str)
  except ValueError:
    return datetime.min

  month_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*', link_text, re.I)
  day_match = re.search(r'\b(\d{1,2})\b', link_text)

  if month_match and day_match:
    month_str = month_match.group(1)
    day = int(day_match.group(1))

    for fmt in ("%b", "%B"):
      try:
        dt = datetime.strptime(f"{month_str} {day} {year}", f"{fmt} %d %Y")
        return dt
      except ValueError:
        pass

  return datetime(year, 12, 31)

def fetch_rendered_html(url: str) -> str:
  print("launching browser to render JS...")
  with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url, wait_until="networkidle")

    try:
      page.wait_for_selector("table", timeout=15000)
    except Exception:
      print("warning: timed out waiting for table selector.")

    html_content = page.content()
    browser.close()
    return html_content

def scrape_and_download():
  html = fetch_rendered_html(URL)
  soup = BeautifulSoup(html, "html.parser")

  table = soup.find("table")
  if not table:
    print("error: could not find the table containing PDF links.")
    return

  print("table found! extracting links...")

  session = requests.Session()
  session.headers.update(HEADERS)

  downloaded_files: list[Path] = []

  # iterate over table rows (each row corresponds to a year)
  rows = table.find_all("tr")

  for row in rows:
    cols = row.find_all("td")
    if len(cols) < 2:
      continue

    # step 1: extract year from the first column
    year_elem = cols[0].find(["h1", "h2", "h3", "strong", "b", "p"])
    year_text = year_elem.get_text(strip=True) if year_elem else cols[0].get_text(strip=True)

    # extract year
    year_match = re.search(r'\b(20\d{2}\b)', year_text)
    year = year_match.group(1) if year_match else clean_filename(year_text)

    if not year.isdigit() or int(year) < CUTOFF_DATE.year:
      continue

    # 2. extract month & links from the second column
    top_ul = cols[1].find("ul", recursive=False) or cols[1]

    month_lis = top_ul.find_all("li", recursive=False)
    if not month_lis:
      month_lis = cols[1].find_all("li")

    for month_li in month_lis:
      direct_text = "".join([
        item.strip() for item in month_li.contents
        if isinstance(item, str) and item.strip()
      ]).strip()

      month_name = clean_filename(direct_text) if direct_text else "General"

      # find nested <a> tags for the actual PDF links
      pdf_links = month_li.find_all("a", href=True)

      for link in pdf_links:
        href = str(link.get("href", "")).strip()

        raw_text = link.get_text(strip=True)
        link_text = clean_filename(raw_text)

        approx_date = parse_link_approx_date(year, f"{month_name} {link_text}")
        if approx_date < CUTOFF_DATE:
          continue

        full_pdf_url = urljoin(URL, href)

        filename = f"{link_text}.pdf" if not link_text.lower().endswith(".pdf") else link_text

        target_dir = BASE_DIR / year / month_name
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / filename

        if file_path.exists() and file_path.stat().st_size > 0:
          print(f"skipping (already exists): {filename}")
          continue

        # download file
        print(f"downloading: [{year} / {month_name}] -> {filename}")
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