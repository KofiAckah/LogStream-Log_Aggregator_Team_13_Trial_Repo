"""
LogStream ETL Pipeline - Production Grade
Focus: Incremental Processing, Health Metrics, and Partition Management
"""
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import logging

# Configure logging for production visibility
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from config.config import DATABASE_URL
engine = create_engine(DATABASE_URL)

def manage_partitions():
    """Ensures a partition exists for today and tomorrow."""
    tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime('%Y_%m_%d')
    table_name = f"log_entries_y{tomorrow}"
    start_date = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')
    end_date = (datetime.utcnow() + timedelta(days=2)).strftime('%Y-%m-%d')
    
    query = text(f"""
        CREATE TABLE IF NOT EXISTS {table_name} 
        PARTITION OF log_entries 
        FOR VALUES FROM ('{start_date}') TO ('{end_date}');
    """)
    with engine.begin() as conn:
        conn.execute(query)
        logger.info(f"Verified partition: {table_name}")

def extract_incremental_logs(minutes=15):
    """Extracts only recent logs to minimize DB load."""
    query = text("""
        SELECT id, timestamp, level, message, service_name, source
        FROM log_entries
        WHERE timestamp >= NOW() - INTERVAL ':mins minutes'
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"mins": minutes})

def transform_health_metrics(logs_df):
    """Calculates 24h error rates and last log per service for the Health Dashboard."""
    if logs_df.empty:
        return pd.DataFrame()

    # Calculate metrics
    health = logs_df.groupby("service_name").agg(
        last_log=("timestamp", "max"),
        total_logs=("id", "count"),
        error_logs=("level", lambda x: (x == 'ERROR').sum())
    ).reset_index()
    
    health["error_rate"] = (health["error_logs"] / health["total_logs"]) * 100
    # Status indicator logic
    health["status"] = health["error_rate"].apply(lambda x: "CRITICAL" if x > 15 else "STABLE")
    
    return health

def load_data(df, table_name, method="append"):
    """Loads data using append to preserve history."""
    if df.empty:
        return
    df.to_sql(table_name, engine, if_exists=method, index=False)
    logger.info(f"Successfully loaded {len(df)} rows to {table_name}")

def run_pipeline():
    try:
        # 1. Maintenance Task
        manage_partitions() # Ensure ingestion can continue

        # 2. Extract
        logs_df = extract_incremental_logs(minutes=60)
        if logs_df.empty:
            logger.info("No new logs found. Skipping transformation.")
            return

        # 3. Transform for Health Dashboard
        health_df = transform_health_metrics(logs_df)
        
        # 4. Load
        # We use 'replace' for the dashboard because it represents the CURRENT status
        load_data(health_df, "service_health_dashboard", method="replace")
        
        # Hourly volume is cumulative history, so we 'append'
        hourly_vol = logs_df.groupby([pd.to_datetime(logs_df["timestamp"]).dt.floor("H"), "level", "service_name"]).size().reset_index(name="count")
        load_data(hourly_vol, "analytics_volume_trends", method="append")

        logger.info("Pipeline run successful.")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")

if __name__ == "__main__":
    run_pipeline()


# TODO: Add anomaly detection (spike in error rate)
# TODO: Add service dependency mapping
# TODO: Add log retention compliance check