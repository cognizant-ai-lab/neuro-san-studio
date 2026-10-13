# Known Error Patterns

## Database Timeout

Match when logs include one or more:

- `SQLTransientConnectionException`
- `HikariPool`
- `Connection is not available`
- `connection timeout`
- database API returns HTTP 500

## API Failure

Match when logs include one or more:

- `HTTP 500`
- `HTTP 502`
- `HTTP 503`
- `HTTP 504`
- `Connection refused`
- `Read timed out`
- `upstream`
- `gateway`

## Memory Issue

Match when logs include one or more:

- `OutOfMemoryError`
- `Java heap space`
- `GC overhead limit exceeded`
- `container killed`
- `OOMKilled`

## Classification Rule

Prefer the most specific match:

1. Memory issue
2. Database timeout
3. API failure
4. Unknown incident
