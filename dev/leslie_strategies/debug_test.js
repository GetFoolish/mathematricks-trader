/**
 * Simple debug function to test basic functionality
 */
function debugTest() {
  Logger.log('=== DEBUG TEST STARTED ===');
  
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  Logger.log('Spreadsheet found: ' + ss.getName());
  
  const controllerSheet = ss.getSheetByName('SignalController');
  
  if (!controllerSheet) {
    Logger.log('ERROR: SignalController sheet not found');
    Logger.log('Available sheets:');
    ss.getSheets().forEach(sheet => {
      Logger.log('- ' + sheet.getName());
    });
    return;
  }
  
  Logger.log('SignalController sheet found');
  Logger.log('Last row: ' + controllerSheet.getLastRow());
  Logger.log('Last column: ' + controllerSheet.getLastColumn());
  
  // Check data in columns E, F, G (indices 4, 5, 6)
  for (let col = 5; col <= 7; col++) { // E=5, F=6, G=7
    Logger.log(`=== Column ${String.fromCharCode(64 + col)} ===`);
    for (let row = 1; row <= 9; row++) {
      const value = controllerSheet.getRange(row, col).getValue();
      Logger.log(`Row ${row}: "${value}"`);
    }
  }
  
  Logger.log('=== DEBUG TEST COMPLETED ===');
}