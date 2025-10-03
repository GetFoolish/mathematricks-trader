#!/usr/bin/env python3
"""
Signal Converter for Mathematricks Trader
Converts trading signals to standardized Mathematricks orders
"""

from typing import List
from ..core.signal_types import (
    TradingSignal, SignalType, StockSignal, OptionsSignal,
    MultiLegSignal, StopLossSignal
)
from ..core.portfolio import Broker, AssetType
from .order_types import (
    MathematricksOrder, OrderSide, OrderType, TimeInForce
)


class SignalConverter:
    """Convert signals to Mathematricks orders"""

    def __init__(self, default_broker: Broker = Broker.IBKR):
        """
        Initialize signal converter

        Args:
            default_broker: Default broker for orders
        """
        self.default_broker = default_broker

    def convert_signal(
        self,
        signal: TradingSignal,
        broker: Broker = None
    ) -> List[MathematricksOrder]:
        """
        Convert a trading signal to one or more Mathematricks orders

        Args:
            signal: Trading signal to convert
            broker: Target broker (uses default if not specified)

        Returns:
            List of MathematricksOrder objects
        """
        broker = broker or self.default_broker

        if signal.signal_type == SignalType.STOCK:
            return self._convert_stock_signal(signal, broker)
        elif signal.signal_type == SignalType.OPTIONS:
            return self._convert_options_signal(signal, broker)
        elif signal.signal_type == SignalType.MULTI_LEG:
            return self._convert_multi_leg_signal(signal, broker)
        elif signal.signal_type == SignalType.STOP_LOSS:
            return self._convert_stop_loss_signal(signal, broker)
        else:
            raise ValueError(f"Unknown signal type: {signal.signal_type}")

    def _convert_stock_signal(
        self,
        signal: TradingSignal,
        broker: Broker
    ) -> List[MathematricksOrder]:
        """Convert stock signal to order"""
        stock_signal: StockSignal = signal.signal

        # Determine order side
        order_side = (
            OrderSide.BUY if "BUY" in stock_signal.action.upper()
            else OrderSide.SELL
        )

        # Determine asset type based on ticker
        asset_type = self._determine_asset_type(stock_signal.ticker)

        # Create order
        order = MathematricksOrder(
            ticker=stock_signal.ticker,
            broker=broker,
            asset_type=asset_type,
            order_side=order_side,
            quantity=1.0,  # TODO: Calculate from risk/position sizing
            order_type=OrderType.MARKET,
            limit_price=stock_signal.price,
            signal_id=signal.signalID,
            strategy_name=signal.strategy_name
        )

        return [order]

    def _convert_options_signal(
        self,
        signal: TradingSignal,
        broker: Broker
    ) -> List[MathematricksOrder]:
        """Convert options signal to order"""
        options_signal: OptionsSignal = signal.signal

        # Determine order side and option type
        action = options_signal.action.upper()
        if "BUY" in action:
            order_side = OrderSide.BUY
        else:
            order_side = OrderSide.SELL

        if "CALL" in action:
            option_type = "call"
        elif "PUT" in action:
            option_type = "put"
        else:
            option_type = None

        # Create options order
        order = MathematricksOrder(
            ticker=options_signal.ticker,
            broker=broker,
            asset_type=AssetType.OPTION,
            order_side=order_side,
            quantity=1.0,  # TODO: Calculate contracts from risk/position sizing
            order_type=OrderType.MARKET,
            option_type=option_type,
            strike_price=options_signal.strike,
            expiry_date=options_signal.expiry,
            signal_id=signal.signalID,
            strategy_name=signal.strategy_name
        )

        return [order]

    def _convert_multi_leg_signal(
        self,
        signal: TradingSignal,
        broker: Broker
    ) -> List[MathematricksOrder]:
        """Convert multi-leg signal to multiple orders"""
        multi_leg_signal: MultiLegSignal = signal.signal
        orders = []

        for idx, leg in enumerate(multi_leg_signal.legs):
            # Determine order side
            order_side = (
                OrderSide.BUY if "BUY" in leg.action.upper()
                else OrderSide.SELL
            )

            # Determine asset type
            asset_type = self._determine_asset_type(leg.ticker)

            # Create order for this leg
            order = MathematricksOrder(
                ticker=leg.ticker,
                broker=broker,
                asset_type=asset_type,
                order_side=order_side,
                quantity=float(leg.qty),
                order_type=OrderType.MARKET,
                signal_id=signal.signalID,
                strategy_name=signal.strategy_name,
                leg_number=idx + 1,
                parent_order_id=signal.signalID
            )

            orders.append(order)

        return orders

    def _convert_stop_loss_signal(
        self,
        signal: TradingSignal,
        broker: Broker
    ) -> List[MathematricksOrder]:
        """Convert stop-loss signal to order"""
        stop_signal: StopLossSignal = signal.signal

        # Parse trigger to extract ticker (basic parsing)
        # Example: "if AAPL < 145"
        ticker = self._extract_ticker_from_trigger(stop_signal.trigger)

        # Determine order side
        order_side = (
            OrderSide.SELL if "SELL" in stop_signal.action.upper()
            else OrderSide.BUY
        )

        # Determine asset type
        asset_type = self._determine_asset_type(ticker)

        # Create stop-loss order
        order = MathematricksOrder(
            ticker=ticker,
            broker=broker,
            asset_type=asset_type,
            order_side=order_side,
            quantity=0.0,  # TODO: Set to position size or from signal
            order_type=OrderType.STOP,
            is_stop_loss=True,
            trigger_condition=stop_signal.trigger,
            signal_id=signal.signalID,
            strategy_name=signal.strategy_name
        )

        return [order]

    def _determine_asset_type(self, ticker: str) -> AssetType:
        """Determine asset type from ticker"""
        # Simple heuristics (can be improved)
        ticker_upper = ticker.upper()

        if ticker_upper in ['BTC', 'ETH', 'USDT', 'BNB', 'SOL']:
            return AssetType.CRYPTO
        elif '/' in ticker:  # Forex pairs
            return AssetType.FOREX
        else:
            return AssetType.STOCK

    def _extract_ticker_from_trigger(self, trigger: str) -> str:
        """Extract ticker from trigger condition"""
        # Basic parsing: "if AAPL < 145" -> "AAPL"
        parts = trigger.split()
        for part in parts:
            if part.isupper() and len(part) <= 6:
                return part
        return "UNKNOWN"
