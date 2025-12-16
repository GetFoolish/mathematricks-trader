#!/bin/bash
# Mathematricks Trader - One-Command Setup Script
# Usage: ./setup.sh [--TestSignal]

set -e  # Exit on error

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Flags
TEST_SIGNAL=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --TestSignal)
            TEST_SIGNAL=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Usage: ./setup.sh [--TestSignal]"
            exit 1
            ;;
    esac
done

# Function to print colored messages
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

# Check if Docker is installed
check_docker_installed() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        echo "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop"
        exit 1
    fi
    print_success "Docker is installed"
}

# Check if Docker daemon is running
check_docker_running() {
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running"
        echo "Please start Docker Desktop and try again"
        exit 1
    fi
    print_success "Docker daemon is running"
}

# Check docker-compose availability (supports both old and new CLI)
check_docker_compose() {
    if docker compose version &> /dev/null 2>&1 || docker-compose --version &> /dev/null 2>&1; then
        print_success "Docker Compose is available"
    else
        print_error "Docker Compose is not available"
        echo "Please install Docker Desktop which includes Docker Compose"
        exit 1
    fi
}

# Check if .env file exists
check_env_file() {
    if [ ! -f .env ]; then
        print_error ".env file not found"
        echo ""
        echo "Please create a .env file from the template:"
        echo "  cp .env.sample .env"
        echo ""
        echo "Then edit .env with your credentials"
        exit 1
    fi
    print_success ".env file found"
}

# Build Docker containers
build_containers() {
    print_info "Building Docker containers (this may take a few minutes)..."
    if make rebuild; then
        print_success "Containers built successfully"
    else
        print_error "Failed to build containers"
        echo "Check the error messages above for details"
        exit 1
    fi
}

# Start all services
start_services() {
    print_info "Starting all services..."
    if make start; then
        print_success "All services started"
    else
        print_error "Failed to start services"
        echo "Run 'make logs' to check for errors"
        exit 1
    fi
}

# Wait for MongoDB replica set to be ready
wait_for_mongodb() {
    print_info "Waiting for MongoDB replica set (max 60 seconds)..."
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if docker-compose exec -T mongodb \
           mongosh --quiet --eval "rs.status().ok" 2>/dev/null | grep -q "1"; then
            print_success "MongoDB replica set is ready"
            return 0
        fi

        if [ $((attempt % 5)) -eq 0 ]; then
            echo "  Still waiting... (attempt $attempt/$max_attempts)"
        fi

        sleep 2
        attempt=$((attempt + 1))
    done

    print_error "MongoDB did not become ready in time"
    echo "Check MongoDB logs with: make logs-mongodb"
    return 1
}

# Wait for PubSub emulator to be ready
wait_for_pubsub() {
    print_info "Waiting for PubSub emulator (max 60 seconds)..."
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:8085/ &>/dev/null; then
            print_success "PubSub emulator is ready"
            return 0
        fi

        if [ $((attempt % 5)) -eq 0 ]; then
            echo "  Still waiting... (attempt $attempt/$max_attempts)"
        fi

        sleep 2
        attempt=$((attempt + 1))
    done

    print_error "PubSub emulator did not start in time"
    echo "Check logs with: make logs"
    return 1
}

# Verify MongoDB seed data
verify_seed_data() {
    print_info "Verifying MongoDB seed data..."

    local collection_count=$(docker-compose exec -T mongodb \
        mongosh --quiet --eval \
        "db.getSiblingDB('mathematricks_trading').getCollectionNames().length" \
        2>/dev/null | tail -1)

    if [ "$collection_count" -ge 9 ]; then
        print_success "Seed data loaded successfully ($collection_count collections)"
        return 0
    else
        print_warning "Expected 9 collections, found $collection_count"
        echo "Seed data may not be fully loaded"
        return 1
    fi
}

# Wait for application services to stabilize
wait_for_services() {
    print_info "Waiting for application services to start (10 seconds)..."
    sleep 10

    # Check for critical error patterns in logs
    if docker-compose logs --tail=50 2>&1 | grep -i "error.*failed to start\|fatal\|crashed" &>/dev/null; then
        print_warning "Some services may have errors"
        echo "Check logs with: make logs"
    else
        print_success "Application services started successfully"
    fi
}

# Send test signal
send_test_signal() {
    print_header "SENDING TEST SIGNAL"

    print_info "This will send a test ENTRY+EXIT signal pair for AAPL"
    print_info "Watch the logs to see signal propagation through services"
    echo ""

    # Check if Python 3 is available
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required to send test signals"
        echo "Please install Python 3.11+ and try again"
        return 1
    fi

    # Install required Python packages
    print_info "Installing Python dependencies..."
    pip3 install -q pymongo python-dotenv 2>&1 | grep -v "Requirement already satisfied" || true

    # Send signal
    print_info "Sending test signal..."
    echo ""
    if python3 tests/signals_testing/send_test_signal.py \
        --file tests/signals_testing/sample_signals/equity_simple_signal_1.json; then
        echo ""
        print_success "Test signal sent successfully"
    else
        print_error "Failed to send test signal"
        return 1
    fi

    echo ""
    print_info "Watching for signal flow in logs..."
    print_info "You should see: signal-ingestion → cerebro-service → execution-service"
    print_info "Press Ctrl+C to stop watching logs"
    echo ""
    sleep 3

    # Display filtered logs showing signal flow
    make logs | grep -iE "(signal|ENTRY|EXIT|AAPL|Processing|Order)" || true
}

# Print summary
print_summary() {
    print_header "✓ SETUP COMPLETE!"

    echo "Access points:"
    echo "  Frontend Dashboard:  http://localhost:5173"
    echo "                      (username: admin, password: admin)"
    echo "  MongoDB:            mongodb://localhost:27018"
    echo "  PubSub Emulator:    http://localhost:8085"
    echo "  Portfolio Builder:  http://localhost:8003"
    echo "  Dashboard Creator:  http://localhost:8004"
    echo ""
    echo "Useful commands:"
    echo "  make status         - Check service status"
    echo "  make logs           - View all logs (streaming)"
    echo "  make logs-cerebro   - View cerebro service logs"
    echo "  make stop           - Stop all services"
    echo "  make restart        - Restart all services"
    echo ""
    echo "Send test signal:"
    echo "  python3 tests/signals_testing/send_test_signal.py \\"
    echo "    --file tests/signals_testing/sample_signals/equity_simple_signal_1.json"
    echo ""
    echo "Documentation:"
    echo "  SETUP.md           - Detailed setup guide"
    echo "  TESTING.md         - Testing procedures"
    echo ""
}

# Main execution
main() {
    print_header "Mathematricks Trader Setup"

    # Prerequisite checks
    check_docker_installed
    check_docker_running
    check_docker_compose
    check_env_file

    echo ""

    # Build and start
    build_containers
    echo ""
    start_services

    echo ""

    # Health checks
    wait_for_mongodb
    wait_for_pubsub
    wait_for_services

    echo ""

    # Verify data
    verify_seed_data

    echo ""

    # Print summary
    print_summary

    # Optional: Send test signal
    if [ "$TEST_SIGNAL" = true ]; then
        send_test_signal
    fi
}

# Run main function
main "$@"
