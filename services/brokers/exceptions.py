"""
Broker Exception Classes
Defines all exceptions that can be raised by broker implementations
"""


class BrokerError(Exception):
    """
    Base exception class for all broker-related errors.

    All broker implementations should raise exceptions derived from this class.
    """
    def __init__(self, message: str, broker_name: str = None, details: dict = None):
        """
        Args:
            message: Human-readable error message
            broker_name: Name of the broker (e.g., "IBKR", "Zerodha")
            details: Additional error details (optional)
        """
        self.message = message
        self.broker_name = broker_name
        self.details = details or {}

        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format the complete error message"""
        if self.broker_name:
            msg = f"[{self.broker_name}] {self.message}"
        else:
            msg = self.message

        if self.details:
            msg += f" | Details: {self.details}"

        return msg


class BrokerConnectionError(BrokerError):
    """
    Raised when broker connection fails or is lost.

    Examples:
        - TWS/Gateway not running (IBKR)
        - Invalid API credentials (Zerodha)
        - Network timeout
        - Connection refused
    """
    pass


class OrderRejectedError(BrokerError):
    """
    Raised when broker rejects an order.

    Examples:
        - Insufficient buying power
        - Invalid order parameters
        - Market closed
        - Symbol not supported
        - Order size exceeds limits

    Attributes:
        order_id: Local order ID (if available)
        rejection_reason: Broker's rejection reason
    """
    def __init__(self, message: str, broker_name: str = None,
                 order_id: str = None, rejection_reason: str = None, details: dict = None):
        """
        Args:
            message: Human-readable error message
            broker_name: Name of the broker
            order_id: Local order ID
            rejection_reason: Broker's rejection reason
            details: Additional error details
        """
        self.order_id = order_id
        self.rejection_reason = rejection_reason

        if not details:
            details = {}

        if order_id:
            details['order_id'] = order_id

        if rejection_reason:
            details['rejection_reason'] = rejection_reason

        super().__init__(message, broker_name, details)


class OrderNotFoundError(BrokerError):
    """
    Raised when attempting to query/cancel an order that doesn't exist.

    Examples:
        - Order ID not found in broker system
        - Order expired/purged from broker records

    Attributes:
        broker_order_id: Broker's order ID
    """
    def __init__(self, message: str, broker_name: str = None,
                 broker_order_id: str = None, details: dict = None):
        """
        Args:
            message: Human-readable error message
            broker_name: Name of the broker
            broker_order_id: Broker's order ID
            details: Additional error details
        """
        self.broker_order_id = broker_order_id

        if not details:
            details = {}

        if broker_order_id:
            details['broker_order_id'] = broker_order_id

        super().__init__(message, broker_name, details)


class BrokerAPIError(BrokerError):
    """
    Raised for general broker API errors.

    Examples:
        - API rate limit exceeded
        - Invalid API response format
        - Unexpected API error code
        - Server error (500)

    Attributes:
        error_code: Broker's error code (if available)
        http_status: HTTP status code (if applicable)
    """
    def __init__(self, message: str, broker_name: str = None,
                 error_code: str = None, http_status: int = None, details: dict = None):
        """
        Args:
            message: Human-readable error message
            broker_name: Name of the broker
            error_code: Broker's error code
            http_status: HTTP status code
            details: Additional error details
        """
        self.error_code = error_code
        self.http_status = http_status

        if not details:
            details = {}

        if error_code:
            details['error_code'] = error_code

        if http_status:
            details['http_status'] = http_status

        super().__init__(message, broker_name, details)


class InsufficientFundsError(BrokerError):
    """
    Raised when account has insufficient funds for an operation.

    Examples:
        - Buying power too low for order
        - Margin requirement not met
        - Cash balance insufficient

    Attributes:
        required: Required amount
        available: Available amount
    """
    def __init__(self, message: str, broker_name: str = None,
                 required: float = None, available: float = None, details: dict = None):
        """
        Args:
            message: Human-readable error message
            broker_name: Name of the broker
            required: Required amount
            available: Available amount
            details: Additional error details
        """
        self.required = required
        self.available = available

        if not details:
            details = {}

        if required is not None:
            details['required'] = required

        if available is not None:
            details['available'] = available

        super().__init__(message, broker_name, details)


class InvalidSymbolError(BrokerError):
    """
    Raised when symbol is invalid or not supported by broker.

    Examples:
        - Symbol not found
        - Trading not permitted for symbol
        - Symbol format invalid

    Attributes:
        symbol: The invalid symbol
    """
    def __init__(self, message: str, broker_name: str = None,
                 symbol: str = None, details: dict = None):
        """
        Args:
            message: Human-readable error message
            broker_name: Name of the broker
            symbol: The invalid symbol
            details: Additional error details
        """
        self.symbol = symbol

        if not details:
            details = {}

        if symbol:
            details['symbol'] = symbol

        super().__init__(message, broker_name, details)


class MarketClosedError(BrokerError):
    """
    Raised when attempting to trade while market is closed.

    Examples:
        - Market hours ended
        - Weekend/holiday
        - Pre-market/after-hours not allowed for symbol

    Attributes:
        symbol: Symbol being traded
        market_status: Current market status
    """
    def __init__(self, message: str, broker_name: str = None,
                 symbol: str = None, market_status: str = None, details: dict = None):
        """
        Args:
            message: Human-readable error message
            broker_name: Name of the broker
            symbol: Symbol being traded
            market_status: Current market status
            details: Additional error details
        """
        self.symbol = symbol
        self.market_status = market_status

        if not details:
            details = {}

        if symbol:
            details['symbol'] = symbol

        if market_status:
            details['market_status'] = market_status

        super().__init__(message, broker_name, details)


class AuthenticationError(BrokerError):
    """
    Raised when broker authentication fails.

    Examples:
        - Invalid API key/secret
        - Expired access token
        - Invalid credentials
        - Account suspended

    Attributes:
        auth_method: Authentication method that failed
    """
    def __init__(self, message: str, broker_name: str = None,
                 auth_method: str = None, details: dict = None):
        """
        Args:
            message: Human-readable error message
            broker_name: Name of the broker
            auth_method: Authentication method (e.g., "API_KEY", "TOKEN")
            details: Additional error details
        """
        self.auth_method = auth_method

        if not details:
            details = {}

        if auth_method:
            details['auth_method'] = auth_method

        super().__init__(message, broker_name, details)


class BrokerTimeoutError(BrokerError):
    """
    Raised when broker operation times out.

    Examples:
        - Order placement timeout
        - Account data query timeout
        - Connection timeout

    Attributes:
        operation: Operation that timed out
        timeout_seconds: Timeout duration
    """
    def __init__(self, message: str, broker_name: str = None,
                 operation: str = None, timeout_seconds: float = None, details: dict = None):
        """
        Args:
            message: Human-readable error message
            broker_name: Name of the broker
            operation: Operation that timed out
            timeout_seconds: Timeout duration in seconds
            details: Additional error details
        """
        self.operation = operation
        self.timeout_seconds = timeout_seconds

        if not details:
            details = {}

        if operation:
            details['operation'] = operation

        if timeout_seconds is not None:
            details['timeout_seconds'] = timeout_seconds

        super().__init__(message, broker_name, details)
