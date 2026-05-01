import os
import sys
import argparse
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from psycopg2.extras import execute_values
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

def shift_dates(df, years):
    """
    Shifts all datetime columns in a DataFrame by a specified number of years.
    """
    date_cols = [col for col in df.columns if any(suffix in col for suffix in ["_at", "_date", "timestamp"])]
    
    for col in date_cols:
        try:
            # Convert to datetime if not already
            df[col] = pd.to_datetime(df[col], format='mixed', errors='coerce', utc=True)
            # Only shift non-null values
            mask = df[col].notna()
            df.loc[mask, col] = df.loc[mask, col] + pd.DateOffset(years=years)
            logger.info(f"  Shifted column '{col}' by {years} years.")
        except Exception as e:
            logger.warning(f"  Could not shift column '{col}': {e}")
    return df

def seed_data(args):
    # Construct DB connection
    connection_url = URL.create(
        drivername="postgresql+psycopg2",
        username=args.user,
        password=args.password,
        host=args.host,
        port=args.port,
        database=args.database,
    )
    engine = create_engine(connection_url)

    # File to Table mapping
    files = [f for f in os.listdir(args.data_dir) if f.endswith('.csv')]
    
    priority = {
        "distribution_centers": 1,
        "products": 2,
        "users": 3,
        "inventory_items": 4,
        "orders": 5,
        "order_items": 6,
        "events": 7
    }
    
    def get_priority(filename):
        for key in priority:
            if key in filename:
                return priority[key]
        return 99

    files.sort(key=get_priority)

    # 1. Truncate tables first
    with engine.connect() as conn:
        if args.truncate_first:
            logger.info(f"Truncating tables in schema '{args.schema}'...")
            with conn.begin():
                tables = ["events", "order_items", "inventory_items", "orders", "products", "users", "distribution_centers"]
                for table in tables:
                    conn.execute(text(f"TRUNCATE TABLE {args.schema}.{table} CASCADE;"))
            logger.info("Truncation complete.")

    # 2. Load data from CSVs
    for file in files:
        table_name = None
        for key in priority:
            if key in file:
                table_name = key
                break
        
        if not table_name:
            continue

        # Skip events table if requested
        if table_name == "events" and args.skip_events:
            logger.info(f"Skipping table: {table_name} as requested.")
            continue

        file_path = os.path.join(args.data_dir, file)
        logger.info(f"Processing {file} -> {args.schema}.{table_name}...")

        # Load CSV using pandas
        df = pd.read_csv(file_path)
        
        # Apply time shift
        if args.year_shift != 0:
            df = shift_dates(df, args.year_shift)

        # Bulk Insert using psycopg2 execute_values (bypasses pandas to_sql compatibility issues)
        logger.info(f"  Uploading {len(df)} rows to {table_name}...")
        
        # Get a raw DBAPI connection
        raw_conn = engine.raw_connection()
        try:
            # Prepare values as list of tuples, manually converting NaT/NaN to None (NULL)
            values = []
            for row in df.itertuples(index=False, name=None):
                values.append(tuple(None if pd.isna(x) else x for x in row))
            
            columns = ",".join([f'"{col}"' for col in df.columns]) # Quote columns to handle reserved words
            query = f"INSERT INTO {args.schema}.{table_name} ({columns}) VALUES %s"
            
            with raw_conn.cursor() as cursor:
                # Use execute_values for high-performance batch insertion
                execute_values(cursor, query, values, page_size=5000)
            
            raw_conn.commit()
            logger.info(f"  Successfully loaded {table_name}.")
        except Exception as e:
            raw_conn.rollback()
            logger.error(f"  Failed to load {table_name}: {e}")
            raise e
        finally:
            raw_conn.close()

    logger.info("Seeding process completed successfully!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Postgres with TheLook CSV data and time shift.")
    parser.add_argument("--host", default="localhost", help="Database host")
    parser.add_argument("--port", type=int, default=5433, help="Database port")
    parser.add_argument("--database", default="thelook_db", help="Database name")
    parser.add_argument("--user", default="db_user", help="Database user")
    parser.add_argument("--password", default="db_password", help="Database password")
    parser.add_argument("--schema", default="demo", help="Database schema")
    parser.add_argument("--data-dir", default="./data", help="Directory containing CSV files")
    parser.add_argument("--truncate-first", action="store_true", help="Truncate tables before loading")
    parser.add_argument("--year-shift", type=int, default=3, help="Number of years to shift dates")
    parser.add_argument("--skip-events", action="store_true", help="Skip loading the events table")

    args = parser.parse_args()
    
    if not os.path.exists(args.data_dir):
        logger.error(f"Data directory not found: {args.data_dir}")
        sys.exit(1)

    try:
        seed_data(args)
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        sys.exit(1)
