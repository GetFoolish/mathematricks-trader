"""
Quick test to verify Phase 3 margin constraint is working
"""
import sys
sys.path.insert(0, '.')

from services.cerebro_service.research.construct_portfolio import load_strategies_from_mongodb, get_constructor
from services.cerebro_service.research.backtest_engine import WalkForwardBacktest
import logging

# Set logging to INFO to see margin analysis
logging.basicConfig(level=logging.INFO, format='%(message)s')

print("="*80)
print("TESTING PHASE 3: MARGIN CONSTRAINT")
print("="*80)

# Load data
print("\n[1/3] Loading strategies from MongoDB...")
strategies_data = load_strategies_from_mongodb()
print(f"  ✓ Loaded {len(strategies_data)} strategies")

# Check if margin data is present
has_margin = False
for sid, data in strategies_data.items():
    if 'margin_used' in data and any(m > 0 for m in data['margin_used']):
        has_margin = True
        print(f"  ✓ {sid}: has margin data (max=${max(data['margin_used']):,.0f})")

if not has_margin:
    print("  ❌ No margin data found!")
    sys.exit(1)

print("\n[2/3] Creating MaxHybrid constructor...")
constructor = get_constructor('max_hybrid')
print(f"  ✓ Constructor: {constructor.__class__.__name__}")
print(f"  ✓ Max Leverage: {constructor.max_leverage}")

print("\n[3/3] Running one window to test margin constraint...")
engine = WalkForwardBacktest(
    constructor=constructor,
    train_days=252,
    test_days=63,
    walk_forward_type='anchored',
    output_dir='services/cerebro_service/portfolio_constructor/max_hybrid/outputs'
)

# Run full backtest to see final results
results = engine.run(strategies_data)

print("\n" + "="*80)
print("PHASE 3 TEST RESULTS")
print("="*80)
print(f"CAGR: {results['cagr']:.2f}%")
print(f"Sharpe: {results['sharpe']:.2f}")
print(f"Max DD: {results['max_drawdown']:.2f}%")
print("\n✓ Margin constraint is working if:")
print("  1. You see '📊 Margin Analysis' in the logs above")
print("  2. You see '💰 Margin Usage' in allocation results")
print("  3. Performance differs slightly from before (constraint is active)")
print("="*80)
