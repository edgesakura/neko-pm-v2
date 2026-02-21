"""
Mock data generation utilities for SRE Agent tools.
Provides helpers for generating realistic time-series metrics, logs, and status data.
"""
import random
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional


def now_iso() -> str:
    """Return current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def past_iso(minutes_ago: int) -> str:
    """Return UTC time N minutes ago in ISO 8601 format."""
    dt = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return dt.isoformat()


def generate_timestamps(duration_minutes: int, interval_minutes: int = 1) -> List[str]:
    """Generate a list of ISO timestamps from (now - duration) to now."""
    now = datetime.now(timezone.utc)
    timestamps = []
    for i in range(duration_minutes, -1, -interval_minutes):
        ts = now - timedelta(minutes=i)
        timestamps.append(ts.isoformat())
    return timestamps


def generate_cpu_values(duration_minutes: int, base: float = 35.0, spike: bool = False) -> List[float]:
    """
    Generate realistic CPU usage percentages.
    spike=True simulates a sudden CPU spike near the end of the period.
    """
    values = []
    for i in range(duration_minutes + 1):
        if spike and i > duration_minutes * 0.8:
            val = min(100.0, base + random.uniform(30, 50))
        else:
            val = base + random.uniform(-5, 10)
        values.append(round(max(0.0, min(100.0, val)), 2))
    return values


def generate_memory_values(duration_minutes: int, base: float = 60.0, leak: bool = False) -> List[float]:
    """
    Generate realistic memory usage percentages.
    leak=True simulates a gradual memory leak trend.
    """
    values = []
    for i in range(duration_minutes + 1):
        trend = (i / duration_minutes) * 20.0 if leak else 0.0
        val = base + trend + random.uniform(-3, 5)
        values.append(round(max(0.0, min(100.0, val)), 2))
    return values


def generate_latency_series(
    duration_minutes: int,
    base_p50: float = 120.0,
    base_p95: float = 350.0,
    base_p99: float = 800.0,
    anomaly: bool = False,
) -> Dict[str, List[float]]:
    """
    Generate P50/P95/P99 latency time series in milliseconds.
    anomaly=True simulates high latency period near the end.
    """
    p50_vals, p95_vals, p99_vals = [], [], []
    for i in range(duration_minutes + 1):
        multiplier = random.uniform(1.0, 3.5) if (anomaly and i > duration_minutes * 0.75) else 1.0
        p50_vals.append(round(base_p50 * multiplier + random.uniform(-20, 30), 1))
        p95_vals.append(round(base_p95 * multiplier + random.uniform(-50, 80), 1))
        p99_vals.append(round(base_p99 * multiplier + random.uniform(-100, 200), 1))
    return {"p50": p50_vals, "p95": p95_vals, "p99": p99_vals}


def generate_error_rate_series(
    duration_minutes: int,
    base_rate: float = 0.5,
    spike: bool = False,
) -> List[float]:
    """
    Generate HTTP 5xx error rate percentages over time.
    spike=True simulates a sudden error spike.
    """
    values = []
    for i in range(duration_minutes + 1):
        if spike and i > duration_minutes * 0.7:
            val = base_rate + random.uniform(8, 15)
        else:
            val = base_rate + random.uniform(-0.3, 0.5)
        values.append(round(max(0.0, val), 2))
    return values


def generate_log_entry(
    service: str,
    level: str = "ERROR",
    message: Optional[str] = None,
    minutes_ago_range: tuple = (0, 30),
) -> Dict[str, Any]:
    """Generate a single realistic log entry."""
    error_messages = {
        "ERROR": [
            f"Connection refused: unable to connect to downstream service",
            f"Timeout after 30s waiting for response from db-primary",
            f"NullPointerException in {service}.handleRequest()",
            f"Circuit breaker OPEN: too many failures in 5s window",
            f"HTTP 503 Service Unavailable from upstream dependency",
        ],
        "WARN": [
            f"Response time exceeded SLO threshold: 2100ms",
            f"Retrying request (attempt 2/3) to payment-gateway",
            f"Connection pool near capacity: 95/100 connections used",
            f"GC pause detected: 850ms stop-the-world",
        ],
        "INFO": [
            f"Request processed successfully in 142ms",
            f"Health check passed",
            f"Cache hit ratio: 87.3%",
        ],
    }
    msgs = error_messages.get(level, error_messages["INFO"])
    return {
        "timestamp": past_iso(random.randint(*minutes_ago_range)),
        "level": level,
        "service": service,
        "message": message or random.choice(msgs),
        "trace_id": f"trace-{random.randint(100000, 999999):06x}",
        "span_id": f"span-{random.randint(10000, 99999):05x}",
        "host": f"{service}-{random.randint(1, 5):02d}",
    }


def generate_pod_status(
    name: str,
    namespace: str = "production",
    phase: str = "Running",
    restart_count: int = 0,
    ready: bool = True,
) -> Dict[str, Any]:
    """Generate a realistic Kubernetes pod status dict."""
    return {
        "name": name,
        "namespace": namespace,
        "phase": phase,
        "ready": ready,
        "restart_count": restart_count,
        "last_restart": past_iso(restart_count * 2) if restart_count > 0 else None,
        "node": f"ip-10-0-{random.randint(1, 9)}-{random.randint(100, 254)}.ap-northeast-1.compute.internal",
        "age_minutes": random.randint(60, 1440),
        "containers": [
            {
                "name": name.split("-")[0],
                "image": f"ecr.amazonaws.com/{name.split('-')[0]}:latest",
                "ready": ready,
                "restart_count": restart_count,
                "last_termination_reason": "OOMKilled" if restart_count > 5 else None,
            }
        ],
    }
