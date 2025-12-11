/**
 * ==================================================================
 * CONFIGURATION
 * ==================================================================
 */
const CONFIG = {
  STRATEGY_NAME: 'UPRO_NewYork',
  CONTROLLER_SHEET_NAME: 'Signals_Testing',
  DATA_START_ROW: 7,  // Data starts at row 7 (after header + description)
  CONTROLLER_COLUMN: {
    PRICE: 1,             // Column A - Price (fetched from Yahoo Finance)
    DATE: 2,              // Column B - Date
    SIGNAL_STRENGTH: 3,   // Column C - Signal Strength (%)
    BUY_SELL_SIGNAL: 4,   // Column D - Buy/Sell Signal
    ORDER_TYPE: 5,        // Column E - Order Type
    STATUS: 6             // Column F - Status (to mark "Sent")
  },
  TICKER_CELL: 'C3',  // Primary Ticker location (UPRO)
  // Timer cells
  LAST_RUN_CELL: 'H1',
  LAST_ONCHANGE_CELL: 'H2',
  COUNTDOWN_CELL: 'H3',
  WAIT_MINUTES: 1,  // Set to 1 minute for testing (change to 5 for production)
  ACCOUNT_EQUITY: 1,  // Fixed value for this strategy (fractional % as decimal)
  API_URL: 'https://staging.mathematricks.fund/api/v1/signals',  // Signal endpoint
  HISTORY_SHEET_NAME: 'SignalHistory',
  HISTORY_COLUMN: {
    TIMESTAMP: 1,
    SIGNAL_ID: 2,
    STRATEGY: 3,
    TICKER: 4,
    DATE: 5,
    SIGNAL_STRENGTH: 6,
    PRICE: 7,
    BUY_SELL_SIGNAL: 8,
    ORDER_TYPE: 9,
    STATUS: 10,
    ACK_TIMESTAMP: 11,
    RESPONSE_CODE: 12,
    ACK_MESSAGE: 13
  }
};

/**
 * ==================================================================
 * MAIN CONTROLLER - Processes the last entry signal
 * ==================================================================
 */
