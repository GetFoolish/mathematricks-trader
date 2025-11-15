#!/bin/bash
# Stop all MVP services gracefully

# Use current directory as project root
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
PID_DIR="$LOG_DIR/pids"

echo "Stopping MVP services..."

# Function to stop all PIDs in a file
stop_service() {
    local pid_file="$1"
    local service_name="$2"

    if [ -f "$pid_file" ]; then
        local pids=$(cat "$pid_file")
        local killed_count=0

        for pid in $pids; do
            if kill "$pid" 2>/dev/null; then
                killed_count=$((killed_count + 1))
            fi
        done

        if [ $killed_count -gt 0 ]; then
            echo "✓ $service_name stopped ($killed_count process(es))"
        fi

        rm "$pid_file"
    fi
}

# Stop services in reverse order (via PID files)
stop_service "$PID_DIR/frontend.pid" "Admin Frontend"
stop_service "$PID_DIR/signal_ingestion.pid" "SignalIngestionService"
stop_service "$PID_DIR/execution_service.pid" "ExecutionService"
stop_service "$PID_DIR/cerebro_service.pid" "CerebroService"
stop_service "$PID_DIR/dashboard_creator.pid" "DashboardCreatorService"
stop_service "$PID_DIR/portfolio_builder.pid" "PortfolioBuilderService"
stop_service "$PID_DIR/account_data_service.pid" "AccountDataService"
stop_service "$PID_DIR/pubsub.pid" "Pub/Sub emulator"

# Cleanup orphaned processes (not tracked by PID files)
echo ""
echo "Checking for orphaned processes..."

# Function to kill all processes matching a pattern
kill_all_matching() {
    local pattern="$1"
    local service_name="$2"
    local pids=$(pgrep -f "$pattern")
    if [ -n "$pids" ]; then
        echo "✓ Killing orphaned $service_name processes:"
        for pid in $pids; do
            echo "  - PID $pid"
            kill -9 "$pid" 2>/dev/null
        done
    fi
}

# Kill all Python service processes (more aggressive)
kill_all_matching "signal_ingestion/main.py --staging" "signal_ingestion (staging)"
kill_all_matching "signal_ingestion/main.py" "signal_ingestion"
kill_all_matching "services/cerebro_service/main.py" "cerebro_service"
kill_all_matching "services/execution_service/main.py" "execution_service"
kill_all_matching "services/dashboard_creator/main.py" "dashboard_creator"
kill_all_matching "services/account_data_service/main.py" "account_data_service"
kill_all_matching "services/portfolio_builder/main.py" "portfolio_builder"

# Kill processes on known ports (show PIDs)
PIDS=$(lsof -ti:8001 2>/dev/null)
if [ -n "$PIDS" ]; then
    echo "✓ Killed process on port 8001 (cerebro): PIDs $PIDS"
    kill $PIDS 2>/dev/null
fi

PIDS=$(lsof -ti:8002 2>/dev/null)
if [ -n "$PIDS" ]; then
    echo "✓ Killed process on port 8002 (account_data): PIDs $PIDS"
    kill $PIDS 2>/dev/null
fi

PIDS=$(lsof -ti:8003 2>/dev/null)
if [ -n "$PIDS" ]; then
    echo "✓ Killed process on port 8003 (portfolio_builder): PIDs $PIDS"
    kill $PIDS 2>/dev/null
fi

PIDS=$(lsof -ti:8004 2>/dev/null)
if [ -n "$PIDS" ]; then
    echo "✓ Killed process on port 8004 (dashboard_creator): PIDs $PIDS"
    kill $PIDS 2>/dev/null
fi

PIDS=$(lsof -ti:8085 2>/dev/null)
if [ -n "$PIDS" ]; then
    echo "✓ Killed process on port 8085 (pubsub): PIDs $PIDS"
    kill $PIDS 2>/dev/null
fi

PIDS=$(lsof -ti:5173 2>/dev/null)
if [ -n "$PIDS" ]; then
    echo "✓ Killed process on port 5173 (frontend): PIDs $PIDS"
    kill $PIDS 2>/dev/null
fi

echo ""
echo "✓ All services stopped"
