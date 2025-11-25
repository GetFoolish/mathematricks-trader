# Cerebro Service

## Overview

The Cerebro Service is the intelligent decision-making engine of the Mathematricks Trader system. It processes trading signals, performs risk analysis, calculates optimal position sizes, enforces margin constraints, and determines the final order quantities to be executed.

## Location

`/services/cerebro_service/`

## Key Responsibilities

1. Receive standardized signals from Signal Ingestion Service
2. Query Account Data Service for current account state
3. Analyze signals and determine ENTRY vs EXIT actions
4. Check for conflicting open positions
5. Calculate margin requirements for proposed trades
6. Apply position sizing algorithms with risk constraints
7. Enforce 30% slippage rule for margin safety
8. Generate trading order decisions
9. Publish orders to Execution Service
10. Store all decisions in MongoDB for audit trail

## Main Files

### cerebro_main.py (97KB)
- Pub/Sub subscriber for signals
- Main orchestration and decision logic
- Position sizing algorithms
- Margin constraint enforcement
- Order generation

### position_manager.py
- Tracks open positions by strategy and account
- Manages deployed capital
- Calculates position PnL
- Provides position lookups

### broker_adapter.py
- Abstraction layer for broker interactions
- Queries account balances and positions
- Performs margin impact calculations
- Handles broker API differences

### precision_service.py
- Broker-specific quantity rounding
- Ensures order quantities meet broker requirements
- Handles lot sizes, tick sizes, minimum quantities
- Supports stocks, futures, options, forex, crypto

### margin_calculation/
Folder containing asset-class-specific margin calculators

## Key Classes

### PositionManager
Manages position tracking:
- `get_open_position(strategy, symbol)` - Retrieve current position
- `add_position(position)` - Record new position
- `update_position(position_id, updates)` - Update existing position
- `close_position(position_id)` - Mark position as closed
- `get_deployed_capital(strategy)` - Calculate capital in use

### CerebroBrokerAdapter
Broker communication layer:
- `get_account_state(account_name)` - Fetch balances and positions
- `get_margin_available()` - Query available margin
- `preview_margin_impact(order)` - Calculate margin requirement
- `validate_order(order)` - Pre-execution validation

### MarginCalculatorFactory
Creates asset-class-specific calculators:
- `create(asset_class)` - Returns appropriate calculator
- Supported classes: STOCK, FUTURE, CRYPTO, OPTION, FOREX

## Signal Processing Workflow

```
1. Receive Signal from Pub/Sub
   ↓
2. Query Account Data Service
   - Get current balances
   - Get open positions
   - Get available margin
   ↓
3. Analyze Signal
   - Determine ENTRY or EXIT
   - Check for conflicts
   - Validate signal structure
   ↓
4. Calculate Margin Requirement
   - Use MarginCalculatorFactory
   - Asset-class specific calculation
   - Apply broker rules
   ↓
5. Position Sizing
   - Apply 30% slippage rule
   - Check margin constraints
   - Apply max position size limits
   - Calculate final quantity
   ↓
6. Generate Decision
   - APPROVED or REJECTED
   - Final quantity and price
   - Rationale/notes
   ↓
7. Publish to Execution Service
   - Pub/Sub: trading-orders topic
   ↓
8. Store Decision in MongoDB
   - Update signal_store collection
   - Audit trail
```

## Margin Calculation

### Base Margin Calculator
Location: `margin_calculation/base.py`

Abstract base class:
```python
class MarginCalculator(ABC):
    @abstractmethod
    def calculate_margin_requirement(
        self,
        symbol: str,
        quantity: int,
        price: float,
        side: str
    ) -> float:
        pass
```

### Stock Margin Calculator
Location: `margin_calculation/stock.py`

- Standard margin: 50% (2x leverage)
- Calculation: `position_value * 0.5`
- No day trading margin implemented yet

### Future Margin Calculator
Location: `margin_calculation/future.py`

- Broker-specific initial margin
- Queries broker for contract specifications
- Maintenance margin tracking
- Handles various contract multipliers

### Crypto Margin Calculator
Location: `margin_calculation/crypto.py`

- Collateral-based margin (IBKR specific)
- Uses `cashQty` for crypto orders
- Different rules for BTC, ETH, altcoins
- No leverage for most crypto pairs

### Forex Margin Calculator
Location: `margin_calculation/forex.py`

- Percentage-based margin
- Typically 2-5% of notional value
- Currency pair specific
- Handles cross-currency calculations

### Option Margin Calculator
Location: `margin_calculation/option.py`

- Portfolio margin approach
- SPAN margin for IBKR
- Considers strategy type (covered, naked, spreads)
- Complex calculation with Greeks

