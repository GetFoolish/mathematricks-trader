#!/usr/bin/env node
/**
 * Test Signal: NVDA (NVIDIA)
 * 
 * Strategy: NVDA_NewYork
 * Description: High-price, high-volatility stock test
 * Use: Tuesday testing for expensive stocks with wide spreads
 * 
 * Usage:
 *   node signal-senders/test_signals/NVDA_NewYork.js
 */

const axios = require('axios');

const SIGNAL_INGESTION_URL = process.env.SIGNAL_INGESTION_URL || 'http://localhost:8090/api/v1/signals/webhook';

// Test signal for NVDA
const signal = {
    strategy_id: "NVDA_NewYork",
    action: "ENTER",
    direction: "LONG",
    instrument: "NVDA",
    quantity: 2,
    order_type: "MARKET",
    signal_timestamp: new Date().toISOString(),
    metadata: {
        source: "test_signal",
        test_type: "high_price_stock",
        description: "NVDA test during market hours - expensive stock with potentially wider spreads"
    }
};

async function sendSignal() {
    try {
        console.log('📤 Sending NVDA test signal...');
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
