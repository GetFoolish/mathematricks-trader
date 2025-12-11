#!/bin/bash
# Check if required services for live testing are running

echo "🔍 Checking service status..."
echo "================================"

check_service() {
    local service_name=$1
    local port=$2
    
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "✅ $service_name (port $port) - RUNNING"
        return 0
    else
        echo "❌ $service_name (port $port) - NOT RUNNING"
        return 1
    fi
}

all_running=true

# Check all services
check_service "Signal Ingestion" 3002 || all_running=false
check_service "Cerebro Service" 8001 || all_running=false
check_service "Account Data" 8002 || all_running=false
check_service "Execution Service" 8003 || all_running=false

echo "================================"

if $all_running; then
    echo "✅ All services are running!"
    echo ""
    echo "Ready to run live signal tester:"
    echo "  python live_signal_tester.py --interval 10 --count 5"
    exit 0
else
    echo "❌ Some services are not running"
    echo ""
    echo "Start all services with:"
    echo "  ./run_mvp_demo.sh"
    echo ""
    echo "Then run the tester:"
    echo "  python live_signal_tester.py --interval 10 --count 5"
    exit 1
fi
