import sys
import traceback
from pathlib import Path
from typing import Dict, Any, List, Optional
from parser import process_pdf_file, peek_date_range
from db import insert_records, is_date_range_exists

BASE_DIR = Path("downloads")

def get_local_pdf_paths(base_dir: Path) -> List[Path]:
  if not base_dir.exists():
    print(f"error: directory '{base_dir}' does not exist.")
    return []

  return sorted(list(base_dir.rglob("*.pdf")))

def process_and_upload_pdf(pdf_path: Path, report_id: int) -> int:
  try:
    start_date, end_date = peek_date_range(str(pdf_path))

    if start_date and end_date and is_date_range_exists(start_date, end_date):
      print(f"skipping {pdf_path.name}: date range [{start_date} to {end_date}] already exists in DB.")
      return 0


    result: Dict[str, Optional[Any]] = process_pdf_file(str(pdf_path), report_id=report_id)
    records: List[Dict[str, Any]] = result.get("records") or []

    if not records:
      print(f"no records extracted from {pdf_path.name}")
      return 0

    inserted_count = insert_records(records)
    print(f"[{result['start_date']} to {result['end_date']}] inserted/updated {inserted_count} records for {pdf_path.name}")
    return inserted_count

  except Exception as e:
    print(f"error processing PDF {pdf_path.name}: {e}")
    return 0

def run_pipeline():
  pdf_paths = get_local_pdf_paths(BASE_DIR)

  if not pdf_paths:
    print("everything is up to date! no new PDFs to download")
    return

  print(f"processing newly downloaded pdf files...")

  total_records = 0
  for idx, pdf_path in enumerate(pdf_paths, start=1):
    count = process_and_upload_pdf(pdf_path, report_id=idx)
    total_records += count

  print(f"processed {len(pdf_paths)} PDFs with {total_records} total database records.")

if __name__ == "__main__":
  run_pipeline()