"""
pandas_analytics.py
====================
Pandas equivalents of the four SQL analytics queries in this directory.
Produces identical results to the SQL queries when run against the same data.

These functions accept a pre-loaded and cleaned DataFrame (output of
clean_and_validate() in data_analytics.py). In the future this DataFrame
will be sourced from MinIO; for now load from the generated CSV/JSON file.

Field contract (matches backend log_entries table):
    id, timestamp, level, source, message, service_name, created_at
"""

from datetime import datetime, timedelta,timezone
from dataclasses import dataclass, field
import pandas as pd
from config.config import (VALID_LEVELS,REQUIRED_COLS)
from scripts.utils.logger import get_logger 



logger = get_logger(__name__)




@dataclass
class ValidationReport:
    total_rows:        int = 0
    valid_rows:        int = 0
    invalid_rows:      int = 0
    issues:            dict = field(default_factory=dict)

    def passed(self) -> bool:
        return self.invalid_rows == 0

    def summary(self) -> str:
        lines = [
            f"\n{'='*55}",
            f"  Validation Report",
            f"  Total rows   : {self.total_rows:,}",
            f"  Valid rows   : {self.valid_rows:,}",
            f"  Invalid rows : {self.invalid_rows:,}",
        ]
        if self.issues:
            lines.append("  Issues found :")
            for check, count in self.issues.items():
                lines.append(f"    ✗ {check:<40} {count:>6,} rows affected")
        else:
            lines.append("  ✓ All checks passed")
        lines.append(f"{'='*55}\n")
        return "\n".join(lines)




def validate(df: pd.DataFrame, raise_on_error: bool = False) -> tuple[pd.DataFrame, ValidationReport]:
    """
    Validates the raw DataFrame against the log_entries field contract.
    Returns a cleaned DataFrame and a ValidationReport.

    Checks performed:
      1. Required columns present
      2. No completely empty rows
      3. service_name not null or blank
      4. level is one of TRACE/DEBUG/INFO/WARN/ERROR
      5. message not null or blank
      6. timestamp is parseable
      7. No duplicate IDs
      8. timestamp not in the future (clock skew guard)
      9. service_name does not exceed 100 chars (matches DB constraint)
     10. message is not suspiciously short (< 3 chars)
    """
    report = ValidationReport(total_rows=len(df))
    issues = {}
    mask_invalid = pd.Series(False, index=df.index)


    missing_cols = REQUIRED_COLS - set(df.columns)
    if missing_cols:
        raise ValueError(f"[validate] Missing required columns: {missing_cols}")

    empty_mask = df.isna().all(axis=1)
    if empty_mask.any():
        issues["Completely empty rows"] = int(empty_mask.sum())
        mask_invalid |= empty_mask

    bad_service = df["service_name"].isna() | (df["service_name"].astype(str).str.strip() == "")
    if bad_service.any():
        issues["service_name null or blank"] = int(bad_service.sum())
        mask_invalid |= bad_service
        
    normalized_level = df["level"].astype(str).str.upper().str.strip()
    bad_level = ~normalized_level.isin(VALID_LEVELS)
    if bad_level.any():
        issues["level not in TRACE/DEBUG/INFO/WARN/ERROR"] = int(bad_level.sum())
        mask_invalid |= bad_level
    else:
        df["level"] = normalized_level  # normalize in place


    bad_msg = df["message"].isna() | (df["message"].astype(str).str.strip() == "")
    if bad_msg.any():
        issues["message null or blank"] = int(bad_msg.sum())
        mask_invalid |= bad_msg

    # ── 6. Unparseable timestamp ────────────────────────────────────────────
    parsed_ts = pd.to_datetime(df["timestamp"], utc=True, errors="coerce").dt.tz_localize(None)
    bad_ts = parsed_ts.isna()
    if bad_ts.any():
        issues["timestamp unparseable"] = int(bad_ts.sum())
        mask_invalid |= bad_ts
    else:
        df["timestamp"] = parsed_ts

    # Duplicate IDs 
    dup_ids = df.duplicated(subset=["id"], keep="first")
    if dup_ids.any():
        issues["Duplicate id (keeping first)"] = int(dup_ids.sum())
        mask_invalid |= dup_ids
        
    df["timestamp"] = pd.to_datetime(df["timestamp"],errors="coerce")
    
    #drop unparseable timestamps 
    bad_ts_mask = df["timestamp"].isna()
    
    if bad_ts_mask.any():
        issues["timestamp unparseable"] = int(bad_ts_mask.sum())   
        mask_invalid |= bad_ts_mask
    
    # Future timestamps (allow 60s clock skew)
    future_mask = df["timestamp"] > datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=60)
    if future_mask.any():
        issues["timestamp in the future"] = int(future_mask.sum()) 
        mask_invalid |= future_mask

    #service_name too long
    too_long_svc = df["service_name"].astype(str).str.len() > 100
    if too_long_svc.any():
        issues["service_name exceeds 100 chars"] = int(too_long_svc.sum())
        mask_invalid |= too_long_svc

    #Suspiciously short message
    short_msg = df["message"].astype(str).str.strip().str.len() < 3
    if short_msg.any():
        issues["message shorter than 3 chars"] = int(short_msg.sum())
        mask_invalid |= short_msg

    #Build clean DataFrame
    clean_df = df[~mask_invalid].reset_index(drop=True)

    report.invalid_rows = int(mask_invalid.sum())
    report.valid_rows   = len(clean_df)
    report.issues       = issues

    logger.info(report.summary())

    if raise_on_error and not report.passed():
        raise ValueError(f"Validation failed: {report.invalid_rows:,} invalid rows found.")

    return clean_df, report




