#!/bin/bash
# Stop all MVP services gracefully

PROJECT_ROOT="/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader"
LOG_DIR="$PROJECT_ROOT/logs"

echo "Stopping MVP services..."

# Stop services in reverse order
if [ -f "$LOG_DIR/signal_collector.pid" ]; then
    kill $(cat "$LOG_DIR/signal_collector.pid") 2>/dev/null && echo "✓ signal_collector stopped"
    rm "$LOG_DIR/signal_collector.pid"
fi

if [ -f "$LOG_DIR/execution_service.pid" ]; then
    kill $(cat "$LOG_DIR/execution_service.pid") 2>/dev/null && echo "✓ ExecutionService stopped"
    rm "$LOG_DIR/execution_service.pid"
fi

if [ -f "$LOG_DIR/cerebro_service.pid" ]; then
    kill $(cat "$LOG_DIR/cerebro_service.pid") 2>/dev/null && echo "✓ CerebroService stopped"
    rm "$LOG_DIR/cerebro_service.pid"
fi

if [ -f "$LOG_DIR/account_data_service.pid" ]; then
    kill $(cat "$LOG_DIR/account_data_service.pid") 2>/dev/null && echo "✓ AccountDataService stopped"
    rm "$LOG_DIR/account_data_service.pid"
fi

if [ -f "$LOG_DIR/pubsub.pid" ]; then
    kill $(cat "$LOG_DIR/pubsub.pid") 2>/dev/null && echo "✓ Pub/Sub emulator stopped"
    rm "$LOG_DIR/pubsub.pid"
fi

echo ""
echo "✓ All services stopped"
