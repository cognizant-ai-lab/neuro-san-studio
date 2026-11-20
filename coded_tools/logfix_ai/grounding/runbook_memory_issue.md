# Memory Issue Runbook

## Symptoms

- `OutOfMemoryError`
- Java heap space errors
- Container memory limit exceeded
- Frequent full garbage collection
- Service restart loop

## Likely Causes

1. Memory leak.
2. Traffic spike increased memory usage.
3. Heap size too low for workload.
4. Large payload or batch job exhausted memory.
5. Recent release increased object retention.

## Approved Checks

1. Check memory usage trend.
2. Review GC logs if available.
3. Check recent deployment or workload changes.
4. Capture heap/thread dump only if approved.
5. Restart only after incident lead approval.
6. Escalate to application owner for leak analysis.

## Do Not

- Do not attach heap dumps to public tickets.
- Do not increase memory limits without capacity review.
