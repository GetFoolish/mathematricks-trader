# Cross-Platform Testing Guide

## Quick Start

### One-Command Setup

**Mac/Linux:**
```bash
./setup.sh
```

**Windows:**
```powershell
.\setup.ps1
```

### Setup with Test Signal

To verify the entire trading pipeline works:

**Mac/Linux:**
```bash
./setup.sh --TestSignal
```

**Windows:**
```powershell
.\setup.ps1 -TestSignal
```

This will:
- Run the full setup
- Send a test ENTRY+EXIT signal for AAPL
- Display logs showing signal flow through all services
- Validate end-to-end functionality

---

## Automated Cross-Platform Testing

### Running All Tests

```bash
./test-cross-platform.sh
```

This script will:
1. Create isolated test environments
2. Test Windows simulation (Docker on Mac)
3. Test Linux container (Ubuntu with Docker-in-Docker)
4. Generate test report

Test environments are created in: `../test-environments/`

---

## Manual Testing Procedures

### Windows Simulation Test (on Mac)

This tests that the setup works in an environment similar to Windows Docker Desktop:

```bash
# 1. Create test directory
mkdir -p /path/to/test-environments/windows-simulation
cd /path/to/test-environments/windows-simulation

# 2. Clone repository
git clone https://github.com/GetFoolish/mathematricks-trader.git
cd mathematricks-trader
git checkout mathematricks-trader-v4a-dockerized

# 3. Copy .env file (ONLY dependency)
cp /path/to/main/project/.env .env

# 4. Run setup
bash setup.sh

# 5. Verify services
make status

# 6. Test signal flow
make send-test-signal

# 7. View logs
make logs

# 8. Cleanup
make clean
```

### Linux Container Test

This tests pure Linux environment behavior:

```bash
# 1. Create test directory
mkdir -p /path/to/test-environments/linux-container
cd /path/to/test-environments/linux-container

# 2. Copy .env file
cp /path/to/main/project/.env .env

# 3. Run Ubuntu container with Docker-in-Docker
docker run --privileged \
  --name mathematricks-linux-test \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd):/workspace \
  ubuntu:22.04 \
  bash

# 4. Inside container - Install dependencies
apt-get update && apt-get install -y git python3 python3-pip curl
pip3 install docker-compose

# 5. Clone and setup
cd /workspace
git clone https://github.com/GetFoolish/mathematricks-trader.git
cd mathematricks-trader
git checkout mathematricks-trader-v4a-dockerized
cp /workspace/.env .env

# 6. Run setup
bash setup.sh

# 7. Test and validate
make status
make send-test-signal
make logs

# 8. Exit and cleanup
exit
docker rm -f mathematricks-linux-test
```

### Actual Windows Testing

**Prerequisites:**
- Windows 10/11 machine
- Docker Desktop for Windows
- Git for Windows
- PowerShell 5.1+

**Process:**

```powershell
# 1. Create test directory
New-Item -Path C:\temp\mathematricks-test -ItemType Directory
Set-Location C:\temp\mathematricks-test

# 2. Clone repository
git clone https://github.com/GetFoolish/mathematricks-trader.git
Set-Location mathematricks-trader
git checkout mathematricks-trader-v4a-dockerized

# 3. Copy .env file
# (Transfer .env file from Mac via secure method)
Copy-Item path\to\.env .env

# 4. Run PowerShell setup
.\setup.ps1

# 5. Verify
.\make.bat status

# 6. Test with signal
.\setup.ps1 -TestSignal

# 7. Cleanup
.\make.bat clean
Set-Location ..\..
Remove-Item -Recurse -Force mathematricks-test
```

---

## Test Validation

### Success Criteria

A successful test must meet ALL of these criteria:

#### 1. Services Running
```bash
make status
```
Expected: All 11 services showing as "Up"
- cerebro-service
- execution-service
- signal-ingestion
- account-data-service
- portfolio-builder
- dashboard-creator
- ib-gateway
- frontend
- mongodb
- pubsub-emulator
- pubsub-init (exits after initialization)

