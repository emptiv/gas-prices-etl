from parser import process_pdf_file

if __name__ == "__main__":
  pdf_path = "samples/NEWER_HYBRID.pdf"
  records = process_pdf_file(pdf_path, report_id=1)

  print(f"extracted {len(records)} clean records ready for database insertion ;)")
  print(records)