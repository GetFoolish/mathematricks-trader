/**
 * ==================================================================
 * UPRO EVP STRATEGY SIGNAL SENDER
 * ==================================================================
 * 
 * Purpose: Monitors the "Daily Signals" sheet and sends trading signals
 *          when the portfolio allocation percentage changes.
 * 
 * Sheet Structure:
 *   Column A: Date (Date Signal issued)
 *   Column B: Signal Strength (%) - Target allocation
 *   Column C: Buy/Sell Signal - Change from yesterday
 *   Column D: Order Type - BUY/SELL/No Action
 * 
 * SignalHistory Sheet Structure:
 *   Column A: Timestamp (when signal was sent)
 *   Column B: Trade Date (from Daily Signals sheet)
 *   Column C: Signal ID (unique identifier)
 *   Column D: Ticker (UPRO)
 *   Column E: Action (BUY/SELL)
 *   Column F: % Change (from Column C of Daily Signals)
 *   Column G: Target % (from Column B of Daily Signals)
 *   Column H: Status (Pending/Acknowledged/Error)
 *   Column I: Ack Timestamp (when acknowledged)
 *   Column J: Ack Message (response from webhook)
 *   Column K: Response Code (HTTP status)
 *   Column L: Actual Position (from acknowledgement)
 *   Column M: Retry Attempts (how many tries)
 * 
 * Configuration (Script Properties):
 *   - passphrase: Your API passphrase
 *   - ticker: "UPRO" (can be overridden)
 *   - strategy_name: "UPRO_EVP_Strategy"
 * 
 * ==================================================================
 */

// Configuration Constants
const CONFIG = {
  SHEET_NAME: 'Daily Signals',
  HISTORY_SHEET_NAME: 'SignalHistory',
  API_URL: 'https://mathematricks.fund/api/signals',
  TICKER: 'UPRO',
  STRATEGY_NAME: 'UPRO_EVP_Strategy',
  DEBOUNCE_DELAY_MS: 2000, // 2 seconds
  MAX_RETRIES: 3,
  COLUMN: {
    DATE: 1,           // A
    TARGET_PCT: 2,     // B
    CHANGE_PCT: 3,     // C
    ACTION: 4          // D
  },
  HISTORY_COLUMN: {
    TIMESTAMP: 1,      // A
    TRADE_DATE: 2,     // B
    SIGNAL_ID: 3,      // C
    TICKER: 4,         // D
    ACTION: 5,         // E
    CHANGE_PCT: 6,     // F
    TARGET_PCT: 7,     // G
    STATUS: 8,         // H
    ACK_TIMESTAMP: 9,  // I
    ACK_MESSAGE: 10,   // J
    RESPONSE_CODE: 11, // K
    ACTUAL_POS: 12,    // L
    RETRY_ATTEMPTS: 13 // M
  }
};

/**
 * ==================================================================
 * TRIGGER FUNCTIONS
 * ==================================================================
 */

/**
 * onEdit trigger - Fires when any cell is edited
 * Implements debouncing to handle rapid edits
 */
function onEdit(e) {
  try {
    const sheet = e.source.getActiveSheet();
    const range = e.range;
    
    // Only proceed if it's the "Daily Signals" sheet and Column B (Target %)
    if (sheet.getName() !== CONFIG.SHEET_NAME || range.getColumn() !== CONFIG.COLUMN.TARGET_PCT) {
      return;
    }
    
    const editedRow = range.getRow();
    
    // Skip header row
    if (editedRow === 1) {
      return;
    }
    
    Logger.log(`=== onEdit triggered for row ${editedRow} ===`);
    
    // Debounce: Store the latest edited row
    const scriptProps = PropertiesService.getScriptProperties();
    scriptProps.setProperty('pending_edit_row', editedRow.toString());
    scriptProps.setProperty('pending_edit_timestamp', new Date().getTime().toString());
    
    Logger.log(`Stored pending edit for row ${editedRow}`);
    
    // Delete any existing debounce triggers
    deleteAllDebounceTriggers();
    
    // Create new trigger to run after debounce delay
    ScriptApp.newTrigger('processDebounced')
      .timeBased()
      .after(CONFIG.DEBOUNCE_DELAY_MS)
      .create();
    
    Logger.log(`Created debounce trigger (${CONFIG.DEBOUNCE_DELAY_MS}ms delay)`);
    
  } catch (error) {
    Logger.log(`ERROR in onEdit: ${error}`);
  }
}

