#!/bin/bash
# Run MVP Demo - Mathematricks Trading System
# Starts all microservices and signal_collector

set -e

PROJECT_ROOT="/Users/vandanchopra/VandanStuff/CODE_STUFF/mathematricks-trader"
VENV_PYTHON="$PROJECT_ROOT/venv/bin/python"
LOG_DIR="$PROJECT_ROOT/logs"
PID_DIR="$LOG_DIR/pids"

# Create PID directory if it doesn't exist
mkdir -p "$PID_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "MATHEMATRICKS MVP DEMO"
echo "=========================================="
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "✗ Python venv not found"
    exit 1
fi
echo "✓ Python venv found"

if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "✗ .env file not found"
    exit 1
fi
echo "✓ .env file found"

# Load environment variables
source "$PROJECT_ROOT/.env"

# Start Pub/Sub emulator
echo ""
echo -e "${YELLOW}Step 1: Starting Pub/Sub emulator...${NC}"
export PUBSUB_EMULATOR_HOST="localhost:8085"

# Check if emulator is already running
if curl -s $PUBSUB_EMULATOR_HOST > /dev/null 2>&1; then
    echo "✓ Pub/Sub emulator already running"
else
    echo "Starting emulator in background..."
    # Use full Java path to ensure emulator starts correctly
    export PATH="/opt/homebrew/opt/openjdk@11/bin:$PATH"
    /opt/homebrew/opt/openjdk@11/bin/java -jar "$PROJECT_ROOT/google-cloud-sdk/platform/pubsub-emulator/lib/cloud-pubsub-emulator-0.8.6.jar" --host=localhost --port=8085 > "$LOG_DIR/pubsub_emulator.log" 2>&1 &
    PUBSUB_PID=$!
    echo $PUBSUB_PID >> "$PID_DIR/pubsub.pid"
    sleep 5
    echo "✓ Pub/Sub emulator started (PID: $PUBSUB_PID)"
fi

# Setup Pub/Sub topics
echo ""
echo -e "${YELLOW}Step 2: Creating Pub/Sub topics and subscriptions...${NC}"
PUBSUB_EMULATOR_HOST=$PUBSUB_EMULATOR_HOST $VENV_PYTHON << 'EOF'
from google.cloud import pubsub_v1
import time

project_id = 'mathematricks-trader'
publisher = pubsub_v1.PublisherClient()
subscriber = pubsub_v1.SubscriberClient()

# Create topics
topics = ['standardized-signals', 'trading-orders', 'execution-confirmations', 'account-updates', 'order-commands']
for topic_name in topics:
    topic_path = publisher.topic_path(project_id, topic_name)
    try:
        publisher.create_topic(request={"name": topic_path})
        print(f"✓ Created topic: {topic_name}")
    except Exception as e:
        if 'AlreadyExists' in str(e):
            print(f"  Topic {topic_name} already exists")
        else:
            print(f"✗ Error creating {topic_name}: {e}")

time.sleep(1)

# Create subscriptions
subscriptions = [
    ('standardized-signals-sub', 'standardized-signals', 600),
    ('trading-orders-sub', 'trading-orders', 600),
    ('execution-confirmations-sub', 'execution-confirmations', 600),
    ('account-updates-sub', 'account-updates', 600),
    ('order-commands-sub', 'order-commands', 600)
]

for sub_name, topic_name, ack_deadline in subscriptions:
    topic_path = publisher.topic_path(project_id, topic_name)
    sub_path = subscriber.subscription_path(project_id, sub_name)
    try:
        subscriber.create_subscription(
            request={
                "name": sub_path,
                "topic": topic_path,
                "ack_deadline_seconds": ack_deadline
            }
        )
        print(f"✓ Created subscription: {sub_name}")
    except Exception as e:
        if 'AlreadyExists' in str(e):
            print(f"  Subscription {sub_name} already exists")
        else:
            print(f"✗ Error creating {sub_name}: {e}")