function processLastSignal() {
  Logger.log('=== processLastSignal START ===');
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const controllerSheet = ss.getSheetByName(CONFIG.CONTROLLER_SHEET_NAME);

  if (!controllerSheet) {
    Logger.log(`ERROR: The "${CONFIG.CONTROLLER_SHEET_NAME}" sheet was not found.`);
    SpreadsheetApp.getUi().alert(`Error: The "${CONFIG.CONTROLLER_SHEET_NAME}" sheet was not found. Please create it.`);
    return;
  }

  // Get the last row with data
  const lastRow = controllerSheet.getLastRow();
  Logger.log(`Sheet last row: ${lastRow}, DATA_START_ROW: ${CONFIG.DATA_START_ROW}`);

  if (lastRow < CONFIG.DATA_START_ROW) {
    Logger.log('No data rows to process');
    return;
  }

  // Read all data rows (starting from column B to column G to include all data + status)
  const dataRange = controllerSheet.getRange(CONFIG.DATA_START_ROW, 1, lastRow - CONFIG.DATA_START_ROW + 1, 7);
  const values = dataRange.getValues();
  Logger.log(`Read ${values.length} rows of data`);

  // Find the LAST ENTRY (last row with actual data, working backwards)
  let lastEntryRow = null;
  let lastEntryIndex = -1;

  for (let i = values.length - 1; i >= 0; i--) {
    const rowData = values[i];
    const date = rowData[CONFIG.CONTROLLER_COLUMN.DATE - 1];
    const orderType = rowData[CONFIG.CONTROLLER_COLUMN.ORDER_TYPE - 1];
    const signalStrength = rowData[CONFIG.CONTROLLER_COLUMN.SIGNAL_STRENGTH - 1];

    Logger.log(`Checking row ${i + CONFIG.DATA_START_ROW}: date=${date}, orderType=${orderType}, signalStrength=${signalStrength}`);

    // Check if this row has actual data (not empty)
    if (date && orderType && signalStrength !== '') {
      lastEntryRow = rowData;
      lastEntryIndex = i + CONFIG.DATA_START_ROW; // Convert to actual sheet row number
      Logger.log(`Found last entry at row ${lastEntryIndex}`);
      break;
    }
  }

  if (!lastEntryRow) {
    Logger.log('No data entries found in the sheet');
    updateLastRunTime();
    return;
  }

  // Check if we've already sent a signal for this DATE
  const lastEntryDate = lastEntryRow[CONFIG.CONTROLLER_COLUMN.DATE - 1];
  const formattedDate = Utilities.formatDate(new Date(lastEntryDate), Session.getScriptTimeZone(), 'MM/dd/yyyy');
  const currentSignalStrength = parseFloat(lastEntryRow[CONFIG.CONTROLLER_COLUMN.SIGNAL_STRENGTH - 1]) || 0;

  Logger.log(`Last entry date: ${formattedDate}, Signal Strength: ${currentSignalStrength}%`);

  // Check if signal already sent for this date
  const previousSignal = getLastSignalForDate(formattedDate);

  if (previousSignal) {
    // Signal was sent before for this date - check if % changed
    const previousSignalStrength = parseFloat(previousSignal.signalStrength) || 0;

    Logger.log(`Comparing signal strengths: Previous=${previousSignalStrength}, Current=${currentSignalStrength}`);

    // Use small epsilon for floating point comparison
    const epsilon = 0.0001;
    const strengthDifference = Math.abs(currentSignalStrength - previousSignalStrength);

    if (strengthDifference < epsilon) {
      Logger.log(`Signal for date ${formattedDate} already sent with same % (${currentSignalStrength}%) - skipping`);
      updateLastRunTime();
      return;
    } else {
      Logger.log(`Signal for date ${formattedDate} found but % changed: ${previousSignalStrength}% → ${currentSignalStrength}% (diff: ${strengthDifference}) - sending updated signal`);
    }
  } else {
    Logger.log(`No previous signal for date ${formattedDate} - sending new signal`);
  }

  Logger.log(`Processing last entry at row ${lastEntryIndex} for date ${formattedDate}`);

  // Update the last row's price before sending signal
  updateLastRowPrice();

  // Re-read the row data to get the updated price
  const updatedDataRange = controllerSheet.getRange(lastEntryIndex, 1, 1, 7);
  const updatedRowData = updatedDataRange.getValues()[0];

  processSignal(updatedRowData, lastEntryIndex, controllerSheet);

  // Update Last Run timestamp
  updateLastRunTime();
  Logger.log('=== processLastSignal END ===');
}

/**
 * ==================================================================
 * PROCESS SIGNAL - Handles signal logic for the last unsent row
 * ==================================================================
 */
