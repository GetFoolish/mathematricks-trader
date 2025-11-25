/**
 * ==================================================================
 * CONFIGURATION
 * ==================================================================
 */
const CONFIG = {
  STRATEGY_NAME: 'LeslieForex',
  CONTROLLER_SHEET_NAME: 'SignalController',
  CONTROLLER_COLUMN: {
    PAIR_ID: 1,           // Column A - Pair ID
    IS_ON: 2,             // Column B - Is On?
    SYMBOL: 3,            // Column C - Symbol
    MODEL_POS: 4,         // Column D - Model Position
    LAST_KNOWN_POS: 5,    // Column E - Last Known Model Position
    SIGNAL_STATUS: 6,     // Column F - Signal Status
    ACTION: 7,            // Column G - Generated Signal Action
    QTY: 8,               // Column H - Generated Signal Quantity
    ACTUAL_POS: 9,        // Column I - Actual Position
    LAST_UPDATE: 10       // Column J - Last Update
  },
  HISTORY_SHEET_NAME: 'SignalHistory',
  HISTORY_COLUMN: {
    TIMESTAMP: 1,
    SIGNAL_ID: 2,
    STRATEGY: 3,
    TICKER: 4,
    ACTION: 5,
    QUANTITY: 6,
    PRICE: 7,
    STATUS: 8,
    ACK_TIMESTAMP: 9,
    ACK_MESSAGE: 10,
    RESPONSE_CODE: 11,
    MODEL_POSITION: 12,
    ACTUAL_POSITION: 13
  }
};

/**
 * ==================================================================
 * MAIN CONTROLLER - Parses all symbols and processes signals
 * ==================================================================
 */
function parseSymbols() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const controllerSheet = ss.getSheetByName(CONFIG.CONTROLLER_SHEET_NAME);
  
  if (!controllerSheet) {
    Logger.log(`ERROR: The "${CONFIG.CONTROLLER_SHEET_NAME}" sheet was not found.`);
    SpreadsheetApp.getUi().alert(`Error: The "${CONFIG.CONTROLLER_SHEET_NAME}" sheet was not found. Please create it.`);
    return;
  }

  // Read all the data from the sheet
  const dataRange = controllerSheet.getRange(1, 1, controllerSheet.getLastRow(), controllerSheet.getLastColumn());
  const values = dataRange.getValues();
  
  // Track symbols with no signals needed
  const noSignalSymbols = [];
  
  // Iterate through rows (starting from row 2, skipping header)
  for (let i = 1; i < values.length; i++) {
    const rowData = values[i];
    const rowIndex = i + 1; // Actual sheet row number (1-indexed)
    
    // Process this symbol and track if no signal was needed
    const signalProcessed = processSignal(rowData, rowIndex, controllerSheet);
    
    if (!signalProcessed) {
      const symbol = rowData[CONFIG.CONTROLLER_COLUMN.SYMBOL - 1];
      if (symbol && symbol !== '') {
        noSignalSymbols.push(symbol);
      }
    }
  }
  
  // Log all symbols with no signals needed
  if (noSignalSymbols.length > 0) {
    Logger.log(`No Signals Needed for: ${noSignalSymbols.join(', ')}`);
  }
}

/**
 * ==================================================================
 * PROCESS SIGNAL - Handles signal logic for a single symbol
 * Returns true if signal was processed, false otherwise
 * ==================================================================
 */
