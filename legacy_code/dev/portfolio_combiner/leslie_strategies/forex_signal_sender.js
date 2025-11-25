/**
 * ==================================================================
 * CONTROLLER FUNCTION - This is the main function we will run.
 * FIX: Updated to handle vertical (column-based) trade data.
 * ==================================================================
 */
function processSignals() {
  Logger.log('=== PROCESS SIGNALS STARTED ===');
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  Logger.log('Spreadsheet name: ' + ss.getName());
  
  const controllerSheet = ss.getSheetByName('SignalController');
  
  if (!controllerSheet) {
    Logger.log('ERROR: The "SignalController" sheet was not found. Please create it.');
    Logger.log('Available sheets:');
    ss.getSheets().forEach(sheet => {
      Logger.log('- ' + sheet.getName());
    });
    SpreadsheetApp.getUi().alert('Error: The "SignalController" sheet was not found. Please create it.');
    return;
  }
  
  Logger.log('SignalController sheet found!');

  // --- Read all the data from the sheet ---
  Logger.log(`Sheet dimensions - Last Row: ${controllerSheet.getLastRow()}, Last Column: ${controllerSheet.getLastColumn()}`);
  
  const dataRange = controllerSheet.getRange(1, 1, controllerSheet.getLastRow(), controllerSheet.getLastColumn());
  const values = dataRange.getValues();
  Logger.log(`Data array dimensions: ${values.length} rows x ${values[0].length} columns`);
  
  // Define the COLUMN numbers for each data point based on your sheet layout:
  const COL_PAIR_ID = 1;            // Column A - Pair ID (E, F, G, etc.)
  const COL_IS_ON = 2;              // Column B - Is On? 
  const COL_SYMBOL = 3;             // Column C - Symbol
  const COL_MODEL_POS = 4;          // Column D - Model Position
  const COL_LAST_KNOWN_POS = 5;     // Column E - Last Known Model Position
  const COL_SIGNAL_STATUS = 6;      // Column F - Signal Status
  const COL_ACTION = 7;             // Column G - Generated Signal Action
  const COL_QTY = 8;                // Column H - Generated Signal Quantity
  const COL_ACTUAL_POS = 9;         // Column I - Actual Position
  const COL_LAST_UPDATE = 10;       // Column J - Last Update

  // --- NEW LOOP: Iterate across rows (starting from row 2, skipping header) ---
  Logger.log(`Starting loop from row 2 to ${values.length}`);
  
  for (let i = 1; i < values.length; i++) { // Start from row 2 (index 1)
    // i is the row index (0 = row 1, 1 = row 2, etc.)
    
    // Read the data for the current currency pair (i.e., the current row)
    let pairId = values[i][COL_PAIR_ID - 1];        // Column A
    let isOn = values[i][COL_IS_ON - 1];            // Column B
    let symbol = values[i][COL_SYMBOL - 1];         // Column C
    let modelPosition = values[i][COL_MODEL_POS - 1];     // Column D
    let lastModelPos = values[i][COL_LAST_KNOWN_POS - 1]; // Column E
    let signalStatus = values[i][COL_SIGNAL_STATUS - 1];  // Column F
    let actualPosition = values[i][COL_ACTUAL_POS - 1];   // Column I
    
    // Safety check for empty rows
    if (!symbol || symbol === '') {
      Logger.log(`Row ${i + 1}: Empty symbol, skipping...`);
      continue;
    }


    // --- Start of the Safety Checks ---
    // Ensure all position values are treated as numbers
    modelPosition = parseFloat(modelPosition) || 0;
    lastModelPos = parseFloat(lastModelPos) || 0;
    actualPosition = parseFloat(actualPosition) || 0;
    
    // Ensure isOn is a number for comparison
    const onFlag = parseFloat(isOn) || 0;
    
    // Log the current state before the checks
    Logger.log(`Processing Row ${i + 1} (${symbol}): IsOn: ${onFlag}, Model: ${modelPosition}, Last: ${lastModelPos}, Actual: ${actualPosition}, Status: ${signalStatus}`);

    // Safety Check 1: Is the system on?
    if (onFlag !== 1) continue;
    
    // Safety Check 2: Has a signal already been sent for this model position?
    if (signalStatus === 'Sent') {
      Logger.log(`SIGNAL CHECK: ${symbol} - Signal already sent (Status: ${signalStatus}), skipping...`);
      continue;
    }
    
    
    let signalNeeded = false;
    
    // TRIGGER 1: Model position has changed from the last time we sent it.
    if (modelPosition !== lastModelPos) {
      signalNeeded = true;
      Logger.log(`DIFFERENCE IDENTIFIED: ${symbol} - Model Position changed from ${lastModelPos} to ${modelPosition}`);
    }
    
    // TRIGGER 2: Mismatch between model and actual positions.
    if (!signalNeeded && modelPosition !== actualPosition) {
       signalNeeded = true;
       Logger.log(`DIFFERENCE IDENTIFIED: ${symbol} - Model Position (${modelPosition}) != Actual Position (${actualPosition})`);
    }
    
    if (signalNeeded) {
      const quantity = modelPosition - actualPosition;
      let action;
      
      if (quantity > 0) {
        action = 'BUY';
      } else if (quantity < 0) {
        action = 'SELL';
      } else {
        // If quantity is 0, positions are in sync. Reset the state.
        // Update Last Known Position (Column E)
        controllerSheet.getRange(i + 1, COL_LAST_KNOWN_POS).setValue(modelPosition); 
        // Reset Status (Column F)
        controllerSheet.getRange(i + 1, COL_SIGNAL_STATUS).setValue('Ready');
        continue;
      }
      
      const absoluteQuantity = Math.abs(quantity);

      // --- CRITICAL: Update sheet BEFORE sending signal ---
      controllerSheet.getRange(i + 1, COL_SIGNAL_STATUS).setValue('Sent');     // Column F
      controllerSheet.getRange(i + 1, COL_ACTION).setValue(action);           // Column G
      controllerSheet.getRange(i + 1, COL_QTY).setValue(absoluteQuantity);    // Column H
      
      Logger.log(`Signal needed for ${symbol}: ${action} ${absoluteQuantity}. Sending...`);

      // --- Send the signal via webhook ---
      try {
        const strategyName = "SignalControllerStrategy"; 
        const price = 0; 
        
        Logger.log(`SENDING SIGNAL: ${symbol} - ${action} ${absoluteQuantity} at price ${price}`);
        sendSignal(strategyName, symbol, price, action, absoluteQuantity);
        
        // On successful send, update the 'Last Known Model Position' (Column E)
        controllerSheet.getRange(i + 1, COL_LAST_KNOWN_POS).setValue(modelPosition);
        Logger.log(`SIGNAL SENT SUCCESSFULLY: ${symbol} - ${action} ${absoluteQuantity}`);
        
      } catch (error) {
        Logger.log(`SIGNAL SEND FAILED: ${symbol} - ${error.toString()}`);
        controllerSheet.getRange(i + 1, COL_SIGNAL_STATUS).setValue('Error'); // Mark row as having an error
      }
    } else {
      Logger.log(`NO SIGNAL NEEDED: ${symbol} - Positions are in sync (Model: ${modelPosition}, Actual: ${actualPosition})`);
    }
  }
  
  Logger.log('=== PROCESS SIGNALS COMPLETED ===');
}

