# Strategy Management: Public Upload Portal & Admin Improvements

## Revised Scope (After User Clarification)

### What We're Actually Building

1. **Public Strategy Submission Portal** (mathematricks-website repo)
   - Public-facing upload form
   - CSV validation and preview
   - Equity curve + metrics dashboard (CAGR, Sharpe, Calmar)
   - Submits to `uploaded_strategies` collection (PENDING_APPROVAL)

2. **Admin Approval Workflow** (frontend-admin)
   - New "Strategy Approval" tab
   - Review submitted strategies
   - Approve → move to `strategies` collection
   - Reject → delete or mark rejected

3. **Incremental Backtest Updates** (Both repos)
   - Update existing strategies with new dates
   - Backfill new columns synthetically
   - Data hash tracking for integrity

4. **Allocation Safety** (Backend)
   - Hash tracking prevents stale allocations
   - Auto-invalidate when data changes
   - Block signals from outdated allocations

5. **Deprecate CLI Script**
   - All uploads through UI (public or admin)
   - Remove/archive `load_strategies_from_folder.py`

### User Clarifications

- **Synthetic margin is fine**: 0% return → no position → no margin (correct logic)
- **Full data preferred**: But synthetic as fallback if developers upload partial
- **Multi-account is handled**: Cerebro routes, execution rejects invalid instruments
- **Dummy strategies OK**: For testing purposes
- **Position sizing**: Cerebro handles this

---

## Current State Analysis

### Frontend (http://localhost:5173/strategies)

**What Currently Exists:**
- Full CRUD interface for strategies
- Fields: strategy_id, name, asset_class, instruments, status, trading_mode, accounts, include_in_optimization, developer_contact, notes
- Actions: Create, Edit, Delete, Toggle status/mode/optimization
- **MISSING**: Backtest upload UI (only "Sync Backtest" button exists with no handler)

### Backend Current Implementation

**API Endpoints (Portfolio Builder Service :8003):**
- `POST /api/v1/strategies` - Create strategy (metadata only)
- `PUT /api/v1/strategies/{id}` - Update strategy
- `DELETE /api/v1/strategies/{id}` - Delete strategy
- `POST /api/v1/strategies/{id}/sync-backtest` - Sync backtest (exists but minimal)

**Data Upload Current Method:**
- **Script-based only**: `legacy_code/tools/load_strategies_from_folder.py`
- Command line: `python load_strategies_from_folder.py <csv_folder>`
- No UI upload capability

### Data Contract

**Required from Strategy Developer:**
- Date (YYYY-MM-DD)
- Daily_Return_Pct (0.5 or "0.5%" or 0.005)

**Optional but Recommended:**
- Account_Equity
- Daily_PnL
- Max_Margin_Used ⚠️ **CRITICAL for margin constraints**
- Max_Notional_Value

**Synthetic Data Generation (when missing):**
```python
account_equity = previous_equity * (1 + return/100)
daily_pnl = current_equity - previous_equity
margin_used = (abs(return) / max_return) * equity * 0.8
notional_value = margin * 3
```

## What Actually Needs Fixing

### ✅ Current System Works Fine (No Changes Needed)

1. **Synthetic Margin Formula**: Actually correct - 0% return likely means no position held
2. **Multi-Account Assignment**: Works, Cerebro handles routing
3. **Account-Asset Validation**: Already exists (main.py:1136-1155)
4. **Dummy Strategies**: Intentional for testing
5. **Position Sizing**: Cerebro handles, don't need to change

### 🆕 What's Missing (Need to Build)

1. **Public Strategy Upload Portal**
   - No public-facing website for developers to submit strategies
   - Need: Upload form, validation, metrics dashboard
   - Strategy goes to `uploaded_strategies` collection (PENDING_APPROVAL)

2. **Admin Approval Workflow**
   - No way for fund manager to review/approve submitted strategies
   - Need: "Strategy Approval" tab in frontend-admin
   - Approve → move to `strategies` collection

3. **Incremental Backtest Updates**
   - Current: Must upload full history every time (CLI only)
   - Need: Update with just new dates (Nov 31 → Jan 12)
   - Need: UI for updates (both public portal and admin)

4. **Data Hash Tracking**
   - Current: No version tracking of backtest data
   - Need: Hash of `raw_data_backtest_full`
   - Need: Track which hash each allocation uses

5. **Allocation Invalidation**
   - Current: Allocations stay ACTIVE even if strategy data changes
   - Need: Auto-mark OUTDATED when hash changes
   - Need: Block signals from outdated allocations

6. **CLI Script Deprecation**
   - Current: `load_strategies_from_folder.py` is primary upload method
   - Need: Phase out CLI, everything through UI

## User Decisions

### 1. Synthetic Margin Data Handling
**Decision:** Allow synthetic margin but warn user it's unrealistic
- Strategy can be used immediately in optimization
- System warns developer that margin constraint may be inaccurate
- Developer can update later with real margin data

### 2. Backtest Update Method
**Decision:** Incremental updates with sophisticated handling
- **Time incremental:** Append new rows (Dec 1 - Jan 12)
- **Column incremental:** If new columns added (e.g., margin_used), update existing rows
- **Conflict detection:** Warn if updating existing dates, require user confirmation for "replace"
- **Data integrity:** Create hash of backtest data used in allocations
- **Safety mechanism:** Reject signals if backtest data hash doesn't match allocation hash

### 3. UI Upload Feature
**Decision:** Add UI upload to /strategies tab
- Drag-drop CSV upload
- Validation feedback with preview
- Better UX for non-technical strategy developers

