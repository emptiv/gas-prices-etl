import os
from pathlib import Path
import psycopg2
from psycopg2.extras import execute_values
from typing import Dict, Any, List, Tuple, Optional
from dotenv import load_dotenv

__all__ = [
  "get_db_connection",
  "insert_records",
  "is_date_range_exists",
  "get_latest_date_range",
]

load_dotenv(Path(__file__).resolve().parent / ".env")

def get_db_connection():
  return psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432")
  )

def insert_records(records: List[Dict[str, Any]]) -> int:
  if not records:
    print("no records provided for insertion.")
    return 0

  query = """
      INSERT INTO ncr_gas_prices (
        report_id, start_date, end_date, product,
        overall_range_min, overall_range_max, common_price
      )
      VALUES %s
      ON CONFLICT (start_date, end_date, product)
      DO NOTHING;
  """

  tuple_records = [
    (
      r["report_id"],
      r["start_date"],
      r["end_date"],
      r["product"],
      r["overall_range_min"],
      r["overall_range_max"],
      r["common_price"]
    )
    for r in records
  ]

  conn = get_db_connection()
  try:
    with conn.cursor() as cur:
      execute_values(cur,query, tuple_records)
      conn.commit()
      return len(tuple_records)
  except Exception as e:
    conn.rollback()
    print(f"error inserting records into the database: {e}")
    raise e
  finally:
    conn.close()

def is_date_range_exists(start_date: str, end_date: str, expected_products: int = 6) -> bool:
  if not start_date or not end_date:
    return False

  query = """
    SELECT COUNT(DISTINCT product)
    FROM ncr_gas_prices
    WHERE start_date = %s AND end_date = %s;
  """
  conn = get_db_connection()
  try:
    with conn.cursor() as cur:
      cur.execute(query, (start_date, end_date))
      row = cur.fetchone()
      return row is not None and row[0] >= expected_products
  except Exception as e:
    print(f"error checking date range in DB: {e}")
    return False
  finally:
    conn.close()


def get_latest_date_range() -> Optional[Tuple[str, str]]:
  query = """
    SELECT start_date, end_date
    FROM ncr_gas_prices
    GROUP BY start_date, end_date
    ORDER BY end_date DESC, start_date DESC
    LIMIT 1;
  """

  conn = get_db_connection()
  try:
    with conn.cursor() as cur:
      cur.execute(query)
      row = cur.fetchone()
      if not row:
        return None
      return row[0], row[1]
  except Exception as e:
    print(f"error fetching latest date range from DB: {e}")
    return None
  finally:
    conn.close()