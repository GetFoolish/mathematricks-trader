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
let rawSignalsCollection;

// Connect to MongoDB
async function connectToMongo() {
  try {
    const client = new MongoClient(MONGODB_URI);
    await client.connect();
    db = client.db('mathematricks_trading');
    signalStoreCollection = db.collection('signal_store');
    tradingOrdersCollection = db.collection('trading_orders');
    // Add collections for new Activity tabs
    rawSignalsCollection = db.collection('trading_signals_raw');
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
// CONSOLIDATED SCHEMA v3: Each document has legs[] array, return each leg as a signal row
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

    // Flatten legs: each leg becomes a separate signal row
    const signals = [];
    for (const doc of docs) {
      const legs = doc.legs || [];

      for (const leg of legs) {
        const raw = leg.raw || {};
        const cerebro = leg.cerebro || null;
        const execution = leg.execution || null;
        const position = doc.position || {};

        // Get first leg from raw.legs (the actual BUY/SELL actions)
        let firstLeg = {};
        if (raw.legs && raw.legs.length > 0) {
          firstLeg = raw.legs[0];
        }

        // Cerebro decision status
        let decisionStatus = cerebro ? (cerebro.status || 'PENDING') : null;

        // Signal type
        let signalType = leg.leg_type || raw.signal_type || 'UNKNOWN';

        // Calculate timestamps and lags
        const signalSentEpoch = raw.sent_epoch;
        let signalSentTimestamp = null;
        if (signalSentEpoch) {
          signalSentTimestamp = new Date(signalSentEpoch * 1000).toISOString();
        }

        let signalReceivedTimestamp = raw.received_at;
        if (typeof signalReceivedTimestamp === 'string') {
          signalReceivedTimestamp = new Date(signalReceivedTimestamp);
        }

        let receiveLagSeconds = null;
        if (signalSentEpoch && signalReceivedTimestamp) {
          receiveLagSeconds = (signalReceivedTimestamp.getTime() / 1000) - signalSentEpoch;
        }

        // Execution timestamp
        let executionCompletedTimestamp = null;
        let executionLagSeconds = null;

        if (execution && execution.orders && execution.orders.length > 0) {
          const lastOrder = execution.orders[execution.orders.length - 1];
          if (lastOrder.filled_at) {
            executionCompletedTimestamp = new Date(lastOrder.filled_at);
          }
        }
        // Fallback to cerebro timestamp
        if (!executionCompletedTimestamp && cerebro && cerebro.timestamp) {
          executionCompletedTimestamp = new Date(cerebro.timestamp);
        }

        if (executionCompletedTimestamp && signalSentEpoch) {
          executionLagSeconds = (executionCompletedTimestamp.getTime() / 1000) - signalSentEpoch;
        }

        // Get PnL from position
        const pnl = position.pnl || null;

        // Get final quantity from cerebro.legs or execution
        let finalQuantity = firstLeg.quantity;
        if (cerebro && cerebro.legs && cerebro.legs.length > 0) {
          finalQuantity = cerebro.legs[0].quantity;
        } else if (execution && execution.total_quantity_filled) {
          // For EXIT legs, cerebro.legs is empty but execution has the actual quantity
          finalQuantity = execution.total_quantity_filled;
        }

        signals.push({
          signal_id: leg.leg_id || doc.signal_id,  // Use leg_id as unique identifier
          base_signal_id: doc.signal_id,  // Parent signal ID
          strategy_id: doc.strategy_id || 'Unknown',
          timestamp: serializeDocument(raw.received_at || doc.created_at),
          created_at: serializeDocument(raw.received_at || doc.created_at),
          instrument: firstLeg.instrument || doc.instrument,
          action: firstLeg.action,
          direction: firstLeg.direction,
          price: firstLeg.price,
          quantity: firstLeg.quantity,
          final_quantity: finalQuantity,
          environment: doc.environment || 'production',
          processed_by_cerebro: decision !== null,
          receive_lag_ms: receiveLagSeconds ? Math.round(receiveLagSeconds * 1000) : 0,
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
        });
      }
    }

    res.json({ status: 'success', count: signals.length, signals });
  } catch (error) {
    console.error('[API] Error fetching signals:', error);
    res.status(500).json({ detail: error.message });
  }
});

