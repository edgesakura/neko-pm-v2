"""
Metrics query tools for SRE diagnostic agent.
Queries time-series metrics (CPU, memory, disk, network, latency) from monitoring systems.
In production, these would connect to Datadog, CloudWatch, or Prometheus.
For development/testing, they return realistic mock data.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../'))

from typing import Dict, List, Optional
from strands import tool

from common.mock_data import (
    generate_timestamps,
    generate_cpu_values,
    generate_memory_values,
    generate_latency_series,
    past_iso,
)
import logging
import random

logger = logging.getLogger(__name__)


def _clamp_duration(duration_minutes: int) -> int:
    """duration_minutes を 1〜1440 の範囲にクランプする。"""
    original = duration_minutes
    clamped = max(1, min(1440, duration_minutes))
    if clamped != original:
        logger.warning("duration_minutes clamped: %d -> %d", original, clamped)
    return clamped


@tool
def query_cpu_metrics(service: str, duration_minutes: int = 30) -> Dict:
    """
    Query CPU utilization time-series metrics for a given service.

    Retrieves per-pod and aggregate CPU usage over the specified time window.
    Useful for diagnosing CPU throttling, high load, and resource saturation.
    Returns data points at 1-minute intervals with average, max, and min values.

    Use this tool when:
    - Investigating high latency that may be caused by CPU throttling
    - Checking if a service is overloaded after a traffic spike
    - Verifying CPU usage after a deployment or scaling event

    Args:
        service: The service name to query (e.g., "payment-service", "order-service")
        duration_minutes: Time window in minutes to look back (default: 30)

    Returns:
        Dict with timestamps, values (list of CPU % per data point), avg, max, min, unit
    """
    duration_minutes = _clamp_duration(duration_minutes)
    spike = service in ("payment-service", "order-service")
    base = random.uniform(25.0, 55.0)
    values = generate_cpu_values(duration_minutes, base=base, spike=spike)
    timestamps = generate_timestamps(duration_minutes)

    return {
        "service": service,
        "metric": "cpu.utilization",
        "unit": "percent",
        "duration_minutes": duration_minutes,
        "data_points": [
            {"timestamp": ts, "value": v}
            for ts, v in zip(timestamps, values)
        ],
        "summary": {
            "avg": round(sum(values) / len(values), 2),
            "max": round(max(values), 2),
            "min": round(min(values), 2),
            "current": values[-1],
        },
        "source": "mock-datadog",
    }


@tool
def query_memory_metrics(service: str, duration_minutes: int = 30) -> Dict:
    """
    Query memory utilization time-series metrics for a given service.

    Retrieves heap and RSS memory usage over the specified time window.
    Useful for diagnosing OOMKilled pods, memory leaks, and oversized containers.
    Returns data points at 1-minute intervals.

    Use this tool when:
    - A pod is OOMKilled and you need to understand memory usage trend
    - Investigating gradual performance degradation (possible memory leak)
    - Sizing container memory requests and limits

    Args:
        service: The service name to query (e.g., "user-api", "auth-service")
        duration_minutes: Time window in minutes to look back (default: 30)

    Returns:
        Dict with timestamps, memory values (%), summary stats, and memory limit info
    """
    duration_minutes = _clamp_duration(duration_minutes)
    leak = service in ("user-api", "notification-worker")
    base = random.uniform(45.0, 70.0)
    values = generate_memory_values(duration_minutes, base=base, leak=leak)
    timestamps = generate_timestamps(duration_minutes)

    memory_limit_mib = 512 if service in ("user-api",) else 1024

    return {
        "service": service,
        "metric": "memory.utilization",
        "unit": "percent",
        "memory_limit_mib": memory_limit_mib,
        "duration_minutes": duration_minutes,
        "data_points": [
            {"timestamp": ts, "value": v, "value_mib": round(v / 100.0 * memory_limit_mib, 1)}
            for ts, v in zip(timestamps, values)
        ],
        "summary": {
            "avg": round(sum(values) / len(values), 2),
            "max": round(max(values), 2),
            "min": round(min(values), 2),
            "current": values[-1],
            "current_mib": round(values[-1] / 100.0 * memory_limit_mib, 1),
        },
        "trend": "increasing" if values[-1] > values[0] + 10 else "stable",
        "source": "mock-datadog",
    }


@tool
def query_disk_metrics(service: str, duration_minutes: int = 30) -> Dict:
    """
    Query disk I/O and disk usage metrics for a given service or host.

    Retrieves read/write throughput (MB/s), IOPS, and disk utilization percentage.
    Useful for diagnosing disk saturation, log disk full issues, and I/O bottlenecks.

    Use this tool when:
    - Investigating slow file I/O that may be causing latency
    - Checking if log volumes are filling up
    - Diagnosing storage-related performance issues

    Args:
        service: The service name or host to query (e.g., "batch-processor", "log-aggregator")
        duration_minutes: Time window in minutes to look back (default: 30)

    Returns:
        Dict with disk read/write throughput, IOPS, and disk usage percentage over time
    """
    duration_minutes = _clamp_duration(duration_minutes)
    timestamps = generate_timestamps(duration_minutes)
    base_read = random.uniform(5.0, 30.0)
    base_write = random.uniform(2.0, 20.0)
    disk_used_pct = random.uniform(40.0, 75.0)

    return {
        "service": service,
        "metric": "disk.io",
        "unit": "mbps",
        "disk_usage_percent": round(disk_used_pct, 1),
        "duration_minutes": duration_minutes,
        "data_points": [
            {
                "timestamp": ts,
                "read_mbps": round(base_read + random.uniform(-3, 8), 2),
                "write_mbps": round(base_write + random.uniform(-2, 5), 2),
                "read_iops": random.randint(100, 500),
                "write_iops": random.randint(50, 300),
            }
            for ts in timestamps
        ],
        "summary": {
            "avg_read_mbps": round(base_read, 2),
            "avg_write_mbps": round(base_write, 2),
            "disk_used_percent": round(disk_used_pct, 1),
            "disk_free_gb": round((100 - disk_used_pct) / 100 * 50, 1),
        },
        "source": "mock-cloudwatch",
    }


@tool
def query_network_metrics(service: str, duration_minutes: int = 30) -> Dict:
    """
    Query network throughput and error metrics for a given service.

    Retrieves inbound/outbound bytes per second, packet rate, TCP error rate,
    and connection counts. Useful for diagnosing network saturation, packet loss,
    and connection-level issues.

    Use this tool when:
    - Investigating high latency that may be network-related
    - Checking for packet drops or TCP retransmits
    - Verifying bandwidth usage during traffic spikes

    Args:
        service: The service name to query (e.g., "api-gateway", "payment-service")
        duration_minutes: Time window in minutes to look back (default: 30)

    Returns:
        Dict with network in/out bytes, packet rate, error rate, and connection count
    """
    duration_minutes = _clamp_duration(duration_minutes)
    timestamps = generate_timestamps(duration_minutes)
    base_in = random.uniform(10.0, 80.0)
    base_out = random.uniform(5.0, 40.0)

    return {
        "service": service,
        "metric": "network.throughput",
        "unit": "mbps",
        "duration_minutes": duration_minutes,
        "data_points": [
            {
                "timestamp": ts,
                "bytes_in_mbps": round(base_in + random.uniform(-5, 15), 2),
                "bytes_out_mbps": round(base_out + random.uniform(-3, 10), 2),
                "packets_in": random.randint(5000, 20000),
                "packets_out": random.randint(3000, 15000),
                "tcp_errors": random.randint(0, 5),
                "active_connections": random.randint(100, 800),
            }
            for ts in timestamps
        ],
        "summary": {
            "avg_in_mbps": round(base_in, 2),
            "avg_out_mbps": round(base_out, 2),
            "total_tcp_errors": random.randint(0, 30),
            "peak_connections": random.randint(500, 1200),
        },
        "source": "mock-datadog",
    }


@tool
def query_latency_metrics(
    service: str,
    duration_minutes: int = 30,
    percentiles: Optional[List[str]] = None,
) -> Dict:
    """
    Query HTTP request latency percentiles (P50/P95/P99) for a given service.

    Retrieves response time distributions at specified percentiles over the time window.
    Essential for diagnosing SLO breaches and identifying long-tail latency issues.
    High P99 with normal P50 indicates long-tail problems (slow queries, GC pauses).
    All percentiles elevated indicates overload or resource saturation.

    Use this tool when:
    - An alert fires for high latency on a service
    - Investigating P99 SLO breach
    - Comparing latency before and after a deployment
    - Identifying which endpoints are causing latency issues

    Args:
        service: The service name to query (e.g., "order-service", "payment-service")
        duration_minutes: Time window in minutes to look back (default: 30)
        percentiles: List of percentiles to include, e.g. ["p50", "p95", "p99"] (default: all three)

    Returns:
        Dict with per-percentile time series, current values, SLO status, and endpoint breakdown
    """
    duration_minutes = _clamp_duration(duration_minutes)
    if percentiles is None:
        percentiles = ["p50", "p95", "p99"]

    anomaly = service in ("order-service", "recommendation-service")
    series = generate_latency_series(
        duration_minutes,
        base_p50=120.0,
        base_p95=350.0,
        base_p99=800.0,
        anomaly=anomaly,
    )
    timestamps = generate_timestamps(duration_minutes)

    data_points = []
    for i, ts in enumerate(timestamps):
        point = {"timestamp": ts}
        for p in percentiles:
            if p in series:
                point[f"{p}_ms"] = series[p][i]
        data_points.append(point)

    current_p99 = series["p99"][-1] if "p99" in percentiles else None
    slo_threshold_ms = 1000
    slo_status = "BREACHING" if current_p99 and current_p99 > slo_threshold_ms else "OK"

    return {
        "service": service,
        "metric": "http.request.duration",
        "unit": "milliseconds",
        "percentiles": percentiles,
        "duration_minutes": duration_minutes,
        "data_points": data_points,
        "summary": {
            "current": {f"{p}_ms": series[p][-1] for p in percentiles if p in series},
            "max": {f"{p}_ms": max(series[p]) for p in percentiles if p in series},
        },
        "slo": {
            "threshold_ms": slo_threshold_ms,
            "status": slo_status,
            "percentile": "p99",
        },
        "source": "mock-datadog-apm",
    }
