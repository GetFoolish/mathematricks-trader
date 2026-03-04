// Consolidate MOCK accounts and fix fund structure
db = db.getSiblingDB('mathematricks_trading');

print("=== BEFORE ===");
print("Trading accounts (mock):", db.trading_accounts.countDocuments({account_type: "mock"}));
print("Funds:", JSON.stringify(db.funds.find({}, {fund_id: 1, accounts: 1}).toArray(), null, 2));

// 1. Delete redundant MOCK accounts (keep IBKR-MOCK, delete others)
print("\n=== Deleting redundant MOCK accounts ===");
const redundantAccounts = ["BINANCE_MOCK", "VANTAGE_MOCK", "BYBIT_MOCK", "OANDA_MOCK"];
redundantAccounts.forEach(acc => {
    const result = db.trading_accounts.deleteOne({account_id: acc});
    print(`Deleted ${acc}: ${result.deletedCount} document(s)`);
});

// 2. Add IBKR-TESTING-ACCOUNT to mock-fund-1 for unified testing
print("\n=== Adding IBKR-TESTING-ACCOUNT to mock-fund-1 ===");
db.funds.updateOne(
    {fund_id: "mock-fund-1"},
    {
        $set: {
            accounts: ["IBKR-MOCK", "IBKR-TESTING-ACCOUNT"],
            updated_at: new Date()
        }
    }
);

// 3. Update IBKR-TESTING-ACCOUNT fund_id
print("\n=== Updating IBKR-TESTING-ACCOUNT fund_id ===");
db.trading_accounts.updateOne(
    {account_id: "IBKR-TESTING-ACCOUNT"},
    {
        $set: {
            fund_id: "mock-fund-1",
            updated_at: new Date()
        }
    }
);

// 4. Archive ibkr-testing fund (no longer needed)
print("\n=== Archiving ibkr-testing fund ===");
db.funds.updateOne(
    {fund_id: "ibkr-testing"},
    {
        $set: {
            status: "ARCHIVED",
            accounts: [],
            updated_at: new Date(),
            archived_reason: "Consolidated into mock-fund-1 for unified multi-mode testing"
        }
    }
);

print("\n=== AFTER ===");
print("Trading accounts (mock):", db.trading_accounts.countDocuments({account_type: "mock"}));
print("Trading accounts (paper):", db.trading_accounts.countDocuments({account_type: "paper"}));
print("Funds (ACTIVE):", JSON.stringify(db.funds.find({status: "ACTIVE"}, {fund_id: 1, accounts: 1}).toArray(), null, 2));
print("\n✅ Account consolidation complete!");
