# Strategy Submission System - Testing Guide

## Overview

This guide walks you through testing the complete strategy submission and approval workflow.

## System Components

### Backend (✅ Complete)
- **Service**: PortfolioBuilder (port 8003)
- **File**: `services/portfolio_builder/main.py`
- **Endpoints**: 8 new endpoints for public submission and admin approval
- **Collections**: `uploaded_strategies`, `strategies`, `portfolio_allocations`

### CLI Script (✅ Complete)
- **File**: `scripts/upload_strategy.py`
- **Purpose**: Command-line tool for testing strategy uploads
- **Features**: Colorized output, formatted tearsheet, metrics display

### Frontend Admin (✅ Complete)
- **Page**: `frontend-admin/src/pages/StrategyApproval.tsx`
- **Route**: `/strategy-approval`
- **Features**: Review queue, approval/rejection modals, metrics dashboard

---

## Testing Workflow

### Prerequisites

1. **MongoDB Running**
   ```bash
   # Check if MongoDB is running
   mongosh --eval "db.runCommand({ ping: 1 })"
   ```

2. **Backend Service Running**
   ```bash
   # Start PortfolioBuilder service
   .venv/bin/python services/portfolio_builder/main.py

   # Should see:
   # PortfolioBuilder Service Starting
   # Uvicorn running on http://0.0.0.0:8003
   ```

3. **Frontend Running**
   ```bash
   cd frontend-admin
   npm run dev

   # Should see:
   # Local: http://localhost:5173
   ```

---

## Step 1: Upload Strategy via CLI

Use the CLI script to upload a test strategy:

```bash
.venv/bin/python scripts/upload_strategy.py \
  --file tests/test_data/strategy_uploads/test_strategy_full_data.csv \
  --name "John Doe" \
  --email "john@example.com" \
  --note "High-performance SPX momentum strategy" \
  --strategy-name "SPX Momentum Test"
```

### Expected Output

```
================================================================================
                              STRATEGY UPLOAD
================================================================================

Upload Details:
  File:           test_strategy_full_data.csv
  Strategy Name:  SPX Momentum Test
  Developer:      John Doe <john@example.com>
  Note:           High-performance SPX momentum strategy
  Starting Capital: $1,000,000.00
  API URL:        http://localhost:8003

ℹ Uploading to http://localhost:8003/api/v1/public/submit-strategy...
✓ Strategy uploaded successfully!

================================================================================
                   STRATEGY PERFORMANCE TEARSHEET
================================================================================

Submission Details:
  Submission ID: sub_abc123xyz456
  Status:        PENDING_APPROVAL

Key Performance Metrics:
  CAGR:               42.50%
  Sharpe Ratio:       2.45
  Calmar Ratio:       3.12
  Max Drawdown:       -12.30%
  Total Return:       156.80%

Risk Metrics:
  Volatility (Ann.):  18.20%
  Sortino Ratio:      3.45
  Win Rate:           64.20%
  Profit Factor:      2.15

Backtest Period:
  Start Date:         2020-01-01
  End Date:           2025-12-31
  Total Days:         2,190
  Equity Curve Points: 5,000

⚠ Generated synthetic data for columns: Max_Margin_Used, Max_Notional_Value

================================================================================
                              NEXT STEPS
================================================================================
1. Your submission ID: sub_abc123xyz456
2. Status: PENDING_APPROVAL
3. Check status at: http://localhost:8003/api/v1/public/submission/sub_abc123xyz456
4. Admin will review and approve/reject your strategy

✓ Upload complete! Check your email for updates.
```

### What Happened?

1. CSV parsed and validated
2. Missing columns generated synthetically
3. Performance metrics calculated (CAGR, Sharpe, Calmar, etc.)
4. Document created in `uploaded_strategies` MongoDB collection
5. Status set to `PENDING_APPROVAL`

### Verify in MongoDB

```bash
mongosh mathematricks_trading --eval "db.uploaded_strategies.find({}).pretty()"
```

---

## Step 2: Review in Admin UI

1. **Open Frontend Admin**
   - URL: http://localhost:5173
   - Login: `admin` / `admin`

2. **Navigate to Strategy Approval**
   - Click "Strategy Approval" in left sidebar
   - Icon: CheckCircle (✓)

