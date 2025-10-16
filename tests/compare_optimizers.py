"""
Compare portfolio_optimizer.py vs MaxCAGRConstructor
Test both with same strategies and constraints to identify differences
"""
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from services.cerebro_service.portfolio_optimizer import optimize_portfolio
from services.cerebro_service.portfolio_constructor.max_cagr.strategy import MaxCAGRConstructor
from services.cerebro_service.portfolio_constructor.context import PortfolioContext

# Load environment
load_dotenv(os.path.join(project_root, '.env'))


def load_strategies_from_mongodb():
    """Load strategy data from MongoDB"""
    mongo_uri = os.getenv('MONGODB_URI')
    client = MongoClient(mongo_uri, tls=True, tlsAllowInvalidCertificates=True)
    db = client['mathematricks_trading']
    strategies_collection = db['strategies']
    
    strategies_cursor = strategies_collection.find({})
    strategies_data = {}
    
    for doc in strategies_cursor:
        strategy_id = doc.get('strategy_id') or doc.get('name') or str(doc.get('_id'))
        
        if 'backtest_data' not in doc:
            continue
            
        backtest_data = doc['backtest_data']
        
        if 'daily_returns' in backtest_data and isinstance(backtest_data['daily_returns'], list):
            daily_returns = backtest_data['daily_returns']
            if len(daily_returns) > 0:
                if isinstance(daily_returns[0], dict):
                    dates = [datetime.fromisoformat(item['date']) if isinstance(item.get('date'), str)
                            else item['date'] for item in daily_returns]
                    returns = [float(item['return']) for item in daily_returns]
                else:
                    if 'dates' in backtest_data:
                        dates = [datetime.fromisoformat(d) if isinstance(d, str) else d 
                                for d in backtest_data['dates']]
                        returns = [float(r) for r in daily_returns]
                    else:
                        continue
                
                strategies_data[strategy_id] = {
                    'dates': dates,
                    'returns': returns
                }
    
    return strategies_data


