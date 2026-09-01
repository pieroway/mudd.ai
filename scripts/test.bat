@echo off
REM Test script for Windows (equivalent to scripts/test.sh)

echo Building test containers...
docker compose -f compose.test.yaml build
if errorlevel 1 goto error

echo Running backend unit tests...
docker compose -f compose.test.yaml run --rm backend_test
set BACKEND_EXIT=%errorlevel%

echo Stopping test services...
docker compose -f compose.test.yaml down

if %BACKEND_EXIT% neq 0 (
    echo FAILED: Unit tests failed. Deployment blocked.
    exit /b 1
)

echo SUCCESS: All unit tests passed!
exit /b 0

:error
echo ERROR: Docker compose build failed
exit /b 1
