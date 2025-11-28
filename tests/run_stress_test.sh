#!/bin/bash
# Quick Start Script for Stress Test

echo "🚀 MathematricksTrader Stress Test Quick Start"
echo "=============================================="
echo ""
echo "Available Commands:"
echo ""
echo "1. Start stress test (default settings):"
echo "   venv/bin/python tests/stress_test_trading.py"
echo ""
echo "2. Start with custom interval (fast - 10s):"
echo "   venv/bin/python tests/stress_test_trading.py --interval 10 --max-positions 3"
echo ""
echo "3. Start with slow testing (20s):"
echo "   venv/bin/python tests/stress_test_trading.py --interval 20 --max-positions 8"
echo ""
echo "4. Stop test:"
echo "   Press Ctrl+C (will cleanup automatically)"
echo ""
echo "5. Monitor execution logs:"
echo "   tail -f logs/execution_service.log"
echo ""
echo "6. Monitor stress test logs:"
echo "   tail -f logs/stress_test.log"
echo ""
echo "=============================================="
echo ""
read -p "Run default stress test now? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo "Starting stress test..."
    venv/bin/python tests/stress_test_trading.py
fi
