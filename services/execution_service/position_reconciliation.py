"""
Position Reconciliation Engine

Handles EXIT signal processing by:
1. Querying broker for current position
2. Canceling pending ENTRY orders
3. Exiting filled positions to reach target
4. Retrying up to 6 times with delays
5. Alerting humans if reconciliation fails
"""

import time
import logging
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from brokers import OrderStatus

logger = logging.getLogger(__name__)


class ReconciliationResult:
    """Result of a reconciliation attempt"""
    def __init__(self):
        self.success = False
        self.attempts = []
        self.final_position = None
        self.target_position = None
        self.needs_manual_intervention = False
        self.error_message = None


def reconcile_exit_position(
    broker,
    order_data: Dict[str, Any],
    cerebro_decision: Dict[str, Any],
    max_retries: int = 6,
    retry_delay: float = 3.0
) -> ReconciliationResult:
    """
    Reconcile position to reach target (usually 0 for full EXIT, or calculated for partial).
    
    This function:
    - Queries broker for real-time position (not MongoDB)
    - Cancels any pending ENTRY orders
    - Exits filled position shares
    - Retries up to max_retries times
    - Returns detailed attempt history
    
    Args:
        broker: Broker instance with active connection
        order_data: Order data from Cerebro containing instrument, account, etc.
        cerebro_decision: Decision metadata with entry_order_ids, target_position, scale_out_percentage
        max_retries: Maximum number of reconciliation attempts (default: 6)
        retry_delay: Seconds to wait between attempts (default: 3.0)
    
    Returns:
        ReconciliationResult with success status and attempt history
    """
    result = ReconciliationResult()
    
    instrument = order_data.get('instrument')
    account_id = order_data.get('account_id')
    strategy_id = order_data.get('strategy_id')
    signal_id = order_data.get('signal_id')
    
    # Extract reconciliation parameters from cerebro decision
    decision_metadata = cerebro_decision.get('risk_metrics', {})
    entry_order_ids = decision_metadata.get('entry_order_ids', [])
    target_position = decision_metadata.get('target_position')  # 0 for full exit, None for partial
    scale_out_percentage = decision_metadata.get('scale_out_percentage', 100.0)
    
    logger.info(f"🔄 Starting position reconciliation for {instrument}")
    logger.info(f"   Signal: {signal_id}")
    logger.info(f"   Strategy: {strategy_id}")
    logger.info(f"   Account: {account_id}")
    logger.info(f"   Scale Out: {scale_out_percentage}%")
    logger.info(f"   Target Position: {target_position if target_position is not None else 'TBD'}")
    logger.info(f"   Entry Orders to Cancel: {len(entry_order_ids)}")
    logger.info(f"   Max Retries: {max_retries}")
    
    for attempt_num in range(1, max_retries + 1):
        logger.info(f"🔁 Reconciliation Attempt {attempt_num}/{max_retries}")
        attempt_data = {
            'attempt': attempt_num,
            'timestamp': datetime.utcnow().isoformat(),
            'cancel_results': [],
            'exit_results': [],
            'position_before': None,
            'position_after': None
        }
        
        try:
            # Step 1: Query broker for current position (TRUTH from broker, not MongoDB)
            current_position = get_current_position(broker, instrument, account_id)
            attempt_data['position_before'] = current_position
            logger.info(f"   Current Position: {current_position} shares")
            
            # Step 2: Cancel pending ENTRY orders
            if entry_order_ids:
                logger.info(f"   Attempting to cancel {len(entry_order_ids)} entry orders...")
                cancel_results = cancel_pending_orders(broker, entry_order_ids)
                attempt_data['cancel_results'] = cancel_results
                
                for cancel_res in cancel_results:
                    if cancel_res['success']:
                        logger.info(f"      ✅ Cancelled order {cancel_res['order_id']}")
                    elif cancel_res['reason'] == 'already_filled':
                        logger.info(f"      ℹ️  Order {cancel_res['order_id']} already filled")
                    else:
                        logger.warning(f"      ⚠️  Failed to cancel {cancel_res['order_id']}: {cancel_res['reason']}")
            
            # Step 3: Calculate target position for partial exits
            if target_position is None:
                # Partial exit - calculate based on scale_out_percentage
                qty_to_close = int(current_position * (scale_out_percentage / 100.0))
                calculated_target = current_position - qty_to_close
                logger.info(f"   Partial Exit: {current_position} × {scale_out_percentage}% = close {qty_to_close}, target {calculated_target}")
            else:
                # Full exit or explicit target
                calculated_target = target_position
                qty_to_close = current_position - target_position
                logger.info(f"   Target Position: {calculated_target}, need to close {qty_to_close}")
            
            result.target_position = calculated_target
            
            # Step 4: Exit current position if needed
            if current_position != calculated_target:
                qty_to_exit = abs(current_position - calculated_target)
                
                logger.info(f"   Sending exit order for {qty_to_exit} shares...")
                exit_result = send_exit_order(broker, instrument, qty_to_exit, order_data, current_position)
                attempt_data['exit_results'].append(exit_result)
                
                if exit_result['success']:
                    logger.info(f"      ✅ Exit order filled: {exit_result['quantity']} @ ${exit_result['avg_price']:.2f}")
                    
                    # CRITICAL: Update MongoDB position after successful exit
                    # Import here to avoid circular dependency
                    from execution_service.execution_main import create_or_update_position, update_signal_store_with_execution
                    
                    # Build order_data for position update (mark as EXIT)
                    exit_order_data = {
                        **order_data,
                        'signal_type': 'EXIT',
                        'action': 'EXIT'
                    }
                    create_or_update_position(exit_order_data, exit_result['quantity'], exit_result['avg_price'])
                    logger.info(f"      📝 Updated MongoDB position after exit")
                    
                    # Also update signal_store position field with execution data
                    execution_data = {
                        'broker_order_id': exit_result.get('broker_order_id'),
                        'quantity_filled': exit_result['quantity'],
                        'avg_fill_price': exit_result['avg_price'],
                        'fills': exit_result.get('fills', []),
                        'commission': exit_result.get('commission', 0)
                    }
                    update_signal_store_with_execution(exit_order_data, execution_data)
                    logger.info(f"      📊 Updated signal_store position field")
                else:
                    logger.warning(f"      ⚠️  Exit order failed: {exit_result['reason']}")
            else:
                logger.info(f"   ✅ Position already at target ({calculated_target})")
            
            # Step 5: Verify final position
            time.sleep(retry_delay)  # Wait for fills to propagate
            final_position = get_current_position(broker, instrument, account_id)
            attempt_data['position_after'] = final_position
            result.final_position = final_position
            
            logger.info(f"   Final Position: {final_position} (target: {calculated_target})")
            
            # Step 6: Check if reconciliation succeeded
            if final_position == calculated_target:
                logger.info(f"✅ Reconciliation SUCCESS on attempt {attempt_num}")
                result.success = True
                result.attempts.append(attempt_data)
                return result
            else:
                diff = abs(final_position - calculated_target)
                logger.warning(f"   ⚠️  Position not yet reconciled (off by {diff} shares)")
        
        except Exception as e:
            logger.error(f"   ❌ Error during reconciliation attempt {attempt_num}: {e}", exc_info=True)
            attempt_data['error'] = str(e)
        
        result.attempts.append(attempt_data)
        
        # Wait before next retry (except on last attempt)
        if attempt_num < max_retries:
            logger.info(f"   Waiting {retry_delay}s before retry...")
            time.sleep(retry_delay)
    
    # All retries exhausted - reconciliation failed
    logger.critical(f"🚨 Reconciliation FAILED after {max_retries} attempts!")
    logger.critical(f"   Instrument: {instrument}")
    logger.critical(f"   Current Position: {result.final_position}")
    logger.critical(f"   Target Position: {result.target_position}")
    logger.critical(f"   Gap: {abs(result.final_position - result.target_position) if result.final_position is not None else 'Unknown'}")
    
    result.success = False
    result.needs_manual_intervention = True
    result.error_message = f"Failed to reconcile position after {max_retries} attempts. Current: {result.final_position}, Target: {result.target_position}"
    
    return result


