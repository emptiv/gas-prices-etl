-- main table for the extracted data
CREATE TABLE IF NOT EXISTS ncr_gas_prices (
  id SERIAL PRIMARY KEY,
  report_id INT NOT NULL,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  product VARCHAR(50) NOT NULL,
  overall_range_min NUMERIC(6, 2),
  overall_range_max NUMERIC(6, 2),
  common_price NUMERIC(6, 2),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

  -- prevent inserting identical product records for the same date window
  CONSTRAINT unique_report_product UNIQUE (start_date, end_date, product)
);