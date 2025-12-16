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
if "%1"=="logs-signal-ingestion" goto logs-signal-ingestion
if "%1"=="logs-account-data" goto logs-account-data
if "%1"=="logs-portfolio" goto logs-portfolio
if "%1"=="logs-dashboard" goto logs-dashboard
if "%1"=="logs-mongodb" goto logs-mongodb
if "%1"=="send-test-signal" goto send-test-signal
if "%1"=="restart-cerebro" goto restart-cerebro
if "%1"=="restart-execution" goto restart-execution
if "%1"=="restart-signal-ingestion" goto restart-signal-ingestion
if "%1"=="restart-account-data" goto restart-account-data
if "%1"=="restart-portfolio" goto restart-portfolio
if "%1"=="restart-dashboard" goto restart-dashboard
if "%1"=="rebuild" goto rebuild
if "%1"=="clean" goto clean

echo Unknown target: %1
goto help

:help
echo Mathematricks Trader - Docker Management (Windows)
echo --------------------------------------------------
echo .\make.bat start                  - Start all services in background
echo .\make.bat stop                   - Stop all services
echo .\make.bat restart                - Restart all services
echo .\make.bat status                 - Check status of services
echo .\make.bat logs                   - View logs of all services
echo .\make.bat logs-cerebro           - View logs of cerebro-service
echo .\make.bat logs-execution         - View logs of execution-service
echo .\make.bat logs-frontend          - View logs of frontend
echo .\make.bat logs-signal-ingestion  - View logs of signal-ingestion
echo .\make.bat logs-account-data      - View logs of account-data-service
echo .\make.bat logs-portfolio         - View logs of portfolio-builder
echo .\make.bat logs-dashboard         - View logs of dashboard-creator
echo .\make.bat logs-mongodb           - View logs of mongodb
echo .\make.bat send-test-signal       - Send test ENTRY+EXIT signal for AAPL
echo .\make.bat restart-cerebro        - Restart cerebro-service
echo .\make.bat restart-execution      - Restart execution-service
echo .\make.bat restart-signal-ingestion - Restart signal-ingestion
echo .\make.bat restart-account-data   - Restart account-data-service
echo .\make.bat restart-portfolio      - Restart portfolio-builder
echo .\make.bat restart-dashboard      - Restart dashboard-creator
echo .\make.bat rebuild                - Rebuild all containers
echo .\make.bat clean                  - Stop and remove all containers and volumes (DATA LOSS!)
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
docker-compose logs -f cerebro-service execution-service signal-ingestion account-data-service portfolio-builder dashboard-creator ib-gateway frontend pubsub-emulator
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

:logs-signal-ingestion
docker-compose logs -f signal-ingestion
exit /b %errorlevel%

:logs-account-data
docker-compose logs -f account-data-service
exit /b %errorlevel%

:logs-portfolio
docker-compose logs -f portfolio-builder
exit /b %errorlevel%

:logs-dashboard
docker-compose logs -f dashboard-creator
exit /b %errorlevel%

:logs-mongodb
docker-compose logs -f mongodb
exit /b %errorlevel%

:send-test-signal
REM Try venv first, then fall back to system python
if exist ".\venv\Scripts\python.exe" (
    .\venv\Scripts\python.exe tests\signals_testing\send_test_signal.py --file tests\signals_testing\sample_signals\equity_simple_signal_1.json
) else (
    python tests\signals_testing\send_test_signal.py --file tests\signals_testing\sample_signals\equity_simple_signal_1.json
)
exit /b %errorlevel%

:restart-cerebro
docker-compose restart cerebro-service
exit /b %errorlevel%

:restart-execution
docker-compose restart execution-service
exit /b %errorlevel%

:restart-signal-ingestion
docker-compose restart signal-ingestion
exit /b %errorlevel%

:restart-account-data
docker-compose restart account-data-service
exit /b %errorlevel%

:restart-portfolio
docker-compose restart portfolio-builder
exit /b %errorlevel%

:restart-dashboard
docker-compose restart dashboard-creator
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
