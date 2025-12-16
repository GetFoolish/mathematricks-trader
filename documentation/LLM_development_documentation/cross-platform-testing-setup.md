# Cross-Platform Docker Testing & Setup Script Implementation Plan

## Overview

This plan implements a streamlined one-command setup system with automated testing capabilities for the mathematricks-trader Docker environment. The implementation includes setup scripts for Mac/Linux/Windows, automated cross-platform testing infrastructure, and comprehensive documentation.

## User Requirements Summary

1. **Fix Logging First** - Verify `make logs` shows all services (already working correctly)
2. **One-Command Setup** - Create setup scripts that Windows developers can run with a single command
3. **Automated Test Signal** - Setup script should accept `--test-signal` flag to demonstrate signal flow
4. **Cross-Platform Testing** - Test on Windows (Docker Desktop) and Linux containers from Mac
5. **Isolated Test Environments** - Test folders that can be manually deleted after validation

## Current State Analysis

### Existing Infrastructure ✓
- **Makefile line 33-34**: `make logs` already implements `docker-compose logs -f` (shows all services)
- **11 Docker services**: All configured in docker-compose.yml with proper dependencies
- **Test signal script**: `tests/signals_testing/send_test_signal.py` (fully functional)
- **Sample signal**: `tests/signals_testing/sample_signals/equity_simple_signal_1.json` (ENTRY+EXIT pair)
- **MongoDB seed data**: `seed_data/mongodb_dump/` with 9 collections

### What Needs to Be Built
1. Setup scripts (setup.sh, setup.ps1)
2. Cross-platform testing orchestration script
3. Testing documentation
4. Update existing documentation

---

## Implementation Plan

### Part 1: Create Setup Scripts (One-Command Developer Onboarding)

#### File 1: `setup.sh` (Mac/Linux)

**Location**: `/Users/vandanchopra/VandanStuff/CODE_STUFF/mathematricks/mathematricks-trader-docker-test/mathematricks-trader/setup.sh`

**Purpose**: Single-command setup for Unix-based systems

**Functionality**:
```bash
#!/bin/bash
# Usage: ./setup.sh [--test-signal]

# 1. Prerequisite Checks
- Check Docker installed and running
- Check docker-compose available
- Check .env file exists
- Display clear error messages with installation links

# 2. Build Containers
- Run: docker-compose build
- Show build progress
- Handle build failures gracefully

# 3. Start All Services
- Run: docker-compose up -d
- Monitor startup progress

# 4. Health Checks (with timeouts)
- MongoDB: Wait for replica set initialization (rs.status())
- PubSub Emulator: Wait for HTTP endpoint (localhost:8085)
- Services: Check logs for startup confirmation

# 5. Verify Seed Data
- Check MongoDB has 9 collections
- Validate data loaded correctly

# 6. Display Summary
- Show all service URLs
- List useful make commands
- Show next steps

# 7. Optional: Test Signal Flow (if --test-signal flag)
- Launch: docker-compose logs -f (in background or split display)
- Wait 10 seconds for services to stabilize
- Send test signal: python3 tests/signals_testing/send_test_signal.py --file ...
- Filter logs: show signal-ingestion → cerebro → execution flow
- Display expected output pattern
```

**Key Features**:
- Color-coded output (green ✓, red ✗, yellow ⚠)
- Progress indicators for long operations
- Timeout handling (max 60 seconds per health check)
- Graceful error handling with helpful messages
- Works with both `docker-compose` and `docker compose` commands

**Status**: ⬜ Not Started

#### File 2: `setup.ps1` (Windows)

**Location**: `/Users/vandanchopra/VandanStuff/CODE_STUFF/mathematricks/mathematricks-trader-docker-test/mathematricks-trader/setup.ps1`

**Purpose**: Single-command setup for Windows (PowerShell)

**Functionality**:
```powershell
# Usage: .\setup.ps1 [-TestSignal]

# Mirrors all functionality from setup.sh
# PowerShell-native implementation with same logic flow
# Uses PowerShell cmdlets and error handling
```

**Status**: ⬜ Not Started

---

### Part 2: Cross-Platform Testing Infrastructure

#### File 3: `test-cross-platform.sh`

**Location**: `/Users/vandanchopra/VandanStuff/CODE_STUFF/mathematricks/mathematricks-trader-docker-test/mathematricks-trader/test-cross-platform.sh`

