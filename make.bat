@echo off
setlocal

REM Default target if none provided
if "%1"=="" goto help

if "%1"=="help" goto help
if "%1"=="start" goto start
if "%1"=="stop" goto stop
if "%1"=="restart" goto restart
if "%1"=="status" goto status
if "%1"=="logs" goto logs
if "%1"=="logs-cerebro" goto logs-cerebro
if "%1"=="logs-execution" goto logs-execution
if "%1"=="logs-frontend" goto logs-frontend
if "%1"=="restart-cerebro" goto restart-cerebro
if "%1"=="rebuild" goto rebuild
if "%1"=="clean" goto clean

echo Unknown target: %1
goto help

:help
echo Mathematricks Trader - Docker Management (Windows Wrapper)
echo --------------------------------------------------------
echo .\make.bat start          - Start all services in background
echo .\make.bat stop           - Stop all services
echo .\make.bat restart        - Restart all services
echo .\make.bat status         - Check status of services
echo .\make.bat logs           - View logs of all services
echo .\make.bat logs-cerebro   - View logs of cerebro-service
echo .\make.bat logs-execution - View logs of execution-service
echo .\make.bat rebuild        - Rebuild all containers
echo .\make.bat clean          - Stop and remove all containers and volumes (DATA LOSS!)
exit /b 0

:start
docker-compose up -d
exit /b %errorlevel%

:stop
docker-compose stop
exit /b %errorlevel%

:restart
docker-compose restart
exit /b %errorlevel%

:status
docker-compose ps
exit /b %errorlevel%

:logs
docker-compose logs -f
exit /b %errorlevel%

:logs-cerebro
docker-compose logs -f cerebro-service
exit /b %errorlevel%

:logs-execution
docker-compose logs -f execution-service
exit /b %errorlevel%

:logs-frontend
docker-compose logs -f frontend
exit /b %errorlevel%

:restart-cerebro
docker-compose restart cerebro-service
exit /b %errorlevel%

:rebuild
docker-compose build
exit /b %errorlevel%

:clean
echo WARNING: This will remove all containers and volumes.
echo Press Ctrl+C to cancel or wait 5 seconds...
timeout /t 5
docker-compose down -v
exit /b %errorlevel%