## Position Sizing Algorithm

### 30% Slippage Rule
Cerebro applies a conservative 30% buffer to margin calculations:
```python
max_position_value = margin_available / (margin_requirement * 1.3)
```

This ensures:
- Protection against sudden price moves
- Margin buffer for existing positions
- Prevents margin calls

### Max Position Size Constraint
From environment variable `MAX_POSITION_SIZE_PCT` (default: 10%):
```python
max_position_value = min(
    max_position_value,
    total_equity * (MAX_POSITION_SIZE_PCT / 100)
)
```

### Final Quantity Calculation
```python
final_quantity = floor(max_position_value / current_price)
final_quantity = apply_broker_precision(final_quantity, symbol, broker)
```

## MongoDB Collections

### signal_store (Read/Write)
Cerebro updates with its decision:
```json
{
  "signal_id": "sig_1732450800_5678",
  "received_time": "2024-11-24T10:30:00Z",
  "signal_data": { ... },
  "cerebro_decision": {
    "decision": "APPROVED",
    "final_quantity": 100,
    "final_price": 235.00,
    "margin_required": 11750.00,
    "margin_available": 250000.00,
    "rationale": "Position sized within margin constraints",
    "timestamp": "2024-11-24T10:30:05Z"
  },
  "order_id": null,
  "status": "APPROVED"
}
```

### positions (Read/Write)
Track open positions:
```json
{
  "_id": "pos_abc123",
  "strategy_name": "SPX 1-Day Options",
  "account_id": "acc_abc123",
  "symbol": "SPY",
  "side": "LONG",
  "quantity": 100,
  "avg_entry_price": 235.00,
  "current_price": 237.00,
  "unrealized_pnl": 200.00,
  "opened_at": "2024-11-24T10:30:00Z",
  "status": "OPEN"
}
```

## Pub/Sub Integration

### Subscribed Topics

**standardized-signals**
- Receives standardized signals from Signal Ingestion Service
- Message format: JSON with signal_id, signal_data, metadata

### Published Topics

**trading-orders**
- Sends approved orders to Execution Service
- Message format:
```json
{
  "signal_id": "sig_1732450800_5678",
  "order_type": "MARKET",
  "symbol": "SPY",
  "side": "BUY",
  "quantity": 100,
  "account_id": "acc_abc123",
  "strategy_name": "SPX 1-Day Options"
}
```

## Decision Logic

### ENTRY Signals
1. Check for existing position in same symbol
2. If position exists and same direction → REJECT (no pyramiding)
3. If position exists and opposite direction → REJECT (must exit first)
4. Calculate margin requirement
5. Apply position sizing
6. Generate BUY/SELL order

### EXIT Signals
1. Look for open position in symbol
2. If no position exists → REJECT
3. If position exists → Generate closing order
4. Quantity = full position size (close entire position)
5. Update position status to CLOSING

### Signal Type Detection
Cerebro determines signal type from the `signal_type` field:
- `signal_type: "ENTRY"` → Entry signal
- `signal_type: "EXIT"` → Exit signal
- `action: "EXIT"` → Also treated as exit (legacy support)

## Configuration

### Environment Variables
```bash
# Account Data Service URL
ACCOUNT_DATA_SERVICE_URL=http://localhost:8082

# Risk limits
MAX_POSITION_SIZE_PCT=10
MAX_BROKER_ALLOCATION_PCT=40

# Margin safety buffer (hardcoded in cerebro_main.py)
SLIPPAGE_BUFFER=0.30  # 30%

# Mock broker for testing
USE_MOCK_BROKER=false
```

## Error Handling

1. **Account Query Failures**
   - Logs error
   - Rejects signal with reason
   - Does not publish to Execution Service

2. **Invalid Signals**
   - Validates required fields
   - Rejects malformed signals
   - Stores rejection reason in signal_store

3. **Margin Constraint Violations**
   - Calculates safe position size
   - If quantity < minimum tradeable → REJECT
   - Logs constraint details

4. **Conflicting Positions**
   - Detects existing positions
   - Rejects new ENTRY if position exists
   - Logs conflict details

## Logging

Logs to:
- Console (real-time output)
- `logs/cerebro_service.log` (service-specific)
- `logs/signal_processing.log` (unified signal journey)

Log format:
```
Timestamp | [CEREBRO] | Message
```

Example log entries:
```
2024-11-24 10:30:05 | [CEREBRO] | Processing signal: sig_1732450800_5678
2024-11-24 10:30:06 | [CEREBRO] | Account state: Equity=$1000000, Available=$250000
2024-11-24 10:30:07 | [CEREBRO] | Margin required: $11750, Available: $250000
2024-11-24 10:30:08 | [CEREBRO] | Position sized: 100 shares of SPY at $235.00
2024-11-24 10:30:09 | [CEREBRO] | Decision: APPROVED, Publishing to trading-orders
```

