# Runbook: API 5xx Error Rate Spike

**Category**: API_5XX_SPIKE
**Severity**: P1 (critical) / P2 (high)
**Owner**: Platform SRE Team
**Last Updated**: 2026-02-18

---

## Overview

This runbook covers investigation and mitigation of elevated HTTP 5xx error rates on internal services.
A 5xx spike typically indicates backend failures (crashes, timeouts, dependency failures, resource exhaustion).

**SLO Threshold**: Error rate < 0.5% over 5 minutes
**Alert Threshold**: Error rate > 5% for 2+ minutes → P1. Error rate > 1% for 10+ minutes → P2.

---

## Initial Triage (0–5 minutes)

### 1. Confirm the scope

```bash
# Identify affected services and time range
kubectl get pods -n production | grep -v Running

# Check error rate by service (Datadog)
# Query: sum:trace.http.request.errors{env:production} by {service}.as_rate()
```

### 2. Check deployment history

```bash
# Was there a recent deployment?
kubectl rollout history deployment/<service-name> -n production

# Check last 3 deploys with timestamps
kubectl get rs -n production --sort-by=.metadata.creationTimestamp | tail -5
```

### 3. Check downstream dependencies

```bash
# Verify RDS connectivity
kubectl exec -it <pod-name> -n production -- sh -c 'nc -zv $DB_HOST $DB_PORT && echo OK'

# Verify Redis connectivity
kubectl exec -it <pod-name> -n production -- sh -c 'redis-cli -h $REDIS_HOST ping'
```

---

## Diagnosis Decision Tree

```
5xx Error Spike Detected
├── Recent deployment? YES → Rollback (see Mitigation A)
│
├── DB errors in logs? YES
│   ├── Connection refused → Check RDS status, security groups
│   ├── Timeout → Check slow queries, connection pool
│   └── Too many connections → Scale RDS or enable PgBouncer
│
├── Memory/CPU spike? YES
│   ├── OOMKilled → Increase memory limits or fix memory leak
│   └── CPU throttling → Increase CPU limits or optimize
│
├── External dependency down? YES
│   └── Enable circuit breaker, serve cached/degraded response
│
└── Unknown → Deep log analysis (see Investigation section)
```

---

## Investigation

### Check application logs

```bash
# Last 100 error logs from affected service
kubectl logs -n production deployment/<service-name> --since=30m | grep -i "error\|exception\|panic" | tail -100

# If multiple pods, aggregate
kubectl logs -n production -l app=<service-name> --since=30m | grep "ERROR" | tail -200
```

### Check metrics (Datadog queries)

```
# Request rate by status code
sum:trace.http.request.hits{service:<svc>} by {http.status_code}.as_rate()

# Latency percentiles
avg:trace.http.request.duration{service:<svc>} by {resource_name}.rollup(percentile, 99)

# DB connection pool utilization
avg:postgresql.percent_usage_connections{dbname:<db>}
```

### Check infrastructure

```bash
# Node resource pressure
kubectl top nodes

# Pod resource usage
kubectl top pods -n production -l app=<service-name>

# Events (OOMKilled, eviction, etc.)
kubectl get events -n production --sort-by=.lastTimestamp | tail -30
```

---

## Mitigation

### Mitigation A: Rollback Deployment

```bash
# Rollback to previous version
kubectl rollout undo deployment/<service-name> -n production

# Monitor rollout
kubectl rollout status deployment/<service-name> -n production

# Verify error rate drops (wait 2 minutes after rollout complete)
```

### Mitigation B: Scale Out (if overloaded)

```bash
# Temporarily increase replicas
kubectl scale deployment/<service-name> -n production --replicas=10

# Set HPA max (if HPA is blocking)
kubectl patch hpa <service-name> -n production -p '{"spec":{"maxReplicas":20}}'
```

### Mitigation C: Enable Circuit Breaker / Traffic Shedding

```bash
# Reduce traffic to affected service via Ingress weight (if using ALB)
# Contact on-call network engineer for traffic routing changes

# Enable maintenance mode response (if applicable)
kubectl set env deployment/<service-name> -n production MAINTENANCE_MODE=true
```

### Mitigation D: Restart Pods (last resort)

```bash
# Rolling restart (zero downtime)
kubectl rollout restart deployment/<service-name> -n production
```

---

## Escalation Criteria

| Condition | Action |
|-----------|--------|
| Error rate > 20% for 5+ minutes | Page Engineering Manager + CTO |
| Multiple services affected simultaneously | Declare major incident, war room |
| Data loss suspected | Freeze all writes, involve Data Engineering |
| External customer impact confirmed | Activate status page update |

**Escalation contacts**: See PagerDuty service directory → `platform-sre-oncall`

---

## Post-Incident

1. **Within 24h**: Draft initial postmortem (timeline + root cause hypothesis)
2. **Within 72h**: Complete postmortem with action items
3. **Within 1 week**: Action items assigned and in backlog
4. **Update this runbook** if new patterns discovered
