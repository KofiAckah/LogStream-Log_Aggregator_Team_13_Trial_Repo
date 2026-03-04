"""
LogStream Retention Enforcer - Issue #28
Automates the 'Detach and Drop' strategy for expired log partitions.
"""
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
from config.config import DATABASE_URL
from utils.logger import get_logger

logger = get_logger("RetentionEnforcer")
engine = create_engine(DATABASE_URL)

def get_retention_policies():
    """Fetches active retention rules set by the admin."""
    query = "SELECT log_level, retention_days FROM retention_policies WHERE active = true"
    return pd.read_sql(query, engine)

def enforce_retention():
    policies = get_retention_policies()
    if policies.empty:
        logger.warning("No active retention policies found. Using default 30 days.")
        # Fallback to a global 30-day window
        policies = pd.DataFrame([{"log_level": "ALL", "retention_days": 30}])

    with engine.begin() as conn:
        for _, policy in policies.iterrows():
            # Calculate the cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=int(policy['retention_days']))
            partition_suffix = cutoff_date.strftime('%Y_%m_%d')
            target_partition = f"log_entries_y{partition_suffix}"

            try:
                # 1. Check if the specific partition exists
                exists_query = text("""
                    SELECT count(*) FROM pg_class c 
                    JOIN pg_namespace n ON n.oid = c.relnamespace 
                    WHERE c.relname = :partition
                """)
                result = conn.execute(exists_query, {"partition": target_partition}).scalar()

                if result > 0:
                    logger.info(f"Expiring logs for {policy['log_level']} on {partition_suffix}")
                    
                    # 2. Detach Partition (separates it from the main table)
                    conn.execute(text(f"ALTER TABLE log_entries DETACH PARTITION {target_partition};"))
                    
                    # 3. Drop (or you could move this to S3/Cold Storage here)
                    conn.execute(text(f"DROP TABLE {target_partition};"))
                    logger.info(f"Successfully dropped partition: {target_partition}")
                
            except Exception as e:
                logger.error(f"Failed to process partition {target_partition}: {e}")

if __name__ == "__main__":
    enforce_retention()