3. **Review Submission**
   - You should see the uploaded strategy in the table
   - Status: PENDING_APPROVAL (yellow badge)
   - Developer: John Doe <john@example.com>
   - Key metrics: CAGR, Sharpe, Calmar

4. **View Details**
   - Click the "View Details" (eye icon) button
   - Modal shows:
     - Strategy information
     - Developer info
     - Full performance metrics dashboard
     - Backtest period details
     - Synthetic data warnings

---

## Step 3: Approve Strategy

1. **Click "Approve" Button** (green checkmark icon)

2. **Fill Approval Form**:
   - **Strategy ID**: `SPX_Momentum_V1` (unique identifier)
   - **Asset Class**: Select `equity`
   - **Instruments**: Add `SPX`, `SPY` (press Enter or click Add)
   - **Status**: Select `ACTIVE` or `TESTING`
   - **Trading Mode**: Select `PAPER` or `LIVE`
   - **Include in Optimization**: Check/uncheck
   - **Notes**: Optional approval notes

3. **Click "Approve Strategy"**

### Expected Result

- ✅ Success message appears
- Strategy appears in main Strategies list
- Submission status changes to `APPROVED`
- New document created in `strategies` collection
- `backtest_data_hash` calculated and stored

### Verify Approval

Navigate to "Strategies" page and confirm the new strategy appears.

---

## Step 4: Test Rejection (Optional)

Upload another strategy and test rejection:

```bash
.venv/bin/python scripts/upload_strategy.py \
  --file tests/test_data/strategy_uploads/test_strategy_minimal.csv \
  --name "Jane Smith" \
  --email "jane@example.com" \
  --strategy-name "Test Rejection"
```

1. Go to Strategy Approval page
2. Click "Reject" button (red X icon)
3. Enter rejection reason:
   ```
   Insufficient backtest history. Strategy requires at least 2 years of data.
   ```
4. Click "Reject Strategy"

### Expected Result

- Submission status changes to `REJECTED`
- Rejection reason stored in database
- Developer could be notified (future feature)

---

## Step 5: Test with Different CSV Files

Test with various CSV formats to verify robustness:

### Full Data (All Columns)
```bash
.venv/bin/python scripts/upload_strategy.py \
  --file tests/test_data/strategy_uploads/test_strategy_full_data.csv \
  --name "Full Data Test" \
  --email "test@example.com"
```
✅ Should upload without warnings

### Minimal Data (Date + Return Only)
```bash
.venv/bin/python scripts/upload_strategy.py \
  --file tests/test_data/strategy_uploads/test_strategy_minimal.csv \
  --name "Minimal Test" \
  --email "test@example.com"
```
⚠️ Should upload with synthetic data warnings

### Missing Columns
```bash
.venv/bin/python scripts/upload_strategy.py \
  --file tests/test_data/strategy_uploads/test_strategy_missing_2cols.csv \
  --name "Missing Cols Test" \
  --email "test@example.com"
```
⚠️ Should upload with specific column warnings

### Invalid Format (Should Fail)
```bash
.venv/bin/python scripts/upload_strategy.py \
  --file tests/test_data/strategy_uploads/test_strategy_invalid_format.csv \
  --name "Invalid Test" \
  --email "test@example.com"
```
❌ Should fail with validation error

---

## API Testing (Advanced)

### Test Public Submission Endpoint

```bash
curl -X POST http://localhost:8003/api/v1/public/submit-strategy \
  -F "file=@tests/test_data/strategy_uploads/test_strategy_full_data.csv" \
  -F "strategy_name=API Test Strategy" \
  -F "developer_name=API Tester" \
  -F "developer_email=api@example.com" \
  -F "developer_note=Testing the API directly"
```

### Check Submission Status

```bash
curl http://localhost:8003/api/v1/public/submission/sub_abc123xyz456 | jq
```

### Get All Pending Submissions (Admin)

```bash
curl http://localhost:8003/api/v1/admin/submissions?status=PENDING_APPROVAL | jq
```

### Approve via API

```bash
curl -X POST http://localhost:8003/api/v1/admin/submissions/sub_abc123xyz456/approve \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_id": "API_Test_Strategy",
    "asset_class": "equity",
    "instruments": ["SPX"],
    "status": "ACTIVE",
    "trading_mode": "PAPER"
  }' | jq
```

### Reject via API

