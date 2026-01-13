from datetime import datetime


def map_account_balance(account_response: dict) -> dict:
    balances = account_response.get("balances", [])

    cash = sum(float(b["free"]) for b in balances)
    locked = sum(float(b["locked"]) for b in balances)

    return {
        "account_id": "BINANCE",
        "equity": cash + locked,
        "cash_balance": cash,
        "margin_used": 0.0,
        "margin_available": cash,
        "buying_power": cash,
        "timestamp": datetime.utcnow().isoformat()
    }
