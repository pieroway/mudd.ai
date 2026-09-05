@echo off
setlocal

echo Building and starting the isolated E2E stack...
docker compose -p muddai-e2e -f compose.e2e.yaml up -d --build --wait
if errorlevel 1 goto failure

echo Building the Playwright test image...
docker build -t muddai-e2e ./e2e
if errorlevel 1 goto failure

echo Running browser tests...
if not exist e2e\test-results mkdir e2e\test-results
docker run --rm --add-host=host.docker.internal:host-gateway -e E2E_BASE_URL=http://host.docker.internal:15173 -v "%cd%\e2e\test-results:/tests/test-results" muddai-e2e
if errorlevel 1 goto failure

docker compose -p muddai-e2e -f compose.e2e.yaml down -v
echo Playwright tests passed.
exit /b 0

:failure
docker compose -p muddai-e2e -f compose.e2e.yaml down -v
echo Playwright tests failed.
exit /b 1