/**
 * Sends a signal with a specified strategy, symbol, price, action, and quantity
 * to the API endpoint via an HTTP POST request.
 */
function sendSignal(strategyName, symbol, price, action, quantity = null) {
  const url = 'https://mathematricks.fund/api/signals';
  // Retrieve the passphrase securely from Script Properties.
  const properties = PropertiesService.getScriptProperties();
  const api_passphrase = properties.getProperty('passphrase');

  // Best Practice: Check if the passphrase was found before proceeding.
  if (!api_passphrase) {
    const errorMessage = 'ERROR: API_PASSPHRASE is not set in Script Properties.';
    Logger.log(errorMessage);
    throw new Error(errorMessage);
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
    "signalID": "signal_" + new Date().getTime(),
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
    Logger.log(`Signal sent for ${symbol}. Response code: ${response.getResponseCode()}`);
    
    if (response.getResponseCode() !== 200) {
      throw new Error(`HTTP ${response.getResponseCode()}: ${response.getContentText()}`);
    }
    
    return response;
  } catch (error) {
    Logger.log(`Error in sendSignal for ${symbol}: ${error.toString()}`);
    throw error;
  }
}

/**
 * onEdit trigger function - runs automatically when any cell is edited
 * This will trigger even for programmatic changes from other sheets/APIs
 */
function onEdit(e) {
  // Only run if we have event data (won't run if called manually)
  if (!e || !e.range) {
    Logger.log('onEdit called manually - no event data');
    return;
  }
  
  // Get the sheet name and range that was edited
  const sheetName = e.source.getActiveSheet().getName();
  const editedColumn = e.range.getColumn();
  const editedRow = e.range.getRow();
  
  Logger.log(`onEdit triggered: Sheet="${sheetName}", Row=${editedRow}, Column=${editedColumn}`);
  
  // Only process if the edit was on the SignalController sheet
  if (sheetName !== 'SignalController') {
    Logger.log('Edit was not on SignalController sheet, ignoring');
    return;
  }
  
  // Only process if the edit was in relevant columns and not the header row
  const relevantColumns = [2, 3, 4, 9]; // B=Is On, C=Symbol, D=Model Position, I=Actual Position
  if (editedRow === 1 || !relevantColumns.includes(editedColumn)) {
    Logger.log(`Edit in row ${editedRow}, column ${editedColumn} - not relevant for signal processing`);
    return;
  }
  
  Logger.log('Relevant edit detected - triggering processSignals()');
  
  try {
    processSignals();
  } catch (error) {
    Logger.log('Error in onEdit trigger: ' + error.toString());
  }
}

/**
 * Manual function to set up the onEdit trigger
 * Run this once to install the automatic trigger
 */
function setupTriggers() {
  // Delete existing triggers for this function
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(trigger => {
    if (trigger.getHandlerFunction() === 'onEdit') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
  
  // Create new onEdit trigger
  ScriptApp.newTrigger('onEdit')
    .onEdit()
    .create();
    
  Logger.log('onEdit trigger installed successfully');
}