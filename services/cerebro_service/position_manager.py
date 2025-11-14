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

    def __init__(self, mongo_client: MongoClient):
        """
        Initialize PositionManager.

        Args:
            mongo_client: MongoDB client instance
        """
        self.db = mongo_client['mathematricks_trading']
        self.positions = self.db['open_positions']
        self.orders = self.db['trading_orders']

        # Create indexes for efficient queries
        self.positions.create_index([("strategy_id", 1), ("instrument", 1), ("direction", 1)])
        self.positions.create_index([("status", 1)])

    def get_open_position(self, strategy_id: str, instrument: str, direction: str, retry_count: int = 3, retry_delay: float = 0.5) -> Optional[Dict[str, Any]]:
        """
        Get open position for strategy + instrument + direction.
        Includes retry logic to handle race conditions where position is being created.

        Args:
            strategy_id: Strategy identifier
            instrument: Instrument symbol (e.g., "AAPL")
            direction: "LONG" or "SHORT"
            retry_count: Number of retries (default: 3)
            retry_delay: Delay between retries in seconds (default: 0.5)

        Returns:
            Position document or None if no position exists
        """
        for attempt in range(retry_count):
            position = self.positions.find_one({
                "strategy_id": strategy_id,
                "instrument": instrument,
                "direction": direction,
                "status": "OPEN"
            })

            if position:
                if attempt > 0:
                    logger.info(f"✅ Found position for {strategy_id}/{instrument} on retry attempt {attempt + 1}")
                return position

            # If not found and not last attempt, wait and retry
            if attempt < retry_count - 1:
                logger.debug(f"⏳ Position not found for {strategy_id}/{instrument}, retrying in {retry_delay}s (attempt {attempt + 1}/{retry_count})")
                time.sleep(retry_delay)

        # Not found after all retries
        return None

    def get_positions_by_strategy(self, strategy_id: str) -> List[Dict[str, Any]]:
        """
        Get all open positions for a strategy.

        Args:
            strategy_id: Strategy identifier

        Returns:
            List of position documents
        """
        return list(self.positions.find({
            "strategy_id": strategy_id,
            "status": "OPEN"
        }))

    def get_deployed_capital(self, strategy_id: str) -> Dict[str, Any]:
        """
        Calculate deployed capital from OPEN positions (not pending orders).

        Args:
            strategy_id: Strategy identifier

        Returns:
            Dict with:
                - deployed_capital: Total cost basis of open positions
                - deployed_margin: Total margin used
                - open_positions: List of position documents
                - position_count: Number of open positions
        """
        positions = self.get_positions_by_strategy(strategy_id)

        total_capital = sum(p.get('total_cost_basis', 0) for p in positions)
        total_margin = sum(p.get('margin_used', 0) for p in positions)

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

    def create_or_update_position(self, order_confirmation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create or update position when order fills.

        Logic:
        - If no position exists: create new position
        - If position exists same direction: scale in (add to position)
        - If position exists opposite direction: scale out/close opposite position

        Args:
            order_confirmation: Order fill details from execution service

        Returns:
            Dict with:
                - action: "created", "scaled_in", "scaled_out", "closed"
                - position: Updated position document
        """
        strategy_id = order_confirmation.get('strategy_id')
        instrument = order_confirmation.get('instrument')
        direction = order_confirmation.get('direction')
        filled_qty = order_confirmation.get('filled_quantity', 0)
        fill_price = order_confirmation.get('fill_price', 0)
        order_id = order_confirmation.get('order_id')
        margin_used = order_confirmation.get('margin_used', 0)

        # Get existing position (same direction)
        existing_position = self.get_open_position(strategy_id, instrument, direction)

        if existing_position:
            # SCALE IN: Add to existing position
            old_qty = existing_position['quantity']
            old_cost_basis = existing_position['total_cost_basis']
            old_avg_price = existing_position['avg_entry_price']

            new_qty = old_qty + filled_qty
            new_cost_basis = old_cost_basis + (filled_qty * fill_price)
            new_avg_price = new_cost_basis / new_qty if new_qty > 0 else fill_price

            # Update position
            self.positions.update_one(
                {"_id": existing_position['_id']},
                {
                    "$set": {
                        "quantity": new_qty,
                        "avg_entry_price": new_avg_price,
                        "total_cost_basis": new_cost_basis,
                        "margin_used": existing_position.get('margin_used', 0) + margin_used,
                        "updated_at": datetime.utcnow()
                    },
                    "$push": {
                        "entry_order_ids": order_id
                    }
                }
            )

            logger.info(f"✅ SCALE IN: {strategy_id} {instrument} {direction} {old_qty}→{new_qty} shares @ avg ${new_avg_price:.2f}")

            return {
                "action": "scaled_in",
                "position": self.get_open_position(strategy_id, instrument, direction)
            }

        else:
            # Check for opposite direction position (scale out scenario)
            opposite_dir = "SHORT" if direction == "LONG" else "LONG"
            opposite_position = self.get_open_position(strategy_id, instrument, opposite_dir)

            if opposite_position:
                # SCALE OUT or CLOSE opposite position
                opp_qty = opposite_position['quantity']

                if filled_qty >= opp_qty:
                    # Full close of opposite position
                    self.positions.update_one(
                        {"_id": opposite_position['_id']},
                        {
                            "$set": {
                                "status": "CLOSED",
                                "closed_at": datetime.utcnow(),
                                "quantity": 0
                            },
                            "$push": {
                                "exit_order_ids": order_id
                            }
                        }
                    )

                    logger.info(f"✅ CLOSED: {strategy_id} {instrument} {opposite_dir} position of {opp_qty} shares")

                    # If filled_qty > opp_qty, create new position in opposite direction
                    remaining_qty = filled_qty - opp_qty
                    if remaining_qty > 0:
                        logger.info(f"✅ FLIP: Creating new {direction} position with {remaining_qty} shares")
                        return self._create_new_position(
                            strategy_id, instrument, direction, remaining_qty, fill_price, order_id, margin_used
                        )

                    return {
                        "action": "closed",
                        "position": opposite_position
                    }
                else:
                    # Partial close (scale out)
                    new_qty = opp_qty - filled_qty
                    new_cost_basis = opposite_position['total_cost_basis'] * (new_qty / opp_qty)

                    self.positions.update_one(
                        {"_id": opposite_position['_id']},
                        {
                            "$set": {
                                "quantity": new_qty,
                                "total_cost_basis": new_cost_basis,
                                "updated_at": datetime.utcnow()
                            },
                            "$push": {
                                "exit_order_ids": order_id
                            }
                        }
                    )

                    logger.info(f"✅ SCALE OUT: {strategy_id} {instrument} {opposite_dir} {opp_qty}→{new_qty} shares")

                    return {
                        "action": "scaled_out",
                        "position": self.get_open_position(strategy_id, instrument, opposite_dir)
                    }

            else:
                # NEW ENTRY: No existing position
                return self._create_new_position(
                    strategy_id, instrument, direction, filled_qty, fill_price, order_id, margin_used
                )

    def _create_new_position(self, strategy_id, instrument, direction, quantity, price, order_id, margin_used):
        """Helper to create a new position"""
        position_id = f"{strategy_id}_{instrument}_{direction}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        new_position = {
            "position_id": position_id,
            "strategy_id": strategy_id,
            "account": "DU1234567",  # TODO: Get from order
            "instrument": instrument,
            "direction": direction,
            "quantity": quantity,
            "avg_entry_price": price,
            "total_cost_basis": quantity * price,
            "margin_used": margin_used,
            "status": "OPEN",
            "opened_at": datetime.utcnow(),
            "closed_at": None,
            "entry_order_ids": [order_id],
            "exit_order_ids": [],
            "pnl_realized": 0,
            "pnl_unrealized": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        self.positions.insert_one(new_position)

        logger.info(f"✅ NEW ENTRY: {strategy_id} {instrument} {direction} {quantity} shares @ ${price:.2f}")

        return {
            "action": "created",
            "position": new_position
        }
