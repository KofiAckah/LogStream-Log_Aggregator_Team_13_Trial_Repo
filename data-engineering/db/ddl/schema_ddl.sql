-- Extension for Keyword/Trigram search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 1. Retention Policies (As defined by Backend)
CREATE TABLE retention_policies (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(100), -- nullable = global policy
    name VARCHAR(100),
    retention_days INTEGER DEFAULT 30,
    log_level VARCHAR(10) CHECK (log_level IN ('TRACE', 'DEBUG', 'INFO', 'WARN', 'ERROR')),
    active BOOLEAN DEFAULT true,
    UNIQUE (service_name, log_level) -- prevent duplicate policies
);

-- 2. Partitioned Log Entries
-- Note: PK must include the partition key (timestamp)
CREATE TABLE log_entries (
    id UUID DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL,
    level VARCHAR(10) NOT NULL CHECK (level IN ('TRACE', 'DEBUG', 'INFO', 'WARN', 'ERROR')),
    source VARCHAR(100),
    message TEXT NOT NULL,
    service_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (timestamp, id) 
) PARTITION BY RANGE (timestamp);

-- 3. Users Table (For Authentication)
-- Use the 'citext' extension for case-insensitive email storage
-- This prevents 'Admin@Amalitech.com' and 'admin@amalitech.com' from being dual-registered
CREATE EXTENSION IF NOT EXISTS citext;

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email CITEXT UNIQUE NOT NULL, -- Prevents duplicate emails regardless of casing
    name VARCHAR(100) NOT NULL,
    password TEXT NOT NULL, -- Store Bcrypt/Argon2 hashes here
    role VARCHAR(20) NOT NULL CHECK (role IN ('ADMIN', 'USER')),
    active BOOLEAN DEFAULT true,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexing for authentication
-- When a user logs in, the Java backend will query 'WHERE email = ?'
CREATE INDEX idx_users_email ON users (email);

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