```bash
curl -X POST http://localhost:8003/api/v1/admin/submissions/sub_abc123xyz456/reject \
  -H "Content-Type": application/json" \
  -d '{
    "rejection_reason": "Test rejection via API"
  }' | jq
```

---

## Common Issues & Troubleshooting

### Issue: "Cannot connect to API at http://localhost:8003"

**Solution**: Start the backend service
```bash
.venv/bin/python services/portfolio_builder/main.py
```

### Issue: "ModuleNotFoundError: No module named 'pandas'"

**Solution**: Install dependencies
```bash
.venv/bin/pip install -r requirements.txt
```

### Issue: Frontend shows "Network Error"

**Solution**: Check CORS settings and ensure backend is running
```bash
# In services/portfolio_builder/main.py, verify:
allow_origins=["*"]  # Should allow all origins for development
```

### Issue: "Cannot upload empty strategy"

**Solution**: CSV file must have at least one data row (excluding header)

### Issue: "Required column 'Daily_Return_Pct' is missing"

**Solution**: CSV must have both `Date` and `Daily_Return_Pct` columns

---

## Success Criteria

✅ CLI script uploads strategy successfully
✅ Backend API creates submission in MongoDB
✅ Metrics calculated correctly (CAGR, Sharpe, Calmar)
✅ Synthetic data generated for missing columns
✅ Warnings displayed for synthetic columns
✅ Admin UI shows submission in review queue
✅ Details modal displays all metrics
✅ Approval form validates required fields
✅ Approved strategy appears in Strategies list
✅ Rejection stores reason in database
✅ Hash tracking implemented for backtest data

---

## Next Steps

After verifying the core workflow works:

1. **Test Incremental Updates**
   - Upload strategy with partial data
   - Later upload more dates
   - Verify hash changes and allocation invalidation

2. **Test Public Website Integration**
   - Build mathematricks-website upload form
   - Deploy to Netlify staging
   - Test end-to-end from public portal

3. **Add Email Notifications**
   - Notify developer when approved/rejected
   - Notify admin when new submission arrives

4. **Add Authentication**
   - Implement JWT auth for admin endpoints
   - Add role-based access control

---

## File Locations Reference

### Backend
- Main API: `services/portfolio_builder/main.py` (lines 340-861)
- Upload Handler: `services/portfolio_builder/backtest_upload_handler.py`
- Metrics Calculator: `services/portfolio_builder/metrics_calculator.py`

### CLI Tool
- Script: `scripts/upload_strategy.py`

### Frontend
- Approval Page: `frontend-admin/src/pages/StrategyApproval.tsx`
- API Client: `frontend-admin/src/services/api.ts` (lines 377-407)
- Types: `frontend-admin/src/types/index.ts` (lines 394-456)
- Route: `frontend-admin/src/App.tsx` (line 48)
- Navigation: `frontend-admin/src/components/Layout.tsx` (line 24)

### Test Data
- Directory: `tests/test_data/strategy_uploads/`
- Files: 13 CSV files with 5000+ rows each

---

## MongoDB Collections

### uploaded_strategies
```javascript
{
  submission_id: "sub_abc123xyz456",
  status: "PENDING_APPROVAL|APPROVED|REJECTED",
  strategy_name: "SPX Momentum Test",
  developer_info: {
    name: "John Doe",
    email: "john@example.com",
    note: "Strategy description"
  },
  raw_data_backtest_full: [...],  // Backtest data
  metrics: {...},  // Calculated metrics
  synthetic_data: {...},  // What was generated
  submitted_at: ISODate,
  reviewed_at: ISODate,
  rejection_reason: "..."  // If rejected
}
```

### strategies
```javascript
{
  strategy_id: "SPX_Momentum_V1",
  name: "SPX Momentum Test",
  asset_class: "equity",
  instruments: ["SPX", "SPY"],
  status: "ACTIVE|TESTING",
  raw_data_backtest_full: [...],
  metrics: {...},
  backtest_data_hash: "abc123...",  // SHA256 hash
  original_submission_id: "sub_abc123xyz456",
  developer_contact: {...}
}
```

---

## Questions or Issues?

If you encounter any problems:

1. Check the backend logs: `logs/portfolio_builder.log`
2. Check MongoDB collections
3. Verify API responses with curl
4. Review browser console for frontend errors

Happy testing! 🚀
