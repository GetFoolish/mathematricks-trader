#!/usr/bin/env python3
"""
Gmail Signal Collector - Polling Version

Single self-contained script that polls Gmail for trading signals and forwards them
to the Mathematricks API. Can run as a cron job or continuously in daemon mode.

Setup:
1. Create a .env file with required credentials:
   GMAIL_CLIENT_ID=your_client_id.apps.googleusercontent.com
   GMAIL_CLIENT_SECRET=your_client_secret
   MATHEMATRICKS_API_URL=https://your-api-url/api/signals
   MATHEMATRICKS_PASSPHRASE=your_passphrase
   STRATEGY_NAME=Gmail_Signal_Strategy (optional)
   SIGNAL_IDENTIFIER=SIGNAL (optional)
   POLL_INTERVAL_SECONDS=60 (optional, for daemon mode)

2. Install dependencies:
   pip install google-auth google-auth-oauthlib google-api-python-client python-dotenv requests

3. Run once to authenticate:
   python gmail_signal_collector.py --auth

4. Run continuously (daemon mode):
   python gmail_signal_collector.py --daemon

5. Or add to crontab (runs every 5 minutes):
   */5 * * * * cd /path/to/script && /usr/bin/python3 gmail_signal_collector.py >> /var/log/gmail_signal.log 2>&1

Usage:
  python gmail_signal_collector.py             # Check for new signals (one-time)
  python gmail_signal_collector.py --daemon    # Run continuously
  python gmail_signal_collector.py --auth      # Authenticate with Gmail
  python gmail_signal_collector.py --test      # Test API connection
  python gmail_signal_collector.py --dry-run   # Check for signals but don't send to API
"""

import os
import sys
import json
import re
import base64
import argparse
import time
import signal as signal_module
from datetime import datetime, timedelta
from pathlib import Path

# Google API imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Other imports
import requests
from dotenv import load_dotenv


# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Load and validate configuration from .env file"""
    
    def __init__(self):
        # Load .env file from project root (two levels up)
        script_dir = Path(__file__).parent
        project_root = script_dir.parent.parent
        env_path = project_root / '.env'
        
        if not env_path.exists():
            # Fallback to local .env
            env_path = script_dir / '.env'
        
        load_dotenv(env_path)
        print(f"Loading config from: {env_path}")
        
        # Gmail Configuration
        self.GMAIL_CLIENT_ID = os.getenv('GMAIL_CLIENT_ID')
        self.GMAIL_CLIENT_SECRET = os.getenv('GMAIL_CLIENT_SECRET')
        self.GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
        
        # Mathematricks API Configuration
        self.API_URL = os.getenv('MATHEMATRICKS_API_URL', 'https://mathematricks.fund/api/signals')
        self.PASSPHRASE = os.getenv('MATHEMATRICKS_PASSPHRASE')
        
        # Strategy Configuration
        self.STRATEGY_NAME = os.getenv('STRATEGY_NAME', 'Gmail_Signal_Strategy')
        self.SIGNAL_IDENTIFIER = os.getenv('SIGNAL_IDENTIFIER', 'SIGNAL')
        
        # Operational Settings
        self.TOKEN_FILE = script_dir / 'token.json'
        self.CREDENTIALS_FILE = script_dir / 'credentials.json'
        self.STATE_FILE = script_dir / '.gmail_state.json'
        self.MAX_EMAILS_PER_RUN = int(os.getenv('MAX_EMAILS_PER_RUN', '50'))
        self.LOOKBACK_HOURS = int(os.getenv('LOOKBACK_HOURS', '24'))
        self.POLL_INTERVAL_SECONDS = int(os.getenv('POLL_INTERVAL_SECONDS', '60'))
    
    def validate(self):
        """Validate required configuration"""
        required = {
            'GMAIL_CLIENT_ID': self.GMAIL_CLIENT_ID,
            'GMAIL_CLIENT_SECRET': self.GMAIL_CLIENT_SECRET,
            'MATHEMATRICKS_PASSPHRASE': self.PASSPHRASE
        }
        
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise ValueError(f"Missing required config: {', '.join(missing)}")
        
        return True


