-- Extension for Keyword/Trigram search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 1. Retention Policies (As defined by Backend)
CREATE TABLE retention_policies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    retention_days INTEGER DEFAULT 30,
    log_level VARCHAR(10), -- TRACE, DEBUG, INFO, WARN, ERROR
    active BOOLEAN DEFAULT true
);

-- 2. Partitioned Log Entries
-- Note: PK must include the partition key (timestamp)
CREATE TABLE log_entries (
    id UUID DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL,
    level VARCHAR(10) NOT NULL,
    source VARCHAR(100),
    message TEXT NOT NULL,
    service_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (timestamp, id) 
) PARTITION BY RANGE (timestamp);

-- 3. Initial Partition (Required so the app doesn't crash on the first INSERT)
CREATE TABLE log_entries_default PARTITION OF log_entries DEFAULT;

-- For Backend Dev B: Search by service, level, and time
CREATE INDEX idx_logs_search_lookup 
ON log_entries (service_name, level, timestamp DESC);

-- For Backend Dev C: Volume trends and Error rates (Aggregations)
-- BRIN is extremely efficient for large time-series scans.
CREATE INDEX idx_logs_volume_brin 
ON log_entries USING BRIN (timestamp);

-- For Keyword search in the message field
CREATE INDEX idx_logs_msg_search 
ON log_entries USING GIN (message gin_trgm_ops);