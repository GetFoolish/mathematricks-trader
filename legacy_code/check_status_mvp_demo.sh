#!/bin/bash
# Check status of all Mathematricks Trader services

echo "================================================================================"
echo "Mathematricks Trader - Service Status Check"
echo "================================================================================"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if a service is running
check_service() {
    local service_name=$1
    local search_pattern=$2
    local port=$3

    echo "📋 $service_name"
    echo "   Search: $search_pattern"

    # Check process
    pid=$(ps aux | grep "$search_pattern" | grep -v grep | awk '{print $2}' | head -1)
    if [ -n "$pid" ]; then
        echo -e "   Process: ${GREEN}✅ Running${NC} (PID: $pid)"

        # Get uptime
        ps -p $pid -o etime= | xargs -I {} echo "   Uptime: {}"

        # Get memory usage
        ps -p $pid -o rss= | awk '{printf "   Memory: %.1f MB\n", $1/1024}'
    else
        echo -e "   Process: ${RED}❌ Not running${NC}"
    fi

    # Check port if specified
    if [ -n "$port" ]; then
        if lsof -i :$port | grep LISTEN > /dev/null 2>&1; then
            echo -e "   Port $port: ${GREEN}✅ Listening${NC}"
        else
            echo -e "   Port $port: ${RED}❌ Not listening${NC}"
        fi
    fi

    echo ""
}

# Check each service
echo "1️⃣  CORE SERVICES"
echo "--------------------------------------------------------------------------------"
check_service "Signal Ingestion" "python.*signal_ingestion/main.py" ""
check_service "Cerebro Service" "python.*cerebro_service/main.py" ""
check_service "Account Data Service" "python.*account_data_service/main.py" "8082"
check_service "Execution Service" "python.*execution_service/main.py" ""

echo ""
echo "2️⃣  SUPPORT SERVICES"
echo "--------------------------------------------------------------------------------"
check_service "Portfolio Builder" "python.*portfolio_builder/main.py" "8003"
check_service "Dashboard Creator" "python.*dashboard_creator/main.py" "8002"

echo ""
echo "3️⃣  INFRASTRUCTURE"
echo "--------------------------------------------------------------------------------"

# MongoDB
echo "📋 MongoDB (Local Replica Set)"
if ps aux | grep mongod | grep -v grep > /dev/null; then
    pid=$(ps aux | grep mongod | grep -v grep | awk '{print $2}')
    echo -e "   Process: ${GREEN}✅ Running${NC} (PID: $pid)"

    # Check replica set status
    if mongosh --quiet --eval "rs.status().ok" 2>/dev/null | grep -q "1"; then
        replica_set=$(mongosh --quiet --eval "rs.status().set" 2>/dev/null)
        primary=$(mongosh --quiet --eval "rs.status().members.find(m => m.stateStr === 'PRIMARY')?.name" 2>/dev/null)
        echo -e "   Replica Set: ${GREEN}✅ $replica_set${NC}"
        echo "   Primary: $primary"
    else
        echo -e "   Replica Set: ${YELLOW}⚠️  Not initialized${NC}"
    fi
else
    echo -e "   Process: ${RED}❌ Not running${NC}"
fi
echo ""

# TWS/Gateway
echo "📋 IBKR TWS/Gateway"
if lsof -i :7497 | grep LISTEN > /dev/null 2>&1; then
    echo -e "   Port 7497: ${GREEN}✅ Listening${NC}"
else
    echo -e "   Port 7497: ${RED}❌ Not listening${NC}"
    echo "   (Start TWS or IB Gateway on port 7497)"
fi
echo ""

# Pub/Sub Emulator (optional)
echo "📋 Pub/Sub Emulator (Optional)"
if lsof -i :8085 | grep LISTEN > /dev/null 2>&1; then
    echo -e "   Port 8085: ${GREEN}✅ Running${NC}"
else
    echo -e "   Port 8085: ${YELLOW}⚠️  Not running${NC} (optional for local dev)"
fi
echo ""

echo ""
echo "4️⃣  SERVICE LOGS (Last 5 lines each)"
echo "--------------------------------------------------------------------------------"

for log in signal_ingestion cerebro_service account_data_service execution_service portfolio_builder dashboard_creator; do
    if [ -f "logs/${log}.log" ]; then
        echo ""
        echo "📄 logs/${log}.log (last 5 lines):"
        tail -5 "logs/${log}.log" | sed 's/^/   /'
    fi
done

echo ""
echo "================================================================================"
echo "Summary"
echo "================================================================================"

# Count running services
running=0
total=6

for pattern in "signal_ingestion/main.py" "cerebro_service/main.py" "account_data_service/main.py" "execution_service/main.py" "portfolio_builder/main.py" "dashboard_creator/main.py"; do
    if ps aux | grep "python.*$pattern" | grep -v grep > /dev/null; then
        ((running++))
    fi
done

echo -e "Services: ${running}/${total} running"

if [ $running -eq $total ]; then
    echo -e "Status: ${GREEN}✅ All services running${NC}"
elif [ $running -gt 0 ]; then
    echo -e "Status: ${YELLOW}⚠️  Some services down${NC}"
else
    echo -e "Status: ${RED}❌ No services running${NC}"
fi

echo ""
echo "Tip: To restart a specific service, check logs/ folder for error details"
echo "================================================================================"
