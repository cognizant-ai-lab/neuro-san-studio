# DB Timeout Runbook

## Symptoms

- `SQLTransientConnectionException`
- `HikariPool` connection timeout
- Database connection is not available
- API returns HTTP 500 after database calls
- Timeout values such as `30000ms`

## Likely Causes

1. Database host is unreachable from the application server.
2. Database port is blocked or network route is unavailable.
3. Application database credentials or connection string changed.
4. Hikari connection pool is exhausted.
5. Database max connection limit has been reached.
6. Sudden traffic spike caused connection starvation.

## Approved Checks

1. Check database health/status.
2. Verify database endpoint, port, and DNS resolution.
3. Confirm recent credential or configuration changes.
4. Review active and idle Hikari pool metrics.
5. Review database active connection count and max connection limit.
6. Check recent deployment/configuration changes.
7. Restart service only after approval and only if runbook conditions are met.

## Do Not

- Do not expose credentials or connection strings in the incident update.
- Do not restart production service without approval.
- Do not change pool size without validating database capacity.

## Escalation Criteria

Escalate to database/platform team when:

- Database is unreachable from multiple services.
- Connection limits are consistently exhausted.
- Credentials/configuration were changed by another team.
- Customer-facing APIs are failing for more than one release/service.
