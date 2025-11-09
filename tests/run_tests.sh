#!/bin/bash

# Mathematricks Trader Test Runner
# Runs integration tests with HTML report generation

set -e

echo "=========================================="
echo "Mathematricks Trader Integration Tests"
echo "=========================================="
echo ""

# Navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Check if Python venv exists
PYTHON_PATH="/Users/vandanchopra/VandanStuff/CODE_STUFF/mathematricks-trader/venv/bin/python"

if [ ! -f "$PYTHON_PATH" ]; then
    echo "❌ Python virtual environment not found at: $PYTHON_PATH"
    echo "   Please update the path in this script or create the venv"
    exit 1
fi

echo "Using Python: $PYTHON_PATH"
echo ""

# Install test dependencies if needed
echo "Installing test dependencies..."
$PYTHON_PATH -m pip install -q -r tests/requirements.txt
echo "✅ Test dependencies installed"
echo ""

# Check if services are running
echo "Checking service health..."

check_service() {
    local service_name=$1
    local url=$2

    if curl -s -f -o /dev/null "$url"; then
        echo "  ✅ $service_name is running"
        return 0
    else
        echo "  ❌ $service_name is not responding at $url"
        return 1
    fi
}

SERVICES_OK=true

check_service "CerebroService" "http://localhost:8001/health" || SERVICES_OK=false
check_service "AccountDataService" "http://localhost:8002/health" || SERVICES_OK=false
check_service "Pub/Sub Emulator" "http://localhost:8085" || SERVICES_OK=false

if [ "$SERVICES_OK" = false ]; then
    echo ""
    echo "⚠️  Some services are not running!"
    echo "   Run './run_mvp_demo.sh' to start all services"
    echo ""
    read -p "Continue with tests anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "=========================================="
echo "Running Tests..."
echo "=========================================="
echo ""

# Run pytest with options
# Default: Stop after 5 failures (use --maxfail=0 to run all tests)
if [[ ! "$@" =~ "--maxfail" ]]; then
    MAXFAIL_ARG="--maxfail=5"
else
    MAXFAIL_ARG=""
fi

$PYTHON_PATH -m pytest tests/integration/ \
    -v \
    --tb=short \
    --html=tests/reports/test_report.html \
    --self-contained-html \
    $MAXFAIL_ARG \
    "$@"

TEST_EXIT_CODE=$?

echo ""
echo "=========================================="
echo "Test Results"
echo "=========================================="

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "✅ All tests passed!"
else
    echo "❌ Some tests failed (exit code: $TEST_EXIT_CODE)"
fi

echo ""
echo "📊 HTML Report: tests/reports/test_report.html"
echo ""

# Open HTML report in browser (macOS)
if [ -f "tests/reports/test_report.html" ]; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Opening report in browser..."
        open "tests/reports/test_report.html"
    fi
fi

exit $TEST_EXIT_CODE
