"""
Test data generators for creating realistic test data
"""

import json
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any


class SignalDataGenerator:
    """Generate realistic signal data for testing"""
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path("tests/test_data")
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_signal_file(
        self,
        symbol: str,
        num_pairs: int = 5,
        filename: str = None
    ) -> Path:
        """Generate signal JSON file with entry/exit pairs"""
        if filename is None:
            filename = f"{symbol.lower()}_signals_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        signals = []
        base_price = random.uniform(100, 200)
        
        for i in range(num_pairs):
            # Entry signal
            entry_price = base_price + random.uniform(-5, 5)
            entry = {
                "signal_id": f"sig_entry_{symbol}_{i}_{int(datetime.now().timestamp())}",
                "strategy_id": "test_strategy",
                "symbol": symbol,
                "action": "ENTRY",
                "signal_type": "LONG",
                "timestamp": (datetime.now(timezone.utc) + timedelta(minutes=i*60)).isoformat(),
                "price": round(entry_price, 2),
                "quantity": random.choice([50, 100, 150, 200]),
                "stop_loss": round(entry_price * 0.97, 2),
                "take_profit": round(entry_price * 1.05, 2),
                "status": "PENDING",
                "metadata": {
                    "confidence": round(random.uniform(0.7, 0.95), 2),
                    "source": "test_generator"
                }
            }
            signals.append(entry)
            
            # Exit signal
            exit_price = entry_price * random.uniform(0.98, 1.06)
            exit_signal = {
                "signal_id": f"sig_exit_{symbol}_{i}_{int(datetime.now().timestamp())}",
                "strategy_id": "test_strategy",
                "symbol": symbol,
                "action": "EXIT",
                "signal_type": "LONG",
                "timestamp": (datetime.now(timezone.utc) + timedelta(minutes=i*60+30)).isoformat(),
                "price": round(exit_price, 2),
                "quantity": entry["quantity"],
                "status": "PENDING",
                "metadata": {
                    "exit_reason": random.choice(["take_profit", "stop_loss", "manual"]),
                    "source": "test_generator"
                }
            }
            signals.append(exit_signal)
        
        # Save to file
        output_path = self.output_dir / filename
        with open(output_path, 'w') as f:
            json.dump(signals, f, indent=2)
        
        return output_path
    
    def generate_batch_signal_files(
        self,
        symbols: List[str],
        signals_per_symbol: int = 10
    ) -> List[Path]:
        """Generate signal files for multiple symbols"""
        paths = []
        for symbol in symbols:
            path = self.generate_signal_file(symbol, signals_per_symbol)
            paths.append(path)
        return paths
    
    def generate_edge_case_signals(self) -> Path:
        """Generate edge case signals for testing"""
        edge_cases = [
            # Very small quantity
            {
                "signal_id": f"edge_small_qty_{int(datetime.now().timestamp())}",
                "strategy_id": "test_strategy",
                "symbol": "AAPL",
                "action": "ENTRY",
                "signal_type": "LONG",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "price": 150.00,
                "quantity": 1,
                "stop_loss": 145.00,
                "take_profit": 155.00,
                "status": "PENDING"
            },
            # Very large quantity
            {
                "signal_id": f"edge_large_qty_{int(datetime.now().timestamp())}",
                "strategy_id": "test_strategy",
                "symbol": "AAPL",
                "action": "ENTRY",
                "signal_type": "LONG",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "price": 150.00,
                "quantity": 10000,
                "stop_loss": 145.00,
                "take_profit": 155.00,
                "status": "PENDING"
            },
            # Very tight stop loss
            {
                "signal_id": f"edge_tight_stop_{int(datetime.now().timestamp())}",
                "strategy_id": "test_strategy",
                "symbol": "AAPL",
                "action": "ENTRY",
                "signal_type": "LONG",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "price": 150.00,
                "quantity": 100,
                "stop_loss": 149.90,
                "take_profit": 160.00,
                "status": "PENDING"
            },
            # Wide stop loss
            {
                "signal_id": f"edge_wide_stop_{int(datetime.now().timestamp())}",
                "strategy_id": "test_strategy",
                "symbol": "AAPL",
                "action": "ENTRY",
                "signal_type": "LONG",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "price": 150.00,
                "quantity": 100,
                "stop_loss": 100.00,
                "take_profit": 200.00,
                "status": "PENDING"
            },
            # SHORT signal
            {
                "signal_id": f"edge_short_{int(datetime.now().timestamp())}",
                "strategy_id": "test_strategy",
                "symbol": "AAPL",
                "action": "ENTRY",
                "signal_type": "SHORT",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "price": 150.00,
                "quantity": 100,
                "stop_loss": 155.00,
                "take_profit": 140.00,
                "status": "PENDING"
            }
        ]
        
        filename = f"edge_case_signals_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_path = self.output_dir / filename
        
        with open(output_path, 'w') as f:
            json.dump(edge_cases, f, indent=2)
        
        return output_path


