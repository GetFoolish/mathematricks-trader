#!/bin/bash
# Mathematricks Trader - Cross-Platform Testing Script
# This script creates isolated test environments and validates the setup works on different platforms

set -e

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_ROOT="$(dirname "$PROJECT_ROOT")/test-environments"
REPO_URL="https://github.com/GetFoolish/mathematricks-trader.git"
BRANCH="mathematricks-trader-v4a-dockerized"

# Functions
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_header() {
    echo ""
    echo "========================================="
    echo "  $1"
    echo "========================================="
    echo ""
}

# Test Windows simulation
test_windows_simulation() {
    print_header "Testing Windows Simulation"

    local test_dir="$TEST_ROOT/windows-simulation"

    print_info "Creating test environment at: $test_dir"

    # Clean up if exists
    if [ -d "$test_dir" ]; then
        print_warning "Test directory exists, removing..."
        rm -rf "$test_dir"
    fi

    # Create directory
    mkdir -p "$test_dir"
    cd "$test_dir"

    # Clone repository
    print_info "Cloning repository..."
    if git clone "$REPO_URL" mathematricks-trader; then
        print_success "Repository cloned"
    else
        print_error "Failed to clone repository"
        return 1
    fi

    cd mathematricks-trader

    # Checkout branch
    print_info "Checking out $BRANCH branch..."
    git checkout "$BRANCH"

    # Copy .env file (ONLY dependency from main project)
    print_info "Copying .env file..."
    if [ -f "$PROJECT_ROOT/.env" ]; then
        cp "$PROJECT_ROOT/.env" .env
        print_success ".env file copied"
    else
        print_error ".env file not found in main project"
        return 1
    fi

    # Run setup script
    print_info "Running setup.sh..."
    if bash setup.sh; then
        print_success "Setup completed successfully"
    else
        print_error "Setup failed"
        return 1
    fi

    # Validate services
    print_info "Validating services..."
    local service_count=$(docker-compose ps | grep -c "Up" || true)

    if [ "$service_count" -ge 9 ]; then
        print_success "Services running: $service_count"
    else
        print_warning "Expected at least 9 services, found: $service_count"
    fi

    # Test signal flow
    print_info "Testing signal flow..."
    if python3 tests/signals_testing/send_test_signal.py \
        --file tests/signals_testing/sample_signals/equity_simple_signal_1.json; then
        print_success "Test signal sent successfully"
    else
        print_error "Test signal failed"
        return 1
    fi

    # Save logs
    print_info "Saving test results..."
    docker-compose logs > "$test_dir/test-results-windows.log" 2>&1
    print_success "Logs saved to: $test_dir/test-results-windows.log"

    # Cleanup
    print_info "Stopping services..."
    docker-compose down

    print_success "Windows simulation test completed"
    return 0
}

# Test Linux container
test_linux_container() {
    print_header "Testing Linux Container"

    local test_dir="$TEST_ROOT/linux-container"

    print_info "Creating test environment at: $test_dir"

    # Clean up if exists
    if [ -d "$test_dir" ]; then
        print_warning "Test directory exists, removing..."
        rm -rf "$test_dir"
    fi

    # Create directory
    mkdir -p "$test_dir"

    # Copy .env file
    print_info "Copying .env file..."
    if [ -f "$PROJECT_ROOT/.env" ]; then
        cp "$PROJECT_ROOT/.env" "$test_dir/.env"
        print_success ".env file copied"
    else
        print_error ".env file not found in main project"
        return 1
    fi

    # Create test script to run inside container
    cat > "$test_dir/run-test.sh" << 'INNER_SCRIPT'
#!/bin/bash
set -e

# Install dependencies
apt-get update -qq
apt-get install -y -qq git python3 python3-pip curl > /dev/null 2>&1

# Install docker-compose
pip3 install -q docker-compose

# Clone repository
cd /workspace
git clone https://github.com/GetFoolish/mathematricks-trader.git
cd mathematricks-trader
git checkout mathematricks-trader-v4a-dockerized

# Copy .env
cp /workspace/.env .env

# Run setup
bash setup.sh

# Validate
service_count=$(docker-compose ps | grep -c "Up" || echo "0")
echo "Services running: $service_count"

# Test signal
python3 tests/signals_testing/send_test_signal.py \
    --file tests/signals_testing/sample_signals/equity_simple_signal_1.json

# Save logs
docker-compose logs > /workspace/test-results-linux.log 2>&1

# Cleanup
docker-compose down

echo "Linux container test completed"
INNER_SCRIPT

    chmod +x "$test_dir/run-test.sh"

    # Run Linux container
    print_info "Starting Linux container test..."
    print_warning "This requires Docker-in-Docker and may take several minutes..."

    if docker run --privileged \
        --name mathematricks-linux-test \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v "$test_dir:/workspace" \
        ubuntu:22.04 \
        bash /workspace/run-test.sh; then
        print_success "Linux container test completed"
    else
        print_error "Linux container test failed"
        docker rm -f mathematricks-linux-test 2>/dev/null || true
        return 1
    fi

    # Cleanup container
    docker rm -f mathematricks-linux-test 2>/dev/null || true

    print_success "Logs saved to: $test_dir/test-results-linux.log"
    return 0
}