#### 2. MongoDB Seed Data
```bash
docker-compose exec mongodb mongosh --eval "db.getSiblingDB('mathematricks_trading').getCollectionNames()"
```
Expected: 9+ collections loaded:
- signal_store
- current_allocation
- fund_state
- account_hierarchy
- dashboard_snapshots
- portfolio_tests
- account_state
- trading_accounts
- trading_signals_raw

#### 3. PubSub Topics Created
```bash
curl http://localhost:8085/
```
Expected: HTTP 200 response

#### 4. Test Signal Flow

Send test signal:
```bash
make send-test-signal
```

Watch logs:
```bash
make logs
```

**Expected Log Pattern:**

```
signal-ingestion    | Received signal: ENTRY for AAPL
signal-ingestion    | Signal ID: sig_1702396800_1234
cerebro-service     | Processing signal sig_1702396800_1234
cerebro-service     | Position sizing: BUY 10 shares AAPL
execution-service   | Order placed: BUY 10 AAPL @ MARKET

[15 second wait]

signal-ingestion    | Received signal: EXIT for AAPL
signal-ingestion    | Signal ID: sig_1702396815_5678
cerebro-service     | Processing EXIT signal
execution-service   | Order placed: SELL 10 AAPL @ MARKET
```

#### 5. No Critical Errors
```bash
make logs | grep -i "error\|fatal\|crashed"
```
Expected: No critical errors (warnings are acceptable)

#### 6. Frontend Accessible
```bash
curl http://localhost:5173
```
Expected: HTTP 200 response

---

## Expected Output Examples

### Successful Setup Output

```
=========================================
  Mathematricks Trader Setup
=========================================

✓ Docker is installed
✓ Docker daemon is running
✓ Docker Compose is available (modern CLI)
✓ .env file found

Building Docker containers...
✓ Containers built successfully

Starting all services...
✓ All services started

Waiting for MongoDB replica set...
✓ MongoDB replica set is ready

Waiting for PubSub emulator...
✓ PubSub emulator is ready

Waiting for application services to start...
✓ Application services started successfully

Verifying MongoDB seed data...
✓ Seed data loaded successfully (9 collections)

=========================================
  ✓ SETUP COMPLETE!
=========================================

Access points:
  Frontend:     http://localhost:5173
  MongoDB:      mongodb://localhost:27018
  Portfolio API: http://localhost:8003
  Dashboard API: http://localhost:8004
```

### Successful Test Signal Output

```
================================================================================
✅ Test Signal Inserted Successfully (ENTRY)
================================================================================
Signal ID:    sig_1734386400_1234
Strategy:     SPX_1-D_Opt
Action:       BUY 10 AAPL (1 legs)
Type:         ENTRY
Staging:      Yes
MongoDB ID:   6758f1a0b2c3d4e5f6789012
Timestamp:    2025-12-16T18:00:00.000000+00:00
================================================================================

📡 Signal should be picked up by signal_ingestion via Change Stream

💡 Monitor logs:
   tail -f logs/signal_ingestion.log    # Should show signal received
   tail -f logs/cerebro_service.log      # Should show position sizing
   tail -f logs/execution_service.log    # Should show order placement

⏳ Waiting for signal_ingestion to process ENTRY signal...
✓ ENTRY signal processed - signal_store ID: 6758f1a0b...

[15 second wait with same process for EXIT signal]
```

---

## Troubleshooting

### Common Issues

#### Docker Not Running
**Error:** `Cannot connect to the Docker daemon`
**Solution:** Start Docker Desktop

#### Port Conflicts
**Error:** `port is already allocated`
**Solution:**
```bash
# Check what's using the port
lsof -i :27018  # or whatever port

# Stop conflicting service or change port in docker-compose.yml
```

#### .env File Missing
**Error:** `.env file not found`
**Solution:**
```bash
cp .env.sample .env
# Edit .env with your credentials
```

#### MongoDB Not Initializing
**Error:** `MongoDB did not become ready in time`
**Solution:**
```bash
# Check MongoDB logs
docker-compose logs mongodb

# Try restarting
docker-compose restart mongodb

# If persists, clean volumes and restart
make clean
make start
```

