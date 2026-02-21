"""
EKS cluster check tools for SRE diagnostic agent.
Lists pods and describes deployments in Kubernetes clusters.
In production, these would query the Kubernetes API via boto3 or kubectl.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../'))

from typing import List, Dict, Optional
from strands import tool

from common.mock_data import past_iso
import random


@tool
def list_pods(
    namespace: str = "production",
    label_selector: Optional[str] = None,
) -> List[Dict]:
    """
    List all Kubernetes pods in a namespace with their current status.

    Retrieves pod name, phase, readiness, restart count, assigned node,
    resource requests/limits, and container image. Provides a quick overview
    of the health of all workloads in the namespace. Use this as a starting
    point when investigating service degradation or alerts.

    Use this tool when:
    - Getting an overview of all pods and their health in a namespace
    - Checking how many replicas of a service are Running vs Pending/Failing
    - Verifying that a rollout completed successfully
    - Finding pods matching a specific label selector (e.g., "app=payment-service")

    Args:
        namespace: Kubernetes namespace to list pods from (default: "production")
        label_selector: Optional label selector to filter pods (e.g., "app=payment-service",
                        "tier=backend", "version=v2"). If None, returns all pods.

    Returns:
        List of pod dicts with name, phase, ready, restart_count, node,
        resource requests/limits, image, and labels
    """
    all_pods = [
        ("payment-service", "app=payment-service,version=v3.2.1", "Running", 0, True, "512Mi", "500m"),
        ("payment-service", "app=payment-service,version=v3.2.1", "Running", 0, True, "512Mi", "500m"),
        ("payment-service", "app=payment-service,version=v3.2.1", "Running", 0, True, "512Mi", "500m"),
        ("order-service", "app=order-service,version=v2.8.0", "Running", 0, True, "1Gi", "1000m"),
        ("order-service", "app=order-service,version=v2.8.0", "Running", 0, True, "1Gi", "1000m"),
        ("user-api", "app=user-api,version=v3.1.0", "CrashLoopBackOff", 15, False, "512Mi", "500m"),
        ("user-api", "app=user-api,version=v3.1.0", "CrashLoopBackOff", 8, False, "512Mi", "500m"),
        ("user-api", "app=user-api,version=v3.1.0", "Running", 0, True, "512Mi", "500m"),
        ("auth-service", "app=auth-service,version=v1.5.2", "Running", 0, True, "256Mi", "250m"),
        ("auth-service", "app=auth-service,version=v1.5.2", "Running", 0, True, "256Mi", "250m"),
        ("inventory-service", "app=inventory-service,version=v2.3.0", "Running", 0, True, "1Gi", "500m"),
        ("notification-worker", "app=notification-worker,version=v1.2.0", "Running", 2, True, "512Mi", "250m"),
        ("recommendation-service", "app=recommendation-service,version=v1.1.0", "Running", 0, True, "4Gi", "2000m"),
        ("search-service", "app=search-service,version=v2.0.1", "Running", 0, True, "2Gi", "1000m"),
    ]

    filtered = all_pods
    if label_selector:
        key, val = label_selector.split("=", 1) if "=" in label_selector else ("app", label_selector)
        filtered = [p for p in all_pods if key in p[1] and val in p[1]]

    pods = []
    pod_counters: Dict[str, int] = {}
    for app_name, labels, phase, restarts, ready, mem_limit, cpu_limit in filtered:
        pod_counters[app_name] = pod_counters.get(app_name, 0) + 1
        suffix = f"{random.randint(10000, 99999):05d}"
        full_name = f"{app_name}-{random.randint(10000,99999):05x}-{suffix[:5]}"

        pods.append({
            "name": full_name,
            "namespace": namespace,
            "phase": phase,
            "ready": ready,
            "restart_count": restarts,
            "node": f"ip-10-0-{random.randint(1,9)}-{random.randint(100,254)}.ap-northeast-1.compute.internal",
            "age_minutes": random.randint(30, 1440),
            "labels": dict(item.split("=") for item in labels.split(",") if "=" in item),
            "resources": {
                "requests": {"memory": mem_limit, "cpu": str(int(cpu_limit.replace("m", "")) // 2) + "m"},
                "limits": {"memory": mem_limit, "cpu": cpu_limit},
            },
            "image": f"123456789.dkr.ecr.ap-northeast-1.amazonaws.com/{app_name}:{labels.split('version=')[-1]}",
            "last_termination_reason": "OOMKilled" if restarts > 5 else (None if restarts == 0 else "Error"),
        })

    return pods


@tool
def describe_deployment(
    namespace: str = "production",
    deployment_name: Optional[str] = None,
) -> Dict:
    """
    Describe a Kubernetes Deployment including replica status and rollout history.

    Retrieves desired vs ready vs available replicas, current rollout strategy,
    HPA configuration, resource requests/limits per container, last deployment time,
    and recent rollout history. Essential for understanding the current state of a
    deployment and diagnosing rolling update issues or replica mismatches.

    Use this tool when:
    - Verifying that a deployment has the expected number of ready replicas
    - Checking if a rollout is in progress or stuck
    - Understanding the rollout strategy (RollingUpdate vs Recreate)
    - Investigating if HPA has scaled the deployment unexpectedly
    - Getting the image version currently running in production

    Args:
        namespace: Kubernetes namespace (default: "production")
        deployment_name: Name of the deployment to describe.
                         If None, returns a summary of all deployments in the namespace.

    Returns:
        Dict with replica status, strategy, HPA config, container specs,
        rollout history (last 5 revisions), and creation timestamp
    """
    deployments = {
        "user-api-deployment": {
            "desired": 3, "ready": 1, "available": 1, "updated": 3,
            "image": "123456789.dkr.ecr.ap-northeast-1.amazonaws.com/user-api:v3.1.0",
            "previous_image": "123456789.dkr.ecr.ap-northeast-1.amazonaws.com/user-api:v3.0.9",
            "memory_limit": "512Mi", "cpu_limit": "500m",
            "last_updated": past_iso(45),
            "rollout_status": "DEGRADED - 2/3 pods in CrashLoopBackOff",
        },
        "payment-service": {
            "desired": 3, "ready": 3, "available": 3, "updated": 3,
            "image": "123456789.dkr.ecr.ap-northeast-1.amazonaws.com/payment-service:v3.2.1",
            "previous_image": "123456789.dkr.ecr.ap-northeast-1.amazonaws.com/payment-service:v3.2.0",
            "memory_limit": "512Mi", "cpu_limit": "500m",
            "last_updated": past_iso(180),
            "rollout_status": "COMPLETE",
        },
        "order-service": {
            "desired": 2, "ready": 2, "available": 2, "updated": 2,
            "image": "123456789.dkr.ecr.ap-northeast-1.amazonaws.com/order-service:v2.8.0",
            "previous_image": "123456789.dkr.ecr.ap-northeast-1.amazonaws.com/order-service:v2.7.3",
            "memory_limit": "1Gi", "cpu_limit": "1000m",
            "last_updated": past_iso(240),
            "rollout_status": "COMPLETE",
        },
    }

    if deployment_name and deployment_name in deployments:
        dep = deployments[deployment_name]
    elif deployment_name:
        dep = {
            "desired": 2, "ready": 2, "available": 2, "updated": 2,
            "image": f"123456789.dkr.ecr.ap-northeast-1.amazonaws.com/{deployment_name}:v1.0.0",
            "previous_image": f"123456789.dkr.ecr.ap-northeast-1.amazonaws.com/{deployment_name}:v0.9.0",
            "memory_limit": "512Mi", "cpu_limit": "500m",
            "last_updated": past_iso(360),
            "rollout_status": "COMPLETE",
        }
        deployment_name = deployment_name
    else:
        # Return all deployments summary
        return {
            "namespace": namespace,
            "deployments": [
                {
                    "name": name,
                    "replicas": f"{d['ready']}/{d['desired']}",
                    "status": d["rollout_status"],
                    "image_tag": d["image"].split(":")[-1],
                    "last_updated": d["last_updated"],
                }
                for name, d in deployments.items()
            ],
            "source": "mock-kubernetes-api",
        }

    return {
        "name": deployment_name or "user-api-deployment",
        "namespace": namespace,
        "replicas": {
            "desired": dep["desired"],
            "ready": dep["ready"],
            "available": dep["available"],
            "updated": dep["updated"],
            "unavailable": dep["desired"] - dep["ready"],
        },
        "strategy": {
            "type": "RollingUpdate",
            "max_surge": "25%",
            "max_unavailable": "25%",
        },
        "hpa": {
            "enabled": True,
            "min_replicas": 2,
            "max_replicas": 20,
            "current_replicas": dep["ready"],
            "target_cpu_pct": 70,
        },
        "containers": [
            {
                "name": (deployment_name or "user-api-deployment").replace("-deployment", "").split("-")[0],
                "image": dep["image"],
                "resources": {
                    "requests": {
                        "memory": str(int(dep["memory_limit"].replace("Mi", "")) // 2) + "Mi",
                        "cpu": "250m",
                    },
                    "limits": {
                        "memory": dep["memory_limit"],
                        "cpu": dep["cpu_limit"],
                    },
                },
                "readiness_probe": {"http_get": "/health", "period_seconds": 10},
                "liveness_probe": {"http_get": "/health", "period_seconds": 30},
            }
        ],
        "rollout_history": [
            {
                "revision": 5,
                "image": dep["image"],
                "deployed_at": dep["last_updated"],
                "deployed_by": "ci-pipeline",
                "status": dep["rollout_status"],
            },
            {
                "revision": 4,
                "image": dep["previous_image"],
                "deployed_at": past_iso(1440),
                "deployed_by": "ci-pipeline",
                "status": "COMPLETE",
            },
        ],
        "rollout_status": dep["rollout_status"],
        "last_updated": dep["last_updated"],
        "source": "mock-kubernetes-api",
    }