function processSignal(rowData, rowIndex, controllerSheet) {
  // Extract data from row using CONFIG
  const price = parseFloat(rowData[CONFIG.CONTROLLER_COLUMN.PRICE - 1]) || 0;
  const date = rowData[CONFIG.CONTROLLER_COLUMN.DATE - 1];
  const signalStrength = parseFloat(rowData[CONFIG.CONTROLLER_COLUMN.SIGNAL_STRENGTH - 1]) || 0;
  const buySellSignal = rowData[CONFIG.CONTROLLER_COLUMN.BUY_SELL_SIGNAL - 1];
  const orderType = String(rowData[CONFIG.CONTROLLER_COLUMN.ORDER_TYPE - 1]).trim();

  // Safety Check 1: Is orderType valid?
  if (!orderType || orderType === 'No Action' || orderType === '') {
    Logger.log(`Row ${rowIndex}: Skipping - Order Type is "${orderType}"`);
    return;
  }

  // Safety Check 2: Is signalStrength valid?
  if (signalStrength === 0 || isNaN(signalStrength)) {
    Logger.log(`Row ${rowIndex}: Skipping - Signal Strength is ${signalStrength}`);
    return;
  }

  // Safety Check 3: Ensure quantity never exceeds account_equity (protection)
  let finalQuantity = signalStrength;
  if (signalStrength > CONFIG.ACCOUNT_EQUITY) {
    Logger.log(`⚠️ Row ${rowIndex}: WARNING - Quantity ${signalStrength} exceeds account_equity ${CONFIG.ACCOUNT_EQUITY}. Capping to ${CONFIG.ACCOUNT_EQUITY}`);
    finalQuantity = CONFIG.ACCOUNT_EQUITY;
  }

  // Get ticker from B3
  const ticker = controllerSheet.getRange(CONFIG.TICKER_CELL).getValue();
  if (!ticker) {
    Logger.log(`ERROR: Ticker not found in cell ${CONFIG.TICKER_CELL}`);
    return;
  }

  // Format the date
  const formattedDate = Utilities.formatDate(new Date(date), Session.getScriptTimeZone(), 'MM/dd/yyyy');

  // Generate signalID
  const signalID = "signal_" + new Date().getTime();

  // Send the signal
  const result = sendSignal(
    CONFIG.STRATEGY_NAME,
    ticker,
    formattedDate,
    finalQuantity,
    orderType,
    signalID,
    CONFIG.ACCOUNT_EQUITY,
    price
  );

  // Log to SignalHistory
  logSignalToHistory(
    signalID,
    CONFIG.STRATEGY_NAME,
    ticker,
    formattedDate,
    finalQuantity,
    price,
    buySellSignal,
    orderType,
    result
  );

  // Update controller sheet based on result
  if (result.success) {
    const timestamp = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'M/d/yyyy h:mm:ss a');
    const statusMessage = `SENT: ${finalQuantity}% @ ${timestamp}`;
    controllerSheet.getRange(rowIndex, CONFIG.CONTROLLER_COLUMN.STATUS).setValue(statusMessage);
    Logger.log(`Row ${rowIndex}: Signal sent successfully - ${orderType} ${finalQuantity}%`);
  } else {
    Logger.log(`Row ${rowIndex}: ERROR - ${result.error}`);
  }
}

/**
 * ==================================================================
 * SEND SIGNAL - Sends signal to API endpoint
 * ==================================================================
 */