# Helpers

def _load_df(path: str) -> pd.DataFrame:
    """Load a generated log file (JSON or CSV) into a raw DataFrame."""
    if path.endswith(".json"):
        df = pd.read_json(path)
    else:
        df = pd.read_csv(path)
    return df


def _window(df: pd.DataFrame, days: int = 0, hours: int = 0) -> pd.DataFrame:
    """Return rows within the last N days or hours."""
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days, hours=hours)
    return df[df["timestamp"] >= cutoff]



def error_rate_24h(df: pd.DataFrame, service_name: str = None) -> pd.DataFrame:
    """
    Error rate per service for the last 24 hours.

    Parameters
    ----------
    df           : cleaned log DataFrame
    service_name : optional filter to a single service

    Returns
    -------
    DataFrame with columns: service_name, total_logs, error_count, error_rate_percent
    """
    data = _window(df, hours=24)
    if service_name:
        data = data[data["service_name"] == service_name]

    if data.empty:
        return pd.DataFrame(columns=["service_name", "total_logs", "error_count", "error_rate_percent"])

    result = (
        data.groupby("service_name")
        .agg(
            total_logs=("level", "count"),
            error_count=("level", lambda x: (x == "ERROR").sum()),
        )
        .assign(error_rate_percent=lambda d: (d["error_count"] / d["total_logs"] * 100).round(2))
        .reset_index()
        .sort_values("error_rate_percent", ascending=False)
    )
    return result