class MarketDataGenerator:
    """Generate realistic market data for testing"""
    
    @staticmethod
    def generate_ohlcv_data(
        symbol: str,
        days: int = 30,
        base_price: float = 150.00
    ) -> List[Dict[str, Any]]:
        """Generate OHLCV (candlestick) data"""
        data = []
        current_price = base_price
        
        for i in range(days):
            date = datetime.now(timezone.utc) - timedelta(days=days - i)
            
            # Random daily movement
            daily_change = random.uniform(-0.03, 0.03)
            current_price *= (1 + daily_change)
            
            # Generate OHLC
            open_price = current_price
            high_price = open_price * random.uniform(1.00, 1.02)
            low_price = open_price * random.uniform(0.98, 1.00)
            close_price = random.uniform(low_price, high_price)
            
            data.append({
                "symbol": symbol,
                "date": date.strftime("%Y-%m-%d"),
                "timestamp": date.isoformat(),
                "open": round(open_price, 2),
                "high": round(high_price, 2),
                "low": round(low_price, 2),
                "close": round(close_price, 2),
                "volume": random.randint(1000000, 10000000)
            })
            
            current_price = close_price
        
        return data
    
    @staticmethod
    def generate_tick_data(
        symbol: str,
        num_ticks: int = 100,
        base_price: float = 150.00
    ) -> List[Dict[str, Any]]:
        """Generate tick-by-tick market data"""
        ticks = []
        current_price = base_price
        
        for i in range(num_ticks):
            timestamp = datetime.now(timezone.utc) + timedelta(seconds=i)
            
            # Small random price movement
            current_price += random.uniform(-0.10, 0.10)
            
            tick = {
                "symbol": symbol,
                "timestamp": timestamp.isoformat(),
                "last": round(current_price, 2),
                "bid": round(current_price - 0.05, 2),
                "ask": round(current_price + 0.05, 2),
                "bid_size": random.randint(100, 1000),
                "ask_size": random.randint(100, 1000),
                "volume": random.randint(100, 10000)
            }
            ticks.append(tick)
        
        return ticks


class StrategyDataGenerator:
    """Generate strategy configurations for testing"""
    
    @staticmethod
    def generate_strategies(num_strategies: int = 5) -> List[Dict[str, Any]]:
        """Generate strategy configurations"""
        strategies = []
        trading_modes = ["LIVE_PAPER", "BACKTEST", "LIVE_REAL"]
        symbols_pool = [
            ["AAPL", "GOOGL", "MSFT"],
            ["TSLA", "NVDA", "AMD"],
            ["SPY", "QQQ", "IWM"],
            ["AMZN", "META", "NFLX"]
        ]
        
        for i in range(num_strategies):
            strategy = {
                "strategy_id": f"strat_{i+1:03d}_{int(datetime.now().timestamp())}",
                "strategy_name": f"Test Strategy {i+1}",
                "is_active": random.choice([True, False]),
                "trading_mode": random.choice(trading_modes),
                "symbols": random.choice(symbols_pool),
                "max_position_size": random.choice([5000, 10000, 20000, 50000]),
                "risk_per_trade": round(random.uniform(0.01, 0.03), 3),
                "max_open_positions": random.randint(3, 10),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "description": f"Auto-generated test strategy {i+1}",
                    "author": "test_generator",
                    "version": "1.0"
                }
            }
            strategies.append(strategy)
        
        return strategies


class AccountDataGenerator:
    """Generate account data for testing"""
    
    @staticmethod
    def generate_accounts(num_accounts: int = 3) -> List[Dict[str, Any]]:
        """Generate trading account configurations"""
        accounts = []
        brokers = ["IBKR", "TD", "ALPACA"]
        account_types = ["PAPER", "LIVE"]
        
        for i in range(num_accounts):
            account = {
                "account_id": f"acc_{i+1:03d}_{int(datetime.now().timestamp())}",
                "account_name": f"Test Account {i+1}",
                "broker": random.choice(brokers),
                "account_type": random.choice(account_types),
                "is_active": True,
                "initial_balance": random.choice([50000, 100000, 250000]),
                "current_balance": random.uniform(50000, 300000),
                "credentials": {
                    "host": "localhost",
                    "port": random.choice([4001, 4002, 4003, 4004]),
                    "client_id": i + 1
                },
                "created_at": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "description": f"Auto-generated test account {i+1}"
                }
            }
            accounts.append(account)
        
        return accounts


def generate_complete_test_dataset(output_dir: Path = None) -> Dict[str, Any]:
    """Generate complete test dataset with all components"""
    if output_dir is None:
        output_dir = Path("tests/test_data/generated")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate all data types
    signal_gen = SignalDataGenerator(output_dir)
    
    symbols = ["AAPL", "GOOGL", "MSFT", "TSLA"]
    signal_files = signal_gen.generate_batch_signal_files(symbols, signals_per_symbol=10)
    edge_case_file = signal_gen.generate_edge_case_signals()
    
    strategies = StrategyDataGenerator.generate_strategies(5)
    accounts = AccountDataGenerator.generate_accounts(3)
    
    # Save strategies and accounts
    with open(output_dir / "strategies.json", 'w') as f:
        json.dump(strategies, f, indent=2)
    
    with open(output_dir / "accounts.json", 'w') as f:
        json.dump(accounts, f, indent=2)
    
    # Generate market data for each symbol
    for symbol in symbols:
        market_data = MarketDataGenerator.generate_ohlcv_data(symbol, days=30)
        with open(output_dir / f"{symbol.lower()}_market_data.json", 'w') as f:
            json.dump(market_data, f, indent=2)
    
    return {
        "signal_files": [str(f) for f in signal_files],
        "edge_case_file": str(edge_case_file),
        "strategies_file": str(output_dir / "strategies.json"),
        "accounts_file": str(output_dir / "accounts.json"),
        "output_dir": str(output_dir)
    }


if __name__ == "__main__":
    # Generate test data when run directly
    print("Generating complete test dataset...")
    result = generate_complete_test_dataset()
    print(f"\nTest data generated in: {result['output_dir']}")
    print(f"Signal files: {len(result['signal_files'])}")
    print(f"Edge case file: {result['edge_case_file']}")
    print(f"Strategies file: {result['strategies_file']}")
    print(f"Accounts file: {result['accounts_file']}")
