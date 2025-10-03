#!/usr/bin/env python3
"""
Signal Sender for Mathematricks Fund
Sends trading signals to the webhook endpoint
"""

import requests
import time
import uuid
from datetime import datetime, timezone
import argparse

class SignalSender:
    def __init__(self, passphrase="yahoo123", use_staging=False):
        self.api_url = "https://staging.mathematricks.fund/api/signals" if use_staging else "https://mathematricks.fund/api/signals"
        self.passphrase = passphrase
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Mathematricks-SignalSender/1.0'
        })

    def send_signal(self, signal_id, signal_data, current_timestamp=None):
        """Send a trading signal to the webhook"""
        if current_timestamp is None:
            now = datetime.now(timezone.utc)
            current_timestamp = now.isoformat()
        else:
            now = datetime.fromisoformat(current_timestamp.replace('Z', '+00:00'))

        epoch_time = int(now.timestamp())

        payload = {
            # Required Pydantic fields
            "strategy_name": "Default Strategy",  # Required
            "signal_sent_EPOCH": epoch_time,      # Required
            "signalID": signal_id,                # Required

            # Optional fields
            "passphrase": self.passphrase,
            "timestamp": current_timestamp,
            "signal": signal_data  # Can be dict, list, or any structure
        }

        try:
            print(f"📡 Sending signal: {signal_id}")
            print(f"   Epoch: {epoch_time}")
            print(f"   URL: {self.api_url}")
            print(f"   Signal: {signal_data}")

            response = self.session.post(
                self.api_url,
                json=payload,
                timeout=10
            )

            print(f"   Status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print(f"   ✅ Success: {result.get('message', 'Signal sent')}")
                return True
            else:
                print(f"   ❌ Error: {response.text}")
                return False

        except requests.exceptions.Timeout:
            print(f"   ⏰ Timeout: Request took too long")
            return False
        except requests.exceptions.ConnectionError:
            print(f"   🔌 Connection Error: Could not reach webhook")
            return False
        except Exception as e:
            print(f"   💥 Unexpected Error: {str(e)}")
            return False

    def test_invalid_passphrase(self):
        """Test with invalid passphrase (should fail)"""
        print(f"\n🔒 Testing invalid passphrase...")
        old_passphrase = self.passphrase
        self.passphrase = "wrong_password"

        result = self.send_signal("test_001", {"ticker": "TEST", "action": "BUY", "price": 100.0})

        self.passphrase = old_passphrase
        return not result  # Should return True if it properly failed

    def run_test_suite(self):
        """Run a comprehensive test of the webhook"""
        print("🚀 Starting Mathematricks Webhook Test Suite")
        print("=" * 50)

        tests = [
            ("stock_001", {"ticker": "AAPL", "action": "BUY", "price": 150.25, "volume_24h": 50000000}),
            ("stock_002", {"ticker": "TSLA", "action": "SELL", "price": 245.75, "volume_24h": 75000000}),
            ("crypto_001", {"ticker": "BTC", "action": "BUY", "price": 42000.0, "volume_24h": 1000000}),
            ("crypto_002", {"ticker": "ETH", "action": "SELL", "price": 2500.0, "volume_24h": 800000}),
            ("options_001", {"type": "options", "ticker": "GOOGL", "strike": 140.50, "expiry": "2025-01-17", "action": "BUY_CALL"}),
            ("multi_leg_001", [{"ticker": "SPY", "action": "BUY", "quantity": 100}, {"ticker": "QQQ", "action": "SELL", "quantity": 50}]),
            ("stop_loss_001", {"trigger": "if AAPL < 145", "action": "SELL_ALL", "stop_loss": True})
        ]

        successful = 0
        total = len(tests)

        for i, (signal_id, signal_data) in enumerate(tests, 1):
            print(f"\n--- Test {i}/{total} ---")
            if self.send_signal(signal_id, signal_data):
                successful += 1
            time.sleep(1)  # Small delay between requests

        # Test invalid passphrase
        print(f"\n--- Security Test ---")
        if self.test_invalid_passphrase():
            print("   ✅ Security test passed (invalid passphrase rejected)")
        else:
            print("   ❌ Security test failed (invalid passphrase accepted)")

        print(f"\n📊 Results: {successful}/{total} signals sent successfully")
        return successful == total

def main():
    parser = argparse.ArgumentParser(description='Send trading signals to Mathematricks webhook')
    parser.add_argument('--signalId', required=True,
                       help='Unique signal identifier')
    parser.add_argument('--passphrase', default='yahoo123',
                       help='Webhook passphrase')
    parser.add_argument('--current_timestamp',
                       help='Current timestamp (ISO format, defaults to now)')
    parser.add_argument('--signal', required=True,
                       help='Signal data as JSON string (can be dict or list)')
    parser.add_argument('--staging', action='store_true',
                       help='Use staging environment')
    parser.add_argument('--test-suite', action='store_true',
                       help='Run full test suite')

    args = parser.parse_args()

    sender = SignalSender(args.passphrase, args.staging)

    if args.test_suite:
        sender.run_test_suite()
    elif args.signalId and args.signal:
        try:
            # Parse signal JSON
            import json
            signal_data = json.loads(args.signal)
            sender.send_signal(args.signalId, signal_data, args.current_timestamp)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in --signal: {e}")
            print("   Example: --signal '{\"ticker\": \"AAPL\", \"action\": \"BUY\", \"price\": 150.25}'")
    else:
        print("Usage examples:")
        print("  python signal_sender.py --test-suite")
        print("  python signal_sender.py --signalId 'strategy_1_001' --signal '{\"ticker\": \"AAPL\", \"action\": \"BUY\", \"price\": 150.25}'")
        print("  python signal_sender.py --staging --signalId 'strategy_1_001' --signal '{\"ticker\": \"AAPL\", \"action\": \"BUY\", \"price\": 150.25}'")
        print("  python signal_sender.py --signalId 'multi_leg_001' --signal '[{\"ticker\": \"SPY\", \"action\": \"BUY\"}, {\"ticker\": \"QQQ\", \"action\": \"SELL\"}]'")
        print("  python signal_sender.py --signalId 'options_001' --signal '{\"type\": \"options\", \"strike\": 150, \"expiry\": \"2025-01-17\", \"action\": \"BUY_CALL\"}'")
        print("  python signal_sender.py --signalId 'stop_loss_001' --signal '{\"trigger\": \"if AAPL < 145\", \"action\": \"SELL_ALL\", \"stop_loss\": true}'")

if __name__ == "__main__":
    main()