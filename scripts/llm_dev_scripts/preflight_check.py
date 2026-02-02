#!/usr/bin/env python3
"""
Pre-Flight Validation Script for Tuesday Market Testing

Runs 10 critical checks before live market testing to ensure system is ready.

Usage:
    python3 scripts/preflight_check.py
    ./scripts/preflight_check.py  # If executable
"""
import os
import sys
import subprocess
import requests
from datetime import datetime, time as dt_time
from typing import Dict, List, Tuple
import pytz
import yaml
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# Colors for terminal output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


class PreflightChecker:
    def __init__(self):
        self.passed = []
        self.warnings = []
        self.failed = []
        self.mongo_client = None
        self.db = None
        self.test_accounts = self._load_test_accounts()
    
    def _load_test_accounts(self) -> List[str]:
        """Load test accounts from gateway_config.yml"""
        config_path = os.path.join(PROJECT_ROOT, 'services', 'execution_service', 'gateway_config.yml')
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                accounts = config.get('always_start_accounts', [])
                return [acc for acc in accounts if acc]  # Filter out None/empty
        except Exception as e:
            print(f"{YELLOW}⚠️  Could not load gateway_config.yml: {e}{RESET}")
            print(f"{YELLOW}   Falling back to IBKR-TESTING-ACCOUNT{RESET}")
            return ['IBKR-TESTING-ACCOUNT']

    def check(self, name: str, func) -> bool:
        """Run a check and track results"""
        print(f"\n{BLUE}{'='*70}{RESET}")
        print(f"{BOLD}CHECK: {name}{RESET}")
        print(f"{BLUE}{'='*70}{RESET}")
        
        try:
            result, message = func()
            if result:
                self.passed.append(name)
                print(f"{GREEN}✅ PASS:{RESET} {message}")
                return True
            else:
                # Determine if warning or failure
                if "warning" in message.lower() or "optional" in message.lower():
                    self.warnings.append((name, message))
                    print(f"{YELLOW}⚠️  WARNING:{RESET} {message}")
                    return True  # Warnings don't block
                else:
                    self.failed.append((name, message))
                    print(f"{RED}❌ FAIL:{RESET} {message}")
                    return False
        except Exception as e:
            self.failed.append((name, f"Exception: {str(e)}"))
            print(f"{RED}❌ FAIL:{RESET} Exception: {str(e)}")
            return False

    def check_docker_services(self) -> Tuple[bool, str]:
        """Check if Docker services are running"""
        try:
            result = subprocess.run(
                ['docker', 'ps', '--format', '{{.Names}}'],
                capture_output=True,
                text=True,
                check=True
            )
            
            running_containers = result.stdout.strip().split('\n')
            required = [
                'mathematricks-trader-mongodb-1',
                'mathematricks-trader-cerebro-service-1',
                'mathematricks-trader-execution-service-1'
            ]
            
            missing = [svc for svc in required if svc not in running_containers]
            
            if missing:
                return False, f"Missing containers: {', '.join(missing)}"
            
            return True, f"All required containers running ({len(required)})"
        except Exception as e:
            return False, f"Docker not running or error: {str(e)}"

    def check_mongodb_connection(self) -> Tuple[bool, str]:
        """Check MongoDB connection"""
        try:
            mongo_uri = os.getenv('MONGODB_URI')
            if not mongo_uri:
                return False, "MONGODB_URI not set in .env"
            
            # For preflight check running on host, use localhost:27018 (Docker port mapping)
            # Replace internal Docker hostnames with localhost
            if 'mongodb://' in mongo_uri:
                # Replace 'mongodb' hostname with localhost and port 27017 with 27018
                mongo_uri = mongo_uri.replace('mongodb://mongodb:', 'mongodb://localhost:')
                mongo_uri = mongo_uri.replace(':27017/', ':27018/')
                mongo_uri = mongo_uri.replace(':27017', ':27018')  # Handle URIs without trailing slash
                # Add directConnection=true for host access
                if '?' not in mongo_uri:
                    mongo_uri += '/?directConnection=true'
            
            use_tls = 'mongodb+srv' in mongo_uri or 'mongodb.net' in mongo_uri
            if use_tls:
                self.mongo_client = MongoClient(mongo_uri, tls=True, tlsAllowInvalidCertificates=True)
            else:
                self.mongo_client = MongoClient(mongo_uri)
            
            self.db = self.mongo_client['mathematricks_trading']
            
            # Test connection
            self.db.command('ping')
            
            # Check collections exist
            collections = self.db.list_collection_names()
            required = ['signal_store', 'trading_orders', 'trading_accounts', 'strategies']
            missing = [col for col in required if col not in collections]
            
            if missing:
                return False, f"Missing collections: {', '.join(missing)}"
            
            return True, f"MongoDB connected ({len(collections)} collections)"
        except Exception as e:
            return False, f"MongoDB connection failed: {str(e)}"

    def check_ib_gateway_connected(self) -> Tuple[bool, str]:
        """Check if IB Gateway is connected for test accounts"""
        try:
            if not self.test_accounts:
                return False, "No test accounts configured in gateway_config.yml"
            
            results = []
            all_ok = True
            
            for account_id in self.test_accounts:
                account = self.db['trading_accounts'].find_one({"account_id": account_id})
                if not account:
                    results.append(f"{account_id}: not found in database")
                    all_ok = False
                    continue
                
                auth = account.get('authentication_details', {})
                host = auth.get('host', '127.0.0.1')
                port = auth.get('port', 4002)
                
                # If running from host (not inside Docker), check if container exists instead
                if 'ib-gateway' in host:
                    # Running from host - check if container is running
                    import subprocess
                    try:
                        result = subprocess.run(
                            ['docker', 'ps', '--filter', f'name={host}', '--format', '{{.Names}}'],
                            capture_output=True, text=True, timeout=5
                        )
                        if host in result.stdout:
                            results.append(f"{account_id}: ✓")
                        else:
                            results.append(f"{account_id}: container not running")
                            all_ok = False
                    except Exception as e:
                        results.append(f"{account_id}: error checking container")
                        all_ok = False
                else:
                    # Try direct socket connection (for localhost or when running inside Docker)
                    import socket
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    result = sock.connect_ex((host, port))
                    sock.close()
                    
                    if result == 0:
                        results.append(f"{account_id}: ✓")
                    else:
                        results.append(f"{account_id}: not responding")
                        all_ok = False
            
            if all_ok:
                return True, f"All gateways running: {', '.join(results)}"
            else:
                return False, f"Gateway issues: {', '.join(results)}"
        except Exception as e:
            return False, f"Error checking IB Gateway: {str(e)}"

    def check_market_data_connection(self) -> Tuple[bool, str]:
        """Check market data by fetching AAPL price for each account"""
        try:
            if not self.test_accounts:
                return False, "No test accounts configured"
            
            # Import here to avoid issues if ib_insync not installed
            sys.path.insert(0, PROJECT_ROOT)
            from services.brokers.ibkr.ibkr_broker import IBKRBroker
            from ib_insync import Stock
            
            results = []
            all_ok = True
            
            for account_id in self.test_accounts:
                # Get IB Gateway Docker container port mapping
                try:
                    docker_result = subprocess.run(
                        ['docker', 'ps', '--filter', 'name=ib-gateway', '--format', '{{.Ports}}'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    # Parse port mapping (e.g., "0.0.0.0:62772->4004/tcp")
                    ports_output = docker_result.stdout.strip()
                    host_port = None
                    for port_map in ports_output.split(','):
                        if '->4004/tcp' in port_map or '->4002/tcp' in port_map:
                            # Extract host port from "0.0.0.0:62772->4004/tcp"
                            host_port = int(port_map.split(':')[1].split('->')[0])
                            break
                    
                    if not host_port:
                        results.append(f"{account_id}: IB Gateway port not found")
                        all_ok = False
                        continue
                    
                    # Build broker config for host connection
                    config = {
                        'broker': 'IBKR',
                        'account_id': account_id,
                        'host': '127.0.0.1',
                        'port': host_port,
                        'client_id': 99,  # Unique client ID for preflight
                    }
                    
                    # Test market data connection
                    broker = IBKRBroker(config)
                    broker.connect()
                    broker.ib.reqMarketDataType(1)  # Request live data
                    broker.ib.sleep(0.5)
                    
                    # Create contract and request data
                    contract = Stock('AAPL', 'SMART', 'USD')
                    broker.ib.qualifyContracts(contract)
                    ticker = broker.ib.reqMktData(contract, '', False, False)
                    
                    # Wait for data (max 3 seconds)
                    price_found = False
                    for _ in range(30):
                        broker.ib.sleep(0.1)
                        if ticker.bid or ticker.ask or ticker.last:
                            mid = (ticker.bid + ticker.ask)/2 if (ticker.bid and ticker.ask) else ticker.last
                            results.append(f"{account_id}: AAPL=${mid:.2f}")
                            price_found = True
                            break
                    
                    broker.ib.cancelMktData(contract)
                    broker.disconnect()
                    
                    if not price_found:
                        results.append(f"{account_id}: no market data")
                        all_ok = False
                        
                except subprocess.TimeoutExpired:
                    results.append(f"{account_id}: Docker timeout")
                    all_ok = False
                except Exception as e:
                    results.append(f"{account_id}: {str(e)[:50]}")
                    all_ok = False
            
            if all_ok:
                return True, f"Market data streaming: {', '.join(results)}"
            else:
                return False, f"CRITICAL: Market data NOT streaming ({', '.join(results)}). Check IBKR subscription & permissions."
        except Exception as e:
            return False, f"Error checking market data: {str(e)}"

    def check_market_hours(self) -> Tuple[bool, str]:
        """Check if market is open (9:30 AM - 4:00 PM ET, weekdays)"""
        try:
            et_tz = pytz.timezone('America/New_York')
            now_et = datetime.now(et_tz)
            current_time = now_et.time()
            
            # Check if weekend
            if now_et.weekday() >= 5:
                return False, f"WARNING: Weekend (market closed). Come back Monday-Friday."
            
            # Market hours: 9:30 AM - 4:00 PM ET
            market_open = dt_time(9, 30)
            market_close = dt_time(16, 0)
            
            if market_open <= current_time <= market_close:
                return True, f"Market is OPEN. Current time: {now_et.strftime('%I:%M %p ET')}"
            elif current_time < market_open:
                return False, f"WARNING: Pre-market (opens 9:30 AM ET). Current: {now_et.strftime('%I:%M %p ET')}"
            else:
                return False, f"WARNING: After-hours (closed 4:00 PM ET). Current: {now_et.strftime('%I:%M %p ET')}"
        except Exception as e:
            return False, f"Error checking market hours: {str(e)}"

    def check_account_config(self) -> Tuple[bool, str]:
        """Check account mode (market_data_type is IBKR-specific in auth details)"""
        try:
            if not self.test_accounts:
                return False, "No test accounts configured"
            
            results = []
            all_ok = True
            
            for account_id in self.test_accounts:
                account = self.db['trading_accounts'].find_one({"account_id": account_id})
                if not account:
                    results.append(f"{account_id}: not found")
                    all_ok = False
                    continue
                
                mode = account.get('mode')
                if mode != 'paper_live':
                    results.append(f"{account_id}: mode={mode} (expected paper_live)")
                    all_ok = False
                else:
                    results.append(f"{account_id}: ✓")
            
            if all_ok:
                return True, f"All accounts configured: {', '.join(results)}"
            else:
                return False, f"Config issues: {', '.join(results)}"
        except Exception as e:
            return False, f"Error checking account config: {str(e)}"

    def check_account_balance(self) -> Tuple[bool, str]:
        """Check account balance > $1000"""
        try:
            if not self.test_accounts:
                return False, "No test accounts configured"
            
            results = []
            all_ok = True
            
            for account_id in self.test_accounts:
                account = self.db['trading_accounts'].find_one({"account_id": account_id})
                if not account:
                    results.append(f"{account_id}: not found")
                    all_ok = False
                    continue
                
                balances = account.get('balances', {})
                equity = balances.get('equity', 0)
                
                if equity < 1000:
                    results.append(f"{account_id}: ${equity:,.0f} (need >$1K)")
                    all_ok = False
                else:
                    results.append(f"{account_id}: ${equity:,.0f} ✓")
            
            if all_ok:
                return True, f"Balances OK: {', '.join(results)}"
            else:
                return False, f"Balance issues: {', '.join(results)}"
        except Exception as e:
            return False, f"Error checking balance: {str(e)}"

    def check_strategies_exist(self) -> Tuple[bool, str]:
        """Check that strategies exist and are mapped to test accounts"""
        try:
            if not self.test_accounts:
                return False, "No test accounts configured"
            
            results = []
            all_ok = True
            
            for account_id in self.test_accounts:
                account = self.db['trading_accounts'].find_one({"account_id": account_id})
                if not account:
                    results.append(f"{account_id}: not found")
                    all_ok = False
                    continue
                
                # Strategies have accounts as an array field
                strategies = list(self.db['strategies'].find({"accounts": account_id}))
                if not strategies:
                    results.append(f"{account_id}: no strategies")
                    all_ok = False
                    continue
                
                active = [s for s in strategies if s.get('status') == 'ACTIVE']
                results.append(f"{account_id}: {len(active)} active")
            
            if all_ok:
                return True, f"Strategies mapped: {', '.join(results)}"
            else:
                return False, f"Strategy issues: {', '.join(results)}"
        except Exception as e:
            return False, f"Error checking strategies: {str(e)}"

    def check_service_health(self) -> Tuple[bool, str]:
        """Check service health endpoints (if they exist)"""
        try:
            services = [
                ('Cerebro', 'http://localhost:8081/health'),
                ('Execution', 'http://localhost:8080/health'),
                ('Account Data', 'http://localhost:8082/health')
            ]
            
            statuses = []
            for name, url in services:
                try:
                    response = requests.get(url, timeout=2)
                    if response.status_code == 200:
                        statuses.append(f"{name}:✅")
                    else:
                        statuses.append(f"{name}:⚠️({response.status_code})")
                except requests.exceptions.RequestException:
                    # Health endpoints might not be implemented - that's OK
                    statuses.append(f"{name}:N/A")
            
            # If all are N/A, it's a warning, not a failure
            if all('N/A' in s for s in statuses):
                return True, f"WARNING: Health endpoints not implemented. {', '.join(statuses)}"
            
            return True, ', '.join(statuses)
        except Exception as e:
            return False, f"Error checking service health: {str(e)}"

    def check_test_signals_exist(self) -> Tuple[bool, str]:
        """Check that test signal files exist"""
        try:
            signal_files = [
                'signal-senders/UPRO_NewYork.js',
            ]
            
            missing = []
            for file_path in signal_files:
                full_path = os.path.join(PROJECT_ROOT, file_path)
                if not os.path.exists(full_path):
                    missing.append(file_path)
            
            if missing:
                return False, f"Missing signal files: {', '.join(missing)}"
            
            return True, f"{len(signal_files)} test signal files found"
        except Exception as e:
            return False, f"Error checking signal files: {str(e)}"

    def check_clean_slate(self) -> Tuple[bool, str]:
        """Check for clean slate (no stale signals or positions)"""
        try:
            # Check for unprocessed signals
            pending_signals = self.db['signal_store'].count_documents({
                "status": {"$nin": ["completed", "rejected", "cancelled"]}
            })
            
            # Check for open positions across all test accounts
            total_open_positions = 0
            for account_id in self.test_accounts:
                account = self.db['trading_accounts'].find_one({"account_id": account_id})
                if account:
                    all_positions = account.get('open_positions', [])
                    open_positions = len([p for p in all_positions if p.get('status') == 'OPEN'])
                    total_open_positions += open_positions
            
            issues = []
            if pending_signals > 0:
                issues.append(f"{pending_signals} pending signals")
            if total_open_positions > 0:
                issues.append(f"{total_open_positions} open positions")
            
            if issues:
                return False, f"WARNING: Not a clean slate: {', '.join(issues)}. Run cleanup script if needed."
            
            return True, "Clean slate (no pending signals or positions)"
        except Exception as e:
            return False, f"Error checking clean slate: {str(e)}"

    def run_all_checks(self):
        """Run all pre-flight checks"""
        print(f"\n{BOLD}{BLUE}{'='*70}{RESET}")
        print(f"{BOLD}{BLUE}🚀 PRE-FLIGHT CHECKS FOR TUESDAY MARKET TESTING{RESET}")
        print(f"{BOLD}{BLUE}{'='*70}{RESET}")
        
        # Run all checks
        self.check("1. Docker Services Running", self.check_docker_services)
        self.check("2. MongoDB Connected", self.check_mongodb_connection)
        self.check("3. IB Gateway Connected", self.check_ib_gateway_connected)
        self.check("4. Market Data Connection (AAPL Price)", self.check_market_data_connection)
        self.check("5. Market Hours", self.check_market_hours)
        self.check("6. Account Configuration", self.check_account_config)
        self.check("7. Account Balance", self.check_account_balance)
        self.check("8. Strategies Exist and Mapped", self.check_strategies_exist)
        self.check("9. Service Health Endpoints", self.check_service_health)
        self.check("10. Test Signal Files", self.check_test_signals_exist)
        self.check("11. Clean Slate (No Stale Data)", self.check_clean_slate)
        
        # Summary
        print(f"\n{BOLD}{BLUE}{'='*70}{RESET}")
        print(f"{BOLD}SUMMARY{RESET}")
        print(f"{BOLD}{BLUE}{'='*70}{RESET}")
        print(f"{GREEN}✅ Passed:{RESET} {len(self.passed)}")
        print(f"{YELLOW}⚠️  Warnings:{RESET} {len(self.warnings)}")
        print(f"{RED}❌ Failed:{RESET} {len(self.failed)}")
        
        if self.warnings:
            print(f"\n{YELLOW}Warnings:{RESET}")
            for name, msg in self.warnings:
                print(f"  - {name}: {msg}")
        
        if self.failed:
            print(f"\n{RED}Failures:{RESET}")
            for name, msg in self.failed:
                print(f"  - {name}: {msg}")
            print(f"\n{RED}❌ Pre-flight checks FAILED. Fix issues before testing.{RESET}")
            return False
        else:
            print(f"\n{GREEN}✅ All pre-flight checks PASSED! System ready for testing.{RESET}")
            if self.warnings:
                print(f"{YELLOW}⚠️  Review warnings above before proceeding.{RESET}")
            return True


if __name__ == "__main__":
    checker = PreflightChecker()
    success = checker.run_all_checks()
    sys.exit(0 if success else 1)
