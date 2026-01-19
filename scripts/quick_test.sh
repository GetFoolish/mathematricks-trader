#!/bin/bash
##############################################################################
# Quick Test Runner for Tuesday Market Testing
#
# This script provides a streamlined workflow for running market tests:
# - Pre-flight checks
# - Test signal sending
# - Log monitoring
#
# Usage:
#   ./scripts/quick_test.sh                    # Interactive menu
#   ./scripts/quick_test.sh preflight          # Run preflight checks only
#   ./scripts/quick_test.sh cleanup            # Clean up test data
#   ./scripts/quick_test.sh send AAPL          # Send AAPL test signal
#   ./scripts/quick_test.sh send SPY           # Send SPY test signal
#   ./scripts/quick_test.sh send QQQ           # Send QQQ test signal
#   ./scripts/quick_test.sh send NVDA          # Send NVDA test signal
#   ./scripts/quick_test.sh exit AAPL          # Send AAPL exit signal
#   ./scripts/quick_test.sh logs               # Tail all logs
##############################################################################

set -e  # Exit on error

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

##############################################################################
# Functions
##############################################################################

print_header() {
    echo -e "\n${BOLD}${BLUE}========================================${NC}"
    echo -e "${BOLD}${BLUE}$1${NC}"
    echo -e "${BOLD}${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

run_preflight_checks() {
    print_header "🚀 PRE-FLIGHT CHECKS"
    python3 scripts/preflight_check.py
    
    if [ $? -eq 0 ]; then
        print_success "All checks passed!"
        return 0
    else
        print_error "Pre-flight checks failed!"
        return 1
    fi
}

cleanup_test_data() {
    print_header "🧹 CLEANUP TEST DATA"
    
    echo -e "${YELLOW}This will remove stale signals, orders, and closed positions.${NC}"
    echo -e "${YELLOW}Open positions will be preserved.${NC}\n"
    
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        python3 scripts/cleanup_test_data.py
        print_success "Cleanup complete!"
    else
        print_info "Cleanup cancelled"
    fi
}

send_test_signal() {
    local symbol=$1
    print_header "📤 SENDING $symbol TEST SIGNAL"
    
    case $symbol in
        AAPL)
            node signal-senders/UPRO_NewYork.js
            ;;
        SPY)
            node signal-senders/test_signals/SPY_NewYork.js
            ;;
        QQQ)
            node signal-senders/test_signals/QQQ_NewYork.js
            ;;
        NVDA)
            node signal-senders/test_signals/NVDA_NewYork.js
            ;;
        *)
            print_error "Unknown symbol: $symbol"
            echo "Available: AAPL, SPY, QQQ, NVDA"
            return 1
            ;;
    esac
    
    if [ $? -eq 0 ]; then
        print_success "Signal sent!"
        print_info "Watch logs for execution: ./scripts/quick_test.sh logs"
    else
        print_error "Failed to send signal"
        return 1
    fi
}

send_exit_signal() {
    local symbol=$1
    print_header "📤 SENDING $symbol EXIT SIGNAL"
    
    case $symbol in
        AAPL)
            node signal-senders/test_signals/AAPL_EXIT.js
            ;;
        *)
            print_error "Exit signal not available for: $symbol"
            echo "Available: AAPL"
            return 1
            ;;
    esac
    
    if [ $? -eq 0 ]; then
        print_success "Exit signal sent!"
        print_info "Watch logs for execution: ./scripts/quick_test.sh logs"
    else
        print_error "Failed to send exit signal"
        return 1
    fi
}

tail_logs() {
    print_header "📋 TAILING LOGS"
    print_info "Press Ctrl+C to stop"
    echo
    
    # Tail signal processing log (shows complete flow)
    if [ -f "logs/signal_processing.log" ]; then
        tail -f logs/signal_processing.log
    else
        print_error "Signal processing log not found"
        print_info "Falling back to Docker logs..."
        docker logs -f mathematricks-trader-cerebro-service-1
    fi
}

show_menu() {
    print_header "🧪 QUICK TEST MENU"
    
    echo "1. Run Pre-Flight Checks"
    echo "2. Clean Up Test Data"
    echo "3. Send AAPL Signal"
    echo "4. Send SPY Signal"
    echo "5. Send QQQ Signal"
    echo "6. Send NVDA Signal"
    echo "7. Send AAPL Exit Signal"
    echo "8. Tail Logs"
    echo "9. Exit"
    echo
    
    read -p "Select option (1-9): " choice
    
    case $choice in
        1) run_preflight_checks ;;
        2) cleanup_test_data ;;
        3) send_test_signal AAPL ;;
        4) send_test_signal SPY ;;
        5) send_test_signal QQQ ;;
        6) send_test_signal NVDA ;;
        7) send_exit_signal AAPL ;;
        8) tail_logs ;;
        9) exit 0 ;;
        *) print_error "Invalid option"; show_menu ;;
    esac
}

##############################################################################
# Main
##############################################################################

if [ $# -eq 0 ]; then
    # No arguments - show interactive menu
    while true; do
        show_menu
        echo
        read -p "Press Enter to continue..." dummy
    done
else
    # Parse command-line arguments
    case $1 in
        preflight)
            run_preflight_checks
            ;;
        cleanup)
            cleanup_test_data
            ;;
        send)
            if [ -z "$2" ]; then
                print_error "Usage: $0 send <SYMBOL>"
                echo "Available: AAPL, SPY, QQQ, NVDA"
                exit 1
            fi
            send_test_signal "$2"
            ;;
        exit)
            if [ -z "$2" ]; then
                print_error "Usage: $0 exit <SYMBOL>"
                echo "Available: AAPL"
                exit 1
            fi
            send_exit_signal "$2"
            ;;
        logs)
            tail_logs
            ;;
        *)
            print_error "Unknown command: $1"
            echo
            echo "Usage:"
            echo "  $0                     # Interactive menu"
            echo "  $0 preflight           # Run pre-flight checks"
            echo "  $0 cleanup             # Clean up test data"
            echo "  $0 send <SYMBOL>       # Send test signal (AAPL, SPY, QQQ, NVDA)"
            echo "  $0 exit <SYMBOL>       # Send exit signal (AAPL)"
            echo "  $0 logs                # Tail logs"
            exit 1
            ;;
    esac
fi