def common_errors_top_n(df: pd.DataFrame, top_n: int = 10, service_name: str = None, days_back: int = 30) -> pd.DataFrame:
    """
    Top N most frequent ERROR messages per service.

    Parameters
    ----------
    df           : cleaned log DataFrame
    top_n        : number of results to return (default 10)
    service_name : optional filter to a single service
    days_back    : look-back window in days (default 30)

    Returns
    -------
    DataFrame with columns: service_name, message, occurrences
    """
    data = _window(df, days=days_back)
    data = data[data["level"] == "ERROR"]
    if service_name:
        data = data[data["service_name"] == service_name]

    if data.empty:
        return pd.DataFrame(columns=["service_name", "message", "occurrences"])

    result = (
        data.groupby(["service_name", "message"])
        .size()
        .reset_index(name="occurrences")
        .sort_values("occurrences", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
    return result




def volume_trends_hourly(df: pd.DataFrame, service_name: str = None, days_back: int = 7) -> pd.DataFrame:
    """
    Log volume per service broken down by hour.

    Parameters
    ----------
    df           : cleaned log DataFrame
    service_name : optional filter to a single service
    days_back    : look-back window in days (default 7)

    Returns
    -------
    DataFrame with columns: hour, service_name, level, log_count
    """
    data = _window(df, days=days_back)
    if service_name:
        data = data[data["service_name"] == service_name]

    if data.empty:
        return pd.DataFrame(columns=["hour", "service_name", "level", "log_count"])

    data = data.copy()
    data["hour"] = data["timestamp"].dt.floor("h")

    result = (
        data.groupby(["hour", "service_name", "level"])
        .size()
        .reset_index(name="log_count")
        .sort_values(["hour", "service_name", "level"])
        .reset_index(drop=True)
    )
    return result




def volume_trends_daily(df: pd.DataFrame, service_name: str = None, days_back: int = 30) -> pd.DataFrame:
    """
    Log volume per service broken down by day.

    Parameters
    ----------
    df           : cleaned log DataFrame
    service_name : optional filter to a single service
    days_back    : look-back window in days (default 30)

    Returns
    -------
    DataFrame with columns: day, service_name, level, log_count
    """
    data = _window(df, days=days_back)
    if service_name:
        data = data[data["service_name"] == service_name]

    if data.empty:
        return pd.DataFrame(columns=["day", "service_name", "level", "log_count"])

    data = data.copy()
    data["day"] = data["timestamp"].dt.floor("D")

    result = (
        data.groupby(["day", "service_name", "level"])
        .size()
        .reset_index(name="log_count")
        .sort_values(["day", "service_name", "level"])
        .reset_index(drop=True)
    )
    return result




# WARN rate per service — last 24 hours
# Equivalent to: vw_warn_rate_24h

def warn_rate_24h(df: pd.DataFrame) -> pd.DataFrame:
    """
    WARN rate per service for the last 24 hours.
    WARNs are leading indicators — a rising warn rate often precedes errors.

    Returns
    -------
    DataFrame with columns: service_name, total_logs, warn_count, warn_rate_percent
    """
    data = _window(df, hours=24)
    if data.empty:
        return pd.DataFrame(columns=["service_name", "total_logs", "warn_count", "warn_rate_percent"])

    return (
        data.groupby("service_name")
        .agg(
            total_logs=("level", "count"),
            warn_count=("level", lambda x: (x == "WARN").sum()),
        )
        .assign(warn_rate_percent=lambda d: (d["warn_count"] / d["total_logs"] * 100).round(2))
        .reset_index()
        .sort_values("warn_rate_percent", ascending=False)
    )



# Log level distribution per service — last 30 days
# Equivalent to: vw_level_distribution

def level_distribution(df: pd.DataFrame, days_back: int = 30) -> pd.DataFrame:
    """
    Log level breakdown per service as counts and percentages.
    Useful as a stacked bar chart in Metabase.

    Returns
    -------
    DataFrame with columns: service_name, level, log_count, pct_of_service_total
    """
    data = _window(df, days=days_back)
    if data.empty:
        return pd.DataFrame(columns=["service_name", "level", "log_count", "pct_of_service_total"])

    counts = (
        data.groupby(["service_name", "level"])
        .size()
        .reset_index(name="log_count")
    )
    totals = counts.groupby("service_name")["log_count"].transform("sum")
    counts["pct_of_service_total"] = (counts["log_count"] / totals * 100).round(2)
    return counts.sort_values(["service_name", "level"]).reset_index(drop=True)



# Service activity heatmap — hour of day × day of week
#    Equivalent to: vw_activity_heatmap

def activity_heatmap(df: pd.DataFrame, days_back: int = 30) -> pd.DataFrame:
    """
    Log volume by hour-of-day and day-of-week per service.
    Feed directly into a Metabase pivot/heatmap panel.

    Returns
    -------
    DataFrame with columns: service_name, day_of_week, hour_of_day, log_count
    """
    data = _window(df, days=days_back).copy()
    if data.empty:
        return pd.DataFrame(columns=["service_name", "day_of_week", "hour_of_day", "log_count"])

    data["day_of_week"] = data["timestamp"].dt.dayofweek   # 0=Mon … 6=Sun
    data["hour_of_day"] = data["timestamp"].dt.hour

    return (
        data.groupby(["service_name", "day_of_week", "hour_of_day"])
        .size()
        .reset_index(name="log_count")
        .sort_values(["service_name", "day_of_week", "hour_of_day"])
        .reset_index(drop=True)
    )



#Error spike detection — current 1h vs 7-day daily average
#Equivalent to: vw_error_spike_detection

def error_spike_detection(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compares each service's errors in the last 1 hour against its
    7-day daily error average. spike_ratio > 1.5 = ELEVATED, > 3 = CRITICAL.

    Returns
    -------
    DataFrame with columns:
        service_name, avg_daily_errors_7d, errors_last_1h,
        spike_ratio, spike_status
    """
    # 7-day daily baseline
    week_data = _window(df, days=7).copy()
    week_data["day"] = week_data["timestamp"].dt.floor("D")
    baseline = (
        week_data[week_data["level"] == "ERROR"]
        .groupby(["service_name", "day"])
        .size()
        .reset_index(name="daily_errors")
        .groupby("service_name")["daily_errors"]
        .mean()
        .round(2)
        .reset_index(name="avg_daily_errors_7d")
    )

    # Last 1 hour errors
    current = (
        _window(df, hours=1)
        .query("level == 'ERROR'")
        .groupby("service_name")
        .size()
        .reset_index(name="errors_last_1h")
    )

    result = baseline.merge(current, on="service_name", how="left").fillna({"errors_last_1h": 0})
    result["errors_last_1h"] = result["errors_last_1h"].astype(int)
    result["spike_ratio"] = (
        result["errors_last_1h"] * 24.0 / result["avg_daily_errors_7d"].replace(0, float("nan"))
    ).round(2)

    def _status(r):
        if r["spike_ratio"] > 3:   return "CRITICAL"
        if r["spike_ratio"] > 1.5: return "ELEVATED"
        return "NORMAL"

    result["spike_status"] = result.apply(_status, axis=1)
    return result.sort_values("spike_ratio", ascending=False).reset_index(drop=True)



# Silent services — no logs in last N minutes
# Equivalent to: vw_silent_services

def silent_services(df: pd.DataFrame, silent_minutes: int = 10) -> pd.DataFrame:
    """
    Services that have not emitted any log in the last `silent_minutes`.
    A service that stops logging may have crashed or been scaled down.

    Returns
    -------
    DataFrame with columns: service_name, last_log_at, minutes_silent
    """
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=silent_minutes)
    last_seen = (
        df.groupby("service_name")["timestamp"]
        .max()
        .reset_index(name="last_log_at")
    )
    silent = last_seen[last_seen["last_log_at"] < cutoff].copy()
    silent["minutes_silent"] = (
        (datetime.now(timezone.utc).replace(tzinfo=None) - silent["last_log_at"]).dt.total_seconds() / 60
    ).round(1)
    return silent.sort_values("last_log_at").reset_index(drop=True)



# Top noisy services — last 24 hours
# Equivalent to: vw_top_noisy_services

def top_noisy_services(df: pd.DataFrame) -> pd.DataFrame:
    """
    Services ranked by log volume in the last 24 hours.
    Useful for identifying services driving storage and retention cost.

    Returns
    -------
    DataFrame with columns: service_name, total_logs, pct_of_total
    """
    data = _window(df, hours=24)
    if data.empty:
        return pd.DataFrame(columns=["service_name", "total_logs", "pct_of_total"])

    counts = data.groupby("service_name").size().reset_index(name="total_logs")
    counts["pct_of_total"] = (counts["total_logs"] / counts["total_logs"].sum() * 100).round(2)
    return counts.sort_values("total_logs", ascending=False).reset_index(drop=True)



# Mean time between errors per service — last 7 days
# Equivalent to: vw_mtbe_per_service

def mean_time_between_errors(df: pd.DataFrame, days_back: int = 7) -> pd.DataFrame:
    """
    Average minutes between consecutive ERROR logs per service.
    Higher value = more reliable service.

    Returns
    -------
    DataFrame with columns: service_name, total_errors, avg_minutes_between_errors
    """
    data = _window(df, days=days_back)
    errors = data[data["level"] == "ERROR"].copy().sort_values("timestamp")

    if errors.empty:
        return pd.DataFrame(columns=["service_name", "total_errors", "avg_minutes_between_errors"])

    errors["prev_ts"] = errors.groupby("service_name")["timestamp"].shift(1)
    errors["gap_minutes"] = (
        (errors["timestamp"] - errors["prev_ts"]).dt.total_seconds() / 60
    )

    return (
        errors.dropna(subset=["gap_minutes"])
        .groupby("service_name")
        .agg(
            total_errors=("level", "count"),
            avg_minutes_between_errors=("gap_minutes", lambda x: round(x.mean(), 1)),
        )
        .reset_index()
        .sort_values("avg_minutes_between_errors")
    )



#Recent critical events — last 50 errors
# Equivalent to: vw_recent_critical_events

def recent_critical_events(df: pd.DataFrame, limit: int = 50) -> pd.DataFrame:
    """
    Most recent ERROR logs across all services.
    Designed for a live feed / alert panel in Metabase.

    Returns
    -------
    DataFrame with columns: timestamp, service_name, level, message
    """
    return (
        df[df["level"] == "ERROR"]
        [["timestamp", "service_name", "level", "message"]]
        .sort_values("timestamp", ascending=False)
        .head(limit)
        .reset_index(drop=True)
    )
    
    


    
if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "./data/logs_20260305_092708.json"
    logger.info(f"Loading: {path}")
    raw_df = _load_df(path)
    logger.info(f"Loaded {len(raw_df):,} raw records")

    # Always validate before running any analytics
    df, report = validate(raw_df)
    if not report.passed():
        logger.warning(f"{report.invalid_rows:,} invalid rows dropped before analytics.")


    logger.info("\nError Rate (24h)\n%s", error_rate_24h(df).to_string(index=False))

    logger.info("\n── Top 10 Common Errors (30d) ────────────────────\n%s",
            common_errors_top_n(df).to_string(index=False))
    
    logger.info("\n── Hourly Volume Trends (7d) ─────────────────────\n%s",
            volume_trends_hourly(df).head(20).to_string(index=False))

    logger.info("\n── Daily Volume Trends (30d) ─────────────────────\n%s",
            volume_trends_daily(df).head(20).to_string(index=False))

    logger.info("\n── Warn Rate (24h) ──────────────────────────────\n%s",
            warn_rate_24h(df).to_string(index=False))

    logger.info("\n── Level Distribution (30d) ─────────────────────\n%s",
            level_distribution(df).to_string(index=False))

    logger.info("\n── Service Activity Heatmap (30d) ───────────────\n%s",
            activity_heatmap(df).head(20).to_string(index=False))

    logger.info("\n── Error Spike Detection ─────────────────────────\n%s",
            error_spike_detection(df).to_string(index=False))

    logger.info("\n── Silent Services (last 10 min) ────────────────\n%s",
            silent_services(df).to_string(index=False))


    logger.info("\n── Top Noisy Services (24h) ─────────────────────\n%s",
            top_noisy_services(df).to_string(index=False))


    logger.info("\n── Mean Time Between Errors (7d) ────────────────\n%s",
            mean_time_between_errors(df).to_string(index=False))


    logger.info("\n── Recent Critical Events (last 50) ─────────────\n%s",
            recent_critical_events(df).to_string(index=False))