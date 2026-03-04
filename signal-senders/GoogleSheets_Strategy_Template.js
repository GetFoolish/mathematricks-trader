/**
 * ============================================================================
 * MATHEMATRICKS TRADING SYSTEM - GOOGLE SHEETS STRATEGY TEMPLATE
 * ============================================================================
 * 
 * FEATURES:
 * - Position reconciliation (model vs actual positions)
 * - Automatic signal generation on position mismatch
 * - Error handling and retry logic
 * - Signal history tracking
 * - Support for all instrument types (STOCK, FOREX, OPTIONS, FUTURES)
 * - Forex residual handling (base currency conversion)
 * - Mode-aware routing (paper_live → live_live transition)
 * 
 * SETUP INSTRUCTIONS:
 * 1. Open your Google Sheet
 * 2. Extensions → Apps Script
 * 3. Copy this code
 * 4. Set Script Properties (Project Settings → Script Properties):
 *    - passphrase: your_webhook_passphrase
 *    - strategy_name: YOUR_STRATEGY_NAME
 *    - api_url: https://staging.mathematricks.fund/api/v1/signals (or production)
 * 5. Set up triggers:
 *    - onChange: Run captureOnChange
 *    - Time-based: Every 1 minute, run whenToTrigger
 * 
 * SHEET STRUCTURE:
 * 
 * Sheet: "SignalController"
 * | A          | B       | C        | D              | E                   | F            | G      | H   | I           | J           |
 * |------------|---------|----------|----------------|---------------------|--------------|--------|-----|-------------|-------------|
 * | Pair ID    | Is On?  | Symbol   | Model Position | Last Known Position | Signal Status| Action | Qty | Actual Pos  | Last Update |
 * | JPY/CHF-01 | 1       | JPY/CHF  | 25000          | 0                   | Sent         | BUY    | 25k | 25000       | 2026-02-02  |
 * | EUR/USD-02 | 1       | EUR/USD  | -10000         | 0                   | Sent         | SELL   | 10k | -10000      | 2026-02-02  |
 * 
 * CONFIGURATION CELLS (Top of SignalController sheet):
 * - C1: Last Updated (from data source)
 * - C2: Last Run timestamp
 * - C3: Account Equity
 * - D1: Last onChange timestamp
 * - D2: Countdown display
 * - E1: Trading Mode (staging/production)
 * - E2: Environment (mock_mock/mock_live/paper_live/live_live)
 * 
 * ============================================================================
 */

// ============================================================================
// CONFIGURATION
// ============================================================================

const CONFIG = {
  // Sheet Names
  CONTROLLER_SHEET_NAME: 'SignalController',
  HISTORY_SHEET_NAME: 'SignalHistory',
  POSITIONS_SHEET_NAME: 'ActualPositions',  // Fetched from API
  
  // Controller Sheet Columns (A=1, B=2, etc.)
  CONTROLLER_COLUMN: {
    PAIR_ID: 1,           // A - Unique identifier
    IS_ON: 2,             // B - Is trading enabled? (1=yes, 0=no)
    SYMBOL: 3,            // C - Instrument symbol (JPY/CHF, AAPL, etc.)
    MODEL_POS: 4,         // D - Desired position from strategy model
    LAST_KNOWN_POS: 5,    // E - Last known model position (for duplicate detection)
    SIGNAL_STATUS: 6,     // F - Status of last signal sent
    ACTION: 7,            // G - Last generated action (BUY/SELL)
    QTY: 8,               // H - Last generated quantity
    ACTUAL_POS: 9,        // I - Actual position from broker
    LAST_UPDATE: 10       // J - Timestamp of last update
  },
  
  // Configuration Cells
  LAST_UPDATED_CELL: 'C1',     // Last data update from source
  LAST_RUN_CELL: 'C2',         // Last script run
  ACCOUNT_EQUITY_CELL: 'C3',   // Account equity
  LAST_ONCHANGE_CELL: 'D1',    // Last onChange event
  COUNTDOWN_CELL: 'D2',        // Countdown to next run
  TRADING_MODE_CELL: 'E1',     // staging | production
  ENVIRONMENT_CELL: 'E2',      // mock_mock | mock_live | paper_live | live_live
  
  // Timing
  WAIT_MINUTES: 5,  // Wait 5 minutes after onChange before processing
  
  // Signal History Columns
  HISTORY_COLUMN: {
    TIMESTAMP: 1,
    SIGNAL_ID: 2,
    STRATEGY: 3,
    INSTRUMENT: 4,
    ACTION: 5,
    QUANTITY: 6,
    PRICE: 7,
    STATUS: 8,
    ACK_TIMESTAMP: 9,
    ACK_MESSAGE: 10,
    RESPONSE_CODE: 11,
    MODEL_POSITION: 12,
    ACTUAL_POSITION: 13,
    MODE: 14
  }
};

