# gas-prices-etl

an ETL (extract, transform, load) pipeline that automatically scrapes, parses, and loads National Capital Region (NCR) gas price PDF reports from the Department of Energy (DOE) into a PostgreSQL database.

---

### important notes
- the scraper (`scrape.py`) handles the updated DOE portal layout (`https://doe.gov.ph/data-and-prices/liquid-fuels/retail-pump-prices/ncr-pump-prices`). it uses Playwright and BeautifulSoup to render dynamic JavaScript tables, extract new PDF links, and download missing files automatically.
- PDF files are fetched starting from the cutoff date (July 21, 2023 to present) and saved locally inside organized folder structures under `downloads/`.
- reports are pre-screened using `peek_date_range()` to skip files whose date ranges are already stored in the database, preventing unnecessary heavy PDF parsing.
- extracted pricing data uses PostgreSQL's `ON CONFLICT (start_date, end_date, product)` clause to seamlessly update existing database entries without creating duplicate rows.

---

### installation & setup

1. **clone the repository and install required dependencies**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **configure database credentials in .env file**
   ```env
   DB_NAME=your_database_name
   DB_USER=your_database_user
   DB_PASSWORD=your_database_password
   DB_HOST=localhost
   DB_PORT=5432
   ```

3. **verify local data**
   ensure a `downloads/` directory exists (or let the script create it). downloaded files will automatically be sorted into nested structures like `downloads/YYYY/Month/`.

---

### how to use
- just run the main entry script to trigger the full scraper and database sync pipeline
   ```bash
   python main.py
   ```

---

### main pipeline workflow
1. launches the browser via Playwright to fetch and render the DOE's dynamic HTML tables.
2. checks for missing or new PDF reports and downloads them into the `downloads/` directory.
3. recursively scans `downloads/` to locate all available `.pdf` documents.
4. extracts report metadata (`start_date` and `end_date`) from each PDF header using flexible regex patterns.
5. queries PostgreSQL to verify if the date range already exists.
6. parses product categories (*DIESEL*, *GASOLINE RON91/95/97*, *KEROSENE*) along with min, max, and common prices using `pdfplumber`.
7. inserts new rows or updates existing records in the `ncr_gas_prices` database table.