### 4. Multi-Account Assignment
**Decision:** Multi-account selection based on Hedge Funds structure
- Strategy can be assigned to multiple accounts during add/edit
- Accounts come from the "Hedge Funds" tab (fund → accounts hierarchy)
- Execution manager decides routing at trade time

### 5. Data Hashing for Allocation Safety
**Key Insight from User:**
- When backtest data changes, previous allocation runs become invalid
- Need to track which backtest data version was used for each allocation
- Reject signals from strategies where backtest hash doesn't match allocation hash
- Forces user to re-run allocations after backtest updates

### 6. Data Hash Scope
**Decision:** Hash only `raw_data_backtest_full` array
- Don't include metrics in hash (can be recalculated)
- Changes to backtest data trigger hash change
- Allocation stores hash snapshot at approval time

### 7. Allocation Status After Data Update
**Decision:** Auto-change to OUTDATED, block signals immediately
- Allocation status: ACTIVE → OUTDATED when strategy data changes
- All signals blocked until new allocation approved
- Safest approach, requires immediate user action

### 8. Column Backfill Strategy
**Decision:** Use synthetic formula for all old rows
- When new column added (e.g., margin_used), backfill old rows synthetically
- Maintains consistency (all data uses same formula)
- User can later upload full replacement with real data

---

## IMPLEMENTATION PLAN

### Overview: Two Systems Working Together

**System 1: Public Strategy Portal** (mathematricks-website)
- Developers upload strategies via public website
- See metrics dashboard immediately
- Strategy saved to `uploaded_strategies` (PENDING_APPROVAL)

**System 2: Admin Management** (frontend-admin + backend)
- Fund manager reviews submissions in "Strategy Approval" tab
- Approve → strategy moved to `strategies` collection
- Can also update existing strategies incrementally
- Hash tracking ensures allocation safety

---

### Phase 1: Database Schema & Backend Core (mathematricks-trader)

**Repo:** mathematricks-trader

**Files to Create:**
1. `services/portfolio_builder/backtest_upload_handler.py` - Core upload/merge logic
2. `services/portfolio_builder/metrics_calculator.py` - Calculate CAGR, Sharpe, Calmar

**Files to Modify:**
3. `services/portfolio_builder/main.py` - Add new endpoints
4. `services/mongodb_schemas.md` - Document new collections

#### 1.1 New MongoDB Collections

