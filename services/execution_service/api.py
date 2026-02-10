"""
Execution Service - FastAPI Endpoints
Handles all HTTP API requests for order execution and account management
"""
import logging
import os
from typing import Dict, Optional, Union
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
from pymongo import MongoClient
from bson import ObjectId

logger = logging.getLogger(__name__)

# MongoDB connection
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27018')
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client['mathematricks_trading']

# Will be set by execution_main.py
broker_pool = {}
service_ready = False


class ExecuteOrderRequest(BaseModel):
    """Order execution request from Cerebro"""
    order_id: str
    signal_id: Optional[str] = None
    strategy_id: Optional[str] = None
    fund_id: Optional[str] = None
    account_id: Optional[str] = None
    instrument: Optional[str] = None
    action: Optional[str] = None
    side: Optional[str] = None
    order_type: Optional[str] = None
    price: Optional[float] = None
    quantity: Optional[Union[int, float]] = None  # Support fractional quantities (crypto/forex)
    
    class Config:
        extra = "allow"


class ExecuteOrderResponse(BaseModel):
    """Order execution response"""
    status: str
    order_id: str
    message: str


# Create FastAPI app
app = FastAPI(title="Execution Service", version="2.0")


@app.get('/health')
def health_check():
    """Health check endpoint - returns 503 until service is ready"""
    if service_ready:
        # Get broker details
        brokers_info = {}
        for account_id, broker in broker_pool.items():
            broker_type = "Unknown"
            is_connected = False
            
            if hasattr(broker, 'broker_name'):
                broker_type = broker.broker_name
            if hasattr(broker, 'is_connected'):
                is_connected = broker.is_connected()
            
            brokers_info[account_id] = {
                'type': broker_type,
                'connected': is_connected
            }
        
        return {
            'status': 'healthy',
            'ready': True,
            'broker_pool_size': len(broker_pool),
            'brokers': brokers_info,
            'endpoints': {
                'health': 'GET /health',
                'status': 'GET /status',
                'market_status': 'GET /market_status',
                'get_price': 'GET /api/v1/price/{symbol}?broker={broker_name}&instrument_type={type}',
                'execute_order': 'POST /api/v1/execute-order',
                'sync_balance': 'POST /api/v1/sync-account-balance?account_id=<id>',
                'order_status': 'GET /api/v1/order/<order_id>/status',
                'cancel_order': 'POST /api/v1/order/<order_id>/cancel'
            }
        }
    else:
        return JSONResponse(
            status_code=503,
            content={
                'status': 'starting',
                'ready': False,
                'message': 'Service still initializing'
            }
        )


@app.get('/status')
def status_check():
    """Detailed status endpoint"""
    return {
        'ready': service_ready,
        'broker_pool_size': len(broker_pool),
        'brokers': list(broker_pool.keys())
    }


