"""
Health check tools for SRE diagnostic agent.
Checks pod health, node health, and service endpoint reachability.
In production, these would query the Kubernetes API and perform actual connectivity tests.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../'))

from typing import List, Dict, Optional
from strands import tool

from common.mock_data import generate_pod_status, past_iso
import random


@tool
def check_pod_health(
    namespace: str = "production",
    pod_name: Optional[str] = None,
) -> List[Dict]:
    """
    Check the health status of Kubernetes pods in a namespace.

    Retrieves pod phase (Running/Pending/CrashLoopBackOff/OOMKilled), restart counts,
    container readiness, last termination reason, and resource usage.
    This is the first tool to run when investigating pod-related alerts or CrashLoopBackOff.

    Use this tool when:
    - An alert indicates pod is in CrashLoopBackOff or OOMKilled
    - Investigating service degradation caused by reduced pod capacity
    - Verifying pod health after a deployment or scaling event
    - Checking which pods in a namespace are unhealthy

    Args:
        namespace: Kubernetes namespace to query (default: "production")
        pod_name: Specific pod name to check. If None, returns all pods in namespace.

    Returns:
        List of pod status dicts with name, phase, ready, restart_count,
        last_restart, node, age_minutes, containers info, and last_termination_reason
    """
    services = [
        ("payment-service", 0, True, "Running"),
        ("order-service", 0, True, "Running"),
        ("user-api-deployment-7d4f9b8c5-x2k9j", 15, False, "CrashLoopBackOff"),
        ("user-api-deployment-7d4f9b8c5-m4n8p", 8, False, "CrashLoopBackOff"),
        ("user-api-deployment-7d4f9b8c5-q7r2s", 0, True, "Running"),
        ("auth-service", 0, True, "Running"),
        ("inventory-service", 0, True, "Running"),
        ("notification-worker", 2, True, "Running"),
        ("recommendation-service", 0, True, "Running"),
        ("search-service", 0, True, "Running"),
    ]

    if pod_name:
        filtered = [(n, r, rd, p) for n, r, rd, p in services if pod_name in n]
        if not filtered:
            filtered = [(pod_name, 0, True, "Running")]
    else:
        filtered = services

    return [
        generate_pod_status(
            name=name,
            namespace=namespace,
            phase=phase,
            restart_count=restarts,
            ready=ready,
        )
        for name, restarts, ready, phase in filtered
    ]


@tool
def check_node_health(cluster: str = "main-eks-cluster") -> List[Dict]:
    """
    Check the health and resource utilization of EKS worker nodes.

    Retrieves node conditions (Ready/MemoryPressure/DiskPressure/PIDPressure),
    allocated CPU and memory vs capacity, number of pods scheduled, and kernel version.
    Useful for identifying node-level resource pressure that affects all pods on that node.

    Use this tool when:
    - Multiple pods on the same node are failing or being evicted
    - Investigating OOMKilled events that may be node-level
    - Checking if cluster has capacity for additional pods
    - Investigating node not ready conditions

    Args:
        cluster: EKS cluster name to check (default: "main-eks-cluster")

    Returns:
        List of node status dicts with node name, conditions, CPU/memory allocation,
        pod count, instance type, and availability zone
    """
    instance_types = ["m6i.2xlarge", "m6i.4xlarge", "c6i.2xlarge", "r6g.xlarge"]
    azs = ["ap-northeast-1a", "ap-northeast-1c", "ap-northeast-1d"]

    nodes = []
    for i in range(1, 7):
        cpu_allocated_pct = round(random.uniform(45, 85), 1)
        mem_allocated_pct = round(random.uniform(55, 90), 1)
        memory_pressure = mem_allocated_pct > 88

        node = {
            "name": f"ip-10-0-{random.randint(1,9)}-{100+i*20}.ap-northeast-1.compute.internal",
            "cluster": cluster,
            "instance_type": random.choice(instance_types),
            "availability_zone": random.choice(azs),
            "conditions": {
                "Ready": True,
                "MemoryPressure": memory_pressure,
                "DiskPressure": False,
                "PIDPressure": False,
                "NetworkUnavailable": False,
            },
            "capacity": {
                "cpu_cores": 8,
                "memory_gib": 32,
            },
            "allocated": {
                "cpu_pct": cpu_allocated_pct,
                "memory_pct": mem_allocated_pct,
                "pods": random.randint(15, 35),
                "max_pods": 58,
            },
            "kernel_version": "5.10.210-201.855.amzn2.x86_64",
            "kubelet_version": "v1.28.5-eks-5e0fdde",
            "age_days": random.randint(30, 180),
        }
        nodes.append(node)

    return nodes


@tool
def check_service_endpoint(service: str, port: int = 443) -> Dict:
    """
    Check connectivity and response time for a service endpoint.

    Performs an HTTP health check against the service's health or readiness endpoint.
    Measures DNS resolution time, TCP connection time, TLS handshake time, and
    total response time. Useful for confirming whether a service is actually reachable
    and responding before assuming the issue is in the code.

    Use this tool when:
    - Verifying if a service is responding after a deployment or restart
    - Checking if a service endpoint is reachable from within the cluster
    - Measuring baseline response time for health endpoints
    - Investigating connection refused or timeout errors

    Args:
        service: The service name or FQDN to check (e.g., "payment-service",
                 "payment-service.production.svc.cluster.local")
        port: Port number to connect to (default: 443 for HTTPS, use 8080 for internal)

    Returns:
        Dict with endpoint URL, HTTP status code, response time breakdown,
        TLS certificate info, and overall health status
    """
    service_health = {
        "payment-service": ("healthy", 200, 45),
        "order-service": ("healthy", 200, 52),
        "user-api": ("degraded", 503, 3001),
        "auth-service": ("healthy", 200, 38),
        "inventory-service": ("healthy", 200, 61),
    }

    status_label, http_code, response_ms = service_health.get(
        service, ("healthy", 200, random.randint(30, 120))
    )

    is_healthy = http_code == 200
    fqdn = f"{service}.production.svc.cluster.local" if "." not in service else service

    return {
        "service": service,
        "endpoint": f"{'https' if port == 443 else 'http'}://{fqdn}:{port}/health",
        "port": port,
        "status": status_label,
        "http_status_code": http_code,
        "reachable": is_healthy,
        "timing": {
            "dns_resolution_ms": random.randint(1, 5),
            "tcp_connect_ms": random.randint(1, 10),
            "tls_handshake_ms": random.randint(5, 25) if port == 443 else 0,
            "ttfb_ms": random.randint(10, response_ms // 2),
            "total_ms": response_ms,
        },
        "tls": {
            "valid": True,
            "expires_days": random.randint(30, 365),
            "issuer": "Amazon RSA 2048 M02",
        } if port == 443 else None,
        "checked_at": past_iso(0),
        "source": "mock-synthetic-monitor",
    }