#### Service Startup Failures
**Error:** `Some services may have errors`
**Solution:**
```bash
# Check specific service logs
make logs-cerebro
make logs-execution
make logs-signal-ingestion

# Common issues:
# - Missing dependencies in requirements.txt
# - Syntax errors in service code
# - Configuration errors in .env
```

#### Python Package Issues
**Error:** `No module named 'pymongo'`
**Solution:**
```bash
# For local testing (outside Docker)
pip3 install pymongo python-dotenv

# For Docker services
docker-compose build
docker-compose restart <service-name>
```

#### Signal Not Flowing
**Error:** Signal sent but not processed
**Solution:**
```bash
# 1. Check MongoDB Change Streams
docker-compose exec mongodb mongosh --eval "db.getSiblingDB('mathematricks_trading').trading_signals_raw.find().limit(1)"

# 2. Check signal-ingestion service
make logs-signal-ingestion

# 3. Verify PubSub is running
curl http://localhost:8085/

# 4. Check service connectivity
docker-compose exec cerebro-service ping -c 1 mongodb
```

---

## Test Results Interpretation

### Test Report Structure

After running `./test-cross-platform.sh`, you'll get a report:

```
Test Environments:
==================

1. Windows Simulation Test
   Location: ../test-environments/windows-simulation
   Status: ✓ PASSED
   Logs: ../test-environments/windows-simulation/test-results-windows.log

2. Linux Container Test
   Location: ../test-environments/linux-container
   Status: ✓ PASSED
   Logs: ../test-environments/linux-container/test-results-linux.log
```

### Reviewing Test Logs

```bash
# Windows simulation logs
cat ../test-environments/windows-simulation/test-results-windows.log

# Linux container logs
cat ../test-environments/linux-container/test-results-linux.log

# Look for:
# - Service startup messages
# - Health check confirmations
# - Signal processing logs
# - Any error patterns
```

---

## Performance Benchmarks

### Expected Timing

- **Setup Time**: 5-10 minutes (first run with Docker image pulls)
- **Subsequent Runs**: 2-3 minutes (images cached)
- **Service Startup**: 30-60 seconds
- **MongoDB Initialization**: 10-20 seconds
- **Test Signal Flow**: 15-20 seconds (includes wait time)

### Resource Usage

- **RAM**: 4GB minimum, 8GB recommended
- **Disk**: 20GB minimum (includes Docker images and volumes)
- **CPU**: 4 cores recommended
- **Network**: Internet required for initial setup (GitHub, Docker Hub)

---

## Cleaning Up Test Environments

### Manual Cleanup

```bash
# Stop and remove containers
cd /path/to/test-environment/mathematricks-trader
make clean

# Delete test directory
cd ../..
rm -rf test-environments
```

### Automated Cleanup

The `test-cross-platform.sh` script prompts for cleanup at the end:
```
Are you sure you want to delete? (y/N):
```

Answer `y` to delete or `N` to preserve for inspection.

---

## CI/CD Integration (Future)

For automated testing in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
name: Cross-Platform Docker Test

on:
  push:
    branches: [ main, staging ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Create .env
        run: cp .env.sample .env
      - name: Run setup
        run: ./setup.sh
      - name: Test signal flow
        run: make send-test-signal
      - name: Collect logs
        if: always()
        run: docker-compose logs > test-logs.txt
      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: test-logs
          path: test-logs.txt
```

---

## Additional Resources

- **SETUP.md**: Detailed manual setup instructions
- **docker-compose.yml**: Service configuration
- **Makefile**: Available commands reference
- **setup.sh**: Script source code
- **test-cross-platform.sh**: Testing script source code

---

## Support

If you encounter issues not covered in this guide:

1. Check service logs: `make logs-<service-name>`
2. Verify Docker is running: `docker info`
3. Review .env configuration
4. Check GitHub issues for similar problems
5. Create a new issue with:
   - Operating system and version
   - Docker version
   - Error messages
   - Relevant logs