@app.get('/market_status')
def market_status_check():
    """
    Check broker connections and market status.
    Returns connection status for all brokers in the pool, plus market hours for different asset types.
    """
    try:
        import pytz
        from datetime import datetime, timedelta
        
        result = {
            'brokers': {},
            'ready': service_ready,
            'markets': {},
            'market_details': {},
            'canary_prices': {}
        }
        
        # Check each broker connection
        for account_id, broker in broker_pool.items():
            is_connected = False
            broker_type = "Unknown"
            
            if hasattr(broker, 'is_connected'):
                is_connected = broker.is_connected()
            
            if hasattr(broker, 'broker_name'):
                broker_type = broker.broker_name
            
            result['brokers'][account_id] = {
                'connected': is_connected,
                'broker_type': broker_type
            }
        
        # Check market hours for different asset types
        ny_tz = pytz.timezone('America/New_York')
        now_ny = datetime.now(ny_tz)
        
        # Market schedules (all times in ET)
        schedules = {
            'stock': {
                'weekdays': [0, 1, 2, 3, 4],  # Mon-Fri
                'open_time': (9, 30),
                'close_time': (16, 0),
                'name': 'Stock'
            },
            'option': {
                'weekdays': [0, 1, 2, 3, 4],
                'open_time': (9, 30),
                'close_time': (16, 0),
                'name': 'Option'
            },
            'forex': {
                'weekdays': [0, 1, 2, 3, 4, 6],  # Sun evening - Fri evening
                'open_time': (17, 0),
                'close_time': (17, 0),
                'name': 'Forex',
                '24_5': True
            },
            'crypto': {
                'weekdays': list(range(7)),  # 24/7
                'open_time': (0, 0),
                'close_time': (23, 59),
                'name': 'Crypto',
                '24_7': True
            }
        }
        
        for market_type, schedule in schedules.items():
            # Initialize market details
            market_detail = {
                'status': 'closed',
                'next_transition': None,
                'time_until_transition_seconds': None
            }
            
            # Check if it's a trading day
            if now_ny.weekday() not in schedule['weekdays']:
                result['markets'][market_type] = False
                # Calculate next open
                days_until_next_open = None
                for i in range(1, 8):
                    future_day = (now_ny + timedelta(days=i)).weekday()
                    if future_day in schedule['weekdays']:
                        days_until_next_open = i
                        break
                
                if days_until_next_open:
                    next_open = (now_ny + timedelta(days=days_until_next_open)).replace(
                        hour=schedule['open_time'][0],
                        minute=schedule['open_time'][1],
                        second=0,
                        microsecond=0
                    )
                    market_detail['next_transition'] = next_open.isoformat()
                    market_detail['time_until_transition_seconds'] = int((next_open - now_ny).total_seconds())
                
                result['market_details'][market_type] = market_detail
                continue
            
            # Handle 24/5 and 24/7 markets
            if schedule.get('24_5') or schedule.get('24_7'):
                result['markets'][market_type] = True
                market_detail['status'] = 'open'
                
                # For 24/5, calculate when weekend closes it
                if schedule.get('24_5'):
                    # Forex closes Friday at 5pm
                    if now_ny.weekday() == 4:  # Friday
                        close_time = now_ny.replace(hour=17, minute=0, second=0, microsecond=0)
                        if now_ny < close_time:
                            market_detail['next_transition'] = close_time.isoformat()
                            market_detail['time_until_transition_seconds'] = int((close_time - now_ny).total_seconds())
                    else:
                        # Calculate next Friday 5pm
                        days_until_friday = (4 - now_ny.weekday()) % 7
                        if days_until_friday == 0:
                            days_until_friday = 7
                        next_close = (now_ny + timedelta(days=days_until_friday)).replace(
                            hour=17, minute=0, second=0, microsecond=0
                        )
                        market_detail['next_transition'] = next_close.isoformat()
                        market_detail['time_until_transition_seconds'] = int((next_close - now_ny).total_seconds())
                
                result['market_details'][market_type] = market_detail
                continue
            
            # Check regular market hours
            current_time = now_ny.time()
            market_open_time = now_ny.replace(
                hour=schedule['open_time'][0],
                minute=schedule['open_time'][1],
                second=0,
                microsecond=0
            )
            market_close_time = now_ny.replace(
                hour=schedule['close_time'][0],
                minute=schedule['close_time'][1],
                second=0,
                microsecond=0
            )
            
            is_open = (market_open_time.time() <= current_time <= market_close_time.time())
            result['markets'][market_type] = is_open
            
            if is_open:
                market_detail['status'] = 'open'
                market_detail['next_transition'] = market_close_time.isoformat()
                market_detail['time_until_transition_seconds'] = int((market_close_time - now_ny).total_seconds())
            else:
                market_detail['status'] = 'closed'
                # Are we before open today or after close today?
                if current_time < market_open_time.time():
                    # Before open today
                    market_detail['next_transition'] = market_open_time.isoformat()
                    market_detail['time_until_transition_seconds'] = int((market_open_time - now_ny).total_seconds())
                else:
                    # After close today - find next open
                    days_until_next_open = None
                    for i in range(1, 8):
                        future_day = (now_ny + timedelta(days=i)).weekday()
                        if future_day in schedule['weekdays']:
                            days_until_next_open = i
                            break
                    
                    if days_until_next_open:
                        next_open = (now_ny + timedelta(days=days_until_next_open)).replace(
                            hour=schedule['open_time'][0],
                            minute=schedule['open_time'][1],
                            second=0,
                            microsecond=0
                        )
                        market_detail['next_transition'] = next_open.isoformat()
                        market_detail['time_until_transition_seconds'] = int((next_open - now_ny).total_seconds())
            
            result['market_details'][market_type] = market_detail
        
        # Get canary prices from each broker (validates data is flowing)
        for account_id, broker in broker_pool.items():
            broker_type = getattr(broker, 'broker_name', 'Unknown')
            
            try:
                # IBKR: Try AAPL stock (simple and always available during market hours)
                if broker_type == 'IBKR':
                    if hasattr(broker, 'get_market_price'):
                        try:
                            price = broker.get_market_price('AAPL', 'STOCK')
                            if price and price > 0:
                                result['canary_prices'][f'{account_id}:AAPL'] = round(price, 2)
                        except Exception as e:
                            logger.debug(f"IBKR canary AAPL failed: {e}")
                
                # Coinbase: Try BTC-USD
                elif broker_type == 'Coinbase':
                    if hasattr(broker, 'get_current_price'):
                        try:
                            price = broker.get_current_price('BTC-USD')
                            if price and price > 0:
                                result['canary_prices'][f'{account_id}:BTC-USD'] = round(price, 2)
                        except Exception as e:
                            logger.debug(f"Coinbase canary BTC-USD failed: {e}")
                
                # Mock: Always returns a test price
                elif broker_type == 'Mock':
                    result['canary_prices'][f'{account_id}:MOCK'] = 100.00
                    
            except Exception as e:
                logger.debug(f"Canary price failed for {account_id}: {e}")
        
        return result
    
    except Exception as e:
        logger.error(f"Error in market_status_check: {e}")
        return JSONResponse(
            status_code=500,
            content={'error': str(e), 'ready': False}
        )


