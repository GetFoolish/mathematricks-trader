# Portfolio Builder Service

## Overview

The Portfolio Builder Service handles strategy management, portfolio optimization, backtest processing, and research workflows. It provides APIs for strategy CRUD operations, backtest uploads, portfolio testing, and public strategy submissions.

**Main File:** `services/portfolio_builder/main.py`  
**Port:** 8003  
**Framework:** FastAPI

## Purpose

- **Strategy Management** - Create, read, update, delete strategy configurations
- **Backtest Processing** - Upload, validate, and merge backtest CSV data
- **Portfolio Optimization** - Test different portfolio allocation algorithms
- **Metrics Calculation** - Compute CAGR, Sharpe, drawdown, and other metrics
- **Public Submissions** - Handle community strategy submissions
- **Tearsheet Generation** - Create QuantStats performance reports
- **Allocation Approval** - Manage portfolio allocation lifecycle

## Architecture

### How It Works

```
Strategy CSV → Upload Handler → Backtest Processing → Portfolio Optimizer → Allocation Approval
                     ↓                                        ↓
              strategies collection                    portfolio_tests
              (with metrics)                           (with allocations)
```

### Key Components

1. **Backtest Upload Handler**
   - CSV parsing and validation
   - Returns normalization (daily, cumulative)
   - Synthetic column generation
   - Backtest hash calculation
   - Allocation invalidation on data changes

2. **Metrics Calculator**
   - CAGR, Sharpe ratio, Sortino ratio
   - Max drawdown, Calmar ratio
   - Win rate, profit factor
   - Correlation matrix

3. **Portfolio Optimization**
   - MaxCAGR, MaxSharpe, MaxHybrid algorithms
   - Constraint-based allocation
   - Risk-adjusted position sizing