// ============================================================================
// SCRIPT PROPERTIES HELPERS
// ============================================================================

/**
 * Get script property with error handling
 */
function getScriptProperty(key, defaultValue = null) {
  const properties = PropertiesService.getScriptProperties();
  const value = properties.getProperty(key);
  
  if (!value && defaultValue === null) {
    throw new Error(`Script property '${key}' not set. Please set it in Project Settings → Script Properties.`);
  }
  
  return value || defaultValue;
}

/**
 * Get all required configuration
 */
function getConfig() {
  return {
    apiUrl: getScriptProperty('api_url', 'https://staging.mathematricks.fund/api/v1/signals'),
    passphrase: getScriptProperty('passphrase'),
    strategyName: getScriptProperty('strategy_name'),
    instrumentType: getScriptProperty('instrument_type', 'FOREX'),  // STOCK, FOREX, OPTION, FUTURE
    baseCurrency: getScriptProperty('base_currency', 'CAD'),  // For forex residual handling
    orderType: getScriptProperty('order_type', 'MARKET')  // MARKET or LIMIT
  };
}

// ============================================================================
// POSITION TRACKING & RECONCILIATION
// ============================================================================

/**
 * Fetch actual positions from Mathematricks API
 * This provides real-time position data from the broker
 */
function fetchActualPositions() {
  try {
    const config = getConfig();
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const controllerSheet = ss.getSheetByName(CONFIG.CONTROLLER_SHEET_NAME);
    
    // Get trading mode settings
    const tradingMode = controllerSheet.getRange(CONFIG.TRADING_MODE_CELL).getValue() || 'staging';
    const environment = controllerSheet.getRange(CONFIG.ENVIRONMENT_CELL).getValue() || 'mock_mock';
    
    // Build API URL for positions
    // TODO: Replace with actual position endpoint once implemented
    const positionsUrl = config.apiUrl.replace('/signals', `/positions?strategy=${config.strategyName}&mode=${environment}`);
    
    const options = {
      method: 'get',
      headers: {
        'Content-Type': 'application/json',
        'X-Strategy-Passphrase': config.passphrase  // Passphrase protection
      },
      muteHttpExceptions: true
    };
    
    const response = UrlFetchApp.fetch(positionsUrl, options);
    const responseCode = response.getResponseCode();
    
    if (responseCode === 200) {
      const data = JSON.parse(response.getContentText());
      return data.positions || [];  // Array of {instrument, quantity, side}
    } else {
      Logger.log(`⚠️  Could not fetch positions: HTTP ${responseCode}`);
      return [];
    }
  } catch (error) {
    Logger.log(`⚠️  Error fetching positions: ${error}`);
    return [];
  }
}

/**
 * Update actual positions in sheet from API
 */
function updateActualPositions() {
  const positions = fetchActualPositions();
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const controllerSheet = ss.getSheetByName(CONFIG.CONTROLLER_SHEET_NAME);
  
  // Build position map
  const positionMap = {};
  positions.forEach(pos => {
    positionMap[pos.instrument] = pos.quantity;
  });
  
  // Update sheet
  const lastRow = controllerSheet.getLastRow();
  if (lastRow < 5) return;
  
  const dataRange = controllerSheet.getRange(5, 1, lastRow - 4, CONFIG.CONTROLLER_COLUMN.LAST_UPDATE);
  const values = dataRange.getValues();
  
  for (let i = 0; i < values.length; i++) {
    const symbol = values[i][CONFIG.CONTROLLER_COLUMN.SYMBOL - 1];
    if (symbol && positionMap.hasOwnProperty(symbol)) {
      const actualPos = positionMap[symbol] || 0;
      controllerSheet.getRange(i + 5, CONFIG.CONTROLLER_COLUMN.ACTUAL_POS).setValue(actualPos);
    }
  }
}