def get_current_position(broker, instrument: str, account_id: str) -> int:
    """
    Query broker for current position in instrument.
    
    Args:
        broker: Broker instance
        instrument: Symbol/ticker
        account_id: Account ID
    
    Returns:
        int: Current position quantity (positive for long, negative for short, 0 for flat)
    """
    try:
        positions = broker.get_open_positions(account_id=account_id)
        
        for pos in positions:
            if pos.get('instrument') == instrument:
                qty = pos.get('quantity', 0)
                side = pos.get('side', 'LONG')
                
                # Return signed quantity: positive for long, negative for short
                if side == 'SHORT':
                    return -abs(qty)
                else:
                    return abs(qty)
        
        # No position found
        return 0
    
    except Exception as e:
        logger.error(f"Error querying position for {instrument}: {e}", exc_info=True)
        return 0  # Assume flat on error


def cancel_pending_orders(broker, order_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Cancel a list of pending orders.
    
    Args:
        broker: Broker instance
        order_ids: List of broker order IDs to cancel
    
    Returns:
        List of cancel results with success/failure details
    """
    results = []
    
    for order_id in order_ids:
        try:
            # Check order status first
            status_info = broker.get_order_status(order_id)
            current_status = status_info.get('status', 'UNKNOWN')
            
            if current_status in ['FILLED', 'PARTIALLY_FILLED']:
                results.append({
                    'order_id': order_id,
                    'success': False,
                    'reason': 'already_filled',
                    'filled_quantity': status_info.get('filled_quantity', 0)
                })
                continue
            
            if current_status in ['CANCELLED']:
                results.append({
                    'order_id': order_id,
                    'success': True,
                    'reason': 'already_cancelled'
                })
                continue
            
            # Attempt cancellation
            cancel_success = broker.cancel_order(order_id)
            
            if cancel_success:
                results.append({
                    'order_id': order_id,
                    'success': True,
                    'reason': 'cancelled'
                })
            else:
                results.append({
                    'order_id': order_id,
                    'success': False,
                    'reason': 'cancel_failed'
                })
        
        except Exception as e:
            logger.error(f"Error canceling order {order_id}: {e}")
            results.append({
                'order_id': order_id,
                'success': False,
                'reason': f'error: {str(e)}'
            })
    
    return results


def send_exit_order(broker, instrument: str, quantity: int, original_order_data: Dict[str, Any], current_position: int = 0) -> Dict[str, Any]:
    """
    Send exit order to broker.
    
    Args:
        broker: Broker instance
        instrument: Symbol to exit
        quantity: Quantity to exit (positive number)
        original_order_data: Original order data for context (account, strategy, etc.)
        current_position: Current position to determine direction (positive=LONG, negative=SHORT)
    
    Returns:
        Dict with success status, quantity filled, avg price, etc.
    """
    try:
        # Debug: Log broker type
        broker_type = type(broker).__name__
        logger.info(f"   🔍 send_exit_order using broker: {broker_type}")
        if hasattr(broker, 'mode'):
            logger.info(f"   🔍 Broker mode: {broker.mode}")
        
        # Determine direction to close position
        # If current position is SHORT (negative), we BUY to close (direction='LONG')
        # If current position is LONG (positive), we SELL to close (direction='SHORT')
        if current_position < 0:
            direction = 'LONG'  # BUY to close SHORT
            logger.info(f"   🔍 Closing SHORT position (-{abs(current_position)}) with BUY order")
        else:
            direction = 'SHORT'  # SELL to close LONG
            logger.info(f"   🔍 Closing LONG position (+{abs(current_position)}) with SELL order")
        
        # Build exit order
        exit_order = {
            'order_id': f"{original_order_data.get('signal_id')}_EXIT_RECONCILE",
            'instrument': instrument,
            'instrument_type': original_order_data.get('instrument_type', 'STOCK'),
            'quantity': abs(quantity),
            'order_type': 'MARKET',  # Use market orders for exits to ensure fill
            'price': original_order_data.get('price', 0),  # Include price for mock broker
            'direction': direction,
            'action': 'EXIT',
            'account_id': original_order_data.get('account_id')
        }
        
        logger.info(f"   🔍 Exit order before place_order: price={exit_order.get('price')}")
        
        # Place order with broker
        broker_response = broker.place_order(exit_order)
        
        logger.info(f"   🔍 Broker response: {broker_response}")
        
        # Check if filled (case-insensitive check for broker compatibility)
        status = (broker_response.get('status') or '').upper()
        if status in ['FILLED', 'SUBMITTED']:
            # For mock broker, it fills immediately. For real broker, may need to wait
            time.sleep(0.5)  # Brief wait for fill
            
            # Get fill details
            broker_order_id = broker_response.get('broker_order_id')
            if broker_order_id:
                status_info = broker.get_order_status(broker_order_id)
                
                return {
                    'success': True,
                    'quantity': status_info.get('filled_quantity', quantity),
                    'avg_price': status_info.get('avg_fill_price', 0),
                    'broker_order_id': broker_order_id,
                    'status': status_info.get('status')
                }
            else:
                return {
                    'success': True,
                    'quantity': quantity,
                    'avg_price': 0,
                    'broker_order_id': None,
                    'status': 'FILLED'
                }
        else:
            return {
                'success': False,
                'reason': broker_response.get('message', 'Order not filled'),
                'status': broker_response.get('status')
            }
    
    except Exception as e:
        logger.error(f"Error sending exit order for {instrument}: {e}", exc_info=True)
        return {
            'success': False,
            'reason': f'Exception: {str(e)}'
        }


def start_telegram_alert_loop(
    signal_id: str,
    instrument: str,
    account_id: str,
    current_position: int,
    target_position: int,
    reconciliation_result: ReconciliationResult,
    broker,
    telegram_config: Optional[Dict[str, Any]] = None
):
    """
    Start background thread that sends Telegram alerts every 2 minutes until resolved.
    
    Args:
        signal_id: Signal identifier
        instrument: Symbol with stuck position
        account_id: Account ID
        current_position: Current position quantity
        target_position: Target position quantity
        reconciliation_result: Result object with attempt history
        broker: Broker instance to check position
        telegram_config: Optional Telegram configuration (bot token, chat ID)
    """
    if not telegram_config or not telegram_config.get('enabled', False):
        logger.warning("Telegram alerts disabled - no notifications will be sent")
        return
    
    def alert_loop():
        """Background thread function"""
        bot_token = telegram_config.get('bot_token')
        chat_id = telegram_config.get('chat_id')
        
        if not bot_token or not chat_id:
            logger.error("Missing Telegram bot_token or chat_id - cannot send alerts")
            return
        
        import requests
        
        attempt_count = 0
        while True:
            attempt_count += 1
            
            # Check current position
            live_position = get_current_position(broker, instrument, account_id)
            
            # Build alert message
            message = f"""
🚨 URGENT: EXIT ORDER RECONCILIATION FAILED

Signal: {signal_id}
Instrument: {instrument}
Account: {account_id}

Target Position: {target_position}
Current Position: {live_position}
Gap: {abs(live_position - target_position)}

Reconciliation Attempts: {len(reconciliation_result.attempts)}
Alert Attempts: {attempt_count}

Last Error: {reconciliation_result.error_message}

⚠️ ACTION REQUIRED: Manual intervention needed
Please resolve position manually and update system.
"""
            
            try:
                # Send Telegram message
                telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                response = requests.post(telegram_url, json={
                    'chat_id': chat_id,
                    'text': message
                })
                
                if response.status_code == 200:
                    logger.info(f"📱 Telegram alert sent (attempt {attempt_count})")
                else:
                    logger.error(f"Failed to send Telegram: {response.status_code} {response.text}")
            
            except Exception as e:
                logger.error(f"Error sending Telegram alert: {e}")
            
            # Check if position resolved
            if live_position == target_position:
                success_msg = f"""
✅ POSITION RESOLVED

Signal: {signal_id}
Instrument: {instrument}

Position successfully reconciled to target: {target_position}

Alert thread terminating.
"""
                try:
                    requests.post(telegram_url, json={
                        'chat_id': chat_id,
                        'text': success_msg
                    })
                except:
                    pass
                
                logger.info(f"✅ Position resolved - stopping alert thread")
                break
            
            # Wait 2 minutes before next alert
            time.sleep(120)
    
    # Start background thread
    alert_thread = threading.Thread(target=alert_loop, daemon=True)
    alert_thread.start()
    logger.info(f"📱 Started Telegram alert loop (2-minute interval)")
