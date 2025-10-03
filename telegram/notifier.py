#!/usr/bin/env python3
"""
Telegram Notifier for Mathematricks Trader
Sends notifications for signals, trades, and position updates
"""

import os
import requests
from typing import Dict, List, Optional
from datetime import datetime
from src.utils.logger import setup_logger

logger = setup_logger('telegram', 'telegram.log')


class TelegramNotifier:
    """
    Send notifications to Telegram
    """

    def __init__(self, bot_token: str = None, chat_id: str = None, enabled: bool = True):
        """
        Initialize Telegram notifier

        Args:
            bot_token: Telegram bot token
            chat_id: Telegram chat ID
            enabled: Whether notifications are enabled
        """
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')
        self.enabled = enabled and os.getenv('TELEGRAM_ENABLED', 'false').lower() == 'true'

        if self.enabled and (not self.bot_token or not self.chat_id):
            logger.warning("Telegram enabled but bot_token or chat_id not configured")
            self.enabled = False

        if self.enabled:
            logger.info("Telegram notifications enabled")
        else:
            logger.info("Telegram notifications disabled")

    def send_message(self, message: str, parse_mode: str = 'HTML') -> bool:
        """
        Send a message to Telegram

        Args:
            message: Message text
            parse_mode: Message parse mode (HTML or Markdown)

        Returns:
            True if sent successfully
        """
        if not self.enabled:
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': parse_mode
        }

        try:
            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                logger.debug("Telegram message sent successfully")
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    def notify_signal_received(self, signal_data: Dict) -> bool:
        """
        Notify when a new signal is received

        Args:
            signal_data: Signal data dictionary

        Returns:
            True if sent successfully
        """
        try:
            signal_id = signal_data.get('signalID', 'Unknown')
            strategy = signal_data.get('strategy_name', 'Unknown')
            timestamp = signal_data.get('timestamp', datetime.now().isoformat())
            signal = signal_data.get('signal', {})

            # Format signal details
            signal_details = self._format_signal_details(signal)

            message = f"""
🔔 <b>NEW SIGNAL RECEIVED</b>

📊 <b>Strategy:</b> {strategy}
🆔 <b>Signal ID:</b> {signal_id}
🕐 <b>Time:</b> {timestamp}

{signal_details}

⏳ <i>Processing signal...</i>
"""

            return self.send_message(message)

        except Exception as e:
            logger.error(f"Error formatting signal notification: {e}")
            return False

    def notify_trade_executed(
        self,
        signal_id: str,
        strategy_name: str,
        orders: List[Dict],
        execution_results: List[Dict]
    ) -> bool:
        """
        Notify when trades are executed

        Args:
            signal_id: Signal ID
            strategy_name: Strategy name
            orders: List of orders
            execution_results: List of execution results

        Returns:
            True if sent successfully
        """
        try:
            # Count successful trades
            successful = sum(1 for r in execution_results if r.get('status') in ['submitted', 'filled'])
            failed = len(execution_results) - successful

            # Format orders
            order_details = []
            for i, (order, result) in enumerate(zip(orders, execution_results), 1):
                status_icon = "✅" if result.get('status') in ['submitted', 'filled'] else "❌"
                order_details.append(
                    f"{status_icon} <b>{order.get('ticker', 'N/A')}</b> - "
                    f"{order.get('order_side', 'N/A')} {order.get('quantity', 0)} @ "
                    f"{order.get('broker', 'N/A')}"
                )

            orders_text = "\n".join(order_details)

            message = f"""
✅ <b>TRADES EXECUTED</b>

📊 <b>Strategy:</b> {strategy_name}
🆔 <b>Signal ID:</b> {signal_id}
🕐 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📈 <b>Orders:</b>
{orders_text}

📊 <b>Summary:</b>
✅ Successful: {successful}
❌ Failed: {failed}
"""

            return self.send_message(message)

        except Exception as e:
            logger.error(f"Error formatting trade notification: {e}")
            return False

    def notify_signal_failed(
        self,
        signal_id: str,
        strategy_name: str,
        error: str
    ) -> bool:
        """
        Notify when signal processing fails

        Args:
            signal_id: Signal ID
            strategy_name: Strategy name
            error: Error message

        Returns:
            True if sent successfully
        """
        try:
            message = f"""
❌ <b>SIGNAL PROCESSING FAILED</b>

📊 <b>Strategy:</b> {strategy_name}
🆔 <b>Signal ID:</b> {signal_id}
🕐 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

⚠️ <b>Error:</b>
<code>{error}</code>
"""

            return self.send_message(message)

        except Exception as e:
            logger.error(f"Error formatting failure notification: {e}")
            return False

    def notify_compliance_violation(
        self,
        signal_id: str,
        strategy_name: str,
        violations: List[str]
    ) -> bool:
        """
        Notify when compliance check fails

        Args:
            signal_id: Signal ID
            strategy_name: Strategy name
            violations: List of violation messages

        Returns:
            True if sent successfully
        """
        try:
            violations_text = "\n".join([f"• {v}" for v in violations])

            message = f"""
⚠️ <b>COMPLIANCE VIOLATION</b>

📊 <b>Strategy:</b> {strategy_name}
🆔 <b>Signal ID:</b> {signal_id}
🕐 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🚫 <b>Violations:</b>
{violations_text}

⛔ <i>Trade execution skipped</i>
"""

            return self.send_message(message)

        except Exception as e:
            logger.error(f"Error formatting compliance notification: {e}")
            return False

    def notify_position_closed(
        self,
        ticker: str,
        broker: str,
        quantity: float,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_pct: float
    ) -> bool:
        """
        Notify when a position is closed

        Args:
            ticker: Ticker symbol
            broker: Broker name
            quantity: Position quantity
            entry_price: Entry price
            exit_price: Exit price
            pnl: Profit/Loss amount
            pnl_pct: Profit/Loss percentage

        Returns:
            True if sent successfully
        """
        try:
            pnl_icon = "🟢" if pnl >= 0 else "🔴"
            pnl_sign = "+" if pnl >= 0 else ""

            message = f"""
{pnl_icon} <b>POSITION CLOSED</b>

📊 <b>Ticker:</b> {ticker}
🏦 <b>Broker:</b> {broker}
📦 <b>Quantity:</b> {quantity}

💰 <b>Entry Price:</b> ${entry_price:.2f}
💰 <b>Exit Price:</b> ${exit_price:.2f}

{pnl_icon} <b>P&L:</b> {pnl_sign}${pnl:.2f} ({pnl_sign}{pnl_pct:.2f}%)
🕐 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

            return self.send_message(message)

        except Exception as e:
            logger.error(f"Error formatting position closed notification: {e}")
            return False

    def notify_daily_summary(
        self,
        total_signals: int,
        total_trades: int,
        successful_trades: int,
        total_pnl: float,
        top_strategy: str = None
    ) -> bool:
        """
        Send daily summary notification

        Args:
            total_signals: Total signals received
            total_trades: Total trades executed
            successful_trades: Successful trades
            total_pnl: Total P&L
            top_strategy: Best performing strategy

        Returns:
            True if sent successfully
        """
        try:
            pnl_icon = "🟢" if total_pnl >= 0 else "🔴"
            pnl_sign = "+" if total_pnl >= 0 else ""

            message = f"""
