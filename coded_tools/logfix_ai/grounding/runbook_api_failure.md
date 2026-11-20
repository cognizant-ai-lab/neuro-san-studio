# API Failure Runbook

## Symptoms

- HTTP 500, 502, 503, or 504 responses
- Upstream dependency timeout
- Connection refused from downstream service
- Repeated retry failures

## Likely Causes

1. Downstream dependency unavailable.
2. Application exception not handled.
3. Timeout threshold too low for current load.
4. Recent deployment introduced regression.
5. External service returned invalid response.

## Approved Checks

1. Identify impacted endpoint and service.
2. Check latest deployment timestamp.
3. Review downstream service health.
4. Check gateway/load balancer status.
5. Validate whether failures are isolated or widespread.
6. Escalate with evidence lines and correlation ID if available.

## Do Not

- Do not assume the API service is at fault without checking dependencies.
- Do not share full customer payloads in status messages.