/**
 * Check if signal already sent for this model position
 */
function getLastSignalForSymbol(symbol) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const historySheet = ss.getSheetByName(CONFIG.HISTORY_SHEET_NAME);
  
  if (!historySheet) return null;
  
  const lastRow = historySheet.getLastRow();
  if (lastRow < 2) return null;
  
  // Search from bottom (most recent)
  const data = historySheet.getRange(2, 1, lastRow - 1, CONFIG.HISTORY_COLUMN.MODE).getValues();
  
  for (let i = data.length - 1; i >= 0; i--) {
    const instrument = data[i][CONFIG.HISTORY_COLUMN.INSTRUMENT - 1];
    if (instrument === symbol) {
      return {
        modelPosition: data[i][CONFIG.HISTORY_COLUMN.MODEL_POSITION - 1],
        actualPosition: data[i][CONFIG.HISTORY_COLUMN.ACTUAL_POSITION - 1],
        status: data[i][CONFIG.HISTORY_COLUMN.STATUS - 1],
        timestamp: data[i][CONFIG.HISTORY_COLUMN.TIMESTAMP - 1]
      };
    }
  }
  
  return null;
}

// ============================================================================
// FOREX RESIDUAL HANDLING
// ============================================================================

/**
 * Generate forex residual cleanup signals
 * 
 * Example: Trading JPY/CHF leaves residuals in JPY and CHF
 * Solution: Convert residuals to base currency (CAD)
 * 
 * EXIT JPY/CHF 25000
 *   → Creates +25000 JPY and +25000 CHF residuals
 *   → Send: SELL JPY/CAD 25000 (convert JPY to CAD)
 *   → Send: SELL CHF/CAD 25000 (convert CHF to CAD)
 */
function generateForexResidualCleanup(baseSymbol, quantity, action) {
  const config = getConfig();
  
  if (config.instrumentType !== 'FOREX') {
    return [];  // Only relevant for forex
  }
  
  // Parse forex pair (e.g., JPY/CHF → ['JPY', 'CHF'])
  const currencies = baseSymbol.split('/');
  if (currencies.length !== 2) {
    Logger.log(`⚠️  Invalid forex pair format: ${baseSymbol}`);
    return [];
  }
  
  const baseCurrency = config.baseCurrency;
  const cleanupSignals = [];
  
  // On EXIT, we need to convert residuals back to base currency
  // Example: EXIT JPY/CHF leaves JPY and CHF
  // Convert both to CAD
  
  currencies.forEach(currency => {
    if (currency === baseCurrency) return;  // Skip if already base currency
    
    // Determine which direction to convert
    // If we exited a LONG position, we now have the quote currency
    // If we exited a SHORT position, we now have the base currency
    
    const conversionPair = `${currency}/${baseCurrency}`;
    const conversionAction = 'SELL';  // Sell foreign currency for base
    
    cleanupSignals.push({
      instrument: conversionPair,
      action: conversionAction,
      quantity: Math.abs(quantity),
      signalType: 'CLEANUP',  // Special type for cleanup
      reason: `Residual cleanup from ${baseSymbol} position`
    });
  });
  
  return cleanupSignals;
}

// ============================================================================
// MAIN SIGNAL PROCESSING
// ============================================================================

/**
 * Process all symbols and send signals where needed
 */
function parseSymbols() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const controllerSheet = ss.getSheetByName(CONFIG.CONTROLLER_SHEET_NAME);
  const config = getConfig();
  
  if (!controllerSheet) {
    Logger.log(`ERROR: "${CONFIG.CONTROLLER_SHEET_NAME}" sheet not found`);
    return;
  }
  
  // Update actual positions from API first
  updateActualPositions();
  
  // Read data
  const lastRow = controllerSheet.getLastRow();
  if (lastRow < 5) {
    Logger.log('No data rows to process');
    return;
  }
  
  const dataRange = controllerSheet.getRange(5, 1, lastRow - 4, controllerSheet.getLastColumn());
  const values = dataRange.getValues();
  
  const noSignalSymbols = [];
  
  for (let i = 0; i < values.length; i++) {
    const rowData = values[i];
    const rowIndex = i + 5;
    
    const signalProcessed = processSignal(rowData, rowIndex, controllerSheet);
    
    if (!signalProcessed) {
      const symbol = rowData[CONFIG.CONTROLLER_COLUMN.SYMBOL - 1];
      if (symbol && symbol !== '') {
        noSignalSymbols.push(symbol);
      }
    }
  }
  
  if (noSignalSymbols.length > 0) {
    Logger.log(`No signals needed for: ${noSignalSymbols.join(', ')}`);
  }
  
  updateLastRunTime();
}