function processSignal(rowData, rowIndex, controllerSheet) {
  // Extract data from row using CONFIG
  const symbol = rowData[CONFIG.CONTROLLER_COLUMN.SYMBOL - 1];
  
  // Safety check for empty rows
  if (!symbol || symbol === '') {
    return false;
  }
  
  const isOn = parseFloat(rowData[CONFIG.CONTROLLER_COLUMN.IS_ON - 1]) || 0;
  const modelPosition = parseFloat(rowData[CONFIG.CONTROLLER_COLUMN.MODEL_POS - 1]) || 0;
  const lastKnownPosition = parseFloat(rowData[CONFIG.CONTROLLER_COLUMN.LAST_KNOWN_POS - 1]) || 0;
  const actualPosition = parseFloat(rowData[CONFIG.CONTROLLER_COLUMN.ACTUAL_POS - 1]) || 0;
  
  // Safety Check 1: Is the system on?
  if (isOn !== 1) {
    return false;
  }
  
  // Safety Check 2: Check SignalHistory - has a signal already been sent for this model position?
  const lastSignal = getLastSignalForSymbol(symbol);
  if (lastSignal && lastSignal.modelPosition === modelPosition) {
    return false;
  }
  
  // Check if signal is needed (mismatch between model and actual positions)
  if (modelPosition === actualPosition) {
    return false;
  }
  
  // Calculate action and quantity
  const quantity = modelPosition - actualPosition;
  let action;
  
  if (quantity > 0) {
    action = 'BUY';
  } else if (quantity < 0) {
    action = 'SELL';
  } else {
    return false;
  }
  
  const absoluteQuantity = Math.abs(quantity);
  
  // Send the signal
  const price = 0;
  const signalID = "signal_" + new Date().getTime();
  const result = sendSignal(CONFIG.STRATEGY_NAME, symbol, price, action, absoluteQuantity, signalID);
  
  // Log to SignalHistory
  logSignalToHistory(signalID, CONFIG.STRATEGY_NAME, symbol, action, absoluteQuantity, price, modelPosition, actualPosition, result);
  
  // Update controller sheet based on result
  const timestamp = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss');
  
  // Always log the signal attempt
  if (result.success) {
    controllerSheet.getRange(rowIndex, CONFIG.CONTROLLER_COLUMN.SIGNAL_STATUS).setValue(`Sent (${timestamp})`);
    controllerSheet.getRange(rowIndex, CONFIG.CONTROLLER_COLUMN.ACTION).setValue(action);
    controllerSheet.getRange(rowIndex, CONFIG.CONTROLLER_COLUMN.QTY).setValue(absoluteQuantity);
    controllerSheet.getRange(rowIndex, CONFIG.CONTROLLER_COLUMN.LAST_KNOWN_POS).setValue(modelPosition);
    
    Logger.log(`${symbol} - ModelPosition: ${modelPosition}, LastKnownModelPosition: ${lastKnownPosition}, ActualPosition: ${actualPosition}, Signal: ${action} ${absoluteQuantity}`);
  } else {
    controllerSheet.getRange(rowIndex, CONFIG.CONTROLLER_COLUMN.SIGNAL_STATUS).setValue(`Error (${timestamp})`);
    
    Logger.log(`${symbol} - ModelPosition: ${modelPosition}, LastKnownModelPosition: ${lastKnownPosition}, ActualPosition: ${actualPosition}, Signal: ERROR - ${result.error}`);
  }
  
  return true;
}

/**
 * ==================================================================
 * SEND SIGNAL - Sends signal to API endpoint
 * ==================================================================
 */
