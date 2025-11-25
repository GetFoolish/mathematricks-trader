# Signal Specification for Strategy Developers

## Overview

This document defines the signal payload structure required by the Mathematricks trading system. All signals sent to the API must conform to this specification.

---

## API Endpoint

**URL:** `https://staging.mathematricks.fund/api/signals` (staging)
**URL:** `https://mathematricks.fund/api/signals` (production)
**Method:** POST
**Content-Type:** application/json

---

## Signal Envelope Structure

All signals must be wrapped in this envelope:

```json
{
  "timestamp": "2025-10-28T12:00:00.000000+00:00",
  "signalID": "SPY_20251028_120000_001",
  "signal_sent_EPOCH": 1730116800,
  "strategy_name": "SPY",
  "signal": {
    // Signal payload goes here (see below)
  },
  "environment": "staging",
  "passphrase": "your_passphrase_here"
}
```

**Required Envelope Fields:**
- `timestamp` - ISO 8601 format with timezone
- `signalID` - Unique identifier (format: `{strategy}_{YYYYMMDD}_{HHMMSS}_{sequence}`)
- `signal_sent_EPOCH` - Unix timestamp (seconds since epoch)
- `strategy_name` - Your strategy identifier
- `signal` - The actual signal payload (see specifications below)
- `environment` - "staging" or "production"
- `passphrase` - Authentication passphrase

---

## Signal Payload Structure

### Core Required Fields (All Asset Types)

```json
{
  "strategy_id": "SPY",
  "instrument_type": "STOCK",      // REQUIRED: STOCK, OPTION, FOREX, or FUTURE
  "instrument": "SPY",             // Symbol (not required for options)
  "direction": "LONG",             // LONG or SHORT
  "action": "BUY",                 // BUY or SELL
  "order_type": "MARKET",          // MARKET or LIMIT
  "price": 575.25,                 // Current price or limit price
  "quantity": 100,                 // Number of shares/contracts/units
  "signal_type": "ENTRY",          // Optional: ENTRY, EXIT, SCALE_IN, SCALE_OUT
  "account": "DU1234567"           // IBKR account ID
}
```

### Optional Fields (All Asset Types)

```json
{
  "stop_loss": 570.00,             // Stop loss price (0 if none)
  "take_profit": 580.00            // Take profit price (0 if none)
}
```

---

## Asset Type Specifications

### 1. STOCK (Equities)

**Required Fields:**
- `instrument_type`: "STOCK"
- `instrument`: Ticker symbol (e.g., "SPY", "AAPL", "TSLA")

**Example - Simple Stock Entry:**

```json
{
  "signal": {
    "strategy_id": "SPY",
    "instrument_type": "STOCK",
    "instrument": "SPY",
    "direction": "LONG",
    "action": "BUY",
    "order_type": "MARKET",
    "price": 575.25,
    "quantity": 100,
    "signal_type": "ENTRY",
    "account": "DU1234567",
    "stop_loss": 570.00,
    "take_profit": 585.00
  }
}
```

**Example - Stock Exit:**

```json
{
  "signal": {
    "strategy_id": "SPY",
    "instrument_type": "STOCK",
    "instrument": "SPY",
    "direction": "LONG",
    "action": "SELL",
    "order_type": "MARKET",
    "price": 580.50,
    "quantity": 100,
    "signal_type": "EXIT",
    "account": "DU1234567"
  }
}
```

**Example - Scale In (Adding to Position):**

```json
{
  "signal": {
    "strategy_id": "AAPL",
    "instrument_type": "STOCK",
    "instrument": "AAPL",
    "direction": "LONG",
    "action": "BUY",
    "order_type": "LIMIT",
    "price": 229.50,
    "quantity": 50,
    "signal_type": "SCALE_IN",
    "account": "DU1234567"
  }
}
```

---

### 2. FOREX (Currency Pairs)

**Required Fields:**
- `instrument_type`: "FOREX"
- `instrument`: 6-character currency pair (e.g., "EURUSD", "GBPUSD")

**Example - Forex Entry:**

```json
{
  "signal": {
    "strategy_id": "Forex",
    "instrument_type": "FOREX",
    "instrument": "EURUSD",
    "direction": "LONG",
    "action": "BUY",
    "order_type": "MARKET",
    "price": 1.0850,
    "quantity": 100000,
    "signal_type": "ENTRY",
    "account": "DU1234567"
  }
}
```

**Example - Forex Exit:**

