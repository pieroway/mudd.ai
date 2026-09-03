# Local Load Testing

This directory contains opt-in k6 load tests for the MUD WebSocket protocol.
They run against a dedicated Docker Compose stack with ephemeral PostgreSQL and
Redis storage. They never use development or production game data.

## Commands

```bash
make load-smoke     # 10 players, 30 seconds
make load-test      # 100 players, 5 minutes
make load-stress    # 500 players, 10 minutes
```

The first run may download the pinned k6 image. Each command builds and starts
the isolated backend, runs the scenario, then removes its containers, network,
and volumes even when a threshold fails.

Override the defaults directly if needed:

```bash
LOAD_VUS=50 LOAD_DURATION=2m SESSION_SECONDS=60 THINK_TIME_MS=750 \
  docker compose -f compose.load.yaml run --rm k6
docker compose -f compose.load.yaml down -v
```

On PowerShell, set the variables with `$env:LOAD_VUS = "50"` before running the
Compose command.

## Current Scenario

`normal-gameplay.js` creates unique players that repeatedly run `look`,
`inventory`, `north`, and `south`. Only one command is outstanding per player,
so command-response latency can be measured despite unsolicited room events.

The baseline and stress runs fail if:

- More than 1% of command responses fail.
- p95 command latency reaches 500 ms.
- p99 command latency reaches 1 second.
- p95 WebSocket connection time reaches 1 second.
- Fewer than 99% of WebSocket upgrade checks pass.

The smoke profile permits p95 command latency below 1 second and p99 below 2
seconds. Its purpose is to verify the harness and protocol with modest load;
baseline and stress retain the stricter capacity thresholds. All thresholds can
be overridden with `COMMAND_P95_MS` and `COMMAND_P99_MS`.

These are initial development thresholds, not production capacity claims. Run
the smoke profile before larger tests and monitor Docker CPU and memory usage.
Specialized crowded-room, contention, reconnect-storm, and post-run database
invariant scenarios remain listed in the project scalability plan.
