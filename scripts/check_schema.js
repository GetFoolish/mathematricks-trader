db = db.getSiblingDB('mathematricks_trading');
print('=== SIGNAL_STORE SCHEMA CHECK ===');
var signal = db.signal_store.findOne({signal_id: 'sig_1770737879_8923_737879_1770737879'});
if (signal && signal.legs && signal.legs.length > 0) {
  var leg = signal.legs[0];
  print('\nLeg 0 fields:');
  print('  cerebro:', leg.cerebro ? 'EXISTS ✅' : 'MISSING ❌');
  print('  decision:', leg.decision ? 'EXISTS (OLD SCHEMA) ⚠️' : 'NOT FOUND ✅');
  print('  execution:', leg.execution ? 'EXISTS' : 'NOT FOUND');
  
  if (leg.cerebro) {
    print('\nCerebro field contents:');
    print('  status:', leg.cerebro.status);
    print('  reason:', leg.cerebro.reason);
    print('  created_orders:', leg.cerebro.created_orders ? 'EXISTS ✅' : 'MISSING ❌');
    print('  legs (OLD):', leg.cerebro.legs ? 'EXISTS (OLD SCHEMA) ⚠️' : 'NOT FOUND ✅');
    
    if (leg.cerebro.created_orders && leg.cerebro.created_orders.length > 0) {
      print('\nCreated order 0:');
      var order = leg.cerebro.created_orders[0];
      print('  instrument:', order.instrument);
      print('  quantity:', order.quantity);
      print('  broker:', order.broker || 'MISSING ❌');
    }
  }
  
  if (leg.execution && leg.execution.orders && leg.execution.orders.length > 0) {
    print('\nExecution order 0:');
    var execOrder = leg.execution.orders[0];
    print('  account_id:', execOrder.account_id);
    print('  broker:', execOrder.broker ? execOrder.broker + ' ✅' : 'MISSING ❌');
    print('  quantity_filled:', execOrder.quantity_filled);
  }
} else {
  print('Signal not found or no legs');
}
