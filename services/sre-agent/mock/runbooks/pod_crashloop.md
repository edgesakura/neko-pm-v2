# Runbook: Pod CrashLoopBackOff

**Category**: POD_CRASHLOOP
**Severity**: P2 (high) / P3 (medium)
**Owner**: Platform SRE Team
**Last Updated**: 2026-02-18

---

## Overview

CrashLoopBackOff occurs when a Kubernetes pod repeatedly crashes and restarts.
Kubernetes applies exponential backoff between restarts (10s → 20s → 40s → ... → 5m max).

**SLO Impact**: Reduced capacity; potential total outage if all replicas crash.
**Alert Threshold**: Any pod with restart_count > 5 in 30 minutes → P2.

---

## Quick Assessment (0–3 minutes)

### 1. Identify crash pattern

```bash
# Check pod status and restart count
kubectl get pods -n production | grep -v "Running\|Completed"

# Detailed pod info
kubectl describe pod <pod-name> -n production

# Last termination reason (OOMKilled, Error, etc.)
kubectl get pod <pod-name> -n production -o json | jq '.status.containerStatuses[].lastState.terminated'
```

### 2. Get last logs before crash

```bash
# Logs from previous (crashed) container instance
kubectl logs <pod-name> -n production --previous

# If pod is currently running but unstable
kubectl logs <pod-name> -n production --since=5m
```

---

## Diagnosis Decision Tree

```
CrashLoopBackOff
├── lastTerminationReason = OOMKilled
│   └── See: Memory Issue Investigation
│
├── lastTerminationReason = Error (exit code 1/2)
│   ├── Logs show missing env var → Check ConfigMap/Secret
│   ├── Logs show connection refused → Check dependency health
│   └── Logs show panic/exception → Code bug, rollback
│
├── lastTerminationReason = Error (exit code 137 = SIGKILL)
│   └── Likely OOM or liveness probe kill
│
├── Liveness probe failing
│   └── Check if service is actually unhealthy or probe misconfigured
│
└── Recent deployment? → Rollback first, investigate after
```

---

## Investigation

### Memory Issue (OOMKilled)

```bash
# Check memory usage trend
kubectl top pod <pod-name> -n production

# Check memory limits vs requests
kubectl get pod <pod-name> -n production -o json | jq '.spec.containers[].resources'

# Check for memory leak indicators in logs
kubectl logs <pod-name> -n production --previous | grep -i "memory\|heap\|gc\|oom"
```

**Immediate fix**: Increase memory limit temporarily:
```bash
kubectl set resources deployment/<deployment-name> -n production \
  --limits=memory=2Gi --requests=memory=1Gi
```

### Missing Configuration

```bash
# Check if all required env vars are present
kubectl exec -it <pod-name> -n production -- env | grep -E "DB_|REDIS_|API_KEY"

# Compare with expected config
kubectl get configmap <config-name> -n production -o yaml

# Check if secret exists
kubectl get secret <secret-name> -n production
```

### Startup Failure / Dependency

```bash
# Check if crash happens immediately (startup) or after some time (runtime)
kubectl get pod <pod-name> -n production -o json | \
  jq '.status.containerStatuses[].lastState.terminated.startedAt'

# Test connectivity from pod
kubectl exec -it <pod-name> -n production -- nc -zv $DB_HOST 5432
kubectl exec -it <pod-name> -n production -- nc -zv $REDIS_HOST 6379
```

---

## Mitigation

### Mitigation A: Immediate Rollback

```bash
kubectl rollout undo deployment/<deployment-name> -n production
kubectl rollout status deployment/<deployment-name> -n production
```

### Mitigation B: Increase Resources

```bash
# Memory
kubectl set resources deployment/<deployment-name> -n production \
  --limits=memory=4Gi --requests=memory=2Gi

# CPU (if CPU throttling is causing issues)
kubectl set resources deployment/<deployment-name> -n production \
  --limits=cpu=2000m --requests=cpu=500m
```

### Mitigation C: Force Pod Restart / Delete Crashlooping Pods

```bash
# Delete crashlooping pods (Deployment will recreate)
kubectl delete pod <pod-name> -n production

# Or rolling restart if all pods are affected
kubectl rollout restart deployment/<deployment-name> -n production
```

### Mitigation D: Temporarily Scale Down + Fix + Scale Up

```bash
# Scale down to 0 (stop the crash loop)
kubectl scale deployment/<deployment-name> -n production --replicas=0

# Fix the issue (update ConfigMap, Secret, resource limits, etc.)
# ...

# Scale back up
kubectl scale deployment/<deployment-name> -n production --replicas=3
```

### Mitigation E: Fix Missing Config

```bash
# Add missing env var to ConfigMap
kubectl patch configmap <config-name> -n production \
  --patch '{"data":{"MISSING_VAR":"value"}}'

# Or add directly to deployment (temporary)
kubectl set env deployment/<deployment-name> -n production MISSING_VAR=value
```

---

## Escalation Criteria

| Condition | Action |
|-----------|--------|
| All pods of a service are crashlooping | Declare P1, page on-call |
| Multiple services crashlooping simultaneously | Potential platform issue, escalate to infra team |
| OOMKilled on all pods despite limit increase | Memory leak investigation required |

---

## Prevention Checklist

- [ ] Resource requests/limits set based on load test results
- [ ] All required env vars validated at startup (panic with clear message)
- [ ] Startup probe configured for services with slow initialization
- [ ] ConfigMap changes go through GitOps (no manual kubectl apply)
- [ ] Staging has identical resource limits as production
