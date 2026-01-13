def get_quantity_precision(exchange_info: dict, symbol: str) -> int:
    for s in exchange_info.get("symbols", []):
        if s["symbol"] == symbol:
            for f in s["filters"]:
                if f["filterType"] == "LOT_SIZE":
                    step = f["stepSize"]
                    return len(step.rstrip("0").split(".")[1])
    return 0
