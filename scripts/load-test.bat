@echo off
setlocal

set "PROFILE=%~1"
if "%PROFILE%"=="" set "PROFILE=smoke"

if "%PROFILE%"=="smoke" (
  set "LOAD_VUS=10"
  set "LOAD_DURATION=30s"
  set "SESSION_SECONDS=15"
  set "THINK_TIME_MS=1000"
  set "COMMAND_P95_MS=1000"
  set "COMMAND_P99_MS=2000"
) else if "%PROFILE%"=="baseline" (
  set "LOAD_VUS=100"
  set "LOAD_DURATION=5m"
  set "SESSION_SECONDS=60"
  set "THINK_TIME_MS=1000"
  set "COMMAND_P95_MS=500"
  set "COMMAND_P99_MS=1000"
) else if "%PROFILE%"=="stress" (
  set "LOAD_VUS=500"
  set "LOAD_DURATION=10m"
  set "SESSION_SECONDS=90"
  set "THINK_TIME_MS=750"
  set "COMMAND_P95_MS=500"
  set "COMMAND_P99_MS=1000"
) else (
  echo Unknown load-test profile: %PROFILE%
  exit /b 2
)

set "RUN_ID=%RANDOM%%RANDOM%"
echo Starting isolated %PROFILE% load-test stack...
docker compose -f compose.load.yaml up -d --build backend_load
if errorlevel 1 goto :failed

docker compose -f compose.load.yaml run --rm k6
set "TEST_EXIT=%ERRORLEVEL%"
docker compose -f compose.load.yaml down -v
exit /b %TEST_EXIT%

:failed
set "TEST_EXIT=%ERRORLEVEL%"
docker compose -f compose.load.yaml down -v
exit /b %TEST_EXIT%