4. **Tearsheet Generator**
   - QuantStats integration
   - HTML performance reports
   - Submission validation

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URI_LOCAL` | Local MongoDB URI (development) | - |
| `MONGODB_URI` | MongoDB URI (production) | Required |

### Directory Structure

```
services/portfolio_builder/
├── main.py                    # FastAPI app
├── backtest_upload_handler.py # CSV processing
├── metrics_calculator.py      # Performance metrics
├── requirements.txt
├── algorithms/                # Portfolio optimization
│   ├── base.py
│   ├── context.py
│   ├── max_cagr/
│   ├── max_sharpe/
│   └── max_hybrid/
├── research/                  # Research tools
│   ├── backtest_engine.py
│   ├── tearsheet_generator.py
│   └── outputs/              # Generated tearsheets
└── submissions_tearsheets/   # Public submission tearsheets
```

## MongoDB Collections

### `strategies`
Unified strategy collection with backtest data:
```javascript
{
  _id: ObjectId,
  strategy_id: "MaxCAGR_v2",
  name: "Max CAGR Strategy v2",
  asset_class: "STOCK",
  instruments: ["SPY", "QQQ", "IWM"],
  
  // Backtest data (embedded)
  backtest: {
    data_hash: "abc123...",
    returns: {
      daily: [0.001, -0.002, 0.003, ...],
      cumulative: [1.001, 0.999, 1.002, ...]
    },
    equity_curve: [100000, 100100, 100000, ...],
    dates: ["2020-01-01", "2020-01-02", ...],
    
    metrics: {
      cagr: 0.15,
      sharpe_ratio: 1.8,
      max_drawdown: -0.12,
      win_rate: 0.65,
      total_trades: 250,
      ...
    },
    
    uploaded_at: ISODate,
    uploaded_by: "admin"
  },
  
  // Strategy configuration
  config: {
    max_positions: 10,
    position_size_pct: 0.05,
    rebalance_frequency: "daily"
  },
  
  status: "active" | "paused" | "archived",
  created_at: ISODate,
  updated_at: ISODate
}
```

### `uploaded_strategies`
Public strategy submissions:
```javascript
{
  _id: ObjectId,
  submission_id: "sub_abc123",
  strategy_name: "Community Strategy XYZ",
  submitted_by: "trader@example.com",
  
  backtest_data: {
    returns: [...],
    equity_curve: [...],
    metrics: { ... }
  },
  
  status: "pending" | "approved" | "rejected",
  rejection_reason: "Insufficient backtest history",
  
  tearsheet_path: "submissions_tearsheets/sub_abc123.html",
  
  submitted_at: ISODate,
  reviewed_at: ISODate,
  reviewed_by: "admin"
}
```

### `portfolio_tests`
Portfolio optimization test results:
```javascript
{
  _id: ObjectId,
  test_id: "test_abc123",
  algorithm: "MaxHybrid",
  
  parameters: {
    cagr_weight: 0.4,
    sharpe_weight: 0.4,
    diversification_weight: 0.2
  },
  
  strategies: ["MaxCAGR_v2", "MeanReversion_v1"],
  
  allocations: {
    "MaxCAGR_v2": 0.60,
    "MeanReversion_v1": 0.40
  },
  
  portfolio_metrics: {
    cagr: 0.18,
    sharpe_ratio: 2.1,
    max_drawdown: -0.10
  },
  
  created_at: ISODate
}
```

### `portfolio_allocations`
Allocation tracking and invalidation:
```javascript
{
  _id: ObjectId,
  strategy_id: "MaxCAGR_v2",
  allocation_name: "Production_Q1_2026",
  data_hash: "abc123...",
  is_valid: true,
  
  allocations: {
    "MaxCAGR_v2": 0.30,
    "MeanReversion_v1": 0.20
  },
  
  created_at: ISODate,
  invalidated_at: ISODate
}
```

## API Endpoints

### Strategy Management

#### `GET /api/v1/strategies`
Get all strategies with backtest data.

**Response:**
```json
{
  "status": "success",
  "count": 5,
  "strategies": [
    {
      "strategy_id": "MaxCAGR_v2",
      "name": "Max CAGR Strategy v2",
      "backtest": {
        "metrics": {
          "cagr": 0.15,
          "sharpe_ratio": 1.8
        }
      }
    }
  ]
}
```

#### `GET /api/v1/strategies/{strategy_id}`
Get single strategy details.

#### `POST /api/v1/strategies`
Create new strategy.

**Request:**
```json
{
  "strategy_id": "NewStrategy_v1",
  "name": "New Strategy",
  "asset_class": "STOCK",
  "instruments": ["AAPL", "MSFT"]
}
```

#### `PUT /api/v1/strategies/{strategy_id}`
Update strategy configuration.

#### `DELETE /api/v1/strategies/{strategy_id}`
Delete strategy (soft delete - sets status to "archived").

### Backtest Management

#### `POST /api/v1/strategies/{strategy_id}/upload-backtest`
Upload backtest CSV file.

**Request:** Multipart form data
- `file`: CSV file with columns: `Date`, `Returns` (or `Equity`)

**Response:**
```json
{
  "status": "success",
  "strategy_id": "MaxCAGR_v2",
  "metrics": {
    "cagr": 0.15,
    "sharpe_ratio": 1.8,
    "max_drawdown": -0.12
  },
  "invalidated_allocations": 2
}
```

#### `POST /api/v1/strategies/{strategy_id}/sync-backtest`
Sync backtest from external source (placeholder for future webhook integration).

#### `POST /api/v1/strategies/{strategy_id}/refresh-cache`
Recalculate metrics from existing backtest data.

### Portfolio Allocation

#### `GET /api/v1/allocations/current`
Get current approved allocations.

**Response:**
```json
{
  "allocation_name": "Production_Q1_2026",
  "strategies": {
    "MaxCAGR_v2": {
      "allocation": 0.30,
      "metrics": {
        "cagr": 0.15,
        "sharpe_ratio": 1.8
      }
    }
  },
  "portfolio_metrics": {
    "cagr": 0.14,
    "sharpe_ratio": 1.9
  }
}
```

#### `GET /api/v1/allocations/outdated`
Get allocations invalidated by backtest changes.

#### `POST /api/v1/allocations/approve`
Approve portfolio allocation.

**Request:**
```json
{
  "allocation_name": "Production_Q1_2026",
  "allocations": {
    "MaxCAGR_v2": 0.60,
    "MeanReversion_v1": 0.40
  }
}
```

### Portfolio Testing

#### `GET /api/v1/portfolio-tests`
Get all portfolio optimization tests.

#### `DELETE /api/v1/portfolio-tests/{test_id}`
Delete portfolio test result.

### Public Strategy Submissions

#### `POST /api/v1/public/submit-strategy`
Submit strategy for review (community feature).

**Request:** Multipart form data
- `strategy_name`: Strategy name
- `submitted_by`: Email address
- `file`: Backtest CSV file

**Response:**
```json
{
  "status": "success",
  "submission_id": "sub_abc123",
  "message": "Strategy submitted for review"
}
```

#### `GET /api/v1/public/submission/{submission_id}`
Get submission details.

#### `GET /api/v1/public/submission/{submission_id}/tearsheet`
Download tearsheet HTML file.

### Admin Endpoints

#### `GET /api/v1/admin/submissions`
Get all pending submissions.

**Query Parameters:**
- `status`: Filter by status (pending/approved/rejected)

#### `POST /api/v1/admin/submissions/{submission_id}/approve`
Approve submission and convert to strategy.

**Request:**
```json
{
  "strategy_id": "Community_Strategy_1",
  "allocation_pct": 0.05
}
```

#### `POST /api/v1/admin/submissions/{submission_id}/reject`
Reject submission with reason.

**Request:**
```json
{
  "reason": "Insufficient backtest history (min 2 years required)"
}
```

#### `DELETE /api/v1/admin/submissions/{submission_id}`
Delete submission permanently.

## Key Functions

### Backtest Processing

#### `parse_csv(file_content)`
Parse CSV file to DataFrame.

**Supported Formats:**
- Date, Returns (daily returns)
- Date, Equity (equity curve)
- Date, Close (price data)

#### `normalize_returns(df)`
Normalize returns to daily and cumulative.

**Returns:**
```python
{
    'daily_returns': [0.001, -0.002, ...],
    'cumulative_returns': [1.001, 0.999, ...],
    'equity_curve': [100000, 100100, ...],
    'dates': ['2020-01-01', '2020-01-02', ...]
}
```

#### `calculate_backtest_hash(backtest_data)`
Generate hash of backtest data for change detection.

**Algorithm:** SHA256 of returns array

#### `invalidate_allocations_for_strategy(strategy_id, db)`
Mark all allocations invalid when backtest changes.

**Side Effects:** Updates `portfolio_allocations.is_valid = False`

### Metrics Calculation

#### `calculate_all_metrics(returns, equity_curve)`
Compute comprehensive performance metrics.

**Returns:**
```python
{
    'cagr': 0.15,
    'sharpe_ratio': 1.8,
    'sortino_ratio': 2.1,
    'max_drawdown': -0.12,
    'calmar_ratio': 1.25,
    'win_rate': 0.65,
    'profit_factor': 2.3,
    'total_trades': 250,
    'avg_win': 0.015,
    'avg_loss': -0.008
}
```

### Portfolio Optimization

#### `construct_portfolio(strategies, algorithm, parameters)`
Run portfolio optimization algorithm.

**Algorithms:**
- `MaxCAGR`: Maximize CAGR
- `MaxSharpe`: Maximize Sharpe ratio
- `MaxHybrid`: Balance multiple objectives

**Returns:**
```python
{
    'allocations': {
        'MaxCAGR_v2': 0.60,
        'MeanReversion_v1': 0.40
    },
    'portfolio_metrics': {
        'cagr': 0.16,
        'sharpe_ratio': 2.0
    }
}
```

## Example Usage

### Uploading a Backtest

```python
import requests

