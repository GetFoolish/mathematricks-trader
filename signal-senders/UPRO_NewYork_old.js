/****************************
 *   INSTALLABLE ON-EDIT TRIGGER
 ****************************/
function onEditTrigger(e) {
  if (!e) return;
  const sheet = e.source.getActiveSheet();
  if (!sheet) return;

  if (sheet.getName() !== "Signals_Testing") return;

  const range = e.range;

  // Only trigger for Column F edits
  if (range.getColumn() === 6) {
    const value = String(range.getValue()).trim().toLowerCase();

    if (value === "send") {
      Logger.log(`Send detected in row ${range.getRow()}`);

      // Send the row if complete, otherwise fallback to latest complete
      sendRowOrLatest(sheet, range.getRow());

      // Change "send" → "SENT"
      range.setValue("SENT");
    }
  }
}

/****************************
 *   SEND ROW OR LATEST COMPLETE
 ****************************/
function sendRowOrLatest(sheet, row) {
  // Read the row's data
  let date = sheet.getRange(row, 2).getValue();         // Column B
  let signalStrength = sheet.getRange(row, 3).getValue(); // Column C
  let buySellSignal = sheet.getRange(row, 4).getValue();  // Column D
  let orderType = sheet.getRange(row, 5).getValue();      // Column E

  // If any of the fields are missing, use the latest complete row
  if (!date || !signalStrength || !buySellSignal || !orderType) {
    const lastRow = sheet.getLastRow();
    Logger.log(`Incomplete data in row ${row}, using latest row ${lastRow} instead.`);

    date = sheet.getRange(lastRow, 2).getValue();
    signalStrength = sheet.getRange(lastRow, 3).getValue();
    buySellSignal = sheet.getRange(lastRow, 4).getValue();
    orderType = sheet.getRange(lastRow, 5).getValue();
  }

  // Format the date
  const formattedDate = Utilities.formatDate(new Date(date), "America/New_York", "MM/dd/yyyy");

  // Generate signalID
  const signalID = "signal_" + Date.now();

  // Prepare payload
  const payload = {
    strategy_name: "UPRO",
    signal_sent_EPOCH: Math.floor(Date.now() / 1000),
    signalID: signalID,
    passphrase: "test_password_123",
    signal: {
      date: formattedDate,
      signalStrength: signalStrength,
      buySellSignal: buySellSignal,
      orderType: orderType
    }
  };

  Logger.log("Payload to send:\n" + JSON.stringify(payload, null, 2));

  // Send the payload
  try {
    const url = "https://staging.mathematricks.fund/api/signals";
    const response = UrlFetchApp.fetch(url, {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });

    const httpCode = response.getResponseCode();
    const responseText = response.getContentText();

    Logger.log("HTTP Code: " + httpCode);
    Logger.log("Response: " + responseText);

    // Log to SignalHistory
    logSignalHistory({
      timestamp: new Date(),
      date: formattedDate,
      signalStrength: signalStrength,
      buySellSignal: buySellSignal,
      orderType: orderType,
      signalID: signalID,
      httpCode: httpCode,
      response: responseText
    });
  } catch (err) {
    Logger.log("Error sending signal: " + err.toString());
  }
}

/****************************
 *   LOG TO SIGNAL HISTORY
 ****************************/
function logSignalHistory(entry) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName("SignalHistory");

  // Create sheet if missing
  if (!sheet) {
    sheet = ss.insertSheet("SignalHistory");
    sheet.appendRow([
      "Timestamp",
      "Date",
      "Signal Strength (%)",
      "Buy/Sell Signal",
      "Order Type",
      "SignalID",
      "HTTP Code",
      "Response"
    ]);
  }

  sheet.appendRow([
    entry.timestamp,
    entry.date,
    entry.signalStrength,
    entry.buySellSignal,
    entry.orderType,
    entry.signalID,
    entry.httpCode,
    entry.response
  ]);
}
