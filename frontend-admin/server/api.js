import express from 'express';
import cors from 'cors';
import { MongoClient, ObjectId } from 'mongodb';

const app = express();
const PORT = process.env.API_PORT || 8000;

// MongoDB connection
const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27018/?replicaSet=rs0';
let db;
let signalStoreCollection;
let tradingOrdersCollection;

// Connect to MongoDB
async function connectToMongo() {
  try {
    const client = new MongoClient(MONGODB_URI);
    await client.connect();
    db = client.db('mathematricks_trading');
    signalStoreCollection = db.collection('signal_store');
    tradingOrdersCollection = db.collection('trading_orders');
    console.log('[API] Connected to MongoDB (mathematricks_trading)');
  } catch (error) {
    console.error('[API] MongoDB connection error:', error);
    process.exit(1);
  }
}

// Middleware
app.use(cors());
app.use(express.json());

// Helper to serialize MongoDB documents
function serializeDocument(doc) {
  if (doc === null || doc === undefined) return doc;
  if (doc instanceof ObjectId) return doc.toString();
  if (doc instanceof Date) return doc.toISOString();
  if (Array.isArray(doc)) return doc.map(serializeDocument);
  if (typeof doc === 'object') {
    const serialized = {};
    for (const [key, value] of Object.entries(doc)) {
      serialized[key] = serializeDocument(value);
    }
    return serialized;
  }
  return doc;
}

// GET /api/v1/activity/signals
// Supports both v1 (signal_data, cerebro_decision) and v2 (raw, decision) schema
app.get('/api/v1/activity/signals', async (req, res) => {
  try {
    const limit = parseInt(req.query.limit) || 50;
    const environment = req.query.environment;

    const query = {};
    if (environment) {
      query.environment = environment;
    }

    const docs = await signalStoreCollection
      .find(query)
      .sort({ created_at: -1 })
      .limit(limit)
      .toArray();

    const signals = docs.map(doc => {
      // Support both v1 (signal_data) and v2 (raw) schema
      const raw = doc.raw || {};
      const signalData = doc.signal_data || {};

      // Get first leg from v2 raw.legs or v1 signal_data.signal
      let firstLeg = {};
      if (raw.legs && raw.legs.length > 0) {
        firstLeg = raw.legs[0];
      } else {
        let signalDetails = signalData.signal || {};
        if (Array.isArray(signalDetails) && signalDetails.length > 0) {
          firstLeg = signalDetails[0];
        } else {
          firstLeg = signalDetails;
        }
      }

      // Support both v1 (cerebro_decision) and v2 (decision) schema
      const decision = doc.decision || doc.cerebro_decision || null;
      let decisionStatus = null;
      if (decision) {
        decisionStatus = decision.status || decision.decision || 'PENDING';
      }

      // Get signal type from v2 raw or v1 signal_data
      let signalType = raw.signal_type || signalData.signal_type || 'UNKNOWN';
      if (signalType === 'UNKNOWN') {
        const action = (firstLeg.action || '').toUpperCase();
        if (['ENTRY', 'BUY'].includes(action)) signalType = 'ENTRY';
        else if (['EXIT', 'SELL', 'CLOSE'].includes(action)) signalType = 'EXIT';
      }

      // Calculate timestamps and lags
      const signalSentEpoch = raw.sent_epoch || signalData.signal_sent_EPOCH;
      let signalSentTimestamp = null;
      if (signalSentEpoch) {
        signalSentTimestamp = new Date(signalSentEpoch * 1000).toISOString();
      }

      let signalReceivedTimestamp = raw.received_at || doc.created_at;
      if (typeof signalReceivedTimestamp === 'string') {
        signalReceivedTimestamp = new Date(signalReceivedTimestamp);
      }

      let receiveLagSeconds = null;
      if (signalSentEpoch && signalReceivedTimestamp) {
        receiveLagSeconds = (signalReceivedTimestamp.getTime() / 1000) - signalSentEpoch;
      }

      // Execution timestamp - support v2 (execution.orders[]) and v1 (execution.filled_at)
      const execution = doc.execution;
      let executionCompletedTimestamp = null;
      let executionLagSeconds = null;

      if (execution) {
        // v2: check orders array
        if (execution.orders && execution.orders.length > 0) {
          const lastOrder = execution.orders[execution.orders.length - 1];
          if (lastOrder.filled_at) {
            executionCompletedTimestamp = new Date(lastOrder.filled_at);
          }
        }
        // v1: check filled_at directly
        else if (execution.filled_at) {
          executionCompletedTimestamp = new Date(execution.filled_at);
        }
      }
      // Fallback to decision timestamp
      if (!executionCompletedTimestamp && decision && decision.timestamp) {
        executionCompletedTimestamp = new Date(decision.timestamp);
      }

      if (executionCompletedTimestamp && signalSentEpoch) {
        executionLagSeconds = (executionCompletedTimestamp.getTime() / 1000) - signalSentEpoch;
      }

      // Get PnL from v2 position.pnl or v1 doc.pnl
      const position = doc.position || {};
      const pnl = position.pnl || doc.pnl || null;

      // Get final quantity from v2 decision.legs or v1 cerebro_decision.final_quantity
      let finalQuantity = firstLeg.quantity;
      if (decision) {
        if (decision.legs && decision.legs.length > 0) {
          finalQuantity = decision.legs[0].quantity;
        } else if (decision.final_quantity !== undefined) {
          finalQuantity = decision.final_quantity;
        }
      }

      return {
        signal_id: doc.signal_id,
        strategy_id: doc.strategy_id || signalData.strategy_name || 'Unknown',
        timestamp: serializeDocument(doc.created_at),
        created_at: serializeDocument(doc.created_at),
        instrument: firstLeg.instrument || firstLeg.ticker,
        action: firstLeg.action,
        direction: firstLeg.direction,
        price: firstLeg.price || firstLeg.entry_price,
        quantity: firstLeg.quantity,
        final_quantity: finalQuantity,
        environment: doc.environment || 'production',
        processed_by_cerebro: decision !== null,
        receive_lag_ms: doc.receive_lag_ms || 0,
        decision: serializeDocument(decision),
        decision_status: decisionStatus,
        signal_sent_timestamp: signalSentTimestamp,
        signal_received_timestamp: signalReceivedTimestamp ? signalReceivedTimestamp.toISOString() : null,
        execution_completed_timestamp: executionCompletedTimestamp ? executionCompletedTimestamp.toISOString() : null,
        receive_lag_seconds: receiveLagSeconds,
        execution_lag_seconds: executionLagSeconds,
        signal_type: signalType,
        execution: serializeDocument(execution),
        position: serializeDocument(position),
        pnl: serializeDocument(pnl)
      };
    });

    res.json({ status: 'success', count: signals.length, signals });
  } catch (error) {
    console.error('[API] Error fetching signals:', error);
    res.status(500).json({ detail: error.message });
  }
});

