#!/bin/bash
set -e

MODE="${1:-api}"

case "$MODE" in
  api)
    exec uvicorn app.main:app --host 0.0.0.0 --port 8080
    ;;
  worker)
    exec python -m app.worker.worker
    ;;
  *)
    echo "Unknown mode: $MODE. Valid modes: api, worker"
    exit 1
    ;;
esac
