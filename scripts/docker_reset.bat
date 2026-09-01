@echo off
REM Clean up Docker state and restart

echo Stopping and removing all containers/networks...
docker compose down

echo Pruning unused Docker networks...
docker network prune -f

echo Starting development environment...
docker compose up -d

echo.
echo If services don't start, try:
echo   docker compose down -v
echo   docker compose up -d --build