/**
 * Processes the debounced edit after delay
 * This ensures we only process the FINAL value after rapid edits
 */
function processDebounced() {
  try {
    Logger.log('=== processDebounced started ===');
    
    const scriptProps = PropertiesService.getScriptProperties();
    const pendingRow = scriptProps.getProperty('pending_edit_row');
    
    if (!pendingRow) {
      Logger.log('No pending row found, exiting');
      deleteAllDebounceTriggers();
      return;
    }
    
    const row = parseInt(pendingRow);
    Logger.log(`Processing row ${row}`);
    
    // Clear the pending flag
    scriptProps.deleteProperty('pending_edit_row');
    scriptProps.deleteProperty('pending_edit_timestamp');
    
    // Process the signal
    processSignal(row);
    
    // Clean up triggers
    deleteAllDebounceTriggers();
    
    Logger.log('=== processDebounced completed ===');
    
  } catch (error) {
    Logger.log(`ERROR in processDebounced: ${error}`);
    deleteAllDebounceTriggers();
  }
}

/**
 * Deletes all debounce-related triggers to prevent duplicates
 */
function deleteAllDebounceTriggers() {
  const triggers = ScriptApp.getProjectTriggers();
  let deleteCount = 0;
  
  for (let trigger of triggers) {
    if (trigger.getHandlerFunction() === 'processDebounced') {
      ScriptApp.deleteTrigger(trigger);
      deleteCount++;
    }
  }
  
  if (deleteCount > 0) {
    Logger.log(`Deleted ${deleteCount} debounce trigger(s)`);
  }
}

/**
 * ==================================================================
 * SIGNAL PROCESSING
 * ==================================================================
 */

/**
 * Main signal processing function
 * Validates, generates, and sends the signal
 */
