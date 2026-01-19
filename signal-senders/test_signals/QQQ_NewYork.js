#!/usr/bin/env node
/**
 * Test Signal: QQQ (Nasdaq-100 ETF)
 * 
 * Strategy: QQQ_NewYork
 * Description: High liquidity tech ETF test
 * Use: Tuesday testing for tech sector exposure
 * 
 * Usage:
 *   node signal-senders/test_signals/QQQ_NewYork.js
 */

const axios = require('axios');

const SIGNAL_INGESTION_URL = process.env.SIGNAL_INGESTION_URL || 'http://localhost:8090/api/v1/signals/webhook';

// Test signal for QQQ
const signal = {
    strategy_id: "QQQ_NewYork",
    action: "ENTER",
    direction: "LONG",
    instrument: "QQQ",
    quantity: 5,
    order_type: "MARKET",
    signal_timestamp: new Date().toISOString(),
    metadata: {
        source: "test_signal",
        test_type: "high_liquidity_tech",
        description: "QQQ test during market hours - Nasdaq-100 tracking"
    }
};

async function sendSignal() {
    try {
        console.log('📤 Sending QQQ test signal...');
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