/**
 * Process signal for a single symbol
 */
function processSignal(rowData, rowIndex, controllerSheet) {
  const config = getConfig();
  const symbol = rowData[CONFIG.CONTROLLER_COLUMN.SYMBOL - 1];
  
  if (!symbol || symbol === '') return false;
  
  const isOn = parseFloat(rowData[CONFIG.CONTROLLER_COLUMN.IS_ON - 1]) || 0;
  const modelPosition = parseFloat(rowData[CONFIG.CONTROLLER_COLUMN.MODEL_POS - 1]) || 0;
  const lastKnownPosition = parseFloat(rowData[CONFIG.CONTROLLER_COLUMN.LAST_KNOWN_POS - 1]) || 0;
  const actualPosition = parseFloat(rowData[CONFIG.CONTROLLER_COLUMN.ACTUAL_POS - 1]) || 0;
  
  // Safety checks
  if (isOn !== 1) return false;
  
  // Check if signal already sent
  const lastSignal = getLastSignalForSymbol(symbol);
  if (lastSignal && lastSignal.modelPosition === modelPosition) {
    return false;  // Already sent signal for this position
  }
  
  // Check if mismatch exists
  if (modelPosition === actualPosition) {
    return false;  // Positions match, no signal needed
  }
  
  // Calculate action and quantity
  const quantity = modelPosition - actualPosition;
  let action, signalType;
  
  if (quantity > 0) {
    action = 'BUY';
    signalType = (actualPosition === 0) ? 'ENTRY' : 'SCALE_IN';
  } else if (quantity < 0) {
    action = 'SELL';
    signalType = (modelPosition === 0) ? 'EXIT' : 'SCALE_OUT';
  } else {
    return false;
  }
  
  const absoluteQuantity = Math.abs(quantity);
  
  // Get account equity
  const accountEquity = controllerSheet.getRange(CONFIG.ACCOUNT_EQUITY_CELL).getValue() || 100000;
  
  // Get trading mode
  const tradingMode = controllerSheet.getRange(CONFIG.TRADING_MODE_CELL).getValue() || 'staging';
  const environment = controllerSheet.getRange(CONFIG.ENVIRONMENT_CELL).getValue() || 'mock_mock';
  
  // Parse environment into mode components
  const modeParts = environment.split('_');
  const accountType = modeParts[0] || 'mock';  // mock, paper, live
  const dataSource = modeParts[1] || 'mock';   // mock, live
  
  // Send primary signal
  const signalID = `signal_${config.strategyName}_${Date.now()}`;
  const price = 0;  // Use 0 for MARKET orders
  
  const result = sendSignal({
    strategyName: config.strategyName,
    symbol: symbol,
    price: price,
    action: action,
    quantity: absoluteQuantity,
    signalID: signalID,
    accountEquity: accountEquity,
    signalType: signalType,
    instrumentType: config.instrumentType,
    orderType: config.orderType,
    environment: tradingMode,
    mode: environment,
    accountType: accountType,
    dataSource: dataSource
  });
  
  // Log to history
  logSignalToHistory(
    signalID,
    config.strategyName,
    symbol,
    action,
    absoluteQuantity,
    price,
    modelPosition,
    actualPosition,
    result,
    environment
  );
  
  // Update controller sheet
  const timestamp = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss');
  
  if (result.success) {
    controllerSheet.getRange(rowIndex, CONFIG.CONTROLLER_COLUMN.SIGNAL_STATUS).setValue(`Sent (${timestamp})`);
    controllerSheet.getRange(rowIndex, CONFIG.CONTROLLER_COLUMN.ACTION).setValue(action);
    controllerSheet.getRange(rowIndex, CONFIG.CONTROLLER_COLUMN.QTY).setValue(absoluteQuantity);
    controllerSheet.getRange(rowIndex, CONFIG.CONTROLLER_COLUMN.LAST_KNOWN_POS).setValue(modelPosition);
    
    Logger.log(`✅ ${symbol} - Signal sent: ${action} ${absoluteQuantity}`);
    
    // FOREX RESIDUAL HANDLING: Send cleanup signals if this is an EXIT
    if (signalType === 'EXIT' && config.instrumentType === 'FOREX') {
      const cleanupSignals = generateForexResidualCleanup(symbol, absoluteQuantity, action);
      
      cleanupSignals.forEach(cleanup => {
        const cleanupSignalID = `${signalID}_cleanup_${cleanup.instrument}`;
        Logger.log(`🧹 Sending residual cleanup: ${cleanup.instrument} ${cleanup.action} ${cleanup.quantity}`);
        
        sendSignal({
          strategyName: config.strategyName,
          symbol: cleanup.instrument,
          price: 0,
          action: cleanup.action,
          quantity: cleanup.quantity,
          signalID: cleanupSignalID,
          accountEquity: accountEquity,
          signalType: 'CLEANUP',
          instrumentType: 'FOREX',
          orderType: config.orderType,
          environment: tradingMode,
          mode: environment,
          accountType: accountType,
          dataSource: dataSource
        });
      });
    }
  } else {
    controllerSheet.getRange(rowIndex, CONFIG.CONTROLLER_COLUMN.SIGNAL_STATUS).setValue(`Error (${timestamp})`);
    Logger.log(`❌ ${symbol} - Error: ${result.error}`);
  }
  
  return true;
}