function processSignal(row) {
  try {
    Logger.log(`=== Processing signal for row ${row} ===`);
    
    // STEP 1: Check for pending signals (blocking)
    if (hasPendingSignal()) {
      Logger.log('❌ BLOCKED: Found pending signal - not sending new signal');
      SpreadsheetApp.getUi().alert(
        'Signal Not Sent',
        'There is a pending signal waiting for acknowledgement.\n\n' +
        'New signals will be blocked until the previous signal is acknowledged.\n\n' +
        'Check the SignalHistory sheet for pending signals.',
        SpreadsheetApp.getUi().ButtonSet.OK
      );
      return;
    }
    
    // STEP 2: Get spreadsheet and sheets
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getSheetByName(CONFIG.SHEET_NAME);
    
    if (!sheet) {
      throw new Error(`Sheet "${CONFIG.SHEET_NAME}" not found`);
    }
    
    // STEP 3: Read data from the row
    const dateValue = sheet.getRange(row, CONFIG.COLUMN.DATE).getValue();
    const targetPct = sheet.getRange(row, CONFIG.COLUMN.TARGET_PCT).getValue();
    const changePct = sheet.getRange(row, CONFIG.COLUMN.CHANGE_PCT).getValue();
    const action = sheet.getRange(row, CONFIG.COLUMN.ACTION).getValue();
    
    Logger.log(`Data: Date=${dateValue}, Target%=${targetPct}, Change%=${changePct}, Action=${action}`);
    
    // STEP 4: Validate the data
    if (!changePct || changePct === 0 || changePct === '0%' || changePct === '') {
      Logger.log('No change detected (changePct is 0 or empty), exiting');
      return;
    }
    
    if (!action || (action !== 'BUY' && action !== 'SELL')) {
      Logger.log('No valid action (BUY/SELL) found, exiting');
      return;
    }
    
    // STEP 5: Parse percentage values (remove % sign if present)
    const targetPctValue = parseFloat(String(targetPct).replace('%', ''));
    const changePctValue = parseFloat(String(changePct).replace('%', ''));
    
    if (isNaN(targetPctValue) || isNaN(changePctValue)) {
      Logger.log('Invalid percentage values, exiting');
      return;
    }
    
    // STEP 6: Format trade date
    let tradeDate;
    if (dateValue instanceof Date) {
      tradeDate = Utilities.formatDate(dateValue, Session.getScriptTimeZone(), 'yyyy-MM-dd');
    } else {
      tradeDate = String(dateValue);
    }
    
    Logger.log(`Parsed values: Target=${targetPctValue}%, Change=${changePctValue}%, Date=${tradeDate}`);
    
    // STEP 7: Generate unique signal ID
    const signalID = generateUniqueSignalID();
    Logger.log(`Generated Signal ID: ${signalID}`);
    
    // STEP 8: Get current price (for logging purposes, backend will use real-time)
    const currentTimestamp = Math.floor(new Date().getTime() / 1000);
    
    // STEP 9: Create signal payload
    const scriptProps = PropertiesService.getScriptProperties();
    const api_passphrase = scriptProps.getProperty('passphrase');
    
    if (!api_passphrase) {
      throw new Error('API passphrase not configured. Please set it in Script Properties.');
    }
    
    const signalPayload = {
      strategy_name: CONFIG.STRATEGY_NAME,
      signal_sent_EPOCH: currentTimestamp,
      signalID: signalID,
      passphrase: api_passphrase,
      signal: {
        ticker: CONFIG.TICKER,
        action: action,
        percentage_change: Math.abs(changePctValue),
        target_allocation: targetPctValue,
        trade_date: tradeDate,
        price: null // Backend will fetch current price
      }
    };
    
    Logger.log(`Signal payload created: ${JSON.stringify(signalPayload, null, 2)}`);
    
    // STEP 10: Log to SignalHistory (Status: Pending)
    const historyRow = logSignalToHistory(signalID, tradeDate, action, changePctValue, targetPctValue, 'Pending');
    Logger.log(`Logged to SignalHistory at row ${historyRow}`);
    
    // STEP 11: Send signal with retry logic
    const result = sendSignalWithRetry(signalPayload);
    
    // STEP 12: Update SignalHistory based on result
    updateSignalHistoryAfterSend(historyRow, result);
    
    if (result.success) {
      Logger.log('✅ Signal sent successfully!');
      SpreadsheetApp.getUi().alert(
        'Signal Sent',
        `Signal sent successfully!\n\n` +
        `Signal ID: ${signalID}\n` +
        `Action: ${action}\n` +
        `Change: ${changePctValue}%\n` +
        `Target: ${targetPctValue}%\n\n` +
        `Status: Pending acknowledgement`,
        SpreadsheetApp.getUi().ButtonSet.OK
      );
    } else {
      Logger.log(`❌ Signal send failed: ${result.error}`);
      SpreadsheetApp.getUi().alert(
        'Signal Send Failed',
        `Failed to send signal after ${result.attempts} attempts.\n\n` +
        `Error: ${result.error}\n\n` +
        `Check SignalHistory sheet for details.`,
        SpreadsheetApp.getUi().ButtonSet.OK
      );
    }
    
  } catch (error) {
    Logger.log(`ERROR in processSignal: ${error}`);
    SpreadsheetApp.getUi().alert(
      'Error',
      `An error occurred while processing the signal:\n\n${error}`,
      SpreadsheetApp.getUi().ButtonSet.OK
    );
  }
}

/**
 * Checks if there are any pending (unacknowledged) signals
 * Returns true if blocking is needed
 */
