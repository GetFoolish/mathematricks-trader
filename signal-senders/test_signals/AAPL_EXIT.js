#!/usr/bin/env node
/**
 * Test Signal: AAPL EXIT
 * 
 * Strategy: UPRO_NewYork (reusing existing strategy)
 * Description: Exit-only signal to close AAPL position
 * Use: Tuesday testing for position closing
 * 
 * Usage:
 *   node signal-senders/test_signals/AAPL_EXIT.js
 */

const axios = require('axios');

const SIGNAL_INGESTION_URL = process.env.SIGNAL_INGESTION_URL || 'http://localhost:8090/api/v1/signals/webhook';

// Exit signal for AAPL
const signal = {
    strategy_id: "UPRO_NewYork",
    action: "EXIT",
    direction: "FLAT",
    instrument: "AAPL",
    quantity: 1,  // Will be determined by current position
    order_type: "MARKET",
    signal_timestamp: new Date().toISOString(),
    metadata: {
        source: "test_signal",
        test_type: "exit_position",
        description: "AAPL exit test - closes existing position"
    }
};

async function sendSignal() {
    try {
        console.log('📤 Sending AAPL EXIT signal...');
        console.log(JSON.stringify(signal, null, 2));
        
        const response = await axios.post(SIGNAL_INGESTION_URL, signal, {
            headers: { 'Content-Type': 'application/json' }
        });
        
        console.log('✅ Signal sent successfully!');
        console.log(`📋 Response: ${JSON.stringify(response.data, null, 2)}`);
        
    } catch (error) {
        console.error('❌ Error sending signal:');
        if (error.response) {
            console.error(`Status: ${error.response.status}`);
            console.error(`Data: ${JSON.stringify(error.response.data, null, 2)}`);
        } else {
            console.error(error.message);
        }
        process.exit(1);
    }
}

sendSignal();
