📋 FINAL PLAN - Mathematricks Trader v3 Signal Architecture
Current State (v3 Branch):
✅ MongoDB integration exists (data_store.py)
✅ Signal collector exists at root level (signal_collector.py)
✅ Signal specification defined (SIGNAL_SPECIFICATION.md)
✅ Broker integrations exist (brokers)
✅ Signal processor exists (signal_processor.py)
✅ Pub/Sub bridge for microservices available

🎯 Implementation Plan
Phase 1: Create Strategy Adapter System
Location: src/data_collection/ (new folder)

Structure:

Adapter Responsibilities:

Validate incoming signal format (strategy-specific)
Transform to standard TradingSignal format
Specify acknowledgement handler
Specify broker routing preferences
Phase 2: Enhance Root signal_collector.py
Changes to signal_collector.py:

Add Strategy Registry:
Modify webhook handler to:
Extract strategy_name
Route to appropriate adapter
Get standardized TradingSignal
Store in MongoDB (already happening)
Forward to existing signal_processor.py
Get acknowledgement data after execution
Call strategy's ack handler
Phase 3: Extend MongoDB Schema
Add acknowledgement tracking to existing collections:

Phase 4: Update signal_processor.py
Add callback mechanism after execution:

Phase 5: Google Sheets Integration
google_sheets_handler.py will:

Deploy Google Apps Script as Web App (you'll do this)
POST acknowledgement data to Web App URL
Update both SignalHistory and SignalController sheets
Apps Script side (forex_signal_sender.js):

Create SignalHistory sheet with tracking
Implement doPost() to receive acks
Update SignalHistory status
Update SignalController actual position
Implement onEdit trigger with pending signal check
📊 Complete Data Flow
✅ Next Steps
Ready to implement? I'll:

✅ Create src/data_collection/ structure with adapters
✅ Create SignalControllerAdapter for Google Sheets signals
✅ Create GoogleSheetsAckHandler for acknowledgements
✅ Update signal_collector.py with routing logic
✅ Update data_store.py to track acknowledgements
✅ Modify signal_processor.py to support ack callbacks
✅ Update forex_signal_sender.js with full implementation