print("✓ All topics and subscriptions ready!")
EOF

# Start AccountDataService
echo ""
echo -e "${YELLOW}Step 3: Starting AccountDataService (port 8002)...${NC}"
cd "$PROJECT_ROOT/services/account_data_service"
PUBSUB_EMULATOR_HOST=$PUBSUB_EMULATOR_HOST $VENV_PYTHON main.py > "$LOG_DIR/account_data_service.log" 2>&1 &
ACCOUNT_PID=$!
echo $ACCOUNT_PID >> "$PID_DIR/account_data_service.pid"
echo "✓ AccountDataService started (PID: $ACCOUNT_PID)"
cd "$PROJECT_ROOT"

sleep 2

# Start PortfolioBuilderService
echo ""
echo -e "${YELLOW}Step 4: Starting PortfolioBuilderService (port 8003)...${NC}"
cd "$PROJECT_ROOT/services/portfolio_builder"
$VENV_PYTHON main.py > "$LOG_DIR/portfolio_builder.log" 2>&1 &
PORTFOLIO_PID=$!
echo $PORTFOLIO_PID >> "$PID_DIR/portfolio_builder.pid"
echo "✓ PortfolioBuilderService started (PID: $PORTFOLIO_PID)"
cd "$PROJECT_ROOT"

sleep 2

# Start DashboardCreatorService
echo ""
echo -e "${YELLOW}Step 5: Starting DashboardCreatorService (port 8004)...${NC}"
cd "$PROJECT_ROOT/services/dashboard_creator"
$VENV_PYTHON main.py > "$LOG_DIR/dashboard_creator.log" 2>&1 &
DASHBOARD_PID=$!
echo $DASHBOARD_PID >> "$PID_DIR/dashboard_creator.pid"
echo "✓ DashboardCreatorService started (PID: $DASHBOARD_PID)"
cd "$PROJECT_ROOT"

sleep 2

# Start CerebroService
echo ""
echo -e "${YELLOW}Step 6: Starting CerebroService...${NC}"
cd "$PROJECT_ROOT/services/cerebro_service"
PUBSUB_EMULATOR_HOST=$PUBSUB_EMULATOR_HOST ACCOUNT_DATA_SERVICE_URL="http://localhost:8002" $VENV_PYTHON main.py > "$LOG_DIR/cerebro_service.log" 2>&1 &
CEREBRO_PID=$!
echo $CEREBRO_PID >> "$PID_DIR/cerebro_service.pid"
echo "✓ CerebroService started (PID: $CEREBRO_PID)"
cd "$PROJECT_ROOT"

sleep 2

# Start ExecutionService
echo ""
echo -e "${YELLOW}Step 7: Starting ExecutionService...${NC}"
cd "$PROJECT_ROOT/services/execution_service"
PUBSUB_EMULATOR_HOST=$PUBSUB_EMULATOR_HOST $VENV_PYTHON main.py > "$LOG_DIR/execution_service.log" 2>&1 &
EXECUTION_PID=$!
echo $EXECUTION_PID >> "$PID_DIR/execution_service.pid"
echo "✓ ExecutionService started (PID: $EXECUTION_PID)"
echo "  Note: IBKR connection will fail if TWS/Gateway not running (this is OK for demo)"
cd "$PROJECT_ROOT"

sleep 2

# Start SignalIngestionService
echo ""
echo -e "${YELLOW}Step 8: Starting SignalIngestionService (staging mode)...${NC}"
cd "$PROJECT_ROOT/services/signal_ingestion"
PUBSUB_EMULATOR_HOST=$PUBSUB_EMULATOR_HOST $VENV_PYTHON main.py --staging > "$LOG_DIR/signal_ingestion.log" 2>&1 &
SIGNAL_INGESTION_PID=$!
echo $SIGNAL_INGESTION_PID >> "$PID_DIR/signal_ingestion.pid"
echo "✓ SignalIngestionService started (PID: $SIGNAL_INGESTION_PID)"
cd "$PROJECT_ROOT"