// ============================================================================
// SEND SIGNAL TO API
// ============================================================================

/**
 * Send signal to Mathematricks API
 */
function sendSignal(params) {
  const config = getConfig();
  
  const {
    strategyName,
    symbol,
    price,
    action,
    quantity,
    signalID,
    accountEquity,
    signalType = 'ENTRY',
    instrumentType = 'FOREX',
    orderType = 'MARKET',
    environment = 'staging',
    mode = 'mock_mock',
    accountType = 'mock',
    dataSource = 'mock'
  } = params;
  
  // Determine direction
  const direction = action === 'BUY' ? 'LONG' : 'SHORT';
  
  // Build signal leg (matches current schema)
  const signalLeg = {
    instrument: symbol,
    instrument_type: instrumentType,
    action: action,
    direction: direction,
    quantity: quantity,
    order_type: orderType,
    price: price,
    environment: environment  // staging | production
  };
  
  // Build complete payload
  const payload = {
    strategy_name: strategyName,
    signal_sent_EPOCH: Math.floor(Date.now() / 1000),
    signalID: signalID,
    passphrase: config.passphrase,
    account_equity: accountEquity,
    signal_type: signalType,  // ENTRY, EXIT, SCALE_IN, SCALE_OUT, CLEANUP
    signal_legs: [signalLeg],
    
    // Mode routing (critical for proper broker selection)
    mode: mode,              // mock_mock, mock_live, paper_live, live_live
    account_type: accountType,  // mock, paper, live
    data_source: dataSource     // mock, live
  };
  
  const options = {
    method: 'post',
    contentType: 'application/json',
    muteHttpExceptions: true,
    payload: JSON.stringify(payload)
  };
  
  try {
    const response = UrlFetchApp.fetch(config.apiUrl, options);
    const responseCode = response.getResponseCode();
    
    if (responseCode !== 200) {
      return {
        success: false,
        error: `HTTP ${responseCode}: ${response.getContentText()}`,
        responseCode: responseCode
      };
    }
    
    return {
      success: true,
      responseCode: responseCode,
      response: response.getContentText()
    };
  } catch (error) {
    return {
      success: false,
      error: error.toString(),
      responseCode: null
    };
  }
}

// ============================================================================
// SIGNAL HISTORY TRACKING
// ============================================================================

/**
 * Log signal to history sheet
 */
