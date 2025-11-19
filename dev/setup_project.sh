#!/bin/bash

# Mathematricks Trader - Development Environment Setup Script
# This script sets up everything needed to run the project locally

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PYTHON_VERSION="3.11"
VENV_DIR="venv"
MONGO_DB_NAME="mathematricks_trading"
COLLECTIONS_DIR="./dev/downloads/exported_collections"

echo ""
echo "=========================================="
echo "  Mathematricks Trader Setup Script"
echo "=========================================="
echo ""

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo -e "${RED}❌ This script is designed for macOS. Please adapt it for your OS.${NC}"
    exit 1
fi

echo -e "${BLUE}[1/7] Checking system prerequisites...${NC}"
echo ""

# Check for Homebrew
if ! command -v brew &> /dev/null; then
    echo -e "${YELLOW}⚠️  Homebrew not found. Installing Homebrew...${NC}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo -e "${GREEN}✅ Homebrew installed${NC}"
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}⚠️  Python 3 not found. Installing Python ${PYTHON_VERSION}...${NC}"
    brew install python@${PYTHON_VERSION}
else
    PYTHON_VER=$(python3 --version | awk '{print $2}')
    echo -e "${GREEN}✅ Python ${PYTHON_VER} installed${NC}"
fi

# Check for MongoDB
echo ""
echo -e "${BLUE}[2/7] Checking MongoDB installation...${NC}"
echo ""

if ! command -v mongod &> /dev/null; then
    echo -e "${YELLOW}⚠️  MongoDB not found. Installing MongoDB Community Edition...${NC}"

    # Add MongoDB tap
    brew tap mongodb/brew

    # Install MongoDB
    brew install mongodb-community

    echo -e "${GREEN}✅ MongoDB installed${NC}"
else
    MONGO_VER=$(mongod --version | head -n 1)
    echo -e "${GREEN}✅ MongoDB installed: ${MONGO_VER}${NC}"
fi

# Check if MongoDB is running
echo ""
echo -e "${BLUE}[3/7] Checking MongoDB service...${NC}"
echo ""

if pgrep -x "mongod" > /dev/null; then
    echo -e "${GREEN}✅ MongoDB is running${NC}"
else
    echo -e "${YELLOW}⚠️  MongoDB is not running. Starting MongoDB...${NC}"
    brew services start mongodb-community

    # Wait for MongoDB to start
    echo "Waiting for MongoDB to start..."
    sleep 3

    if pgrep -x "mongod" > /dev/null; then
        echo -e "${GREEN}✅ MongoDB started successfully${NC}"
    else
        echo -e "${RED}❌ Failed to start MongoDB. Please start it manually:${NC}"
        echo "   brew services start mongodb-community"
        exit 1
    fi
fi

# Check MongoDB connection
if mongosh --quiet --eval "db.version()" &> /dev/null; then
    echo -e "${GREEN}✅ MongoDB connection successful${NC}"
else
    echo -e "${RED}❌ Cannot connect to MongoDB. Please check MongoDB status.${NC}"
    exit 1
fi

# Create Python virtual environment
echo ""
echo -e "${BLUE}[4/7] Setting up Python virtual environment...${NC}"
echo ""

if [ -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment already exists at ./${VENV_DIR}${NC}"
    read -p "Do you want to recreate it? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$VENV_DIR"
        python3 -m venv "$VENV_DIR"
        echo -e "${GREEN}✅ Virtual environment recreated${NC}"
    else
        echo -e "${BLUE}ℹ️  Using existing virtual environment${NC}"
    fi
else
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✅ Virtual environment created at ./${VENV_DIR}${NC}"
fi

# Activate virtual environment
source "${VENV_DIR}/bin/activate"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1

# Install requirements
echo ""
echo -e "${BLUE}[5/7] Installing Python dependencies...${NC}"
echo ""

if [ -f "requirements.txt" ]; then
    echo "Installing from requirements.txt..."
    pip install -r requirements.txt
    echo -e "${GREEN}✅ Dependencies installed${NC}"
else
    echo -e "${RED}❌ requirements.txt not found${NC}"
    echo "Please ensure requirements.txt exists in the project root"
    exit 1
fi

# Import MongoDB collections
echo ""
echo -e "${BLUE}[6/7] Importing MongoDB collections...${NC}"
echo ""

if [ -d "$COLLECTIONS_DIR" ]; then
    # Find the latest exported files
    LATEST_FILES=$(ls -t "$COLLECTIONS_DIR"/*.json 2>/dev/null | head -4)

    if [ -z "$LATEST_FILES" ]; then
        echo -e "${YELLOW}⚠️  No exported collection files found in ${COLLECTIONS_DIR}${NC}"
        echo "Skipping MongoDB import. You'll need to set up collections manually."
    else
        echo "Found exported collections. Importing..."

        for file in $LATEST_FILES; do
            collection=$(basename "$file" | sed 's/_[0-9]*\.json$//')

            echo "  Importing: $collection"
            mongoimport \
                --db="$MONGO_DB_NAME" \
                --collection="$collection" \
                --file="$file" \
                --jsonArray \
                --drop \
                --quiet

            if [ $? -eq 0 ]; then
                doc_count=$(mongosh --quiet "$MONGO_DB_NAME" --eval "db.${collection}.countDocuments({})")
                echo -e "    ${GREEN}✅ Imported ${doc_count} documents${NC}"
            else
                echo -e "    ${RED}❌ Failed to import ${collection}${NC}"
            fi
        done
    fi
else
    echo -e "${YELLOW}⚠️  Collections directory not found: ${COLLECTIONS_DIR}${NC}"
    echo "You'll need to set up MongoDB collections manually."
fi

# Create .env file if it doesn't exist
echo ""
echo -e "${BLUE}[7/7] Checking configuration files...${NC}"
echo ""

if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Creating template...${NC}"

    cat > .env <<EOF
# MongoDB Configuration
MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0

# GCP Configuration (for Pub/Sub)
GCP_PROJECT_ID=mathematricks-trader
GCP_CREDENTIALS_PATH=path/to/credentials.json

# Service Configuration
DEFAULT_ACCOUNT_ID=Mock_Paper

# Environment
ENVIRONMENT=development
EOF

    echo -e "${GREEN}✅ Created .env template${NC}"
    echo -e "${YELLOW}⚠️  Please update .env with your actual credentials${NC}"
else
    echo -e "${GREEN}✅ .env file exists${NC}"
fi

# Deactivate virtual environment
deactivate

echo ""
echo "=========================================="
echo -e "${GREEN}  ✅ Setup Complete!${NC}"
echo "=========================================="
echo ""
echo -e "${BLUE}📋 Next Steps:${NC}"
echo ""
echo "1. Activate the virtual environment:"
echo -e "   ${YELLOW}source venv/bin/activate${NC}"
echo ""
echo "2. Update configuration (if needed):"
echo -e "   ${YELLOW}nano .env${NC}"
echo ""
echo "3. Start the demo:"
echo -e "   ${YELLOW}python mvp_demo_start.py${NC}"
echo ""
echo -e "${BLUE}📚 Additional Information:${NC}"
echo ""
echo "  • MongoDB Database: $MONGO_DB_NAME"
echo "  • MongoDB running on: localhost:27017"
echo "  • Python Virtual Environment: ./${VENV_DIR}"
echo ""
echo "  To stop MongoDB:"
echo "    brew services stop mongodb-community"
echo ""
echo "  To view logs:"
echo "    tail -f logs/*.log"
echo ""
echo "  For help, see: README.md"
echo ""
