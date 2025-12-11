# Mathematricks Trader - Tools

## Overview

This directory contains utility scripts and tools for managing the Mathematricks Trader system.

## Service Management

### check_services.sh

Check if all required services are running.

**Usage:**
```bash
./tools/check_services.sh
```

**Checks:**
- CerebroService (port 8001)
- AccountDataService (port 8002)
- ExecutionService (background process)
- Pub/Sub Emulator (port 8085)
- signal_collector (background process)
- Admin Frontend (port 5173)

**Output:**
```
Checking Mathematricks Trader Services...

✅ CerebroService is running (PID: 12345) on port 8001
✅ AccountDataService is running (PID: 12346) on port 8002
✅ Pub/Sub Emulator is running (PID: 12347) on port 8085
✅ signal_collector is running (PID: 12348)
✅ ExecutionService is running (PID: 12349)
✅ Admin Frontend is running (PID: 12350) on port 5173

All services are running!
```

### setup_pubsub_emulator.sh

Setup and configure Google Cloud Pub/Sub emulator for local development.

**Usage:**
```bash
./tools/setup_pubsub_emulator.sh
```

**What it does:**
1. Starts Pub/Sub emulator on port 8085
2. Creates all required topics:
   - `standardized-signals` - Signals from signal_collector to Cerebro
   - `trading-orders` - Orders from Cerebro to ExecutionService
   - `execution-confirmations` - Order fills from ExecutionService
   - `account-updates` - Account state updates
   - `order-commands` - Order management commands

3. Creates all required subscriptions:
   - `standardized-signals-sub` - For CerebroService
   - `trading-orders-sub` - For ExecutionService
   - `execution-confirmations-sub` - For AccountDataService
   - `account-updates-sub` - For monitoring
   - `order-commands-sub` - For ExecutionService

**Environment Variables:**
Sets `PUBSUB_EMULATOR_HOST=localhost:8085` so services connect to emulator instead of GCP.

## Development Workflow

### Starting Fresh

```bash
# 1. Setup Pub/Sub emulator
./tools/setup_pubsub_emulator.sh

# 2. Check services
./tools/check_services.sh

# 3. Start all services (if not running)
./run_mvp_demo.sh
```

### Troubleshooting

If Pub/Sub topics/subscriptions are missing:

```bash
# Re-run setup script
./tools/setup_pubsub_emulator.sh
```

If ports are already in use:

```bash
# Stop all services
./stop_mvp_demo.sh

# Check what's using ports
lsof -i :8001  # CerebroService
lsof -i :8002  # AccountDataService
lsof -i :8085  # Pub/Sub Emulator
lsof -i :5173  # Frontend

# Kill specific port if needed
kill -9 $(lsof -t -i:8085)
```

## Adding New Tools

When adding new utility scripts to this directory:

1. **Make executable:** `chmod +x tools/your_script.sh`
2. **Add shebang:** `#!/bin/bash` at top of file
3. **Add help text:** Include usage instructions
4. **Update this README:** Document the new tool
5. **Test thoroughly:** Ensure script works on fresh install

## Contact

For questions about tools, see:
- `/documentation/MathematricksTraderSystemCleanup.md` - System architecture
- `/documentation/CLAUDE.md` - Project instructions
