# Portfolio Builder Service

## Overview

The Portfolio Builder Service manages strategy configurations, portfolio optimization research, and strategy performance analysis. It provides tools for backtesting strategies, generating optimal portfolio allocations, and creating performance reports.

## Location

`/services/portfolio_builder/`

## Key Responsibilities

1. Strategy management (CRUD operations)
2. Portfolio optimization using multiple algorithms
3. Strategy backtesting and performance analysis
4. Current allocation management
5. Performance tearsheet generation
6. Strategy weight calculation
7. Research and analytics tools

## Main Files

### main.py
- FastAPI service entry point
- REST API endpoints
- Strategy management
- Portfolio operations

### algorithms/
Folder containing portfolio optimization algorithms:
- `max_cagr/strategy.py` - Maximize CAGR
- `max_sharpe/strategy.py` - Maximize Sharpe ratio
- `max_cagr_v2/strategy.py` - Enhanced CAGR
- `max_hybrid/strategy.py` - Hybrid optimization

### research/
Research and analysis tools:
- `backtest_engine.py` - Strategy backtesting
- `construct_portfolio.py` - Portfolio construction
- `tearsheet_generator.py` - Performance reports

## REST API Endpoints

**Port:** 8003

### Strategy Management

#### Create Strategy
```
POST /api/strategies
Content-Type: application/json

{
  "strategy_name": "SPX 1-Day Options",
  "developer_name": "John Doe",
  "developer_email": "john@example.com",
  "asset_classes": ["STOCK", "OPTION"],
  "description": "Daily SPX options strategy",
  "risk_level": "MEDIUM",
  "expected_sharpe": 1.8,
  "max_drawdown": 15.0,
  "strategy_data_file": "path/to/historical_data.xlsx"
}

Response: 201 Created
{
  "strategy_id": "strat_abc123",
  "strategy_name": "SPX 1-Day Options",
  "status": "ACTIVE"
}
```

#### List Strategies
```
GET /api/strategies?status=ACTIVE&developer_name=John Doe

Response: 200 OK
{
  "strategies": [
    {
      "strategy_id": "strat_abc123",
      "strategy_name": "SPX 1-Day Options",
      "developer_name": "John Doe",
      "asset_classes": ["STOCK", "OPTION"],
      "status": "ACTIVE",
      "created_at": "2024-11-01T00:00:00Z"
    }
  ]
}
```

#### Get Strategy Details
```
GET /api/strategies/{strategy_id}

Response: 200 OK
{
  "strategy_id": "strat_abc123",
  "strategy_name": "SPX 1-Day Options",
  "developer_name": "John Doe",
  "developer_email": "john@example.com",
  "asset_classes": ["STOCK", "OPTION"],
  "description": "Daily SPX options strategy",
  "performance_metrics": {
    "sharpe_ratio": 1.8,
    "cagr": 25.5,
    "max_drawdown": 12.3,
    "win_rate": 65.0
  },
  "status": "ACTIVE"
}
```

#### Update Strategy
```
PUT /api/strategies/{strategy_id}
Content-Type: application/json

{
  "description": "Updated description",
  "risk_level": "HIGH",
  "status": "PAUSED"
}

Response: 200 OK
{
  "message": "Strategy updated successfully",
  "strategy_id": "strat_abc123"
}
```

#### Delete Strategy
```
DELETE /api/strategies/{strategy_id}

Response: 200 OK
{
  "message": "Strategy deleted successfully",
  "strategy_id": "strat_abc123"
}
```

### Portfolio Operations

#### Run Portfolio Optimization
```
GET /api/portfolio/optimize?algorithm=max_sharpe&risk_level=MEDIUM

Response: 200 OK
{
  "optimization_id": "opt_xyz789",
  "algorithm": "max_sharpe",
  "optimal_weights": {
    "SPX 1-Day Options": 0.25,
    "Gold Futures": 0.15,
    "BTC Swing": 0.10,
    "Forex Pairs": 0.20,
    "Leslie Strategy": 0.30
  },
  "expected_return": 28.5,
  "expected_volatility": 12.3,
  "sharpe_ratio": 2.31,
  "max_drawdown": 15.2
}
```

