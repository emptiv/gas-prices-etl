import re
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from plumber import extract_tables_from_pdf
import pdfplumber

TARGET_PRODUCTS = [
  "DIESEL", "DIESEL PLUS", "KEROSENE",
  "GASOLINE (RON97/100)", "GASOLINE (RON95)", "GASOLINE (RON91)"
]

MONTH_MAP = {
  "jan": 1, "january": 1,
  "feb": 2, "february": 2,
  "mar": 3, "march": 3,
  "apr": 4, "april": 4,
  "may": 5,
  "jun": 6, "june": 6,
  "jul": 7, "july": 7,
  "aug": 8, "august": 8,
  "sep": 9, "sept": 9, "september": 9,
  "oct": 10, "october": 10,
  "nov": 11, "november": 11,
  "dec": 12, "december": 12,
}

def parse_date_range(text:str) -> Tuple[Optional[str], Optional[str]]:
  if not text:
    return None, None

  clean_text = re.sub(r"\.\b", "", text.lower())
  clean_text = re.sub(r"\s+", " ", clean_text)

  match = re.search(r"\((?:as\s+of|for\s+(?:the\s+)?(?:week|period)\s+of)\s+([^\)\n\r]+)\)?", clean_text, re.IGNORECASE)
  raw_range = match.group(1).strip() if match else clean_text

  years = [int(y) for y in re.findall(r"\b(20\d{2})\b", raw_range)]
  if not years:
    return None, None

  two_month_match = re.search(
    r"([a-z]+)\s*(\d{1,2})(?:\s*,\s*\d{4})?\s*[-–\b(?:to)]+\s*([a-z]+)\s*(\d{1,2})(?:\s*,\s*(\d{4}))?",
    raw_range
  )
  if two_month_match:
    m1_str, d1_str, m2_str, d2_str, y2_override = two_month_match.groups()
    m1 = MONTH_MAP.get(m1_str)
    m2 = MONTH_MAP.get(m2_str)
    if m1 and m2:
      y1 = years[0]
      y2 = int(y2_override) if y2_override else (years[1] if len(years) > 1 else years[0])

      if m1 == 12 and m2 == 1 and len(years) == 1:
        y2 = y1 + 1

      try:
        dt1 = datetime(y1, m1, int(d1_str))
        dt2 = datetime(y2, m2, int(d2_str))
        return dt1.strftime("%Y-%m-%d"), dt2.strftime("%Y-%m-%d")
      except ValueError:
        pass
    

  single_month_match = re.search(
    r"([a-z]+)\s*(\d{1,2})\s*[-–\b(?:to)]+\s*(\d{1,2})",
    raw_range
  )
  if single_month_match:
    m_str, d1_str, d2_str = single_month_match.groups()
    m = MONTH_MAP.get(m_str)
    if m:
      year = years[-1]
      try:
        dt1 = datetime(year, m, int(d1_str))
        dt2 = datetime(year, m, int(d2_str))
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