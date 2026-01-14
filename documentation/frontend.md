# Frontend Admin Dashboard

The Frontend Admin Dashboard is a React-based web application that provides real-time monitoring and management of the Mathematricks Trading System.

## Table of Contents
- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Key Features](#key-features)
- [Pages & Components](#pages--components)
- [API Integration](#api-integration)
- [Usage](#usage)
- [Development](#development)

---

## Overview

### Purpose
- **Real-time Monitoring**: Portfolio metrics, positions, P&L
- **Trading Activity**: View signals, orders, executions
- **Portfolio Management**: Manage strategies, funds, allocations
- **Admin Tools**: Configure accounts, approve allocations

### Technology Stack
- **React 18** + **TypeScript**
- **Vite** (build tool)
- **TailwindCSS** (styling)
- **React Router** (routing)
- **Recharts** (visualizations)

### Location
```
frontend-admin/
├── src/                        # React source code
│   ├── pages/                  # Page components
│   │   ├── Login.tsx
│   │   ├── Dashboard.tsx
│   │   ├── Activity.tsx
│   │   ├── Allocations.tsx
│   │   ├── Strategies.tsx
│   │   └── FundSetup.tsx
│   ├── components/             # Reusable components
│   ├── services/
│   │   └── api.ts              # API client
│   └── App.tsx                 # Root component
├── server/                     # Express backend
│   └── api.js                  # MongoDB queries
└── package.json
```

---

## Tech Stack

### Frontend (React)
- **React 18**: Component framework
- **TypeScript**: Type safety
- **Vite**: Fast build tool with HMR
- **TailwindCSS**: Utility-first CSS framework
- **React Router**: Client-side routing
- **Recharts**: Chart library for visualizations

### Backend (Express)
- **Express.js**: REST API server
- **MongoDB**: Direct MongoDB queries (no ORM)
- **CORS**: Cross-origin resource sharing
- **Port 8000**: API server

---

## Key Features

### 1. Real-Time Data
- **Auto-refresh**: Pages poll data every 5-30 seconds
- **Live Updates**: Portfolio metrics, positions, P&L
- **Order Status**: Real-time order and execution tracking

### 2. Portfolio Overview (Dashboard Page)
- **Fund Equity**: Total equity across all accounts
- **Strategy Performance**: Individual strategy P&L
- **Asset Allocation**: Pie charts showing allocation breakdown
- **Correlation Matrix**: Strategy correlation heatmap
- **Recent Activity**: Latest signals and orders

### 3. Trading Activity (Activity Page)
**3 Tabs**:
- **Signal Legs**: All signal legs with raw/cerebro quantities
- **Orders & Executions**: Order status and fill details with P&L
- **Trading Signals**: Aggregated view with position progress bars

**Features**:
- CSV export for all tabs
- Filters by environment (staging/production)
- Sortable columns
- Position progress indicators
- P&L calculations

### 4. Portfolio Allocations (Allocations Page)
- **View Allocations**: Current and historical allocations
- **Approve Allocations**: Activate new allocation recommendations
- **Correlation Matrix**: Interactive heatmap
- **Allocation Summary**: Percentage breakdown by strategy

### 5. Strategy Management (Strategies Page)
- **CRUD Operations**: Create, read, update, delete strategies
- **Account Assignment**: Assign strategies to trading accounts
- **Status Management**: Enable/disable strategies
- **Backtest Data**: View strategy performance metrics

### 6. Fund Setup (FundSetup Page)
- **Fund Configuration**: Create and manage funds
- **Account Assignment**: Assign accounts to funds
- **Asset Class Mapping**: Configure supported asset classes per account
- **Equity Tracking**: Monitor fund-level equity

---

## Pages & Components

### 1. Login Page ([Login.tsx](../frontend-admin/src/pages/Login.tsx))
**Purpose**: Authentication (currently mock JWT for MVP)

**Features**:
- Email/password login form
- JWT token generation
- Protected route redirection
- Remember me functionality

**Usage**:
```typescript
// Default credentials (mock)
Email: admin@mathematricks.com
Password: admin123
```

### 2. Dashboard Page ([Dashboard.tsx](../frontend-admin/src/pages/Dashboard.tsx))
**Purpose**: High-level portfolio overview

**Metrics Displayed**:
- Total fund equity
- Realized P&L
- Unrealized P&L
- Open positions count
- Strategy allocation chart
- Asset class distribution
- Correlation heatmap
- Recent trading activity

**API Endpoints Used**:
```typescript
GET /api/dashboard/metrics     // Portfolio metrics
GET /api/strategies            // Strategy list
GET /api/signals/recent        // Recent signals
GET /api/correlations          // Correlation matrix
```

### 3. Activity Page ([Activity.tsx](../frontend-admin/src/pages/Activity.tsx))
**Purpose**: Detailed trading activity monitoring

**Tab 1: Signal Legs**
- Shows all signal legs (ENTRY, EXIT, SCALE)
- Columns: Strategy, Instrument, Type, Raw Qty, Cerebro Qty, Status, Time
- CSV export button

**Tab 2: Orders & Executions**
- Shows orders and execution details
- Columns: Order ID, Account, Instrument, Type, Qty, Price, Status, P&L, Time
- Execution status badges
- CSV export button

**Tab 3: Trading Signals**
- Aggregated signal view
- Columns: Signal ID, Strategy, Instrument, Status, Position Progress, Entry/Exit Qty, P&L, Time
- Position progress bars (visual fill indicator)
- Sorting: PENDING > OPEN > PARTIAL > CLOSED, then by entry time
- CSV export button

**API Endpoints**:
```typescript
GET /api/signals               // All signals with legs
GET /api/orders                // All orders
GET /api/executions            // All executions
```

### 4. Allocations Page ([Allocations.tsx](../frontend-admin/src/pages/Allocations.tsx))
**Purpose**: Portfolio allocation management and testing

**Features**:
- **Part 1**: View current fund allocations (approved portfolio tests)
- **Part 2**: Research Lab - Run and test portfolio allocations
- **Part 3**: Approve portfolio tests for funds

**Workflow**:
1. User runs portfolio test in Research Lab (Part 2) → creates test in `portfolio_tests` collection
2. User loads test and selects fund in Part 2
3. User clicks "Approve" → updates `funds.portfolio_test_id` to reference the test
4. Part 1 displays approved allocation from `funds` → `portfolio_tests`
5. Cerebro uses approved test allocations for position sizing

**Single Source of Truth**:
- Allocations stored in `portfolio_tests` collection
- Funds reference tests via `portfolio_test_id` field
- No duplicate data in separate allocation collections

**API Endpoints**:
```typescript
GET /api/v1/allocations/current        // Get current fund allocations (funds → portfolio_tests)
POST /api/v1/allocations/approve       // Approve test for fund (portfolio_test_id, fund_id)
GET /api/v1/portfolio-tests            // Get all portfolio tests
POST /api/v1/portfolio-tests/run       // Run new portfolio test
```

### 5. Strategies Page ([Strategies.tsx](../frontend-admin/src/pages/Strategies.tsx))
**Purpose**: Strategy CRUD and configuration

**Features**:
- Create new strategies
- Edit strategy details (name, asset class, accounts)
- Enable/disable strategies
- View backtest metrics (Sharpe, CAGR, volatility)
- Delete strategies

**Form Fields**:
- Strategy Name
- Asset Class (EQUITY, FUTURE, FOREX, OPTION, CRYPTO)
- Assigned Accounts (multi-select)
- Trading Mode (LIVE, PAPER)
- Status (ACTIVE, INACTIVE)

**API Endpoints**:
```typescript
GET /api/strategies            // All strategies
POST /api/strategies           // Create strategy
PUT /api/strategies/:id        // Update strategy
DELETE /api/strategies/:id     // Delete strategy
```

### 6. Fund Setup Page ([FundSetup.tsx](../frontend-admin/src/pages/FundSetup.tsx))
**Purpose**: Fund and account configuration

**Features**:
- Create funds
- Assign accounts to funds
- Configure asset class support per account
- View fund equity aggregation

**Form Fields**:
- Fund Name
- Assigned Accounts
- Initial Equity
- Status

**API Endpoints**:
```typescript
GET /api/funds                 // All funds
POST /api/funds                // Create fund
PUT /api/funds/:id             // Update fund
GET /api/accounts              // All accounts
```

---

## API Integration

### Backend Server ([server/api.js](../frontend-admin/server/api.js))
Express.js server that directly queries MongoDB

**Key Functions**:

#### Get Dashboard Metrics
```javascript
app.get('/api/dashboard/metrics', async (req, res) => {
    const accounts = await db.collection('trading_accounts').find({}).toArray();

    const totalEquity = accounts.reduce((sum, acc) => sum + acc.balances.equity, 0);
    const realizedPnL = accounts.reduce((sum, acc) => sum + acc.balances.realized_pnl, 0);
    const unrealizedPnL = accounts.reduce((sum, acc) => sum + acc.balances.unrealized_pnl, 0);

    res.json({ totalEquity, realizedPnL, unrealizedPnL });
});
```

#### Get All Signals
```javascript
app.get('/api/signals', async (req, res) => {
    const signals = await db.collection('signal_store').find({}).sort({ created_at: -1 }).toArray();

    // Transform to include aggregated position data
    const transformedSignals = signals.map(sig => ({
        signal_id: sig.signal_id,
        strategy_id: sig.strategy_id,
        instrument: sig.instrument,
        status: sig.position.status,
        entry_quantity: sig.position.entry_quantity,
        exit_quantity: sig.position.exit_quantity,
        remaining_quantity: sig.position.remaining_quantity,
        legs: sig.legs.map(leg => ({
            leg_type: leg.leg_type,
            raw_quantity: leg.raw.signal_legs[0].quantity,
            cerebro_quantity: leg.decision?.legs[0]?.quantity || 0,
            execution_quantity: leg.execution?.total_quantity_filled || 0
        }))
    }));

    res.json(transformedSignals);
});
```

### Frontend API Client ([services/api.ts](../frontend-admin/src/services/api.ts))

```typescript
// API client with base URL
const API_BASE_URL = 'http://localhost:8000/api';

export const api = {
    // Dashboard
    getDashboardMetrics: () => fetch(`${API_BASE_URL}/dashboard/metrics`).then(r => r.json()),

    // Signals
    getSignals: () => fetch(`${API_BASE_URL}/signals`).then(r => r.json()),
    getOrders: () => fetch(`${API_BASE_URL}/orders`).then(r => r.json()),

    // Strategies
    getStrategies: () => fetch(`${API_BASE_URL}/strategies`).then(r => r.json()),
    createStrategy: (data) => fetch(`${API_BASE_URL}/strategies`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    }).then(r => r.json()),

    // Allocations
    getCurrentAllocations: () => fetch(`${API_BASE_URL}/api/v1/allocations/current`).then(r => r.json()),
    approveAllocation: (portfolio_test_id, fund_id) => fetch(`${API_BASE_URL}/api/v1/allocations/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ portfolio_test_id, fund_id })
    }).then(r => r.json()),
    getPortfolioTests: () => fetch(`${API_BASE_URL}/api/v1/portfolio-tests`).then(r => r.json())
};
```

---

## Usage

### Starting the Frontend

```bash
# Via Docker Compose (Recommended)
make start

