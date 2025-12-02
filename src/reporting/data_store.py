#!/usr/bin/env python3
"""
MongoDB Data Store for Mathematricks Trader
Stores signals, orders, positions, and PnL data
"""

from typing import Dict, List, Optional
from datetime import datetime
from pymongo import MongoClient, DESCENDING
from pymongo.errors import PyMongoError
from ..core.signal_types import TradingSignal
from ..order_management.order_types import MathematricksOrder, OrderConfirmation


class DataStore:
    """MongoDB data storage for trading system"""

    def __init__(self, mongodb_url: str):
        """
        Initialize data store

        Args:
            mongodb_url: MongoDB connection string
        """
        self.mongodb_url = mongodb_url
        self.client = None
        self.db = None
        self.collections = {}

    def connect(self) -> bool:
        """Connect to MongoDB"""
        try:
            # Detect if connecting to Atlas or local MongoDB
            is_atlas = 'mongodb+srv' in self.mongodb_url or 'mongodb.net' in self.mongodb_url
            
            if is_atlas:
                # Atlas connection requires TLS
                self.client = MongoClient(
                    self.mongodb_url,
                    tls=True,
                    tlsAllowInvalidCertificates=True
                )
            else:
                # Local MongoDB connection (no TLS needed)
                self.client = MongoClient(self.mongodb_url)

            # Test connection
            self.client.admin.command('ping')

            # Get database
            self.db = self.client['mathematricks_trader']

            # Initialize collections
            self.collections = {
                'signals': self.db['trading_signals'],
                'orders': self.db['orders'],
                'positions': self.db['positions'],
                'pnl_history': self.db['pnl_history'],
                'strategy_performance': self.db['strategy_performance']
            }

            print("✅ Connected to MongoDB")
            return True

        except PyMongoError as e:
            print(f"❌ MongoDB connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            print("🔌 Disconnected from MongoDB")

    def store_signal(
        self,
        signal: TradingSignal,
        execution_results: List[Dict]
    ) -> bool:
        """
        Store a trading signal

        Args:
            signal: TradingSignal object
            execution_results: List of execution results

        Returns:
            True if stored successfully
        """
        try:
            signal_doc = {
                'signal_id': signal.signalID,
                'strategy_name': signal.strategy_name,
                'signal_type': signal.signal_type.value,
                'timestamp': signal.timestamp,
                'signal_sent_EPOCH': signal.signal_sent_EPOCH,
                'signal_data': str(signal.signal),
                'execution_results': execution_results,
                'stored_at': datetime.now()
            }

            self.collections['signals'].insert_one(signal_doc)
            return True

        except PyMongoError as e:
            print(f"❌ Error storing signal: {e}")
            return False

    def store_order(
        self,
        order: MathematricksOrder,
        confirmation: OrderConfirmation
    ) -> bool:
        """
        Store an order and its confirmation

        Args:
            order: MathematricksOrder object
            confirmation: OrderConfirmation object

        Returns:
            True if stored successfully
        """
        try:
            order_doc = {
                **order.to_dict(),
                'confirmation': confirmation.to_dict(),
                'stored_at': datetime.now()
            }

            self.collections['orders'].insert_one(order_doc)
            return True

        except PyMongoError as e:
            print(f"❌ Error storing order: {e}")
            return False

    def store_positions_snapshot(
        self,
        positions: List[Dict],
        portfolio_value: float
    ) -> bool:
        """
        Store a snapshot of current positions

        Args:
            positions: List of position dictionaries
            portfolio_value: Total portfolio value

        Returns:
            True if stored successfully
        """
        try:
            snapshot_doc = {
                'positions': positions,
                'portfolio_value': portfolio_value,
                'timestamp': datetime.now()
            }

            self.collections['positions'].insert_one(snapshot_doc)
            return True

        except PyMongoError as e:
            print(f"❌ Error storing positions snapshot: {e}")
            return False

    def store_pnl_record(
        self,
        strategy_name: str,
        pnl: float,
        returns_pct: float,
        date: datetime = None
    ) -> bool:
        """
        Store a PnL record

        Args:
            strategy_name: Name of strategy
            pnl: Profit/Loss amount
            returns_pct: Returns percentage
            date: Date of record (defaults to today)

        Returns:
            True if stored successfully
        """
        try:
            pnl_doc = {
                'strategy_name': strategy_name,
                'pnl': pnl,
                'returns_pct': returns_pct,
                'date': date or datetime.now(),
                'stored_at': datetime.now()
            }

            self.collections['pnl_history'].insert_one(pnl_doc)
            return True

        except PyMongoError as e:
            print(f"❌ Error storing PnL record: {e}")
            return False

    def get_signals(
        self,
        strategy_name: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get signals from database

        Args:
            strategy_name: Filter by strategy (optional)
            limit: Maximum number of signals to return

        Returns:
            List of signal documents
        """
        try:
            query = {}
            if strategy_name:
                query['strategy_name'] = strategy_name

            signals = list(
                self.collections['signals']
                .find(query)
                .sort('stored_at', DESCENDING)
                .limit(limit)
            )

            return signals

        except PyMongoError as e:
            print(f"❌ Error fetching signals: {e}")
            return []

    def get_orders(
        self,
        signal_id: Optional[str] = None,
        strategy_name: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get orders from database

        Args:
            signal_id: Filter by signal ID (optional)
            strategy_name: Filter by strategy (optional)
            limit: Maximum number of orders to return

        Returns:
            List of order documents
        """
        try:
            query = {}
            if signal_id:
                query['signal_id'] = signal_id
            if strategy_name:
                query['strategy_name'] = strategy_name

            orders = list(
                self.collections['orders']
                .find(query)
                .sort('created_at', DESCENDING)
                .limit(limit)
            )

            return orders

        except PyMongoError as e:
            print(f"❌ Error fetching orders: {e}")
            return []

    def get_pnl_history(
        self,
        strategy_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Get PnL history

        Args:
            strategy_name: Filter by strategy (optional)
            start_date: Start date (optional)
            end_date: End date (optional)

        Returns:
            List of PnL records
        """
        try:
            query = {}
            if strategy_name:
                query['strategy_name'] = strategy_name
            if start_date or end_date:
                query['date'] = {}
                if start_date:
                    query['date']['$gte'] = start_date
                if end_date:
                    query['date']['$lte'] = end_date

            pnl_records = list(
                self.collections['pnl_history']
                .find(query)
                .sort('date', 1)
            )

            return pnl_records

        except PyMongoError as e:
            print(f"❌ Error fetching PnL history: {e}")
            return []

    def get_strategy_list(self) -> List[str]:
        """Get list of all unique strategies"""
        try:
            strategies = self.collections['signals'].distinct('strategy_name')
            return strategies

        except PyMongoError as e:
            print(f"❌ Error fetching strategy list: {e}")
            return []
