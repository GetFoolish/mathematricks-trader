#!/bin/bash
# Start Gmail Signal Collector in daemon mode
# This script will run continuously and poll Gmail every 60 seconds

cd "$(dirname "$0")"

echo "Starting Gmail Signal Collector in daemon mode..."
echo "Logs: ../../logs/gmail_signal_collector.log"
echo ""

# Create logs directory if it doesn't exist
mkdir -p ../../logs

# Run in background with nohup
nohup python3 gmail_signal_collector.py --daemon --interval 60 >> ../../logs/gmail_signal_collector.log 2>&1 &

# Save PID
echo $! > ../../logs/gmail_signal_collector.pid

echo "✓ Started with PID: $(cat ../../logs/gmail_signal_collector.pid)"
echo ""
echo "To stop: ./stop_gmail_daemon.sh"
echo "To view logs: tail -f ../../logs/gmail_signal_collector.log"
