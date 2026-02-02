#!/usr/bin/env python3
"""
Check recent signals in MongoDB to investigate test issues
"""
import os
import sys
from pymongo import MongoClient
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Use local connection (port 27018 from host)
MONGODB_URI = 'mongodb://localhost:27018/?directConnection=true'

def check_signals():
    """Check recent signals in trading_signals_raw"""
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        client.server_info()  # Test connection
        
        db = client['mathematricks_trading']
        signals_coll = db['trading_signals_raw']
        signal_store_coll = db['signal_store']
        
        # Get signals from last hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        
        # Get recent signals
        recent_signals = list(signals_coll.find(
            {'received_at': {'$gte': one_hour_ago}},
            {
                'signalID': 1,
                'account_type': 1,
                'data_source': 1,
                'mode': 1,
                'environment': 1,
                'received_at': 1,
                '_id': 1
            }
        ).sort('received_at', -1).limit(30))
        
        print(f"\n{'='*100}")
        print(f"RECENT SIGNALS (last 30, from past hour)")
        print(f"{'='*100}\n")
        
        if not recent_signals:
            print("No signals found in the last hour")
            return
        
        # Group by mode
        signals_by_mode = {}
        for sig in recent_signals:
            mode = sig.get('mode', 'UNKNOWN')
            if mode not in signals_by_mode:
                signals_by_mode[mode] = []
            signals_by_mode[mode].append(sig)
        
        # Print summary
        for mode, sigs in signals_by_mode.items():
            print(f"\n{mode.upper()} Mode: {len(sigs)} signals")
            print("-" * 100)
            for sig in sigs:
                signal_id = sig.get('signalID', 'NO_ID')
                account_type = sig.get('account_type', 'MISSING')
                data_source = sig.get('data_source', 'MISSING')
                env = sig.get('environment', 'MISSING')
                received = sig.get('received_at', '')
                
                # Check if processed in signal_store
                signal_store_doc = signal_store_coll.find_one(
                    {'signal_id': signal_id},
                    {'_id': 1, 'legs.decision.status': 1}
                )
                
                processed = "✅ PROCESSED" if signal_store_doc else "❌ NOT PROCESSED"
                if signal_store_doc:
                    first_leg = signal_store_doc.get('legs', [{}])[0]
                    decision_status = first_leg.get('decision', {}).get('status', 'UNKNOWN')
                    processed += f" ({decision_status})"
                
                print(f"  {signal_id[:40]:42s} | acc={account_type:6s} | data={data_source:6s} | env={env:10s} | {processed}")
        
        # Check for the specific failed signal
        print(f"\n{'='*100}")
        print(f"CHECKING SPECIFIC SIGNAL: sig_tech_stocks_009_786310_1769786310")
        print(f"{'='*100}\n")
        
        failed_signal = signals_coll.find_one({'signalID': 'sig_tech_stocks_009_786310_1769786310'})
        if failed_signal:
            print("Signal found in trading_signals_raw:")
            print(f"  signal_id: {failed_signal.get('signalID')}")
            print(f"  account_type: {failed_signal.get('account_type', 'MISSING')}")
            print(f"  data_source: {failed_signal.get('data_source', 'MISSING')}")
            print(f"  mode: {failed_signal.get('mode', 'MISSING')}")
            print(f"  environment: {failed_signal.get('environment', 'MISSING')}")
            print(f"  received_at: {failed_signal.get('received_at')}")
            
            # Check signal_store
            signal_store_doc = signal_store_coll.find_one({'signal_id': 'sig_tech_stocks_009_786310_1769786310'})
            if signal_store_doc:
                print("\n  ✅ Found in signal_store")
                first_leg = signal_store_doc.get('legs', [{}])[0]
                decision = first_leg.get('decision', {})
                print(f"    Decision: {decision.get('status', 'UNKNOWN')}")
                print(f"    Reason: {decision.get('reason', 'N/A')}")
            else:
                print("\n  ❌ NOT found in signal_store (signal-ingestion didn't process it)")
        else:
            print("Signal NOT found in trading_signals_raw!")
        
        client.close()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    check_signals()
