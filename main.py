from datetime import date
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from scrape import scrape_and_download
from parser import process_pdf_file, peek_date_range
from db import insert_records, get_latest_date_range, is_date_range_exists

BASE_DIR = Path(__file__).resolve().parent / "downloads"

def normalize_date(val: Any) -> Optional[date]:
    if not val:
        return None
    if isinstance(val, date):
        return val
    return date.fromisoformat(str(val))

def get_db_latest_end_date() -> Optional[date]:
    latest_range = get_latest_date_range()
    if latest_range and len(latest_range) == 2:
        return normalize_date(latest_range[1])
    return None

def process_and_upload_pdf(pdf_path: Path, report_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None) -> int:
    try:
        if not start_date or not end_date:
            start_date, end_date = peek_date_range(str(pdf_path))

        if start_date and end_date and is_date_range_exists(start_date, end_date):
            print(f"skipping {pdf_path.name}: date range [{start_date} to {end_date}] fully exists in DB.")
            return 0

        result: Dict[str, Optional[Any]] = process_pdf_file(str(pdf_path), report_id=report_id)
        records: List[Dict[str, Any]] = result.get("records") or []

        if not records:
            print(f"no valid records extracted from {pdf_path.name}")
            return 0

        inserted_count = insert_records(records)
        print(f"[{result['start_date']} to {result['end_date']}] Inserted {inserted_count} records from {pdf_path.name}")
        return inserted_count

    except Exception as e:
        print(f"error processing PDF {pdf_path.name}: {e}")
        return 0

def run_pipeline():
    # 1. Fetch latest state from Database FIRST
    db_latest_end = get_db_latest_end_date()
    print(f"latest database record end date: {db_latest_end or 'None'}")

    # 2. Download only new PDFs past the database cutoff date
    print("checking for new PDFs on DOE website...")
    newly_downloaded = scrape_and_download(since_date=db_latest_end)

    # 3. Gather local PDFs that require processing
    pdf_paths = sorted(list(BASE_DIR.rglob("*.pdf"))) if BASE_DIR.exists() else []
    if not pdf_paths:
        print("no local PDF files found.")
        return

    # Filter files: parse header dates only when necessary
    unprocessed_pdfs: List[Tuple[Path, str, str]] = []

    for pdf_path in pdf_paths:
        start_dt, end_dt = peek_date_range(str(pdf_path))
        if not start_dt or not end_dt:
            continue

        pdf_end = normalize_date(end_dt)

        # Safely ensure pdf_end is not None before comparing
        if pdf_end and db_latest_end and pdf_end <= db_latest_end:
            continue

        unprocessed_pdfs.append((pdf_path, start_dt, end_dt))

    if not unprocessed_pdfs:
        print("database is fully up to date. no new records to insert.")
        return

    print(f"found {len(unprocessed_pdfs)} PDF file(s) newer than DB state. processing...")

    total_records = 0
    for idx, (pdf_path, start_dt, end_dt) in enumerate(unprocessed_pdfs, start=1):
        count = process_and_upload_pdf(pdf_path, report_id=idx, start_date=start_dt, end_date=end_dt)
        total_records += count

    print(f"pipeline finished: processed {len(unprocessed_pdfs)} PDFs, inserted {total_records} total records.")

if __name__ == "__main__":
    run_pipeline()