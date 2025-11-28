#!/usr/bin/env python3
"""
Unified Portfolio Constructor Backtest Script

Usage:
    python services/cerebro_service/research/construct_portfolio.py --constructor max_cagr
    python services/cerebro_service/research/construct_portfolio.py --constructor max_cagr_v2
    python services/cerebro_service/research/construct_portfolio.py --constructor max_sharpe
    python services/cerebro_service/research/construct_portfolio.py --constructor max_hybrid
    python services/cerebro_service/research/construct_portfolio.py --constructor max_cagr_sharpe
    
    # Run with saved config
    python services/cerebro_service/research/construct_portfolio.py --constructor max_hybrid --config path/to/config.json

This script:
1. Loads strategy data from MongoDB
2. Runs walk-forward backtest with the specified constructor
3. Automatically generates and saves:
   - Configuration JSON (for reproducibility)
   - Portfolio equity curve CSV
   - Allocations history CSV
   - Strategy correlation matrix CSV
   - QuantStats HTML tearsheet
"""
import sys
import os
import argparse
import json
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
sys.path.insert(0, project_root)

# Load environment variables
load_dotenv(os.path.join(project_root, '.env'))

from pymongo import MongoClient
from services.cerebro_service.research.backtest_engine import WalkForwardBacktest


def load_strategies_from_mongodb(filter_strategy_ids=None):
    """Load strategy data from MongoDB (cloud).

    Args:
        filter_strategy_ids: Optional list of strategy IDs to load (default: load all)
    """
    print("\n" + "="*80)
    print("LOADING STRATEGY DATA FROM MONGODB")
    print("="*80)

    # Get MongoDB URI from environment
    mongo_uri = os.getenv('MONGODB_URI')
    if not mongo_uri:
        raise ValueError("MONGODB_URI not found in .env file")

    client = MongoClient(mongo_uri, tls=True, tlsAllowInvalidCertificates=True)
    db = client['mathematricks_trading']
    strategies_collection = db['strategies']

    # Build query filter
    query = {}
    if filter_strategy_ids:
        query['strategy_id'] = {'$in': filter_strategy_ids}
        print(f"Filtering for strategies: {filter_strategy_ids}")

    strategies_cursor = strategies_collection.find(query)
    strategies_data = {}
    
    for doc in strategies_cursor:
        strategy_id = doc.get('strategy_id') or doc.get('name') or str(doc.get('_id'))
        
        # NEW UNIFIED STRUCTURE: raw_data_backtest_full at top level
        if 'raw_data_backtest_full' in doc and isinstance(doc['raw_data_backtest_full'], list):
            raw_data = doc['raw_data_backtest_full']
            if len(raw_data) > 0 and isinstance(raw_data[0], dict):
                dates = [datetime.fromisoformat(item['date']) if isinstance(item.get('date'), str)
                        else item['date'] for item in raw_data]
                returns = [float(item['return']) for item in raw_data]
                margin_used = [float(item.get('margin_used', 0)) for item in raw_data]
                notional = [float(item.get('notional_value', 0)) for item in raw_data]
                account_equity = [float(item.get('account_equity', 100000)) for item in raw_data]
                
                strategies_data[strategy_id] = {
                    'dates': dates,
                    'returns': returns,
                    'margin_used': margin_used,
                    'notional': notional,
                    'account_equity': account_equity
                }
                print(f"  ✓ Loaded {strategy_id}: {len(returns)} days of data (unified structure)")
                continue
        
        # LEGACY STRUCTURE: backtest_data.raw_data_backtest_full
        if 'backtest_data' in doc:
            backtest_data = doc['backtest_data']
            
            # Prefer raw_data_backtest_full (has margin and notional data)
            if 'raw_data_backtest_full' in backtest_data and isinstance(backtest_data['raw_data_backtest_full'], list):
                raw_data = backtest_data['raw_data_backtest_full']
                if len(raw_data) > 0 and isinstance(raw_data[0], dict):
                    dates = [datetime.fromisoformat(item['date']) if isinstance(item.get('date'), str)
                            else item['date'] for item in raw_data]
                    returns = [float(item['return']) for item in raw_data]
                    margin_used = [float(item.get('margin_used', 0)) for item in raw_data]
                    notional = [float(item.get('notional_value', 0)) for item in raw_data]
                    account_equity = [float(item.get('account_equity', 100000)) for item in raw_data]
                    
                    strategies_data[strategy_id] = {
                        'dates': dates,
                        'returns': returns,
                        'margin_used': margin_used,
                        'notional': notional,
                        'account_equity': account_equity
                    }
                    print(f"  ✓ Loaded {strategy_id}: {len(returns)} days of data (legacy structure)")
                    continue
            
            # Fallback to daily_returns (backward compatibility)
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
                        'returns': returns,
                        'margin_used': [0] * len(returns),  # Not available in old format
                        'notional': [0] * len(returns),      # Not available in old format
                        'account_equity': [100000] * len(returns)  # Not available in old format
                    }
                    print(f"  ✓ Loaded {strategy_id}: {len(returns)} days of data (legacy daily_returns)")
    
    print(f"\n  ✓ Total strategies loaded: {len(strategies_data)}")
    
    client.close()
    return strategies_data