@app.get('/api/v1/price/{symbol}')
def get_current_price(symbol: str, broker: Optional[str] = None, instrument_type: Optional[str] = 'STOCK'):
    """
    Get current market price for a symbol from a specific broker.
    
    Args:
        symbol: Ticker symbol (e.g., AAPL, EURUSD)
        broker: Broker account_id to query (if None, uses first available broker with get_market_price)
        instrument_type: Type of instrument (STOCK, FOREX, CRYPTO, etc.)
    
    Returns:
        {"symbol": "AAPL", "price": 175.50, "broker": "IBKR-PAPER", "timestamp": "..."}
    """
    try:
        # Find the broker to query
        target_broker = None
        broker_account_id = None
        
        if broker:
            # Use specified broker
            target_broker = broker_pool.get(broker)
            if not target_broker:
                raise HTTPException(
                    status_code=404,
                    detail=f"Broker '{broker}' not found. Available: {list(broker_pool.keys())}"
                )
            broker_account_id = broker
        else:
            # Find first broker with get_market_price capability
            for account_id, b in broker_pool.items():
                if hasattr(b, 'get_market_price'):
                    target_broker = b
                    broker_account_id = account_id
                    break
            
            if not target_broker:
                raise HTTPException(
                    status_code=400,
                    detail="No broker available with price lookup capability. Please specify broker parameter."
                )
        
        # Check if broker supports get_market_price
        if not hasattr(target_broker, 'get_market_price'):
            raise HTTPException(
                status_code=400,
                detail=f"Broker '{broker_account_id}' does not support live price lookup"
            )
        
        # Get the price
        price = target_broker.get_market_price(symbol, instrument_type)
        
        if price is None or price <= 0:
            raise HTTPException(
                status_code=404,
                detail=f"Could not get valid price for {symbol} from {broker_account_id}"
            )
        
        return {
            'symbol': symbol,
            'price': price,
            'broker': broker_account_id,
            'instrument_type': instrument_type,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting price for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching price: {str(e)}")


@app.post('/api/v1/execute-order', response_model=ExecuteOrderResponse)
def execute_order_endpoint(request: ExecuteOrderRequest):
    """
    Execute a trading order.
    Called by cerebro after creating order data.
    
    If data_source=live and account_type=mock, enriches order with live market price.
    """
    def _return_error(message: str, order_data: dict = None, signal_id_val: str = None,
                      fund_id_val: str = None, account_id_val: str = None):
        if signal_id_val and order_data:
            update_signal_store_execution(
                signal_id_val,
                {
                    'status': 'ERROR',
                    'error_reason': message
                },
                order_data,
                fund_id_val,
                account_id_val
            )
        return ExecuteOrderResponse(
            status='ERROR',
            order_id=request.order_id,
            message=message
        )

    try:
        logger.info(f"📥 API Request: Execute order {request.order_id}")
        logger.info(f"📋 FULL ORDER DATA: {request.dict()}")

        account_id = request.account_id
        signal_id = request.signal_id
        fund_id = request.fund_id

        if not account_id:
            return _return_error("Missing account_id")

        # Get broker from pool
        broker = broker_pool.get(account_id)
        if not broker:
            return _return_error(f"No broker found for account {account_id}")

        # Convert request to dict
        order_data = request.dict()

        # Check data_source - only fetch live prices if data_source='live'
        data_source = order_data.get('data_source', 'mock')
        
        # DEBUG: Log broker and data source info
        broker_name = getattr(broker, 'broker_name', 'Unknown')
        logger.info(f"🔍 DEBUG execute_order: broker_name={broker_name}, account_id={account_id}, data_source={data_source}")
        logger.info(f"🔍 DEBUG execute_order: order_type={order_data.get('order_type')}, instrument={order_data.get('instrument')}, signal_price={order_data.get('price')}")

        # If data_source='live', enrich with live price from the appropriate broker
        if data_source == 'live':
            symbol = order_data.get('instrument')
            instrument_type = order_data.get('instrument_type', 'STOCK')
            order_type = order_data.get('order_type', 'MARKET')

            # Only enrich MARKET orders (LIMIT orders already have limit_price)
            if order_type == 'MARKET' and symbol:
                # Deterministically select price broker from strategy mapping
                price_broker = None
                price_broker_id = None
                strategy_id = order_data.get('strategy_id')
                if strategy_id:
                    strategy_doc = db.strategies.find_one({"strategy_id": strategy_id}, {"accounts": 1, "_id": 0})
                    accounts_by_type = (strategy_doc or {}).get('accounts', {})
                    if isinstance(accounts_by_type, dict):
                        desired_accounts = accounts_by_type.get('paper', [])
                    else:
                        desired_accounts = accounts_by_type if data_source == 'live' else []

                    if desired_accounts:
                        price_broker_id = desired_accounts[0]
                        price_broker = broker_pool.get(price_broker_id)

                if not price_broker:
                    return _return_error(
                        f"No live price broker mapped for strategy {strategy_id}",
                        order_data, signal_id, fund_id, account_id
                    )

                logger.info(f"🔍 [{account_id}] Mock execution + Live data: Fetching price for {symbol} from {price_broker_id}")
                try:
                    if hasattr(price_broker, 'get_market_price'):
                        live_price = price_broker.get_market_price(symbol, instrument_type)
                    elif hasattr(price_broker, 'get_current_price'):
                        live_price = price_broker.get_current_price(symbol)
                    else:
                        raise Exception("No price method available on broker")
                    order_data['price'] = live_price
                    order_data['_price_source'] = f'{price_broker_id}_live'
                    order_data['_price_broker'] = price_broker_id  # Store actual broker used for price
                    logger.info(f"📈 Enriched {symbol} with live price: ${live_price:.2f} from {price_broker_id}")
                except Exception as e:
                    logger.error(f"❌ Failed to get live price for {symbol} from {price_broker_id}: {e}")
                    return _return_error(
                        f"Failed to fetch live price for {symbol}: {str(e)}",
                        order_data, signal_id, fund_id, account_id
                    )
        else:
            # DEBUG: Log why price enrichment was skipped
            logger.info(f"⏭️  DEBUG: Price enrichment SKIPPED - broker_name={broker_name}, is_mock={broker.broker_name == 'Mock' if hasattr(broker, 'broker_name') else 'N/A'}, data_source={data_source}")
            logger.info(f"💡 Order will use signal price: {order_data.get('price')} (no live price fetch)")

        # Submit order to broker
        try:
            result = broker.place_order(order_data)
        except Exception as e:
            logger.error(f"🚨 ERROR executing order {request.order_id}: {str(e)}", exc_info=True)
            return _return_error(f"Error executing order: {str(e)}", order_data, signal_id, fund_id, account_id)

        if not result:
            return _return_error("Broker rejected the order", order_data, signal_id, fund_id, account_id)

        logger.info(f"✅ Order {request.order_id} executed: {result.get('status')}")

        # Update signal_store with execution results
        if signal_id:
            update_signal_store_execution(signal_id, result, order_data, fund_id, account_id)

        return ExecuteOrderResponse(
            status=result.get('status', 'SUBMITTED'),
            order_id=request.order_id,
            message=f"Order {request.order_id} executed successfully"
        )

    except Exception as e:
        logger.error(f"🚨 ERROR executing order {request.order_id}: {str(e)}", exc_info=True)
        return _return_error(f"Error executing order: {str(e)}")


def update_signal_store_execution(signal_id: str, execution_result: Dict, order_data: Dict, fund_id: str, account_id: str):
    """Update signal_store with execution results and position summary"""
    try:
        # Extract leg_id from order_id (format: {signal_id}_{fund_id}_{account_id}_SL{leg_index}_ORD)
        order_id = order_data.get('order_id', '')
        leg_index = None
        
        # Parse leg index from order_id (e.g., SL0_ORD, SL1_ORD)
        if '_SL' in order_id and '_ORD' in order_id:
            try:
                leg_part = order_id.split('_SL')[1].split('_ORD')[0]
                leg_index = int(leg_part)
            except (IndexError, ValueError):
                logger.warning(f"Could not parse leg_index from order_id: {order_id}")
        
        if leg_index is None:
            logger.warning(f"No leg_index found for signal {signal_id}, skipping signal_store update")
            return
        
        # Build execution object
        status = execution_result.get('status', 'FILLED')
        is_error = status == 'ERROR'
        # Brokers return 'filled' not 'quantity_filled'
        quantity_filled = 0 if is_error else execution_result.get('filled', execution_result.get('quantity_filled', order_data.get('quantity', 0)))
        avg_fill_price = None if is_error else execution_result.get('avg_fill_price', order_data.get('price', 0))
        execution_obj = {
            'status': status,
            'error_reason': execution_result.get('error_reason'),
            'orders': [{
                'order_id': order_id,
                'fund_id': fund_id,
                'account_id': account_id,
                'broker': order_data.get('broker', 'Unknown'),  # Execution broker (where order executes)
                'data_source': order_data.get('data_source', 'mock'),  # Where data came from (mock/live)
                'price_broker': order_data.get('_price_broker'),  # Actual broker used for price enrichment (e.g., COINBASE-PAPER)
                'quantity_filled': quantity_filled,
                'avg_fill_price': avg_fill_price,
                'filled_at': None if is_error else datetime.utcnow(),
                'broker_order_id': execution_result.get('broker_order_id')
            }],
            'total_quantity_filled': quantity_filled,
            'weighted_avg_price': avg_fill_price
        }
        
        # Update signal_store with execution
        result = db.signal_store.update_one(
            {'signal_id': signal_id},
            {'$set': {
                f'legs.{leg_index}.execution': execution_obj,
                'updated_at': datetime.utcnow()
            }}
        )
        
        if result.modified_count > 0:
            logger.info(f"✅ Updated signal_store execution for {signal_id}, leg {leg_index}")
        else:
            logger.warning(f"⚠️  No signal_store document updated for {signal_id}")
            
        # Calculate and update position summary
        update_position_summary(signal_id)
            
    except Exception as e:
        logger.error(f"Error updating signal_store for {signal_id}: {e}", exc_info=True)


def update_account_balance_with_pnl(signal: Dict, realized_pnl: float):
    """
    Update trading_accounts balance after position is closed with realized P&L.
    
    Args:
        signal: Signal document with fund_id and account routing info
        realized_pnl: Gross realized P&L from the closed position
    """
    try:
        # Get account_id from first leg's execution
        legs = signal.get('legs', [])
        if not legs:
            logger.warning(f"No legs found in signal for balance update")
            return
            
        # Find first leg with execution
        account_id = None
        for leg in legs:
            execution = leg.get('execution')
            if execution and execution.get('orders'):
                account_id = execution['orders'][0].get('account_id')
                break
        
        if not account_id:
            logger.warning(f"No account_id found in signal execution, skipping balance update")
            return
        
        # Get current balances
        account = db.trading_accounts.find_one({"account_id": account_id})
        if not account:
            logger.warning(f"Account {account_id} not found for balance update")
            return
        
        balances = account.get('balances', {})
        current_equity = balances.get('equity', 0.0)
        current_cash = balances.get('cash_balance', balances.get('cash', 0.0))
        current_realized_pnl = balances.get('realized_pnl', 0.0)
        
        # Calculate new balances
        new_equity = current_equity + realized_pnl
        new_cash = current_cash + realized_pnl
        new_realized_pnl = current_realized_pnl + realized_pnl
        
        # Update account balances
        update_result = db.trading_accounts.update_one(
            {"account_id": account_id},
            {
                "$set": {
                    "balances.equity": new_equity,
                    "balances.cash_balance": new_cash,
                    "balances.cash": new_cash,
                    "balances.realized_pnl": new_realized_pnl,
                    "balances.timestamp": datetime.utcnow().isoformat() + "Z",
                    "last_balance_sync": datetime.utcnow()
                }
            }
        )
        
        if update_result.modified_count > 0:
            logger.info(
                f"💰 Updated {account_id} balance after position close: "
                f"Equity ${current_equity:,.2f} → ${new_equity:,.2f} "
                f"({'+' if realized_pnl >= 0 else ''}${realized_pnl:,.2f} P&L)"
            )
            
            # Update fund total_equity (sum of all account equities)
            fund_id = account.get('fund_id')
            if fund_id:
                update_fund_total_equity(fund_id)
        else:
            logger.warning(f"⚠️ No account balance updated for {account_id}")
            
    except Exception as e:
        logger.error(f"❌ Failed to update account balance with P&L: {e}", exc_info=True)


def update_fund_total_equity(fund_id: str):
    """
    Update fund's total_equity by summing all account equities for this fund.
    
    Args:
        fund_id: Fund identifier
    """
    try:
        # Get all accounts for this fund
        accounts = list(db.trading_accounts.find({"fund_id": fund_id}))
        
        # Sum all account equities
        total_equity = 0.0
        for account in accounts:
            balances = account.get('balances', {})
            account_equity = balances.get('equity', 0.0)
            total_equity += account_equity
        
        # Update fund document
        update_result = db.funds.update_one(
            {"fund_id": fund_id},
            {
                "$set": {
                    "total_equity": total_equity,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if update_result.modified_count > 0:
            logger.info(f"💼 Updated fund {fund_id} total_equity: ${total_equity:,.2f}")
        else:
            logger.warning(f"⚠️ Fund {fund_id} not found or not updated")
            
    except Exception as e:
        logger.error(f"❌ Failed to update fund total_equity for {fund_id}: {e}", exc_info=True)


def update_account_positions(signal: Dict, status: str, entry_quantity: float, entry_value: float, exit_quantity: float):
    """
    Update trading_accounts.open_positions array to track positions for deployed capital calculation.
    
    Args:
        signal: Signal document
        status: Position status ('OPEN', 'CLOSED', 'PENDING')
        entry_quantity: Total entry quantity
        entry_value: Total entry notional value
        exit_quantity: Total exit quantity
    """
    try:
        logger.info(f"🔍 update_account_positions called: status={status}, entry_qty={entry_quantity}, exit_qty={exit_quantity}")
        
        # Get account_id and strategy_id from signal
        legs = signal.get('legs', [])
        if not legs:
            return
            
        # Find first leg with execution to get account info
        account_id = None
        strategy_id = signal.get('strategy_id')
        instrument = signal.get('instrument')
        
        for leg in legs:
            execution = leg.get('execution')
            if execution and execution.get('orders'):
                account_id = execution['orders'][0].get('account_id')
                break
        
        if not account_id or not strategy_id or not instrument:
            logger.warning(f"Missing account_id/strategy_id/instrument for position tracking")
            return
        
        # Get direction from first leg
        first_leg = legs[0] if legs else {}
        first_decision = first_leg.get('decision', {})
        first_legs_data = first_decision.get('legs', [])
        direction = first_legs_data[0].get('direction', 'LONG') if first_legs_data else 'LONG'
        
        if status == 'OPEN':
            # Create or update position in open_positions array
            avg_entry_price = entry_value / entry_quantity if entry_quantity > 0 else 0
            
            position_doc = {
                'strategy_id': strategy_id,
                'instrument': instrument,
                'direction': direction,
                'quantity': entry_quantity - exit_quantity,  # Net quantity
                'avg_entry_price': avg_entry_price,
                'total_cost_basis': entry_value - (exit_quantity * avg_entry_price),
                'status': 'OPEN',
                'opened_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            # Upsert: remove old position with same direction and add new one
            db.trading_accounts.update_one(
                {"account_id": account_id},
                {
                    "$pull": {
                        "open_positions": {
                            "strategy_id": strategy_id,
                            "instrument": instrument,
                            "direction": direction  # Include direction to allow LONG + SHORT coexistence
                        }
                    }
                }
            )
            
            db.trading_accounts.update_one(
                {"account_id": account_id},
                {
                    "$push": {
                        "open_positions": position_doc
                    }
                }
            )
            
            logger.info(f"📍 Updated OPEN position for {strategy_id}/{instrument}: {entry_quantity - exit_quantity} @ ${avg_entry_price:.2f}")
            
        elif status == 'CLOSED':
            # Remove position from open_positions array (match by direction too)
            result = db.trading_accounts.update_one(
                {"account_id": account_id},
                {
                    "$pull": {
                        "open_positions": {
                            "strategy_id": strategy_id,
                            "instrument": instrument,
                            "direction": direction  # Include direction to match specific position
                        }
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"📍 Removed CLOSED position for {strategy_id}/{instrument}")
            
    except Exception as e:
        logger.error(f"❌ Failed to update account positions: {e}", exc_info=True)


def update_position_summary(signal_id: str):
    """Calculate and update position summary from all legs"""
    logger.info(f"🔍 update_position_summary called for {signal_id}")
    try:
        # Get signal with all legs
        signal = db.signal_store.find_one({'signal_id': signal_id})
        if not signal:
            logger.warning(f"Signal {signal_id} not found for position summary update")
            return
        
        legs = signal.get('legs', [])
        if not legs:
            return
        
        # Calculate position metrics
        entry_quantity = 0
        entry_value = 0
        exit_quantity = 0
        exit_value = 0
        
        for leg in legs:
            leg_type = leg.get('leg_type', '')
            execution = leg.get('execution')

            if not execution:
                continue

            qty = execution.get('total_quantity_filled', 0)
            price = execution.get('weighted_avg_price', None)

            # Only include legs with actual fills and a valid price
            if not qty or price is None:
                continue

            if leg_type in ['ENTRY', 'SCALE_IN']:
                entry_quantity += qty
                entry_value += qty * price
            elif leg_type in ['EXIT', 'SCALE_OUT']:
                exit_quantity += qty
                exit_value += qty * price
        
        # Determine position status
        if entry_quantity == 0:
            status = 'PENDING'
        elif exit_quantity >= entry_quantity:
            status = 'CLOSED'
        else:
            status = 'OPEN'
        
        # Calculate P&L if position is closed
        pnl = None
        if status == 'CLOSED' and entry_quantity > 0:
            # For SHORT positions (SELL to open), P&L = entry_value - exit_value
            # For LONG positions (BUY to open), P&L = exit_value - entry_value
            # We need to check the first leg's action to determine direction
            first_leg = legs[0] if legs else {}
            first_cerebro = first_leg.get('cerebro', {})  # FIX: Use 'cerebro' not 'decision'
            first_legs_data = first_cerebro.get('created_orders', [])  # FIX: Use 'created_orders' not 'legs'
            
            if first_legs_data:
                first_action = first_legs_data[0].get('action', 'BUY')
                direction = first_legs_data[0].get('direction', 'LONG')
                
                # Determine if this was a SHORT or LONG position
                if first_action == 'SELL' and direction == 'SHORT':
                    # SHORT position: profit when exit price < entry price
                    gross_pnl = entry_value - exit_value
                else:
                    # LONG position: profit when exit price > entry price
                    gross_pnl = exit_value - entry_value
                
                pnl = {
                    'gross': round(gross_pnl, 2),
                    'net': round(gross_pnl, 2),  # Commission calculation could be added here
                    'percent': round((gross_pnl / entry_value * 100), 2) if entry_value > 0 else 0,
                    'commission': 0  # Mock broker has no commission
                }
        
        # Build position object
        position = {
            'status': status,
            'entry_quantity': entry_quantity,
            'exit_quantity': exit_quantity
        }
        
        if pnl:
            position['pnl'] = pnl
            
            # Update account balance with realized P&L when position is CLOSED
            if status == 'CLOSED':
                update_account_balance_with_pnl(signal, pnl['gross'])
        
        # Update trading_accounts.open_positions array for position tracking
        try:
            logger.info(f"🎯 About to call update_account_positions: status={status}, entry_qty={entry_quantity}, exit_qty={exit_quantity}")
            update_account_positions(signal, status, entry_quantity, entry_value, exit_quantity)
            logger.info(f"✅ Successfully called update_account_positions")
        except Exception as e:
            logger.error(f"❌ Exception calling update_account_positions: {e}", exc_info=True)
        
        # Update signal_store
        db.signal_store.update_one(
            {'signal_id': signal_id},
            {'$set': {
                'position': position,
                'updated_at': datetime.utcnow()
            }}
        )
        
        logger.info(f"✅ Updated position summary for {signal_id}: {status} ({entry_quantity}/{exit_quantity})")
            
            
    except Exception as e:
        logger.error(f"Error updating signal_store for {signal_id}: {e}", exc_info=True)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"🚨 ERROR executing order {request.order_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error executing order: {str(e)}")


@app.post('/api/v1/sync-account-balance')
def sync_account_balance(account_id: str):
    """
    Sync account balance from broker.
    Fetches fresh balance data and returns it.
    """
    try:
        logger.info(f"📊 Balance sync request for {account_id}")
        
        # Get broker from pool
        broker = broker_pool.get(account_id)
        if not broker:
            raise HTTPException(
                status_code=404,
                detail=f"No broker found for account {account_id}"
            )
        
        # Check if broker is connected
        if hasattr(broker, 'is_connected') and not broker.is_connected():
            raise HTTPException(
                status_code=503,
                detail=f"Broker not connected for {account_id}"
            )
        
        # Get fresh balance from broker
        if hasattr(broker, 'get_account_balance'):
            balance = broker.get_account_balance()
            
            # Save to MongoDB
            try:
                update_result = db.trading_accounts.update_one(
                    {"account_id": account_id},
                    {
                        "$set": {
                            "balances": balance,
                            "last_balance_sync": datetime.utcnow()
                        }
                    }
                )
                
                if update_result.modified_count > 0:
                    logger.info(f"💾 Updated MongoDB balance for {account_id}")
                else:
                    logger.warning(f"⚠️ No MongoDB update for {account_id} (account may not exist)")
                    
            except Exception as e:
                logger.error(f"Failed to update MongoDB balance: {e}")
                # Continue anyway - return the balance even if save fails
            
            logger.info(f"✅ Synced balance for {account_id}")
            logger.info(f"   Equity: ${balance.get('equity', 0):,.2f}")
            
            return {
                "account_id": account_id,
                "balance": balance,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(
                status_code=501,
                detail=f"Balance sync not supported for broker type"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error syncing balance for {account_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error syncing balance: {str(e)}")


@app.get('/api/v1/order/{order_id}/status')
def get_order_status(order_id: str):
    """
    Get status of a specific order.
    First checks signal_store for historical orders, then queries live brokers.
    """
    try:
        logger.info(f"📋 Order status request for {order_id}")
        
        # First, check signal_store for completed orders
        signal = db.signal_store.find_one(
            {'legs.execution.orders.order_id': order_id},
            {'legs.execution.orders.$': 1, 'signal_id': 1, 'instrument': 1}
        )
        
        if signal and 'legs' in signal:
            for leg in signal.get('legs', []):
                execution = leg.get('execution')
                if execution:
                    for order in execution.get('orders', []):
                        if order.get('order_id') == order_id:
                            logger.info(f"✅ Found order {order_id} in signal_store")
                            return {
                                "order_id": order_id,
                                "signal_id": signal.get('signal_id'),
                                "instrument": signal.get('instrument'),
                                "account_id": order.get('account_id'),
                                "fund_id": order.get('fund_id'),
                                "status": execution.get('status', 'FILLED'),
                                "quantity_filled": order.get('quantity_filled'),
                                "avg_fill_price": order.get('avg_fill_price'),
                                "filled_at": order.get('filled_at'),
                                "source": "signal_store"
                            }
        
        # If not in signal_store, search live brokers
        for account_id, broker in broker_pool.items():
            if hasattr(broker, 'get_order_status'):
                try:
                    status = broker.get_order_status(order_id)
                    if status:
                        logger.info(f"✅ Found order {order_id} in broker {account_id}")
                        return {
                            "order_id": order_id,
                            "account_id": account_id,
                            "status": status,
                            "source": "broker"
                        }
                except Exception as e:
                    logger.debug(f"Order not found in broker {account_id}: {e}")
                    continue
        
        # Order not found anywhere
        raise HTTPException(
            status_code=404,
            detail=f"Order {order_id} not found in signal_store or any broker"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting order status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting order status: {str(e)}")


@app.post('/api/v1/order/{order_id}/cancel')
def cancel_order(order_id: str):
    """
    Cancel a pending order.
    First checks if order is already filled in signal_store.
    Only cancels if order is still pending.
    """
    try:
        logger.info(f"🚫 Cancel order request for {order_id}")
        
        # First check if order is already filled in signal_store
        signal = db.signal_store.find_one(
            {'legs.execution.orders.order_id': order_id}
        )
        
        if signal and 'legs' in signal:
            for leg in signal.get('legs', []):
                execution = leg.get('execution')
                if execution:
                    for order in execution.get('orders', []):
                        if order.get('order_id') == order_id:
                            status = execution.get('status', 'UNKNOWN').upper()
                            if status in ['FILLED', 'COMPLETED']:
                                raise HTTPException(
                                    status_code=400,
                                    detail=f"Cannot cancel order {order_id}: already {status}"
                                )
        
        # Search all brokers for this order and attempt cancellation
        for account_id, broker in broker_pool.items():
            if hasattr(broker, 'cancel_order'):
                try:
                    result = broker.cancel_order(order_id)
                    if result:
                        logger.info(f"✅ Cancelled order {order_id} in {account_id}")
                        return {
                            "order_id": order_id,
                            "account_id": account_id,
                            "status": "CANCELLED",
                            "message": "Order cancelled successfully"
                        }
                except Exception as e:
                    logger.debug(f"Order {order_id} not found in {account_id}: {e}")
                    continue
        
        # Order not found or already filled
        raise HTTPException(
            status_code=404,
            detail=f"Order {order_id} not found or cannot be cancelled"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error cancelling order: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error cancelling order: {str(e)}")


def run_api_server(broker_pool_ref: Dict, ready_flag: bool):
    """
    Run FastAPI server in main thread.
    Called by execution_main.py after broker pool is initialized.
    
    Args:
        broker_pool_ref: Reference to the broker pool dict
        ready_flag: Whether the service is ready
    """
    global broker_pool, service_ready
    broker_pool = broker_pool_ref
    service_ready = ready_flag
    
    logger.info("🚀 Starting API server on port 8083...")
    uvicorn.run(app, host='0.0.0.0', port=8083, log_level='error')