**Purpose**: Automated cross-platform testing orchestration

**Functionality**:
```bash
#!/bin/bash
# Automates creation and testing of isolated environments

# Test Environment 1: Windows Simulation
# - Creates: ../test-environments/windows-simulation/
# - Clones fresh repo
# - Copies only .env file
# - Runs: bash setup.sh --test-signal
# - Validates all services
# - Logs results to test-results-windows.log

# Test Environment 2: Linux Container
# - Creates: ../test-environments/linux-container/
# - Runs Ubuntu container with Docker-in-Docker
# - Clones fresh repo inside container
# - Copies .env
# - Runs: bash setup.sh --test-signal
# - Validates all services
# - Logs results to test-results-linux.log

# Test Validation Criteria:
# ✓ All 11 services start
# ✓ MongoDB has 9 collections with seed data
# ✓ PubSub topics created
# ✓ Test signal flows through: signal_ingestion → cerebro → execution
# ✓ No errors in service logs
# ✓ Frontend accessible on port 5173

# Cleanup Option:
# - Prompt user to keep or delete test environments
# - Manual deletion supported
```

**Test Directory Structure**:
```
test-environments/
├── windows-simulation/
│   ├── mathematricks-trader/  # Fresh clone
│   ├── .env                   # Copied from main
│   └── test-results-windows.log
└── linux-container/
    ├── mathematricks-trader/  # Fresh clone
    ├── .env                   # Copied from main
    └── test-results-linux.log
```

**Status**: ⬜ Not Started

---

### Part 3: Documentation

#### File 4: `TESTING.md`

**Location**: `/Users/vandanchopra/VandanStuff/CODE_STUFF/mathematricks/mathematricks-trader-docker-test/mathematricks-trader/TESTING.md`

**Contents**:
```markdown
# Cross-Platform Testing Guide

## Quick Start
./setup.sh                  # Mac/Linux setup
.\setup.ps1                 # Windows setup
./setup.sh --test-signal    # Setup with automated test

## Automated Cross-Platform Testing
./test-cross-platform.sh    # Test Windows + Linux environments

## Manual Testing Procedures
### Windows Simulation (on Mac)
[Step-by-step instructions]

### Linux Container Test
[Step-by-step instructions]

### Actual Windows Testing
[Instructions for testing on real Windows machine]

## Test Validation
### Success Criteria
- All 11 services running
- MongoDB: 9 collections, 84+ documents
- Test signal flows: ENTRY → 15s wait → EXIT
- No errors in logs

### Expected Log Output
[Show example signal flow logs]

## Troubleshooting
- Port conflicts
- Docker not running
- .env file missing
- Service startup failures
```

**Status**: ⬜ Not Started

#### File 5: Update `SETUP.md`

**Location**: `/Users/vandanchopra/VandanStuff/CODE_STUFF/mathematricks/mathematricks-trader-docker-test/mathematricks-trader/SETUP.md`

**Changes**: Add new section at the beginning:

```markdown
## Quick Setup (Recommended for New Developers)

### One-Command Setup

**Mac/Linux:**
```bash
./setup.sh
```

**Windows:**
```powershell
.\setup.ps1
```

This automated script will:
- ✓ Check all prerequisites (Docker, docker-compose)
- ✓ Build all Docker containers
- ✓ Start all 11 services
- ✓ Initialize MongoDB with seed data
- ✓ Create Pub/Sub topics
- ✓ Verify everything is running
- ✓ Display service URLs and next steps

### Test with Signal Flow

To verify the entire trading pipeline works:

**Mac/Linux:**
```bash
./setup.sh --test-signal
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

## Manual Setup (Original Instructions)
[Keep existing detailed manual setup for troubleshooting]
```

**Status**: ⬜ Not Started

---

### Part 4: Implementation Details

#### Setup Script Components

**1. Prerequisite Checks**
```bash
# Docker check
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not installed"
    echo "Install: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Docker running check
if ! docker info &> /dev/null; then
    echo "❌ Docker daemon not running"
    echo "Start Docker Desktop and try again"
    exit 1
fi

# docker-compose check (supports both old and new CLI)
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif docker-compose --version &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "❌ Docker Compose not available"
    exit 1
fi

# .env file check
if [ ! -f .env ]; then
    echo "❌ .env file not found"
    echo "Copy .env.sample to .env and configure it"
    exit 1