**Create: `uploaded_strategies` collection**
```javascript
{
  "_id": ObjectId,
  "submission_id": String,                // Unique ID (UUID)
  "status": String,                       // "PENDING_APPROVAL" | "APPROVED" | "REJECTED"

  // Strategy metadata
  "strategy_id": String,                  // Proposed strategy ID
  "strategy_name": String,
  "asset_class": String,
  "instruments": [String],

  // Submitter info
  "developer_name": String,
  "developer_email": String,
  "developer_contact": String,

  // Backtest data (same structure as strategies.raw_data_backtest_full)
  "raw_data_backtest_full": [
    {
      "date": String,
      "return": Number,
      "pnl": Number,
      "margin_used": Number,
      "notional_value": Number,
      "account_equity": Number
    }
  ],

  // Calculated metrics (for dashboard)
  "metrics": {
    "cagr": Number,                       // Compound Annual Growth Rate
    "sharpe_ratio": Number,               // Sharpe Ratio (annualized)
    "calmar_ratio": Number,               // CAGR / Max Drawdown
    "max_drawdown": Number,
    "total_return": Number,
    "volatility_annual": Number,
    "win_rate": Number,
    "num_trades": Number,                 // Estimated from margin changes
    "start_date": String,
    "end_date": String,
    "total_days": Number
  },

  // Synthetic data tracking
  "synthetic_data": {
    "columns_generated": [String],
    "starting_capital": Number
  },

  // Admin review
  "reviewed_by": String,                  // Admin user who reviewed
  "reviewed_at": ISODate,
  "rejection_reason": String,             // If rejected

  // Timestamps
  "submitted_at": ISODate,
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Indexes:**
- `{submission_id: 1}` - Unique
- `{status: 1, submitted_at: -1}` - For admin review queue
- `{strategy_id: 1}` - For duplicate detection

---

**Modify: `strategies` collection**

**Add fields:**
```javascript
{
  "backtest_data_hash": String,          // SHA256 of raw_data_backtest_full
  "last_backtest_sync": ISODate,         // When backtest was last updated
  "original_submission_id": String       // Link to uploaded_strategies (if came from portal)
}
```

**Index to add:**
- `{backtest_data_hash: 1}`

---

**Modify: `portfolio_allocations` collection**

**Add fields:**
```javascript
{
  "status": String,                      // Add "OUTDATED" to existing enum
  "strategy_data_hashes": {              // Hash snapshot at approval time
    "strategy_id": String                // SHA256 value
  },
  "outdated_reason": String,             // Why marked OUTDATED
  "outdated_at": ISODate                 // When invalidated
}
```

**Index to add:**
- `{status: 1, outdated_at: -1}`

#### 1.2 Core Backend Functions

**Create: `backtest_upload_handler.py`**

Key functions:
- `parse_csv(file)` - Parse and validate CSV format
- `normalize_returns(df)` - Handle percentage formats (0.5%, 0.5, 0.005)
- `detect_columns(df)` - Identify which columns present/missing
- `generate_synthetic_columns(df, starting_capital)` - Apply formulas
- `merge_backtest_data(existing, new, force_replace)` - Incremental merge
- `calculate_backtest_hash(data_array)` - SHA256 hash
- `invalidate_allocations_for_strategy(strategy_id, new_hash)` - Mark OUTDATED

**Create: `metrics_calculator.py`**

Key functions:
- `calculate_cagr(returns, days)` - Compound annual growth rate
- `calculate_sharpe_ratio(returns)` - Risk-adjusted return
- `calculate_calmar_ratio(cagr, max_drawdown)` - CAGR / MDD
- `calculate_max_drawdown(equity_curve)` - Largest peak-to-trough
- `estimate_num_trades(margin_data)` - Count margin changes
- `calculate_all_metrics(raw_data)` - Return complete metrics dict

#### 1.3 API Endpoints to Add

**Base Service:** PortfolioBuilder (port 8003)

**PUBLIC ENDPOINTS (for mathematricks-website):**

**1. POST /api/v1/public/submit-strategy**
- **Auth:** None (public endpoint)
- **Body (multipart/form-data):**
  ```typescript
  {
    file: File,                          // CSV backtest data
    strategy_id: string,
    strategy_name: string,
    asset_class: string,
    instruments: string,                 // Comma-separated
    developer_name: string,
    developer_email: string,
    developer_contact?: string,
    starting_capital?: number            // Default: 1M
  }
  ```
- **Logic:**
  1. Parse and validate CSV
  2. Generate synthetic columns if needed
  3. Calculate metrics (CAGR, Sharpe, Calmar, etc.)
  4. Create document in `uploaded_strategies` collection
  5. Status: PENDING_APPROVAL
- **Response:**
  ```typescript
  {
    status: "success",
    submission_id: string,
    metrics: {
      cagr: number,
      sharpe_ratio: number,
      calmar_ratio: number,
      max_drawdown: number,
      // ... full metrics
    },
    equity_curve: Array<{date: string, equity: number}>,  // For chart
    warnings: string[],                  // e.g., "Generated synthetic margin_used"
    synthetic_columns: string[]
  }
  ```

**2. GET /api/v1/public/submission/{submission_id}**
- **Auth:** None (public lookup by ID)
- **Response:** Full submission details + metrics
- **Use:** Share submission link with others

---

**ADMIN ENDPOINTS (for frontend-admin):**

**3. GET /api/v1/admin/submissions**
- **Auth:** Required (admin JWT)
- **Query params:** `?status=PENDING_APPROVAL` or `ALL`
- **Response:**
  ```typescript
  {
    status: "success",
    count: number,
    submissions: Array<UploadedStrategy>
  }
  ```

**4. POST /api/v1/admin/submissions/{submission_id}/approve**
- **Auth:** Required (admin JWT)
- **Body:**
  ```typescript
  {
    accounts: string[],                  // Assign to accounts
    status: "ACTIVE" | "TESTING",
    trading_mode: "PAPER" | "LIVE",
    include_in_optimization: boolean,
    notes?: string
  }
  ```
- **Logic:**
  1. Fetch submission from `uploaded_strategies`
  2. Calculate backtest hash
  3. Create strategy in `strategies` collection
  4. Update submission status: APPROVED
  5. Set reviewed_by, reviewed_at
- **Response:**
  ```typescript
  {
    status: "success",
    strategy_id: string,
    message: "Strategy approved and added to portfolio"
  }
  ```

**5. POST /api/v1/admin/submissions/{submission_id}/reject**
- **Auth:** Required (admin JWT)
- **Body:**
  ```typescript
  {
    rejection_reason: string
  }
  ```
- **Logic:**
  1. Update submission status: REJECTED
  2. Set reviewed_by, reviewed_at, rejection_reason
- **Response:**
  ```typescript
  {
    status: "success",
    message: "Strategy submission rejected"
  }
  ```

**6. POST /api/v1/strategies/{strategy_id}/upload-backtest**
- **Auth:** Required (admin JWT)
- **Body (multipart/form-data):**
  ```typescript
  {
    file: File,
    force_replace: boolean,
    starting_capital?: number
  }
  ```
- **Logic:**
  1. Parse CSV
  2. Detect overlaps with existing data
  3. If overlaps && !force_replace → return error
  4. Merge incrementally (append new dates, backfill new columns)
  5. Calculate new hash
  6. Update strategy document
  7. Find ACTIVE allocations using this strategy
  8. Mark them OUTDATED
- **Response:**
  ```typescript
  {
    status: "success",
    upload_summary: {
      total_rows: number,
      new_rows: number,
      updated_rows: number,
      columns_added: string[],
      columns_synthetic: string[]
    },
    old_hash: string,
    new_hash: string,
    invalidated_allocations: {
      count: number,
      allocation_ids: string[]
    }
  }
  ```

**7. GET /api/v1/allocations/outdated**
- **Auth:** Required (admin JWT)
- **Response:** List of OUTDATED allocations with details

**8. MODIFY: POST /api/v1/allocations/approve**
- **Add logic:** Capture strategy hashes at approval
- **Before approval:**
  ```python
  strategy_hashes = {}
  for strategy_id in allocation['allocations'].keys():
      strategy = strategies_collection.find_one({"strategy_id": strategy_id})
      strategy_hashes[strategy_id] = strategy.get('backtest_data_hash', 'NONE')

  allocation_document['strategy_data_hashes'] = strategy_hashes
  ```

---

### Phase 2: Public Strategy Portal (mathematricks-website)

**Repo:** mathematricks-website (React + Vite + TailwindCSS)

**Files to Create:**
1. `src/pages/SubmitStrategy.tsx` - Main upload page
2. `src/components/StrategyUploadForm.tsx` - Upload form component
3. `src/components/StrategyMetricsDashboard.tsx` - Results dashboard
4. `src/services/api.ts` - API client for backend
5. `src/types/strategy.ts` - TypeScript types

**Files to Modify:**
6. `src/App.tsx` - Add `/submit-strategy` route

#### 2.1 Strategy Upload Form

**Route:** `/submit-strategy`

**UI Components:**

**Section 1: Strategy Information**
- Strategy ID (text input, required)
- Strategy Name (text input, required)
- Asset Class (dropdown: equity, options, futures, forex, crypto, commodities)
- Instruments (text input, comma-separated)

**Section 2: Developer Information**
- Your Name (text input, required)
- Email Address (email input, required)
- Contact Info (text input, optional) - Phone, Telegram, etc.

**Section 3: Backtest Data Upload**
- CSV File Upload (drag-drop or file picker)
- Starting Capital (number input, default: 1,000,000)
- File Requirements Panel:
  ```
  Required Columns:
  ✓ Date (YYYY-MM-DD)
  ✓ Daily_Return_Pct (or Daily Returns %)

  Optional Columns (recommended):
  • Account_Equity
  • Daily_PnL
  • Max_Margin_Used
  • Max_Notional_Value

  Note: Missing columns will be calculated synthetically
  ```

**Section 4: Preview (after file upload)**
- File name, size, row count
- Date range detected
- Columns found vs missing
- Preview table (first 10 rows)
- Warnings (if any)

**Submit Button:**
- Disabled until: strategy_id, strategy_name, asset_class, instruments, file uploaded
- "Submit Strategy for Review"

#### 2.2 Metrics Dashboard (Completion Page)

**Shows after successful submission:**

**Header:**
```
✓ Strategy Submitted Successfully!
Submission ID: sub_abc123xyz
Status: Pending Approval
```

**Equity Curve Chart:**
- X-axis: Date
- Y-axis: Account Equity
- Line chart showing equity growth over time
- Use Recharts or Chart.js

**Key Metrics Cards:**
```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ CAGR            │  │ Sharpe Ratio    │  │ Calmar Ratio    │
│ 42.5%           │  │ 2.45            │  │ 3.12            │
└─────────────────┘  └─────────────────┘  └─────────────────┘

┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Max Drawdown    │  │ Total Return    │  │ Win Rate        │
│ -12.3%          │  │ 156.8%          │  │ 64.2%           │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

**Additional Stats:**
- Backtest Period: 2020-01-01 to 2025-12-31
- Total Days: 2190
- Estimated Trades: 450
- Annual Volatility: 18.2%

**Synthetic Data Warning (if applicable):**
```
⚠️ Note: The following columns were generated synthetically:
• margin_used (formula: based on return volatility)
• notional_value (formula: margin × 3)

For more accurate optimization, consider providing real data for these columns.
```

**What's Next:**
```
✓ Your strategy is now in the review queue
✓ You'll receive an email when it's reviewed
✓ Share this link: https://mathematricks.com/submission/sub_abc123xyz
```

#### 2.3 API Client Implementation

**File: `src/services/api.ts`**

```typescript
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_PORTFOLIO_BUILDER_URL || 'http://localhost:8003';

export const apiClient = {
  submitStrategy: async (formData: FormData) => {
    const response = await axios.post(
      `${API_BASE_URL}/api/v1/public/submit-strategy`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60000  // 60 seconds for large files
      }
    );
    return response.data;
  },

  getSubmission: async (submissionId: string) => {
    const response = await axios.get(
      `${API_BASE_URL}/api/v1/public/submission/${submissionId}`
    );
    return response.data;
  }
};
```

---

### Phase 3: Admin Approval Workflow (frontend-admin)

**Repo:** mathematricks-trader/frontend-admin

**Files to Create:**
1. `frontend-admin/src/pages/StrategyApproval.tsx` - NEW TAB for reviewing submissions
2. `frontend-admin/src/components/SubmissionReviewModal.tsx` - Review/approve modal
3. `frontend-admin/src/components/BacktestUploadModal.tsx` - For updating existing strategies
4. `frontend-admin/src/components/AllocationOutdatedBanner.tsx` - Warning banner

**Files to Modify:**
5. `frontend-admin/src/App.tsx` - Add `/strategy-approval` route
6. `frontend-admin/src/components/Layout.tsx` - Add "Strategy Approval" nav item
7. `frontend-admin/src/pages/Strategies.tsx` - Add "Upload Backtest" button
8. `frontend-admin/src/services/api.ts` - Add new API methods

#### 3.1 Strategy Approval Page (NEW TAB)

**Route:** `/strategy-approval`

**Nav Item:**
```tsx
<NavLink to="/strategy-approval">
  <CheckCircle className="w-5 h-5" />
  Strategy Approval
  {pendingCount > 0 && (
    <span className="badge">{pendingCount}</span>
  )}
</NavLink>
```

**Page Layout:**

**Header:**
```
Strategy Approval
Manage strategy submissions from developers
[Status Filter: All | Pending | Approved | Rejected]
```

**Submissions Table:**

Columns:
- Submission ID (clickable)
- Strategy Name
- Asset Class
- Developer (name + email)
- Key Metrics (CAGR, Sharpe)
- Submitted Date
- Status (badge: Pending/Approved/Rejected)
- Actions (Review button)

**Empty State:**
```
No pending submissions
Check back later for new strategy submissions
```

#### 3.2 Submission Review Modal

**Triggered by:** Click "Review" button on submission row

**Modal Sections:**

**Section 1: Strategy Info**
- Strategy ID, Name, Asset Class, Instruments
- Developer: Name, Email, Contact

**Section 2: Backtest Metrics Dashboard**
- Same dashboard as public portal
- Equity curve chart
- Metric cards (CAGR, Sharpe, Calmar, etc.)
- Synthetic data warning (if applicable)

**Section 3: Data Preview**
- Table showing first 20 rows of backtest data
- All columns visible
- Scroll to see full data