function logSignalToHistory(signalID, strategy, symbol, action, quantity, price, modelPos, actualPos, result, mode) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let historySheet = ss.getSheetByName(CONFIG.HISTORY_SHEET_NAME);
  
  // Create sheet if doesn't exist
  if (!historySheet) {
    historySheet = ss.insertSheet(CONFIG.HISTORY_SHEET_NAME);
    historySheet.appendRow([
      'Timestamp', 'Signal ID', 'Strategy', 'Instrument', 'Action',
      'Quantity', 'Price', 'Status', 'Ack Timestamp', 'Ack Message',
      'Response Code', 'Model Position', 'Actual Position', 'Mode'
    ]);
  }
  
  const timestamp = new Date();
  const status = result.success ? 'Success' : 'Error';
  const message = result.success ? result.response : result.error;
  
  historySheet.appendRow([
    timestamp,
    signalID,
    strategy,
    symbol,
    action,
    quantity,
    price,
    status,
    result.success ? timestamp : '',
    message,
    result.responseCode || '',
    modelPos,
    actualPos,
    mode
  ]);
}

// ============================================================================
// TRIGGER FUNCTIONS
// ============================================================================

/**
 * Capture onChange event
 * Called by onChange trigger
 */
function captureOnChange() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const controllerSheet = ss.getSheetByName(CONFIG.CONTROLLER_SHEET_NAME);
  
  if (!controllerSheet) return;
  
  const timestamp = new Date();
  controllerSheet.getRange(CONFIG.LAST_ONCHANGE_CELL).setValue(timestamp);
  
  Logger.log(`onChange captured at ${timestamp}`);
}

/**
 * Check when to trigger signal processing
 * Called every 1 minute by time-based trigger
 */
function whenToTrigger() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const controllerSheet = ss.getSheetByName(CONFIG.CONTROLLER_SHEET_NAME);
  
  if (!controllerSheet) return;
  
  const lastOnChange = controllerSheet.getRange(CONFIG.LAST_ONCHANGE_CELL).getValue();
  const lastRun = controllerSheet.getRange(CONFIG.LAST_RUN_CELL).getValue();
  
  if (!lastOnChange) {
    controllerSheet.getRange(CONFIG.COUNTDOWN_CELL).setValue('No changes detected');
    return;
  }
  
  const now = new Date();
  const lastOnChangeTime = new Date(lastOnChange);
  const lastRunTime = lastRun ? new Date(lastRun) : new Date(0);
  
  const minutesSinceChange = (now - lastOnChangeTime) / 1000 / 60;
  const minutesRemaining = Math.max(0, CONFIG.WAIT_MINUTES - minutesSinceChange);
  
  if (minutesRemaining > 0) {
    const roundedMinutes = Math.ceil(minutesRemaining);
    controllerSheet.getRange(CONFIG.COUNTDOWN_CELL).setValue(`Next run in: ${roundedMinutes} min`);
  } else {
    if (lastOnChangeTime > lastRunTime) {
      controllerSheet.getRange(CONFIG.COUNTDOWN_CELL).setValue('Running now...');
      
      try {
        parseSymbols();
      } catch (error) {
        Logger.log('Error in parseSymbols: ' + error.toString());
        controllerSheet.getRange(CONFIG.COUNTDOWN_CELL).setValue('Error occurred');
      }
    } else {
      controllerSheet.getRange(CONFIG.COUNTDOWN_CELL).setValue('Up to date');
    }
  }
}

/**
 * Update last run timestamp
 */
function updateLastRunTime() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const controllerSheet = ss.getSheetByName(CONFIG.CONTROLLER_SHEET_NAME);
  
  if (controllerSheet) {
    const timestamp = new Date();
    controllerSheet.getRange(CONFIG.LAST_RUN_CELL).setValue(timestamp);
  }
}

// ============================================================================
// MANUAL UTILITIES
// ============================================================================

/**
 * Manual trigger - run immediately (for testing)
 */
function runNow() {
  parseSymbols();
}

/**
 * Clear signal history (for testing)
 */
function clearHistory() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const historySheet = ss.getSheetByName(CONFIG.HISTORY_SHEET_NAME);
  
  if (historySheet) {
    historySheet.clear();
    historySheet.appendRow([
      'Timestamp', 'Signal ID', 'Strategy', 'Instrument', 'Action',
      'Quantity', 'Price', 'Status', 'Ack Timestamp', 'Ack Message',
      'Response Code', 'Model Position', 'Actual Position', 'Mode'
    ]);
  }
}

/**
 * Refresh actual positions from API
 */
function refreshPositions() {
  updateActualPositions();
  Logger.log('✅ Positions refreshed');
}