function sendSignal(strategyName, ticker, signalDate, signalStrength, orderType, signalID, accountEquity, price) {
  const url = CONFIG.API_URL;

  // Retrieve the passphrase securely from Script Properties
  const properties = PropertiesService.getScriptProperties();
  const api_passphrase = properties.getProperty('passphrase');

  if (!api_passphrase) {
    throw new Error('ERROR: passphrase is not set in Script Properties.');
  }

  // Determine direction based on action
  const direction = orderType === 'BUY' ? 'LONG' : 'SHORT';

  // Build signal leg object
  const signalLeg = {
    "instrument": ticker,
    "instrument_type": "ETF",
    "action": orderType,
    "direction": direction,
    "quantity": signalStrength,
    "order_type": "MARKET",
    "price": price || 0,  // Use fetched price or 0 if not available
    "environment": "staging"
  };

  const postData = {
    "strategy_name": strategyName,
    "signal_sent_EPOCH": Math.floor(new Date().getTime() / 1000),
    "signalID": signalID,
    "passphrase": api_passphrase,
    "account_equity": accountEquity,
    "signal_legs": [signalLeg]
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
 * PRICE FETCHING FUNCTIONS
 * ==================================================================
 */

/**
 * Fetches historical price for UPRO from Yahoo Finance for a specific date
 * Returns the closing price or null if not available
 */
function fetchPriceForDate(ticker, date) {
  try {
    const dateObj = new Date(date);
    const today = new Date();

    // Reset time portion for comparison
    today.setHours(0, 0, 0, 0);
    dateObj.setHours(0, 0, 0, 0);

    // Format date as YYYY-MM-DD for Yahoo Finance
    const formattedDate = Utilities.formatDate(dateObj, Session.getScriptTimeZone(), 'yyyy-MM-dd');
    const todayFormatted = Utilities.formatDate(today, Session.getScriptTimeZone(), 'yyyy-MM-dd');

    Logger.log(`Fetching price for date: ${formattedDate}, Today: ${todayFormatted}, Date obj: ${dateObj.toISOString()}`);

    // Skip future dates (more than 1 day in the future to account for timezone issues)
    const oneDayFromNow = new Date(today);
    oneDayFromNow.setDate(oneDayFromNow.getDate() + 1);

    if (dateObj > oneDayFromNow) {
      Logger.log(`⚠️ Skipping future date: ${formattedDate} (more than 1 day in future)`);
      return null;
    }

    if (formattedDate === todayFormatted || dateObj.getTime() === today.getTime()) {
      // Get current/latest price from Yahoo Finance
      return fetchYahooFinancePrice(ticker);
    } else {
      // Fetch historical price from Yahoo Finance
      return fetchYahooFinancePrice(ticker, formattedDate);
    }
  } catch (error) {
    Logger.log(`Error fetching price for ${ticker} on ${date}: ${error}`);
    return null;
  }
}

/**
 * Fetches price from Yahoo Finance API
 */
/**
 * Fetches price from Yahoo Finance API (Updated to use v8 Chart API for both history and current)
 */
function fetchYahooFinancePrice(ticker, date) {
  try {
    // 1. Setup the URL and Options
    // We use the v8 Chart API for both historical and current because the v7/CSV endpoint is blocked.
    let url;
    
    // Yahoo often blocks requests without a User-Agent, so we mimic a browser.
    const params = {
      'muteHttpExceptions': true,
      'headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
      }
    };

    if (date) {
      // --- HISTORICAL PRICE ---
      const dateObj = new Date(date);
      // Create a 48-hour window around the date to ensure we catch the trading session
      // (Timezones can sometimes shift the requested window off the trading day)
      const timestamp1 = Math.floor(dateObj.getTime() / 1000); 
      const timestamp2 = timestamp1 + 86400 + 40000; // +1 day and a bit buffer

      url = `https://query1.finance.yahoo.com/v8/finance/chart/${ticker}?period1=${timestamp1}&period2=${timestamp2}&interval=1d`;
    } else {
      // --- CURRENT PRICE ---
      url = `https://query1.finance.yahoo.com/v8/finance/chart/${ticker}?interval=1d&range=1d`;
    }

    // 2. Fetch Data
    const response = UrlFetchApp.fetch(url, params);
    const responseCode = response.getResponseCode();
    const contentText = response.getContentText();

    if (responseCode !== 200) {
      Logger.log(`Yahoo API Error (${responseCode}) for ${ticker}: ${contentText.substring(0, 200)}`);
      return null;
    }

    // 3. Parse JSON
    const json = JSON.parse(contentText);

    if (json.chart && json.chart.result && json.chart.result.length > 0) {
      const result = json.chart.result[0];
      
      // Check for quote data
      if (result.indicators && result.indicators.quote && result.indicators.quote[0]) {
        const quotes = result.indicators.quote[0];
        
        // If we have close prices
        if (quotes.close && quotes.close.length > 0) {
          // Filter out nulls (which happen on non-trading days/holidays inside the range)
          const validCloses = quotes.close.filter(price => price !== null && !isNaN(price));
          
          if (validCloses.length > 0) {
            // Return the value (for history, we usually want the specific day found)
            // Since we requested a small window, the first valid close is usually the one we want.
            const price = validCloses[0]; 
            // Round to 2 decimals
            const roundedPrice = Math.round(price * 100) / 100;
            
            Logger.log(`Fetched price for ${ticker}: $${roundedPrice}`);
            return roundedPrice;
          }
        }
      }
      
      // Fallback: checks for meta price (often used for current price)
      if (result.meta && result.meta.regularMarketPrice) {
         return result.meta.regularMarketPrice;
      }
    }

    Logger.log(`No valid price data found in JSON response for ${ticker}`);
    return null;

  } catch (error) {
    Logger.log(`Error fetching Yahoo Finance price: ${error}`);
    return null;
  }
}

/**
 * Updates prices in column A for all rows that have dates in column B
 * Always updates all rows with dates (not just empty ones)
 */
function updateAllPrices() {
  Logger.log('=== updateAllPrices START ===');
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const controllerSheet = ss.getSheetByName(CONFIG.CONTROLLER_SHEET_NAME);

  if (!controllerSheet) {
    Logger.log(`ERROR: Sheet "${CONFIG.CONTROLLER_SHEET_NAME}" not found`);
    return;
  }

  const ticker = controllerSheet.getRange(CONFIG.TICKER_CELL).getValue();
  if (!ticker) {
    Logger.log('ERROR: Ticker not found in cell ' + CONFIG.TICKER_CELL);
    return;
  }

  Logger.log(`Ticker: ${ticker}`);

  const lastRow = controllerSheet.getLastRow();
  Logger.log(`Last row in sheet: ${lastRow}, Data starts at: ${CONFIG.DATA_START_ROW}`);

  if (lastRow < CONFIG.DATA_START_ROW) {
    Logger.log('No data rows to update');
    return;
  }

  // Read all dates from column B
  const dateRange = controllerSheet.getRange(CONFIG.DATA_START_ROW, CONFIG.CONTROLLER_COLUMN.DATE, lastRow - CONFIG.DATA_START_ROW + 1, 1);
  const dates = dateRange.getValues();
  Logger.log(`Read ${dates.length} rows from column B (Date column)`);

  let updatedCount = 0;
  let skippedCount = 0;
  let errorCount = 0;

  for (let i = 0; i < dates.length; i++) {
    const date = dates[i][0];
    const rowIndex = CONFIG.DATA_START_ROW + i;

    if (date) {
      Logger.log(`Row ${rowIndex}: Raw date from sheet = ${date}, type = ${typeof date}, constructor = ${date.constructor.name}`);

      // Google Sheets returns a Date object - use it directly without re-parsing
      const dateObj = (date instanceof Date) ? date : new Date(date);
      const formattedDateStr = Utilities.formatDate(dateObj, Session.getScriptTimeZone(), 'yyyy-MM-dd');
      const displayDate = Utilities.formatDate(dateObj, Session.getScriptTimeZone(), 'MM/dd/yyyy');
      Logger.log(`Row ${rowIndex}: Parsed date = ${displayDate} (formatted: ${formattedDateStr})`);

      // There's a date in column B, fetch and update price in column A
      const price = fetchPriceForDate(ticker, date);

      if (price !== null) {
        controllerSheet.getRange(rowIndex, CONFIG.CONTROLLER_COLUMN.PRICE).setValue(price);
        updatedCount++;
        Logger.log(`✓ Row ${rowIndex}: Updated ${ticker} @ $${price} on ${formattedDateStr}`);
      } else {
        errorCount++;
        const today = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd');
        if (formattedDateStr > today) {
          Logger.log(`⚠️ Row ${rowIndex}: Skipped future date ${formattedDateStr}`);
        } else {
          Logger.log(`✗ Row ${rowIndex}: Could not fetch price for ${formattedDateStr}`);
        }
      }

      // Add delay to avoid rate limiting
      Utilities.sleep(500);
    } else {
      // No date in column B, clear column A if it has a value
      const currentPrice = controllerSheet.getRange(rowIndex, CONFIG.CONTROLLER_COLUMN.PRICE).getValue();
      if (currentPrice) {
        controllerSheet.getRange(rowIndex, CONFIG.CONTROLLER_COLUMN.PRICE).clearContent();
        Logger.log(`- Row ${rowIndex}: Cleared price (no date)`);
      } else {
        skippedCount++;
        Logger.log(`- Row ${rowIndex}: Skipped (no date, no price)`);
      }
    }
  }

  Logger.log(`=== updateAllPrices END ===`);
  Logger.log(`Summary: ${updatedCount} updated, ${errorCount} errors, ${skippedCount} skipped`);
}

/**
 * Updates only the last row's price (most recent date)
 * Called hourly and before sending signals
 */
function updateLastRowPrice() {
  Logger.log('=== updateLastRowPrice START ===');
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const controllerSheet = ss.getSheetByName(CONFIG.CONTROLLER_SHEET_NAME);

  if (!controllerSheet) {
    Logger.log(`ERROR: Sheet "${CONFIG.CONTROLLER_SHEET_NAME}" not found`);
    return;
  }

  const ticker = controllerSheet.getRange(CONFIG.TICKER_CELL).getValue();
  if (!ticker) {
    Logger.log('ERROR: Ticker not found in cell ' + CONFIG.TICKER_CELL);
    return;
  }

  const lastRow = controllerSheet.getLastRow();
  if (lastRow < CONFIG.DATA_START_ROW) {
    Logger.log('No data rows to update');
    return;
  }

  // Read dates from column B to find the last row with a date
  const dateRange = controllerSheet.getRange(CONFIG.DATA_START_ROW, CONFIG.CONTROLLER_COLUMN.DATE, lastRow - CONFIG.DATA_START_ROW + 1, 1);
  const dates = dateRange.getValues();

  // Find the last row with a date (working backwards)
  for (let i = dates.length - 1; i >= 0; i--) {
    const date = dates[i][0];

    if (date) {
      const rowIndex = CONFIG.DATA_START_ROW + i;
      Logger.log(`Updating price for last row with date: ${rowIndex} (${date})`);

      const price = fetchPriceForDate(ticker, date);

      if (price !== null) {
        controllerSheet.getRange(rowIndex, CONFIG.CONTROLLER_COLUMN.PRICE).setValue(price);
        Logger.log(`✓ Updated row ${rowIndex}: ${ticker} @ $${price}`);
      } else {
        Logger.log(`✗ Could not fetch price for row ${rowIndex} (${date})`);
      }

      break; // Only update the last row
    }
  }

  Logger.log('=== updateLastRowPrice END ===');
}

/**
 * ==================================================================
 * TRIGGER FUNCTIONS
 * ==================================================================
 */

/**
 * captureOnChange - Called by onChange trigger
 * Saves current timestamp only when changes happen in columns B-E, rows 7+
 */
function captureOnChange(e) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const controllerSheet = ss.getSheetByName(CONFIG.CONTROLLER_SHEET_NAME);

  if (!controllerSheet) return;

  // Only capture if change happened in the controller sheet
  if (e && e.source) {
    const activeSheet = e.source.getActiveSheet();
    if (!activeSheet || activeSheet.getName() !== CONFIG.CONTROLLER_SHEET_NAME) {
      Logger.log('Change detected in different sheet - ignoring');
      return;
    }

    // Check if change was in the signal data area (columns B-F, rows 7+)
    const range = e.range;
    if (range) {
      const row = range.getRow();
      const col = range.getColumn();

      // Only trigger for columns B(2) through F(6) and rows >= 7
      // This includes: Date, Signal Strength, Buy/Sell Signal, Order Type, Status
      if (row < CONFIG.DATA_START_ROW || col < 2 || col > 6) {
        Logger.log(`Change in row ${row}, col ${col} - outside signal data area, ignoring`);
        return;
      }
    }
  }

  // Save current timestamp
  const timestamp = new Date();
  controllerSheet.getRange(CONFIG.LAST_ONCHANGE_CELL).setValue(timestamp);

  Logger.log(`onChange captured at ${timestamp} for signal data change`);
}