**Section 4: Approval Form** (if approving)
- **Accounts** (multi-select): Which accounts can trade this strategy
- **Status**: ACTIVE | TESTING
- **Trading Mode**: PAPER | LIVE
- **Include in Optimization**: Checkbox (default: true)
- **Notes**: Textarea (optional)

**Section 5: Rejection Form** (if rejecting)
- **Rejection Reason**: Textarea (required)
- Examples:
  - "Insufficient backtest history (need at least 2 years)"
  - "Return profile too volatile for our risk limits"
  - "Strategy ID already exists"

**Action Buttons:**
- "Approve Strategy" (green)
- "Reject Submission" (red)
- "Cancel"

#### 3.3 Backtest Upload Modal (For Existing Strategies)

**Triggered by:** Click "Upload Backtest" button on Strategies page

**Features:**
- Drag-drop CSV upload
- Preview (first 10 rows)
- Overlap detection: "50 dates overlap with existing data"
- **Force Replace** checkbox (if overlaps detected)
- Column status:
  - 🟢 Green: Found in CSV
  - 🟡 Yellow: Will be generated
- **Upload** button

**Success Message:**
```
✓ Backtest Updated Successfully
• Uploaded 50 new rows
• Replaced 0 existing rows
• Backfilled margin_used for 100 old rows (synthetic)

⚠️ Warning: 2 allocations marked OUTDATED
Strategy data changed - allocations need re-approval
[View Outdated Allocations]
```

#### 3.4 Allocation Outdated Banner

**Shows on:** Allocations page (when OUTDATED allocations exist)

**Banner:**
```
⚠️ ALLOCATION OUTDATED
Your portfolio allocation is no longer valid because strategy backtest data changed.
Affected strategies: SPX_1-D_Opt, FloridaForex
[View Details] [Create New Allocation]
```

#### 3.5 Strategies Page Modifications

**Add "Upload Backtest" button:**
```tsx
<button
  onClick={() => handleUploadBacktest(strategy)}
  title="Upload Updated Backtest"
  className="p-2 hover:bg-gray-700 rounded"
>
  <Upload className="h-4 w-4 text-green-400" />
</button>
```

**Add hash display:**
```tsx
<div className="text-xs text-gray-500">
  Hash: {strategy.backtest_data_hash?.substring(0, 12) || 'None'}
</div>
<div className="text-xs text-gray-500">
  Last Sync: {formatDate(strategy.last_backtest_sync) || 'Never'}
</div>
```

---

### Phase 4: Signal Safety & Allocation Invalidation (Backend)

**Files to Create:**
1. `services/cerebro_service/signal_validator.py`

**Files to Modify:**
2. `services/cerebro_service/cerebro_main.py` - Add hash verification

#### 4.1 Signal Hash Verification

**Add to signal processing loop:**
```python
# Before executing signal
allocation = get_active_allocation(fund_id)

# Check allocation status
if allocation['status'] == 'OUTDATED':
    reject_signal(signal, "Allocation outdated - strategy data changed")
    continue

# Verify hash matches
is_valid, reason = verify_strategy_hash_matches_allocation(
    signal, allocation, strategies_collection
)

if not is_valid:
    reject_signal(signal, f"Hash mismatch: {reason}")
    continue

# Execute signal...
```

**Function: verify_strategy_hash_matches_allocation()**
- Get current strategy hash from DB
- Get expected hash from allocation.strategy_data_hashes
- Compare hashes
- Return (is_valid, reason)

#### 4.2 Allocation Invalidation

**Triggered when:** Strategy backtest uploaded with new hash

**Logic:**
1. Find all ACTIVE allocations containing strategy_id
2. For each allocation:
   - Update status: ACTIVE → OUTDATED
   - Set outdated_at: current timestamp
   - Set outdated_reason: "Strategy {id} data changed (hash: old → new)"
3. Return list of invalidated allocation_ids
4. Frontend shows warning with count

---

### Phase 5: CLI Script Deprecation

**Current:** `legacy_code/tools/load_strategies_from_folder.py`

**Actions:**
1. Move to `legacy_code/deprecated/load_strategies_from_folder.py`
2. Add deprecation notice at top of file:
   ```python
   """
   DEPRECATED: This script is no longer maintained.

   Please use the web interface instead:
   - Public submission: https://mathematricks.com/submit-strategy
   - Admin upload: frontend-admin Strategy Approval tab

   This script remains for historical reference only.
   """
   ```
3. Update documentation to remove CLI references
4. Keep in repo for emergency bulk uploads (but not recommended)

---

### Phase 6: Testing & Validation

#### 6.1 Enhanced Validations

**Account-Asset Class Compatibility:**
- When assigning strategy to accounts, verify account supports strategy's asset class
- Already implemented in main.py:1136-1155

**Date Gap Detection:**
- Detect gaps > 7 days in backtest data
- Show warnings in validation preview
- Don't block upload, just warn

**Missing Backtest Warning:**
- When setting strategy status to ACTIVE
- Check if raw_data_backtest_full is empty
- Show warning: "Strategy has no backtest data"

#### 6.2 Testing Strategy

**Unit Tests (NEW):**
- `test_merge_no_overlap()` - Happy path merge
- `test_merge_with_overlap_no_force()` - Conflict detection
- `test_merge_with_overlap_force()` - Force replace
- `test_column_backfill()` - Synthetic generation
- `test_hash_calculation_deterministic()` - Same data = same hash
- `test_hash_changes_with_data()` - Different data = different hash

**Integration Tests (NEW):**
- `test_full_upload_flow()` - CSV → allocation invalidation
- `test_signal_blocked_after_outdated()` - Signal rejection
- `test_incremental_update()` - Append new dates
- `test_column_addition()` - Backfill existing rows

