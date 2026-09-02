import os
import re
from urllib.parse import urljoin
from pathlib import Path
from datetime import datetime, date
from typing import Optional, List
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

URL = "https://doe.gov.ph/data-and-prices/liquid-fuels/retail-pump-prices/ncr-pump-prices"
BASE_DIR = Path(__file__).resolve().parent / "downloads"
HARD_CUTOFF = date(2023, 7, 21)

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

def parse_link_approx_date(year_str: str, month_str: str, link_text: str) -> date:
    try:
        year = int(year_str)
    except ValueError:
        return date.min

    day_match = re.search(r'\b(\d{1,2})\b', link_text)
    day = int(day_match.group(1)) if day_match else 1

    month_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*', link_text, re.I)
    target_month = month_match.group(1) if month_match else month_str

    for fmt in ("%b", "%B"):
        try:
            return datetime.strptime(f"{target_month} {day} {year}", f"{fmt} %d %Y").date()
        except ValueError:
            pass

    return date(year, 12, 31)

def fetch_rendered_html(url: str) -> str:
    # 1. fast path: attempt quick HTTP GET without browser rendering
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            if soup.find("table", class_="lex-table") or soup.find("table"):
                print("fast-path: table fetched via standard HTTP request.")
                return res.text
    except Exception as e:
        print(f"fast-path request failed ({e}); falling back to Playwright...")

    # 2. slow path: fall back to Playwright if JavaScript execution is required
    print("launching Playwright browser...")
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

def scrape_and_download(since_date: Optional[date] = None) -> List[Path]:
    effective_cutoff = max(HARD_CUTOFF, since_date) if since_date else HARD_CUTOFF
    print(f"scraping web reports newer than: {effective_cutoff}")

    html = fetch_rendered_html(URL)
    soup = BeautifulSoup(html, "html.parser")

    table = soup.find("table", class_="lex-table") or soup.find("table")
    if not table:
        print("error: could not find table containing PDF links.")
        return []

    session = requests.Session()
    session.headers.update(HEADERS)
    downloaded_files: List[Path] = []
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

        if int(year) < effective_cutoff.year:
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
                
                if approx_date <= effective_cutoff:
                    continue

                filename = f"{link_text}.pdf" if not link_text.lower().endswith(".pdf") else link_text
                target_dir = BASE_DIR / year / current_month
                target_dir.mkdir(parents=True, exist_ok=True)
                file_path = target_dir / filename

                if file_path.exists() and file_path.stat().st_size > 0:
                    print(f"already cached locally: {filename}")
                    continue

                print(f"downloading new PDF: [{year} / {current_month}] -> {filename}")
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