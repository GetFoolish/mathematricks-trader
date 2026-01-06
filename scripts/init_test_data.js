// MongoDB initialization script for testing
// Run with: docker exec -it mathematricks-trader-mongodb-1 mongosh mathematricks < scripts/init_test_data.js

print("============================================================");
print("Initializing Test Data for Mathematricks Trader");
print("============================================================\n");

// Define all test strategies based on sample signals
const strategies = [
  {name: "SPY", asset_class: "EQUITY"},
  {name: "TLT", asset_class: "FIXED_INCOME"},
  {name: "FloridaForex", asset_class: "FOREX"},
  {name: "Com1 - Met", asset_class: "COMMODITIES"},
  {name: "Com2 - Ag", asset_class: "COMMODITIES"},
  {name: "Com3 - Mkt", asset_class: "COMMODITIES"},
  {name: "Com4 - Misc", asset_class: "COMMODITIES"},
  {name: "SPX 0DE Opt", asset_class: "OPTIONS"},
  {name: "SPX 1 - D Opt", asset_class: "OPTIONS"}
];

// 1. Create/Update Strategies
print("📝 Creating/Updating Strategies...");
let strategyCount = 0;
strategies.forEach(s => {
  const result = db.strategies.updateOne(
    {strategy_name: s.name},
    {
      $set: {
        strategy_name: s.name,
        asset_class: s.asset_class,
        status: "ACTIVE",
        updated_at: new Date()
      },
      $setOnInsert: {created_at: new Date()}
    },
    {upsert: true}
  );
  if (result.upsertedCount > 0 || result.modifiedCount > 0) {
    strategyCount++;
    print(`   ✓ ${s.name} (${s.asset_class})`);
  }
});
print(`   Total: ${strategyCount}/${strategies.length} strategies processed\n`);

// 2. Create/Update Mock Fund
print("💰 Creating/Updating Mock Fund...");
const fundResult = db.fund_allocations.updateOne(
  {fund_id: "Mock-Fund-1"},
  {
    $set: {
      fund_id: "Mock-Fund-1",
      fund_name: "Mock Fund 1",
      total_capital: 5000000,  // $5M total
      status: "ACTIVE",
      updated_at: new Date()
    },
    $setOnInsert: {created_at: new Date()}
  },
  {upsert: true}
);
print(`   ✓ Mock-Fund-1 ($5,000,000 total capital)\n`);

// 3. Create/Update Portfolio Allocations
print("📊 Creating/Updating Portfolio Allocations...");
let allocationCount = 0;
strategies.forEach(s => {
  const result = db.portfolio_allocations.updateOne(
    {fund_id: "Mock-Fund-1", strategy_name: s.name},
    {
      $set: {
        fund_id: "Mock-Fund-1",
        strategy_name: s.name,
        allocated_capital: 500000,  // $500K per strategy
        status: "ACTIVE",
        allocation_percentage: 10.0,  // 10% of $5M
        updated_at: new Date()
      },
      $setOnInsert: {created_at: new Date()}
    },
    {upsert: true}
  );
  if (result.upsertedCount > 0 || result.modifiedCount > 0) {
    allocationCount++;
    print(`   ✓ ${s.name}: $500,000 (10%)`);
  }
});
print(`   Total: ${allocationCount}/${strategies.length} allocations processed\n`);

// 4. Verify the setup
print("🔍 Verification:");
const activeStrategies = db.strategies.countDocuments({status: "ACTIVE"});
const activeFunds = db.fund_allocations.countDocuments({status: "ACTIVE"});
const activeAllocations = db.portfolio_allocations.countDocuments({status: "ACTIVE"});

print(`   • Active Strategies: ${activeStrategies}`);
print(`   • Active Funds: ${activeFunds}`);
print(`   • Active Allocations: ${activeAllocations}`);

print("\n============================================================");
print("✅ Test Data Initialization Complete!");
print("============================================================");
print("\nNext steps:");
print("  1. Run: docker-compose restart cerebro-service");
print("  2. Send test signals: make send-test-signal");
print("  3. Or run full test: make test-signals\n");
