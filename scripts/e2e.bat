@echo off
setlocal

set "E2E_HEADED="
if not "%~2"=="" goto usage
if "%~1"=="" goto start
if /I not "%~1"=="--headed" goto usage
set "E2E_HEADED=1"

:start
echo Building and starting the isolated E2E stack...
docker compose -p muddai-e2e -f compose.e2e.yaml up -d --build --wait
if errorlevel 1 goto failure

echo Creating the isolated browser-test admin account...
docker compose -p muddai-e2e -f compose.e2e.yaml exec -T backend_e2e python - < e2e\seed_admin.py
if errorlevel 1 goto failure

if defined E2E_HEADED goto headed

echo Building the Playwright test image...
docker build -t muddai-e2e ./e2e
if errorlevel 1 goto failure

echo Running browser tests...
if not exist e2e\test-results mkdir e2e\test-results
docker run --rm --add-host=host.docker.internal:host-gateway -e E2E_BASE_URL=http://host.docker.internal:15173 -v "%cd%\e2e\test-results:/tests/test-results" muddai-e2e
if errorlevel 1 goto failure

goto success

:headed
echo Running visible Chromium tests on Windows, one worker at a time...
where node >nul 2>&1
if errorlevel 1 goto missing_node
where npm >nul 2>&1
if errorlevel 1 goto missing_node
pushd e2e
if errorlevel 1 goto failure
call npm ci
if errorlevel 1 goto headed_failure
call npx playwright install chromium
if errorlevel 1 goto headed_failure
set "E2E_BASE_URL=http://localhost:15173"
call npm test -- --headed --workers=1
if errorlevel 1 goto headed_failure
popd
goto success

:headed_failure
popd
goto failure

:missing_node
echo Headed tests require Node.js and npm installed on Windows.
goto failure

:usage
echo Usage: scripts\e2e.bat [--headed]
exit /b 2

:success
docker compose -p muddai-e2e -f compose.e2e.yaml down -v
echo Playwright tests passed.
exit /b 0

:failure
docker compose -p muddai-e2e -f compose.e2e.yaml logs --tail 120 backend_e2e
docker compose -p muddai-e2e -f compose.e2e.yaml down -v
echo Playwright tests failed.
exit /b 1
