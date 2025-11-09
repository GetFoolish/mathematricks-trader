#!/bin/bash
# Stop all MVP services gracefully

PROJECT_ROOT="/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader"
LOG_DIR="$PROJECT_ROOT/logs"

echo "Stopping MVP services..."

# Stop services in reverse order (via PID files)
if [ -f "$LOG_DIR/frontend.pid" ]; then
    kill $(cat "$LOG_DIR/frontend.pid") 2>/dev/null && echo "✓ Admin Frontend stopped"
    rm "$LOG_DIR/frontend.pid"
fi

if [ -f "$LOG_DIR/signal_ingestion.pid" ]; then
    kill $(cat "$LOG_DIR/signal_ingestion.pid") 2>/dev/null && echo "✓ SignalIngestionService stopped"
    rm "$LOG_DIR/signal_ingestion.pid"
fi

if [ -f "$LOG_DIR/execution_service.pid" ]; then
    kill $(cat "$LOG_DIR/execution_service.pid") 2>/dev/null && echo "✓ ExecutionService stopped"
    rm "$LOG_DIR/execution_service.pid"
fi

if [ -f "$LOG_DIR/cerebro_service.pid" ]; then
    kill $(cat "$LOG_DIR/cerebro_service.pid") 2>/dev/null && echo "✓ CerebroService stopped"
    rm "$LOG_DIR/cerebro_service.pid"
fi

if [ -f "$LOG_DIR/portfolio_builder.pid" ]; then
    kill $(cat "$LOG_DIR/portfolio_builder.pid") 2>/dev/null && echo "✓ PortfolioBuilderService stopped"
    rm "$LOG_DIR/portfolio_builder.pid"
fi

if [ -f "$LOG_DIR/account_data_service.pid" ]; then
    kill $(cat "$LOG_DIR/account_data_service.pid") 2>/dev/null && echo "✓ AccountDataService stopped"
    rm "$LOG_DIR/account_data_service.pid"
fi

if [ -f "$LOG_DIR/pubsub.pid" ]; then
    kill $(cat "$LOG_DIR/pubsub.pid") 2>/dev/null && echo "✓ Pub/Sub emulator stopped"
    rm "$LOG_DIR/pubsub.pid"
fi

# Cleanup orphaned processes (not tracked by PID files)
echo ""
echo "Checking for orphaned processes..."

# Kill any remaining service processes
pkill -f "services/signal_ingestion/main.py" 2>/dev/null && echo "✓ Killed orphaned signal_ingestion processes"
pkill -f "services/cerebro_service/main.py" 2>/dev/null && echo "✓ Killed orphaned cerebro_service processes"
pkill -f "services/execution_service/main.py" 2>/dev/null && echo "✓ Killed orphaned execution_service processes"
pkill -f "services/account_data_service/main.py" 2>/dev/null && echo "✓ Killed orphaned account_data_service processes"
pkill -f "services/portfolio_builder/main.py" 2>/dev/null && echo "✓ Killed orphaned portfolio_builder processes"

# Kill processes on known ports (only report if PIDs found)
PIDS=$(lsof -ti:8001 2>/dev/null)
[ -n "$PIDS" ] && kill $PIDS 2>/dev/null && echo "✓ Killed process on port 8001 (cerebro)"

PIDS=$(lsof -ti:8002 2>/dev/null)
[ -n "$PIDS" ] && kill $PIDS 2>/dev/null && echo "✓ Killed process on port 8002 (account_data)"

PIDS=$(lsof -ti:8003 2>/dev/null)
[ -n "$PIDS" ] && kill $PIDS 2>/dev/null && echo "✓ Killed process on port 8003 (portfolio_builder)"

PIDS=$(lsof -ti:8085 2>/dev/null)
[ -n "$PIDS" ] && kill $PIDS 2>/dev/null && echo "✓ Killed process on port 8085 (pubsub)"

echo ""
echo "✓ All services stopped"
