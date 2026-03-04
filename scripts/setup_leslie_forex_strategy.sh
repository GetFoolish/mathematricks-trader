#!/bin/bash
# Setup script for Leslie's Forex Strategy
# Integrates Google Sheets forex signals with Mathematricks trading system

set -e

echo "=================================="
echo "Leslie's Forex Strategy Setup"
echo "=================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
FUND_ID="leslie-forex-fund"
STRATEGY_ID="LeslieForex_GoogleSheets"
ACCOUNT_ID="LESLIE-FOREX-ACCOUNT"
IBKR_ACCOUNT_NUMBER="DU1234567"  # Update with actual IBKR paper account
BASE_CURRENCY="CAD"
INITIAL_EQUITY=100000

echo -e "${YELLOW}Configuration:${NC}"
echo "  Fund ID: $FUND_ID"
echo "  Strategy ID: $STRATEGY_ID"
echo "  Account ID: $ACCOUNT_ID"
echo "  IBKR Account: $IBKR_ACCOUNT_NUMBER"
echo "  Base Currency: $BASE_CURRENCY"
echo "  Initial Equity: \$$INITIAL_EQUITY"
echo ""

# Prompt for confirmation
read -p "Continue with setup? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Setup cancelled."
    exit 1
fi

echo ""
echo -e "${GREEN}Step 1: Creating fund, strategy, and account in MongoDB...${NC}"

# Execute MongoDB setup
mongosh --port 27018 mathematricks_trading --quiet --eval "
// 1. Create Fund
print('\n📊 Creating fund: $FUND_ID');
db.funds.insertOne({
  fund_id: '$FUND_ID',
  name: 'Leslie Forex Strategy Fund',
  description: 'Google Sheets forex strategy fund',
  total_equity: $INITIAL_EQUITY,
  currency: '$BASE_CURRENCY',
  accounts: ['$ACCOUNT_ID'],
  status: 'ACTIVE',
  
  approved_allocation: {
    portfolio_test_id: 'leslie_forex_allocation',
    allocations: {
      '$STRATEGY_ID': 100.0
    },
    approved_at: new Date(),
    approved_by: 'setup_script',
    notes: 'Leslie Google Sheets forex strategy - 100% allocation'
  },
  
  created_at: new Date(),
  updated_at: new Date()
});

// 2. Create Strategy
print('🎯 Creating strategy: $STRATEGY_ID');
db.strategies.insertOne({
  strategy_id: '$STRATEGY_ID',
  strategy_name: 'Leslie Forex Strategy (Google Sheets)',
  description: 'Forex trading strategy managed via Google Sheets',
  asset_class: 'forex',
  status: 'ACTIVE',
  trading_mode: 'PAPER',
  
  accounts: {
    mock: ['$ACCOUNT_ID'],
    paper: ['$ACCOUNT_ID'],
    live: ['$ACCOUNT_ID']
  },
  
  developer: 'Leslie',
  signal_source: 'Google Sheets',
  instrument_type: 'FOREX',
  base_currency: '$BASE_CURRENCY',
  
  created_at: new Date(),
  updated_at: new Date()
});

// 3. Create Trading Account
print('🏦 Creating trading account: $ACCOUNT_ID');
db.trading_accounts.insertOne({
  account_id: '$ACCOUNT_ID',
  fund_id: '$FUND_ID',
  broker: 'IBKR',
  broker_account_number: '$IBKR_ACCOUNT_NUMBER',
  
  account_name: 'Leslie Forex Paper Account',
  account_number: '$IBKR_ACCOUNT_NUMBER',
  account_type: 'paper',
  mode: ['paper_live'],
  
  asset_classes: {
    forex: ['all']
  },
  
  authentication_details: {
    auth_type: 'IBKR',
    host: 'ib-gateway-ibkr-testing-account',
    port: 4004,
    client_id: 3,
    account_data_client_id: 103
  },
  
  balances: {
    account_id: '$ACCOUNT_ID',
    equity: $INITIAL_EQUITY,
    cash_balance: $INITIAL_EQUITY,
    margin_used: 0,
    margin_available: $INITIAL_EQUITY,
    buying_power: $INITIAL_EQUITY,
    currency: '$BASE_CURRENCY',
    last_updated: new Date()
  },
  
  open_positions: [],
  status: 'ACTIVE',
  
  created_at: new Date(),
  updated_at: new Date()
});

print('✅ MongoDB setup complete!');
"

echo ""
echo -e "${GREEN}Step 2: Verifying setup...${NC}"

# Verify setup
mongosh --port 27018 mathematricks_trading --quiet --eval "
print('Fund: ' + db.funds.countDocuments({fund_id: '$FUND_ID'}) + ' document(s)');
print('Strategy: ' + db.strategies.countDocuments({strategy_id: '$STRATEGY_ID'}) + ' document(s)');
print('Account: ' + db.trading_accounts.countDocuments({account_id: '$ACCOUNT_ID'}) + ' document(s)');
"

echo ""
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo ""
echo "Next Steps:"
echo "─────────────────────────────────────────"
echo ""
echo "1. Google Sheets Setup:"
echo "   • Share Leslie's sheet with you"
echo "   • Copy script from: signal-senders/GoogleSheets_Strategy_Template.js"
echo "   • Set passphrase in Google Apps Script properties"
echo "   • Configure triggers (onChange + 1-minute timer)"
echo ""
echo "2. Test Signal Flow:"
echo "   • Leslie updates position in sheet"
echo "   • Check logs: docker-compose logs -f signal-ingestion"
echo "   • Verify signal in MongoDB: db.signal_store.findOne({strategy_id: '$STRATEGY_ID'})"
echo ""
echo "3. Monitor Paper Trading:"
echo "   • Run for a few days in paper_live mode"
echo "   • Check positions: curl http://localhost:8081/api/v1/accounts/$ACCOUNT_ID"
echo "   • Review P&L in admin dashboard: http://localhost:5173"
echo ""
echo "4. Go Live (After Testing):"
echo "   • Update account_type to 'live'"
echo "   • Update mode to ['live_live']"
echo "   • Update IBKR credentials to live account"
echo ""
echo "Documentation:"
echo "  • Full guide: documentation/DEVELOPER_FOREX_STRATEGY_SETUP.md"
echo "  • Google Sheets: documentation/GOOGLE_SHEETS_QUICK_REFERENCE.md"
echo "  • Forex residuals: documentation/llm_dev_documentation_and_scripts/FOREX_RESIDUALS_GUIDE.md"
echo ""
