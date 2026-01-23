# Test Framework Quick Start

## Quick Commands

### Via Makefile (Recommended)
```bash
# Preflight checks - verify system is ready
make test-preflight

# Comprehensive suite - full test workflow
make test-comprehensive

# Individual test categories
make test-unit
make test-integration
make test-e2e
make test-coverage
```

### Via Test Runner Script
```bash
# Interactive menu
./tests/run_tests.sh

# Direct commands
./tests/run_tests.sh preflight
./tests/run_tests.sh comprehensive
./tests/run_tests.sh unit
./tests/run_tests.sh coverage
```

### Via Pytest Directly
```bash
# Using virtual environment
./.venv/bin/python -m pytest -v

# Specific markers
./.venv/bin/python -m pytest -m smoke -v
./.venv/bin/python -m pytest -m unit -v
./.venv/bin/python -m pytest -m integration -v
```

## Test Categories

### 🚀 Preflight Checks (`-m smoke`)
**Purpose:** Verify system is ready before running tests  
**When to use:** Before starting any testing session

Tests include:
- ✓ Docker daemon running
- ✓ Required containers running
- ✓ MongoDB connection
- ✓ Required collections exist
- ✓ Active strategies configured
- ✓ Trading accounts configured
- ✓ IBKR gateway reachable
- ✓ Services healthy
- ✓ Environment variables set
- ✓ Required packages installed

```bash
make test-preflight
# or
./tests/run_tests.sh preflight
# or
./.venv/bin/python -m pytest -m smoke -v
```

### 🎯 Comprehensive Suite
**Purpose:** Full test workflow with progressive checks  
**When to use:** Before deployment, weekly regression testing

Workflow:
1. **Preflight Checks** - Verify system readiness
2. **Unit Tests** - Test individual components
3. **Signal Testing** - End-to-end signal flow (optional)

```bash
make test-comprehensive
# or
./tests/run_tests.sh comprehensive
```

### 🔬 Unit Tests (`-m unit`)
**Purpose:** Test individual functions/classes in isolation  
**Speed:** Fast (<1s per test)  
**When to use:** During development, TDD

```bash
make test-unit
# or
./.venv/bin/python -m pytest -m unit -v
```

### 🔗 Integration Tests (`-m integration`)
**Purpose:** Test multiple components working together  
**Speed:** Medium (1-10s per test)  
**When to use:** After unit tests pass

```bash
make test-integration
# or
./.venv/bin/python -m pytest -m integration -v
```

### 🌐 End-to-End Tests (`-m e2e`)
**Purpose:** Test complete user workflows  
**Speed:** Slow (10s+ per test)  
**When to use:** Final validation before deployment

```bash
make test-e2e
# or
./.venv/bin/python -m pytest -m e2e -v
```

## Test Files Structure

```
tests/
├── unit/                           # Unit tests
│   ├── test_signal_ingestion.py   # Signal validation, enrichment
│   ├── test_execution_service.py  # Order creation, execution
│   └── test_preflight_checks.py   # System readiness checks
│
├── integration/                    # Integration tests
│   └── test_signal_flow_integration.py
│
├── e2e/                           # End-to-end tests
│   └── test_trade_scenarios.py
│
└── fixtures/                      # Shared test fixtures
    ├── broker_fixtures.py
    └── database_fixtures.py
```

## Common Workflows

### Before Starting Work
```bash
# Quick health check
make test-preflight
```

### During Development
```bash
# Run unit tests for the module you're working on
./.venv/bin/python -m pytest tests/unit/test_signal_ingestion.py -v

# Watch mode (re-run on file changes)
./.venv/bin/python -m pytest-watch -- tests/unit/test_signal_ingestion.py -v
```

### Before Committing
```bash
# Run all fast tests
make test-fast

# Or run comprehensive suite
make test-comprehensive
```

### Before Deploying
```bash
# Full test suite with coverage
make test-coverage

# Review coverage report
open htmlcov/index.html
```

## Debugging Tests

### Run Single Test
```bash
./.venv/bin/python -m pytest tests/unit/test_signal_ingestion.py::TestSignalValidation::test_valid_entry_signal -v
```

### Extra Verbose Output
```bash
./.venv/bin/python -m pytest -vv --tb=long
```

### Stop on First Failure
```bash
./.venv/bin/python -m pytest -x
```

### Show Print Statements
```bash
./.venv/bin/python -m pytest -s
```

### Run Failed Tests Only
```bash
./.venv/bin/python -m pytest --lf  # Last failed
./.venv/bin/python -m pytest --ff  # Failed first, then rest
```

## Test Markers

Use markers to run specific test categories:

```bash
# Smoke tests (preflight)
./.venv/bin/python -m pytest -m smoke

# Fast tests only
./.venv/bin/python -m pytest -m "not slow"

# Critical tests only
./.venv/bin/python -m pytest -m critical

# Database tests
./.venv/bin/python -m pytest -m database

# Broker tests
./.venv/bin/python -m pytest -m broker
```

## Environment Setup

### First Time Setup
```bash
# Install test dependencies (already in requirements.txt)
./.venv/bin/pip install pytest pytest-asyncio pytest-cov pytest-timeout

# Verify setup
./.venv/bin/python -m pytest --version
```

### Clean Test Artifacts
```bash
make test-clean
# or
./tests/run_tests.sh clean
```

## Success Criteria

✅ **All preflight checks pass** - System is ready  
✅ **Unit tests pass** - Individual components work  
✅ **Integration tests pass** - Components work together  
✅ **E2E tests pass** - Complete workflows work  
✅ **Coverage > 80%** - Code is well-tested  

## Getting Help

```bash
# Show all make targets
make help

# Show test runner options
./tests/run_tests.sh help

# Show pytest options
./.venv/bin/python -m pytest --help
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'pytest'"
```bash
./.venv/bin/pip install pytest pytest-asyncio
```

### "MongoDB connection failed"
```bash
# Check MongoDB is running
docker ps | grep mongo

# Check connection string
echo $MONGO_URI
```

### "Docker containers not running"
```bash
# Start services
make start

# Check status
make status
```

### Tests are slow
```bash
# Run only fast tests
make test-fast

# Run tests in parallel (install pytest-xdist first)
./.venv/bin/pip install pytest-xdist
./.venv/bin/python -m pytest -n auto
```
