@echo off
setlocal

echo Building and starting the application stack...
docker compose up -d --build --wait
if errorlevel 1 goto failure

echo Building the Playwright test image...
docker build -t muddai-e2e ./e2e
if errorlevel 1 goto failure

echo Running browser tests...
docker run --rm --add-host=host.docker.internal:host-gateway -e E2E_BASE_URL=http://host.docker.internal:5173 muddai-e2e
if errorlevel 1 goto failure

echo Playwright tests passed.
exit /b 0

:failure
echo Playwright tests failed.
exit /b 1
