"""
Database health check tools for SRE diagnostic agent.
Checks RDS connection pool utilization and queries for slow database queries.
In production, these would query RDS Performance Insights, CloudWatch, and pg_stat_activity.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../'))

from typing import List, Dict, Optional
from strands import tool

from common.mock_data import past_iso
import logging
import random

logger = logging.getLogger(__name__)


@tool
def check_connection_pool(database: str = "main-rds") -> Dict:
    """
    Check RDS database connection pool utilization and wait statistics.

    Retrieves active connections, idle connections, pool maximum, wait queue depth,
    and average wait time. High connection pool utilization (> 80%) is a common
    cause of API 5xx errors as new requests cannot acquire a DB connection.

    Use this tool when:
    - Investigating API 5xx errors that may be caused by DB connection exhaustion
    - Checking if connection pool limits need to be increased
    - Verifying the impact of traffic spikes on DB connections
    - Diagnosing ETIMEDOUT errors in application logs

    Args:
        database: Database identifier (e.g., "main-rds", "analytics-rds", "auth-rds")

    Returns:
        Dict with connection counts (active, idle, waiting, max), utilization percent,
        avg wait time, and RDS instance info
    """
    db_configs = {
        "main-rds": {"max_connections": 100, "instance": "db.r6g.xlarge", "engine": "postgres14"},
        "analytics-rds": {"max_connections": 200, "instance": "db.r6g.2xlarge", "engine": "postgres14"},
        "auth-rds": {"max_connections": 50, "instance": "db.t3.medium", "engine": "postgres14"},
    }

    config = db_configs.get(database, {"max_connections": 100, "instance": "db.r6g.xlarge", "engine": "postgres14"})
    max_conn = config["max_connections"]

    # Simulate high utilization for main-rds
    if database == "main-rds":
        active = random.randint(75, 98)
        waiting = random.randint(5, 25)
    else:
        active = random.randint(20, 60)
        waiting = random.randint(0, 3)

    idle = random.randint(2, max(3, max_conn - active - waiting))
    total = active + idle
    utilization_pct = round(total / max_conn * 100, 1)

    return {
        "database": database,
        "instance_type": config["instance"],
        "engine": config["engine"],
        "connections": {
            "active": active,
            "idle": idle,
            "waiting": waiting,
            "total": total,
            "max": max_conn,
            "utilization_pct": utilization_pct,
        },
        "wait_stats": {
            "avg_wait_ms": round(waiting * 8.5, 1) if waiting > 0 else 0,
            "max_wait_ms": round(waiting * 25.0, 1) if waiting > 0 else 0,
            "timeout_count_last_5m": waiting // 3 if waiting > 10 else 0,
        },
        "status": "CRITICAL" if utilization_pct > 90 else ("WARNING" if utilization_pct > 75 else "OK"),
        "recommendation": (
            "Connection pool near exhaustion. Consider enabling PgBouncer or increasing RDS instance size."
            if utilization_pct > 85
            else "Connection pool utilization is normal."
        ),
        "checked_at": past_iso(0),
        "source": "mock-cloudwatch",
    }


@tool
def query_slow_queries(
    database: str = "main-rds",
    threshold_ms: int = 1000,
    limit: int = 10,
) -> List[Dict]:
    """
    Query the database for slow-running SQL queries exceeding the threshold.

    Retrieves queries that are taking longer than the specified threshold,
    including execution plan hints, table names, call frequency, and total time impact.
    Slow queries are a primary cause of high latency alerts and connection pool exhaustion.

    Use this tool when:
    - Investigating high latency alerts on services that use this database
    - Looking for N+1 query patterns or missing indexes after a deployment
    - Identifying the most impactful queries to optimize during an incident
    - Checking for lock contention or sequential scans on large tables

    Args:
        database: Database identifier to query (e.g., "main-rds", "analytics-rds")
        threshold_ms: Minimum query duration in milliseconds to include (default: 1000)
        limit: Maximum number of slow queries to return (default: 10)

    Returns:
        List of slow query dicts with SQL (truncated), duration_ms, call_count,
        total_time_ms, rows_examined, suggested_index, and plan_node_type
    """
    original_threshold = threshold_ms
    threshold_ms = max(1, min(60000, threshold_ms))
    if threshold_ms != original_threshold:
        logger.warning("threshold_ms clamped: %d -> %d", original_threshold, threshold_ms)

    slow_query_templates = [
        {
            "query": "SELECT * FROM orders o JOIN order_items oi ON o.id = oi.order_id WHERE o.user_id = $1",
            "duration_ms": random.randint(threshold_ms, threshold_ms * 8),
            "call_count": random.randint(50, 500),
            "rows_examined": random.randint(10000, 500000),
            "plan_node_type": "Seq Scan",
            "suggested_index": "CREATE INDEX idx_orders_user_id ON orders(user_id);",
            "table": "orders",
        },
        {
            "query": "SELECT p.*, pi.url FROM products p LEFT JOIN product_images pi ON p.id = pi.product_id WHERE p.category_id = $1 ORDER BY p.created_at DESC",
            "duration_ms": random.randint(threshold_ms, threshold_ms * 5),
            "call_count": random.randint(100, 1000),
            "rows_examined": random.randint(5000, 100000),
            "plan_node_type": "Seq Scan + Sort",
            "suggested_index": "CREATE INDEX idx_products_category_created ON products(category_id, created_at DESC);",
            "table": "products",
        },
        {
            "query": "UPDATE payments SET status = $1, updated_at = NOW() WHERE id = $2",
            "duration_ms": random.randint(threshold_ms, threshold_ms * 3),
            "call_count": random.randint(200, 2000),
            "rows_examined": 1,
            "plan_node_type": "Index Scan (waiting on lock)",
            "suggested_index": None,
            "table": "payments",
            "lock_info": "Waiting on row lock held by PID 4521 for 2.3s",
        },
        {
            "query": "SELECT COUNT(*) FROM audit_logs WHERE created_at >= $1 AND service = $2",
            "duration_ms": random.randint(threshold_ms * 2, threshold_ms * 12),
            "call_count": random.randint(10, 50),
            "rows_examined": random.randint(1000000, 10000000),
            "plan_node_type": "Seq Scan (no index on created_at)",
            "suggested_index": "CREATE INDEX idx_audit_logs_created_service ON audit_logs(created_at, service);",
            "table": "audit_logs",
        },
        {
            "query": "SELECT u.*, r.name as role_name FROM users u JOIN roles r ON u.role_id = r.id WHERE u.email = $1",
            "duration_ms": random.randint(threshold_ms, threshold_ms * 2),
            "call_count": random.randint(1000, 5000),
            "rows_examined": random.randint(100, 1000),
            "plan_node_type": "Seq Scan (email not indexed)",
            "suggested_index": "CREATE UNIQUE INDEX idx_users_email ON users(email);",
            "table": "users",
        },
    ]

    queries = random.sample(slow_query_templates, min(limit, len(slow_query_templates)))
    queries.sort(key=lambda x: x["duration_ms"], reverse=True)

    return [
        {
            "rank": i + 1,
            "query": q["query"],
            "database": database,
            "duration_ms": q["duration_ms"],
            "call_count_last_hour": q["call_count"],
            "total_time_ms_last_hour": q["duration_ms"] * q["call_count"],
            "rows_examined_avg": q["rows_examined"],
            "plan_node_type": q["plan_node_type"],
            "suggested_index": q.get("suggested_index"),
            "lock_info": q.get("lock_info"),
            "table": q["table"],
            "first_seen": past_iso(random.randint(60, 1440)),
        }
        for i, q in enumerate(queries[:limit])
    ]