```json
{
  "signal": {
    "strategy_id": "Forex",
    "instrument_type": "FOREX",
    "instrument": "GBPUSD",
    "direction": "SHORT",
    "action": "BUY",
    "order_type": "MARKET",
    "price": 1.2700,
    "quantity": 150000,
    "signal_type": "EXIT",
    "account": "DU1234567"
  }
}
```

**Supported Currency Pairs:**
- Major pairs: EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, USDCAD, NZDUSD
- Cross pairs: EURJPY, GBPJPY, EURGBP, EURAUD, EURCHF, etc.

**Quantity:** Typically in increments of 1,000 or 10,000 units (micro/mini lots)

---

### 3. FUTURES (Commodities & Indices)

**Required Fields:**
- `instrument_type`: "FUTURE"
- `instrument`: Future symbol (e.g., "GC", "CL", "ES")
- `expiry`: Contract expiration date (YYYYMMDD format)
- `exchange`: Exchange code (e.g., "COMEX", "NYMEX", "CME")

**Example - Gold Futures Entry:**

```json
{
  "signal": {
    "strategy_id": "Com1-Met",
    "instrument_type": "FUTURE",
    "instrument": "GC",
    "expiry": "20251226",
    "exchange": "COMEX",
    "direction": "LONG",
    "action": "BUY",
    "order_type": "MARKET",
    "price": 2650.00,
    "quantity": 2,
    "signal_type": "ENTRY",
    "account": "DU1234567"
  }
}
```

**Example - Crude Oil Futures Exit:**

```json
{
  "signal": {
    "strategy_id": "Com2-Ag",
    "instrument_type": "FUTURE",
    "instrument": "CL",
    "expiry": "20251219",
    "exchange": "NYMEX",
    "direction": "LONG",
    "action": "SELL",
    "order_type": "MARKET",
    "price": 77.50,
    "quantity": 5,
    "signal_type": "EXIT",
    "account": "DU1234567"
  }
}
```

**Common Futures Contracts:**
| Symbol | Name | Exchange | Contract Size |
|--------|------|----------|---------------|
| GC | Gold | COMEX | 100 troy oz |
| SI | Silver | COMEX | 5,000 troy oz |
| CL | Crude Oil | NYMEX | 1,000 barrels |
| NG | Natural Gas | NYMEX | 10,000 MMBtu |
| ES | E-mini S&P 500 | CME | $50 × index |
| NQ | E-mini NASDAQ | CME | $20 × index |

**Important:** Use active contract months (not expired contracts)

---

### 4. OPTIONS - Single Leg

**Required Fields:**
- `instrument_type`: "OPTION"
- `underlying`: Underlying symbol (e.g., "SPY", "QQQ")
- `legs`: Array with one leg object

**Leg Object Fields:**
- `strike`: Strike price
- `expiry`: Expiration date (YYYYMMDD format)
- `right`: "C" (Call) or "P" (Put)
- `action`: "BUY" or "SELL"
- `quantity`: Number of contracts

**Example - Long Call Entry:**

```json
{
  "signal": {
    "strategy_id": "SPY_0DE_Opt",
    "instrument_type": "OPTION",
    "underlying": "SPY",
    "legs": [
      {
        "strike": 575.0,
        "expiry": "20251128",
        "right": "C",
        "action": "BUY",
        "quantity": 10
      }
    ],
    "direction": "LONG",
    "action": "BUY",
    "order_type": "MARKET",
    "price": 5.50,
    "quantity": 10,
    "signal_type": "ENTRY",
    "account": "DU1234567"
  }
}
```

**Example - Long Put Entry:**

```json
{
  "signal": {
    "strategy_id": "QQQ_Hedge",
    "instrument_type": "OPTION",
    "underlying": "QQQ",
    "legs": [
      {
        "strike": 480.0,
        "expiry": "20251128",
        "right": "P",
        "action": "BUY",
        "quantity": 20
      }
    ],
    "direction": "LONG",
    "action": "BUY",
    "order_type": "MARKET",
    "price": 4.75,
    "quantity": 20,
    "signal_type": "ENTRY",
    "account": "DU1234567"
  }
}
```

**Example - Single-Leg Exit:**

```json
{
  "signal": {
    "strategy_id": "SPY_0DE_Opt",
    "instrument_type": "OPTION",
    "underlying": "SPY",
    "legs": [
      {
        "strike": 575.0,
        "expiry": "20251128",
        "right": "C",
        "action": "SELL",
        "quantity": 10
      }
    ],
    "direction": "LONG",
    "action": "SELL",
    "order_type": "MARKET",
    "price": 6.25,
    "quantity": 10,
    "signal_type": "EXIT",
    "account": "DU1234567"
  }
}
```

