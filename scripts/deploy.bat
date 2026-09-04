@echo off
setlocal

if not exist .env copy .env.example .env

echo Running required test gate...
call scripts\test.bat
if errorlevel 1 goto failure

call scripts\validate-production.bat
if errorlevel 1 goto failure

echo Building application images...
docker compose build
if errorlevel 1 goto failure

echo Starting application stack and waiting for health checks...
docker compose up -d --wait
if errorlevel 1 goto failure

echo Running Playwright workflow...
call scripts\e2e.bat
if errorlevel 1 goto failure

echo Running smoke load test and authoritative-state checks...
call scripts\load-test.bat smoke
if errorlevel 1 goto failure

echo Deployment gate passed.
echo Frontend: http://localhost:5173
echo Backend:  http://localhost:8000
exit /b 0

:failure
echo Deployment stopped because a required stage failed.
exit /b 1
