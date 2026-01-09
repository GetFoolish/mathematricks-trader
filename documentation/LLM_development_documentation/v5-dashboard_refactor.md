# Dashboard System Implementation Plan

## Overview
Build a flexible, widget-based dashboard system with drag-and-drop layout, real-time data updates via Server-Sent Events (SSE), and staleness indicators. Users can create multiple named dashboards with customizable widgets that display fund balances and transaction history.

## User Requirements Summary
- **Multiple named dashboards** - Create, save, and switch between different dashboard layouts
- **Grid layout with drag-resize** - Using react-grid-layout for flexible widget positioning
- **Lock/unlock mode** - Prevent accidental changes when locked
- **Real-time SSE updates**: Instant updates when widget data regenerates (no polling)
- **Staleness tracking**: Widget outline turns orange if data >5 minutes old
- **Manual reload**: Each widget has reload button + dashboard-level "Reload All" button
- **Two initial widgets**:
  1. Fund Account Balances - Fund totals with account breakdowns
  2. Bank Statement - Transaction history with filters (last 30 days, by account/fund, grouped by date)

## Architecture

```
Dashboard Creator Service (port 8004)
    ↓ Generates widget data every 30s
    ↓ Emits SSE events
MongoDB (widget_data, dashboards)
    ↑ Pre-computed data
    ↓
Frontend API Server (port 8000)
    ↓ SSE stream + REST endpoints
Frontend (React + EventSource)
    ↓ Auto-updates via React Query invalidation
Widgets (instant refresh)
```

## Implementation Steps

### Phase 1: Backend Foundation

#### 1. MongoDB Schema Setup

**Create `dashboards` collection:**
```javascript
{
  dashboard_id: String (unique),
  name: String,
  description: String,
  created_by: String,
  fund_id: String,
  is_locked: Boolean,
  widgets: [{
    widget_id: String,
    widget_type: String, // "FundBalances" | "BankStatement"
    position: { x, y, w, h }, // Grid coordinates
    config: { /* widget-specific filters */ }
  }],
  grid_config: { cols: 12, row_height: 100 },
  created_at: Date,
  updated_at: Date
}
```

**Create `widget_data` collection:**
```javascript
{
  widget_type: String,
  fund_id: String,
  filters: Object,
  data: Object, // Widget-specific structure
  computed_at: Date, // For staleness tracking
  ttl: 300, // 5 minutes
  created_at: Date,
  updated_at: Date
}
```

**Indexes:**
- `dashboards`: `{dashboard_id: 1}` (unique), `{created_by: 1, created_at: -1}`
- `widget_data`: `{widget_type: 1, fund_id: 1, filters: 1}`, `{computed_at: 1}`, `{created_at: 1}` (TTL)

#### 2. Dashboard Creator Service - Widget Generators

**File: `services/dashboard_creator/generators/fund_balances_widget.py`**
```python
def generate_fund_balances_widget(mongo_client, fund_id=None):
    """
    Generate fund balances widget data.

    Query funds collection → get linked trading_accounts
    Aggregate: total_equity, accounts[{account_id, broker, equity, cash, margin_used, unrealized_pnl}]
    Store in widget_data collection with computed_at timestamp
    """
    db = mongo_client['mathematricks_trading']

    fund_query = {"status": "ACTIVE"}
    if fund_id:
        fund_query["fund_id"] = fund_id

    funds = list(db['funds'].find(fund_query))

    widget_data = {
        "total_equity": 0,
        "funds": []
    }

    for fund in funds:
        accounts = list(db['trading_accounts'].find({
            "account_id": {"$in": fund.get("accounts", [])}
        }))

        fund_total = sum(acc.get("equity", 0) for acc in accounts)
        widget_data["total_equity"] += fund_total

        fund_entry = {
            "fund_id": fund["fund_id"],
            "fund_name": fund["name"],
            "total_balance": fund_total,
            "accounts": [
                {
                    "account_id": acc["account_id"],
                    "broker": acc["broker"],
                    "equity": acc.get("equity", 0),
                    "cash": acc.get("cash_balance", 0),
                    "margin_used": acc.get("margin_used", 0),
                    "unrealized_pnl": acc.get("unrealized_pnl", 0)
                }
                for acc in accounts
            ]
        }
        widget_data["funds"].append(fund_entry)

    # Store in widget_data
    db['widget_data'].update_one(
        {"widget_type": "FundBalances", "fund_id": fund_id, "filters": {}},
        {
            "$set": {
                "data": widget_data,
                "computed_at": datetime.utcnow(),
                "ttl": 300,
                "updated_at": datetime.utcnow()
            },
            "$setOnInsert": {"created_at": datetime.utcnow()}
        },
        upsert=True
    )

    return widget_data
```