// GET /api/v1/activity/orders
// Fetches execution orders from signal_store.execution.orders[] (v2 schema)
app.get('/api/v1/activity/orders', async (req, res) => {
  try {
    const limit = parseInt(req.query.limit) || 50;
    const environment = req.query.environment;

    // Query for signals with execution.orders
    const query = {
      'execution.orders': { $exists: true, $ne: [] }
    };
    if (environment) {
      query.environment = environment;
    }

    const signals = await signalStoreCollection
      .find(query, {
        projection: {
          signal_id: 1,
          'execution.orders': 1,
          created_at: 1,
          environment: 1,
          'raw.legs': 1
        }
      })
      .sort({ created_at: -1 })
      .limit(limit)
      .toArray();

    // Flatten execution.orders[] from all signals into a single array
    const orders = [];
    signals.forEach(signal => {
      const instrument = signal.raw?.legs?.[0]?.instrument || 'N/A';
      const signalType = signal.raw?.signal_type || 'UNKNOWN';

      signal.execution.orders.forEach(order => {
        // Generate shorter, more readable order ID
        // Format: {signal_id}_{fund}_{broker_short}
        const brokerShort = (order.account_id || 'UNK').replace(/[-_]MOCK/g, '').replace(/IBKR-/g, '');
        const shortOrderId = `${signal.signal_id}_${order.fund_id}_${brokerShort}`;

        // Determine status based on filled quantity
        let status = 'FILLED';
        if (order.quantity_filled === 0) {
          status = 'PENDING';
        } else if (order.quantity_filled < order.quantity_requested) {
          status = 'PARTIAL';
        }

        orders.push({
          signal_id: signal.signal_id,
          order_id: shortOrderId,
          full_order_id: order.order_id, // Keep full ID for reference
          broker_order_id: order.broker_order_id,
          broker: order.account_id || 'N/A', // Broker/account
          fund_id: order.fund_id,
          instrument: instrument,
          signal_type: signalType,
          quantity_requested: order.quantity_requested,
          quantity_filled: order.quantity_filled,
          avg_fill_price: order.avg_fill_price,
          filled_at: order.filled_at,
          status: status,
          environment: signal.environment,
          fills: order.fills
        });
      });
    });

    // Sort by filled_at descending
    orders.sort((a, b) => {
      const timeA = a.filled_at ? new Date(a.filled_at).getTime() : 0;
      const timeB = b.filled_at ? new Date(b.filled_at).getTime() : 0;
      return timeB - timeA;
    });

    res.json({ status: 'success', count: orders.length, orders: serializeDocument(orders) });
  } catch (error) {
    console.error('[API] Error fetching orders:', error);
    res.status(500).json({ detail: error.message });
  }
});

