#!/usr/bin/env python3
"""
Script to close all open positions in IBKR paper account

Note: Positions are account-level, not client-level. Any client ID will see all positions.
"""
import sys
import time
import argparse
from ib_insync import IB, Stock, MarketOrder

def get_ibgateway_port():
    """Dynamically find IB Gateway port from docker"""
    import subprocess
    try:
        # Try port 4004 first (paper trading)
        result = subprocess.run(
            ["docker", "port", "ib-gateway-ibkr-testing-account", "4004"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            # Output format: 0.0.0.0:60951
            port_str = result.stdout.strip().split('\n')[0].split(':')[-1]
            return int(port_str)
        
        # Fall back to 4002 (live trading)
        result = subprocess.run(
            ["docker", "port", "ib-gateway-ibkr-testing-account", "4002"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            port_str = result.stdout.strip().split('\n')[0].split(':')[-1]
            return int(port_str)
    except Exception as e:
        print(f"⚠️  Could not auto-detect port: {e}")
    
    return None

def close_all_positions_for_account(host='127.0.0.1', port=None, client_id=999):
    """Close all positions in the account (positions are account-level, not client-level)"""
    
    # Auto-detect port if not provided
    if port is None:
        port = get_ibgateway_port()
        if port is None:
            print("❌ Could not detect IB Gateway port. Please specify --port")
            sys.exit(1)
    
    ib = IB()
    
    try:
        print("=" * 60)
        print("IBKR Position Cleanup Tool")
        print("=" * 60)
        print(f"Host: {host}")
        print(f"Port: {port}")
        print(f"Client ID: {client_id}")
        print("=" * 60)
        
        print(f"\n🔌 Connecting to IBKR Gateway...")
        ib.connect(host, port, clientId=client_id, readonly=False)
        print(f"✅ Connected")
        
        # Wait for connection to stabilize
        time.sleep(1)
        
        # Request all positions for this account
        ib.reqPositions()
        time.sleep(2)
        
        # Cancel all open orders first
        print(f"\n🔄 Checking open orders...")
        open_orders = ib.openOrders()
        if open_orders:
            print(f"   Found {len(open_orders)} open orders")
            for trade in open_orders:
                ib.cancelOrder(trade.order)
                print(f"   Cancelled order: {trade.order.orderId}")
            time.sleep(1)
        else:
            print("   No open orders")
        
        # Get all positions (account-level, visible to any client)
        positions = ib.positions()
        
        if not positions:
            print(f"\n✅ No open positions found")
            return
        
        print(f"\n📊 Found {len(positions)} open position(s):")
        for pos in positions:
            contract_type = type(pos.contract).__name__
            print(f"   • {pos.contract.symbol} ({contract_type}): {pos.position} @ avg cost ${pos.avgCost:.2f}")
        
        # Close each position individually
        print(f"\n🔨 Closing positions...")
        for pos in positions:
            if abs(pos.position) < 0.01:  # Skip if essentially zero
                continue
                
            symbol = pos.contract.symbol
            contract_type = type(pos.contract).__name__
            current_position = pos.position
            
            # Determine action to close
            if current_position > 0:
                action = 'SELL'  # Close LONG
            else:
                action = 'BUY'   # Close SHORT
            
            quantity = abs(current_position)
            
            print(f"\n   Closing {symbol} ({contract_type}): {action} {quantity}")
            
            # Use the exact contract from the position
            contract = pos.contract
            
            # Set SMART exchange for all orders to avoid routing issues
            contract.exchange = 'SMART'
            
            # Create market order to close
            order = MarketOrder(action, quantity)
            
            # Place order
            trade = ib.placeOrder(contract, order)
            
            # Wait for fill (up to 30 seconds)
            print(f"   Waiting for fill...")
            for i in range(60):
                time.sleep(0.5)
                ib.sleep(0)  # Process events
                status = trade.orderStatus.status
                if status in ['Filled', 'Cancelled', 'Inactive']:
                    break
                if i % 4 == 0:  # Print every 2 seconds
                    print(f"   ... status: {status}")
            
            if trade.orderStatus.status == 'Filled':
                print(f"   ✅ {symbol} position closed: {trade.orderStatus.filled} @ {trade.orderStatus.avgFillPrice:.2f}")
            else:
                print(f"   ❌ {symbol} order status: {trade.orderStatus.status}")
        
        print(f"\n✅ All positions processed")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        if ib.isConnected():
            ib.disconnect()
            print(f"🔌 Disconnected")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Close all IBKR positions')
    parser.add_argument('--host', default='127.0.0.1', help='IB Gateway host (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, help='IB Gateway port (default: auto-detect from docker)')
    parser.add_argument('--client-id', type=int, default=999, help='Client ID to use (default: 999)')
    
    args = parser.parse_args()
    
    close_all_positions_for_account(
        host=args.host,
        port=args.port,
        client_id=args.client_id
    )
