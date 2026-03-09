
"""
data_generator.py
Generates realistic sample logs whose field names exactly match
the backend team's log_entries table:
  id, timestamp, level, source, message, service_name, created_at
"""


#I want to simulate error Spikes  and service outages 
#simulates service outages

#simulates error spikes



import random
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
import argparse
from collections import Counter
from config.config import (SERVICE_OUTAGES,
SERVICES,
ERROR_SPIKES,
LEVELS, LEVEL_WEIGHTS ,
_HOUR_WEIGHTS ,ACTIVE_SPIKES,
ACTIVE_OUTAGES,ERROR_MESSAGES,
MESSAGE_MAP,TRACE_MESSAGES,DEBUG_MESSAGES,WARN_MESSAGES,INFO_MESSAGES)

LOG_DIR = Path("../data")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Services seeded in backend's data.sql
#We would have to log to file instead of print 



def _pick_message(level: str) -> str:
    template = random.choice(MESSAGE_MAP[level])
    # Replace every {n} placeholder with a random number
    parts  = template.split("{n}")
    result = parts[0]
    for part in parts[1:]:
        result += str(random.randint(1, 999)) + part
    return result
  


def _realistic_timestamp(start: datetime, end: datetime) -> datetime:
    """Pick a random timestamp weighted toward business hours."""
    delta_seconds = int((end - start).total_seconds())
    for _ in range(3):
        candidate = start + timedelta(seconds=random.randint(0, delta_seconds))
        if random.random() < _HOUR_WEIGHTS[candidate.hour] / 2.5:
            return candidate
    return candidate



def generate_log(service_name: str, base_time: datetime | None = None) -> dict | None:
    now = base_time or datetime.utcnow()


    # Handle Service Outage
    if service_name in ACTIVE_OUTAGES:
        if now < ACTIVE_OUTAGES[service_name]:
            return None
        else:
            del ACTIVE_OUTAGES[service_name]

    if service_name in SERVICE_OUTAGES:
        cfg = SERVICE_OUTAGES[service_name]
        if random.random() < cfg["probability"]:
            ACTIVE_OUTAGES[service_name] = now + timedelta(minutes=cfg["duration_minutes"])
            return None

    # Handle Error Spike
    weights = LEVEL_WEIGHTS.copy()

    if service_name in ACTIVE_SPIKES:
        if now < ACTIVE_SPIKES[service_name]:
            weights = [0.15, 0.05, 0.10, 0.65, 0.05]  # ERROR dominant
        else:
            del ACTIVE_SPIKES[service_name]

    if service_name in ERROR_SPIKES:
        cfg = ERROR_SPIKES[service_name]
        if random.random() < cfg["probability"]:
            ACTIVE_SPIKES[service_name] = now + timedelta(minutes=cfg["duration_minutes"])
            weights = [0.15, 0.05, 0.10, 0.65, 0.05]

    level = random.choices(LEVELS, weights=weights)[0]

    return {
        "id": str(uuid.uuid4()),
        "timestamp": now.isoformat(),
        "level": level,
        "source": service_name,
        "message": _pick_message(level),
        "service_name": service_name,
        "created_at": now.isoformat(),
    }


def generate_logs(services: list, num_logs: int = 5000, days: int = 30) -> list[dict]:
    """Generates logs spread over the past `days` days with business-hours weighting."""
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days)
    logs = []
    for _ in range(num_logs):
        service = random.choice(services)
        ts = _realistic_timestamp(start_time, end_time)
        log = generate_log(service, ts)
        if log:
            logs.append(log)
    logs.sort(key=lambda x: x["timestamp"])
    return logs
  
  


def print_summary(logs: list[dict]) -> None:
    total = len(logs)
    print(f"\n{'='*52}")
    print(f"  Total logs : {total:,}")
    print(f"\n  Level distribution:")
    for level, count in Counter(l["level"] for l in logs).most_common():
        pct = count / total * 100
        print(f"    {level:<7} {count:>6,}  ({pct:5.1f}%)  {'█' * int(pct/2)}")
    print(f"\n  Service distribution:")
    for svc, count in Counter(l["service_name"] for l in logs).most_common():
        pct = count / total * 100
        print(f"    {svc:<25} {count:>6,}  ({pct:5.1f}%)")
    print(f"{'='*52}\n")



def parse_args():
    parser = argparse.ArgumentParser(description="LogStream sample data generator")
    parser.add_argument("--services", nargs="+", default=list(SERVICES.keys()),
                        help="Service names to generate logs for")
    parser.add_argument("--count", type=int, default=5000,
                        help="Number of log entries to generate (default: 5000)")
    parser.add_argument("--days", type=int, default=30,
                        help="Spread logs over last N days (default: 30)")
    return parser.parse_args()


if __name__ == "__main__":
    logs = generate_logs(list(SERVICES.keys()), 10000)
    filename = LOG_DIR / f"logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w") as f:
        json.dump(logs, f, indent=2)
    print(f"Generated {len(logs)} logs → {filename}")