files = {'file': open('backtest.csv', 'rb')}
response = requests.post(
    'http://localhost:8003/api/v1/strategies/MaxCAGR_v2/upload-backtest',
    files=files
)

result = response.json()
print(f"CAGR: {result['metrics']['cagr']:.2%}")
print(f"Sharpe: {result['metrics']['sharpe_ratio']:.2f}")
print(f"Invalidated allocations: {result['invalidated_allocations']}")
```

### Approving an Allocation

```python
import requests

allocation_data = {
    "allocation_name": "Production_Q1_2026",
    "allocations": {
        "MaxCAGR_v2": 0.60,
        "MeanReversion_v1": 0.40
    }
}

response = requests.post(
    'http://localhost:8003/api/v1/allocations/approve',
    json=allocation_data
)

print(response.json()['message'])
```

### Submitting a Strategy (Public)

```python
import requests

files = {'file': open('my_strategy_backtest.csv', 'rb')}
data = {
    'strategy_name': 'My Awesome Strategy',
    'submitted_by': 'trader@example.com'
}

response = requests.post(
    'http://localhost:8003/api/v1/public/submit-strategy',
    files=files,
    data=data
)

result = response.json()
print(f"Submission ID: {result['submission_id']}")
```

## Troubleshooting

### Problem: CSV upload fails with "Invalid format"
**Cause:** Missing required columns
**Solution:**
- Ensure CSV has `Date` column
- Must have one of: `Returns`, `Equity`, or `Close`
- Date format should be YYYY-MM-DD or parseable by pandas

### Problem: Metrics calculation returns NaN
**Cause:** Insufficient data or invalid returns
**Debug:**
- Check returns array length (min 252 trading days recommended)
- Verify no NaN values in returns
- Check for division by zero (zero volatility)

### Problem: Allocation approval fails
**Cause:** Allocations don't sum to 1.0
**Solution:**
- Ensure allocations sum to exactly 1.0 (or 100%)
- Use: `{"MaxCAGR_v2": 0.6, "MeanReversion_v1": 0.4}`
- Not: `{"MaxCAGR_v2": 60, "MeanReversion_v1": 40}`

### Problem: Tearsheet generation hangs
**Cause:** Large backtest data or QuantStats timeout
**Solutions:**
- Limit backtest to 5 years max
- Reduce data resolution (daily only, no intraday)
- Check Python subprocess timeout (default 60s)

### Problem: "Outdated allocation" detected but backtest unchanged
**Cause:** Hash mismatch due to floating point precision
**Solution:**
- Recalculate hash: `POST /api/v1/strategies/{id}/refresh-cache`
- Check for data corruption in MongoDB
- Re-upload backtest CSV

## Performance Notes

- **CSV Upload:** ~500ms for 2 years of daily data
- **Metrics Calculation:** ~100-200ms for standard metrics
- **Tearsheet Generation:** ~5-10 seconds (QuantStats rendering)
- **Portfolio Optimization:** ~1-5 seconds (depends on number of strategies)

## Dependencies

- `fastapi` - Web framework
- `pandas` - Data processing
- `numpy` - Numerical computations
- `quantstats` - Performance metrics and tearsheets
- `pymongo` - MongoDB driver
- `python-multipart` - File upload support

## Related Services

- **Cerebro Service** - Uses strategy configurations for signal processing
- **Dashboard Creator** - Displays strategy metrics
- **Signal Ingestion** - References strategy IDs

## Data Validation

### Backtest CSV Requirements
- **Minimum rows:** 252 (1 year of trading days)
- **Date column:** Must be parseable
- **Returns:** Must be numeric, not NaN
- **No gaps:** Missing dates interpolated or filled

### Allocation Validation
- **Sum check:** Must equal 1.0 (±0.01 tolerance)
- **Range check:** Each allocation 0.0 to 1.0
- **Strategy check:** All strategies must exist in database

### Submission Validation
- **Backtest quality:** Min 2 years, Sharpe > 0.5
- **Email format:** Valid email address required
- **File size:** Max 10MB
- **Tearsheet:** Must generate successfully

## Logging

### Files
- `logs/portfolio_builder.log` - Service logs

### Key Log Events
- Strategy CRUD operations
- Backtest uploads and processing
- Allocation approvals
- Submission reviews
- Metric calculations
- Portfolio optimizations

## Safety Features

### Allocation Invalidation
When backtest data changes:
1. Calculate new data hash
2. Compare with previous hash
3. If different, invalidate all allocations referencing this strategy
4. Admins must re-approve allocations

### Submission Review
All public submissions require admin approval:
1. Automated metrics validation
2. Tearsheet generation
3. Manual review
4. Approval or rejection with reason

### Data Integrity
- Atomic updates to MongoDB
- Backtest hash verification
- Allocation sum validation
- Strategy existence checks before allocation