// GET /api/v1/activity/orders
// Fetches BOTH pending orders from trading_orders AND executed orders from signal_store
app.get('/api/v1/activity/orders', async (req, res) => {
  try {
    const limit = parseInt(req.query.limit) || 50;
    const environment = req.query.environment;

    const orders = [];

    // PART 1: Fetch PENDING orders from trading_orders collection
    const pendingQuery = { status: 'PENDING' };
    if (environment) {
      pendingQuery.environment = environment;
    }

    const pendingOrders = await tradingOrdersCollection
      .find(pendingQuery)
      .sort({ timestamp: -1 })
      .limit(limit)
      .toArray();

    pendingOrders.forEach(order => {
      // Generate shorter order ID
      const brokerShort = (order.account_id || 'UNK').replace(/[-_]MOCK/g, '').replace(/IBKR-/g, '');
      const shortOrderId = order.fund_id 
        ? `${order.signal_id}_${order.fund_id}_${brokerShort}`
        : `${order.signal_id}_${brokerShort}`;

      orders.push({
        signal_id: order.signal_id,
        leg_id: null,
        leg_type: order.signal_type || 'UNKNOWN',
        order_id: shortOrderId,
        full_order_id: order.order_id,
        broker_order_id: order.broker_order_id || null,
        broker: order.account_id || 'N/A',
        fund_id: order.fund_id || null,
        instrument: order.instrument || 'N/A',
        signal_type: order.signal_type || 'UNKNOWN',
        quantity_requested: order.quantity || 0,
        quantity_filled: 0,
        avg_fill_price: null,
        filled_at: null,
        status: 'PENDING',
        environment: order.environment || 'production',
        fills: [],
        created_at: order.timestamp // For sorting
      });
    });

    // PART 2: Fetch EXECUTED orders from signal_store.legs[].execution.orders[]
    const executedQuery = {
      'legs.execution.orders': { $exists: true, $ne: [] }
    };
    if (environment) {
      executedQuery.environment = environment;
    }

    const signals = await signalStoreCollection
      .find(executedQuery)
      .sort({ created_at: -1 })
      .limit(limit)
      .toArray();

    signals.forEach(signal => {
      const instrument = signal.instrument || 'N/A';

      (signal.legs || []).forEach(leg => {
        if (!leg.execution || !leg.execution.orders) return;

        const signalType = leg.leg_type || 'UNKNOWN';

        leg.execution.orders.forEach(order => {
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
            leg_id: leg.leg_id,
            leg_type: signalType,
            order_id: shortOrderId,
            full_order_id: order.order_id,
            broker_order_id: order.broker_order_id,
            broker: order.account_id || 'N/A',
            fund_id: order.fund_id,
            instrument: instrument,
            signal_type: signalType,
            quantity_requested: order.quantity_requested,
            quantity_filled: order.quantity_filled,
            avg_fill_price: order.avg_fill_price,
            filled_at: order.filled_at,
            status: status,
            environment: signal.environment,
            fills: order.fills,
            created_at: order.filled_at // For sorting
          });
        });
      });
    });

    // Sort by timestamp descending (most recent first)
    orders.sort((a, b) => {
      const timeA = a.created_at ? new Date(a.created_at).getTime() : 0;
      const timeB = b.created_at ? new Date(b.created_at).getTime() : 0;
      return timeB - timeA;
    });

    // Limit total results
    const limitedOrders = orders.slice(0, limit);

    res.json({ status: 'success', count: limitedOrders.length, orders: serializeDocument(limitedOrders) });
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
          instrument: 1,
          'position': 1,
          'legs': 1,
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
      // CONSOLIDATED SCHEMA v3: Get ENTRY leg (first leg)
      const entryLeg = entrySignal.legs?.find(leg => leg.leg_type === 'ENTRY') || entrySignal.legs?.[0] || {};
      const entryRaw = entryLeg.raw || {};
      const entryExecution = entryLeg.execution || {};

      const instrument = entryRaw.legs?.[0]?.instrument || entrySignal.instrument || 'N/A';
      const strategyId = entrySignal.strategy_id || 'N/A';
      const entryPrice = entryExecution.weighted_avg_price || 0;
      const totalQty = entryExecution.total_quantity_filled || 0;
      const costBasis = entryExecution.total_cost_basis || 0;

      // Collect unique fund_ids from execution.orders
      const fundIds = [...new Set((entryExecution.orders || []).map(o => o.fund_id))].filter(Boolean);
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

// GET /api/v1/activity/trading-signals
// Fetches complete trading signals using CONSOLIDATED schema (ONE document per signal)
app.get('/api/v1/activity/trading-signals', async (req, res) => {
  try {
    const limit = parseInt(req.query.limit) || 50;
    const environment = req.query.environment;

    // Query for signal documents (each document represents ONE complete signal with ALL legs)
    const query = {};
    if (environment) query.environment = environment;

    const signals = await signalStoreCollection
      .find(query)
      .sort({ created_at: -1 })
      .limit(limit)
      .toArray();

    // Transform to trading signals format
    const tradingSignals = signals.map(signal => {
      // Get ENTRY leg (should be first leg in array)
      const entryLeg = signal.legs?.find(leg => leg.leg_type === 'ENTRY') || signal.legs?.[0];
      const exitLegs = signal.legs?.filter(leg => leg.leg_type === 'EXIT' || leg.leg_type === 'SCALE_OUT') || [];

      return {
        signal_id: signal.signal_id,
        instrument: signal.instrument,
        strategy_id: signal.strategy_id,
        environment: signal.environment,

        // Position info
        status: signal.position?.status || 'PENDING',
        opened_at: serializeDocument(signal.position?.opened_at),
        closed_at: serializeDocument(signal.position?.closed_at),

        // P&L info (cumulative for PARTIAL, final for CLOSED)
        pnl: serializeDocument(signal.position?.pnl),

        // Partial exit info
        partial_exit_count: signal.position?.partial_exit_count,
        remaining_quantity: signal.position?.remaining_quantity,
        entry_quantity: signal.position?.entry_quantity,
        exit_quantity: signal.position?.exit_quantity,

        // Legs
        legs: serializeDocument(signal.legs),
        entry_leg: serializeDocument(entryLeg),
        exit_legs: exitLegs.map(serializeDocument),

        // Metadata
        created_at: serializeDocument(signal.created_at),
        updated_at: serializeDocument(signal.updated_at)
      };
    });

    res.json({
      status: 'success',
      count: tradingSignals.length,
      trading_signals: tradingSignals
    });

  } catch (error) {
    console.error('[API] Error fetching trading signals:', error);
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

// ============================================================================
// NEW ACTIVITY TAB ENDPOINTS
// ============================================================================

// GET /api/v1/activity/raw-signals - Tab 1: Raw Signals from trading_signals_raw
app.get('/api/v1/activity/raw-signals', async (req, res) => {
  try {
    const limit = parseInt(req.query.limit) || 100;
    const environment = req.query.environment;

    const query = {};
    if (environment) {
      query.environment = environment;
    }

    const rawSignals = await rawSignalsCollection
      .find(query)
      .sort({ received_at: -1 })
      .limit(limit)
      .toArray();

    res.json({
      raw_signals: serializeDocument(rawSignals),
      count: rawSignals.length
    });
  } catch (error) {
    console.error('[API] Error fetching raw signals:', error);
    res.status(500).json({ error: error.message });
  }
});

// GET /api/v1/activity/signal-store - Tab 2: Signal Store
app.get('/api/v1/activity/signal-store', async (req, res) => {
  try {
    const limit = parseInt(req.query.limit) || 100;
    const environment = req.query.environment;

    const query = {};
    if (environment) {
      query.environment = environment;
    }

    const signals = await signalStoreCollection
      .find(query)
      .sort({ created_at: -1 })
      .limit(limit)
      .toArray();

    res.json({
      signals: serializeDocument(signals),
      count: signals.length
    });
  } catch (error) {
    console.error('[API] Error fetching signal store:', error);
    res.status(500).json({ error: error.message });
  }
});

// GET /api/v1/activity/trading-orders-full - Tab 3: Trading Orders
app.get('/api/v1/activity/trading-orders-full', async (req, res) => {
  try {
    const limit = parseInt(req.query.limit) || 100;
    const environment = req.query.environment;

    const query = {};
    if (environment) {
      query.environment = environment;
    }

    const orders = await tradingOrdersCollection
      .find(query)
      .sort({ created_at: -1 })
      .limit(limit)
      .toArray();

    res.json({
      orders: serializeDocument(orders),
      count: orders.length
    });
  } catch (error) {
    console.error('[API] Error fetching trading orders:', error);
    res.status(500).json({ error: error.message });
  }
});

// GET /api/v1/activity/signal-status - Tab 4: Signal Status (one row per signal)
app.get('/api/v1/activity/signal-status', async (req, res) => {
  try {
    const limit = parseInt(req.query.limit) || 100;
    const environment = req.query.environment;

    const query = {};
    if (environment) {
      query.environment = environment;
    }

    const signals = await signalStoreCollection
      .find(query)
      .sort({ created_at: -1 })
      .limit(limit)
      .toArray();

    // Transform to status view: one row per signal with summary info
    const statusData = signals.map(doc => {
      const position = doc.position || {};
      const legs = doc.legs || [];
      
      // Count ENTRY and EXIT legs
      const entryLegs = legs.filter(leg => leg.leg_type === 'ENTRY');
      const exitLegs = legs.filter(leg => leg.leg_type === 'EXIT');

      // Get cerebro decision status from first leg
      const firstLegCerebro = legs.length > 0 ? (legs[0].cerebro || {}) : {};
      const decisionStatus = firstLegCerebro.status || 'PENDING';

      return {
        _id: doc._id,
        signal_id: doc.signal_id,
        base_signal_id: doc.base_signal_id,
        strategy_id: doc.strategy_id,
        instrument: doc.instrument,
        environment: doc.environment,
        mode: doc.mode,
        position_status: position.status || 'PENDING',
        entry_quantity: position.entry_quantity || 0,
        exit_quantity: position.exit_quantity || 0,
        remaining_quantity: position.remaining_quantity || 0,
        pnl: position.pnl,
        opened_at: position.opened_at,
        closed_at: position.closed_at,
        created_at: doc.created_at,
        updated_at: doc.updated_at,
        entry_legs_count: entryLegs.length,
        exit_legs_count: exitLegs.length,
        decision_status: decisionStatus,
        processing_complete: doc.processing_complete,
        raw_document: doc // Include full document for detail view
      };
    });

    res.json({
      signals: serializeDocument(statusData),
      count: statusData.length
    });
  } catch (error) {
    console.error('[API] Error fetching signal status:', error);
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