def get_constructor(constructor_name: str, config_path: str = None):
    """
    Dynamically import and instantiate the requested constructor.
    
    Args:
        constructor_name: Name of constructor (e.g., 'max_cagr', 'max_sharpe')
        config_path: Optional path to config JSON file to override parameters
        
    Returns:
        Instantiated constructor object
    """
    constructor_map = {
        'max_cagr': 'services.cerebro_service.portfolio_constructor.max_cagr.strategy',
        'max_cagr_v2': 'services.cerebro_service.portfolio_constructor.max_cagr_v2.strategy',
        'max_sharpe': 'services.cerebro_service.portfolio_constructor.max_sharpe.strategy',
        'max_hybrid': 'services.cerebro_service.portfolio_constructor.max_hybrid.strategy',
        'max_cagr_sharpe': 'services.cerebro_service.portfolio_constructor.max_cagr_sharpe.strategy',
    }
    
    class_name_map = {
        'max_cagr': 'MaxCAGRConstructor',
        'max_cagr_v2': 'MaxCAGRV2Constructor',
        'max_sharpe': 'MaxSharpeConstructor',
        'max_hybrid': 'MaxHybridConstructor',
        'max_cagr_sharpe': 'MaxCAGRSharpeConstructor',
    }
    
    if constructor_name not in constructor_map:
        available = ', '.join(constructor_map.keys())
        raise ValueError(f"Unknown constructor: {constructor_name}. Available: {available}")
    
    # Dynamic import
    module_path = constructor_map[constructor_name]
    class_name = class_name_map[constructor_name]
    
    module = __import__(module_path, fromlist=[class_name])
    constructor_class = getattr(module, class_name)
    
    # Load config if provided
    constructor_params = {}
    if config_path:
        print(f"\n📄 Loading config from: {config_path}")
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Extract constructor parameters from config
        if 'constructor' in config and 'config' in config['constructor']:
            constructor_params = config['constructor']['config']
            # Remove metadata fields that aren't constructor parameters
            constructor_params.pop('type', None)
            
            print(f"  ✓ Loaded constructor config:")
            for key, value in constructor_params.items():
                print(f"    - {key}: {value}")
    
    # Instantiate constructor with config parameters
    if constructor_params:
        constructor = constructor_class(**constructor_params)
        print(f"\n✓ Loaded constructor: {class_name} (with config overrides)")
    else:
        constructor = constructor_class()
        print(f"\n✓ Loaded constructor: {class_name} (default parameters)")
    
    return constructor


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Run portfolio constructor backtest',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default parameters
  python services/cerebro_service/research/construct_portfolio.py --constructor max_cagr
  python services/cerebro_service/research/construct_portfolio.py --constructor max_sharpe
  python services/cerebro_service/research/construct_portfolio.py --constructor max_hybrid
  
  # Run with saved config (parameters will be overridden)
  python services/cerebro_service/research/construct_portfolio.py --constructor max_hybrid --config path/to/config.json
  