function hasPendingSignal() {
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let historySheet = ss.getSheetByName(CONFIG.HISTORY_SHEET_NAME);
    
    // Create SignalHistory sheet if it doesn't exist
    if (!historySheet) {
      historySheet = createSignalHistorySheet(ss);
      return false; // No history yet, so no pending signals
    }
    
    const data = historySheet.getDataRange().getValues();
    
    // Check if any signal has Status = "Pending"
    for (let i = 1; i < data.length; i++) { // Skip header
      const status = data[i][CONFIG.HISTORY_COLUMN.STATUS - 1];
      
      if (status === 'Pending') {
        const signalID = data[i][CONFIG.HISTORY_COLUMN.SIGNAL_ID - 1];
        const tradeDate = data[i][CONFIG.HISTORY_COLUMN.TRADE_DATE - 1];
        Logger.log(`Found pending signal: ID=${signalID}, Date=${tradeDate}`);
        return true;
      }
    }
    
    return false;
    
  } catch (error) {
    Logger.log(`ERROR in hasPendingSignal: ${error}`);
    return false; // On error, don't block
  }
}

/**
 * Generates a unique signal ID
 * Format: UPRO_EVP_<timestamp>_<random>_<counter>
 */
function generateUniqueSignalID() {
  const timestamp = new Date().getTime();
  const random = Math.floor(Math.random() * 10000);
  
  // Get and increment counter from script properties
  const scriptProps = PropertiesService.getScriptProperties();
  let counter = parseInt(scriptProps.getProperty('signal_counter') || '0');
  counter++;
  scriptProps.setProperty('signal_counter', counter.toString());
  
  // Format: UPRO_EVP_1730897654321_3847_0001
  const signalID = `UPRO_EVP_${timestamp}_${random}_${counter.toString().padStart(4, '0')}`;
  
  return signalID;
}

/**
 * ==================================================================
 * SIGNAL HISTORY MANAGEMENT
 * ==================================================================
 */

/**
 * Creates the SignalHistory sheet with proper headers
 */
function createSignalHistorySheet(ss) {
  Logger.log('Creating SignalHistory sheet...');
  
  const historySheet = ss.insertSheet(CONFIG.HISTORY_SHEET_NAME);
  
  // Set headers
  const headers = [
    'Timestamp',
    'Trade Date',
    'Signal ID',
    'Ticker',
    'Action',
    '% Change',
    'Target %',
    'Status',
    'Ack Timestamp',
    'Ack Message',
    'Response Code',
    'Actual Position',
    'Retry Attempts'
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
  
  Logger.log('SignalHistory sheet created successfully');
  
  return historySheet;
}

/**
 * Logs a signal to the SignalHistory sheet
 * Returns the row number where the signal was logged
 */
function logSignalToHistory(signalID, tradeDate, action, changePct, targetPct, status) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let historySheet = ss.getSheetByName(CONFIG.HISTORY_SHEET_NAME);
  
  if (!historySheet) {
    historySheet = createSignalHistorySheet(ss);
  }
  
  const timestamp = new Date();
  
  const rowData = [
    timestamp,           // A: Timestamp
    tradeDate,           // B: Trade Date
    signalID,            // C: Signal ID
    CONFIG.TICKER,       // D: Ticker
    action,              // E: Action
    changePct,           // F: % Change
    targetPct,           // G: Target %
    status,              // H: Status
    '',                  // I: Ack Timestamp
    '',                  // J: Ack Message
    '',                  // K: Response Code
    '',                  // L: Actual Position
    0                    // M: Retry Attempts
  ];
  
  historySheet.appendRow(rowData);
  
  const lastRow = historySheet.getLastRow();
  
  // Format timestamp column
  historySheet.getRange(lastRow, CONFIG.HISTORY_COLUMN.TIMESTAMP)
    .setNumberFormat('yyyy-mm-dd hh:mm:ss');
  
  // Color code status
  const statusCell = historySheet.getRange(lastRow, CONFIG.HISTORY_COLUMN.STATUS);
  if (status === 'Pending') {
    statusCell.setBackground('#fff3cd').setFontColor('#856404');
  } else if (status === 'Error') {
    statusCell.setBackground('#f8d7da').setFontColor('#721c24');
  }
  
  return lastRow;
}