/**
 * whenToTrigger - Called every 1 minute by time-based trigger
 * Checks if WAIT_MINUTES have passed since last onChange, and triggers processLastSignal if so
 */
function whenToTrigger() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const controllerSheet = ss.getSheetByName(CONFIG.CONTROLLER_SHEET_NAME);

  if (!controllerSheet) return;

  const lastOnChange = controllerSheet.getRange(CONFIG.LAST_ONCHANGE_CELL).getValue();
  const lastRun = controllerSheet.getRange(CONFIG.LAST_RUN_CELL).getValue();

  // If no onChange has been captured yet, clear countdown and exit
  if (!lastOnChange) {
    controllerSheet.getRange(CONFIG.COUNTDOWN_CELL).setValue('No changes detected');
    return;
  }

  const now = new Date();
  const lastOnChangeTime = new Date(lastOnChange);
  const lastRunTime = lastRun ? new Date(lastRun) : new Date(0);

  // Calculate minutes since last onChange
  const minutesSinceChange = (now - lastOnChangeTime) / 1000 / 60;
  const minutesRemaining = Math.max(0, CONFIG.WAIT_MINUTES - minutesSinceChange);

  // Update countdown display
  if (minutesRemaining > 0) {
    const roundedMinutes = Math.ceil(minutesRemaining);
    controllerSheet.getRange(CONFIG.COUNTDOWN_CELL).setValue(`Next run in: ${roundedMinutes} min`);
    Logger.log(`Countdown: ${roundedMinutes} min remaining`);
  } else {
    // Check if we've already run for this onChange
    if (lastOnChangeTime > lastRunTime) {
      // Time to trigger!
      controllerSheet.getRange(CONFIG.COUNTDOWN_CELL).setValue('Running now...');
      Logger.log('Triggering processLastSignal - 5 minutes elapsed since last change');

      try {
        processLastSignal();
      } catch (error) {
        Logger.log('Error in processLastSignal: ' + error.toString());
        controllerSheet.getRange(CONFIG.COUNTDOWN_CELL).setValue('Error occurred');
      }
    } else {
      // Already ran for this onChange
      controllerSheet.getRange(CONFIG.COUNTDOWN_CELL).setValue('Up to date');
    }
  }
}

