#!/bin/bash

# IB Gateway Docker Setup Script
# Sets up the ib-gateway-docker container for IBKR API connectivity

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

CONTAINER_NAME="ib-gateway"
# Using gnzsnz/ib-gateway-docker - well documented and stable
IMAGE="ghcr.io/gnzsnz/ib-gateway:latest"

echo ""
echo "=========================================="
echo "  IB Gateway Docker Setup"
echo "=========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed${NC}"
    echo ""
    echo "Please install Docker Desktop from:"
    echo "  https://www.docker.com/products/docker-desktop"
    echo ""
    exit 1
fi

echo -e "${GREEN}✅ Docker is installed${NC}"

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo -e "${RED}❌ Docker daemon is not running${NC}"
    echo ""
    echo "Please start Docker Desktop and try again"
    exit 1
fi

echo -e "${GREEN}✅ Docker daemon is running${NC}"

# Check if container already exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo ""
    echo -e "${YELLOW}⚠️  Container '${CONTAINER_NAME}' already exists${NC}"

    # Check if it's running
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo -e "${GREEN}✅ Container is already running${NC}"
        echo ""
        echo "To view logs: docker logs ${CONTAINER_NAME}"
        echo "To stop:      docker stop ${CONTAINER_NAME}"
        echo "To remove:    docker rm ${CONTAINER_NAME}"
        exit 0
    else
        echo "Container exists but is not running."
        read -p "Start existing container? (y/n): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker start ${CONTAINER_NAME}
            echo -e "${GREEN}✅ Container started${NC}"
            exit 0
        else
            read -p "Remove and recreate container? (y/n): " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                docker rm ${CONTAINER_NAME}
                echo "Removed existing container"
            else
                echo "Exiting without changes"
                exit 0
            fi
        fi
    fi
fi

# Get IBKR credentials
echo ""
echo -e "${BLUE}Loading IBKR credentials...${NC}"
echo ""

# Try to load from .env file first
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env"

if [ -f "$ENV_FILE" ]; then
    # Source .env file to get variables
    set -a
    source "$ENV_FILE"
    set +a
    echo -e "${GREEN}✅ Loaded .env file${NC}"
fi

# Select trading mode first (to determine which credentials to use)
echo ""
echo "Select trading mode:"
echo "  1) Paper Trading (recommended for testing)"
echo "  2) Live Trading"
read -p "Enter choice [1]: " MODE_CHOICE

case "$MODE_CHOICE" in
    2)
        TRADING_MODE="live"
        echo -e "${YELLOW}⚠️  Live trading mode selected${NC}"
        ;;
    *)
        TRADING_MODE="paper"
        echo -e "${GREEN}Paper trading mode selected${NC}"
        ;;
esac

# Check for credentials from .env based on trading mode
if [ "$TRADING_MODE" = "paper" ]; then
    if [ -n "$IBKR_PAPER_USERNAME" ] && [ -n "$IBKR_PAPER_PASSWORD" ]; then
        echo -e "${BLUE}Using paper trading credentials from .env file${NC}"
        TWS_USERID="$IBKR_PAPER_USERNAME"
        TWS_PASSWORD="$IBKR_PAPER_PASSWORD"
    fi
else
    if [ -n "$IBKR_LIVE_USERNAME" ] && [ -n "$IBKR_LIVE_PASSWORD" ]; then
        echo -e "${BLUE}Using live trading credentials from .env file${NC}"
        TWS_USERID="$IBKR_LIVE_USERNAME"
        TWS_PASSWORD="$IBKR_LIVE_PASSWORD"
    fi
fi

# If credentials not found, prompt for them
if [ -z "$TWS_USERID" ] || [ -z "$TWS_PASSWORD" ]; then
    echo "(Credentials will be passed to the container, not stored)"
    echo ""
    read -p "IBKR Username: " TWS_USERID
    read -s -p "IBKR Password: " TWS_PASSWORD
    echo ""
fi

if [ -z "$TWS_USERID" ] || [ -z "$TWS_PASSWORD" ]; then
    echo -e "${RED}❌ Username and password are required${NC}"
    exit 1
fi

# Pull the latest image
echo ""
echo -e "${BLUE}Pulling IB Gateway Docker image...${NC}"
docker pull ${IMAGE}

# Run the container
echo ""
echo -e "${BLUE}Starting IB Gateway container...${NC}"

# Build docker run command
# gnzsnz/ib-gateway uses internal ports 4003 (live) and 4004 (paper)
# Map to standard ports: 4001 (live) and 4002 (paper) on host
DOCKER_CMD="docker run -d --name ${CONTAINER_NAME} -p 4001:4003 -p 4002:4004 -p 5900:5900"
DOCKER_CMD="${DOCKER_CMD} -e TWS_USERID=${TWS_USERID}"
DOCKER_CMD="${DOCKER_CMD} -e TWS_PASSWORD=${TWS_PASSWORD}"
DOCKER_CMD="${DOCKER_CMD} -e TRADING_MODE=${TRADING_MODE}"
# Auto-restart on 2FA timeout instead of exiting
DOCKER_CMD="${DOCKER_CMD} -e TWOFA_TIMEOUT_ACTION=restart"
# Disable read-only API to allow trading
DOCKER_CMD="${DOCKER_CMD} -e READ_ONLY_API=no"
# Accept incoming API connections
DOCKER_CMD="${DOCKER_CMD} -e IBC_AcceptIncomingConnectionAction=accept"

DOCKER_CMD="${DOCKER_CMD} --restart=always ${IMAGE}"

# Execute
eval $DOCKER_CMD

# Wait a moment for container to initialize
sleep 2

# Verify container is running
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo ""
    echo -e "${GREEN}✅ IB Gateway container started successfully${NC}"
    echo ""
    echo "=========================================="
    echo -e "${BLUE}Important Notes:${NC}"
    echo "=========================================="
    echo ""
    echo "1. Check your IBKR mobile app for 2FA approval"
    echo "   (First login requires mobile approval)"
    echo ""
    echo "2. API Ports:"
    if [ "$TRADING_MODE" = "paper" ]; then
        echo "   - Paper Trading: 4002"
    else
        echo "   - Live Trading: 4001"
    fi
    echo "   - VNC Port: 5900 (for debugging)"
    echo ""
    echo "3. Useful commands:"
    echo "   - View logs:     docker logs ${CONTAINER_NAME}"
    echo "   - Stop:          docker stop ${CONTAINER_NAME}"
    echo "   - Start:         docker start ${CONTAINER_NAME}"
    echo "   - Remove:        docker rm ${CONTAINER_NAME}"
    echo ""
    echo "4. Container will auto-restart on reboot"
    echo ""
else
    echo -e "${RED}❌ Failed to start container${NC}"
    echo ""
    echo "Check Docker logs for errors:"
    echo "  docker logs ${CONTAINER_NAME}"
    exit 1
fi