# ============================================================================
# STATE MANAGEMENT
# ============================================================================

class StateManager:
    """Track processed messages to avoid duplicates"""
    
    def __init__(self, state_file):
        self.state_file = Path(state_file)
        self.state = self._load_state()
    
    def _load_state(self):
        """Load state from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load state file: {e}")
        
        return {
            'processed_messages': [],
            'last_check': None,
            'last_history_id': None
        }
    
    def _save_state(self):
        """Save state to file"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"Error saving state: {e}")
    
    def is_processed(self, message_id):
        """Check if message was already processed"""
        return message_id in self.state.get('processed_messages', [])
    
    def mark_processed(self, message_id):
        """Mark message as processed"""
        if 'processed_messages' not in self.state:
            self.state['processed_messages'] = []
        
        if message_id not in self.state['processed_messages']:
            self.state['processed_messages'].append(message_id)
            
            # Keep only last 1000 messages
            if len(self.state['processed_messages']) > 1000:
                self.state['processed_messages'] = self.state['processed_messages'][-1000:]
            
            self._save_state()
    
    def update_check_time(self):
        """Update last check timestamp"""
        self.state['last_check'] = datetime.utcnow().isoformat()
        self._save_state()
    
    def update_history_id(self, history_id):
        """Update last processed history ID"""
        self.state['last_history_id'] = history_id
        self._save_state()
    
    def get_last_history_id(self):
        """Get last processed history ID"""
        return self.state.get('last_history_id')


# ============================================================================
# GMAIL AUTHENTICATION
# ============================================================================

class GmailAuth:
    """Handle Gmail OAuth2 authentication"""
    
    def __init__(self, config):
        self.config = config
        self.creds = None
        self.service = None
    
    def authenticate(self, force_reauth=False):
        """Authenticate and return Gmail service"""
        
        # Load existing token
        if not force_reauth and self.config.TOKEN_FILE.exists():
            try:
                self.creds = Credentials.from_authorized_user_file(
                    str(self.config.TOKEN_FILE), 
                    self.config.GMAIL_SCOPES
                )
            except Exception as e:
                print(f"Error loading token: {e}")
        
        # Refresh or get new credentials
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                print("Refreshing access token...")
                self.creds.refresh(Request())
            else:
                print("Starting OAuth flow...")
                
                # Create client config
                client_config = {
                    "installed": {
                        "client_id": self.config.GMAIL_CLIENT_ID,
                        "client_secret": self.config.GMAIL_CLIENT_SECRET,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": ["http://localhost"]
                    }
                }
                
                flow = InstalledAppFlow.from_client_config(
                    client_config, 
                    self.config.GMAIL_SCOPES
                )
                self.creds = flow.run_local_server(port=8080)
            
            # Save credentials
            with open(self.config.TOKEN_FILE, 'w') as token:
                token.write(self.creds.to_json())
            print(f"✓ Credentials saved to {self.config.TOKEN_FILE}")
        
        # Build service
        self.service = build('gmail', 'v1', credentials=self.creds)
        return self.service


# ============================================================================
# EMAIL PROCESSING
# ============================================================================

class EmailProcessor:
    """Process Gmail messages"""
    
    def __init__(self, service):
        self.service = service
    
    def search_messages(self, query, max_results=50):
        """Search for messages matching query"""
        try:
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            return results.get('messages', [])
        except HttpError as error:
            print(f"Error searching messages: {error}")
            return []
    
    def get_message(self, message_id):
        """Fetch full message by ID"""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            return message
        except HttpError as error:
            print(f"Error fetching message {message_id}: {error}")
            return None
    
    def get_headers(self, message):
        """Extract headers from message"""
        headers = {}
        if 'payload' in message and 'headers' in message['payload']:
            for header in message['payload']['headers']:
                headers[header['name']] = header['value']
        return headers
    
    def get_body(self, message):
        """Extract text body from message"""
        if 'payload' not in message:
            return ""
        
        payload = message['payload']
        
        # Simple body
        if 'body' in payload and 'data' in payload['body']:
            return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
        
        # Multipart message
        if 'parts' in payload:
            return self._get_multipart_body(payload['parts'])
        
        return ""
    
    def _get_multipart_body(self, parts):
        """Extract body from multipart message"""
        body = ""
        for part in parts:
            mime_type = part.get('mimeType', '')
            
            # Recursive for nested parts
            if 'parts' in part:
                body += self._get_multipart_body(part['parts'])
            elif mime_type == 'text/plain' and 'data' in part.get('body', {}):
                text = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                body += text
            elif mime_type == 'text/html' and not body and 'data' in part.get('body', {}):
                # Fallback to HTML
                html = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                body += html
        
        return body


