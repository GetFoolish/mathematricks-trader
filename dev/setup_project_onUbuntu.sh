#!/bin/bash

# Mathematricks Trader - Development Environment Setup Script (Ubuntu)
# This script sets up everything needed to run the project locally on Ubuntu

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
echo "  Mathematricks Trader Setup Script (Ubuntu)"
echo "=========================================="
echo ""

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo -e "${RED}❌ This script is designed for Ubuntu Linux. Detected: $OSTYPE${NC}"
    exit 1
fi

# Check for sudo privileges
if [ "$EUID" -ne 0 ]; then 
    echo -e "${YELLOW}⚠️  This script requires sudo privileges to install packages.${NC}"
    echo "Please run with sudo or be prepared to enter your password."
    sudo -v
fi

echo -e "${BLUE}[1/7] Checking system prerequisites...${NC}"
echo ""

# Update package list
echo "Updating package list..."
sudo apt-get update

# Install basic dependencies
echo "Installing basic dependencies..."
sudo apt-get install -y curl gnupg software-properties-common build-essential

# Check for Python 3.11 specifically
PYTHON_CMD="python3.11"

if ! command -v $PYTHON_CMD &> /dev/null; then
    echo -e "${YELLOW}⚠️  Python ${PYTHON_VERSION} not found. Installing...${NC}"
    
    # Add deadsnakes PPA for newer Python versions if not present
    if ! grep -q "deadsnakes/ppa" /etc/apt/sources.list /etc/apt/sources.list.d/*; then
        echo "Adding deadsnakes PPA..."
        sudo add-apt-repository ppa:deadsnakes/ppa -y
        sudo apt-get update
    fi

    sudo apt-get install -y python3.11 python3.11-venv python3.11-dev

    # Verify installation
    if ! command -v $PYTHON_CMD &> /dev/null; then
        echo -e "${RED}❌ Failed to install Python ${PYTHON_VERSION}${NC}"
        exit 1
    fi
else
    PYTHON_VER=$($PYTHON_CMD --version | awk '{print $2}')
    echo -e "${GREEN}✅ Python ${PYTHON_VER} installed${NC}"
fi

# Check for MongoDB
echo ""
echo -e "${BLUE}[2/7] Checking MongoDB installation...${NC}"
echo ""

if ! command -v mongod &> /dev/null; then
    echo -e "${YELLOW}⚠️  MongoDB not found. Installing MongoDB Community Edition...${NC}"

    # Import the public key used by the package management system
    curl -fsSL https://pgp.mongodb.com/server-7.0.asc | sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg

    # Create a list file for MongoDB
    # Using jammy (22.04) as a safe default, but trying to detect codename
    UBUNTU_CODENAME=$(lsb_release -cs)
    echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu ${UBUNTU_CODENAME}/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list

    # Reload local package database
    sudo apt-get update

    # Install the MongoDB packages
    sudo apt-get install -y mongodb-org

    echo -e "${GREEN}✅ MongoDB installed${NC}"
else
    MONGO_VER=$(mongod --version | head -n 1)
    echo -e "${GREEN}✅ MongoDB installed: ${MONGO_VER}${NC}"
fi

# Configure MongoDB Replica Set
echo ""
echo -e "${BLUE}[2.5/7] Configuring MongoDB Replica Set...${NC}"
echo ""

if grep -q "#replication:" /etc/mongod.conf; then
    echo "Enabling replication in /etc/mongod.conf..."
    # Backup config
    sudo cp /etc/mongod.conf /etc/mongod.conf.bak
    
    # Uncomment replication and add replSetName
    sudo sed -i 's/#replication:/replication:\n  replSetName: rs0/' /etc/mongod.conf
    
    echo -e "${GREEN}✅ Replication enabled in config${NC}"
    
    # Restart MongoDB to apply changes
    echo "Restarting MongoDB..."
    sudo systemctl restart mongod
    sleep 5
elif grep -q "replSetName: rs0" /etc/mongod.conf; then
    echo -e "${GREEN}✅ Replication already configured${NC}"
else
    echo -e "${YELLOW}⚠️  Replication configuration not detected or custom. Skipping config update.${NC}"
fi

# Check if MongoDB is running
echo ""
echo -e "${BLUE}[3/7] Checking MongoDB service...${NC}"
echo ""

if systemctl is-active --quiet mongod; then
    echo -e "${GREEN}✅ MongoDB is running${NC}"
else
    echo -e "${YELLOW}⚠️  MongoDB is not running. Starting MongoDB...${NC}"
    sudo systemctl start mongod
    sudo systemctl enable mongod

    # Wait for MongoDB to start
    echo "Waiting for MongoDB to start..."
    sleep 3

    if systemctl is-active --quiet mongod; then
        echo -e "${GREEN}✅ MongoDB started successfully${NC}"
    else
        echo -e "${RED}❌ Failed to start MongoDB. Please check logs:${NC}"
        echo "   sudo journalctl -u mongod"
        exit 1
    fi
fi

# Initialize Replica Set
echo "Initializing Replica Set..."
# Check if already initialized (rs.status() returns ok: 1 if member of set)
if mongosh --quiet --eval "try { rs.status().ok } catch(e) { 0 }" | grep -q "1"; then
     echo -e "${GREEN}✅ Replica Set already initialized${NC}"
else
     # Initialize
     echo "Running rs.initiate()..."
     mongosh --quiet --eval "rs.initiate()"
     sleep 2
     if mongosh --quiet --eval "try { rs.status().ok } catch(e) { 0 }" | grep -q "1"; then
         echo -e "${GREEN}✅ Replica Set initialized${NC}"
     else
         echo -e "${RED}❌ Failed to initialize Replica Set. You may need to do it manually.${NC}"
         echo "   Run: mongosh --eval 'rs.initiate()'"
     fi
fi

# Check MongoDB connection
if mongosh --quiet --eval "db.version()" &> /dev/null; then
    echo -e "${GREEN}✅ MongoDB connection successful${NC}"
else
    echo -e "${RED}❌ Cannot connect to MongoDB. Please check MongoDB status.${NC}"
    exit 1
fi

# Check for Google Cloud SDK (Pub/Sub Emulator)
echo ""
echo -e "${BLUE}[4/7] Checking Google Cloud SDK...${NC}"
echo ""

if [ ! -d "google-cloud-sdk" ]; then
    echo -e "${YELLOW}⚠️  Google Cloud SDK not found. Installing...${NC}"
    
    # Download SDK
    echo "Downloading Google Cloud SDK..."
    curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-linux-x86_64.tar.gz
    
    # Extract
    echo "Extracting..."
    tar -xf google-cloud-cli-linux-x86_64.tar.gz
    rm google-cloud-cli-linux-x86_64.tar.gz
    
    # Install Pub/Sub emulator component
    echo "Installing Pub/Sub emulator component..."
    # We use --quiet to avoid prompts and --path-update=false to avoid modifying shell profile
    ./google-cloud-sdk/install.sh --quiet --path-update=false --usage-reporting=false
    ./google-cloud-sdk/bin/gcloud components install pubsub-emulator --quiet
    
    echo -e "${GREEN}✅ Google Cloud SDK installed${NC}"
else
    echo -e "${GREEN}✅ Google Cloud SDK found${NC}"
    
    # Check if pubsub-emulator is installed
    if [ ! -f "google-cloud-sdk/platform/pubsub-emulator/bin/cloud-pubsub-emulator" ]; then
        echo "Installing Pub/Sub emulator component..."
        ./google-cloud-sdk/bin/gcloud components install pubsub-emulator --quiet
        echo -e "${GREEN}✅ Pub/Sub emulator installed${NC}"
    fi
fi

# Create Python virtual environment
echo ""
echo -e "${BLUE}[5/7] Setting up Python virtual environment...${NC}"
echo ""

if [ -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment already exists at ./${VENV_DIR}${NC}"
    read -p "Do you want to recreate it? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$VENV_DIR"
        $PYTHON_CMD -m venv "$VENV_DIR"
        echo -e "${GREEN}✅ Virtual environment recreated${NC}"
    else
        echo -e "${BLUE}ℹ️  Using existing virtual environment${NC}"
    fi
else
    $PYTHON_CMD -m venv "$VENV_DIR"
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
echo -e "${BLUE}[6/7] Installing Python dependencies...${NC}"
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
echo -e "${BLUE}[7/7] Importing MongoDB collections...${NC}"
echo ""

if [ -d "$COLLECTIONS_DIR" ]; then
    # Find the latest exported files
    LATEST_FILES=$(ls -t "$COLLECTIONS_DIR"/*.json 2>/dev/null | head -4)

    if [ -z "$LATEST_FILES" ]; then
        echo -e "${YELLOW}⚠️  No exported collection files found in ${COLLECTIONS_DIR}${NC}"
        echo "Skipping MongoDB import. You'll need to set up collections manually."
    else
        echo "Found exported collections. Checking which need to be imported..."

        for file in $LATEST_FILES; do
            collection=$(basename "$file" | sed 's/_[0-9]*\.json$//')

            # Check if collection exists and has documents
            doc_count=$(mongosh --quiet "$MONGO_DB_NAME" --eval "db.${collection}.countDocuments({})" 2>/dev/null || echo "0")

            if [ "$doc_count" -gt 0 ]; then
                echo -e "  ${BLUE}ℹ️  ${collection}: Already exists with ${doc_count} documents (skipping)${NC}"
            else
                echo "  Importing: $collection"
                mongoimport \
                    --db="$MONGO_DB_NAME" \
                    --collection="$collection" \
                    --file="$file" \
                    --jsonArray \
                    --quiet

                if [ $? -eq 0 ]; then
                    new_count=$(mongosh --quiet "$MONGO_DB_NAME" --eval "db.${collection}.countDocuments({})")
                    echo -e "    ${GREEN}✅ Imported ${new_count} documents${NC}"
                else
                    echo -e "    ${RED}❌ Failed to import ${collection}${NC}"
                fi
            fi
        done
    fi
else
    echo -e "${YELLOW}⚠️  Collections directory not found: ${COLLECTIONS_DIR}${NC}"
    echo "You'll need to set up MongoDB collections manually."
fi

# Create .env file if it doesn't exist
echo ""
echo -e "${BLUE}[8/8] Checking configuration files...${NC}"
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
echo -e "   ${YELLOW}python mvp_demo_start.py${NC} --use-mock-broker"
echo -e "   ${YELLOW}python mvp_demo_start.py${NC} # if you want to test it with live broker"
echo ""
echo -e "${BLUE}📚 Additional Information:${NC}"
echo ""
echo "  • MongoDB Database: $MONGO_DB_NAME"
echo "  • MongoDB running on: localhost:27017"
echo "  • Python Virtual Environment: ./${VENV_DIR}"
echo ""
echo "  To stop MongoDB:"
echo "    sudo systemctl stop mongod"
echo ""
echo "  To view logs:"
echo "    tail -f logs/*.log"
echo ""
echo "  For help, see: README.md"
echo ""
