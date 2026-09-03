#!/usr/bin/env sh
set -u

profile="${1:-smoke}"
case "$profile" in
  smoke)
    export LOAD_VUS=10 LOAD_DURATION=30s SESSION_SECONDS=15 THINK_TIME_MS=1000
    export COMMAND_P95_MS=1000 COMMAND_P99_MS=2000
    ;;
  baseline)
    export LOAD_VUS=100 LOAD_DURATION=5m SESSION_SECONDS=60 THINK_TIME_MS=1000
    export COMMAND_P95_MS=500 COMMAND_P99_MS=1000
    ;;
  stress)
    export LOAD_VUS=500 LOAD_DURATION=10m SESSION_SECONDS=90 THINK_TIME_MS=750
    export COMMAND_P95_MS=500 COMMAND_P99_MS=1000
    ;;
  *)
    echo "Unknown load-test profile: $profile" >&2
    exit 2
    ;;
esac

export RUN_ID="$(date +%s)"
cleanup() {
  docker compose -f compose.load.yaml down -v
}
trap cleanup EXIT INT TERM

echo "Starting isolated $profile load-test stack..."
docker compose -f compose.load.yaml up -d --build backend_load || exit $?
docker compose -f compose.load.yaml run --rm k6