# ============================================================================
# SIGNAL EXTRACTION
# ============================================================================

class SignalExtractor:
    """Extract and parse trading signals from email content"""
    
    def __init__(self, signal_identifier='SIGNAL'):
        self.signal_identifier = signal_identifier
    
    def contains_signal(self, subject, body):
        """Check if email contains signal identifier"""
        content = f"{subject}\n{body}"
        return self.signal_identifier in content
    
    def extract_signal(self, subject, body):
        """Extract signal data from email"""
        full_content = f"{subject}\n{body}"
        
        # Try JSON extraction first
        json_signal = self._extract_json(full_content)
        if json_signal:
            return json_signal
        
        # Try structured text
        text_signal = self._extract_text(full_content)
        if text_signal:
            return text_signal
        
        # Fallback: return raw content
        return {
            "type": "raw",
            "subject": subject,
            "content": body.strip()[:1000]  # Limit to 1000 chars
        }
    
    def _extract_json(self, content):
        """Try to extract JSON signal"""
        # Look for JSON objects
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.finditer(json_pattern, content, re.DOTALL)
        
        for match in matches:
            try:
                data = json.loads(match.group())
                # Validate trading signal fields
                if any(k in data for k in ['ticker', 'symbol', 'action', 'trade', 'signal', 'side']):
                    return data
            except json.JSONDecodeError:
                continue
        
        return None
    
    def _extract_text(self, content):
        """Extract structured signal from text"""
        signal = {}
        
        # Common patterns
        patterns = {
            'ticker': r'(?:ticker|symbol|stock)[\s:]+([A-Z]{1,10})',
            'action': r'(?:action|side|direction|signal)[\s:]+(\w+)',
            'price': r'(?:price|entry|at)[\s:]+\$?([\d,.]+)',
            'quantity': r'(?:quantity|qty|shares|size|contracts)[\s:]+(\d+)',
            'stop_loss': r'(?:stop[\s-]?loss|sl)[\s:]+\$?([\d,.]+)',
            'take_profit': r'(?:take[\s-]?profit|tp|target)[\s:]+\$?([\d,.]+)',
            'type': r'(?:type|order[\s-]?type)[\s:]+(\w+)',
        }
        
        for field, pattern in patterns.items():
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                signal[field] = match.group(1).strip()
        
        # Return if we found key fields
        if signal and ('ticker' in signal or 'action' in signal):
            return signal
        
        return None
    
    def format_for_api(self, signal_data, message_id, strategy_name, passphrase):
        """Format signal for Mathematricks API"""
        timestamp = int(datetime.now().timestamp())
        signal_id = f"gmail_{message_id}_{timestamp}"
        
        payload = {
            "strategy_name": strategy_name,
            "signal_sent_EPOCH": timestamp,
            "signalID": signal_id,
            "passphrase": passphrase,
            "signal": signal_data
        }
        
        return payload


# ============================================================================
# API FORWARDER
# ============================================================================

class APIForwarder:
    """Forward signals to Mathematricks API"""
    
    def __init__(self, api_url):
        self.api_url = api_url
    
    def send_signal(self, payload):
        """Send signal to API"""
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                return True, {
                    'status': 'success',
                    'signal_id': payload['signalID'],
                    'response': response.text
                }
            else:
                return False, {
                    'error': f"API returned {response.status_code}: {response.text}",
                    'status_code': response.status_code
                }
        
        except requests.exceptions.Timeout:
            return False, {'error': 'Request timed out'}
        except requests.exceptions.RequestException as e:
            return False, {'error': f'Request failed: {str(e)}'}
        except Exception as e:
            return False, {'error': f'Unexpected error: {str(e)}'}