/**
 * Updates SignalHistory after send attempt
 */
function updateSignalHistoryAfterSend(row, result) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const historySheet = ss.getSheetByName(CONFIG.HISTORY_SHEET_NAME);
  
  if (!historySheet) {
    Logger.log('ERROR: SignalHistory sheet not found for update');
    return;
  }
  
  // Update retry attempts
  historySheet.getRange(row, CONFIG.HISTORY_COLUMN.RETRY_ATTEMPTS).setValue(result.attempts);
  
  if (result.success) {
    // Update response code
    historySheet.getRange(row, CONFIG.HISTORY_COLUMN.RESPONSE_CODE).setValue(200);
    
    // Add response message
    if (result.response) {
      historySheet.getRange(row, CONFIG.HISTORY_COLUMN.ACK_MESSAGE)
        .setValue(JSON.stringify(result.response));
    }
    
    // Status remains "Pending" until acknowledgement received
    
  } else {
    // Mark as Error
    historySheet.getRange(row, CONFIG.HISTORY_COLUMN.STATUS).setValue('Error');
    
    // Update error message
    historySheet.getRange(row, CONFIG.HISTORY_COLUMN.ACK_MESSAGE).setValue(result.error);
    
    // Color code as error
    historySheet.getRange(row, CONFIG.HISTORY_COLUMN.STATUS)
      .setBackground('#f8d7da')
      .setFontColor('#721c24');
  }
}

/**
 * ==================================================================
 * SIGNAL SENDING WITH RETRY LOGIC
 * ==================================================================
 */

/**
 * Sends a signal with retry logic
 * Returns {success: boolean, response: object, error: string, attempts: number}
 */
function sendSignalWithRetry(signalPayload) {
  const maxRetries = CONFIG.MAX_RETRIES;
  let attempt = 0;
  let success = false;
  let lastError = null;
  let responseData = null;
  
  while (attempt < maxRetries && !success) {
    attempt++;
    
    try {
      Logger.log(`\n--- Sending signal (attempt ${attempt}/${maxRetries}) ---`);
      
      const options = {
        'method': 'post',
        'contentType': 'application/json',
        'muteHttpExceptions': true, // Don't throw on non-200 responses
        'payload': JSON.stringify(signalPayload)
      };
      
      const response = UrlFetchApp.fetch(CONFIG.API_URL, options);
      const responseCode = response.getResponseCode();
      const responseText = response.getContentText();
      
      Logger.log(`Response Code: ${responseCode}`);
      Logger.log(`Response Body: ${responseText}`);
      
      // Try to parse response as JSON
      let responseBody;
      try {
        responseBody = JSON.parse(responseText);
      } catch (e) {
        responseBody = {raw: responseText};
      }
      
      // Check for success
      if (responseCode === 200 && responseBody.success === true) {
        success = true;
        responseData = responseBody;
        Logger.log('✅ Signal sent successfully!');
        
      } else if (responseCode === 200) {
        // 200 but success !== true
        lastError = `Webhook returned success=false: ${JSON.stringify(responseBody)}`;
        Logger.log(`⚠️ Attempt ${attempt} failed: ${lastError}`);
        
      } else {
        // Non-200 response
        lastError = `HTTP ${responseCode}: ${JSON.stringify(responseBody)}`;
        Logger.log(`❌ Attempt ${attempt} failed: ${lastError}`);
      }
      
      // If not successful and we have more retries, wait before retrying
      if (!success && attempt < maxRetries) {
        const waitTime = Math.pow(2, attempt) * 1000; // Exponential backoff: 2s, 4s, 8s
        Logger.log(`Waiting ${waitTime}ms before retry...`);
        Utilities.sleep(waitTime);
      }
      
    } catch (error) {
      lastError = `Exception: ${error.toString()}`;
      Logger.log(`❌ Attempt ${attempt} exception: ${lastError}`);
      
      if (attempt < maxRetries) {
        const waitTime = Math.pow(2, attempt) * 1000;
        Logger.log(`Waiting ${waitTime}ms before retry...`);
        Utilities.sleep(waitTime);
      }
    }
  }
  
  // Return result
  if (success) {
    return {
      success: true,
      response: responseData,
      error: null,
      attempts: attempt
    };
  } else {
    return {
      success: false,
      response: null,
      error: lastError || 'Unknown error',
      attempts: attempt
    };
  }
}