**File: `services/dashboard_creator/generators/bank_statement_widget.py`**
```python
def generate_bank_statement_widget(mongo_client, fund_id, account_filter, date_range_days, group_by):
    """
    Generate bank statement widget data.

    Query signal_store for closed positions in date range
    Extract execution.orders with filled_at, avg_fill_price
    Calculate debit/credit based on ENTRY/EXIT
    Get position.pnl for realized P&L
    Return transactions[] and summary{}
    """
    db = mongo_client['mathematricks_trading']

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=date_range_days)

    query = {"created_at": {"$gte": start_date, "$lte": end_date}}
    if fund_id:
        query["execution.orders.fund_id"] = fund_id
    if account_filter:
        query["execution.orders.account_id"] = account_filter

    signals = list(db['signal_store'].find(query).sort("created_at", -1))

    transactions = []
    total_debits = 0
    total_credits = 0

    for signal in signals:
        execution = signal.get("execution", {})
        for order in execution.get("orders", []):
            if not order.get("filled_at"):
                continue

            filled_qty = order.get("quantity_filled", 0)
            filled_price = order.get("avg_fill_price", 0)
            notional = filled_qty * filled_price

            is_entry = signal.get("raw", {}).get("signal_type") == "ENTRY"
            debit = notional if is_entry else 0
            credit = notional if not is_entry else 0

            total_debits += debit
            total_credits += credit

            pnl = signal.get("position", {}).get("pnl", {})
            realized_pnl = pnl.get("net", 0) if not is_entry else 0

            transactions.append({
                "date": order["filled_at"][:10],
                "timestamp": order["filled_at"],
                "account_id": order["account_id"],
                "fund_id": order.get("fund_id"),
                "type": "TRADE",
                "description": f"{signal.get('raw', {}).get('signal_type')} {signal.get('strategy_id')} @ ${filled_price:.2f} x {filled_qty}",
                "signal_id": signal["signal_id"],
                "debit": debit,
                "credit": credit,
                "balance": 0,
                "realized_pnl": realized_pnl
            })

    # Group by date if requested
    if group_by == "date":
        grouped = {}
        for txn in transactions:
            date = txn["date"]
            if date not in grouped:
                grouped[date] = []
            grouped[date].append(txn)

        transactions = []
        for date in sorted(grouped.keys(), reverse=True):
            transactions.extend(grouped[date])

    widget_data = {
        "transactions": transactions,
        "summary": {
            "total_debits": total_debits,
            "total_credits": total_credits,
            "net_pnl": total_credits - total_debits,
            "transaction_count": len(transactions)
        }
    }

    # Store in widget_data
    filters = {
        "account_filter": account_filter,
        "date_range_days": date_range_days,
        "group_by": group_by
    }

    db['widget_data'].update_one(
        {"widget_type": "BankStatement", "fund_id": fund_id, "filters": filters},
        {
            "$set": {
                "data": widget_data,
                "computed_at": datetime.utcnow(),
                "ttl": 300,
                "updated_at": datetime.utcnow()
            },
            "$setOnInsert": {"created_at": datetime.utcnow()}
        },
        upsert=True
    )

    return widget_data
```

