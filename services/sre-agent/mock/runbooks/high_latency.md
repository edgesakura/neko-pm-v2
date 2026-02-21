# Runbook: High Latency

**Category**: HIGH_LATENCY
**Severity**: P2 (high) / P3 (medium)
**Owner**: Platform SRE Team
**Last Updated**: 2026-02-18

---

## Overview

High latency occurs when a service's response time exceeds SLO thresholds.
This can be caused by increased load, inefficient queries, external dependency degradation, or resource saturation.

**SLO**: P99 < 1000ms, P95 < 500ms, P50 < 150ms (adjust per service)
**Alert Threshold**: P99 > 2x SLO for 5+ minutes → P2. P99 > 5x SLO → P1.

---

## Quick Assessment (0–5 minutes)

### 1. Characterize the latency pattern

```bash
# Datadog queries to run immediately:
# P50/P95/P99 trend for affected service
avg:trace.http.request.duration{service:<svc>} by {resource_name}.rollup(percentile, 99)

# Request rate (latency from overload?)
sum:trace.http.request.hits{service:<svc>}.as_rate()

# Downstream service latency (cascading issue?)
avg:trace.http.request.duration{service:*} by {service}.rollup(percentile, 99)
```

### 2. Check recent changes

```bash
# Recent deployments
kubectl rollout history deployment/<service-name> -n production | tail -5

# Feature flags (if applicable)
# Check your feature flag service for recent changes
```

---

## Diagnosis Decision Tree

```
High Latency Detected
├── All percentiles high (P50 also elevated)?
│   └── Overload or resource saturation (CPU/Memory/Network)
│       ├── Scale out (HPA or manual)
│       └── Investigate traffic spike root cause
│
├── Only P99/P95 high (P50 normal)?
│   └── Long-tail issue (slow queries, N+1, external call)
│       ├── Check DB slow query log
│       ├── Check external API latency
│       └── Look for N+1 query patterns in APM traces
│
├── Specific endpoints high?
│   └── Code-level issue in that handler
│       ├── Check APM traces for that resource
│       └── Look for missing DB index
│
├── Started after deployment?
│   └── Rollback, investigate new code
│
└── External dependency degraded?
    └── Implement timeout + circuit breaker + cached fallback
```

---

## Investigation

### Database Analysis

```bash
# PostgreSQL: Current slow queries
kubectl exec -it <rds-proxy-or-jump-pod> -- psql $DATABASE_URL -c \
  "SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
   FROM pg_stat_activity
   WHERE (now() - pg_stat_activity.query_start) > interval '1 second'
   ORDER BY duration DESC LIMIT 20;"

# Check for missing indexes
kubectl exec -it <rds-proxy-or-jump-pod> -- psql $DATABASE_URL -c \
  "SELECT schemaname, tablename, attname, n_distinct, correlation
   FROM pg_stats
   WHERE tablename = '<table_name>';"

# Connection pool status
kubectl exec -it <rds-proxy-or-jump-pod> -- psql $DATABASE_URL -c \
  "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
```

### Application-Level Analysis

```bash
# Get traces with high latency (via APM)
# Datadog APM → Traces → Filter by service + p99 > 2000ms → Flame graph

# Check GC pauses (JVM services)
kubectl logs <pod-name> -n production --since=15m | grep "GC\|gc\|pause"

# Check thread pool / async queue depth (if exposed via metrics)
# avg:service.thread_pool.queue_depth{service:<svc>}
```

### Infrastructure Analysis

```bash
# CPU throttling
kubectl top pods -n production -l app=<service-name>

# Network I/O
kubectl exec -it <pod-name> -n production -- ss -s

# Check if nodes are under pressure
kubectl describe nodes | grep -A5 "Conditions:"
```

### External Dependency Analysis

```bash
# Test external endpoint latency directly from pod
kubectl exec -it <pod-name> -n production -- \
  time curl -o /dev/null -s -w "%{time_total}" https://<dependency-endpoint>/health

# Check DNS resolution time
kubectl exec -it <pod-name> -n production -- \
  time nslookup <dependency-hostname>
```

---

## Mitigation

### Mitigation A: Scale Out

```bash
# Immediate scale out if overloaded
kubectl scale deployment/<service-name> -n production --replicas=20

# Increase HPA max
kubectl patch hpa <service-name> -n production -p '{"spec":{"maxReplicas":30}}'
```

### Mitigation B: Rollback

```bash
kubectl rollout undo deployment/<service-name> -n production
kubectl rollout status deployment/<service-name> -n production
```

### Mitigation C: Add Missing DB Index (Emergency)

```sql
-- Create index concurrently (non-blocking in PostgreSQL)
CREATE INDEX CONCURRENTLY idx_<table>_<column> ON <table>(<column>);

-- Verify index is used
EXPLAIN ANALYZE SELECT ... WHERE <column> = ...;
```

### Mitigation D: Implement Timeout + Circuit Breaker

```bash
# Set aggressive timeout via env var (if service supports it)
kubectl set env deployment/<service-name> -n production \
  EXTERNAL_API_TIMEOUT_MS=500 \
  CIRCUIT_BREAKER_THRESHOLD=50

# Deploy updated configuration
kubectl rollout restart deployment/<service-name> -n production
```

### Mitigation E: Enable Caching / Degraded Mode

```bash
# Enable response caching or serve stale cache (if applicable)
kubectl set env deployment/<service-name> -n production \
  CACHE_TTL_SECONDS=300 \
  SERVE_STALE_ON_ERROR=true
```

---

## Escalation Criteria

| Condition | Action |
|-----------|--------|
| P50 > SLO (all requests slow) | Scale out first, then escalate |
| P99 > 10x SLO with no root cause | Escalate to Engineering Manager |
| External dependency confirmed degraded | Contact vendor + open support ticket |
| Data integrity concern | Freeze writes, involve Data team |

---

## Performance Baseline Reference

| Service | P50 SLO | P95 SLO | P99 SLO |
|---------|---------|---------|---------|
| payment-service | 100ms | 300ms | 800ms |
| order-service | 150ms | 500ms | 1000ms |
| user-api | 80ms | 250ms | 600ms |
| recommendation-service | 200ms | 800ms | 2000ms |

---

## Post-Incident

1. Add DB index to migration if missing index was root cause
2. Add circuit breaker for identified external dependency
3. Update HPA configuration if scale-out was needed
4. Add latency alert for specific endpoint if not covered