function sendSignal(strategyName, symbol, price, action, quantity = null, signalID = null) {
  const url = 'https://mathematricks.fund/api/signals';
  // Retrieve the passphrase securely from Script Properties.
  const properties = PropertiesService.getScriptProperties();
  const api_passphrase = properties.getProperty('passphrase');

  // Best Practice: Check if the passphrase was found before proceeding.
  if (!api_passphrase) {
    throw new Error('ERROR: API_PASSPHRASE is not set in Script Properties.');
  }

  const signalData = {
    "ticker": symbol,
    "action": action,
    "price": price
  };

  // Add quantity if provided
  if (quantity !== null) {
    signalData.quantity = quantity;
  }

  const postData = {
    "strategy_name": strategyName,
    "signal_sent_EPOCH": Math.floor(new Date().getTime() / 1000),
    "signalID": signalID || "signal_" + new Date().getTime(),
    "passphrase": api_passphrase,
    "signal": signalData
  };
  
  const options = {
    'method': 'post',
    'contentType': 'application/json',
    'muteHttpExceptions': true,
    'payload': JSON.stringify(postData)
  };
  
  try {
    const response = UrlFetchApp.fetch(url, options);
    const responseCode = response.getResponseCode();
    
    if (responseCode !== 200) {
      const errorMsg = `HTTP ${responseCode}: ${response.getContentText()}`;
      return {
        success: false,
        error: errorMsg,
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

/**
 * ==================================================================
 * TRIGGER FUNCTIONS
 * ==================================================================
 */

/**
 * handleEdit - Works with existing trigger "handleEdit"
 * Triggers on ANY sheet edit to catch both direct edits and source data changes
 */
function handleEdit(e) {
  // Only run if we have event data
  if (!e || !e.range) {
    return;
  }
  
  // Get the sheet name and range that was edited
  const sheetName = e.source.getActiveSheet().getName();
  const editedColumn = e.range.getColumn();
  const editedRow = e.range.getRow();
  
  // Option 1: Edit directly on SignalController sheet
  if (sheetName === CONFIG.CONTROLLER_SHEET_NAME) {
    const relevantColumns = [
      CONFIG.CONTROLLER_COLUMN.IS_ON,
      CONFIG.CONTROLLER_COLUMN.SYMBOL,
      CONFIG.CONTROLLER_COLUMN.MODEL_POS,
      CONFIG.CONTROLLER_COLUMN.ACTUAL_POS
    ];
    
    if (editedRow === 1 || !relevantColumns.includes(editedColumn)) {
      return;
    }
    
    try {
      parseSymbols();
    } catch (error) {
      Logger.log('Error in handleEdit trigger: ' + error.toString());
    }
    return;
  }
  
  // Option 2: Edit on Sheet1 (or any source sheet that feeds formulas)
  // This catches changes to cells referenced by INDIRECT formulas
  if (sheetName === 'Sheet1') {
    // Skip header row
    if (editedRow === 1) {
      return;
    }
    
    try {
      parseSymbols();
    } catch (error) {
      Logger.log('Error in handleEdit trigger from Sheet1: ' + error.toString());
    }
  }
}

/**
 * ==================================================================
 * SIGNAL HISTORY FUNCTIONS
 * ==================================================================
 */

/**
 * Gets the last signal sent for a specific symbol from SignalHistory
 * Returns { modelPosition, status, timestamp } or null if no history exists
 */
function getLastSignalForSymbol(symbol) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const historySheet = ss.getSheetByName(CONFIG.HISTORY_SHEET_NAME);
  
  if (!historySheet) {
    // No history sheet exists, so no previous signals
    return null;
  }
  
  const lastRow = historySheet.getLastRow();
  
  // If only header row exists (or empty sheet), no signals
  if (lastRow <= 1) {
    return null;
  }
  
  // Get all data from history sheet
  const dataRange = historySheet.getRange(2, 1, lastRow - 1, CONFIG.HISTORY_COLUMN.ACTUAL_POSITION);
  const values = dataRange.getValues();
  
  // Search backwards (from most recent) for this symbol
  for (let i = values.length - 1; i >= 0; i--) {
    const rowTicker = values[i][CONFIG.HISTORY_COLUMN.TICKER - 1];
    
    if (rowTicker === symbol) {
      // Found the most recent signal for this symbol
      return {
        modelPosition: parseFloat(values[i][CONFIG.HISTORY_COLUMN.MODEL_POSITION - 1]) || 0,
        status: values[i][CONFIG.HISTORY_COLUMN.STATUS - 1],
        timestamp: values[i][CONFIG.HISTORY_COLUMN.TIMESTAMP - 1]
      };
    }
  }
  
  // No signal found for this symbol
  return null;
}

/**
 * Creates the SignalHistory sheet with proper headers
 */
function createSignalHistorySheet(ss) {
  const historySheet = ss.insertSheet(CONFIG.HISTORY_SHEET_NAME);
  
  // Set headers
  const headers = [
    'Timestamp',
    'Signal ID',
    'Strategy',
    'Ticker',
    'Action',
    'Quantity',
    'Price',
    'Status',
    'Ack Timestamp',
    'Ack Message',
    'Response Code',
    'Model Position',
    'Actual Position'
  ];
  
  historySheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  
  // Format header row
  historySheet.getRange(1, 1, 1, headers.length)
    .setFontWeight('bold')
    .setBackground('#4285f4')
    .setFontColor('#ffffff');
  
  // Freeze header row
  historySheet.setFrozenRows(1);
  
  // Auto-resize columns
  for (let i = 1; i <= headers.length; i++) {
    historySheet.autoResizeColumn(i);
  }
  
  return historySheet;
}

/**
 * Logs a signal to the SignalHistory sheet
 * Now accepts the send result and logs everything in one call
 */
function logSignalToHistory(signalID, strategyName, ticker, action, quantity, price, modelPosition, actualPosition, result) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let historySheet = ss.getSheetByName(CONFIG.HISTORY_SHEET_NAME);
  
  if (!historySheet) {
    historySheet = createSignalHistorySheet(ss);
  } else {
    // Check if headers exist
    const headerCheck = historySheet.getRange(1, 1).getValue();
    if (headerCheck !== 'Timestamp') {
      // Insert headers
      historySheet.insertRowBefore(1);
      
      const headers = [
        'Timestamp',
        'Signal ID',
        'Strategy',
        'Ticker',
        'Action',
        'Quantity',
        'Price',
        'Status',
        'Ack Timestamp',
        'Ack Message',
        'Response Code',
        'Model Position',
        'Actual Position'
      ];
      
      historySheet.getRange(1, 1, 1, headers.length).setValues([headers]);
      historySheet.getRange(1, 1, 1, headers.length)
        .setFontWeight('bold')
        .setBackground('#4285f4')
        .setFontColor('#ffffff');
      historySheet.setFrozenRows(1);
    }
  }
  
  const timestamp = new Date();
  const status = result.success ? 'Sent' : 'Error';
  const ackMessage = result.success ? (result.response || '') : result.error;
  
  const rowData = [
    timestamp,              // A: Timestamp
    signalID,              // B: Signal ID
    strategyName,          // C: Strategy
    ticker,                // D: Ticker
    action,                // E: Action
    quantity,              // F: Quantity
    price,                 // G: Price
    status,                // H: Status
    timestamp,             // I: Ack Timestamp
    ackMessage,            // J: Ack Message
    result.responseCode || '', // K: Response Code
    modelPosition,         // L: Model Position
    actualPosition         // M: Actual Position
  ];
  
  historySheet.appendRow(rowData);
  
  const lastRow = historySheet.getLastRow();
  
  // Format timestamp columns
  historySheet.getRange(lastRow, CONFIG.HISTORY_COLUMN.TIMESTAMP).setNumberFormat('yyyy-mm-dd hh:mm:ss');
  historySheet.getRange(lastRow, CONFIG.HISTORY_COLUMN.ACK_TIMESTAMP).setNumberFormat('yyyy-mm-dd hh:mm:ss');
  
  // Color code status
  const statusCell = historySheet.getRange(lastRow, CONFIG.HISTORY_COLUMN.STATUS);
  if (result.success) {
    statusCell.setBackground('#d4edda').setFontColor('#155724');
  } else {
    statusCell.setBackground('#f8d7da').setFontColor('#721c24');
  }
}

/**
 * ==================================================================
 * TIMER TRIGGER SETUP - Runs parseSymbols every 5 minutes
 * ==================================================================
 */

/**
 * Setup time-based trigger to run parseSymbols every 5 minutes
 * Run this function once manually to install the trigger
 */
function setupTimerTrigger() {
  // Delete any existing parseSymbols triggers to avoid duplicates
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(trigger => {
    if (trigger.getHandlerFunction() === 'parseSymbolsWithTimer') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
  
  // Create new 5-minute trigger
  ScriptApp.newTrigger('parseSymbolsWithTimer')
    .timeBased()
    .everyMinutes(5)
    .create();
  
  Logger.log('✅ Timer trigger installed - parseSymbols will run every 5 minutes');
  
  // Initialize the timer display cell
  updateLastRunTime();
}

/**
 * Wrapper function that runs parseSymbols and updates the timer display
 * This is what the trigger actually calls
 */
function parseSymbolsWithTimer() {
  parseSymbols();
  updateLastRunTime();
}

/**
 * Updates cell K1 with the last run timestamp
 */
function updateLastRunTime() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const controllerSheet = ss.getSheetByName(CONFIG.CONTROLLER_SHEET_NAME);
  
  if (!controllerSheet) return;
  
  const timestamp = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss');
  const cell = controllerSheet.getRange('K1');
  
  cell.setValue(`⏰ Last Run: ${timestamp}`)
      .setBackground('#4285f4')
      .setFontColor('#ffffff')
      .setFontWeight('bold')
      .setHorizontalAlignment('center');
}