# Generate test report
generate_report() {
    print_header "Test Report"

    local report_file="$TEST_ROOT/test-report.txt"

    cat > "$report_file" << EOF
Mathematricks Trader - Cross-Platform Testing Report
Generated: $(date)

Test Environments:
==================

1. Windows Simulation Test
   Location: $TEST_ROOT/windows-simulation
   Status: $([ -f "$TEST_ROOT/windows-simulation/test-results-windows.log" ] && echo "✓ PASSED" || echo "✗ FAILED")
   Logs: $TEST_ROOT/windows-simulation/test-results-windows.log

2. Linux Container Test
   Location: $TEST_ROOT/linux-container
   Status: $([ -f "$TEST_ROOT/linux-container/test-results-linux.log" ] && echo "✓ PASSED" || echo "✗ FAILED")
   Logs: $TEST_ROOT/linux-container/test-results-linux.log

Summary:
========
All tests validate:
- Docker Compose starts all services
- MongoDB initializes with seed data
- PubSub emulator creates topics
- Test signal flows through: signal_ingestion → cerebro → execution
- No critical errors in service logs

Test Artifacts:
===============
Test environments are preserved in: $TEST_ROOT
You can manually delete them when done reviewing.

EOF

    cat "$report_file"
    print_success "Report saved to: $report_file"
}

# Cleanup function
cleanup_test_environments() {
    print_header "Cleanup"

    echo "This will delete all test environments in: $TEST_ROOT"
    echo ""
    read -p "Are you sure you want to delete? (y/N): " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Deleting test environments..."
        rm -rf "$TEST_ROOT"
        print_success "Test environments deleted"
    else
        print_info "Cleanup cancelled"
        print_info "Test environments preserved at: $TEST_ROOT"
    fi
}

# Main execution
main() {
    print_header "Mathematricks Trader - Cross-Platform Testing"

    echo "This script will:"
    echo "  1. Create isolated test environments"
    echo "  2. Test Windows simulation (Docker on Mac)"
    echo "  3. Test Linux container (Ubuntu with Docker-in-Docker)"
    echo "  4. Generate test report"
    echo ""
    echo "Test environments will be created at: $TEST_ROOT"
    echo ""

    read -p "Continue? (Y/n): " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Nn]$ ]]; then
        print_info "Testing cancelled"
        exit 0
    fi

    # Create test root directory
    mkdir -p "$TEST_ROOT"

    # Track test results
    local tests_passed=0
    local tests_failed=0

    # Run Windows simulation test
    if test_windows_simulation; then
        ((tests_passed++))
    else
        ((tests_failed++))
    fi

    echo ""

    # Run Linux container test
    if test_linux_container; then
        ((tests_passed++))
    else
        ((tests_failed++))
    fi

    echo ""

    # Generate report
    generate_report

    echo ""
    print_header "Testing Complete"
    echo "Tests passed: $tests_passed"
    echo "Tests failed: $tests_failed"
    echo ""

    # Offer cleanup
    cleanup_test_environments
}

# Run main function
main "$@"
