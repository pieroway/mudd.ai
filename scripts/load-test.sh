#!/usr/bin/env sh
set -u

profile="${1:-smoke}"
case "$profile" in
  smoke)
    scenario=normal-gameplay
    export LOAD_VUS=10 LOAD_DURATION=30s SESSION_SECONDS=15 THINK_TIME_MS=1000
    export COMMAND_P95_MS=1000 COMMAND_P99_MS=2000
    ;;
  baseline)
    scenario=normal-gameplay
    export LOAD_VUS=100 LOAD_DURATION=5m SESSION_SECONDS=60 THINK_TIME_MS=1000
    export COMMAND_P95_MS=500 COMMAND_P99_MS=1000
    ;;
  stress)
    scenario=normal-gameplay
    export LOAD_VUS=500 LOAD_DURATION=10m SESSION_SECONDS=90 THINK_TIME_MS=750
    export COMMAND_P95_MS=500 COMMAND_P99_MS=1000
    ;;
  crowded)
    scenario=crowded-room
    export LOAD_VUS=100 LOAD_DURATION=2m SESSION_SECONDS=60 THINK_TIME_MS=2000
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
mkdir -p load-tests/results
docker compose -f compose.load.yaml run --rm k6 run \
  --summary-export "/results/$RUN_ID-$profile.json" \
  "/scripts/scenarios/$scenario.js"
k6_exit=$?
docker compose -f compose.load.yaml exec -T backend_load \
  python /load-tests/check_invariants.py
invariant_exit=$?

if [ "$k6_exit" -ne 0 ]; then
  exit "$k6_exit"
fi
exit "$invariant_exit"
