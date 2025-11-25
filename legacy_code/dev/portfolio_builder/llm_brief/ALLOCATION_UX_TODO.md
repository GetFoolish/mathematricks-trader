# Portfolio Allocation UX Enhancement Roadmap

## Current Status (MVP)
✅ Current Active Allocation display
✅ Latest Recommendation with basic approve
✅ Allocation History table (not expandable yet)
✅ Correlation Matrix heatmap
✅ CORS fixed for frontend-backend communication

## Phase 1: Expandable History (IN PROGRESS)
- [ ] Make allocation history rows clickable/expandable
- [ ] Show full allocation details in expanded view
- [ ] Add approve/edit buttons to each PENDING_APPROVAL allocation
- [ ] Show optimization mode label (Max Sharpe, Max CAGR, Min Volatility)

## Phase 2: Run New Optimization UI
**Location**: Between "Current Active Allocation" and "Allocation History"

Features:
- [ ] Strategy Selection
  - Checkboxes to select/deselect strategies
  - Show strategy metadata (Sharpe, volatility, etc.)
  - Default: All ACTIVE strategies selected

- [ ] Optimization Mode Selector
  - Dropdown or radio buttons for:
    - Max Sharpe Ratio
    - Max CAGR with Drawdown Constraint
    - Min Volatility

- [ ] Parameter Inputs
  - Max Leverage slider (0-200%)
  - Max Single Strategy allocation slider (0-50%)
  - Max Drawdown input (for CAGR mode, default -20%)

- [ ] Run Button
  - Triggers optimization
  - Shows loading state
  - Redirects to results when complete

## Phase 3: Equity Curve Visualization
- [ ] Calculate portfolio equity curve from daily returns
- [ ] Use Recharts or similar library for visualization
- [ ] Show equity curve in expanded allocation view
- [ ] Add comparison: current vs recommended allocation curves

## Phase 4: Edit Allocation Functionality
- [ ] Edit modal to manually adjust allocation percentages
- [ ] Real-time validation (total <= max leverage)
- [ ] Recalculate expected metrics on edit
- [ ] Save as new PENDING_APPROVAL allocation

## Phase 5: StratQuant Tearsheet Integration
- [ ] Add tearsheet URL field to strategy configuration
- [ ] Display clickable link in allocation details
- [ ] Open in new window
- [ ] Handle missing tearsheets gracefully

## Phase 6: Advanced Features
- [ ] Allocation diff view (before/after comparison)
- [ ] Historical performance tracking
- [ ] Allocation versioning and rollback
- [ ] Bulk operations (approve multiple, reject multiple)
- [ ] Email notifications for new optimization runs
- [ ] Export allocation data (CSV, JSON)

## Backend Enhancements Needed
- [ ] `/api/v1/portfolio/optimization/run` - Actually trigger optimization (currently placeholder)
- [ ] `/api/v1/portfolio/allocations/{id}/edit` - Update allocation allocations
- [ ] `/api/v1/portfolio/allocations/{id}/reject` - Reject allocation
- [ ] `/api/v1/portfolio/allocations/{id}/equity-curve` - Calculate and return equity curve data
- [ ] Strategy filtering by status, asset class, etc.
