"""
Log query tools for SRE diagnostic agent.
Searches application, infrastructure, and audit logs for error investigation.
In production, these would query Datadog Logs, CloudWatch Logs Insights, or Elasticsearch.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../'))

from typing import List, Dict, Optional
from strands import tool

from common.mock_data import generate_log_entry, past_iso
import logging
import random

logger = logging.getLogger(__name__)


def _clamp_limit(limit: int) -> int:
    """limit を 1〜1000 の範囲にクランプする。"""
    original = limit
    clamped = max(1, min(1000, limit))
    if clamped != original:
        logger.warning("limit clamped: %d -> %d", original, clamped)
    return clamped


@tool
def query_application_logs(
    service: str,
    level: str = "ERROR",
    limit: int = 20,
) -> List[Dict]:
    """
    Search application logs for a given service, filtered by log level.

    Retrieves structured log entries from the application logging system.
    Useful for identifying exception stack traces, error messages, and
    application-level failures that correlate with alerts.

    Use this tool when:
    - Investigating 5xx errors to find the underlying exception or stack trace
    - Looking for specific error patterns after a deployment
    - Identifying which requests are failing and why
    - Checking if circuit breakers or retries are firing

    Args:
        service: The service name to query logs for (e.g., "payment-service", "user-api")
        level: Log level filter: "ERROR", "WARN", "INFO", "DEBUG" (default: "ERROR")
        limit: Maximum number of log entries to return (default: 20)

    Returns:
        List of log entry dicts with timestamp, level, message, trace_id, span_id, host
    """
    limit = _clamp_limit(limit)
    error_templates = {
        "payment-service": [
            "PaymentGatewayException: Stripe API timeout after 30000ms",
            "DatabaseException: FATAL: remaining connection slots are reserved",
            "CircuitBreaker[payment-gateway] OPEN: failure rate 68.5% > threshold 50%",
            "TransactionRollbackException: deadlock detected on table 'payments'",
            "java.net.SocketTimeoutException: Read timed out after 5000ms",
        ],
        "user-api": [
            "NullPointerException: Cannot read property 'id' of undefined at UserController",
            "UnauthorizedException: JWT token expired at 2026-02-18T10:25:00Z",
            "PoolError: timeout acquiring connection from pool (waited 30000ms)",
            "RedisError: READONLY You can't write against a read only replica",
            "ValidationError: email must be a valid email address",
        ],
        "order-service": [
            "SlowQueryWarning: query took 8542ms: SELECT * FROM orders JOIN ...",
            "InventoryServiceException: HTTP 503 from inventory-service",
            "TooManyConnectionsException: max_connections=100 exceeded",
            "TimeoutError: Request to payment-service timed out after 3000ms",
            "DataIntegrityViolationException: duplicate key value violates unique constraint",
        ],
    }

    templates = error_templates.get(service, [
        f"ConnectionRefusedError: unable to connect to downstream service",
        f"TimeoutError: operation exceeded 30s timeout",
        f"InternalServerError: unexpected error in request handler",
        f"ServiceUnavailableException: upstream dependency returned 503",
    ])

    logs = []
    for i in range(min(limit, random.randint(8, 20))):
        entry = generate_log_entry(
            service=service,
            level=level,
            message=random.choice(templates),
            minutes_ago_range=(0, 30),
        )
        logs.append(entry)

    logs.sort(key=lambda x: x["timestamp"], reverse=True)
    return logs[:limit]


@tool
def query_infrastructure_logs(
    host: Optional[str] = None,
    source: str = "syslog",
    limit: int = 20,
) -> List[Dict]:
    """
    Search infrastructure-level logs from hosts, system daemons, and Kubernetes components.

    Retrieves system logs including kernel messages, kubelet events, Docker daemon logs,
    and OS-level errors. Useful for diagnosing node-level issues that affect multiple
    pods or services running on the same host.

    Use this tool when:
    - A node shows unhealthy status in Kubernetes
    - Multiple pods on the same node are experiencing issues
    - OOMKilled events suggest node memory pressure
    - Investigating disk I/O or network issues at the host level

    Args:
        host: Specific host/node name to filter (e.g., "ip-10-0-1-205.ap-northeast-1.compute.internal")
              If None, returns logs from all hosts
        source: Log source: "syslog", "kubelet", "docker", "kernel" (default: "syslog")
        limit: Maximum number of log entries to return (default: 20)

    Returns:
        List of infrastructure log entries with timestamp, host, source, severity, message
    """
    limit = _clamp_limit(limit)
    source_templates = {
        "kubelet": [
            "Node condition MemoryPressure set to True due to available memory 245MiB < threshold 300MiB",
            "Evicting pod production/user-api-7d9f8b5c4-k2m3n due to memory pressure",
            "Unable to attach volume 'pvc-abc123': timeout waiting for volume to be attached",
            "Pod sandbox changed, it will be killed and re-created.",
            "OOMKilling container user-api in pod user-api-deployment-7d4f9b8c5-x2k9j",
        ],
        "docker": [
            "container died: OOMKilled (memory cgroup out of memory: Kill process 12345)",
            "failed to create shim task: OCI runtime create failed",
            "Error response from daemon: No such container: abc123",
        ],
        "syslog": [
            "kernel: Out of memory: Kill process 9876 (java) score 892 or sacrifice child",
            "systemd[1]: Started Docker Application Container Engine.",
            "sshd[2345]: Failed password for invalid user admin from 203.0.113.42 port 54321 ssh2",
            "kernel: EXT4-fs error (device nvme0n1p1): ext4_validate_block_bitmap:376",
        ],
        "kernel": [
            "kernel: TCP: request_sock_TCP: Possible SYN flooding on port 443",
            "kernel: nf_conntrack: table full, dropping packet",
            "kernel: WARNING: CPU: 0 PID: 1234 at kernel/rcu/tree.c:2847",
        ],
    }

    templates = source_templates.get(source, source_templates["syslog"])
    hosts = [host] if host else [
        f"ip-10-0-{random.randint(1,9)}-{random.randint(100,254)}.ap-northeast-1.compute.internal"
        for _ in range(3)
    ]

    logs = []
    for _ in range(min(limit, random.randint(5, 15))):
        logs.append({
            "timestamp": past_iso(random.randint(0, 30)),
            "host": random.choice(hosts),
            "source": source,
            "severity": random.choice(["WARNING", "ERROR", "CRITICAL"]),
            "facility": "kern" if source == "kernel" else "daemon",
            "message": random.choice(templates),
            "pid": random.randint(1000, 65535),
        })

    logs.sort(key=lambda x: x["timestamp"], reverse=True)
    return logs[:limit]


@tool
def query_audit_logs(
    action: Optional[str] = None,
    principal: Optional[str] = None,
    limit: int = 20,
) -> List[Dict]:
    """
    Search audit logs for security and operational events.

    Retrieves CloudTrail / Kubernetes audit logs tracking who did what and when.
    Useful for investigating unauthorized changes, configuration drift,
    and post-incident forensics to identify human-triggered changes.

    Use this tool when:
    - Investigating if a recent manual change caused an incident
    - Looking for unauthorized access or configuration modifications
    - Tracking deployment and scaling events
    - Security incident investigation

    Args:
        action: Filter by action type (e.g., "kubectl.apply", "kubectl.delete",
                "aws.iam.CreateUser", "aws.ec2.StopInstances"). None = all actions.
        principal: Filter by user/role (e.g., "sre-bot", "admin@company.com"). None = all principals.
        limit: Maximum number of audit log entries to return (default: 20)

    Returns:
        List of audit log entries with timestamp, principal, action, resource, source_ip, result
    """
    limit = _clamp_limit(limit)
    actions = [
        ("kubectl.apply", "deployment/payment-service", "sre-bot@company.com"),
        ("kubectl.delete", "pod/user-api-7d9f8b5c4-k2m3n", "admin@company.com"),
        ("kubectl.scale", "deployment/order-service", "ci-pipeline"),
        ("aws.iam.AttachRolePolicy", "role/EKSNodeRole", "terraform-bot"),
        ("aws.rds.ModifyDBInstance", "db-main-rds", "sre-bot@company.com"),
        ("aws.eks.UpdateClusterConfig", "main-eks-cluster", "admin@company.com"),
        ("aws.s3.DeleteObject", "bucket/config-backup", "sre-bot@company.com"),
        ("kubectl.exec", "pod/payment-service-abc123", "developer@company.com"),
        ("aws.ec2.StopInstances", "i-0abc123def456789", "lambda-scheduler"),
        ("kubectl.apply", "configmap/app-config", "gitops-flux"),
    ]

    filtered = actions
    if action:
        filtered = [(a, r, p) for a, r, p in filtered if action.lower() in a.lower()]
    if principal:
        filtered = [(a, r, p) for a, r, p in filtered if principal.lower() in p.lower()]
    if not filtered:
        filtered = actions

    logs = []
    for _ in range(min(limit, random.randint(5, 15))):
        act, resource, princ = random.choice(filtered)
        logs.append({
            "timestamp": past_iso(random.randint(0, 120)),
            "principal": princ,
            "action": act,
            "resource": resource,
            "source_ip": f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
            "user_agent": random.choice(["kubectl/1.28.0", "aws-cli/2.15.0", "terraform/1.7.0"]),
            "result": random.choice(["Success", "Success", "Success", "AccessDenied"]),
            "region": "ap-northeast-1",
            "request_id": f"req-{random.randint(100000, 999999):06x}",
        })

    logs.sort(key=lambda x: x["timestamp"], reverse=True)
    return logs[:limit]
