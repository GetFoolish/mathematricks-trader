/**
 * Sends a signal with a specified strategy, symbol, price, and action
 * to the API endpoint via an HTTP POST request.
 */
function sendSignal(strategyName, symbol, price, action) {
  const url = 'https://mathematricks.fund/api/signals';
  // Retrieve the passphrase securely from Script Properties.
  const properties = PropertiesService.getScriptProperties();
  const api_passphrase = properties.getProperty('passphrase');

  // Best Practice: Check if the passphrase was found before proceeding.
  if (!api_passphrase) {
    const errorMessage = 'ERROR: API_PASSPHRASE is not set in Script Properties.';
    Logger.log(errorMessage);
    // You could also throw an error to halt execution completely if you prefer.
    // throw new Error(errorMessage); 
    return; // Stop the function.
  }

  const postData = {
    "strategy_name": strategyName,
    "signal_sent_EPOCH": Math.floor(new Date().getTime() / 1000),
    "signalID": "signal_" + new Date().getTime(),
    "passphrase": api_passphrase, // For better security, consider using Script Properties.
    "signal": {
      "ticker": symbol,
      "action": action,
      "price": price
    }
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
    return response;
  } catch (error) {
    Logger.log(`Error in sendSignal for ${symbol}: ${error.toString()}`);
    throw error;
  }
}

/**
 * An INSTALLABLE trigger that calls the sendSignal function
 * when a cell is edited. Renamed from onEdit to allow for proper authorization.
 *
 * @param {Object} e The event parameter provided by the trigger.
 */
function handleEdit(e) { // <--- RENAMED FROM onEdit
  if (!e) {
    Logger.log('The handleEdit function was run manually from the editor.');
    return;
  }

  if (e.range.getA1Notation() === 'B1' && e.value == '1') {
    try {
      sendSignal('LeslieTestStrategy', 'GOOG', 150.25, 'BUY');
      e.range.clearContent();
    } catch (error) {
      Logger.log('Failed to send signal from handleEdit trigger: ' + error.toString());
    }
  }
}