## Portfolio Constructors (Research)

Located in `portfolio_constructor/`:

### Max CAGR Strategy
File: `max_cagr/strategy.py`
- Maximizes compound annual growth rate
- Uses historical returns
- Optimizes for long-term growth

### Max Sharpe Strategy
File: `max_sharpe/strategy.py`
- Maximizes risk-adjusted returns
- Uses Sharpe ratio optimization
- Balances return vs volatility

### Max CAGR v2 Strategy
File: `max_cagr_v2/strategy.py`
- Enhanced CAGR optimization
- Considers drawdown constraints
- Improved risk management

### Max Hybrid Strategy
File: `max_hybrid/strategy.py`
- Combines CAGR and Sharpe approaches
- Weighted multi-objective optimization
- Balanced growth and stability

**Note:** These are research modules for portfolio optimization, not actively used in live signal processing.

## Precision Service

The precision service ensures order quantities meet broker requirements.

### Key Functions

**apply_broker_precision(quantity, symbol, broker)**
- Rounds quantity to broker-acceptable value
- Handles lot sizes (e.g., options contracts)
- Respects minimum quantities

### Broker-Specific Rules

**IBKR:**
- Stocks: Whole shares (round down)
- Options: Whole contracts
- Futures: Whole contracts
- Forex: Depends on pair (typically 1000 units)
- Crypto: Uses `cashQty` (USD amount)

**Zerodha:**
- Stocks: Whole shares
- Options: Lot size multiples (Nifty: 50, BankNifty: 25)
- Futures: Lot size multiples

## Dependencies

- **Google Cloud Pub/Sub** - Signal input/output
- **MongoDB** - Decision storage
- **Account Data Service API** - Account state queries
- **BrokerFactory** - Margin calculations
- **Telegram notifier** - Critical alerts
- **Python packages**:
  - `google-cloud-pubsub>=2.18.4`
  - `pymongo>=4.6.1`
  - `requests>=2.31.0`
  - `numpy>=2.3.4`
  - `pandas>=2.3.3`

## Startup Command

```bash
# Via mvp_demo_start.py
python mvp_demo_start.py

# Manual startup
python services/cerebro_service/cerebro_main.py

# With mock broker
python services/cerebro_service/cerebro_main.py --use-mock-broker
```

## Health Checks

Check service status:
```bash
python mvp_demo_status.py
```

View logs:
```bash
tail -f logs/cerebro_service.log
tail -f logs/signal_processing.log
```

Monitor Pub/Sub subscriptions:
```bash
gcloud pubsub subscriptions list
```

## Testing

### Send Test Signal
```bash
cd tests/signals_testing
python send_test_signal.py --file equity_simple_signal_1.json
```

### Monitor Processing
```bash
# Watch unified signal journey
tail -f logs/signal_processing.log | grep CEREBRO

# Watch Cerebro-specific logs
tail -f logs/cerebro_service.log
```

### Check Decision in MongoDB
```bash
mongosh
use mathematricks_trading
db.signal_store.findOne({"signal_id": "sig_1732450800_5678"})
```

## Related Documentation

- [Signal Ingestion Service](signal_ingestion.md) - Sends signals to Cerebro
- [Account Data Service](account_data_service.md) - Provides account state
- [Execution Service](execution_service.md) - Receives orders from Cerebro
- [Brokers](brokers.md) - Broker abstraction layer
- [Testing Signals](signals_testing.md) - How to test signal flow

## Common Issues

### Signals Not Being Processed
- Check Pub/Sub subscription: `standardized-signals`
- Verify Cerebro service is running
- Look for errors in `cerebro_service.log`
- Ensure MongoDB is accessible

### All Signals Rejected
- Check Account Data Service is running (port 8082)
- Verify account has sufficient margin
- Check `MAX_POSITION_SIZE_PCT` setting
- Look for account query errors in logs

### Incorrect Position Sizing
- Verify margin calculation for asset class
- Check 30% slippage buffer application
- Ensure broker precision rules are correct
- Test with `USE_MOCK_BROKER=true`

### Margin Calculation Errors
- Check broker connection in Account Data Service
- Verify symbol format matches broker
- Look for margin calculation errors in logs
- Test margin preview API directly

## Performance Considerations

- Cerebro processes signals sequentially (no parallel processing)
- Account queries add ~100-200ms latency per signal
- Margin calculations are typically fast (<50ms)
- MongoDB writes are asynchronous
- Pub/Sub publish is fast (~10-50ms)

Total signal processing time: ~300-500ms per signal