fi
```

**2. MongoDB Health Check**
```bash
wait_for_mongodb() {
    echo "⏳ Waiting for MongoDB replica set..."
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if $COMPOSE_CMD exec -T mongodb \
           mongosh --quiet --eval "rs.status().ok" 2>/dev/null | grep -q "1"; then
            echo "✓ MongoDB ready"
            return 0
        fi
        sleep 2
        attempt=$((attempt + 1))
    done

    echo "❌ MongoDB timeout"
    return 1
}
```

**3. Test Signal Flow**
```bash
send_test_signal() {
    echo ""
    echo "========================================="
    echo "  SENDING TEST SIGNAL"
    echo "========================================="
    echo ""

    # Install Python dependencies
    pip3 install -q pymongo python-dotenv

    # Send signal
    python3 tests/signals_testing/send_test_signal.py \
        --file tests/signals_testing/sample_signals/equity_simple_signal_1.json

    echo ""
    echo "⏳ Watching for signal flow in logs..."
    echo "   Press Ctrl+C to stop"
    echo ""
    sleep 2

    # Display logs with signal flow filter
    $COMPOSE_CMD logs -f --tail=100 | \
        grep -E "(signal-ingestion|cerebro-service|execution-service)" | \
        grep -iE "(signal|ENTRY|EXIT|AAPL|Processing)"
}
```

**4. Success Summary**
```bash
print_summary() {
    echo ""
    echo "========================================="
    echo "  ✓ SETUP COMPLETE!"
    echo "========================================="
    echo ""
    echo "Access points:"
    echo "  Frontend:     http://localhost:5173"
    echo "  MongoDB:      mongodb://localhost:27018"
    echo "  Portfolio API: http://localhost:8003"
    echo "  Dashboard API: http://localhost:8004"
    echo ""
    echo "Useful commands:"
    echo "  make status   # Check services"
    echo "  make logs     # View all logs"
    echo "  make stop     # Stop everything"
    echo ""
}
```

---

### Part 5: Testing Strategy

#### Windows Testing (Docker Desktop on Windows)

**Approach**: Both Mac and Windows run Linux containers via Docker Desktop

**Key Insight**: The Docker engine behavior is identical on Mac and Windows. Both use:
- Linux containers (not Windows containers)
- Same docker-compose syntax
- Same networking model

**Testing Method**:
1. Simulate Windows environment on Mac (validates container behavior)
2. Provide PowerShell script for actual Windows users
3. Document manual Windows testing for final validation

**What We Can Test on Mac**:
- ✓ Container build and startup
- ✓ Service orchestration
- ✓ Network communication
- ✓ Volume mounts
- ✓ Health checks
- ✓ Signal flow

**What Requires Real Windows**:
- PowerShell script execution
- Windows path handling in scripts
- Windows line endings (CRLF)

#### Linux Container Testing

**Approach**: Run Ubuntu container with Docker-in-Docker

**Method**:
```bash
docker run -it --privileged \
  -v /var/run/docker.sock:/var/run/docker.sock \
  ubuntu:22.04 /bin/bash

# Inside container:
apt-get update && apt-get install -y docker.io docker-compose git python3
git clone <repo>
./setup.sh --test-signal
```

**Validates**:
- Pure Linux behavior
- Shell script compatibility
- Path handling
- Permission handling

---

## Critical Files Summary

### Files to Create (4 new files):

1. **setup.sh** - Main setup script for Mac/Linux
   - Full path: `mathematricks-trader/setup.sh`
   - ~300 lines with functions, health checks, test signal integration
   - **Status**: ✅ Complete

2. **setup.ps1** - Setup script for Windows PowerShell
   - Full path: `mathematricks-trader/setup.ps1`
   - Mirrors bash script functionality
   - **Status**: ⬜ Not Started

3. **test-cross-platform.sh** - Automated testing orchestration
   - Full path: `mathematricks-trader/test-cross-platform.sh`
   - Creates isolated test environments, runs tests, collects results
   - **Status**: ⬜ Not Started

4. **TESTING.md** - Comprehensive testing documentation
   - Full path: `mathematricks-trader/TESTING.md`
   - Testing procedures, validation criteria, troubleshooting
   - **Status**: ⬜ Not Started

### Files to Modify (1 file):

1. **SETUP.md** - Add Quick Setup section at top
   - Full path: `mathematricks-trader/SETUP.md`
   - Insert new section referencing setup.sh/setup.ps1
   - Keep existing manual instructions for reference
   - **Status**: ⬜ Not Started

### Files NOT Modified (Already Perfect):

- ✓ `Makefile` - Line 33-34 `make logs` already works
- ✓ `docker-compose.yml` - No changes needed
- ✓ `tests/signals_testing/send_test_signal.py` - Already functional
- ✓ All service code - No changes needed

---

## Expected Developer Experience

### Before (Current State):
```bash
# Read SETUP.md
# Install Docker, Git, Python
# Clone repo
cp .env.sample .env
# Edit .env with credentials
make rebuild
make start
make status
# Manually verify each service
# Manually test signals
```
**Time**: ~30-60 minutes + troubleshooting

### After (With Setup Script):
```bash
# Clone repo
cp .env.sample .env  # Edit credentials
./setup.sh --test-signal
```
**Time**: ~10 minutes (mostly Docker build time)

**What Developer Sees**:
```
========================================
  Mathematricks Trader Setup
