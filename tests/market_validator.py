#!/usr/bin/env python3
"""
Market Data Validation Module
Checks live market data availability before running tests

Reuses preflight check patterns from tests/legacy/test_preflight_checks.py
"""

import sys
import json
import time
import select
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import pytz

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logger = logging.getLogger(__name__)


def check_market_hours(instrument_type: str = 'STOCK') -> Dict[str, Any]:
    """
    Check if markets are currently open for the given instrument type.
    
    Returns:
        Dict with:
          - is_open: bool
          - market_status: str
          - opens_at: datetime (if closed)
          - closes_at: datetime (if open)
    """
    ny_tz = pytz.timezone('America/New_York')
    now_ny = datetime.now(ny_tz)
    
    # Market schedules (all times in ET)
    schedules = {
        'STOCK': {
            'weekdays': [0, 1, 2, 3, 4],  # Mon-Fri
            'open_time': (9, 30),
            'close_time': (16, 0),
            'name': 'US Stock Market'
        },
        'BOND': {  # Same as stocks for bond ETFs
            'weekdays': [0, 1, 2, 3, 4],
            'open_time': (9, 30),
            'close_time': (16, 0),
            'name': 'US Bond Market'
        },
        'OPTION': {  # Same as stocks
            'weekdays': [0, 1, 2, 3, 4],
            'open_time': (9, 30),
            'close_time': (16, 0),
            'name': 'US Options Market'
        },
        'FUTURE': {  # 24/5 trading
            'weekdays': [0, 1, 2, 3, 4, 6],  # Sun evening - Fri evening
            'open_time': (18, 0),  # Sunday 6pm
            'close_time': (17, 0),  # Friday 5pm
            'name': 'Futures Market',
            '24_5': True
        },
        'FOREX': {  # 24/5 trading
            'weekdays': [0, 1, 2, 3, 4, 6],
            'open_time': (17, 0),  # Sunday 5pm
            'close_time': (17, 0),  # Friday 5pm
            'name': 'Forex Market',
            '24_5': True
        },
        'CRYPTO': {  # 24/7
            'weekdays': list(range(7)),
            'open_time': (0, 0),
            'close_time': (23, 59),
            'name': 'Crypto Market',
            '24_7': True
        }
    }
    
    schedule = schedules.get(instrument_type, schedules['STOCK'])
    
    # Check if it's a trading day
    if now_ny.weekday() not in schedule['weekdays']:
        # Calculate next open day
        days_until_open = 1
        next_day = now_ny + timedelta(days=1)
        while next_day.weekday() not in schedule['weekdays']:
            days_until_open += 1
            next_day += timedelta(days=1)
        
        next_open = next_day.replace(
            hour=schedule['open_time'][0],
            minute=schedule['open_time'][1],
            second=0,
            microsecond=0
        )
        
        return {
            'is_open': False,
            'market_status': f"{schedule['name']} is closed (weekend/holiday)",
            'opens_at': next_open,
            'current_time': now_ny
        }
    
    # Check time
    current_time = now_ny.time()
    market_open = now_ny.replace(
        hour=schedule['open_time'][0],
        minute=schedule['open_time'][1],
        second=0,
        microsecond=0
    ).time()
    market_close = now_ny.replace(
        hour=schedule['close_time'][0],
        minute=schedule['close_time'][1],
        second=0,
        microsecond=0
    ).time()
    
    # Handle 24/5 and 24/7 markets
    if schedule.get('24_5') or schedule.get('24_7'):
        # Simplified check - just verify it's a trading day
        return {
            'is_open': True,
            'market_status': f"{schedule['name']} is open (24-hour trading)",
            'current_time': now_ny
        }
    
    # Regular market hours
    if market_open <= current_time <= market_close:
        closes_at = now_ny.replace(
            hour=schedule['close_time'][0],
            minute=schedule['close_time'][1],
            second=0,
            microsecond=0
        )
        return {
            'is_open': True,
            'market_status': f"{schedule['name']} is open",
            'closes_at': closes_at,
            'current_time': now_ny
        }
    else:
        # Market closed - calculate next open
        if current_time < market_open:
            # Opens today
            opens_at = now_ny.replace(
                hour=schedule['open_time'][0],
                minute=schedule['open_time'][1],
                second=0,
                microsecond=0
            )
        else:
            # Opens next trading day
            days_until_open = 1
            next_day = now_ny + timedelta(days=1)
            while next_day.weekday() not in schedule['weekdays']:
                days_until_open += 1
                next_day += timedelta(days=1)
            
            opens_at = next_day.replace(
                hour=schedule['open_time'][0],
                minute=schedule['open_time'][1],
                second=0,
                microsecond=0
            )
        
        return {
            'is_open': False,
            'market_status': f"{schedule['name']} is closed (after hours)",
            'opens_at': opens_at,
            'current_time': now_ny
        }