📊 <b>DAILY SUMMARY</b>

📅 <b>Date:</b> {datetime.now().strftime('%Y-%m-%d')}

📈 <b>Activity:</b>
• Signals Received: {total_signals}
• Trades Executed: {total_trades}
• Success Rate: {(successful_trades/total_trades*100 if total_trades > 0 else 0):.1f}%

{pnl_icon} <b>Performance:</b>
• Total P&L: {pnl_sign}${total_pnl:.2f}
"""

            if top_strategy:
                message += f"\n🏆 <b>Top Strategy:</b> {top_strategy}"

            return self.send_message(message)

        except Exception as e:
            logger.error(f"Error formatting daily summary: {e}")
            return False

    def _format_signal_details(self, signal: Dict) -> str:
        """Format signal details for display"""
        if isinstance(signal, list):
            # Multi-leg order
            legs = []
            for leg in signal:
                legs.append(f"  • {leg.get('ticker', 'N/A')}: {leg.get('action', 'N/A')} {leg.get('qty', 0)}")
            return "<b>📋 Multi-leg Order:</b>\n" + "\n".join(legs)

        elif signal.get('type') == 'options':
            # Options signal
            return f"""<b>📋 Options Signal:</b>
  • Ticker: {signal.get('ticker', 'N/A')}
  • Action: {signal.get('action', 'N/A')}
  • Strike: ${signal.get('strike', 'N/A')}
  • Expiry: {signal.get('expiry', 'N/A')}"""

        elif signal.get('stop_loss'):
            # Stop-loss signal
            return f"""<b>🛑 Stop-Loss Signal:</b>
  • Trigger: {signal.get('trigger', 'N/A')}
  • Action: {signal.get('action', 'N/A')}"""

        else:
            # Stock signal
            return f"""<b>📋 Stock Signal:</b>
  • Ticker: {signal.get('ticker', 'N/A')}
  • Action: {signal.get('action', 'N/A')}
  • Price: ${signal.get('price', 'N/A')}"""