---

### 5. OPTIONS - Multi-Leg Strategies

Multi-leg strategies are defined by providing multiple leg objects in the `legs` array. The system handles each leg generically without hardcoded strategy types.

#### Example - Bull Call Spread (2 Legs)

**Entry:**
```json
{
  "signal": {
    "strategy_id": "SPY_Spreads",
    "instrument_type": "OPTION",
    "underlying": "SPY",
    "legs": [
      {
        "strike": 575.0,
        "expiry": "20251128",
        "right": "C",
        "action": "BUY",
        "quantity": 5
      },
      {
        "strike": 585.0,
        "expiry": "20251128",
        "right": "C",
        "action": "SELL",
        "quantity": 5
      }
    ],
    "direction": "LONG",
    "action": "BUY",
    "order_type": "MARKET",
    "price": 3.50,
    "quantity": 5,
    "signal_type": "ENTRY",
    "account": "DU1234567"
  }
}
```

**Exit (Reverse the Actions):**
```json
{
  "signal": {
    "strategy_id": "SPY_Spreads",
    "instrument_type": "OPTION",
    "underlying": "SPY",
    "legs": [
      {
        "strike": 575.0,
        "expiry": "20251128",
        "right": "C",
        "action": "SELL",
        "quantity": 5
      },
      {
        "strike": 585.0,
        "expiry": "20251128",
        "right": "C",
        "action": "BUY",
        "quantity": 5
      }
    ],
    "direction": "LONG",
    "action": "SELL",
    "order_type": "MARKET",
    "price": 4.25,
    "quantity": 5,
    "signal_type": "EXIT",
    "account": "DU1234567"
  }
}
```

#### Example - Iron Condor (4 Legs)

**Entry:**
```json
{
  "signal": {
    "strategy_id": "SPX_1-D_Opt",
    "instrument_type": "OPTION",
    "underlying": "SPY",
    "legs": [
      {
        "strike": 570.0,
        "expiry": "20251128",
        "right": "P",
        "action": "BUY",
        "quantity": 1
      },
      {
        "strike": 575.0,
        "expiry": "20251128",
        "right": "P",
        "action": "SELL",
        "quantity": 1
      },
      {
        "strike": 585.0,
        "expiry": "20251128",
        "right": "C",
        "action": "SELL",
        "quantity": 1
      },
      {
        "strike": 590.0,
        "expiry": "20251128",
        "right": "C",
        "action": "BUY",
        "quantity": 1
      }
    ],
    "direction": "LONG",
    "action": "BUY",
    "order_type": "MARKET",
    "price": 1.50,
    "quantity": 1,
    "signal_type": "ENTRY",
    "account": "DU1234567"
  }
}
```

**Exit (Reverse All Actions):**
```json
{
  "signal": {
    "strategy_id": "SPX_1-D_Opt",
    "instrument_type": "OPTION",
    "underlying": "SPY",
    "legs": [
      {
        "strike": 570.0,
        "expiry": "20251128",
        "right": "P",
        "action": "SELL",
        "quantity": 1
      },
      {
        "strike": 575.0,
        "expiry": "20251128",
        "right": "P",
        "action": "BUY",
        "quantity": 1
      },
      {
        "strike": 585.0,
        "expiry": "20251128",
        "right": "C",
        "action": "BUY",
        "quantity": 1
      },
      {
        "strike": 590.0,
        "expiry": "20251128",
        "right": "C",
        "action": "SELL",
        "quantity": 1
      }
    ],
    "direction": "LONG",
    "action": "SELL",
    "order_type": "MARKET",
    "price": 1.25,
    "quantity": 1,
    "signal_type": "EXIT",
    "account": "DU1234567"
  }
}
```

#### Example - Straddle (2 Legs - Call + Put)

**Entry:**
```json
{
  "signal": {
    "strategy_id": "SPY_Vol",
    "instrument_type": "OPTION",
    "underlying": "SPY",
    "legs": [
      {
        "strike": 580.0,
        "expiry": "20251128",
        "right": "C",
        "action": "BUY",
        "quantity": 10
      },
      {
        "strike": 580.0,
        "expiry": "20251128",
        "right": "P",
        "action": "BUY",
        "quantity": 10
      }
    ],
    "direction": "LONG",
    "action": "BUY",
    "order_type": "MARKET",
    "price": 12.50,
    "quantity": 10,
    "signal_type": "ENTRY",
    "account": "DU1234567"
  }
}
```

#### Example - Covered Call (Stock + Short Call)

