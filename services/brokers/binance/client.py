import time
import hmac
import hashlib
import requests

from services.brokers.exceptions import (
    BrokerAPIError,
    AuthenticationError,
    BrokerTimeoutError
)


class BinanceClient:
    def __init__(self, api_key, api_secret, base_url):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")

    def _headers(self):
        return {"X-MBX-APIKEY": self.api_key}

    def _sign(self, params: dict) -> str:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return hmac.new(
            self.api_secret.encode(),
            query.encode(),
            hashlib.sha256
        ).hexdigest()

    def request(self, method: str, path: str, params=None):
        params = params or {}
        params["timestamp"] = int(time.time() * 1000)
        params["signature"] = self._sign(params)

        try:
            response = requests.request(
                method,
                self.base_url + path,
                headers=self._headers(),
                params=params,
                timeout=10
            )
        except requests.Timeout:
            raise BrokerTimeoutError(
                "Binance API timeout",
                broker_name="BINANCE",
                operation=path,
                timeout_seconds=10
            )

        if response.status_code == 401:
            raise AuthenticationError(
                "Invalid Binance API credentials",
                broker_name="BINANCE",
                auth_method="API_KEY"
            )

        if response.status_code >= 400:
            data = response.json()
            raise BrokerAPIError(
                message=data.get("msg", "Binance API error"),
                broker_name="BINANCE",
                error_code=str(data.get("code")),
                http_status=response.status_code
            )

        return response.json()

    def ping(self):
        return requests.get(self.base_url + "/api/v3/time", timeout=5).json()