#### Get Current Allocation
```
GET /api/portfolio/current-allocation

Response: 200 OK
{
  "allocation_id": "alloc_current",
  "allocation_date": "2024-11-20T00:00:00Z",
  "strategy_weights": {
    "SPX 1-Day Options": 0.25,
    "Gold Futures": 0.15,
    "BTC Swing": 0.10,
    "Forex Pairs": 0.20,
    "Leslie Strategy": 0.30
  },
  "status": "ACTIVE",
  "last_updated": "2024-11-20T10:00:00Z"
}
```

#### Approve New Allocation
```
POST /api/portfolio/allocations
Content-Type: application/json

{
  "strategy_weights": {
    "SPX 1-Day Options": 0.30,
    "Gold Futures": 0.20,
    "BTC Swing": 0.15,
    "Forex Pairs": 0.15,
    "Leslie Strategy": 0.20
  },
  "approved_by": "portfolio_manager",
  "notes": "Increased allocation to SPX strategy based on recent performance"
}

Response: 201 Created
{
  "allocation_id": "alloc_abc456",
  "status": "ACTIVE",
  "effective_date": "2024-11-24T00:00:00Z"
}
```

### Research Operations

#### Run Backtest
```
GET /api/research/backtest?strategy_id=strat_abc123&start_date=2023-01-01&end_date=2024-01-01

Response: 200 OK
{
  "backtest_id": "bt_def789",
  "strategy_id": "strat_abc123",
  "period": "2023-01-01 to 2024-01-01",
  "metrics": {
    "total_return": 35.5,
    "cagr": 35.5,
    "sharpe_ratio": 1.85,
    "sortino_ratio": 2.34,
    "max_drawdown": 12.3,
    "win_rate": 67.0,
    "total_trades": 250,
    "avg_win": 2.5,
    "avg_loss": -1.2
  },
  "equity_curve": [ ... ],
  "drawdown_curve": [ ... ]
}
```

#### Generate Tearsheet
```
GET /api/research/tearsheet?strategy_id=strat_abc123&format=html

Response: 200 OK
{
  "tearsheet_url": "/static/tearsheets/strat_abc123.html",
  "generated_at": "2024-11-24T10:30:00Z",
  "format": "html"
}
```

## MongoDB Collections

### strategies
Strategy definitions and metadata:
```json
{
  "_id": "strat_abc123",
  "strategy_id": "strat_abc123",
  "strategy_name": "SPX 1-Day Options",
  "developer_name": "John Doe",
  "developer_email": "john@example.com",
  "asset_classes": ["STOCK", "OPTION"],
  "description": "Daily SPX options strategy targeting 0-DTE opportunities",
  "risk_level": "MEDIUM",
  "performance_metrics": {
    "sharpe_ratio": 1.8,
    "cagr": 25.5,
    "max_drawdown": 12.3,
    "win_rate": 65.0,
    "total_trades": 1250,
    "avg_trade_duration_hours": 8
  },
  "strategy_data_file": "data/strategies/spx_1day_options.xlsx",
  "status": "ACTIVE",
  "created_at": "2024-11-01T00:00:00Z",
  "updated_at": "2024-11-20T15:30:00Z"
}
```

### current_allocation
Active portfolio allocation:
```json
{
  "_id": "alloc_current",
  "allocation_id": "alloc_current",
  "allocation_date": "2024-11-20T00:00:00Z",
  "strategy_weights": {
    "SPX 1-Day Options": 0.25,
    "Gold Futures": 0.15,
    "BTC Swing": 0.10,
    "Forex Pairs": 0.20,
    "Leslie Strategy": 0.30
  },
  "optimization_algorithm": "max_sharpe",
  "expected_metrics": {
    "expected_return": 28.5,
    "expected_volatility": 12.3,
    "sharpe_ratio": 2.31
  },
  "approved_by": "portfolio_manager",
  "status": "ACTIVE",
  "created_at": "2024-11-20T10:00:00Z"
}
```

