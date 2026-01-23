"""
Preflight check tests - Verify system is ready before running tests
"""

import os
import subprocess
import pytest
import requests
from datetime import datetime, time as dt_time
from typing import Tuple
import pytz
from pymongo import MongoClient


@pytest.mark.unit
@pytest.mark.smoke
class TestSystemPreflight:
    """Preflight system checks"""
    
    def test_docker_running(self):
        """Check Docker daemon is running"""
        try:
            result = subprocess.run(
                ['docker', 'ps'],
                capture_output=True,
                timeout=5
            )
            assert result.returncode == 0, "Docker daemon is not running"
        except FileNotFoundError:
            pytest.skip("Docker not installed")
        except subprocess.TimeoutExpired:
            pytest.fail("Docker command timed out")
    
    def test_required_containers_running(self):
        """Check required Docker containers are running"""
        try:
            result = subprocess.run(
                ['docker', 'ps', '--format', '{{.Names}}'],
                capture_output=True,
                text=True,
                check=True
            )
            
            running = result.stdout.strip().split('\n')
            required = [
                'mathematricks-trader-mongodb-1',
                'mathematricks-trader-execution-service-1',
                'mathematricks-trader-cerebro-service-1'
            ]
            
            missing = [r for r in required if not any(r in c for c in running)]
            
            assert not missing, f"Missing required containers: {missing}"
        except subprocess.CalledProcessError:
            pytest.fail("Could not check Docker containers")


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.smoke
class TestDatabasePreflight:
    """Preflight database checks"""
    
    def test_mongodb_connection(self, mongo_uri):
        """Test MongoDB connection"""
        try:
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            # Force connection
            client.server_info()
            client.close()
        except Exception as e:
            pytest.fail(f"Cannot connect to MongoDB: {e}")
    
    def test_database_exists(self, mongo_client):
        """Test main database exists"""
        db_name = "mathematricks_trading"
        databases = mongo_client.list_database_names()
        assert db_name in databases, f"Database {db_name} not found"
    
    def test_required_collections(self, mongo_client):
        """Test required collections exist"""
        db = mongo_client["mathematricks_trading"]
        required_collections = [
            "signals",
            "strategies", 
            "trading_accounts",
            "positions",
            "orders"
        ]
        
        existing = db.list_collection_names()
        missing = [c for c in required_collections if c not in existing]
        
        assert not missing, f"Missing collections: {missing}"
    
    def test_active_strategies_exist(self, mongo_client):
        """Test that active strategies exist"""
        db = mongo_client["mathematricks_trading"]
        count = db.strategies.count_documents({"is_active": True})
        
        assert count > 0, "No active strategies found in database"
    
    def test_trading_accounts_configured(self, mongo_client):
        """Test trading accounts are configured"""
        db = mongo_client["mathematricks_trading"]
        count = db.trading_accounts.count_documents({})
        
        assert count > 0, "No trading accounts configured"


@pytest.mark.integration
@pytest.mark.broker
@pytest.mark.smoke  
class TestBrokerPreflight:
    """Preflight broker connectivity checks"""
    
    def test_ibkr_gateway_reachable(self):
        """Test IBKR gateway container is reachable"""
        try:
            result = subprocess.run(
                ['docker', 'ps', '--filter', 'name=ib-gateway', '--format', '{{.Names}}'],
                capture_output=True,
                text=True,
                check=True
            )
            
            gateways = result.stdout.strip().split('\n')
            running_gateways = [g for g in gateways if g]
            
            # Should have at least one gateway running
            assert len(running_gateways) > 0, "No IB Gateway containers running"
        except subprocess.CalledProcessError:
            pytest.skip("Could not check IB Gateway status")


@pytest.mark.integration
@pytest.mark.smoke
class TestServicesPreflight:
    """Preflight service health checks"""
    
    def test_execution_service_healthy(self):
        """Test execution service is healthy"""
        try:
            result = subprocess.run(
                ['docker', 'inspect', '--format={{.State.Status}}', 
                 'mathematricks-trader-execution-service-1'],
                capture_output=True,
                text=True,
                check=True
            )
            
            status = result.stdout.strip()
            assert status == "running", f"Execution service is {status}"
        except subprocess.CalledProcessError:
            pytest.fail("Execution service not found")
    
    def test_cerebro_service_healthy(self):
        """Test cerebro service is healthy"""
        try:
            result = subprocess.run(
                ['docker', 'inspect', '--format={{.State.Status}}',
                 'mathematricks-trader-cerebro-service-1'],
                capture_output=True,
                text=True,
                check=True
            )
            
            status = result.stdout.strip()
            assert status == "running", f"Cerebro service is {status}"
        except subprocess.CalledProcessError:
            pytest.fail("Cerebro service not found")


@pytest.mark.unit
@pytest.mark.smoke
class TestEnvironmentPreflight:
    """Preflight environment checks"""
    
    def test_required_env_vars(self):
        """Test required environment variables are set"""
        required = [
            "MONGO_URI",
        ]
        
        missing = [var for var in required if not os.getenv(var)]
        
        assert not missing, f"Missing environment variables: {missing}"
    
    def test_python_version(self):
        """Test Python version is compatible"""
        import sys
        version = sys.version_info
        
        assert version >= (3, 9), f"Python 3.9+ required, found {version.major}.{version.minor}"
    
    def test_required_packages(self):
        """Test required Python packages are installed"""
        required = [
            "pymongo",
            "pytest",
            "ib_insync"
        ]
        
        missing = []
        for package in required:
            try:
                __import__(package.replace("-", "_"))
            except ImportError:
                missing.append(package)
        
        assert not missing, f"Missing packages: {missing}"


@pytest.mark.smoke
class TestMarketStatusPreflight:
    """Preflight market status checks"""
    
    def test_market_hours_check(self):
        """Check if market is open (warning only)"""
        et = pytz.timezone('America/New_York')
        now_et = datetime.now(et)
        
        # Market hours: 9:30 AM - 4:00 PM ET, Mon-Fri
        market_open = dt_time(9, 30)
        market_close = dt_time(16, 0)
        
        is_weekday = now_et.weekday() < 5
        is_market_hours = market_open <= now_et.time() <= market_close
        
        if not (is_weekday and is_market_hours):
            pytest.skip(
                f"Market is closed (Current time: {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')})"
            )


@pytest.mark.smoke
def test_preflight_summary():
    """Run all preflight checks and provide summary"""
    # This test serves as a summary - individual tests provide details
    pass


# Standalone function for running all preflight checks
def run_preflight_checks() -> bool:
    """
    Run all preflight checks and return True if all pass
    Can be called from other scripts
    """
    import sys
    
    print("\n" + "="*70)
    print("🚀 PREFLIGHT CHECKS - MATHEMATRICKS TRADER")
    print("="*70 + "\n")
    
    # Run pytest with preflight checks
    result = pytest.main([
        __file__,
        "-v",
        "-m", "smoke",
        "--tb=short",
        "-x"  # Stop on first failure
    ])
    
    return result == 0


if __name__ == "__main__":
    # Allow running this file directly
    import sys
    success = run_preflight_checks()
    sys.exit(0 if success else 1)