sleep 2

# Start Admin Frontend
echo ""
echo -e "${YELLOW}Step 9: Starting Admin Frontend (port 5173)...${NC}"
cd "$PROJECT_ROOT/frontend-admin"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID >> "$PID_DIR/frontend.pid"
echo "✓ Admin Frontend started (PID: $FRONTEND_PID)"
cd "$PROJECT_ROOT"

echo ""
echo "=========================================="
echo -e "${GREEN}✓ ALL SERVICES RUNNING!${NC}"
echo "=========================================="
echo ""
echo "Services:"
echo "  • Pub/Sub Emulator: localhost:8085"
echo "  • AccountDataService: http://localhost:8002"
echo "  • PortfolioBuilderService: http://localhost:8003"
echo "  • DashboardCreatorService: http://localhost:8004"
echo "  • CerebroService: Background (consumes from Pub/Sub)"
echo "  • ExecutionService: Background (consumes from Pub/Sub)"
echo "  • SignalIngestionService: Monitoring staging.mathematricks.fund"
echo "  • Admin Frontend: http://localhost:5173"
echo ""
echo "Admin Dashboard:"
echo "  Open browser: http://localhost:5173"
echo "  Login: username=admin, password=admin"
echo ""
echo "Logs:"
echo "  tail -f logs/signal_ingestion.log     # Signal collection"
echo "  tail -f logs/portfolio_builder.log    # Strategy management & portfolio optimization"
echo "  tail -f logs/dashboard_creator.log    # Dashboard generation"
echo "  tail -f logs/cerebro_service.log      # Position sizing decisions"
echo "  tail -f logs/execution_service.log    # Order execution"
echo "  tail -f logs/frontend.log             # Frontend dev server"
echo ""
echo "Broker Connections:"
# Wait for services to write initial logs
sleep 2

# Check IBKR connection status from execution_service log
if grep -q "✅ IBKR broker connected successfully" "$LOG_DIR/execution_service.log" 2>/dev/null; then
    echo "  ✅ IBKR (ExecutionService): Connected"
elif grep -q "⚠️  Failed to connect to IBKR" "$LOG_DIR/execution_service.log" 2>/dev/null; then
    echo "  ❌ IBKR (ExecutionService): Not Connected"
    echo "     → Check TWS API Settings: Enable ActiveX and Socket Clients"
    echo "     → Verify TWS listening on 127.0.0.1:7497"
    echo "     → Ensure client ID 1 is available"
elif grep -q "TimeoutError" "$LOG_DIR/execution_service.log" 2>/dev/null; then
    echo "  ❌ IBKR (ExecutionService): Connection Timeout"
    echo "     → TWS/Gateway may not be running on 127.0.0.1:7497"
    echo "     → Check TWS API Settings: Enable ActiveX and Socket Clients"
else
    echo "  ⏳ IBKR (ExecutionService): Connecting..."
fi

# Check AccountDataService broker status
if grep -q "⚠️  Broker polling disabled" "$LOG_DIR/account_data_service.log" 2>/dev/null; then
    echo "  ⚠️  IBKR (AccountDataService): Polling Disabled (using Pub/Sub only)"
else
    echo "  ⏳ IBKR (AccountDataService): Checking..."
fi

# Check Zerodha (Kite) availability
if grep -q "kiteconnect not installed" "$LOG_DIR/execution_service.log" 2>/dev/null; then
    echo "  ⚠️  Zerodha (Kite): Python package not installed"
    echo "     → Run: pip install kiteconnect"
else
    echo "  ℹ️  Zerodha (Kite): Available (not configured in ExecutionService)"
fi

echo ""
echo "To send a test signal:"
echo "  python signal_sender.py --ticker SPY --action BUY --price 450.25"
echo ""
echo "To stop all services:"
echo "  ./stop_mvp_demo.sh"
echo ""