**Manual Testing Checklist:**
- [ ] Upload CSV with all columns (no synthetic)
- [ ] Upload CSV with only date + return (full synthetic)
- [ ] Upload CSV with overlaps (no force) → blocked
- [ ] Upload CSV with overlaps (force) → replaced
- [ ] Upload CSV adding new column → backfilled
- [ ] Verify allocation marked OUTDATED
- [ ] Verify signal rejected from OUTDATED allocation
- [ ] Create new allocation → signals execute

---

### Phase 7: Documentation & Migration

#### 7.1 Update Documentation

**Files to Update:**
1. `services/mongodb_schemas.md` - Document new fields
2. `legacy_code/dev/data_collection_request_email/email_for_strategy_devs.md` - Update with UI upload instructions

**Add sections:**
- "Uploading Backtest Data via UI"
- "Understanding Synthetic Data Warnings"
- "What Happens When You Update Backtest Data"
- "Allocation Invalidation and Re-approval"

#### 7.2 Migration Plan

**Step 1:** Add schema fields to existing strategies
```javascript
// Run migration script
db.strategies.updateMany(
  { backtest_data_hash: { $exists: false } },
  { $set: {
      backtest_data_hash: null,
      last_backtest_sync: null
  }}
)
```

**Step 2:** Calculate hashes for existing strategies
```python
# Python migration script
for strategy in strategies_collection.find():
    if strategy.get('raw_data_backtest_full'):
        hash_val = calculate_backtest_hash(strategy['raw_data_backtest_full'])
        strategies_collection.update_one(
            {"_id": strategy["_id"]},
            {"$set": {"backtest_data_hash": hash_val}}
        )
```

**Step 3:** Update existing allocations
```javascript
// Add strategy_data_hashes to ACTIVE allocations
db.portfolio_allocations.updateMany(
  {
    status: "ACTIVE",
    strategy_data_hashes: { $exists: false }
  },
  { $set: { strategy_data_hashes: {} } }
)
```

**Step 4:** Backfill strategy hashes in allocations
```python
# For each ACTIVE allocation, capture current strategy hashes
for allocation in allocations_collection.find({"status": "ACTIVE"}):
    strategy_hashes = {}
    for strategy_id in allocation['allocations'].keys():
        strategy = strategies_collection.find_one({"strategy_id": strategy_id})
        if strategy:
            strategy_hashes[strategy_id] = strategy.get('backtest_data_hash', 'LEGACY')

    allocations_collection.update_one(
        {"_id": allocation["_id"]},
        {"$set": {"strategy_data_hashes": strategy_hashes}}
    )
```

---

## SUMMARY

### What We're Building

**1. Public Strategy Portal** (mathematricks-website)
- Developers submit strategies via public website
- See metrics dashboard immediately
- Submission saved to `uploaded_strategies` collection

**2. Admin Approval System** (frontend-admin)
- New "Strategy Approval" tab
- Review submissions with full metrics
- Approve → moves to `strategies` collection
- Reject with reason

**3. Incremental Updates** (Both systems)
- Update existing strategies with new dates
- Backfill missing columns synthetically
- Conflict detection (force replace option)

**4. Data Integrity** (Backend)
- SHA256 hash of backtest data
- Allocations track strategy hashes
- Auto-invalidate when data changes
- Block signals from outdated allocations

**5. Deprecate CLI**
- Everything through UI
- Archive old script

### Critical Files

**Backend (mathematricks-trader):**
1. `services/portfolio_builder/main.py` - Add 8 new endpoints
2. `services/portfolio_builder/backtest_upload_handler.py` - Upload logic (NEW)
3. `services/portfolio_builder/metrics_calculator.py` - CAGR, Sharpe, Calmar (NEW)
4. `services/cerebro_service/signal_validator.py` - Hash verification (NEW)
5. `services/mongodb_schemas.md` - Document `uploaded_strategies` collection

**Public Portal (mathematricks-website):**
1. `src/pages/SubmitStrategy.tsx` - Upload page (NEW)
2. `src/components/StrategyUploadForm.tsx` - Form (NEW)
3. `src/components/StrategyMetricsDashboard.tsx` - Results dashboard (NEW)
4. `src/services/api.ts` - API client (NEW)
5. `src/App.tsx` - Add route

**Admin Frontend (mathematricks-trader/frontend-admin):**
1. `src/pages/StrategyApproval.tsx` - Review tab (NEW)
2. `src/components/SubmissionReviewModal.tsx` - Approve/reject modal (NEW)
3. `src/components/BacktestUploadModal.tsx` - Update existing strategies (NEW)
4. `src/components/AllocationOutdatedBanner.tsx` - Warning banner (NEW)
5. `src/pages/Strategies.tsx` - Add upload button
6. `src/components/Layout.tsx` - Add nav item
7. `src/App.tsx` - Add route

**Testing:**
1. `services/portfolio_builder/tests/test_backtest_upload.py` (NEW)
2. `services/portfolio_builder/tests/test_submission_approval.py` (NEW)
3. `services/portfolio_builder/tests/test_allocation_invalidation.py` (NEW)

**Deprecated:**
1. `legacy_code/tools/load_strategies_from_folder.py` → Move to deprecated/

---

## End-to-End Verification

### Test Flow 1: Public Submission → Approval

1. **Public Portal:**
   - Go to mathematricks-website
   - Navigate to `/submit-strategy`
   - Fill form: strategy details + developer info
   - Upload CSV backtest
   - See metrics dashboard with CAGR, Sharpe, Calmar
   - Get submission ID

2. **Admin Review:**
   - Go to frontend-admin
   - Click "Strategy Approval" tab
   - See new submission in PENDING list
   - Click "Review"
   - See full metrics + data preview
   - Fill approval form (assign accounts, status)
   - Click "Approve Strategy"

