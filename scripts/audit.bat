@echo off
setlocal

echo Building pinned dependency-audit images...
docker compose -f compose.test.yaml build backend_test frontend_test
if errorlevel 1 goto infrastructure_failure
docker build -t muddai-e2e ./e2e
if errorlevel 1 goto infrastructure_failure

echo Auditing Python dependencies ^(all advisories block^)...
docker compose -f compose.test.yaml run --rm --no-deps backend_test pip-audit --local
set "BACKEND_EXIT=%ERRORLEVEL%"

echo Auditing frontend dependencies ^(high and critical advisories block^)...
docker compose -f compose.test.yaml run --rm --no-deps frontend_test npm audit --audit-level=high --fetch-retries=2 --fetch-timeout=60000
if errorlevel 1 (
  echo Frontend audit failed; retrying once in case the advisory service was unavailable...
  docker compose -f compose.test.yaml run --rm --no-deps frontend_test npm audit --audit-level=high --fetch-retries=2 --fetch-timeout=60000
)
set "FRONTEND_EXIT=%ERRORLEVEL%"

echo Auditing Playwright dependencies ^(high and critical advisories block^)...
docker run --rm muddai-e2e npm audit --audit-level=high --fetch-retries=2 --fetch-timeout=60000
if errorlevel 1 (
  echo Playwright audit failed; retrying once in case the advisory service was unavailable...
  docker run --rm muddai-e2e npm audit --audit-level=high --fetch-retries=2 --fetch-timeout=60000
)
set "E2E_EXIT=%ERRORLEVEL%"

docker compose -f compose.test.yaml down
if not "%BACKEND_EXIT%"=="0" goto audit_failure
if not "%FRONTEND_EXIT%"=="0" goto audit_failure
if not "%E2E_EXIT%"=="0" goto audit_failure

echo Dependency audit passed.
exit /b 0

:infrastructure_failure
set "AUDIT_EXIT=%ERRORLEVEL%"
docker compose -f compose.test.yaml down
echo Dependency audit could not start because an image build or registry operation failed.
exit /b %AUDIT_EXIT%

:audit_failure
echo Dependency audit failed. Review each tool's output to distinguish advisories from registry/service errors.
exit /b 1
