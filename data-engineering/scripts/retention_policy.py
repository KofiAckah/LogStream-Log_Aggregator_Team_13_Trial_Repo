"""
LogStream Retention Enforcer - Per-Service Archival
Enforces configurable retention policies per service and log level.
Archives expired rows to CSV before permanently deleting them.
"""
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
from pathlib import Path
from config.config import DATABASE_URL
from utils.logger import get_logger

logger = get_logger("RetentionEnforcer")
engine = create_engine(DATABASE_URL)


def get_retention_policies():
    """Fetches active retention rules set by the admin, including per-service policies."""
    query = "SELECT service_name, log_level, retention_days FROM retention_policies WHERE active = true"
    return pd.read_sql(query, engine)


def enforce_retention():
    """
    Enforces retention policies by:
    1. Building per-service WHERE clauses from the retention_policies table.
    2. Selecting expired rows matching each policy.
    3. Exporting them to a dated CSV archive.
    4. Deleting those exact rows from the database.
    
    If no policies exist, falls back to a global 30-day default for all services/levels.
    """
    policies = get_retention_policies()
    if policies.empty:
        logger.warning("No active retention policies found. Using default 30 days for all logs.")
        policies = pd.DataFrame([{"service_name": None, "log_level": None, "retention_days": 30}])

    archive_dir = Path(__file__).parent.parent / "archives"
    archive_dir.mkdir(parents=True, exist_ok=True)

    with engine.begin() as conn:
        for _, policy in policies.iterrows():
            service = policy.get("service_name")  # None = global
            level = policy.get("log_level")        # None = all levels
            retention_days = int(policy["retention_days"])
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

            # Build the dynamic WHERE clause
            conditions = ["timestamp < :cutoff"]
            params = {"cutoff": cutoff_date}

            if pd.notna(service):
                conditions.append("service_name = :service")
                params["service"] = service

            if pd.notna(level):
                conditions.append("level = :level")
                params["level"] = level

            where_clause = " AND ".join(conditions)
            policy_label = f"{service or 'ALL_SERVICES'}_{level or 'ALL_LEVELS'}_{cutoff_date.strftime('%Y%m%d')}"

            try:
                # 1. Select expired rows
                select_query = text(f"SELECT * FROM log_entries WHERE {where_clause}")
                expired_data = pd.read_sql(select_query, conn, params=params)

                if expired_data.empty:
                    logger.info(f"No expired logs found for policy [{policy_label}]. Skipping.")
                    continue

                # 2. Archive to CSV
                archive_file = archive_dir / f"archived_{policy_label}.csv"
                expired_data.to_csv(archive_file, index=False)
                logger.info(f"Archived {len(expired_data)} rows to {archive_file}")

                # 3. Delete the archived rows from the database
                delete_query = text(f"DELETE FROM log_entries WHERE {where_clause}")
                result = conn.execute(delete_query, params)
                logger.info(f"Deleted {result.rowcount} expired rows for policy [{policy_label}]")

            except Exception as e:
                logger.error(f"Failed to enforce policy [{policy_label}]: {e}")


if __name__ == "__main__":
    enforce_retention()