/**
 * ==================================================================
 * SIGNAL HISTORY FUNCTIONS
 * ==================================================================
 */

/**
 * Gets the last signal sent for a specific date
 * Returns an object with signal details if found, or null if not found
 */
function getLastSignalForDate(signalDate) {
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

  // Get all data from history sheet (Date and Signal Strength columns)
  const dataRange = historySheet.getRange(2, 1, lastRow - 1, 12); // Get all columns
  const values = dataRange.getValues();

  // Search backwards (most recent first) for matching date
  for (let i = values.length - 1; i >= 0; i--) {
    const rowData = values[i];
    const historyDate = rowData[CONFIG.HISTORY_COLUMN.DATE - 1];

    if (historyDate === signalDate) {
      // Found a signal for this date - return its details
      Logger.log(`Found existing signal for date ${signalDate} in SignalHistory (row ${i + 2})`);
      return {
        timestamp: rowData[CONFIG.HISTORY_COLUMN.TIMESTAMP - 1],
        signalID: rowData[CONFIG.HISTORY_COLUMN.SIGNAL_ID - 1],
        signalStrength: rowData[CONFIG.HISTORY_COLUMN.SIGNAL_STRENGTH - 1],
        orderType: rowData[CONFIG.HISTORY_COLUMN.ORDER_TYPE - 1],
        status: rowData[CONFIG.HISTORY_COLUMN.STATUS - 1]
      };
    }
  }

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
    'Date',
    'Signal Strength',
    'Price',
    'Buy/Sell Signal',
    'Order Type',
    'Status',
    'Ack Timestamp',
    'Response Code',
    'Ack Message'
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
 */
function logSignalToHistory(signalID, strategyName, ticker, signalDate, signalStrength, price, buySellSignal, orderType, result) {
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
        'Date',
        'Signal Strength',
        'Price',
        'Buy/Sell Signal',
        'Order Type',
        'Status',
        'Ack Timestamp',
        'Response Code',
        'Ack Message'
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
    signalDate,            // E: Date
    signalStrength,        // F: Signal Strength
    price || 0,            // G: Price
    buySellSignal,         // H: Buy/Sell Signal
    orderType,             // I: Order Type
    status,                // J: Status
    timestamp,             // K: Ack Timestamp
    result.responseCode || '', // L: Response Code
    ackMessage             // M: Ack Message
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
 * TIMER TRIGGER SETUP
 * ==================================================================
 */

/**
 * Setup triggers for the script
 * Run this function once manually to install both triggers
 */
function setupTriggers() {
  const triggers = ScriptApp.getProjectTriggers();

  // Delete any existing triggers to avoid duplicates
  triggers.forEach(trigger => {
    const handlerFunction = trigger.getHandlerFunction();
    if (handlerFunction === 'whenToTrigger' || handlerFunction === 'captureOnChange' || handlerFunction === 'updateLastRowPrice') {
      ScriptApp.deleteTrigger(trigger);
    }
  });

  // Create onChange trigger
  ScriptApp.newTrigger('captureOnChange')
    .forSpreadsheet(SpreadsheetApp.getActive())
    .onChange()
    .create();

  // Create 1-minute timer trigger to check when to run processLastSignal
  ScriptApp.newTrigger('whenToTrigger')
    .timeBased()
    .everyMinutes(1)
    .create();

  // Create hourly timer trigger to update last row's price
  ScriptApp.newTrigger('updateLastRowPrice')
    .timeBased()
    .everyHours(1)
    .create();

  Logger.log('✅ Triggers installed successfully');
  Logger.log('  - onChange trigger: captureOnChange()');
  Logger.log('  - 1-minute timer: whenToTrigger()');
  Logger.log('  - Hourly timer: updateLastRowPrice()');

  // Initialize cells with labels
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const controllerSheet = ss.getSheetByName(CONFIG.CONTROLLER_SHEET_NAME);
  if (controllerSheet) {
    // Set labels in column G
    controllerSheet.getRange('G1').setValue('Last Run:');
    controllerSheet.getRange('G2').setValue('Last Change:');
    controllerSheet.getRange('G3').setValue('Status:');

    // Set column header labels in row 5
    controllerSheet.getRange('A5').setValue('Price');
    controllerSheet.getRange('F5').setValue('STATUS');

    // Initialize status cell
    controllerSheet.getRange(CONFIG.COUNTDOWN_CELL).setValue('Waiting for changes...');

    // Format labels (bold)
    controllerSheet.getRange('G1:G3').setFontWeight('bold');
    controllerSheet.getRange('A5:F5').setFontWeight('bold');
  }
}

/**
 * DEBUG FUNCTION - Run this manually to test signal sending
 */
function debugProcessSignal() {
  Logger.log('===== DEBUG MODE =====');
  processLastSignal();
  Logger.log('Check the execution log above for details');
}

/**
 * Updates H1 with the last run timestamp
 */
function updateLastRunTime() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const controllerSheet = ss.getSheetByName(CONFIG.CONTROLLER_SHEET_NAME);

  if (!controllerSheet) return;

  const timestamp = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'M/d/yyyy H:mm:ss');
  controllerSheet.getRange(CONFIG.LAST_RUN_CELL).setValue(timestamp);

  Logger.log(`Last Run updated: ${timestamp}`);
}