**Update: `services/dashboard_creator/schedulers/background_jobs.py`**
```python
from pymongo import MongoClient
from datetime import datetime
import json

# Global event bus for SSE (can be replaced with Redis pub/sub)
widget_update_events = []

def generate_all_widget_data(mongo_client: MongoClient):
    """Generate all widget data and emit SSE events"""
    db = mongo_client['mathematricks_trading']
    funds = list(db['funds'].find({"status": "ACTIVE"}))

    for fund in funds:
        fund_id = fund["fund_id"]

        try:
            # Generate FundBalances
            generate_fund_balances_widget(mongo_client, fund_id)
            emit_widget_update_event({
                "widget_type": "FundBalances",
                "fund_id": fund_id,
                "timestamp": datetime.utcnow().isoformat()
            })

            # Generate BankStatement (default filters)
            generate_bank_statement_widget(
                mongo_client, fund_id=fund_id,
                account_filter=None, date_range_days=30, group_by="date"
            )
            emit_widget_update_event({
                "widget_type": "BankStatement",
                "fund_id": fund_id,
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Failed to generate widgets for {fund_id}: {e}")

def emit_widget_update_event(event_data):
    """Emit widget update event to SSE subscribers"""
    widget_update_events.append(event_data)
    # Keep only last 100 events to avoid memory issues
    if len(widget_update_events) > 100:
        widget_update_events.pop(0)

# Add job to scheduler
scheduler.add_job(
    func=lambda: generate_all_widget_data(mongo_client),
    trigger=IntervalTrigger(seconds=30),
    id='widget_data_generator',
    name='Generate All Widget Data',
    replace_existing=True
)
```

**Add SSE endpoint: `services/dashboard_creator/dashboard_creator_main.py`**
```python
from fastapi.responses import StreamingResponse
from fastapi import Request
import asyncio
import json

@app.get("/api/v1/widgets/events")
async def widget_updates_stream(request: Request):
    """
    SSE endpoint for real-time widget updates
    Sends events when widget data is regenerated
    """
    async def event_generator():
        last_event_index = 0
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                # Send new events
                if last_event_index < len(widget_update_events):
                    for event in widget_update_events[last_event_index:]:
                        yield f"data: {json.dumps(event)}\n\n"
                    last_event_index = len(widget_update_events)

                # Keep connection alive (heartbeat)
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )

@app.post("/api/v1/widgets/{widget_type}/generate")
async def generate_widget_on_demand(widget_type: str, request: dict):
    """Generate widget data on-demand (for reload button)"""
    try:
        fund_id = request.get("fund_id")
        filters = request.get("filters", {})

        if widget_type == "FundBalances":
            data = generate_fund_balances_widget(mongo_client, fund_id)
        elif widget_type == "BankStatement":
            data = generate_bank_statement_widget(
                mongo_client, fund_id=fund_id,
                account_filter=filters.get("account_filter"),
                date_range_days=filters.get("date_range_days", 30),
                group_by=filters.get("group_by", "date")
            )
        else:
            return JSONResponse(
                status_code=400,
                content={"error": f"Unknown widget type: {widget_type}"}
            )

        return {"status": "success", "widget_type": widget_type, "data": data}
    except Exception as e:
        logger.error(f"Error generating widget {widget_type}: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to generate widget: {str(e)}"}
        )
```

#### 3. Frontend API Server - Dashboard Endpoints

**Update: `frontend-admin/server/api.js`**

Add dashboard CRUD and widget endpoints:

```javascript
// GET /api/v1/dashboards
app.get('/api/v1/dashboards', async (req, res) => {
  const { fund_id, created_by } = req.query;
  const query = {};
  if (fund_id) query.fund_id = fund_id;
  if (created_by) query.created_by = created_by;

  const dashboards = await db.collection('dashboards')
    .find(query)
    .sort({ updated_at: -1 })
    .toArray();

  res.json({ dashboards: serializeDocument(dashboards) });
});

// GET /api/v1/dashboards/:dashboard_id
app.get('/api/v1/dashboards/:dashboard_id', async (req, res) => {
  const dashboard = await db.collection('dashboards')
    .findOne({ dashboard_id: req.params.dashboard_id });

  if (!dashboard) {
    return res.status(404).json({ error: 'Dashboard not found' });
  }

  res.json(serializeDocument(dashboard));
});

// POST /api/v1/dashboards
app.post('/api/v1/dashboards', async (req, res) => {
  const { name, description, fund_id, created_by } = req.body;

  const dashboard = {
    dashboard_id: `dash_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    name,
    description: description || '',
    created_by,
    fund_id,
    is_locked: false,
    widgets: [],
    grid_config: { cols: 12, row_height: 100 },
    created_at: new Date(),
    updated_at: new Date()
  };

  await db.collection('dashboards').insertOne(dashboard);
  res.json({ status: 'success', dashboard_id: dashboard.dashboard_id });
});