3. **Verify:**
   - Strategy appears in Strategies tab
   - Has backtest_data_hash populated
   - Can create allocation with this strategy
   - Allocation captures strategy hash

### Test Flow 2: Incremental Update → Allocation Invalidation

1. **Update Strategy:**
   - Go to Strategies tab
   - Click "Upload Backtest" on existing strategy
   - Upload CSV with new dates (overlap detected)
   - Check "Force Replace"
   - Upload succeeds
   - Warning: "2 allocations marked OUTDATED"

2. **Verify Allocation Blocked:**
   - Go to Allocations tab
   - See red banner: "Allocation OUTDATED"
   - Signal arrives for this strategy
   - Cerebro rejects signal: "Allocation outdated"

3. **Re-approve:**
   - Create new allocation
   - Approve
   - New allocation captures new hash
   - Signals now execute

### Test Flow 3: Synthetic Data Handling

1. **Upload Minimal CSV** (only date + return)
   - See warning: "Will generate synthetic columns"
   - Preview shows which columns synthetic
   - Upload succeeds
   - Dashboard shows metrics correctly

2. **Add Column Later:**
   - Upload CSV with new column (margin_used)
   - System detects: "margin_used will be backfilled"
   - Old rows get synthetic margin_used
   - New rows have real margin_used
   - Hash changes, allocations invalidated

---

## Test Data Files Strategy

We'll create a suite of test CSV files to systematically test synthetic data generation and validation:

### Test File 1: `test_strategy_full_data.csv`
**Purpose:** Baseline - all columns present
```csv
Date,Daily_Return_Pct,Account_Equity,Daily_PnL,Max_Margin_Used,Max_Notional_Value
2025-01-01,2.5,100000,2500,80000,240000
2025-01-02,-1.2,98800,-1200,47520,142560
2025-01-03,0.8,99590,790,31836,95508
```
**Expected:** No synthetic data warnings, all metrics calculated from real data

### Test File 2: `test_strategy_missing_1col.csv`
**Purpose:** Missing Max_Notional_Value (least critical column)
```csv
Date,Daily_Return_Pct,Account_Equity,Daily_PnL,Max_Margin_Used
2025-01-01,2.5,100000,2500,80000
2025-01-02,-1.2,98800,-1200,47520
2025-01-03,0.8,99590,790,31836
```
**Expected:**
- Warning: "⚠️ Generated synthetic Max_Notional_Value using formula: margin × 3"
- Synthetic values: 240000, 142560, 95508

### Test File 3: `test_strategy_missing_2cols.csv`
**Purpose:** Missing Max_Margin_Used and Max_Notional_Value
```csv
Date,Daily_Return_Pct,Account_Equity,Daily_PnL
2025-01-01,2.5,100000,2500
2025-01-02,-1.2,98800,-1200
2025-01-03,0.8,99590,790
```
**Expected:**
- Warning: "⚠️ Generated synthetic Max_Margin_Used using formula: (|return| / max_return) × equity × 0.8"
- Warning: "⚠️ Generated synthetic Max_Notional_Value using formula: margin × 3"
- max_return calculated from column (2.5%)

### Test File 4: `test_strategy_missing_3cols.csv`
**Purpose:** Only Date, Daily_Return_Pct, Account_Equity
```csv
Date,Daily_Return_Pct,Account_Equity
2025-01-01,2.5,100000
2025-01-02,-1.2,98800
2025-01-03,0.8,99590
```
**Expected:**
- Warning: "⚠️ Generated synthetic Daily_PnL using formula: equity[i] - equity[i-1]"
- Warning: "⚠️ Generated synthetic Max_Margin_Used"
- Warning: "⚠️ Generated synthetic Max_Notional_Value"

### Test File 5: `test_strategy_minimal.csv`
**Purpose:** Only required columns (Date + Daily_Return_Pct)
```csv
Date,Daily_Return_Pct
2025-01-01,2.5
2025-01-02,-1.2
2025-01-03,0.8
2025-01-04,1.5
2025-01-05,-0.5
```
**Expected:**
- Warning: "⚠️ Generated synthetic Account_Equity (starting: $100,000)"
- Warning: "⚠️ Generated synthetic Daily_PnL"
- Warning: "⚠️ Generated synthetic Max_Margin_Used"
- Warning: "⚠️ Generated synthetic Max_Notional_Value"
- All metrics calculated correctly from synthetic data
- Equity curve shows reasonable progression

### Test File 6: `test_strategy_empty_simulation.csv`
**Purpose:** Ultimate test - empty file, pure simulation
```csv
Date,Daily_Return_Pct
```
**Expected:**
- Error: "Cannot upload empty strategy. At least 1 data row required."
- Alternative: If we want to support simulations, generate random walk data

### Test File 7: `test_strategy_incremental_time.csv`
**Purpose:** Extend existing data with new dates
```csv
Date,Daily_Return_Pct,Account_Equity,Daily_PnL,Max_Margin_Used,Max_Notional_Value
2025-01-04,1.5,101084,1494,40434,121302
2025-01-05,-0.5,100577,-507,20115,60346
```
**Expected:**
- Detects: "Strategy already has data until 2025-01-03"
- Merges new dates: 2025-01-04, 2025-01-05
- Recalculates hash
- Invalidates existing allocations

### Test File 8: `test_strategy_incremental_columns.csv`
**Purpose:** Add missing columns to existing minimal data
```csv
Date,Daily_Return_Pct,Max_Margin_Used
2025-01-01,2.5,78000
2025-01-02,-1.2,48000
2025-01-03,0.8,32000
```
**Expected:**
- Detects: "New column Max_Margin_Used found"
- Backfills old rows with synthetic Max_Margin_Used
- New rows use real Max_Margin_Used from upload
- Recalculates hash
- Invalidates allocations

