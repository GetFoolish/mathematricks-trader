# Cerebro Service

The Cerebro Service is the intelligent position sizing and portfolio management engine of the Mathematricks Trading System. It determines optimal position sizes based on fund allocations, validates margin requirements, and routes orders to appropriate trading accounts.

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Key Components](#key-components)
- [Position Sizing Logic](#position-sizing-logic)
- [Fund Architecture](#fund-architecture)
- [Account Routing](#account-routing)
- [Configuration](#configuration)
- [Usage](#usage)
- [Monitoring](#monitoring)

---

## Overview

### Purpose
- **Position Sizing**: Calculate optimal position sizes based on portfolio allocations
- **Fund Management**: Support multi-fund architecture with percentage-based allocations
- **Risk Management**: Validate margin requirements and prevent over-leveraging
- **Account Routing**: Intelligently distribute orders across compatible trading accounts
- **Decision Recording**: Update signal_store with cerebro decision data

### Technology Stack
- **Python 3.11+**
- **PyMongo** (MongoDB Change Streams)
- **FastAPI** client (Account Data Service communication)
- **Docker** (containerization)

### Location
```
services/cerebro_service/
├── cerebro_main.py              # Main entry point with Change Stream watcher
├── position_sizing.py           # Core position sizing logic
├── fund_allocation_logic.py     # Fund-based capital allocation
├── broker_adapter.py            # Margin calculation via broker API
├── precision_service.py         # Instrument-specific rounding
├── position_manager.py          # Position tracking
├── portfolio_constructor/       # Portfolio optimization strategies
│   ├── max_cagr.py
│   └── max_hybrid.py
└── margin_calculation/          # Broker-specific margin calculators
    ├── ibkr_margin.py
    └── zerodha_margin.py
```

---

## Architecture

### Service Model
The Cerebro Service operates as a **MongoDB Change Stream watcher** that:

1. Watches `signal_store` collection for new legs without cerebro decisions
2. Retrieves fund allocation from `funds` → `portfolio_tests` collections
3. Calculates position sizes based on strategy allocation
4. Validates margin requirements via Account Data Service
5. Creates orders in `trading_orders` collection
6. Updates `signal_store.legs[].decision` field with cerebro data

### Design Philosophy
- **Fund-First**: All capital allocation starts at the fund level
- **Strategy-Based**: Each strategy gets a percentage of fund equity
- **Account-Agnostic**: Capital distributed across accounts automatically
- **Risk-Aware**: Margin validation prevents over-leveraging
- **Deterministic**: Same inputs always produce same position sizes

---

## Key Components

### 1. `cerebro_main.py`
**Main service orchestrator with MongoDB Change Stream watching**

**Key Functions**:
```python
def watch_signal_store():
    """
    Watch signal_store for new legs needing cerebro decisions

    Pipeline:
    - Match documents where legs[].decision is null
    - Process each leg sequentially
    - Calculate position size
    - Create trading orders
    - Update signal_store with decision data
    """
```

**Change Stream Pipeline**:
```python
pipeline = [
    {
        "$match": {
            "operationType": {"$in": ["insert", "update"]},
            "fullDocument.legs": {
                "$elemMatch": {"decision": None}  # Find legs without decisions
            }
        }
    }
]
```

---

### 2. `position_sizing.py`
**Core position sizing calculation logic**

**Main Function**:
```python
def calculate_position_size(
    signal_id: str,
    strategy_id: str,
    instrument: str,
    raw_quantity: int,
    signal_price: float,
    fund_id: str
) -> dict:
    """
    Calculate cerebro position size based on fund allocation

    Steps:
    1. Get fund's total equity from trading_accounts
    2. Retrieve strategy allocation % from portfolio_allocations
    3. Calculate allocated capital = fund_equity * allocation_%
    4. Determine position size based on signal and allocation
    5. Round to instrument-specific lot sizes
    6. Validate margin requirements
    7. Distribute across compatible accounts

    Returns:
        {
            "strategy_allocation": 0.15,           # 15% of fund
            "allocated_capital": 150000.00,        # $150k allocated
            "cerebro_quantity": 300,               # Calculated quantity
            "accounts": [                          # Account distribution
                {"account_id": "OANDA_MOCK", "quantity": 150, "fund_id": "fund_001"},
                {"account_id": "VANTAGE_MOCK", "quantity": 150, "fund_id": "fund_001"}
            ],
            "margin_required": 30000.00,
            "cerebro_timestamp": "2024-01-09T12:00:05Z"
        }
    """
```

**Position Sizing Formula**:
```python
# 1. Get fund equity
fund_equity = sum(account.equity for account in fund_accounts)

# 2. Get strategy allocation percentage
allocation = get_active_allocation(fund_id, strategy_id)  # e.g., 0.15 = 15%

# 3. Calculate allocated capital
allocated_capital = fund_equity * allocation

# 4. Calculate position size
# Method A: Price-based sizing
cerebro_quantity = allocated_capital / signal_price

# Method B: Quantity scaling (if raw quantity provided)
scaling_factor = allocated_capital / signal_account_equity
cerebro_quantity = raw_quantity * scaling_factor

# 5. Round to lot size
cerebro_quantity = round_to_lot_size(cerebro_quantity, instrument)

# 6. Distribute across accounts
account_distribution = distribute_across_accounts(cerebro_quantity, strategy_id, fund_id)
```

---

### 3. `fund_allocation_logic.py`
**Fund-based capital allocation retrieval**

**Key Functions**:

#### `get_active_allocations_for_strategy()`
```python
def get_active_allocations_for_strategy(
    strategy_id: str,
    funds_collection,
    portfolio_tests_collection
) -> List[Dict]:
    """
    Get active allocation percentage for strategy across all funds
    Single source of truth: funds → portfolio_tests

    Query Flow:
    1. Find all ACTIVE funds with portfolio_test_id
    2. For each fund, fetch portfolio test from portfolio_tests collection
    3. Extract allocations[strategy_id] percentage
    4. Return list of fund allocations

    Example:
    Fund document:
    {
        "fund_id": "mock-fund-1",
        "status": "ACTIVE",
        "portfolio_test_id": "equal_weighted_allocation_for_testing"
    }

    Portfolio test document:
    {
        "test_id": "equal_weighted_allocation_for_testing",
        "allocations": {
            "SPY": 11.11,           # 11.11%
            "TLT": 11.11,           # 11.11%
            "Com1-Met": 11.11       # 11.11%
        }
    }

    Returns:
        [
            {
                "fund_id": "mock-fund-1",
                "allocations": {"SPY": 11.11, "TLT": 11.11, ...},
                "portfolio_test_id": "equal_weighted_allocation_for_testing"
            }
        ]
    """
```

#### `get_fund_equity()`
```python
def get_fund_equity(fund_id: str) -> float:
    """
    Calculate total fund equity across all accounts

    Query:
    - Find all trading_accounts where fund_id matches
    - Sum account.balances.equity for each account

    Example:
    fund_001 has 3 accounts:
    - OANDA_MOCK: $500,000
    - VANTAGE_MOCK: $300,000
    - IBKR_LIVE: $200,000
    Total fund equity: $1,000,000

    Returns:
        1000000.00
    """
```

---

### 4. `broker_adapter.py`
**Margin calculation via broker APIs**

**Key Functions**:

#### `calculate_margin_requirement()`
```python
def calculate_margin_requirement(
    account_id: str,
    instrument: str,
    quantity: int,
    price: float,
    order_type: str = "MARKET"
) -> float:
    """
    Calculate margin required for position via broker API

    Steps:
    1. Determine broker type (IBKR/Zerodha/Mock)
    2. Query Account Data Service for margin preview
    3. Return margin requirement

    API Call:
    POST /accounts/margin-preview
    {
        "account_id": "OANDA_MOCK",
        "instrument": "SPY",
        "quantity": 100,
        "price": 450.25,
        "order_type": "MARKET"
    }

    Returns:
        9005.00  # $9,005 margin required
    """
```

---

### 5. `precision_service.py`
**Instrument-specific quantity rounding**

**Purpose**: Different instruments have different lot sizes and precision requirements

**Examples**:
```python
# Stocks: Round to nearest whole share
round_to_lot_size(100.7, "AAPL") → 101

# Futures: Round to contract lot sizes
round_to_lot_size(3.2, "ES")  → 3   # E-mini S&P 500 contracts
round_to_lot_size(4.8, "GC")  → 5   # Gold futures contracts

# Forex: Round to micro lots
round_to_lot_size(0.15, "EUR/USD") → 0.1  # 10,000 units

# Options: Round to whole contracts
round_to_lot_size(7.3, "SPX_C_4500") → 7  # Option contracts
```

**Implementation**:
```python
LOT_SIZES = {
    "STOCK": 1,           # Whole shares
    "FUTURE": 1,          # Whole contracts
    "FOREX": 0.01,        # Micro lots (1,000 units)
    "OPTION": 1,          # Whole contracts
    "CRYPTO": 0.00000001  # Satoshi for BTC
}

def round_to_lot_size(quantity: float, instrument: str) -> int:
    instrument_type = get_instrument_type(instrument)
    lot_size = LOT_SIZES.get(instrument_type, 1)
    return round(quantity / lot_size) * lot_size
```

---

### 6. `position_manager.py`
**Position tracking and aggregation**

**Key Functions**:

#### `get_open_positions()`
```python
def get_open_positions(account_id: str, instrument: str = None) -> list:
    """
    Get open positions for account, optionally filtered by instrument

    Query:
    - Find trading_accounts document by account_id
    - Return open_positions[] array
    - Filter by instrument if specified

    Returns:
        [
            {
                "instrument": "SPY",
                "quantity": 100,
                "avg_entry_price": 450.25,
                "current_price": 455.50,
                "unrealized_pnl": 525.00
            }
        ]
    """
```

#### `update_position_tracking()`
```python
def update_position_tracking(
    account_id: str,
    instrument: str,
    quantity_change: int,
    price: float
):
    """
    Update account's open_positions array

    ENTRY (quantity_change > 0):
    - Add new position or increase existing position
    - Update avg_entry_price using weighted average

    EXIT (quantity_change < 0):
    - Decrease position or remove if fully closed
    - Calculate realized P&L
    - Update account.balances.realized_pnl
    """
```

---

## Position Sizing Logic

### Calculation Flow

```
1. SIGNAL ARRIVES
   ↓
   Raw Signal: SPY ENTRY, Qty=100, Price=$450, Strategy Equity=$50k

2. GET FUND EQUITY
   ↓
   Query trading_accounts where fund_id="fund_001"
   Total Fund Equity = $1,000,000

3. GET STRATEGY ALLOCATION
   ↓
   Query funds → portfolio_tests via portfolio_test_id
   SPY Strategy Allocation = 15%

4. CALCULATE ALLOCATED CAPITAL
   ↓
   Allocated Capital = $1,000,000 × 0.15 = $150,000

5. DETERMINE POSITION SIZE
   ↓
   Method: Scale raw quantity by capital ratio
   Scaling Factor = $150,000 / $50,000 = 3.0
   Cerebro Quantity = 100 × 3.0 = 300 shares

6. VALIDATE MARGIN
   ↓
   Call Account Data Service: /accounts/margin-preview
   Margin Required = $60,000 (assuming 50% margin)
   Available Margin = $500,000 ✓ (sufficient)

7. DISTRIBUTE ACROSS ACCOUNTS
   ↓
   Find accounts with fund_id="fund_001" and asset_class="EQUITY"
   - OANDA_MOCK: 150 shares
   - VANTAGE_MOCK: 150 shares
   Total: 300 shares

8. CREATE ORDERS
   ↓
   Insert into trading_orders collection:
   - Order 1: OANDA_MOCK, 150 shares, PENDING
   - Order 2: VANTAGE_MOCK, 150 shares, PENDING

9. UPDATE SIGNAL_STORE
   ↓
   Update signal_store.legs[0].decision:
   {
       "strategy_allocation": 0.15,
       "allocated_capital": 150000.00,
       "cerebro_quantity": 300,
       "legs": [
           {"account_id": "OANDA_MOCK", "quantity": 150},
           {"account_id": "VANTAGE_MOCK", "quantity": 150}
       ]
   }
```

---

## Fund Architecture

### Fund Structure (v5.1)

The system supports a **multi-fund architecture** where:

1. **Funds** are top-level entities that own multiple accounts
2. **Accounts** belong to exactly one fund
3. **Strategies** are allocated a percentage of fund equity via approved portfolio tests
4. **Capital** is distributed across accounts automatically
5. **Single Source of Truth**: Allocations stored in `portfolio_tests`, referenced by `funds.portfolio_test_id`

### Example Fund Setup

```json
// funds collection
{
    "_id": ObjectId("..."),
    "fund_id": "fund_001",
    "name": "Vandan's Main Fund",
    "total_equity": 1000000.00,
    "accounts": ["OANDA_MOCK", "VANTAGE_MOCK", "IBKR_LIVE"],
    "status": "ACTIVE",
    "created_at": "2024-01-01T00:00:00Z"
}

// trading_accounts collection
{
    "account_id": "OANDA_MOCK",
    "fund_id": "fund_001",              // Belongs to fund_001
    "broker": "OANDA",
    "balances": {
        "equity": 500000.00
    },
    "asset_classes": {
        "EQUITY": true,
        "FUTURE": true,
        "FOREX": true
    }
}

{
    "account_id": "VANTAGE_MOCK",
    "fund_id": "fund_001",              // Belongs to fund_001
    "broker": "VANTAGE",
    "balances": {
        "equity": 300000.00
    },
    "asset_classes": {
        "EQUITY": true,
        "FUTURE": true
    }
}

// portfolio_tests collection (single source of truth for allocations)
{
    "test_id": "test_20260114_120000",
    "allocations": {
        "SPY": 20.0,                     // 20% to SPY strategy
        "TLT": 15.0,                     // 15% to TLT strategy
        "Com1-Met": 10.0,                // 10% to Com1-Met strategy
        "Florida-Forex": 5.0             // 5% to Florida-Forex
    },
    "performance": {
        "cagr": 1.45,
        "sharpe": 2.1,
        "max_drawdown": -0.08
    },
    "created_at": "2024-01-01T00:00:00Z"
}

// Fund references the approved test
{
    "fund_id": "fund_001",
    "portfolio_test_id": "test_20260114_120000",  // Links to portfolio test
    "allocation_approved_at": "2024-01-01T12:00:00Z"
}
```

### Capital Allocation Example

**Scenario**: SPY strategy (20% allocation) receives ENTRY signal

```python
# 1. Get fund equity
fund_accounts = get_fund_accounts("fund_001")
fund_equity = sum([500000, 300000, 200000])  # $1M total

# 2. Get strategy allocation
allocation = get_active_allocation("fund_001", "SPY")  # 0.20 = 20%

# 3. Calculate allocated capital
allocated_capital = 1000000 * 0.20 = $200,000

# 4. Determine position size
signal_price = $450
cerebro_quantity = 200000 / 450 = 444 shares (rounded to 444)

# 5. Distribute across accounts (proportional to account equity)
total_equity = 1000000
account_quantities = [
    ("OANDA_MOCK", 444 * (500000/1000000)),    # 222 shares
    ("VANTAGE_MOCK", 444 * (300000/1000000)),  # 133 shares
    ("IBKR_LIVE", 444 * (200000/1000000))      # 89 shares
]
```

---

## Account Routing

### Routing Logic

Cerebro intelligently routes orders to compatible accounts based on:

1. **Fund Ownership**: Account must belong to the strategy's fund
2. **Asset Class Compatibility**: Account must support the instrument's asset class
3. **Strategy Permissions**: Strategy must list account in `strategies.accounts[]`
4. **Margin Availability**: Account must have sufficient margin

### Routing Algorithm

```python
def route_order_to_accounts(
    strategy_id: str,
    fund_id: str,
    instrument: str,
    total_quantity: int
) -> list:
    """
    Distribute order across compatible accounts

    Steps:
    1. Get instrument asset class (EQUITY, FUTURE, FOREX, OPTION)
    2. Find accounts where:
       - fund_id matches
       - asset_classes[instrument_type] = true
       - account_id in strategy.accounts[]
    3. Check margin availability for each account
    4. Distribute quantity proportionally by account equity
    5. Return list of (account_id, quantity) tuples
    """

    # Example
    instrument_type = get_instrument_type(instrument)  # "EQUITY"
    compatible_accounts = []

    for account in get_fund_accounts(fund_id):
        # Check asset class support
        if not account.asset_classes.get(instrument_type):
            continue

        # Check strategy permissions
        strategy = get_strategy(strategy_id)
        if account.account_id not in strategy.accounts:
            continue

        # Check margin availability
        required_margin = calculate_margin(account, instrument, quantity, price)
        if account.balances.margin_available < required_margin:
            continue

        compatible_accounts.append(account)

    # Distribute quantity proportionally
    total_equity = sum(acc.balances.equity for acc in compatible_accounts)
    distribution = []

    for account in compatible_accounts:
        proportion = account.balances.equity / total_equity
        account_quantity = round(total_quantity * proportion)
        distribution.append((account.account_id, account_quantity))

    return distribution
```

### Example Routing Scenarios

**Scenario 1: Equity Signal (SPY)**
```
Strategy: SPY (EQUITY asset class)
Fund: fund_001
Signal: BUY 300 shares

Compatible Accounts:
✓ OANDA_MOCK (equity=$500k, asset_classes={EQUITY:true})
✓ VANTAGE_MOCK (equity=$300k, asset_classes={EQUITY:true})
✗ IBKR_FUTURES (asset_classes={FUTURE:true, EQUITY:false})

Distribution:
- OANDA_MOCK: 187 shares (62.5% of 300)
- VANTAGE_MOCK: 113 shares (37.5% of 300)
```

**Scenario 2: Futures Signal (GC - Gold)**
```
Strategy: Com1-Met (FUTURE asset class)
Fund: fund_001
Signal: BUY 10 contracts

Compatible Accounts:
✓ OANDA_MOCK (equity=$500k, asset_classes={FUTURE:true})
✗ VANTAGE_MOCK (asset_classes={EQUITY:true, FUTURE:false})
✓ IBKR_FUTURES (equity=$200k, asset_classes={FUTURE:true})

Distribution:
- OANDA_MOCK: 7 contracts (71% of 10)
- IBKR_FUTURES: 3 contracts (29% of 10)
```

---

## Configuration

### Environment Variables

```bash
# .env file

# Account Data Service URL (for margin calculations)
ACCOUNT_DATA_SERVICE_URL=http://account-data-service:8082

# Mock Broker Mode (for testing)
USE_MOCK_BROKER=true

# Default Account (fallback if routing fails)
DEFAULT_ACCOUNT_ID=Mock_Paper

# MongoDB Connection
MONGODB_URI=mongodb://mongodb:27017/mathematricks_trading
```

### Docker Compose Configuration

```yaml
# docker-compose.yml
services:
  cerebro-service:
    build: ./services/cerebro_service
    container_name: mathematricks-trader-cerebro-service-1
    command: python cerebro_main.py --staging
    environment:
      - MONGODB_URI=${MONGODB_URI}
      - ACCOUNT_DATA_SERVICE_URL=${ACCOUNT_DATA_SERVICE_URL}
      - USE_MOCK_BROKER=${USE_MOCK_BROKER}
    ports:
      - "5678:5678"  # Python debugger
    depends_on:
      - mongodb
      - account-data-service
    networks:
      - tradenet
    restart: unless-stopped
```

---

## Usage

### Starting the Service

```bash
# Via Docker Compose (Recommended)
make start

# View Cerebro logs
make logs-cerebro

# Restart Cerebro only
docker restart mathematricks-trader-cerebro-service-1

# Standalone (Development)
cd services/cerebro_service
python cerebro_main.py --staging
```

### Verifying Position Sizing

#### Check signal_store for Decision Data
```bash
# MongoDB shell
docker exec -it mathematricks-trader-mongodb-1 mongosh mathematricks_trading

> db.signal_store.find({signal_id: "sig_spy_001"}).pretty()

# Expected output (legs[0].decision should be populated):
{
    "signal_id": "sig_spy_001",
    "legs": [
        {
            "leg_type": "ENTRY",
            "decision": {
                "strategy_allocation": 0.20,
                "allocated_capital": 200000.00,
                "cerebro_quantity": 444,
                "legs": [
                    {"account_id": "OANDA_MOCK", "quantity": 222},
                    {"account_id": "VANTAGE_MOCK", "quantity": 222}
                ]
            }
        }
    ]
}
```

#### Check trading_orders Collection
```bash
> db.trading_orders.find({signal_id: "sig_spy_001"}).pretty()

# Expected output (2 orders created):
[
    {
        "order_id": "ord_001",
        "signal_id": "sig_spy_001",
        "account_id": "OANDA_MOCK",
        "quantity": 222,
        "status": "PENDING"
    },
    {
        "order_id": "ord_002",
        "signal_id": "sig_spy_001",
        "account_id": "VANTAGE_MOCK",
        "quantity": 222,
        "status": "PENDING"
    }
]
```

---

## Monitoring

### Log Files
- **Docker**: `docker logs mathematricks-trader-cerebro-service-1`
- **Local**: `logs/cerebro_service.log`

### Log Format
```
2024-01-09 12:00:05 INFO  [cerebro] Processing ENTRY leg for signal: sig_spy_001
2024-01-09 12:00:05 INFO  [cerebro] Fund equity: $1,000,000.00
2024-01-09 12:00:05 INFO  [cerebro] Strategy allocation: 20%
2024-01-09 12:00:05 INFO  [cerebro] Allocated capital: $200,000.00
2024-01-09 12:00:05 INFO  [cerebro] Cerebro quantity: 444 shares
2024-01-09 12:00:05 INFO  [cerebro] Distributed to 2 accounts
2024-01-09 12:00:05 INFO  [cerebro] Created 2 trading orders
2024-01-09 12:00:05 INFO  [cerebro] Updated signal_store with decision data
```

### Key Metrics
1. **Position Sizing Accuracy**: Verify cerebro quantities match allocation percentages
2. **Margin Utilization**: Monitor margin usage across accounts
3. **Account Distribution**: Verify orders distributed correctly
4. **Processing Latency**: Time from signal arrival to order creation
5. **Rejection Rate**: Orders rejected due to insufficient margin

---

## Related Documentation
- [Signal Ingestion Service](signal_ingestion_service.md) - Signal processing
- [Account Data Service](account_data_service.md) - Account state management
- [Execution Service](execution_service.md) - Order execution
- [Setup Guide](../Setup.md) - Initial setup