// GET /api/v1/activity/positions
// Fetches positions (both open and closed) from signal_store
app.get('/api/v1/activity/positions', async (req, res) => {
  try {
    const limit = parseInt(req.query.limit) || 50;
    const environment = req.query.environment;
    const status = req.query.status; // 'OPEN' or 'CLOSED'

    // Query for ENTRY signals with position data
    const query = {
      'position.status': { $exists: true }
    };
    if (environment) {
      query.environment = environment;
    }
    if (status) {
      query['position.status'] = status;
    }

    const entrySignals = await signalStoreCollection
      .find(query, {
        projection: {
          signal_id: 1,
          strategy_id: 1,
          'position': 1,
          'execution': 1,
          'raw.legs': 1,
          'raw.signal_type': 1,
          created_at: 1,
          environment: 1
        }
      })
      .sort({ 'position.opened_at': -1 })
      .limit(limit)
      .toArray();

    // Build positions with entry and exit signal details
    const positions = [];
    for (const entrySignal of entrySignals) {
      const instrument = entrySignal.raw?.legs?.[0]?.instrument || 'N/A';
      const strategyId = entrySignal.strategy_id || 'N/A';
      const entryPrice = entrySignal.execution?.weighted_avg_price || 0;
      const totalQty = entrySignal.execution?.total_quantity_filled || 0;
      const costBasis = entrySignal.execution?.total_cost_basis || 0;

      // Collect unique fund_ids from execution.orders
      const fundIds = [...new Set((entrySignal.execution?.orders || []).map(o => o.fund_id))].filter(Boolean);
      const fundId = fundIds.join(', ') || 'N/A';

      let exitSignals = [];
      let exitPrice = null;
      let proceeds = null;

      // Fetch exit signals if position is closed
      if (entrySignal.position.status === 'CLOSED' && entrySignal.position.exit_signals?.length > 0) {
        // Get unique exit signal IDs
        const uniqueExitIds = [...new Set(entrySignal.position.exit_signals.map(id => id.toString()))];

        exitSignals = await signalStoreCollection
          .find(
            { _id: { $in: uniqueExitIds.map(id => new ObjectId(id)) } },
            { projection: { signal_id: 1, 'execution.weighted_avg_price': 1, 'execution.total_proceeds': 1 } }
          )
          .toArray();

        // Use first exit signal for price (they should all be the same for multi-fund)
        if (exitSignals.length > 0) {
          exitPrice = exitSignals[0].execution?.weighted_avg_price || 0;
          proceeds = exitSignals[0].execution?.total_proceeds || 0;
        }
      }

      positions.push({
        entry_signal_id: entrySignal.signal_id,
        exit_signal_ids: exitSignals.map(s => s.signal_id),
        strategy_id: strategyId,
        fund_id: fundId,
        instrument: instrument,
        status: entrySignal.position.status,
        quantity: totalQty,
        entry_price: entryPrice,
        exit_price: exitPrice,
        cost_basis: costBasis,
        proceeds: proceeds,
        current_value: entrySignal.position.status === 'OPEN' ? costBasis : proceeds, // TODO: calculate unrealized for open
        pnl: entrySignal.position.pnl || null,
        opened_at: entrySignal.position.opened_at,
        closed_at: entrySignal.position.closed_at || null,
        environment: entrySignal.environment
      });
    }

    res.json({
      status: 'success',
      count: positions.length,
      positions: serializeDocument(positions)
    });
  } catch (error) {
    console.error('[API] Error fetching positions:', error);
    res.status(500).json({ detail: error.message });
  }
});