def check_ibkr_gateway_running() -> bool:
    """Check if any IB Gateway containers are running"""
    try:
        result = subprocess.run(
            ['docker', 'ps', '--filter', 'name=ib-gateway', '--format', '{{.Names}}'],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        
        gateways = result.stdout.strip().split('\n')
        running_gateways = [g for g in gateways if g]
        
        return len(running_gateways) > 0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def get_next_weekly_expiry() -> datetime:
    """Get next weekly options expiry (Friday)"""
    today = datetime.now()
    days_until_friday = (4 - today.weekday()) % 7
    if days_until_friday == 0 and today.hour >= 16:  # After market close Friday
        days_until_friday = 7
    if days_until_friday == 0:
        days_until_friday = 7  # Get next Friday
    next_friday = today + timedelta(days=days_until_friday)
    return next_friday


def get_canary_instruments() -> Dict[str, Dict[str, Any]]:
    """
    Get canary instruments for market validation.
    Returns simple, highly liquid instruments for each asset class.
    """
    next_friday = get_next_weekly_expiry()
    
    canaries = {
        'STOCK': {
            'instrument': 'SPY',
            'instrument_type': 'STOCK'
        },
        
        'BOND': {
            'instrument': 'TLT',
            'instrument_type': 'STOCK'  # Bond ETF traded as stock
        },
        
        'OPTION': {
            'instrument': 'SPY',
            'instrument_type': 'OPTION',
            'strike': 700.0,  # ATM strike for SPY ~$693
            'right': 'CALL',
            'expiry': next_friday.strftime('%Y%m%d'),
            'multiplier': 100
        },
        
        'FUTURE': {
            'instrument': 'ES',  # E-mini S&P 500
            'instrument_type': 'FUTURE',
            'exchange': 'CME',
            'multiplier': 50,
            'currency': 'USD'
        },
        
        'FOREX': {
            'instrument': 'EUR.USD',  # EURUSD pair
            'instrument_type': 'FOREX',
            'exchange': 'IDEALPRO'
        },
        
        # Skip crypto for now - not available in IBKR paper
        'CRYPTO': None
    }
    
    return canaries


def get_broker_config(broker_name: str) -> Optional[Dict[str, Any]]:
    """
    Fetch broker configuration from trading_accounts MongoDB collection.
    Returns config dict or None if not found.
    
    Note: Adjusts host from Docker network name to localhost for Mac execution.
    """
    try:
        import pymongo
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        mongodb_uri = os.getenv('MONGODB_URI_LOCAL') or os.getenv('MONGODB_URI') or 'mongodb://localhost:27018'
        
        client = pymongo.MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        db = client['mathematricks_trading']
        accounts_col = db['trading_accounts']
        
        # Map broker names to account queries
        broker_mapping = {
            'ibkr_paper': {'broker': 'IBKR', 'account_type': 'paper'},
            'ibkr_live': {'broker': 'IBKR', 'account_type': 'live'},
        }
        
        query = broker_mapping.get(broker_name, {})
        if not query:
            return None
        
        account = accounts_col.find_one(query)
        if not account:
            return None
        
        # Extract broker auth details (try both auth_details and authentication_details)
        auth = account.get('auth_details') or account.get('authentication_details', {})
        
        # Convert Docker network hostname to localhost for Mac testing
        host = auth.get('host', '127.0.0.1')
        if 'ib-gateway' in host:
            host = '127.0.0.1'
        
        # Get port from Docker container if needed
        port = auth.get('port', 4002)
        if 'ib-gateway' in auth.get('host', ''):
            # Try to get mapped port from Docker
            try:
                container_name = auth.get('host')
                result = subprocess.run(
                    ['docker', 'port', container_name, str(port)],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    # Output format: "0.0.0.0:53420"
                    mapped = result.stdout.strip().split(':')[-1]
                    if mapped.isdigit():
                        port = int(mapped)
                        logger.info(f"Using mapped port {port} for {container_name}")
            except:
                pass
        
        return {
            'broker': account.get('broker'),
            'host': host,
            'port': port,
            'client_id': 999,  # Use unique client_id for testing (avoid conflicts with execution service)
            'account_id': account.get('account_id')
        }
    
    except Exception as e:
        logger.error(f"Failed to fetch broker config: {e}")
        return None


def check_market_data_availability(signals_folder: Path, broker_name: str, file_filter: str = None) -> Dict[str, Any]:
    """
    Check market data availability for signals by querying the execution service.
    
    This validates:
    1. Markets are open
    2. Broker connections in execution service are healthy
    3. Market data is available (via canary check)
    
    Args:
        signals_folder: Path to folder containing signal JSON files
        broker_name: Broker to use for validation (ibkr_paper, ibkr_live, etc.)
        file_filter: Optional filename to filter (e.g., "crypto_signals.json")
    
    Returns dict with:
    - asset_classes: Dict of asset class → status
    - signals: List of signals with availability status
    - summary: Counts of tradeable/queued/skipped
    """
    print("\n" + "="*80)
    print("📊 MARKET DATA VALIDATION")
    print("="*80)
    
    # Load signals (filter by specific file if provided)
    if file_filter:
        signal_files = [signals_folder / file_filter]
    else:
        signal_files = list(signals_folder.glob('*.json'))
    
    all_signals = []
    
    for file in signal_files:
        if not file.exists():
            continue
        try:
            with open(file, 'r') as f:
                signals_in_file = json.load(f)
                if isinstance(signals_in_file, list):
                    for sig in signals_in_file:
                        sig['_source_file'] = file.name
                        all_signals.append(sig)
                else:
                    signals_in_file['_source_file'] = file.name
                    all_signals.append(signals_in_file)
        except Exception as e:
            logger.error(f"Failed to load {file.name}: {e}")
    
    if not all_signals:
        return {
            'asset_classes': {},
            'signals': [],
            'summary': {'tradeable': 0, 'queued': 0, 'skipped': 0, 'total': 0}
        }
    
    # Query execution service for market status instead of creating our own connection
    print(f"\n🔌 Checking execution service market status...")
    
    try:
        import requests
        response = requests.get('http://localhost:8083/market_status', timeout=10)
        
        if response.status_code != 200:
            print(f"   ❌ Execution service returned {response.status_code}")
            return {
                'asset_classes': {},
                'signals': [],
                'summary': {'tradeable': 0, 'queued': 0, 'skipped': len(all_signals), 'total': len(all_signals)}
            }
        
        market_data = response.json()
        
        if not market_data.get('ready'):
            print(f"   ❌ Execution service not ready (broker pool initializing)")
            return {
                'asset_classes': {},
                'signals': [],
                'summary': {'tradeable': 0, 'queued': 0, 'skipped': len(all_signals), 'total': len(all_signals)}
            }
        
        print(f"   ✅ Execution service ready")
        
        # Check broker connections
        brokers = market_data.get('brokers', {})
        connected_brokers = [k for k, v in brokers.items() if v.get('connected')]
        if not connected_brokers:
            print(f"   ❌ No broker connections available")
            return {
                'asset_classes': {},
                'signals': [],
                'summary': {'tradeable': 0, 'queued': 0, 'skipped': len(all_signals), 'total': len(all_signals)}
            }
        
        print(f"   ✅ {len(connected_brokers)} broker connection(s) ready")
        
        # Check market hours
        markets = market_data.get('markets', {})
        print(f"\n   Checking market hours...")
        for market_type, is_open in markets.items():
            status_icon = "✅" if is_open else "⏰"
            status_text = "open" if is_open else "CLOSED"
            print(f"   • {market_type}: {status_icon} US {market_type.title()} Market is {status_text}")
        
        # Check canary prices (validates market data is flowing)
        canary_prices = market_data.get('canary_prices', {})
        if canary_prices:
            print(f"\n   Running canary checks (for open markets only)...")
            for symbol, price in canary_prices.items():
                print(f"   • STOCK ({symbol})... ✅ ${price:.2f}")
        
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Cannot connect to execution service at http://localhost:8083")
        print(f"   Make sure execution service is running: docker ps")
        return {
            'asset_classes': {},
            'signals': [],
            'summary': {'tradeable': 0, 'queued': 0, 'skipped': len(all_signals), 'total': len(all_signals)}
        }
    except Exception as e:
        print(f"   ❌ Error checking market status: {e}")
        return {
            'asset_classes': {},
            'signals': [],
            'summary': {'tradeable': 0, 'queued': 0, 'skipped': len(all_signals), 'total': len(all_signals)}
        }
    
    # Group signals by instrument_type
    signals_by_type = {}
    for sig in all_signals:
        inst_type = sig.get('signal_legs', [{}])[0].get('instrument_type', 'UNKNOWN')
        if inst_type not in signals_by_type:
            signals_by_type[inst_type] = []
        signals_by_type[inst_type].append(sig)
    
    # Build asset_class_status from market data
    asset_class_status = {}
    for inst_type in signals_by_type.keys():
        is_open = markets.get(inst_type, False)
        
        if is_open:
            asset_class_status[inst_type] = {
                'status': 'AVAILABLE',
                'market': 'OPEN'
            }
        else:
            asset_class_status[inst_type] = {
                'status': 'QUEUED',
                'market': 'CLOSED',
                'reason': f'{inst_type} market is closed'
            }
    
    # Build validated signals list
    print(f"\n   Processing {len(all_signals)} signal(s)...")
    validated_signals = []
    
    for sig in all_signals:
        leg = sig.get('signal_legs', [{}])[0]
        instrument = leg.get('instrument')
        inst_type = leg.get('instrument_type', 'UNKNOWN')
        tif = leg.get('time_in_force', 'DAY')
        
        # Warn if TIF was defaulted
        if 'time_in_force' not in leg:
            leg['time_in_force'] = 'DAY'
        
        # Check asset class status
        asset_status = asset_class_status.get(inst_type, {}).get('status')
        
        if asset_status == 'AVAILABLE':
            # Market is open for this asset class
            sig['_validation'] = {'status': 'AVAILABLE'}
            sig['_tif'] = tif
            validated_signals.append(sig)
        
        elif asset_status == 'QUEUED':
            # Market closed - respect TIF
            sig['_validation'] = {'status': 'QUEUED', 'tif': tif}
            sig['_tif'] = tif
            validated_signals.append(sig)
        
        else:
            # Unknown status - mark as AVAILABLE (will fail later if truly unavailable)
            sig['_validation'] = {'status': 'AVAILABLE', 'note': 'No market check'}
            sig['_tif'] = tif
            validated_signals.append(sig)
    
    # Calculate summary
    tradeable = sum(1 for s in validated_signals if s['_validation'].get('status') == 'AVAILABLE')
    queued = sum(1 for s in validated_signals if s['_validation'].get('status') == 'QUEUED')
    skipped = len(validated_signals) - tradeable - queued
    
    return {
        'asset_classes': asset_class_status,
        'signals': validated_signals,
        'summary': {
            'tradeable': tradeable,
            'queued': queued,
            'skipped': skipped,
            'total': len(all_signals)
        }
    }


def print_market_status_report(validation_result: Dict[str, Any]) -> bool:
    """
    Print colored market status report and wait for countdown.
    Returns True if should proceed, False if should abort.
    """
    import select
    
    signals = validation_result['signals']
    asset_classes = validation_result['asset_classes']
    summary = validation_result['summary']
    
    print("\n" + "="*80)
    print("📊 MARKET STATUS & SIGNAL DISTRIBUTION")
    print("="*80)
    
    # Group signals by status and type
    signals_by_type = {}
    
    for sig in signals:
        inst_type = sig.get('signal_legs', [{}])[0].get('instrument_type', 'UNKNOWN')
        
        if inst_type not in signals_by_type:
            signals_by_type[inst_type] = {
                'available': [],
                'gtc_queued': [],
                'day_skipped': [],
                'invalid': []
            }
        
        validation = sig['_validation']
        tif = sig['_tif']
        
        if validation.get('status') == 'AVAILABLE':
            signals_by_type[inst_type]['available'].append(sig)
        elif validation.get('status') == 'STALE':
            if tif in ['GTC', 'GTD']:
                signals_by_type[inst_type]['gtc_queued'].append(sig)
            else:
                signals_by_type[inst_type]['day_skipped'].append(sig)
        elif validation.get('status') == 'INVALID':
            signals_by_type[inst_type]['invalid'].append(sig)
    
    # Print consolidated status for each asset type
    print()
    for inst_type in sorted(signals_by_type.keys()):
        counts = signals_by_type[inst_type]
        asset_info = asset_classes.get(inst_type, {})
        
        # Get market status
        market_status = asset_info.get('status', 'UNKNOWN')
        
        # Build status line
        if market_status == 'AVAILABLE':
            status_icon = "✅"
            market_name = {
                'STOCK': 'Stock Market',
                'BOND': 'Bond Market', 
                'OPTION': 'Options Market',
                'FUTURE': 'Futures Market',
                'FOREX': 'Forex Market',
                'CRYPTO': 'Crypto Market',
                'COMMODITY': 'Commodity Market'
            }.get(inst_type, f'{inst_type} Market')
            status_text = f"{status_icon} {market_name} is OPEN"
        else:
            status_icon = "⏰"
            market_name = {
                'STOCK': 'Stock Market',
                'BOND': 'Bond Market',
                'OPTION': 'Options Market', 
                'FUTURE': 'Futures Market',
                'FOREX': 'Forex Market',
                'CRYPTO': 'Crypto Market',
                'COMMODITY': 'Commodity Market'
            }.get(inst_type, f'{inst_type} Market')
            status_text = f"{status_icon} {market_name} is CLOSED"
        
        # Count signals
        available = len(counts['available'])
        queued = len(counts['gtc_queued'])
        skipped = len(counts['day_skipped'])
        invalid = len(counts['invalid'])
        total = available + queued + skipped + invalid
        
        # Build signal distribution text
        parts = []
        if available > 0:
            parts.append(f"{available} APPROVED")
        if queued > 0:
            parts.append(f"{queued} QUEUED (GTC)")
        if skipped > 0:
            parts.append(f"{skipped} SKIPPED (DAY)")
        if invalid > 0:
            parts.append(f"{invalid} INVALID")
        
        signal_text = ", ".join(parts) if parts else "0 signals"
        
        # Print consolidated line
        print(f"   {inst_type:<12} {status_text:<35} │ {signal_text}")
    
    # Print overall summary
    print("\n" + "="*80)
    print(f"📈 SUMMARY: {summary['tradeable']} will execute now, {summary['queued']} will queue, {summary['skipped']} skipped (Total: {summary['total']})")
    print("="*80)
    
    # If nothing can run, abort
    if summary['tradeable'] == 0 and summary['queued'] == 0:
        print("\n❌ No signals can be executed or queued. Aborting test.")
        return False
    
    # Countdown with Enter to skip
    print("\n⏰ Starting tests in 10 seconds (press ENTER to skip countdown)...")
    
    i, o, e = select.select([sys.stdin], [], [], 10)
    if i:
        sys.stdin.readline()
        print("▶️  Starting immediately...\n")
    else:
        print("▶️  Starting tests now...\n")
    
    return True
