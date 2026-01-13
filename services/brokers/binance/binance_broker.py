from services.brokers.base import AbstractBroker, OrderStatus
from services.brokers.exceptions import (
    BrokerConnectionError,
    OrderRejectedError,
    OrderNotFoundError,
    InsufficientFundsError
)

from .client import BinanceClient
from .order_mapper import translate_order
from .account_mapper import map_account_balance
from .utils import get_quantity_precision


class BinanceBroker(AbstractBroker):

    def __init__(self, config):
        super().__init__(config)
        self.client = BinanceClient(
            config["api_key"],
            config["api_secret"],
            config["base_url"]
        )
        self.connected = False

    # CONNECTION
    def connect(self) -> bool:
        try:
            self.client.ping()
            self.connected = True
            return True
        except Exception:
            raise BrokerConnectionError(
                "Unable to connect to Binance",
                broker_name="BINANCE"
            )

    def disconnect(self) -> bool:
        self.connected = False
        return True

    def is_connected(self) -> bool:
        return self.connected

    # ORDERS
    def place_order(self, order: dict) -> dict:
        payload = translate_order(order)
        try:
            result = self.client.request("POST", "/api/v3/order", payload)
        except Exception as e:
            if "insufficient" in str(e).lower():
                raise InsufficientFundsError(
                    "Insufficient funds",
                    broker_name="BINANCE"
                )
            raise OrderRejectedError(
                "Order rejected",
                broker_name="BINANCE",
                rejection_reason=str(e)
            )

        return {
            "broker_order_id": str(result["orderId"]),
            "status": OrderStatus.SUBMITTED.value,
            "timestamp": result["transactTime"],
            "message": "Order placed on Binance"
        }

    def cancel_order(self, broker_order_id: str) -> bool:
        try:
            self.client.request(
                "DELETE",
                "/api/v3/order",
                {"orderId": broker_order_id, "symbol": self.config["symbol"]}
            )
            return True
        except Exception:
            raise OrderNotFoundError(
                "Order not found",
                broker_name="BINANCE",
                broker_order_id=broker_order_id
            )

    def get_order_status(self, broker_order_id: str) -> dict:
        result = self.client.request(
            "GET",
            "/api/v3/order",
            {"orderId": broker_order_id, "symbol": self.config["symbol"]}
        )

        return {
            "broker_order_id": broker_order_id,
            "status": result["status"],
            "filled_quantity": result["executedQty"],
            "remaining_quantity": float(result["origQty"]) - float(result["executedQty"]),
            "avg_fill_price": result.get("price"),
            "fills": []
        }

    # ACCOUNT
    def get_account_balance(self, account_id=None) -> dict:
        data = self.client.request("GET", "/api/v3/account")
        return map_account_balance(data)

    def get_open_positions(self, account_id=None):
        return []  # Spot crypto has no concept of positions like stocks

    def get_margin_info(self, account_id=None):
        return {}

    def get_open_orders(self, account_id=None):
        return self.client.request("GET", "/api/v3/openOrders")

    def get_quantity_precision(self, symbol: str, instrument_type: str) -> int:
        exchange_info = self.client.request("GET", "/api/v3/exchangeInfo")
        return get_quantity_precision(exchange_info, symbol)
