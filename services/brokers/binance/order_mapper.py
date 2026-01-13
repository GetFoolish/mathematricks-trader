from services.brokers.base import OrderSide, OrderType


def translate_order(order: dict) -> dict:
    side = OrderSide.BUY.value if order["direction"] == "LONG" else OrderSide.SELL.value

    payload = {
        "symbol": order["instrument"],
        "side": side,
        "type": order["order_type"],
        "quantity": order["quantity"]
    }

    if order["order_type"] == OrderType.LIMIT.value:
        payload["price"] = order["limit_price"]
        payload["timeInForce"] = "GTC"

    if order.get("stop_price"):
        payload["stopPrice"] = order["stop_price"]

    return payload
