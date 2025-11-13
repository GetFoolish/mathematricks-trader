"""
Pydantic models for Account Data Service
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional

class AuthenticationDetails(BaseModel):
    """Authentication details for broker connection"""
    auth_type: str  # "TWS", "API", etc.
    host: Optional[str] = None
    port: Optional[int] = None
    client_id: Optional[int] = None
    username: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    access_token: Optional[str] = None


class Balances(BaseModel):
    """Account balance information"""
    base_currency: str = "USD"
    equity: float
    cash_balance: float
    margin_used: float
    margin_available: float
    unrealized_pnl: float
    realized_pnl: float
    margin_utilization_pct: float
    last_updated: datetime


class OpenPosition(BaseModel):
    """Open position details"""
    symbol: str
    quantity: float
    side: str  # "LONG" or "SHORT"
    avg_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    position_margin: Optional[float] = None


class TradingAccount(BaseModel):
    """Complete trading account model"""
    account_id: str = Field(alias="_id")
    account_name: str
    broker: str  # "IBKR", "Zerodha", etc.
    account_number: Optional[str] = None
    authentication_details: AuthenticationDetails
    balances: Balances
    open_positions: List[OpenPosition]
    positions_last_updated: datetime
    connection_status: str  # "CONNECTED", "DISCONNECTED", "ERROR"
    last_poll_time: Optional[datetime] = None
    last_poll_success: bool
    status: str  # "ACTIVE", "INACTIVE"
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True


class CreateAccountRequest(BaseModel):
    """Request to create a new trading account"""
    account_id: str
    account_name: str
    broker: str
    account_number: Optional[str] = None
    authentication_details: AuthenticationDetails
