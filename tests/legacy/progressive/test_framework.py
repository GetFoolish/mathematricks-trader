"""
Test Framework Utilities for 4-Mode Signal Testing

Provides:
- ModeConfig: Configuration for each trading mode
- SignalTestRunner: Executes signal tests in specified mode
- TestResult: Test result data structure
"""

import os
import sys
import json
import requests
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from datetime import datetime
import pymongo

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@dataclass
class ModeConfig:
    """Configuration for a trading mode"""
    mode: str
    account_type: str  # mock | paper | live
    data_source: str   # mock | live
    account_id: str
    description: str
    requires_ibkr_gateway: bool
    is_production: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'mode': self.mode,
            'account_type': self.account_type,
            'data_source': self.data_source,
            'account_id': self.account_id,
            'description': self.description
        }


@dataclass
class TestResult:
    """Result of a signal test"""
    test_name: str
    mode: str
    success: bool
    duration: float
    signal_id: Optional[str] = None
    order_id: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


def get_mode_config(mode: str) -> ModeConfig:
    """Get configuration for a specific mode"""
    configs = {
        'mock_mock': ModeConfig(
            mode='mock_mock',
            account_type='mock',
            data_source='mock',
            account_id='Mock_Paper',  # Or your mock account ID
            description='Mock account + Mock data (fast testing)',
            requires_ibkr_gateway=False,
            is_production=False
        ),
        'mock_live': ModeConfig(
            mode='mock_live',
            account_type='mock',
            data_source='live',
            account_id='Mock_Paper',  # Uses mock account with live data
            description='Mock account + Live data (strategy testing)',
            requires_ibkr_gateway=True,  # Need IBKR for live data
            is_production=False
        ),
        'paper_live': ModeConfig(
            mode='paper_live',
            account_type='paper',
            data_source='live',
            account_id='IBKR-TESTING-ACCOUNT',  # Your IBKR paper account
            description='IBKR paper account + Live data (true paper trading)',
            requires_ibkr_gateway=True,
            is_production=False
        ),
        'live_live': ModeConfig(
            mode='live_live',
            account_type='live',
            data_source='live',
            account_id='IBKR-LIVE-ACCOUNT',  # Your IBKR live account
            description='Live account + Live data (PRODUCTION - REAL MONEY)',
            requires_ibkr_gateway=True,
            is_production=True
        )
    }
    
    if mode not in configs:
        raise ValueError(f"Invalid mode: {mode}. Valid modes: {', '.join(configs.keys())}")
    
    return configs[mode]


class SignalTestRunner:
    """Runs signal tests in a specific mode"""
    
    def __init__(self, mode_config: ModeConfig):
        self.mode_config = mode_config
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.mongo_client = None
        self.db = None
    
    def _connect_mongo(self):
        """Connect to MongoDB"""
        if not self.mongo_client:
            self.mongo_client = pymongo.MongoClient(self.mongo_uri)
            self.db = self.mongo_client['mathematricks_trading']
    
    def _ensure_account_mode(self):
        """Ensure account is in correct mode"""
        self._connect_mongo()
        
        account = self.db.trading_accounts.find_one({'account_id': self.mode_config.account_id})
        
        if not account:
            raise ValueError(f"Account {self.mode_config.account_id} not found in MongoDB")
        
        # Update account_type and data_source if different
        needs_update = False
        updates = {}
        
        if account.get('account_type') != self.mode_config.account_type:
            updates['account_type'] = self.mode_config.account_type
            needs_update = True
        
        if account.get('data_source') != self.mode_config.data_source:
            updates['data_source'] = self.mode_config.data_source
            needs_update = True
        
        if needs_update:
            # Compute mode
            updates['mode'] = f"{self.mode_config.account_type}_{self.mode_config.data_source}"
            
            self.db.trading_accounts.update_one(
                {'account_id': self.mode_config.account_id},
                {'$set': updates}
            )
            print(f"   📝 Updated account to {self.mode_config.mode} mode")
        
        return account
    
    def run_test(self, signal_file: Path) -> TestResult:
        """
        Run a single signal test
        
        Args:
            signal_file: Path to signal JSON file
        
        Returns:
            TestResult with test outcome
        """
        start_time = time.time()
        test_name = signal_file.stem
        
        try:
            # Ensure account is in correct mode
            self._ensure_account_mode()
            
            # Load signal
            with open(signal_file, 'r') as f:
                signal = json.load(f)
            
            # Send signal
            signal_id = self._send_signal(signal)
            
            # Wait for processing
            order_id = self._wait_for_order(signal_id, timeout=30)
            
            # Verify order execution
            success = self._verify_order(order_id) if order_id else False
            
            duration = time.time() - start_time
            
            return TestResult(
                test_name=test_name,
                mode=self.mode_config.mode,
                success=success,
                duration=duration,
                signal_id=signal_id,
                order_id=order_id
            )
        
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_name=test_name,
                mode=self.mode_config.mode,
                success=False,
                duration=duration,
                error=str(e)
            )
    
    def _send_signal(self, signal: Dict[str, Any]) -> str:
        """Send signal to signal ingestion service"""
        # POST to signal ingestion API
        url = "http://localhost:8001/submit-signal"  # Adjust port as needed
        
        response = requests.post(url, json=signal, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        signal_id = result.get('signal_id')
        
        if not signal_id:
            raise ValueError("No signal_id returned from signal ingestion")
        
        return signal_id
    
    def _wait_for_order(self, signal_id: str, timeout: int = 30) -> Optional[str]:
        """Wait for order to be created from signal"""
        self._connect_mongo()
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Check if order exists for this signal
            order = self.db.orders.find_one({'signal_id': signal_id})
            
            if order:
                return order.get('order_id')
            
            time.sleep(1)
        
        return None
    
    def _verify_order(self, order_id: str) -> bool:
        """Verify order execution"""
        self._connect_mongo()
        
        order = self.db.orders.find_one({'order_id': order_id})
        
        if not order:
            return False
        
        # Check order status
        status = order.get('status')
        
        # Consider these statuses as success
        success_statuses = ['FILLED', 'SUBMITTED', 'PENDING']
        
        return status in success_statuses


class ModeConfigManager:
    """Manages mode configurations stored in config files"""
    
    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
    
    def save_config(self, mode_config: ModeConfig):
        """Save mode configuration to JSON file"""
        config_file = self.config_dir / f"{mode_config.mode}.json"
        
        with open(config_file, 'w') as f:
            json.dump(mode_config.to_dict(), f, indent=2)
    
    def load_config(self, mode: str) -> ModeConfig:
        """Load mode configuration from JSON file"""
        config_file = self.config_dir / f"{mode}.json"
        
        if not config_file.exists():
            # Return default config
            return get_mode_config(mode)
        
        with open(config_file, 'r') as f:
            data = json.load(f)
        
        return ModeConfig(**data)