Available constructors:
  - max_cagr: Maximize CAGR with drawdown constraint
  - max_cagr_v2: Improved MaxCAGR with proper mean calculation
  - max_sharpe: Maximize Sharpe ratio (risk-adjusted returns)
  - max_hybrid: Balanced multi-objective (Sharpe + CAGR)
  - max_cagr_sharpe: Maximize CAGR with Sharpe constraint
        """
    )
    
    parser.add_argument(
        '--constructor',
        type=str,
        required=True,
        choices=['max_cagr', 'max_cagr_v2', 'max_sharpe', 'max_hybrid', 'max_cagr_sharpe'],
        help='Portfolio constructor to test'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='Path to config JSON file (overrides constructor default parameters)'
    )
    
    parser.add_argument(
        '--train-days',
        type=int,
        default=252,
        help='Training window size in days (default: 252)'
    )
    
    parser.add_argument(
        '--test-days',
        type=int,
        default=63,
        help='Test window size in days (default: 63)'
    )
    
    parser.add_argument(
        '--walk-forward-type',
        type=str,
        default='anchored',
        choices=['anchored', 'rolling'],
        help='Walk-forward type: anchored (expanding) or rolling (default: anchored)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Output directory for results (default: auto-detect from constructor path)'
    )

    parser.add_argument(
        '--strategies',
        type=str,
        default=None,
        help='Comma-separated list of strategy IDs to include (default: all active strategies)'
    )

    args = parser.parse_args()

    # Parse strategy filter list
    filter_strategies = None
    if args.strategies:
        filter_strategies = [s.strip() for s in args.strategies.split(',')]

    # Print header
    print("\n" + "="*80)
    print("PORTFOLIO CONSTRUCTOR BACKTEST")
    print("="*80)
    print(f"Constructor: {args.constructor}")
    if args.config:
        print(f"Config File: {args.config}")
    print(f"Train Days: {args.train_days}")
    print(f"Test Days: {args.test_days}")
    print(f"Walk-Forward: {args.walk_forward_type}")
    if args.output_dir:
        print(f"Output Dir: {args.output_dir}")
    else:
        print(f"Output Dir: Auto-detect from constructor")
    if filter_strategies:
        print(f"Strategy Filter: {', '.join(filter_strategies)}")
    print("="*80)

    try:
        # Load strategies from MongoDB
        strategies_data = load_strategies_from_mongodb(filter_strategy_ids=filter_strategies)
        
        if not strategies_data:
            print("\n❌ No strategy data found in MongoDB")
            return 1
        
        # Get constructor (with optional config override)
        constructor = get_constructor(args.constructor, args.config)
        
        # Initialize backtest engine
        backtest = WalkForwardBacktest(
            constructor=constructor,
            train_days=args.train_days,
            test_days=args.test_days,
            walk_forward_type=args.walk_forward_type,
            output_dir=args.output_dir
        )
        
        # Run backtest (automatically saves all outputs)
        results = backtest.run(strategies_data)
        
        # Print summary
        print("\n" + "="*80)
        print("BACKTEST COMPLETE")
        print("="*80)
        metrics = results['metrics']
        print(f"\nPerformance Metrics:")
        print(f"  Total Days:      {metrics['total_days']}")
        print(f"  Years:           {metrics['total_days']/252:.2f}")
        print(f"  Total Return:    {metrics['total_return_pct']:.2f}%")
        print(f"  CAGR:            {metrics['cagr_pct']:.2f}%")
        print(f"  Sharpe Ratio:    {metrics['sharpe_ratio']:.2f}")
        print(f"  Max Drawdown:    {metrics['max_drawdown_pct']:.2f}%")
        print(f"  Annual Vol:      {metrics['annual_volatility_pct']:.2f}%")
        
        print("\n" + "="*80)
        print("✓ SUCCESS - All outputs saved!")
        print("="*80)
        
        return 0
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
