#!/bin/bash
# Run MVP Demo - Mathematricks Trading System
# Starts all microservices and signal_collector

set -e

PROJECT_ROOT="/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader"
VENV_PYTHON="$PROJECT_ROOT/venv/bin/python"
LOG_DIR="$PROJECT_ROOT/logs"

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
    gcloud beta emulators pubsub start --host-port=$PUBSUB_EMULATOR_HOST > "$LOG_DIR/pubsub_emulator.log" 2>&1 &
    PUBSUB_PID=$!
    echo $PUBSUB_PID > "$LOG_DIR/pubsub.pid"
    sleep 3
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
topics = ['standardized-signals', 'trading-orders', 'execution-confirmations', 'account-updates']
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
    ('standardized-signals-sub', 'standardized-signals', 60),
    ('trading-orders-sub', 'trading-orders', 60),
    ('execution-confirmations-sub', 'execution-confirmations', 30),
    ('account-updates-sub', 'account-updates', 30)
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
echo $ACCOUNT_PID > "$LOG_DIR/account_data_service.pid"
echo "✓ AccountDataService started (PID: $ACCOUNT_PID)"
cd "$PROJECT_ROOT"

sleep 2

# Start CerebroService
echo ""
echo -e "${YELLOW}Step 4: Starting CerebroService...${NC}"
cd "$PROJECT_ROOT/services/cerebro_service"
PUBSUB_EMULATOR_HOST=$PUBSUB_EMULATOR_HOST ACCOUNT_DATA_SERVICE_URL="http://localhost:8002" $VENV_PYTHON main.py > "$LOG_DIR/cerebro_service.log" 2>&1 &
CEREBRO_PID=$!
echo $CEREBRO_PID > "$LOG_DIR/cerebro_service.pid"
echo "✓ CerebroService started (PID: $CEREBRO_PID)"
cd "$PROJECT_ROOT"

sleep 2

# Start ExecutionService
echo ""
echo -e "${YELLOW}Step 5: Starting ExecutionService...${NC}"
cd "$PROJECT_ROOT/services/execution_service"
PUBSUB_EMULATOR_HOST=$PUBSUB_EMULATOR_HOST $VENV_PYTHON main.py > "$LOG_DIR/execution_service.log" 2>&1 &
EXECUTION_PID=$!
echo $EXECUTION_PID > "$LOG_DIR/execution_service.pid"
echo "✓ ExecutionService started (PID: $EXECUTION_PID)"
echo "  Note: IBKR connection will fail if TWS/Gateway not running (this is OK for demo)"
cd "$PROJECT_ROOT"

sleep 2

# Start signal_collector
echo ""
echo -e "${YELLOW}Step 6: Starting signal_collector (staging mode)...${NC}"
PUBSUB_EMULATOR_HOST=$PUBSUB_EMULATOR_HOST $VENV_PYTHON signal_collector.py --staging > "$LOG_DIR/signal_collector.log" 2>&1 &
COLLECTOR_PID=$!
echo $COLLECTOR_PID > "$LOG_DIR/signal_collector.pid"
echo "✓ signal_collector started (PID: $COLLECTOR_PID)"

sleep 2

# Start Admin Frontend
echo ""
echo -e "${YELLOW}Step 7: Starting Admin Frontend (port 5173)...${NC}"
cd "$PROJECT_ROOT/frontend-admin"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$LOG_DIR/frontend.pid"
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
echo "  • CerebroService: http://localhost:8001"
echo "  • ExecutionService: Background (consumes from Pub/Sub)"
echo "  • signal_collector: Monitoring staging.mathematricks.fund"
echo "  • Admin Frontend: http://localhost:5173"
echo ""
echo "Admin Dashboard:"
echo "  Open browser: http://localhost:5173"
echo "  Login: username=admin, password=admin"
echo ""
echo "Logs:"
echo "  tail -f logs/signal_collector.log     # Signal collection"
echo "  tail -f logs/cerebro_service.log      # Position sizing decisions"
echo "  tail -f logs/execution_service.log    # Order execution"
echo "  tail -f logs/frontend.log             # Frontend dev server"
echo ""
echo "To send a test signal:"
echo "  python signal_sender.py --ticker SPY --action BUY --price 450.25"
echo ""
echo "To stop all services:"
echo "  ./stop_mvp_demo.sh"
echo ""