// PUT /api/v1/dashboards/:dashboard_id
app.put('/api/v1/dashboards/:dashboard_id', async (req, res) => {
  const { widgets, is_locked, name, description } = req.body;

  const updates = { updated_at: new Date() };
  if (widgets !== undefined) updates.widgets = widgets;
  if (is_locked !== undefined) updates.is_locked = is_locked;
  if (name !== undefined) updates.name = name;
  if (description !== undefined) updates.description = description;

  await db.collection('dashboards').updateOne(
    { dashboard_id: req.params.dashboard_id },
    { $set: updates }
  );

  res.json({ status: 'success' });
});

// DELETE /api/v1/dashboards/:dashboard_id
app.delete('/api/v1/dashboards/:dashboard_id', async (req, res) => {
  await db.collection('dashboards').deleteOne(
    { dashboard_id: req.params.dashboard_id }
  );
  res.json({ status: 'success' });
});

// GET /api/v1/widgets/:widget_type/data
app.get('/api/v1/widgets/:widget_type/data', async (req, res) => {
  const { widget_type } = req.params;
  const { fund_id, ...filters } = req.query;

  const query = { widget_type, fund_id: fund_id || null };
  if (Object.keys(filters).length > 0) {
    query.filters = filters;
  }

  const widgetData = await db.collection('widget_data')
    .findOne(query, { sort: { computed_at: -1 } });

  if (!widgetData) {
    return res.status(404).json({ error: 'Widget data not found' });
  }

  // Calculate staleness
  const now = new Date();
  const ageSeconds = (now - widgetData.computed_at) / 1000;
  const isStale = ageSeconds > widgetData.ttl;

  res.json({
    data: serializeDocument(widgetData.data),
    computed_at: widgetData.computed_at.toISOString(),
    age_seconds: ageSeconds,
    is_stale: isStale
  });
});

// POST /api/v1/widgets/:widget_type/reload
app.post('/api/v1/widgets/:widget_type/reload', async (req, res) => {
  const { widget_type } = req.params;
  const { fund_id, ...filters } = req.body;

  try {
    const response = await fetch(`http://localhost:8004/api/v1/widgets/${widget_type}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fund_id, filters })
    });

    const result = await response.json();
    res.json({ status: 'success', ...result });
  } catch (error) {
    res.status(500).json({ error: 'Failed to reload widget', detail: error.message });
  }
});

// POST /api/v1/dashboards/:dashboard_id/reload-all
app.post('/api/v1/dashboards/:dashboard_id/reload-all', async (req, res) => {
  const dashboard = await db.collection('dashboards')
    .findOne({ dashboard_id: req.params.dashboard_id });

  if (!dashboard) {
    return res.status(404).json({ error: 'Dashboard not found' });
  }

  const reloadPromises = dashboard.widgets.map(widget => {
    return fetch(`http://localhost:8004/api/v1/widgets/${widget.widget_type}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fund_id: dashboard.fund_id, filters: widget.config })
    });
  });

  await Promise.all(reloadPromises);
  res.json({ status: 'success', reloaded_count: dashboard.widgets.length });
});
```

### Phase 2: Frontend Core

#### 4. Type Definitions & API Client

**Update: `frontend-admin/src/types/index.ts`**

Add complete dashboard and widget type definitions (see plan for full types).

**Update: `frontend-admin/src/services/api.ts`**

Add methods:
```typescript
async getDashboards(fundId?: string, createdBy?: string): Promise<Dashboard[]>
async getDashboard(dashboardId: string): Promise<Dashboard>
async createDashboard(data: {...}): Promise<{ dashboard_id: string }>
async updateDashboard(dashboardId: string, updates: Partial<Dashboard>): Promise<void>
async deleteDashboard(dashboardId: string): Promise<void>
async getWidgetData<T>(widgetType: WidgetType, fundId?: string, filters?: WidgetConfig): Promise<WidgetData<T>>
async reloadWidget(widgetType: WidgetType, fundId?: string, filters?: WidgetConfig): Promise<void>
async reloadAllWidgets(dashboardId: string): Promise<void>
```

#### 5. SSE Integration

**Create: `frontend-admin/src/hooks/useWidgetSSE.ts`**
```typescript
import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';

