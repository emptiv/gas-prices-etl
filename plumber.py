import pdfplumber
import pandas as pd

def extract_tables_from_pdf(pdf_path):
  all_tables = []
  with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
      tables = page.extract_tables()
      for table in tables:
        if table:
          all_tables.append(table)

  return all_tables