// GET /api/v1/activity/decisions
// Supports both v1 (cerebro_decision) and v2 (decision) schema
app.get('/api/v1/activity/decisions', async (req, res) => {
  try {
    const limit = parseInt(req.query.limit) || 50;
    const environment = req.query.environment;

    // Query for docs with either v1 or v2 decision field
    const query = {
      $or: [
        { decision: { $ne: null } },
        { cerebro_decision: { $ne: null } }
      ]
    };
    if (environment) {
      query.environment = environment;
    }

    const docs = await signalStoreCollection
      .find(query, { projection: { _id: 0 } })
      .sort({ created_at: -1 })
      .limit(limit)
      .toArray();

    const decisions = docs.map(doc => {
      // Support both v1 and v2 schema
      const decision = doc.decision || doc.cerebro_decision || {};
      decision.signal_id = doc.signal_id;
      return serializeDocument(decision);
    });

    res.json({ status: 'success', count: decisions.length, decisions });
  } catch (error) {
    console.error('[API] Error fetching decisions:', error);
    res.status(500).json({ detail: error.message });
  }
});

// ============================================================================
// Dashboard Management Endpoints (v5)
// ============================================================================

// GET /api/v1/dashboards - List all dashboards
app.get('/api/v1/dashboards', async (req, res) => {
  try {
    const fundId = req.query.fund_id;
    const createdBy = req.query.created_by;

    const query = {};
    if (fundId) query.fund_id = fundId;
    if (createdBy) query.created_by = createdBy;

    const dashboards = await db.collection('dashboards')
      .find(query)
      .sort({ created_at: -1 })
      .toArray();

    res.json({ status: 'success', dashboards: dashboards.map(serializeDocument) });
  } catch (error) {
    console.error('[API] Error fetching dashboards:', error);
    res.status(500).json({ error: error.message });
  }
});

// GET /api/v1/dashboards/:dashboard_id - Get specific dashboard
app.get('/api/v1/dashboards/:dashboard_id', async (req, res) => {
  try {
    const { dashboard_id } = req.params;

    const dashboard = await db.collection('dashboards').findOne({ dashboard_id });

    if (!dashboard) {
      return res.status(404).json({ error: 'Dashboard not found' });
    }

    res.json(serializeDocument(dashboard));
  } catch (error) {
    console.error('[API] Error fetching dashboard:', error);
    res.status(500).json({ error: error.message });
  }
});

