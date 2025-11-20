#!/usr/bin/env bash
set -euo pipefail

echo "[test-entrypoint] starting; forwarding to test command..."

# If /tests is missing, warn but continue so user sees the problem
if [ ! -d /tests ]; then
  echo "[test-entrypoint] warning: /tests not found" >&2
fi

# If /app is missing, warn but continue so user sees the problem
if [ ! -d /app ]; then
  echo "[test-entrypoint] warning: /app not found" >&2
fi

# If a test command file was passed, ensure it's executable (non-fatal)
if [ "$#" -gt 0 ] && [ -f "$1" ]; then
  chmod +x "$1" || true
fi

# Exec the provided command so stdout/stderr and exit code are forwarded
exec "$@"
