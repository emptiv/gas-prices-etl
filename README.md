# gas-prices-etl

*this is a work in progress!!!*

### required packages
- requests
- beautifulsoup4
- playwright
  - chromium
- pdfplumber
- pandas
- psycopg2-binary
- python-dotenv

### workflow
1. extract and download pdf files from source website (filtered to records from july 21, 2023 to present only)
2. extract data from summary table of the pdf files
3. load extracted data to the local database