# Access frontend at: http://localhost:5173
# API server at: http://localhost:8000

# Standalone (Development)
cd frontend-admin

# Install dependencies
npm install

# Start dev server (Vite)
npm run dev

# Start API server (Express)
npm run server

# Or run both concurrently
npm run dev:all
```

### Building for Production

```bash
cd frontend-admin

# Build frontend
npm run build

# Output: dist/ folder

# Serve production build
npm run preview
```

---

## Development

### Project Structure
```
frontend-admin/
├── src/
│   ├── pages/                  # Page components
│   ├── components/             # Reusable components
│   ├── services/
│   │   └── api.ts              # API client
│   ├── App.tsx                 # Root component
│   ├── main.tsx                # Entry point
│   └── index.css               # Global styles
├── server/
│   └── api.js                  # Express API server
├── public/                     # Static assets
├── index.html                  # HTML template
├── package.json
├── tsconfig.json               # TypeScript config
├── vite.config.ts              # Vite config
└── tailwind.config.js          # Tailwind config
```

### Adding a New Page

1. **Create page component**:
```typescript
// src/pages/MyNewPage.tsx
import React from 'react';

export function MyNewPage() {
    return (
        <div className="p-6">
            <h1 className="text-2xl font-bold mb-4">My New Page</h1>
            <p>Content here...</p>
        </div>
    );
}
```

2. **Add route** ([App.tsx](../frontend-admin/src/App.tsx)):
```typescript
import { MyNewPage } from './pages/MyNewPage';

<Route path="/my-new-page" element={<MyNewPage />} />
```

3. **Add navigation link**:
```typescript
<Link to="/my-new-page" className="nav-link">
    My New Page
</Link>
```

### Adding API Endpoint

1. **Backend** ([server/api.js](../frontend-admin/server/api.js)):
```javascript
app.get('/api/my-data', async (req, res) => {
    const data = await db.collection('my_collection').find({}).toArray();
    res.json(data);
});
```

2. **Frontend** ([services/api.ts](../frontend-admin/src/services/api.ts)):
```typescript
export const api = {
    getMyData: () => fetch(`${API_BASE_URL}/my-data`).then(r => r.json())
};
```

3. **Use in component**:
```typescript
import { api } from '../services/api';

function MyComponent() {
    const [data, setData] = useState([]);

    useEffect(() => {
        api.getMyData().then(setData);
    }, []);

    return <div>{JSON.stringify(data)}</div>;
}
```

---

## Related Documentation
- [Dashboard Creator](dashboard_creator.md) - Pre-computed dashboards
- [Account Data Service](account_data_service.md) - Account data API
- [Setup Guide](../Setup.md) - Initial setup