/**
 * ==================================================================
 * ACKNOWLEDGEMENT RECEIVER
 * ==================================================================
 */

/**
 * doPost - Receives acknowledgements from the webhook
 * This is called when the trading system acknowledges a signal
 */
function doPost(e) {
  try {
    Logger.log('=== doPost received ===');
    
    // Parse the incoming data
    let data;
    try {
      data = JSON.parse(e.postData.contents);
    } catch (error) {
      Logger.log('ERROR parsing POST data: ' + error);
      return ContentService.createTextOutput(JSON.stringify({
        success: false,
        error: 'Invalid JSON'
      })).setMimeType(ContentService.MimeType.JSON);
    }
    
    Logger.log('Received data: ' + JSON.stringify(data, null, 2));
    
    // Extract acknowledgement fields
    const signalID = data.signalID || data.signal_id;
    const status = data.status;
    const actualPosition = data.actual_position || data.actualPosition;
    const message = data.message || '';
    
    if (!signalID) {
      Logger.log('ERROR: No signalID provided in acknowledgement');
      return ContentService.createTextOutput(JSON.stringify({
        success: false,
        error: 'Missing signalID'
      })).setMimeType(ContentService.MimeType.JSON);
    }
    
    Logger.log(`Processing acknowledgement for Signal ID: ${signalID}`);
    
    // Update SignalHistory
    const updated = updateSignalAcknowledgement(signalID, status, actualPosition, message);
    
    if (updated) {
      Logger.log('✅ SignalHistory updated successfully');
      return ContentService.createTextOutput(JSON.stringify({
        success: true,
        message: 'Acknowledgement received and recorded'
      })).setMimeType(ContentService.MimeType.JSON);
    } else {
      Logger.log('⚠️ Signal ID not found in history');
      return ContentService.createTextOutput(JSON.stringify({
        success: false,
        error: 'Signal ID not found'
      })).setMimeType(ContentService.MimeType.JSON);
    }
    
  } catch (error) {
    Logger.log('ERROR in doPost: ' + error);
    return ContentService.createTextOutput(JSON.stringify({
      success: false,
      error: error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * Updates SignalHistory with acknowledgement data
 * Returns true if signal was found and updated
 */
function updateSignalAcknowledgement(signalID, status, actualPosition, message) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const historySheet = ss.getSheetByName(CONFIG.HISTORY_SHEET_NAME);
  
  if (!historySheet) {
    Logger.log('ERROR: SignalHistory sheet not found');
    return false;
  }
  
  const data = historySheet.getDataRange().getValues();
  
  // Find the row with matching Signal ID
  for (let i = 1; i < data.length; i++) { // Skip header
    const rowSignalID = data[i][CONFIG.HISTORY_COLUMN.SIGNAL_ID - 1];
    
    if (rowSignalID === signalID) {
      const row = i + 1; // Convert to 1-based row number
      
      Logger.log(`Found signal at row ${row}, updating...`);
      
      // Update Status
      historySheet.getRange(row, CONFIG.HISTORY_COLUMN.STATUS).setValue('Acknowledged');
      
      // Update Ack Timestamp
      const ackTimestamp = new Date();
      historySheet.getRange(row, CONFIG.HISTORY_COLUMN.ACK_TIMESTAMP).setValue(ackTimestamp);
      historySheet.getRange(row, CONFIG.HISTORY_COLUMN.ACK_TIMESTAMP)
        .setNumberFormat('yyyy-mm-dd hh:mm:ss');
      
      // Update Ack Message
      historySheet.getRange(row, CONFIG.HISTORY_COLUMN.ACK_MESSAGE).setValue(message);
      
      // Update Actual Position if provided
      if (actualPosition !== null && actualPosition !== undefined) {
        historySheet.getRange(row, CONFIG.HISTORY_COLUMN.ACTUAL_POS).setValue(actualPosition);
      }
      
      // Color code as acknowledged (green)
      historySheet.getRange(row, CONFIG.HISTORY_COLUMN.STATUS)
        .setBackground('#d4edda')
        .setFontColor('#155724');
      
      Logger.log('SignalHistory updated successfully');
      
      return true;
    }
  }
  
  Logger.log('Signal ID not found in history');
  return false;
}

/**
 * ==================================================================
 * SETUP & UTILITY FUNCTIONS
 * ==================================================================
 */

/**
 * Manual function to set up the onEdit trigger
 * Run this once to install the automatic trigger
 */
function setupTriggers() {
  // Remove existing onEdit triggers to avoid duplicates
  const triggers = ScriptApp.getProjectTriggers();
  for (let trigger of triggers) {
    if (trigger.getHandlerFunction() === 'onEdit') {
      ScriptApp.deleteTrigger(trigger);
    }
  }
  
  // Create new onEdit trigger
  ScriptApp.newTrigger('onEdit')
    .forSpreadsheet(SpreadsheetApp.getActiveSpreadsheet())
    .onEdit()
    .create();
  
  Logger.log('✅ onEdit trigger installed successfully');
  SpreadsheetApp.getUi().alert(
    'Setup Complete',
    'The onEdit trigger has been installed.\n\n' +
    'The script will now automatically monitor Column B for changes.',
    SpreadsheetApp.getUi().ButtonSet.OK
  );
}

/**
 * Manual function to set up script properties
 * Run this to configure your API passphrase
 */
function setupScriptProperties() {
  const ui = SpreadsheetApp.getUi();
  
  // Prompt for passphrase
  const passphraseResponse = ui.prompt(
    'API Configuration',
    'Enter your API passphrase:',
    ui.ButtonSet.OK_CANCEL
  );
  
  if (passphraseResponse.getSelectedButton() === ui.Button.OK) {
    const passphrase = passphraseResponse.getResponseText();
    
    if (passphrase) {
      const scriptProps = PropertiesService.getScriptProperties();
      scriptProps.setProperty('passphrase', passphrase);
      
      ui.alert(
        'Configuration Saved',
        'API passphrase has been saved securely.',
        ui.ButtonSet.OK
      );
    } else {
      ui.alert('Error', 'Passphrase cannot be empty.', ui.ButtonSet.OK);
    }
  }
}

/**
 * Manual test function - sends a test signal
 * Run this to verify the setup
 */
function testSignalSend() {
  Logger.log('=== TEST SIGNAL SEND ===');
  
  const scriptProps = PropertiesService.getScriptProperties();
  const api_passphrase = scriptProps.getProperty('passphrase');
  
  if (!api_passphrase) {
    SpreadsheetApp.getUi().alert(
      'Configuration Error',
      'API passphrase not configured.\n\nPlease run setupScriptProperties() first.',
      SpreadsheetApp.getUi().ButtonSet.OK
    );
    return;
  }
  
  const testSignalID = generateUniqueSignalID();
  
  const testPayload = {
    strategy_name: CONFIG.STRATEGY_NAME,
    signal_sent_EPOCH: Math.floor(new Date().getTime() / 1000),
    signalID: testSignalID,
    passphrase: api_passphrase,
    signal: {
      ticker: CONFIG.TICKER,
      action: 'BUY',
      percentage_change: 25,
      target_allocation: 50,
      trade_date: new Date().toISOString().split('T')[0],
      price: null
    }
  };
  
  Logger.log('Test payload: ' + JSON.stringify(testPayload, null, 2));
  
  const result = sendSignalWithRetry(testPayload);
  
  if (result.success) {
    SpreadsheetApp.getUi().alert(
      'Test Successful',
      `Test signal sent successfully!\n\nSignal ID: ${testSignalID}\n\nAttempts: ${result.attempts}`,
      SpreadsheetApp.getUi().ButtonSet.OK
    );
  } else {
    SpreadsheetApp.getUi().alert(
      'Test Failed',
      `Test signal failed after ${result.attempts} attempts.\n\nError: ${result.error}`,
      SpreadsheetApp.getUi().ButtonSet.OK
    );
  }
}

/**
 * Manual function to view pending signals
 */
function viewPendingSignals() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const historySheet = ss.getSheetByName(CONFIG.HISTORY_SHEET_NAME);
  
  if (!historySheet) {
    SpreadsheetApp.getUi().alert(
      'No History',
      'SignalHistory sheet not found.',
      SpreadsheetApp.getUi().ButtonSet.OK
    );
    return;
  }
  
  const data = historySheet.getDataRange().getValues();
  const pendingSignals = [];
  
  for (let i = 1; i < data.length; i++) {
    const status = data[i][CONFIG.HISTORY_COLUMN.STATUS - 1];
    
    if (status === 'Pending') {
      pendingSignals.push({
        signalID: data[i][CONFIG.HISTORY_COLUMN.SIGNAL_ID - 1],
        tradeDate: data[i][CONFIG.HISTORY_COLUMN.TRADE_DATE - 1],
        action: data[i][CONFIG.HISTORY_COLUMN.ACTION - 1],
        timestamp: data[i][CONFIG.HISTORY_COLUMN.TIMESTAMP - 1]
      });
    }
  }
  
  if (pendingSignals.length === 0) {
    SpreadsheetApp.getUi().alert(
      'No Pending Signals',
      'All signals have been acknowledged.',
      SpreadsheetApp.getUi().ButtonSet.OK
    );
  } else {
    let message = `Found ${pendingSignals.length} pending signal(s):\n\n`;
    
    pendingSignals.forEach((signal, index) => {
      message += `${index + 1}. Signal ID: ${signal.signalID}\n`;
      message += `   Date: ${signal.tradeDate}\n`;
      message += `   Action: ${signal.action}\n`;
      message += `   Sent: ${signal.timestamp}\n\n`;
    });
    
    SpreadsheetApp.getUi().alert(
      'Pending Signals',
      message,
      SpreadsheetApp.getUi().ButtonSet.OK
    );
  }
}

/**
 * ==================================================================
 * DOCUMENTATION
 * ==================================================================
 * 
 * SETUP INSTRUCTIONS:
 * 
 * 1. Open your Google Sheet
 * 2. Go to Extensions > Apps Script
 * 3. Delete any existing code and paste this entire script
 * 4. Save the script (Ctrl+S or Cmd+S)
 * 5. Run setupScriptProperties() to configure your API passphrase
 * 6. Run setupTriggers() to install the onEdit trigger
 * 7. Authorize the script when prompted
 * 8. Run testSignalSend() to verify everything works
 * 
 * USAGE:
 * 
 * - Edit Column B (Signal Strength %) in the "Daily Signals" sheet
 * - The script will automatically detect changes after 2 seconds
 * - If Column C (Change %) is non-zero, a signal will be sent
 * - Check the "SignalHistory" sheet for signal status
 * - New signals are blocked until previous signals are acknowledged
 * 
 * MANUAL FUNCTIONS:
 * 
 * - setupScriptProperties(): Configure API passphrase
 * - setupTriggers(): Install/reinstall the onEdit trigger
 * - testSignalSend(): Send a test signal
 * - viewPendingSignals(): View all unacknowledged signals
 * 
 * TROUBLESHOOTING:
 * 
 * - Check the Execution log (Ctrl+Enter or Cmd+Enter)
 * - Verify script properties are set correctly
 * - Check SignalHistory sheet for error messages
 * - Ensure formulas in Columns C and D are working
 * 
 * ==================================================================
 */
