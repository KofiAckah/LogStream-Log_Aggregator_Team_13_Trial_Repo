import pytest
from datetime import datetime, timedelta

from scripts.data_generator import (
    generate_log,
    generate_logs,
    _realistic_timestamp,
    SERVICES
)

#Test Log Schema
def test_generate_log_schema():
    log = generate_log("auth-service", datetime.utcnow())

    assert isinstance(log, dict)

    expected_fields = {
        "id",
        "timestamp",
        "level",
        "source",
        "message",
        "service_name",
        "created_at",
    }

    assert set(log.keys()) == expected_fields
    
    

#Test Log Level Validity
def test_log_level_is_valid():
    log = generate_log("auth-service", datetime.utcnow())

    valid_levels = {"INFO", "DEBUG", "WARN", "ERROR", "TRACE"}

    assert log["level"] in valid_levels
    
    
#

def test_realistic_timestamp_range():
    start = datetime.utcnow() - timedelta(days=10)
    end = datetime.utcnow()

    ts = _realistic_timestamp(start, end)

    assert start <= ts <= end
    
    

#Test Multiple Log Generation
def test_generate_logs_count():
    services = list(SERVICES.keys())

    logs = generate_logs(services, num_logs=100)

    assert len(logs) <= 100
    
#Test Logs Are Sorted  
def test_logs_are_sorted():
    services = list(SERVICES.keys())

    logs = generate_logs(services, num_logs=200)

    timestamps = [log["timestamp"] for log in logs]

    assert timestamps == sorted(timestamps)
    
#Test Service Names   
def test_service_names_valid():
    services = list(SERVICES.keys())

    logs = generate_logs(services, num_logs=200)

    for log in logs:
        assert log["service_name"] in services


#Test Message is Not Empty
def test_log_message_not_empty():
    log = generate_log("auth-service", datetime.utcnow())

    assert isinstance(log["message"], str)
    assert len(log["message"]) > 5
    
#Test UUID Format
import uuid

def test_log_id_is_uuid():
    log = generate_log("auth-service", datetime.utcnow())

    uuid_obj = uuid.UUID(log["id"])

    assert str(uuid_obj) == log["id"]



#Test Large Generation 
def test_large_log_generation():
    services = list(SERVICES.keys())

    logs = generate_logs(services, num_logs=2000)

    assert len(logs) > 0