**Entry:**
```json
{
  "signal": {
    "strategy_id": "SPY_Income",
    "instrument_type": "OPTION",
    "underlying": "SPY",
    "legs": [
      {
        "strike": 585.0,
        "expiry": "20251128",
        "right": "C",
        "action": "SELL",
        "quantity": 1
      }
    ],
    "direction": "LONG",
    "action": "SELL",
    "order_type": "MARKET",
    "price": 2.50,
    "quantity": 1,
    "signal_type": "ENTRY",
    "account": "DU1234567",
    "stop_loss": 0,
    "take_profit": 0
  }
}
```

**Note:** For covered calls, send a separate STOCK signal for the underlying position.

---

## Signal Type Field

The `signal_type` field helps the system understand the intent of your signal. It's optional but recommended.

**Supported Values:**
- `ENTRY` - Opening a new position
- `EXIT` - Closing an entire position
- `SCALE_IN` - Adding to an existing position (same direction)
- `SCALE_OUT` - Reducing an existing position (opposite action)

**Inference Rules (if signal_type not provided):**
- If no existing position → `ENTRY`
- If existing position and same direction → `SCALE_IN`
- If existing position and opposite action → `EXIT` or `SCALE_OUT`

---

## Order Types

**MARKET** - Execute immediately at current market price
```json
{
  "order_type": "MARKET",
  "price": 575.25  // Reference price only
}
```

**LIMIT** - Execute only at specified price or better
```json
{
  "order_type": "LIMIT",
  "price": 575.00  // Limit price
}
```

---

## Error Handling

### Common Validation Errors

**1. Missing `instrument_type`:**
```
Error: "REJECTED: Missing required field 'instrument_type'. Must be STOCK, OPTION, FOREX, or FUTURE"
```

**2. Invalid `instrument_type`:**
```
Error: "REJECTED: Invalid instrument_type 'STOCKS'. Must be STOCK, OPTION, FOREX, or FUTURE"
```

**3. Missing required fields for OPTION:**
```
Error: "REJECTED: OPTION type requires 'legs' field as list"
Error: "REJECTED: OPTION type requires 'underlying' field"
Error: "REJECTED: Option leg 1 missing required fields: ['strike', 'expiry', 'right']"
```

**4. Missing required fields for FOREX:**
```
Error: "REJECTED: FOREX instrument must be 6-character currency pair (e.g. EURUSD), got: EUR"
```

**5. Missing required fields for FUTURE:**
```
Error: "REJECTED: FUTURE type requires 'expiry' field (YYYYMMDD format)"
```

---

## Testing Your Signals

### Use the Test Script

The `test_multiasset_execution.py` script provides examples for testing:

```bash
python test_multiasset_execution.py
```

### Use the Comprehensive Tester

To test all patterns across all asset types:

```bash
python comprehensive_signal_tester.py
```

### Manual Testing with cURL

```bash
curl -X POST https://staging.mathematricks.fund/api/signals \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2025-10-28T12:00:00.000000+00:00",
    "signalID": "TEST_20251028_120000_001",
    "signal_sent_EPOCH": 1730116800,
    "strategy_name": "TEST",
    "signal": {
      "strategy_id": "TEST",
      "instrument_type": "STOCK",
      "instrument": "SPY",
      "direction": "LONG",
      "action": "BUY",
      "order_type": "MARKET",
      "price": 575.25,
      "quantity": 10,
      "signal_type": "ENTRY",
      "account": "DU1234567"
    },
    "environment": "staging",
    "passphrase": "yahoo123"
  }'
```

---

## Best Practices

1. **Always include `instrument_type`** - This is mandatory for the system to route your signal correctly

2. **Use descriptive `strategy_id`** - This helps with tracking and debugging

3. **Include `signal_type`** - Helps the system understand your intent (ENTRY/EXIT/SCALE_IN/SCALE_OUT)

4. **Validate strikes and expiries** - Ensure option strikes are near current market price and expiries are in the future

5. **Use active futures contracts** - Don't send expired contract months

6. **Test in staging first** - Always test new signal formats in staging before production

7. **Handle rejections gracefully** - Check logs for rejection reasons and adjust your signal format

8. **Keep signals simple** - Don't include unnecessary fields; the system will use defaults

---

## Support

For questions or issues:
- Check logs: `tail -f logs/signal_processing.log`
- Review execution: `tail -f logs/execution_service.log`
- Contact: [your support contact]

---

## Version History

- **v2.0.0** (2025-10-28) - Added multi-asset support (STOCK, OPTION, FOREX, FUTURE)
- **v1.0.0** (2025-10-27) - Initial release (stocks only)
