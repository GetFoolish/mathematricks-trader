#!/bin/bash
# Stop Gmail Signal Collector daemon

cd "$(dirname "$0")"

if [ -f ../../logs/gmail_signal_collector.pid ]; then
    PID=$(cat ../../logs/gmail_signal_collector.pid)
    echo "Stopping Gmail Signal Collector (PID: $PID)..."
    kill $PID 2>/dev/null
    rm ../../logs/gmail_signal_collector.pid
    echo "✓ Stopped"
else
    echo "No PID file found. Is the daemon running?"
    echo "Checking for running processes..."
    ps aux | grep "gmail_signal_collector.py --daemon" | grep -v grep
fi