### Test File 9: `test_strategy_overlap_conflict.csv`
**Purpose:** Upload overlapping dates without force_replace
```csv
Date,Daily_Return_Pct,Account_Equity,Daily_PnL,Max_Margin_Used,Max_Notional_Value
2025-01-03,0.8,99590,790,31836,95508
2025-01-04,1.5,101084,1494,40434,121302
```
**Expected:**
- Error: "Date 2025-01-03 already exists. Enable 'Force Replace' to overwrite."
- Upload blocked until user checks force_replace flag

### Test File 10: `test_strategy_overlap_force.csv`
**Purpose:** Same as #9 but with force_replace=true
```csv
Date,Daily_Return_Pct,Account_Equity,Daily_PnL,Max_Margin_Used,Max_Notional_Value
2025-01-03,1.2,99800,1000,40000,120000
2025-01-04,1.5,101297,1497,41000,123000
```
**Expected:**
- Warning: "Replacing existing data for 1 date(s)"
- 2025-01-03 data replaced with new values
- 2025-01-04 appended as new row
- Hash recalculated
- Allocations invalidated

### Test File 11: `test_strategy_invalid_format.csv`
**Purpose:** Test error handling
```csv
Date,Daily_Return_Pct
2025-01-01,INVALID
2025-01-02,1.5
```
**Expected:**
- Error: "Invalid return value 'INVALID' on row 2. Must be numeric."
- Upload rejected

### Test File 12: `test_strategy_missing_required.csv`
**Purpose:** Test missing required column
```csv
Date,Account_Equity
2025-01-01,100000
2025-01-02,101500
```
**Expected:**
- Error: "Required column 'Daily_Return_Pct' missing"
- Upload rejected

---

## Unit Testing Strategy

### Backend Tests

**File:** `tests/test_backtest_upload_handler.py`

```python
def test_parse_csv_full_data()
def test_parse_csv_minimal_data()
def test_parse_csv_invalid_format()
def test_parse_csv_missing_required_column()

def test_normalize_returns_percentage()
def test_normalize_returns_decimal()
def test_normalize_returns_mixed()

def test_detect_columns_all_present()
def test_detect_columns_missing_margin()
def test_detect_columns_minimal()

def test_generate_synthetic_account_equity()
def test_generate_synthetic_daily_pnl()
def test_generate_synthetic_margin()
def test_generate_synthetic_notional()

def test_merge_backtest_new_dates()
def test_merge_backtest_overlap_without_force()
def test_merge_backtest_overlap_with_force()
def test_merge_backtest_new_columns()

def test_calculate_backtest_hash()
def test_calculate_backtest_hash_consistency()

def test_invalidate_allocations_for_strategy()
```

**File:** `tests/test_metrics_calculator.py`

```python
def test_calculate_cagr_positive_returns()
def test_calculate_cagr_negative_returns()
def test_calculate_sharpe_ratio()
def test_calculate_max_drawdown()
def test_calculate_calmar_ratio()
def test_estimate_num_trades()
def test_calculate_all_metrics_integration()
```

### Integration Tests

**File:** `tests/integration/test_strategy_submission_flow.py`

```python
def test_full_submission_with_all_data()
def test_submission_with_minimal_data()
def test_submission_approval_creates_strategy()
def test_submission_rejection_deletes_data()
def test_incremental_update_time()
def test_incremental_update_columns()
def test_overlap_handling()
def test_allocation_invalidation()
```

### Frontend Tests

**File:** `frontend-admin/src/tests/StrategyApproval.test.tsx`

```typescript
test('renders submission list', async () => { ... })
test('displays synthetic data warnings', async () => { ... })
test('approve button creates strategy', async () => { ... })
test('reject button deletes submission', async () => { ... })
```

**File:** `mathematricks-website/src/tests/SubmitStrategy.test.tsx`

```typescript
test('renders upload form', () => { ... })
test('validates required fields', async () => { ... })
test('shows preview with metrics', async () => { ... })
test('displays synthetic column warnings', async () => { ... })
```

---

## Development Approach: Test-Driven Implementation

We'll build everything with testing in mind, following this order:

### Phase 1: Create Test Data Files
1. Generate all 12 test CSV files in `tests/test_data/strategy_uploads/`
2. Document expected outcomes for each file
3. Use these files throughout development

### Phase 2: Backend Core (TDD)
1. Write unit tests first for each function
2. Implement function to pass tests
3. Verify with test data files

### Phase 3: API Endpoints
1. Write integration tests for each endpoint
2. Implement endpoints
3. Test with actual test data files using curl/Postman

### Phase 4: Frontend Components
1. Build components with test data in mind
2. Test upload flows with all 12 test files manually
3. Write React component tests

### Phase 5: End-to-End Validation
1. Run through all 12 test files in production-like environment
2. Verify metrics, warnings, and synthetic data handling
3. Test allocation invalidation with hash mismatches

---

## Success Criteria

✅ **Public portal works**: Developers can submit strategies without repo access
✅ **Admin can review**: All submissions visible, easy approve/reject
✅ **Metrics calculated**: CAGR, Sharpe, Calmar shown automatically
✅ **Incremental updates**: Don't need to re-upload full history
✅ **Hash tracking**: Allocations tied to specific data versions
✅ **Signals blocked**: Outdated allocations can't execute
✅ **Synthetic data**: Clear warnings, system handles missing columns
✅ **CLI deprecated**: All uploads through UI
✅ **All 12 test files**: Each test file produces expected behavior
✅ **Unit tests pass**: 100% coverage for core logic functions
✅ **Integration tests pass**: All API endpoints work with test data
