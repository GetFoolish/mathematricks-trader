#!/bin/bash
# Gmail Signal Collector - Quick Setup Script

set -e

echo "========================================"
echo "Gmail Signal Collector Setup"
echo "========================================"
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed"
    echo "Please install Python 3 first"
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"
echo ""

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is not installed"
    echo "Please install pip3 first"
    exit 1
fi

echo "✓ pip3 found"
echo ""

# Install dependencies
echo "Installing Python dependencies..."
pip3 install --user google-auth google-auth-oauthlib google-api-python-client python-dotenv requests

echo ""
echo "✓ Dependencies installed"
echo ""

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from example..."
    cp .env.gmail.example .env
    echo "✓ Created .env file"
    echo ""
    echo "⚠️  Please edit .env and add your credentials:"
    echo "   nano .env"
    echo ""
else
    echo "✓ .env file already exists"
    echo ""
fi

# Make script executable
chmod +x gmail_signal_collector.py

echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Edit .env file with your credentials:"
echo "   nano .env"
echo ""
echo "2. Authenticate with Gmail:"
echo "   python3 gmail_signal_collector.py --auth"
echo ""
echo "3. Test API connection:"
echo "   python3 gmail_signal_collector.py --test"
echo ""
echo "4. Test signal collection (dry run):"
echo "   python3 gmail_signal_collector.py --dry-run"
echo ""
echo "5. Setup cron job (runs every 5 minutes):"
echo "   crontab -e"
echo "   Add: */5 * * * * cd $(pwd) && python3 gmail_signal_collector.py >> /var/log/gmail_signal.log 2>&1"
echo ""
echo "========================================"
