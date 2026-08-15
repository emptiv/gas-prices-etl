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
1. extract pdf files from source website (filtered to records from july 21, 2023 to present only)
2. extract data from summary table of the pdf files
3. load extracted data to the local database

### to do
- [x] build webscraper
- [x] build OCR extractor and data cleaner
- [x] update webscraper so it updates whenever there are new data added but retains the old ones
- [x] connect to database
- [ ] load the pdf files to the database as well instead of locally downloading them
- [ ] fix errors
  - [ ] some pdf files are not processed (add "for the period of [date range]" + *still mystery format* as expected format for extraction)
  - [ ] if pdf files are downloaded, the system does not proceed with the parsing despite some documents are not yet parsed