def test_optimizer_comparison():
    """Compare both optimizers with same data"""
    print("="*80)
    print("OPTIMIZER COMPARISON TEST")
    print("="*80)
    
    # Load strategies
    print("\n[1/4] Loading strategy data from MongoDB...")
    strategies_data = load_strategies_from_mongodb()
    
    for strategy_id, data in strategies_data.items():
        print(f"  ✓ Loaded {strategy_id}: {len(data['returns'])} days of data")
    
    print(f"\n  Total strategies loaded: {len(strategies_data)}")
    
    # Align all strategies to common period
    print("\n[2/4] Aligning strategies to common period...")
    min_length = min(len(data['returns']) for data in strategies_data.values())
    print(f"  Common period: {min_length} days")
    
    # Prepare data for both optimizers
    aligned_data = {}
    for sid, data in strategies_data.items():
        returns = data['returns'][-min_length:]
        aligned_data[sid] = {
            'daily_returns': returns,
            'mean_return_daily': np.mean(returns),
            'volatility_daily': np.std(returns)
        }
    
    # Test configurations
    test_configs = [
        {'max_dd': 0.20, 'label': '20% Max DD'},
        {'max_dd': 0.35, 'label': '35% Max DD'},
    ]
    
    results_table = []
    
    for config in test_configs:
        max_dd = config['max_dd']
        label = config['label']
        
        print(f"\n[3/4] Testing with {label}...")
        print("-" * 80)
        
        # Test 1: portfolio_optimizer.py (max_cagr_drawdown mode)
        print(f"\n  A) portfolio_optimizer.py (max_cagr_drawdown mode):")
        allocations_optimizer = optimize_portfolio(
            strategies=aligned_data,
            max_leverage=2.0,
            max_single_strategy=1.0,
            mode="max_cagr_drawdown",
            max_drawdown_limit=-max_dd  # portfolio_optimizer uses negative values
        )
        
        # Calculate metrics for portfolio_optimizer result
        strategy_ids = list(allocations_optimizer.keys())
        weights = np.array([allocations_optimizer[sid] / 100 for sid in strategy_ids])
        returns_list = [aligned_data[sid]['daily_returns'] for sid in strategy_ids]
        returns_matrix = np.array(returns_list).T
        portfolio_returns_opt = np.dot(returns_matrix, weights)
        
        cumulative_opt = np.cumprod(1 + portfolio_returns_opt)
        running_max_opt = np.maximum.accumulate(cumulative_opt)
        drawdown_opt = (cumulative_opt - running_max_opt) / running_max_opt
        max_dd_opt = drawdown_opt.min()
        
        cagr_opt = ((cumulative_opt[-1]) ** (252 / len(portfolio_returns_opt)) - 1) * 100
        
        mean_ret_opt = np.mean(portfolio_returns_opt)
        std_ret_opt = np.std(portfolio_returns_opt)
        sharpe_opt = (mean_ret_opt / std_ret_opt * np.sqrt(252)) if std_ret_opt > 0 else 0
        
        total_alloc_opt = sum(allocations_optimizer.values())
        
        print(f"     CAGR: {cagr_opt:.2f}%")
        print(f"     Max DD: {max_dd_opt*100:.2f}%")
        print(f"     Sharpe: {sharpe_opt:.2f}")
        print(f"     Total Allocation: {total_alloc_opt:.1f}%")
        print(f"     Active Strategies: {len([v for v in allocations_optimizer.values() if v > 0.01])}")
        
        # Test 2: MaxCAGRConstructor
        print(f"\n  B) MaxCAGRConstructor:")
        constructor = MaxCAGRConstructor(
            max_leverage=2.0,
            max_drawdown_limit=max_dd,  # MaxCAGRConstructor uses positive values
            rebalance_frequency='monthly',
            risk_free_rate=0.0
        )
        
        # Create context with strategy histories
        strategy_histories = {}
        for sid, data in aligned_data.items():
            df = pd.DataFrame({
                'returns': data['daily_returns']
            })
            strategy_histories[sid] = df
        
        context = PortfolioContext(
            strategy_histories=strategy_histories,
            account_equity=1000000.0,
            margin_used=0.0,
            margin_available=1000000.0,
            cash_balance=1000000.0,
            open_positions={},
            open_orders={},
            current_allocations={},
            is_backtest=True
        )
        
        allocations_constructor = constructor.allocate_portfolio(context)
        
        # Calculate metrics for constructor result
        strategy_ids_cons = list(allocations_constructor.keys())
        weights_cons = np.array([allocations_constructor[sid] / 100 for sid in strategy_ids_cons])
        returns_list_cons = [aligned_data[sid]['daily_returns'] for sid in strategy_ids_cons]
        returns_matrix_cons = np.array(returns_list_cons).T
        portfolio_returns_cons = np.dot(returns_matrix_cons, weights_cons)
        
        cumulative_cons = np.cumprod(1 + portfolio_returns_cons)
        running_max_cons = np.maximum.accumulate(cumulative_cons)
        drawdown_cons = (cumulative_cons - running_max_cons) / running_max_cons
        max_dd_cons = drawdown_cons.min()
        
        cagr_cons = ((cumulative_cons[-1]) ** (252 / len(portfolio_returns_cons)) - 1) * 100
        
        mean_ret_cons = np.mean(portfolio_returns_cons)
        std_ret_cons = np.std(portfolio_returns_cons)
        sharpe_cons = (mean_ret_cons / std_ret_cons * np.sqrt(252)) if std_ret_cons > 0 else 0
        
        total_alloc_cons = sum(allocations_constructor.values())
        
        print(f"     CAGR: {cagr_cons:.2f}%")
        print(f"     Max DD: {max_dd_cons*100:.2f}%")
        print(f"     Sharpe: {sharpe_cons:.2f}")
        print(f"     Total Allocation: {total_alloc_cons:.1f}%")
        print(f"     Active Strategies: {len([v for v in allocations_constructor.values() if v > 0.01])}")
        
        # Store results
        results_table.append({
            'Config': label,
            'Optimizer': 'portfolio_optimizer.py',
            'CAGR': f"{cagr_opt:.2f}%",
            'Max DD': f"{max_dd_opt*100:.2f}%",
            'Sharpe': f"{sharpe_opt:.2f}",
            'Total Alloc': f"{total_alloc_opt:.1f}%",
            'Active': len([v for v in allocations_optimizer.values() if v > 0.01])
        })
        
        results_table.append({
            'Config': label,
            'Optimizer': 'MaxCAGRConstructor',
            'CAGR': f"{cagr_cons:.2f}%",
            'Max DD': f"{max_dd_cons*100:.2f}%",
            'Sharpe': f"{sharpe_cons:.2f}",
            'Total Alloc': f"{total_alloc_cons:.1f}%",
            'Active': len([v for v in allocations_constructor.values() if v > 0.01])
        })
        
        # Compare allocations
        print(f"\n  Allocation Comparison:")
        print(f"  {'Strategy':<20} {'portfolio_optimizer':>18} {'MaxCAGRConstructor':>18}")
        print("  " + "-" * 58)
        
        all_strategies = set(allocations_optimizer.keys()) | set(allocations_constructor.keys())
        for sid in sorted(all_strategies):
            opt_val = allocations_optimizer.get(sid, 0.0)
            cons_val = allocations_constructor.get(sid, 0.0)
            diff = abs(opt_val - cons_val)
            marker = " ⚠️" if diff > 5.0 else ""
            print(f"  {sid:<20} {opt_val:>17.2f}% {cons_val:>17.2f}%{marker}")
    
    # Print summary table
    print("\n" + "="*80)
    print("RESULTS SUMMARY")
    print("="*80)
    df = pd.DataFrame(results_table)
    print(df.to_string(index=False))
    
    # Mathematical analysis
    print("\n" + "="*80)
    print("MATHEMATICAL ANALYSIS")
    print("="*80)
    
    print("\n1. Objective Function Differences:")
    print("   portfolio_optimizer.py:")
    print("   - Uses portfolio_negative_cagr() - actual CAGR calculation")
    print("   - CAGR = (total_return ** (1/years)) - 1")
    print("")
    print("   MaxCAGRConstructor:")
    print("   - Uses negative mean return as approximation")
    print("   - Objective = -np.dot(weights, mean_returns)")
    print("   - ⚠️  MEAN RETURN ≠ CAGR (geometric vs arithmetic mean)")
    
    print("\n2. Drawdown Constraint Implementation:")
    print("   Both use same math:")
    print("   - Calculate cumulative returns from weights")
    print("   - Find running max")
    print("   - Calculate drawdown series")
    print("   - Return max_dd + limit (or max_dd - limit in portfolio_optimizer)")
    
    print("\n3. Key Difference Found:")
    print("   ⚠️  MaxCAGRConstructor optimizes MEAN return (arithmetic)")
    print("   ✓  portfolio_optimizer optimizes CAGR (geometric)")
    print("   → For volatile returns, geometric mean < arithmetic mean")
    print("   → This explains why CAGR doesn't increase with looser DD constraint")
    
    return results_table


if __name__ == "__main__":
    test_optimizer_comparison()
