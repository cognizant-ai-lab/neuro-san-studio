#!/bin/bash

# Script to be run to start server before any of test case client that require HTTP services
#
# Expects the following system packages to be present on the PATH
# (installed by the calling workflow's dependency step, not here):
#   - netcat-openbsd  (nc, for port readiness polling)
#   - procps          (ps, for PID liveness check)
#   - net-tools       (netstat, for the final diagnostic)
#   - curl            (transitively via Makefile/pip)

source venv/bin/activate
mkdir -p logs

nohup python -m run --server-only > logs/server.log 2>&1 &
  echo $! > server.pid
  sleep 2

if ! ps -p "$(cat server.pid)" > /dev/null; then
  echo "Server process failed to start"
  echo "----- server.log -----"
  cat logs/server.log
  exit 1
fi

echo "Server process started with PID $(cat server.pid)"

for i in {1..30}; do
  PORT_8080_READY=false

  if nc -z localhost 8080; then
    PORT_8080_READY=true
  fi

  if [ "$PORT_8080_READY" = true ]; then
    echo "Port is ready after awaiting $i seconds"
    break
  fi

  echo "Waiting for port 8080... ($i/30)"
  sleep 1
done

if ! nc -z localhost 8080; then
  echo "Timeout: Port 8080 failed to open after 30 seconds"
  cat logs/server.log
  exit 1
fi

echo "Server is healthy and ready"

netstat -tuln | grep -E '8080' || true