### portfolio_tests
Backtest and optimization results:
```json
{
  "_id": "bt_def789",
  "backtest_id": "bt_def789",
  "strategy_id": "strat_abc123",
  "test_type": "BACKTEST",
  "start_date": "2023-01-01",
  "end_date": "2024-01-01",
  "metrics": {
    "total_return": 35.5,
    "cagr": 35.5,
    "sharpe_ratio": 1.85,
    "max_drawdown": 12.3
  },
  "equity_curve": [ ... ],
  "created_at": "2024-11-24T10:30:00Z"
}
```

### signal_store (Read-only)
Portfolio Builder reads signal data for strategy analysis but does not write to this collection.

## Portfolio Optimization Algorithms

### Max CAGR Algorithm
Location: `algorithms/max_cagr/strategy.py`

**Objective:** Maximize compound annual growth rate

**Method:**
- Uses historical returns
- Optimizes for long-term growth
- Ignores short-term volatility
- Best for aggressive portfolios

**Use Case:** When absolute returns matter more than risk-adjusted returns

### Max Sharpe Algorithm
Location: `algorithms/max_sharpe/strategy.py`

**Objective:** Maximize risk-adjusted returns (Sharpe ratio)

**Method:**
- Balances return vs volatility
- Uses mean-variance optimization
- Penalizes high volatility
- Best for balanced portfolios

**Use Case:** Standard approach for most portfolios

### Max CAGR v2 Algorithm
Location: `algorithms/max_cagr_v2/strategy.py`

**Objective:** Enhanced CAGR with drawdown constraints

**Method:**
- Maximizes CAGR
- Adds max drawdown constraint
- Improves risk management vs v1
- Better tail risk handling

**Use Case:** When growth is priority but drawdown control needed

### Max Hybrid Algorithm
Location: `algorithms/max_hybrid/strategy.py`

**Objective:** Combined CAGR and Sharpe optimization

**Method:**
- Multi-objective optimization
- Weighted combination of CAGR and Sharpe
- Configurable weights
- Best of both worlds

**Use Case:** When both growth and stability are important

## Backtesting Engine

Location: `research/backtest_engine.py`

### Features
- Historical simulation of strategy performance
- Transaction cost modeling
- Slippage simulation
- Multiple asset class support
- Equity curve generation
- Drawdown analysis

### Usage
```python
from research.backtest_engine import BacktestEngine

engine = BacktestEngine()
results = engine.run_backtest(
    strategy_data="path/to/data.xlsx",
    start_date="2023-01-01",
    end_date="2024-01-01",
    initial_capital=100000
)

print(results["sharpe_ratio"])
```

## Tearsheet Generator

Location: `research/tearsheet_generator.py`

### Features
- Comprehensive performance reports
- Visual charts (equity curve, drawdown, returns distribution)
- Key metrics table
- Risk analysis
- Trade statistics
- HTML and PDF output formats

### Generated Metrics
- Total Return
- CAGR
- Sharpe Ratio
- Sortino Ratio
- Max Drawdown
- Calmar Ratio
- Win Rate
- Profit Factor
- Average Win/Loss
- Trade count statistics

## Configuration

### Environment Variables
```bash
# MongoDB connection
MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0

# Service port
PORTFOLIO_BUILDER_PORT=8003

# Data paths
STRATEGY_DATA_DIR=/path/to/strategy_data
RESEARCH_OUTPUT_DIR=/path/to/research_output
```

## Error Handling

1. **Strategy Not Found**
   - Returns 404 with error message
   - Logs query details

2. **Invalid Optimization Parameters**
   - Returns 400 with validation errors
   - Suggests valid parameter ranges

3. **Backtest Failures**
   - Returns 500 with error details
   - Logs full stack trace
   - Suggests data format fixes

4. **Allocation Conflicts**
   - Validates weights sum to 1.0
   - Checks strategy existence
   - Prevents duplicate allocations

## Logging

Logs to:
- Console (real-time output)
- `logs/portfolio_builder.log` (service-specific)

