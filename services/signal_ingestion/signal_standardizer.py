"""
Signal Standardization Module
Converts raw signals to standardized format for Pub/Sub
"""

import json
import datetime
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger('signal_ingestion.standardizer')


class SignalStandardizer:
    """
    Converts raw signals from TradingView/MongoDB to standardized format
    for downstream microservices (Cerebro → Execution)
    """

    @staticmethod
    def generate_signal_id(signal_data: dict, now: Optional[datetime.datetime] = None) -> str:
        """
        Generate clean signal ID: {strategy}_{YYYYMMDD}_{HHMMSS}_{seq}
        """
        if now is None:
            now = datetime.datetime.utcnow()

        strategy_name = signal_data.get('strategy_name', 'Unknown').replace(' ', '_').replace('-', '_')
        date_str = now.strftime('%Y%m%d')
        time_str = now.strftime('%H%M%S')

        # Extract sequence number from original signalID if available
        original_id = signal_data.get('signalID') or signal_data.get('signal_id')
        if original_id:
            # Extract sequence number from end of original ID (e.g., "001" from "SPY_20251027_104528_001")
            parts = str(original_id).split('_')
            if len(parts) > 0 and parts[-1].isdigit():
                seq = parts[-1].zfill(3)[:3]  # Ensure exactly 3 digits
            else:
                seq = str(int(now.microsecond / 1000)).zfill(3)[:3]
        else:
            # Use milliseconds as sequence number (always 3 digits)
            seq = str(int(now.microsecond / 1000)).zfill(3)[:3]

        return f"{strategy_name}_{date_str}_{time_str}_{seq}"

    @staticmethod
    def get_timestamp(signal_data: dict) -> str:
        """
        Extract or generate timestamp from signal data
        Priority: timestamp → received_at → signal_sent_EPOCH → current time
        """
        timestamp_value = signal_data.get('timestamp')
        if not timestamp_value:
            # Try received_at first
            if 'received_at' in signal_data and signal_data['received_at']:
                timestamp_value = signal_data['received_at'].isoformat() if isinstance(
                    signal_data['received_at'], datetime.datetime) else signal_data['received_at']
            # Try signal_sent_EPOCH
            elif 'signal_sent_EPOCH' in signal_data and signal_data['signal_sent_EPOCH']:
                timestamp_value = datetime.datetime.fromtimestamp(signal_data['signal_sent_EPOCH']).isoformat()
            # Fallback to current time
            else:
                timestamp_value = datetime.datetime.utcnow().isoformat()

        return timestamp_value

    @staticmethod
    def standardize(signal_data: dict) -> Dict[str, Any]:
        """
        Convert raw signal to standardized format for Cerebro/Execution services

        Args:
            signal_data: Raw signal data from MongoDB

        Returns:
            Standardized signal dictionary ready for Pub/Sub
        """
        signal_payload = signal_data.get('signal', {})

        # Generate clean signal ID
        signal_id = SignalStandardizer.generate_signal_id(signal_data)

        # Get timestamp
        timestamp = SignalStandardizer.get_timestamp(signal_data)

        # Build standardized signal
        standardized_signal = {
            "signal_id": signal_id,
            "strategy_id": signal_data.get('strategy_name', 'Unknown'),
            "timestamp": timestamp,
            "instrument": signal_payload.get('instrument') or signal_payload.get('ticker', ''),
            "direction": signal_payload.get('direction', 'LONG').upper(),
            "action": signal_payload.get('action', 'ENTRY').upper(),
            "order_type": signal_payload.get('order_type', 'MARKET').upper(),
            "price": float(signal_payload.get('price', 0)),
            "quantity": float(signal_payload.get('quantity', 1)),
            "stop_loss": float(signal_payload.get('stop_loss', 0)),
            "take_profit": float(signal_payload.get('take_profit', 0)),
            "expiry": signal_payload.get('expiry'),  # For futures
            # Multi-asset support fields
            "instrument_type": signal_payload.get('instrument_type'),  # STOCK, OPTION, FOREX, FUTURE
            "underlying": signal_payload.get('underlying'),  # For options
            "legs": signal_payload.get('legs'),  # For multi-leg options
            "exchange": signal_payload.get('exchange'),  # For futures
            "metadata": {
                "expected_alpha": 0.02,  # Would come from backtest data
                "original_signal": signal_data
            },
            "processed_by_cerebro": False,
            "created_at": datetime.datetime.utcnow().isoformat()
        }

        return standardized_signal

    @staticmethod
    def to_json(signal: Dict[str, Any]) -> bytes:
        """Convert standardized signal to JSON bytes for Pub/Sub"""
        return json.dumps(signal).encode('utf-8')