# ============================================================================
# MAIN COLLECTOR
# ============================================================================

class GmailSignalCollector:
    """Main collector orchestrating all components"""
    
    def __init__(self, config):
        self.config = config
        self.state = StateManager(config.STATE_FILE)
        self.auth = GmailAuth(config)
        self.extractor = SignalExtractor(config.SIGNAL_IDENTIFIER)
        self.forwarder = APIForwarder(config.API_URL)
        self.email_processor = None
    
    def run(self, dry_run=False):
        """Main execution: check for signals and forward to API"""
        print(f"\n{'='*60}")
        print(f"Gmail Signal Collector - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        try:
            # Authenticate
            service = self.auth.authenticate()
            self.email_processor = EmailProcessor(service)
            
            # Build search query
            lookback = datetime.now() - timedelta(hours=self.config.LOOKBACK_HOURS)
            query = f'after:{lookback.strftime("%Y/%m/%d")} {self.config.SIGNAL_IDENTIFIER}'
            
            print(f"Searching for: {query}")
            print(f"Max results: {self.config.MAX_EMAILS_PER_RUN}")
            
            # Search for messages
            messages = self.email_processor.search_messages(query, self.config.MAX_EMAILS_PER_RUN)
            print(f"Found {len(messages)} matching messages")
            
            if not messages:
                print("No new signals found")
                self.state.update_check_time()
                return 0
            
            # Process each message
            signals_sent = 0
            signals_skipped = 0
            
            for msg_ref in messages:
                msg_id = msg_ref['id']
                
                # Skip if already processed
                if self.state.is_processed(msg_id):
                    signals_skipped += 1
                    continue
                
                # Fetch full message
                message = self.email_processor.get_message(msg_id)
                if not message:
                    continue
                
                # Extract headers and body
                headers = self.email_processor.get_headers(message)
                subject = headers.get('Subject', '')
                sender = headers.get('From', '')
                body = self.email_processor.get_body(message)
                
                print(f"\n📧 Message {msg_id}")
                print(f"   From: {sender}")
                print(f"   Subject: {subject}")
                
                # Check if it contains a signal
                if not self.extractor.contains_signal(subject, body):
                    print(f"   ⊘ No signal identifier found")
                    self.state.mark_processed(msg_id)
                    continue
                
                # Extract signal
                signal_data = self.extractor.extract_signal(subject, body)
                print(f"   ✓ Signal extracted: {json.dumps(signal_data, indent=6)}")
                
                # Format for API
                payload = self.extractor.format_for_api(
                    signal_data, 
                    msg_id, 
                    self.config.STRATEGY_NAME,
                    self.config.PASSPHRASE
                )
                
                # Send to API (or skip if dry run)
                if dry_run:
                    print(f"   [DRY RUN] Would send: {json.dumps(payload, indent=6)}")
                    signals_sent += 1
                else:
                    success, response = self.forwarder.send_signal(payload)
                    
                    if success:
                        print(f"   ✓ Sent to API: {payload['signalID']}")
                        signals_sent += 1
                    else:
                        print(f"   ✗ Failed to send: {response.get('error')}")
                
                # Mark as processed
                self.state.mark_processed(msg_id)
            
            # Update state
            self.state.update_check_time()
            
            # Summary
            print(f"\n{'='*60}")
            print(f"✓ Signals sent: {signals_sent}")
            print(f"⊘ Already processed: {signals_skipped}")
            print(f"{'='*60}\n")
            
            return signals_sent
        
        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()
            return -1
    
    def test_api(self):
        """Test API connection"""
        print(f"\n{'='*60}")
        print("Testing API Connection")
        print(f"{'='*60}")
        print(f"API URL: {self.config.API_URL}")
        
        test_payload = {
            "strategy_name": self.config.STRATEGY_NAME,
            "signal_sent_EPOCH": int(datetime.now().timestamp()),
            "signalID": f"TEST_{int(datetime.now().timestamp())}",
            "passphrase": self.config.PASSPHRASE,
            "signal": {
                "type": "test",
                "ticker": "TEST",
                "action": "BUY",
                "note": "Test signal from Gmail Signal Collector"
            }
        }
        
        print(f"\nSending test signal:")
        print(json.dumps(test_payload, indent=2))
        
        success, response = self.forwarder.send_signal(test_payload)
        
        if success:
            print(f"\n✓ API connection successful!")
            print(f"Response: {response}")
        else:
            print(f"\n✗ API connection failed!")
            print(f"Error: {response}")
        
        return success


# ============================================================================
# CLI INTERFACE
# ============================================================================

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Gmail Signal Collector - Polling Version',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check for new signals (one-time)
  python gmail_signal_collector.py

  # Run continuously (daemon mode)
  python gmail_signal_collector.py --daemon

  # Authenticate with Gmail (first-time setup)
  python gmail_signal_collector.py --auth

  # Test API connection
  python gmail_signal_collector.py --test

  # Dry run (check for signals but don't send to API)
  python gmail_signal_collector.py --dry-run --daemon

Cron Setup:
  # Run every 5 minutes
  */5 * * * * cd /path/to/script && python3 gmail_signal_collector.py >> /var/log/gmail_signal.log 2>&1

Daemon Mode:
  # Run continuously (recommended for Raspberry Pi)
  nohup python3 gmail_signal_collector.py --daemon >> /var/log/gmail_signal.log 2>&1 &
        """
    )
    
    parser.add_argument('--auth', action='store_true', help='Authenticate with Gmail')
    parser.add_argument('--test', action='store_true', help='Test API connection')
    parser.add_argument('--dry-run', action='store_true', help='Check for signals but do not send to API')
    parser.add_argument('--daemon', action='store_true', help='Run continuously (daemon mode)')
    parser.add_argument('--interval', type=int, help='Poll interval in seconds (default: 60)')
    
    args = parser.parse_args()
    
    try:
        # Load and validate config
        config = Config()
        
        if not args.auth:  # Skip validation for auth-only mode
            config.validate()
        
        # Create collector
        collector = GmailSignalCollector(config)
        
        # Execute command
        if args.auth:
            print("Authenticating with Gmail...")
            collector.auth.authenticate(force_reauth=True)
            print("✓ Authentication complete!")
            return 0
        
        elif args.test:
            success = collector.test_api()
            return 0 if success else 1
        
        elif args.daemon:
            # Daemon mode - run continuously
            poll_interval = args.interval or config.POLL_INTERVAL_SECONDS
            print(f"Starting daemon mode (polling every {poll_interval} seconds)")
            print("Press Ctrl+C to stop\n")
            
            # Setup signal handler for graceful shutdown
            def signal_handler(sig, frame):
                print("\n\nShutting down gracefully...")
                sys.exit(0)
            
            signal_module.signal(signal_module.SIGINT, signal_handler)
            signal_module.signal(signal_module.SIGTERM, signal_handler)
            
            # Run continuously
            while True:
                try:
                    collector.run(dry_run=args.dry_run)
                    
                    # Countdown timer
                    for remaining in range(poll_interval, 0, -1):
                        mins, secs = divmod(remaining, 60)
                        timer = f"{mins:02d}:{secs:02d}"
                        print(f"\rNext check in: {timer}", end='', flush=True)
                        time.sleep(1)
                    print()  # New line after countdown
                    
                except KeyboardInterrupt:
                    print("\n\nShutting down gracefully...")
                    return 0
                except Exception as e:
                    print(f"Error in daemon loop: {e}")
                    print(f"Retrying in {poll_interval} seconds...")
                    time.sleep(poll_interval)
        
        else:
            # Normal operation (one-time run)
            result = collector.run(dry_run=args.dry_run)
            return 0 if result >= 0 else 1
    
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("\nPlease create a .env file with required credentials:")
        print("  GMAIL_CLIENT_ID=...")
        print("  GMAIL_CLIENT_SECRET=...")
        print("  MATHEMATRICKS_PASSPHRASE=...")
        return 1
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
