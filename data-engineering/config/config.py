import os
from dotenv import load_dotenv
load_dotenv()
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "logstream"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}
DATABASE_URL = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"





SERVICES = {
    "auth-service":         {"error_rate": 0.05},
    "payment-service":      {"error_rate": 0.15},
    "order-service":        {"error_rate": 0.08},
    "notification-service": {"error_rate": 0.03},
    "api-gateway":          {"error_rate": 0.02},   
    "user-service":         {"error_rate": 0.04},   
}


# Error spike configuration
ERROR_SPIKES = {
    "payment-service": {
        "probability": 0.02,      # 2% chance spike occurs
        "multiplier": 6,          # ERROR rate increases x6
        "duration_minutes": 20,
    },
    "order-service": {
        "probability": 0.015,
        "multiplier": 4,
        "duration_minutes": 15,
    },
}

# Service outage configuration
SERVICE_OUTAGES = {
    "notification-service": {
        "probability": 0.01,   # 1% chance outage occurs
        "duration_minutes": 30
    },
    "auth-service": {
        "probability": 0.008,
        "duration_minutes": 25
    }
}

# INFO=60%, DEBUG=20%, WARN=10%, ERROR=8%, TRACE=2%
LEVELS        = ["INFO", "DEBUG", "WARN", "ERROR", "TRACE"]
LEVEL_WEIGHTS = [0.60,   0.20,    0.10,   0.08,    0.02]


# Business-hours weighting — more logs during 08:00–18:00
_HOUR_WEIGHTS = [
    0.5, 0.3, 0.2, 0.2, 0.3, 0.5,   # 00-05
    0.8, 1.2, 2.0, 2.5, 2.5, 2.5,   # 06-11
    2.3, 2.5, 2.5, 2.3, 2.0, 1.8,   # 12-17
    1.5, 1.2, 1.0, 0.9, 0.7, 0.6,   # 18-23
]


ACTIVE_SPIKES = {}
ACTIVE_OUTAGES = {}


ERROR_MESSAGES = [
    "Database connection timeout after {n}ms",
    "JWT token expired for user session {n}",
    "Payment gateway unavailable — retry {n} of 3",
    "NullPointerException in OrderProcessor.validate() line {n}",
    "Cache miss threshold exceeded ({n}% misses)",
    "Authentication failed for user admin — invalid credentials",
    "Payment retry attempt {n} of 3 failed",
    "Circuit breaker OPEN after {n} consecutive failures",
    "Failed to acquire DB connection from pool (timeout={n}s)",
    "Order rollback triggered — insufficient inventory for item {n}",          # matches backend seed
]

INFO_MESSAGES = [
    "Request processed successfully in {n}ms",
    "User authenticated — session token issued",
    "Order #{n} created successfully",
    "Email notification dispatched to user {n}",
    "Metrics snapshot updated",
    "User registration completed successfully for ID {n}",
    "Scheduled job completed: log-cleanup removed {n} expired entries",
    "Service health check passed",
    "Payment of ${n} processed for order #{n}",
    "Batch of {n} records processed in {n}ms",
]

WARN_MESSAGES = [
    "Slow query detected: {n}ms exceeds 500ms threshold",
    "Retry attempt {n} of 3 for failed request",
    "Memory usage at {n}% — approaching limit",
    "Connection pool nearing limit ({n} of {n} used)",
    "Response time degraded: {n}ms average over last 60s",
    "Rate limit approaching for client token {n}",
]

DEBUG_MESSAGES = [
    "Cache lookup for key user:session:{n}",
    "Processing batch of {n} records",
    "Entering OrderProcessor.validate() with orderId={n}",
    "DB query returned {n} rows in {n}ms",
    "Token validation passed for sub=user_{n}",
    "Outbound HTTP POST /payments → 202 Accepted",
]

TRACE_MESSAGES = [
    "Method entry: processPayment(orderId={n})",
    "SQL: SELECT * FROM users WHERE id={n}",
    "HTTP GET /health → 200 OK",
    "Entering filter chain: JwtAuthFilter",
    "Stack frame: OrderService.create() → PaymentClient.charge()",
]

MESSAGE_MAP = {
    "ERROR": ERROR_MESSAGES,
    "INFO":  INFO_MESSAGES,
    "WARN":  WARN_MESSAGES,
    "DEBUG": DEBUG_MESSAGES,
    "TRACE": TRACE_MESSAGES,
}
