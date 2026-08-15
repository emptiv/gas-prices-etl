import re
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from plumber import extract_tables_from_pdf
import pdfplumber

TARGET_PRODUCTS = [
  "DIESEL", "DIESEL PLUS", "KEROSENE",
  "GASOLINE (RON97/100)", "GASOLINE (RON95)", "GASOLINE (RON91)"
]

def parse_date_range(text:str) -> Tuple[Optional[str], Optional[str]]:
  if not text:
    return None, None

  match = re.search(r"\(\s*(?:as\s+of|for\s+the\s+week\s+of)\s+([^\)\n\r]+)\)?", text, re.IGNORECASE)
  if not match:
    return None, None

  raw_range = re.sub(r"\s+", " ", match.group(1)).strip()

  cross_month_match = re.match(r"([A-Za-z]+)\s+(\d+)\s*[-to]+\s*([A-Za-z]+)\s+(\d+),?\s*(\d{4})", raw_range, re.IGNORECASE)
  if cross_month_match:
    m1, d1, m2, d2, year = cross_month_match.groups()
    try:
      dt1 = datetime.strptime(f"{m1} {d1} {year}", f"%B %d %Y")
      dt2 = datetime.strptime(f"{m2} {d2} {year}", f"%B %d %Y")
      return dt1.strftime("%Y-%m-%d"), dt2.strftime("%Y-%m-%d")
    except ValueError:
      pass

  same_month_match = re.match(r"([A-Za-z]+)\s+(\d+)\s*[-to]+\s*(\d+),?\s*(\d{4})", raw_range, re.IGNORECASE)
  if same_month_match:
    month, d1, d2, year = same_month_match.groups()
    month_fmt = "%b" if len(month) == 3 else "%B"
    try:
      dt1 = datetime.strptime(f"{month} {d1} {year}", f"{month_fmt} %d %Y")
      dt2 = datetime.strptime(f"{month} {d2} {year}", f"{month_fmt} %d %Y")
      return dt1.strftime("%Y-%m-%d"), dt2.strftime("%Y-%m-%d")
    except ValueError:
      pass

  return None, None

def peek_date_range(pdf_path: str) -> Tuple[Optional[str], Optional[str]]:
  try:
    with pdfplumber.open(pdf_path) as pdf:
      for page in pdf.pages:
        text = page.extract_text() or ""
        if "PREVAILING" in text.upper():
          s_dt, e_dt = parse_date_range(text)
          if s_dt and e_dt:
            return s_dt, e_dt
  except Exception as e:
    print(f"could not peek date range from {pdf_path}: {e}")

  return None, None
          
def process_pdf_file(pdf_path: str, report_id: int) -> Dict[str, Optional[Any]]:
  raw_tables = extract_tables_from_pdf(pdf_path)

  start_date, end_date = None, None
  records = []
  sorted_targets = sorted(TARGET_PRODUCTS, key=len, reverse=True)

  for table in raw_tables:
    for row in table:
      if not row or not any(row):
        continue

      row_cells = [re.sub(r"\s+", " ", str(cell or "")).strip() for cell in row]
      row_str = " ".join(row_cells)

      if "PREVAILING" in row_str.upper():
        s_dt, e_dt = parse_date_range(row_str)
        if s_dt and e_dt:
          start_date, end_date = s_dt, e_dt

      product_name = None
      for cell in row_cells[:2]:
        cell_upper = cell.upper()
        for prod in sorted_targets:
          if prod in cell_upper:
            product_name = prod
            break
        if product_name:
          break

      if not product_name:
        continue

      row_str = " ".join(row_cells)

      clean_str = re.sub(r"GASOLINE\s*\(RON\d+(/\d+)?\)", "", row_str, flags=re.IGNORECASE)
      clean_str = re.sub(r"DIESEL\s*PLUS", "", clean_str, flags=re.IGNORECASE)
      clean_str = re.sub(r"DIESEL|KEROSENE", "", clean_str, flags=re.IGNORECASE)

      prices = [float(p) for p in re.findall(r"\d+\.\d+", clean_str)]

      min_price, max_price, common_price = None, None, None

      if len(prices) >= 3:
        min_price = prices[0]
        max_price = prices[1]
        common_price = prices[2]
      elif len(prices) == 2:
        min_price = prices[0]
        max_price = prices[1]

      records.append({
        "report_id": report_id,
        "start_date": start_date,
        "end_date": end_date,
        "product": product_name,
        "overall_range_min": min_price,
        "overall_range_max": max_price,
        "common_price": common_price
      })

  deduped = {}
  for record in records:
    record["start_date"] = start_date
    record["end_date"] = end_date
    deduped[record["product"]] = record

  if not start_date or not end_date:
    raise ValueError(f"could not extract a valid date range from {pdf_path}")

  return {
    "start_date": start_date,
    "end_date": end_date,
    "records": list(deduped.values())
  }