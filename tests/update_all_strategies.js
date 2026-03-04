// Update ALL strategies to mode-specific account format
db = db.getSiblingDB('mathematricks_trading');

print("=== UPDATING ALL STRATEGIES TO MODE-SPECIFIC FORMAT ===\n");

// Get all strategies
const strategies = db.strategies.find({}).toArray();
print(`Found ${strategies.length} strategies\n`);

strategies.forEach(strat => {
    const strategyId = strat.strategy_id;
    const currentAccounts = strat.accounts;
    
    // Skip if already in new format (has object with mock/paper/live keys)
    if (currentAccounts && typeof currentAccounts === 'object' && !Array.isArray(currentAccounts)) {
        print(`⏭️  SKIP: ${strategyId} - already in mode-specific format`);
        return;
    }
    
    // Convert legacy flat array to mode-specific format
    let newAccounts;
    
    if (!currentAccounts || currentAccounts.length === 0) {
        // No accounts - set empty for all modes
        newAccounts = {
            mock: [],
            paper: [],
            live: []
        };
        print(`📝 UPDATE: ${strategyId} - was empty, setting empty for all modes`);
    } else if (Array.isArray(currentAccounts)) {
        // Has accounts in legacy format
        // Determine account types from the account IDs
        const mockAccounts = currentAccounts.filter(a => a.includes('MOCK'));
        const paperAccounts = currentAccounts.filter(a => a.includes('TESTING'));
        const liveAccounts = currentAccounts.filter(a => !a.includes('MOCK') && !a.includes('TESTING'));
        
        newAccounts = {
            mock: mockAccounts.length > 0 ? mockAccounts : ["IBKR-MOCK"],
            paper: paperAccounts.length > 0 ? paperAccounts : ["IBKR-TESTING-ACCOUNT"],
            live: liveAccounts.length > 0 ? liveAccounts : []
        };
        
        print(`📝 UPDATE: ${strategyId}`);
        print(`   Legacy: [${currentAccounts.join(', ')}]`);
        print(`   New mock: [${newAccounts.mock.join(', ')}]`);
        print(`   New paper: [${newAccounts.paper.join(', ')}]`);
        print(`   New live: [${newAccounts.live.join(', ')}]`);
    }
    
    // Update the strategy
    db.strategies.updateOne(
        {strategy_id: strategyId},
        {
            $set: {
                accounts: newAccounts,
                updated_at: new Date()
            }
        }
    );
});

print("\n=== VERIFICATION ===\n");
const updated = db.strategies.find({}).toArray();
updated.forEach(strat => {
    const accts = strat.accounts;
    if (typeof accts === 'object' && !Array.isArray(accts)) {
        print(`✅ ${strat.strategy_id}:`);
        print(`   mock: [${accts.mock ? accts.mock.join(', ') : ''}]`);
        print(`   paper: [${accts.paper ? accts.paper.join(', ') : ''}]`);
        print(`   live: [${accts.live ? accts.live.join(', ') : ''}]`);
    } else {
        print(`❌ ${strat.strategy_id}: STILL IN LEGACY FORMAT!`);
    }
});

print("\n✅ Strategy account update complete!");