interface WidgetUpdateEvent {
  widget_type: string;
  fund_id: string;
  timestamp: string;
}

export const useWidgetSSE = (dashboardId?: string) => {
  const queryClient = useQueryClient();
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!dashboardId) return;

    // Connect to SSE endpoint
    const eventSource = new EventSource('http://localhost:8004/api/v1/widgets/events');
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data: WidgetUpdateEvent = JSON.parse(event.data);

        // Invalidate React Query cache → automatic refetch
        queryClient.invalidateQueries({
          queryKey: ['widget', data.widget_type, data.fund_id]
        });

        console.log(`Widget updated: ${data.widget_type} for fund ${data.fund_id}`);
      } catch (error) {
        console.error('Error parsing SSE event:', error);
      }
    };

    eventSource.onerror = (error) => {
      console.error('SSE connection error:', error);
      // Automatic reconnection is handled by EventSource
    };

    // Cleanup on unmount
    return () => {
      eventSource.close();
    };
  }, [dashboardId, queryClient]);
};
```

#### 6. Widget Components

**Create widget components:**
- `FundBalancesWidget.tsx` - Display fund totals and account breakdowns
- `BankStatementWidget.tsx` - Display transactions with summary
- `WidgetWrapper.tsx` - Wrapper with reload button, staleness indicator, SSE support

### Phase 3: Dashboard Layout System

#### 7. Grid Layout with react-grid-layout

**Install:**
```bash
npm install react-grid-layout @types/react-grid-layout react-resizable @types/react-resizable
```

**Create: `DashboardCanvas.tsx`**
- GridLayout component with drag/resize
- Lock/unlock mode
- Toolbar with "Reload All" button
- Renders WidgetWrapper for each widget

#### 8. Dashboard Management

**Create: `DashboardManager.tsx`**
- List dashboards
- Create/delete dashboards
- Select active dashboard

**Create: `WidgetLibrary.tsx`**
- Palette of available widgets
- Add widget to canvas

**Create: `Dashboards.tsx` (main page)**
- Integrate DashboardManager, WidgetLibrary, DashboardCanvas
- Enable SSE via `useWidgetSSE()` hook
- Handle dashboard switching

**Update routing:**
- Add `/dashboards` route to App.tsx
- Add "Dashboards" link to Layout.tsx sidebar

### Phase 4: Account Balance Updates for Mock Broker

**Problem:** When trades close with P&L, mock broker accounts don't get their cash balance updated. Real brokers handle this automatically.

**Solution:** Update mock broker account balances in `execution_service` when EXIT signals are filled.

**Update: `services/execution_service/execution_main.py`**

Add after P&L calculation for EXIT signals:

```python
def update_signal_store_with_execution(order_data, execution_data):
    # ... existing EXIT signal logic ...

    if is_exit:
        # ... calculate P&L ...

        # Update mock broker account balances
        account_id = order_data.get('account_id')
        if account_id and is_mock_broker(account_id):
            update_mock_broker_balance(account_id, net_pnl, quantity, exit_price)

def is_mock_broker(account_id: str) -> bool:
    """Check if account is a mock broker account"""
    return 'MOCK' in account_id.upper() or account_id.startswith('Mock_')

