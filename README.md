# gas-prices-etl

an ETL (extract, transform, load) pipeline that parses PDF reports containing National Capital Region (NCR) gas price data and loads structured records into a PostgreSQL database.

---

### important notes
- the original Department of Energy (DOE) portal (`https://doe.gov.ph`) underwent a site overhaul, removing the historical web tables and public PDF links. the web scraper (`scrape.py`) is retained in the codebase solely as a technical reference for how Playwright and BeautifulSoup were used to extract filtered records (July 21, 2023 onwards).
- active processing runs entirely offline against pre-downloaded files in the `downloads/` directory.
- reports are pre-screened via `peek_date_range()` to skip files whose date ranges are already populated in the database.
- extracted prices use PostgreSQL's `ON CONFLICT (start_date, end_date, product)` clause to seamlessly update existing entries without creating duplicates.

---

### required packages
- pdfplumber
- pandas
- psycopg2-binary
- python-dotenv
- requests *(optional reference for `scrape.py`)*
- beautifulsoup4 *(optional reference for `scrape.py`)*
- playwright *(optional reference for `scrape.py`)*
   - chromium

---

### installation & setup

1. **clone the repository and install required dependencies**
   ```bash
   pip install pdfplumber pandas psycopg2-binary python-dotenv
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
   make sure that the extracted/archived PDF reports are inside the `downloads/` directory (nested folder structures like `downloads/YYYY/Month/` are scanned recursively).

---

### how to use
- just run the main entry script to parse all local files and sync to PostgreSQL
   ```bash
   python main.py
   ```

---

### main pipeline workflow
1. recursively locates all `.pdf` documents within `downloads/`.
2. extracts report metadata (`start_date` and `end_date`) from each PDF header.
3. queries the target database to check if the date range already exists.
4. parses product categories (*DIESEL*, *GASOLINE RON91/95/97*, *KEROSENE*) along with min, max, and common prices.
5. inserts new rows or updates records in the `ncr_gas_prices` table.