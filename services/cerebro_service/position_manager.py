"""
Position Manager Module
Handles position state tracking, signal type detection, and deployed capital calculation.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pymongo import MongoClient
import logging
import time

logger = logging.getLogger(__name__)


class PositionManager:
    """
    Manages open positions and tracks deployed capital.

    Key responsibilities:
    - Track open positions in MongoDB
    - Determine signal type (entry/exit/scale)
    - Calculate deployed capital from positions
    - Update positions on order fills
    """

    def __init__(self, mongo_client: MongoClient, default_account_id: str = "Mock_Paper"):
        """
        Initialize PositionManager.

        Args:
            mongo_client: MongoDB client instance
            default_account_id: Default account ID to use for position queries
        """
        self.db = mongo_client['mathematricks_trading']
        self.trading_accounts = self.db['trading_accounts']
        self.orders = self.db['trading_orders']
        self.default_account_id = default_account_id

        # Create indexes for efficient queries on trading_accounts
        self.trading_accounts.create_index([("account_id", 1)])
        self.trading_accounts.create_index([("open_positions.strategy_id", 1)])
        self.trading_accounts.create_index([("open_positions.instrument", 1)])

    def get_open_position(self, strategy_id: str, instrument: str, direction: str, retry_count: int = 3, retry_delay: float = 0.5, account_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Get open position for strategy + instrument + direction from trading_accounts collection.
        Includes retry logic to handle race conditions where position is being created.

        Args:
            strategy_id: Strategy identifier
            instrument: Instrument symbol (e.g., "AAPL")
            direction: "LONG" or "SHORT"
            retry_count: Number of retries (default: 3)
            retry_delay: Delay between retries in seconds (default: 0.5)
            account_id: Account ID (defaults to self.default_account_id)

        Returns:
            Position document or None if no position exists
        """
        if account_id is None:
            account_id = self.default_account_id

        for attempt in range(retry_count):
            # Query trading_accounts collection for open position in open_positions array
            account_doc = self.trading_accounts.find_one({
                "account_id": account_id,
                "open_positions": {
                    "$elemMatch": {
                        "strategy_id": strategy_id,
                        "instrument": instrument,
                        "status": "OPEN"
                    }
                }
            })

            if account_doc:
                # Find the matching position in the array
                open_positions = account_doc.get('open_positions', [])
                for pos in open_positions:
                    if (pos.get('strategy_id') == strategy_id and
                        pos.get('instrument') == instrument and
                        pos.get('status') == 'OPEN'):
                        if attempt > 0:
                            logger.info(f"✅ Found position for {strategy_id}/{instrument} on retry attempt {attempt + 1}")
                        return pos

            # If not found and not last attempt, wait and retry
            if attempt < retry_count - 1:
                logger.debug(f"⏳ Position not found for {strategy_id}/{instrument}, retrying in {retry_delay}s (attempt {attempt + 1}/{retry_count})")
                time.sleep(retry_delay)

        # Not found after all retries
        return None

    def get_positions_by_strategy(self, strategy_id: str, account_id: str = None) -> List[Dict[str, Any]]:
        """
        Get all open positions for a strategy from trading_accounts collection.

        Args:
            strategy_id: Strategy identifier
            account_id: Account ID (defaults to self.default_account_id)

        Returns:
            List of position documents
        """
        if account_id is None:
            account_id = self.default_account_id

        # Query all accounts if account_id is "ALL", otherwise query specific account
        query = {} if account_id == "ALL" else {"account_id": account_id}

        all_positions = []
        for account_doc in self.trading_accounts.find(query):
            open_positions = account_doc.get('open_positions', [])
            for pos in open_positions:
                if pos.get('strategy_id') == strategy_id and pos.get('status') == 'OPEN':
                    all_positions.append(pos)

        return all_positions

    def get_deployed_capital(self, strategy_id: str, account_id: str = None) -> Dict[str, Any]:
        """
        Calculate deployed capital from OPEN positions (not pending orders).

        Args:
            strategy_id: Strategy identifier
            account_id: Account ID (defaults to self.default_account_id)

        Returns:
            Dict with:
                - deployed_capital: Total cost basis of open positions
                - deployed_margin: Total margin used (estimated)
                - open_positions: List of position documents
                - position_count: Number of open positions
        """
        positions = self.get_positions_by_strategy(strategy_id, account_id)

        # Calculate total capital deployed (quantity * avg_entry_price)
        total_capital = sum(
            p.get('quantity', 0) * p.get('avg_entry_price', 0)
            for p in positions
        )

        # Estimate margin (for stocks, typically 25% margin requirement)
        # TODO: Get actual margin from broker or use margin calculator
        total_margin = total_capital * 0.25

        return {
            'deployed_capital': total_capital,
            'deployed_margin': total_margin,
            'open_positions': positions,
            'position_count': len(positions)
        }

    def determine_signal_type(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determine signal type using multiple methods.

        Priority:
        1. Explicit signal.signal_type field ("ENTRY", "EXIT", "SCALE_IN", "SCALE_OUT")
        2. Infer from action + direction + current position state

        Args:
            signal: Signal dictionary with strategy_id, instrument, action, direction, etc.

        Returns:
            Dict with:
                - signal_type: "ENTRY", "EXIT", "SCALE_IN", "SCALE_OUT", "UNKNOWN"
                - method: "explicit", "inferred", or "default"
                - current_position: Position dict or None
                - reasoning: Explanation of how type was determined
        """
        strategy_id = signal.get('strategy_id')
        instrument = signal.get('instrument')
        action = signal.get('action', '').upper()  # BUY or SELL
        direction = signal.get('direction', '').upper()  # LONG or SHORT

        # Method 1: Check for explicit signal_type field (check multiple locations)
        # Try top-level first (handle None case)
        explicit_type = (signal.get('signal_type') or '').upper()

        # If not found, check nested in metadata.original_signal.signal
        if not explicit_type:
            metadata = signal.get('metadata', {})
            original_signal = metadata.get('original_signal', {})
            nested_signal = original_signal.get('signal', {})

            # Handle signal as array (new format) or dict (legacy)
            if isinstance(nested_signal, list):
                nested_signal = nested_signal[0] if len(nested_signal) > 0 else {}

            explicit_type = (nested_signal.get('signal_type') or '').upper()

        if explicit_type in ['ENTRY', 'EXIT', 'SCALE_IN', 'SCALE_OUT']:
            return {
                'signal_type': explicit_type,
                'method': 'explicit',
                'current_position': None,
                'reasoning': f"Explicit signal_type field: {explicit_type}"
            }

        # Method 2: Infer from position state and action
        # Get current position for this strategy+instrument in the signal's direction
        current_position = self.get_open_position(strategy_id, instrument, direction)

        # Also check opposite direction position (for flip scenarios)
        opposite_dir = "SHORT" if direction == "LONG" else "LONG"
        opposite_position = self.get_open_position(strategy_id, instrument, opposite_dir)

        # Inference logic
        if current_position is None and opposite_position is None:
            # No position exists -> ENTRY
            signal_type = "ENTRY"
            reasoning = f"No existing position in {instrument}"

        elif current_position:
            # Position exists in same direction
            current_qty = current_position.get('quantity', 0)

            # Determine if adding (scale in) or reducing (scale out/exit)
            if (direction == "LONG" and action == "BUY") or (direction == "SHORT" and action == "SELL"):
                signal_type = "SCALE_IN"
                reasoning = f"Adding to existing {direction} position of {current_qty} shares"
            elif (direction == "LONG" and action == "SELL") or (direction == "SHORT" and action == "BUY"):
                signal_type = "SCALE_OUT"  # Could be partial or full exit
                reasoning = f"Reducing existing {direction} position of {current_qty} shares"
            else:
                signal_type = "UNKNOWN"
                reasoning = f"Ambiguous: position={direction}, action={action}"

        elif opposite_position:
            # Position exists in opposite direction -> reversing/flipping
            opp_qty = opposite_position.get('quantity', 0)
            signal_type = "EXIT"  # Closing opposite position
            reasoning = f"Closing opposite {opposite_dir} position of {opp_qty} shares"

        else:
            signal_type = "UNKNOWN"
            reasoning = "Unable to determine signal type"

        return {
            'signal_type': signal_type,
            'method': 'inferred',
            'current_position': current_position,
            'opposite_position': opposite_position,
            'reasoning': reasoning
        }