Log format:
```
|LEVEL|Message|Timestamp|file:filename.py:line No.LineNumber|
```

Example log entries:
```
|INFO|Portfolio Builder service started on port 8003|2024-11-24T10:00:00|main.py:25|
|INFO|Created strategy: SPX 1-Day Options|2024-11-24T10:05:00|main.py:120|
|INFO|Running optimization: max_sharpe|2024-11-24T10:10:00|main.py:250|
|INFO|Optimization complete. Sharpe: 2.31|2024-11-24T10:10:15|main.py:275|
```

## Dependencies

- **FastAPI/Uvicorn** - REST API framework
- **MongoDB** - Data storage
- **Pandas, NumPy** - Data analysis
- **SciPy** - Optimization algorithms
- **Matplotlib, Plotly** - Charting
- **QuantStats** - Performance analytics (optional)
- **Python packages**:
  - `fastapi>=0.121.0`
  - `uvicorn>=0.38.0`
  - `pymongo>=4.6.1`
  - `pandas>=2.3.3`
  - `numpy>=2.3.4`
  - `scipy>=1.16.3`
  - `matplotlib>=3.8.0`

## Startup Command

```bash
# Via mvp_demo_start.py
python mvp_demo_start.py

# Manual startup
cd services/portfolio_builder
uvicorn main:app --host 0.0.0.0 --port 8003

# With reload for development
uvicorn main:app --reload --port 8003
```

## Health Checks

Check service status:
```bash
# Via status script
python mvp_demo_status.py

# Direct API call
curl http://localhost:8003/health

# Check if port is listening
lsof -i :8003
```

View logs:
```bash
tail -f logs/portfolio_builder.log
```

## Usage Examples

### Create Strategy via API
```python
import requests

strategy = {
    "strategy_name": "SPX 1-Day Options",
    "developer_name": "John Doe",
    "developer_email": "john@example.com",
    "asset_classes": ["STOCK", "OPTION"],
    "description": "Daily SPX options strategy",
    "risk_level": "MEDIUM"
}

response = requests.post(
    "http://localhost:8003/api/strategies",
    json=strategy
)

print(response.json())
```

### Run Optimization
```python
import requests

response = requests.get(
    "http://localhost:8003/api/portfolio/optimize",
    params={"algorithm": "max_sharpe", "risk_level": "MEDIUM"}
)

optimal_weights = response.json()["optimal_weights"]
print(f"Optimal allocation: {optimal_weights}")
```

## Related Documentation

- [Cerebro Service](cerebro_service.md) - Uses allocation weights for position sizing
- [Dashboard Creator](dashboard_creator.md) - Displays strategy performance
- [Signal Ingestion](signal_ingestion.md) - Receives signals from strategies

## Common Issues

### Strategy Data Import Failures
- Verify Excel file format matches template
- Check for missing columns
- Ensure dates are properly formatted
- Look for NaN values in critical columns

### Optimization Not Converging
- Check historical data quality
- Ensure sufficient data points (min 252 for annual)
- Try different algorithm
- Adjust constraints

### Allocation Weights Don't Sum to 1.0
- API validates and returns 400 error
- Manually adjust weights
- Use optimization result directly

### Backtest Results Unrealistic
- Check for survivorship bias in data
- Verify transaction costs are included
- Ensure slippage is modeled
- Review trade frequency

## Research Workflow

1. **Load Strategy Data**
   - Import historical signals and returns
   - Store in `strategies` collection

2. **Run Backtest**
   - Simulate historical performance
   - Generate metrics and charts

3. **Optimize Portfolio**
   - Run optimization algorithm
   - Get optimal strategy weights

4. **Review Results**
   - Generate tearsheet
   - Analyze risk metrics
   - Compare to benchmarks

5. **Approve Allocation**
   - Submit via API
   - Becomes active allocation
   - Cerebro uses for position sizing

6. **Monitor Performance**
   - Dashboard Creator tracks live results
   - Compare to backtest expectations
   - Adjust allocation as needed
