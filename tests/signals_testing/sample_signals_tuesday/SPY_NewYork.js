#!/usr/bin/env node
/**
 * Test Signal: SPY (S&P 500 ETF)
 * 
 * Strategy: SPY_NewYork
 * Description: High liquidity test with SPY - most liquid ETF in the world
 * Use: Tuesday testing for reliable fills and tight spreads
 * 
 * Usage:
 *   node signal-senders/test_signals/SPY_NewYork.js
 */

const axios = require('axios');

const SIGNAL_INGESTION_URL = process.env.SIGNAL_INGESTION_URL || 'http://localhost:8090/api/v1/signals/webhook';

// Test signal for SPY
const signal = {
    strategy_id: "SPY_NewYork",
    action: "ENTER",
    direction: "LONG",
    instrument: "SPY",
    quantity: 10,
    order_type: "MARKET",
    signal_timestamp: new Date().toISOString(),
    metadata: {
        source: "test_signal",
        test_type: "high_liquidity",
        description: "SPY test during market hours - expect tight spreads and fast fills"
    }
};

async function sendSignal() {
    try {
        console.log('📤 Sending SPY test signal...');
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