def update_mock_broker_balance(account_id, realized_pnl, quantity_closed, exit_price):
    """
    Update mock broker account balance after trade close.
    - Add realized P&L to cash_balance
    - Reduce margin_used (position closed)
    - Update equity
    """
    try:
        account = trading_accounts.find_one({"account_id": account_id})
        if not account:
            logger.warning(f"Account {account_id} not found")
            return

        current_cash = account.get('cash_balance', 0)
        current_margin = account.get('margin_used', 0)
        current_equity = account.get('equity', 0)

        # Add P&L to cash
        new_cash = current_cash + realized_pnl

        # Reduce margin (estimate 10% of notional)
        freed_margin = (quantity_closed * exit_price) * 0.10
        new_margin = max(0, current_margin - freed_margin)

        # Update equity
        new_equity = current_equity + realized_pnl

        # Update account
        trading_accounts.update_one(
            {"account_id": account_id},
            {
                "$set": {
                    "cash_balance": new_cash,
                    "margin_used": new_margin,
                    "equity": new_equity,
                    "last_updated": datetime.utcnow()
                }
            }
        )

        logger.info(
            f"✅ Updated mock broker {account_id}: "
            f"Cash ${current_cash:.2f} → ${new_cash:.2f} (+${realized_pnl:.2f}), "
            f"Equity ${current_equity:.2f} → ${new_equity:.2f}"
        )
    except Exception as e:
        logger.error(f"Failed to update mock broker balance: {e}")
```

**Test script: `services/execution_service/test_account_balance_update.py`**
- Find mock broker account
- Simulate profitable trade close
- Verify cash_balance and equity updates

### Phase 5: Testing & Polish

#### End-to-End Testing
- Create multiple dashboards
- Add/remove/rearrange widgets
- Lock/unlock dashboard
- Test SSE real-time updates
- Test reload buttons
- Verify staleness indicator
- Test filter changes in BankStatement
- Verify data accuracy
- Test mock broker balance updates

#### UI Polish
- Match Activity.tsx styling
- Loading spinners
- Empty states
- Error handling
- Tooltips
- Responsive design

## Critical Files to Modify

1. **`services/dashboard_creator/generators/fund_balances_widget.py`** - New file
2. **`services/dashboard_creator/generators/bank_statement_widget.py`** - New file
3. **`services/dashboard_creator/schedulers/background_jobs.py`** - Add SSE event emission
4. **`services/dashboard_creator/dashboard_creator_main.py`** - Add SSE endpoint
5. **`services/execution_service/execution_main.py`** - Add mock broker balance updates
6. **`frontend-admin/server/api.js`** - Add dashboard & widget endpoints
7. **`frontend-admin/src/hooks/useWidgetSSE.ts`** - New file, SSE hook
8. **`frontend-admin/src/components/dashboards/DashboardCanvas.tsx`** - New file
9. **`frontend-admin/src/components/dashboards/WidgetWrapper.tsx`** - New file
10. **`frontend-admin/src/pages/Dashboards.tsx`** - New file
11. **`frontend-admin/src/services/api.ts`** - Add dashboard/widget methods
12. **`frontend-admin/src/types/index.ts`** - Add dashboard/widget types

## Implementation Timeline

- **Phase 1 (Backend Foundation)**: 2 days
- **Phase 2 (Frontend Core + SSE)**: 2 days
- **Phase 3 (Dashboard Layout)**: 2 days
- **Phase 4 (Mock Broker Balance Fix)**: 0.5 days
- **Phase 5 (Testing & Polish)**: 1 day

**Total**: ~7.5 days

## Key Design Decisions

1. **Pre-computed widget data**: Dashboard Creator pre-computes and caches all widget data in MongoDB every 30 seconds. Frontend only fetches cached data for instant load times.

2. **SSE for real-time updates**: Server-Sent Events push updates to frontend immediately when widget data regenerates. No polling required. React Query cache invalidation triggers automatic refetch.

3. **Staleness via timestamp**: Each widget_data document has `computed_at` timestamp. Frontend calculates age and shows orange border if >5 min.

4. **react-grid-layout**: Proven library for drag-and-drop grid layouts. Handles positioning, resizing, and collision detection automatically.

5. **Lock/unlock mode**: Prevents accidental widget rearrangement. Persisted to MongoDB.

6. **Mock broker balance updates**: Execution service updates mock broker account balances when trades close. Real brokers handle this automatically via account_data_service polling.

## Future Enhancements (Not in Scope)

- Widget config editor (change filters without re-adding widget)
- Dashboard templates (pre-configured layouts)
- Widget export (download as CSV/PDF)
- Dashboard sharing between users
- Redis pub/sub for multi-instance SSE (horizontal scaling)
- More widget types (P&L chart, position heatmap, strategy performance)