========================================

✓ Docker installed
✓ Docker running
✓ docker-compose available
✓ .env file found

Building containers...
  [████████████████████] 100%

Starting services...
✓ All services started

Waiting for MongoDB replica set...
✓ MongoDB ready

Waiting for PubSub emulator...
✓ PubSub ready

Verifying seed data...
✓ Found 9 collections in MongoDB

========================================
  ✓ SETUP COMPLETE!
========================================

Access points:
  Frontend:     http://localhost:5173
  MongoDB:      mongodb://localhost:27018

Sending test signal...
✓ Test signal sent

Watching for signal flow...
  signal-ingestion    | Received ENTRY signal for AAPL
  cerebro-service     | Processing signal sig_1702396800_1234
  execution-service   | Order placed: BUY 10 AAPL
  [15 second wait]
  signal-ingestion    | Received EXIT signal for AAPL
  execution-service   | Order placed: SELL 10 AAPL
```

---

## Success Criteria

### Setup Script Success:
- [ ] One command starts entire environment
- [ ] All 11 services running
- [ ] MongoDB initialized with 9 collections
- [ ] PubSub topics created
- [ ] Health checks pass
- [ ] Clear error messages on failures
- [ ] Works on Mac, Linux, Windows

### Test Signal Success:
- [ ] Signal inserted to MongoDB
- [ ] signal-ingestion picks it up
- [ ] cerebro-service processes it
- [ ] execution-service receives order
- [ ] ENTRY and EXIT both flow through
- [ ] Logs clearly show the flow
- [ ] No errors

### Cross-Platform Testing Success:
- [ ] Isolated test environments created
- [ ] Fresh git clone works
- [ ] Only .env dependency validated
- [ ] Windows simulation passes
- [ ] Linux container test passes
- [ ] Results logged for review
- [ ] Clean manual deletion possible

---

## Implementation Sequence

1. **Create setup.sh** - Core Unix setup script
2. **Test locally on Mac** - Validate without --test-signal
3. **Add --test-signal support** - Integrate signal flow testing
4. **Create setup.ps1** - Windows PowerShell version
5. **Create test-cross-platform.sh** - Testing orchestration
6. **Run cross-platform tests** - Validate both environments
7. **Create TESTING.md** - Document testing procedures
8. **Update SETUP.md** - Add Quick Setup section
9. **Final validation** - Run complete test suite

---

## Notes

- **Logging**: Current `make logs` already perfect (no changes needed)
- **Isolation**: Test environments use fresh clones + .env only
- **Windows**: PowerShell script enables one-command setup for Windows devs
- **Testing**: Fully automated testing validates cross-platform compatibility
- **Cleanup**: Test folders are persistent for manual inspection/deletion

---

## Progress Tracker

Last Updated: 2025-12-16

### Completed:
- [x] Plan created and documented
- [x] Plan saved to LLM_development_documentation

### In Progress:
- [ ] Implementing files

### Next Steps:
1. Create setup.sh with all prerequisite checks and health validations
2. Test setup.sh locally on Mac
3. Add --test-signal flag functionality
4. Create Windows PowerShell equivalent (setup.ps1)
5. Build cross-platform testing script
6. Run full test suite validation