// POST /api/v1/dashboards - Create new dashboard
app.post('/api/v1/dashboards', async (req, res) => {
  try {
    const { name, description, created_by, fund_id, widgets, grid_config } = req.body;

    const dashboard = {
      dashboard_id: `dashboard-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      name,
      description: description || '',
      created_by: created_by || 'anonymous',
      fund_id: fund_id || null,
      is_locked: false,
      widgets: widgets || [],
      grid_config: grid_config || { cols: 12, row_height: 100 },
      created_at: new Date(),
      updated_at: new Date()
    };

    await db.collection('dashboards').insertOne(dashboard);

    res.json({ status: 'success', dashboard_id: dashboard.dashboard_id });
  } catch (error) {
    console.error('[API] Error creating dashboard:', error);
    res.status(500).json({ error: error.message });
  }
});

// PUT /api/v1/dashboards/:dashboard_id - Update dashboard
app.put('/api/v1/dashboards/:dashboard_id', async (req, res) => {
  try {
    const { dashboard_id } = req.params;
    const updates = req.body;

    // Don't allow updating dashboard_id or created_at
    delete updates.dashboard_id;
    delete updates.created_at;

    // Set updated_at
    updates.updated_at = new Date();

    const result = await db.collection('dashboards').updateOne(
      { dashboard_id },
      { $set: updates }
    );

    if (result.matchedCount === 0) {
      return res.status(404).json({ error: 'Dashboard not found' });
    }

    res.json({ status: 'success', modified: result.modifiedCount });
  } catch (error) {
    console.error('[API] Error updating dashboard:', error);
    res.status(500).json({ error: error.message });
  }
});

// DELETE /api/v1/dashboards/:dashboard_id - Delete dashboard
app.delete('/api/v1/dashboards/:dashboard_id', async (req, res) => {
  try {
    const { dashboard_id } = req.params;

    const result = await db.collection('dashboards').deleteOne({ dashboard_id });

    if (result.deletedCount === 0) {
      return res.status(404).json({ error: 'Dashboard not found' });
    }

    res.json({ status: 'success', deleted: result.deletedCount });
  } catch (error) {
    console.error('[API] Error deleting dashboard:', error);
    res.status(500).json({ error: error.message });
  }
});

// ============================================================================
// Widget Data Endpoints (v5)
// ============================================================================

// GET /api/v1/widgets/:widget_type/data - Get widget data with staleness info
app.get('/api/v1/widgets/:widget_type/data', async (req, res) => {
  try {
    const { widget_type } = req.params;
    const { fund_id, account_filter, date_range_days, group_by } = req.query;

    // Build filters object to match Python generator format
    let filters = {};
    if (widget_type === 'AccountStatement') {
      filters = {
        account_filter: account_filter || null,
        date_range_days: date_range_days ? parseInt(date_range_days) : 30,
        group_by: group_by || 'date'
      };
    }
    // FundBalances and other widgets use empty filters

    // Create filters hash (same logic as Python generators)
    // Note: Python's json.dumps uses spaces after colons and commas by default
    const crypto = await import('crypto');
    const filtersStr = JSON.stringify(filters, Object.keys(filters).sort(), 0).replace(/,/g, ', ').replace(/:/g, ': ');
    const filtersHash = crypto.createHash('md5').update(filtersStr).digest('hex');

    // Query widget_data collection
    const query = {
      widget_type,
      fund_id: fund_id || null,
      filters_hash: filtersHash
    };

    const widgetData = await db.collection('widget_data').findOne(query);

    if (!widgetData) {
      return res.status(404).json({ error: 'Widget data not found' });
    }

    // Calculate staleness
    const now = new Date();
    const computedAt = new Date(widgetData.computed_at);
    const ageSeconds = (now - computedAt) / 1000;
    const isStale = ageSeconds > widgetData.ttl;

    res.json({
      data: widgetData.data,
      computed_at: widgetData.computed_at,
      age_seconds: ageSeconds,
      is_stale: isStale
    });
  } catch (error) {
    console.error('[API] Error fetching widget data:', error);
    res.status(500).json({ error: error.message });
  }
});

// POST /api/v1/widgets/:widget_type/reload - Force reload widget
app.post('/api/v1/widgets/:widget_type/reload', async (req, res) => {
  try {
    const { widget_type } = req.params;
    const { fund_id, account_filter, date_range_days, group_by } = req.body;

    // Call dashboard_creator service to regenerate widget
    const axios = await import('axios');
    const dashboardCreatorUrl = process.env.DASHBOARD_CREATOR_URL || 'http://localhost:8004';

    const response = await axios.default.post(
      `${dashboardCreatorUrl}/api/v1/widgets/${widget_type}/generate`,
      { fund_id, account_filter, date_range_days, group_by }
    );

    res.json(response.data);
  } catch (error) {
    console.error('[API] Error reloading widget:', error);
    res.status(500).json({ error: error.message });
  }
});

// POST /api/v1/dashboards/:dashboard_id/reload-all - Reload all widgets in dashboard
app.post('/api/v1/dashboards/:dashboard_id/reload-all', async (req, res) => {
  try {
    const { dashboard_id } = req.params;

    // Get dashboard
    const dashboard = await db.collection('dashboards').findOne({ dashboard_id });

    if (!dashboard) {
      return res.status(404).json({ error: 'Dashboard not found' });
    }

    // Reload each widget
    const axios = await import('axios');
    const dashboardCreatorUrl = process.env.DASHBOARD_CREATOR_URL || 'http://localhost:8004';

    const reloadPromises = dashboard.widgets.map(widget => {
      const payload = {
        fund_id: dashboard.fund_id,
        ...widget.config
      };

      return axios.default.post(
        `${dashboardCreatorUrl}/api/v1/widgets/${widget.widget_type}/generate`,
        payload
      ).catch(err => {
        console.error(`Failed to reload widget ${widget.widget_id}:`, err.message);
        return { error: err.message };
      });
    });

    await Promise.all(reloadPromises);

    res.json({ status: 'success', reloaded: dashboard.widgets.length });
  } catch (error) {
    console.error('[API] Error reloading dashboard widgets:', error);
    res.status(500).json({ error: error.message });
  }
});

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'frontend-api' });
});

// Start server
async function start() {
  await connectToMongo();
  app.listen(PORT, '0.0.0.0', () => {
    console.log(`[API] Frontend API server running on port ${PORT}`);
  });
}

start();
