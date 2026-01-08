import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../services/api';
import { TrendingUp, TrendingDown, Clock, ChevronDown, ChevronRight } from 'lucide-react';

export const Activity: React.FC = () => {
  const [selectedTab, setSelectedTab] = useState<'signals' | 'orders' | 'positions'>('signals');
  const [showStaging, setShowStaging] = useState(true);
  const [showProduction, setShowProduction] = useState(false);
  const [expandedSignalId, setExpandedSignalId] = useState<string | null>(null);

  // Determine environment filter for API calls
  // If both or neither selected, fetch all (no filter)
  // If only one selected, filter by that environment
  const environmentFilter = useMemo(() => {
    if (showStaging && showProduction) return undefined; // Both - fetch all
    if (showStaging) return 'staging';
    if (showProduction) return 'production';
    return undefined; // Neither - fetch all (or could return empty)
  }, [showStaging, showProduction]);

  // Fetch signals
  const { data: signalsData, isLoading: isLoadingSignals } = useQuery({
    queryKey: ['signals', environmentFilter],
    queryFn: () => apiClient.getRecentSignals(50, environmentFilter),
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  // Fetch orders
  const { data: ordersData, isLoading: isLoadingOrders } = useQuery({
    queryKey: ['orders', environmentFilter],
    queryFn: () => apiClient.getRecentOrders(50, environmentFilter),
    refetchInterval: 5000,
  });

  // Fetch positions
  const { data: positionsData, isLoading: isLoadingPositions } = useQuery({
    queryKey: ['positions', environmentFilter],
    queryFn: () => apiClient.getPositions(50, environmentFilter),
    refetchInterval: 5000,
  });

  // Filter results client-side based on checkboxes
  const filterByEnvironment = (items: any[]) => {
    if (showStaging && showProduction) return items; // Show all
    if (!showStaging && !showProduction) return items; // Show all if neither selected
    return items.filter(item => {
      const env = item.environment || 'production';
      if (showStaging && env === 'staging') return true;
      if (showProduction && env === 'production') return true;
      return false;
    });
  };

  // Sort signals by signal_sent_timestamp (latest first)
  const signals = filterByEnvironment(signalsData?.signals || []).sort((a: any, b: any) => {
    const timeA = a.signal_sent_timestamp ? new Date(a.signal_sent_timestamp).getTime() : 0;
    const timeB = b.signal_sent_timestamp ? new Date(b.signal_sent_timestamp).getTime() : 0;
    return timeB - timeA; // Descending (latest first)
  });
  const orders = filterByEnvironment(ordersData?.orders || []);

  // Separate open and closed positions
  const allPositions = filterByEnvironment(positionsData?.positions || []);
  const openPositions = allPositions.filter((p: any) => p.status === 'OPEN');
  const closedPositions = allPositions.filter((p: any) => p.status === 'CLOSED');

  // Helper to display current filter state
  const getFilterLabel = () => {
    if (showStaging && showProduction) return 'ALL';
    if (showStaging) return 'STAGING';
    if (showProduction) return 'PRODUCTION';
    return 'ALL';
  };

  return (
    <div className="space-y-6">
      {/* Environment Filter Checkboxes */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">Trading Activity</h2>

        {/* Checkbox filters */}
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={showStaging}
              onChange={(e) => setShowStaging(e.target.checked)}
              className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-900"
            />
            <span className={`text-sm font-medium ${showStaging ? 'text-blue-400' : 'text-gray-400'}`}>
              Staging
            </span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={showProduction}
              onChange={(e) => setShowProduction(e.target.checked)}
              className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-green-600 focus:ring-green-500 focus:ring-offset-gray-900"
            />
            <span className={`text-sm font-medium ${showProduction ? 'text-green-400' : 'text-gray-400'}`}>
              Production
            </span>
          </label>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex space-x-2 border-b border-gray-700">
        <button
          onClick={() => setSelectedTab('signals')}
          className={`px-6 py-3 font-medium transition-colors ${
            selectedTab === 'signals'
              ? 'border-b-2 border-blue-500 text-blue-500'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          Signals ({signals.length})
        </button>
        <button
          onClick={() => setSelectedTab('orders')}
          className={`px-6 py-3 font-medium transition-colors ${
            selectedTab === 'orders'
              ? 'border-b-2 border-blue-500 text-blue-500'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          Orders & Executions ({orders.length})
        </button>
        <button
          onClick={() => setSelectedTab('positions')}
          className={`px-6 py-3 font-medium transition-colors ${
            selectedTab === 'positions'
              ? 'border-b-2 border-blue-500 text-blue-500'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          Positions ({allPositions.length})
        </button>
      </div>

      {/* Recent Signals Tab */}
      {selectedTab === 'signals' && (
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">
            Signals - {getFilterLabel()}
          </h3>

          {isLoadingSignals ? (
            <div className="text-center py-12">
              <div className="inline-block animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mb-3"></div>
              <p className="text-gray-400">Loading signals...</p>
            </div>
          ) : signals.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-400">No signals found for {getFilterLabel()}</p>
              <p className="text-sm text-gray-500 mt-2">Send test signals using live_signal_tester.py</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="table-header w-8"></th>
                    <th className="table-header">Signal Sent</th>
                    <th className="table-header">Type</th>
                    <th className="table-header">Signal ID</th>
                    <th className="table-header">Strategy</th>
                    <th className="table-header">Symbol</th>
                    <th className="table-header">Action</th>
                    <th className="table-header">Direction</th>
                    <th className="table-header">Qty</th>
                    <th className="table-header">Price</th>
                    <th className="table-header">Cerebro Decision</th>
                    <th className="table-header">Status</th>
                    <th className="table-header">PnL</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {signals.map((signal: any) => {
                    const isExpanded = expandedSignalId === signal.signal_id;
                    // Support both v1 (cerebro_decision) and v2 (decision) schema
                    const hasDecision = (signal.decision || signal.cerebro_decision) && signal.decision_status;

                    // Format timestamps
                    const formatTimestamp = (ts: string | null) => {
                      if (!ts) return 'N/A';
                      return new Date(ts).toLocaleString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit'
                      });
                    };

                    const formatLag = (seconds: number | null) => {
                      if (seconds === null || seconds === undefined) return '';
                      return `(${seconds.toFixed(2)}s)`;
                    };

                    return (
                      <React.Fragment key={signal.signal_id}>
                        <tr className="hover:bg-gray-700/50">
                          {/* Expand button on far left */}
                          <td className="table-cell w-8">
                            <button
                              onClick={() => setExpandedSignalId(isExpanded ? null : signal.signal_id)}
                              className="p-1 hover:bg-gray-600 rounded transition-colors"
                              title="View details"
                            >
                              {isExpanded ? (
                                <ChevronDown className="h-4 w-4 text-blue-400" />
                              ) : (
                                <ChevronRight className="h-4 w-4 text-gray-400" />
                              )}
                            </button>
                          </td>
                          <td className="table-cell text-sm">
                            <div className="flex items-center gap-2">
                              <Clock className="h-4 w-4 text-blue-400" />
                              {formatTimestamp(signal.signal_sent_timestamp)}
                            </div>
                          </td>
                          <td className="table-cell">
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              signal.signal_type === 'ENTRY' ? 'bg-green-900/30 text-green-400' :
                              signal.signal_type === 'EXIT' ? 'bg-red-900/30 text-red-400' :
                              'bg-gray-700/30 text-gray-400'
                            }`}>
                              {signal.signal_type || 'UNKNOWN'}
                            </span>
                          </td>
                          <td className="table-cell font-mono text-xs">{signal.signal_id}</td>
                          <td className="table-cell">
                            <span className="px-2 py-1 bg-blue-900/30 text-blue-400 rounded text-xs font-medium">
                              {signal.strategy_id}
                            </span>
                          </td>
                          <td className="table-cell font-semibold">{signal.instrument}</td>
                          <td className="table-cell">
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              signal.action === 'ENTRY' || signal.action === 'BUY' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'
                            }`}>
                              {signal.action}
                            </span>
                          </td>
                          <td className="table-cell">
                            <div className="flex items-center gap-1">
                              {signal.direction === 'LONG' ? (
                                <>
                                  <TrendingUp className="h-4 w-4 text-green-500" />
                                  <span className="text-green-500">LONG</span>
                                </>
                              ) : (
                                <>
                                  <TrendingDown className="h-4 w-4 text-red-500" />
                                  <span className="text-red-500">SHORT</span>
                                </>
                              )}
                            </div>
                          </td>
                          <td className="table-cell">{signal.quantity || 'N/A'}</td>
                          <td className="table-cell">${signal.price?.toFixed(2) || 'N/A'}</td>
                          <td className="table-cell">
                            {hasDecision ? (
                              <span className={`px-2 py-1 rounded text-xs font-medium ${
                                signal.decision_status === 'APPROVED' || signal.decision_status === 'APPROVE' ? 'bg-green-900/30 text-green-400' :
                                signal.decision_status === 'REJECTED' ? 'bg-red-900/30 text-red-400' :
                                'bg-yellow-900/30 text-yellow-400'
                              }`}>
                                {signal.decision_status === 'APPROVE' ? 'APPROVED' : signal.decision_status}
                              </span>
                            ) : (
                              <span className="px-2 py-1 bg-gray-700/30 text-gray-400 rounded text-xs font-medium">
                                PENDING
                              </span>
                            )}
                          </td>
                          <td className="table-cell">
                            <span className="px-2 py-1 bg-green-900/30 text-green-400 rounded text-xs font-medium">
                              {signal.processed_by_cerebro ? 'PROCESSED' : 'PENDING'}
                            </span>
                          </td>
                          <td className="table-cell">
                            {signal.signal_type === 'ENTRY' ? (
                              <span className="text-gray-500">-</span>
                            ) : signal.pnl ? (
                              <span className={`font-semibold ${
                                (signal.pnl.net ?? signal.pnl.net_pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'
                              }`}>
                                ${(signal.pnl.net ?? signal.pnl.net_pnl ?? 0).toFixed(2)}
                                <span className="text-xs ml-1">
                                  ({(signal.pnl.percent ?? signal.pnl.pnl_percent ?? 0) >= 0 ? '+' : ''}{(signal.pnl.percent ?? signal.pnl.pnl_percent ?? 0).toFixed(2)}%)
                                </span>
                              </span>
                            ) : (
                              <span className="text-gray-500">-</span>
                            )}
                          </td>
                        </tr>

                        {/* Expanded details row */}
                        {isExpanded && (
                          <tr>
                            <td colSpan={13} className="bg-gray-800/50 p-4">
                              <div className="max-w-full overflow-x-auto space-y-4">
                                {/* Timing details */}
                                <div>
                                  <h4 className="text-sm font-semibold text-white mb-2">Timing Details</h4>
                                  <div className="grid grid-cols-3 gap-4 p-3 bg-gray-900 rounded border border-gray-700">
                                    <div>
                                      <p className="text-xs text-gray-400">Signal Received</p>
                                      <p className="text-sm text-white">{formatTimestamp(signal.signal_received_timestamp)}</p>
                                      {signal.receive_lag_seconds !== null && (
                                        <p className="text-xs text-yellow-400">{formatLag(signal.receive_lag_seconds)} lag</p>
                                      )}
                                    </div>
                                    <div>
                                      <p className="text-xs text-gray-400">Execution Complete</p>
                                      <p className="text-sm text-white">{formatTimestamp(signal.execution_completed_timestamp)}</p>
                                      {signal.execution_lag_seconds !== null && (
                                        <p className="text-xs text-yellow-400">{formatLag(signal.execution_lag_seconds)} total</p>
                                      )}
                                    </div>
                                    <div>
                                      <p className="text-xs text-gray-400">Environment</p>
                                      <p className={`text-sm font-medium ${signal.environment === 'staging' ? 'text-blue-400' : 'text-green-400'}`}>
                                        {signal.environment?.toUpperCase() || 'UNKNOWN'}
                                      </p>
                                    </div>
                                  </div>
                                </div>

                                {/* Cerebro decision details - support both v1 and v2 schema */}
                                {hasDecision && (() => {
                                  const decision = signal.decision || signal.cerebro_decision;
                                  const mathText = typeof decision?.math === 'string'
                                    ? decision.math
                                    : null;
                                  const decisionWithoutMath = { ...decision };
                                  if (mathText) delete decisionWithoutMath.math;

                                  return (
                                    <div className={`grid gap-4 ${mathText ? 'grid-cols-2' : 'grid-cols-1'}`}>
                                      <div>
                                        <h4 className="text-sm font-semibold text-white mb-2">Cerebro Decision Details</h4>
                                        <pre className="text-xs text-gray-300 bg-gray-900 p-3 rounded border border-gray-700 overflow-auto max-h-64">
                                          {JSON.stringify(decisionWithoutMath, null, 2)}
                                        </pre>
                                      </div>
                                      {mathText && (
                                        <div>
                                          <h4 className="text-sm font-semibold text-white mb-2">Calculation Breakdown</h4>
                                          <pre className="text-xs text-gray-300 bg-gray-900 p-3 rounded border border-gray-700 overflow-auto max-h-64 whitespace-pre-wrap">
                                            {mathText}
                                          </pre>
                                        </div>
                                      )}
                                    </div>
                                  );
                                })()}
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Orders & Executions Tab */}
      {selectedTab === 'orders' && (
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">
            Recent Orders & Executions - {getFilterLabel()}
          </h3>

          {isLoadingOrders ? (
            <div className="text-center py-12">
              <div className="inline-block animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mb-3"></div>
              <p className="text-gray-400">Loading orders...</p>
            </div>
          ) : orders.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-400">No orders found for {getFilterLabel()}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="table-header">Filled Timestamp</th>
                    <th className="table-header">Signal ID</th>
                    <th className="table-header">Order ID</th>
                    <th className="table-header">Status</th>
                    <th className="table-header">Symbol</th>
                    <th className="table-header">Type</th>
                    <th className="table-header">Broker</th>
                    <th className="table-header">Fund</th>
                    <th className="table-header">Filled Qty</th>
                    <th className="table-header">Filled Price</th>
                    <th className="table-header">Broker Order ID</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {orders.map((order: any, idx: number) => (
                    <tr key={`${order.order_id}-${idx}`} className="hover:bg-gray-700/50">
                      <td className="table-cell text-sm">
                        <div className="flex items-center gap-2">
                          <Clock className="h-4 w-4 text-gray-400" />
                          {order.filled_at ? new Date(order.filled_at).toLocaleString() : 'N/A'}
                        </div>
                      </td>
                      <td className="table-cell">
                        <span className="px-2 py-1 bg-purple-900/30 text-purple-400 rounded text-xs font-medium font-mono">
                          {order.signal_id}
                        </span>
                      </td>
                      <td className="table-cell font-mono text-xs text-gray-400">{order.order_id}</td>
                      <td className="table-cell">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          order.status === 'FILLED' ? 'bg-green-900/30 text-green-400' :
                          order.status === 'PARTIAL' ? 'bg-yellow-900/30 text-yellow-400' :
                          order.status === 'PENDING' ? 'bg-blue-900/30 text-blue-400' :
                          'bg-red-900/30 text-red-400'
                        }`}>
                          {order.status}
                        </span>
                      </td>
                      <td className="table-cell font-semibold">{order.instrument}</td>
                      <td className="table-cell">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          order.signal_type === 'ENTRY' ? 'bg-green-900/30 text-green-400' :
                          order.signal_type === 'EXIT' ? 'bg-red-900/30 text-red-400' :
                          'bg-gray-900/30 text-gray-400'
                        }`}>
                          {order.signal_type}
                        </span>
                      </td>
                      <td className="table-cell">
                        <span className="px-2 py-1 bg-blue-900/30 text-blue-400 rounded text-xs font-medium">
                          {order.broker}
                        </span>
                      </td>
                      <td className="table-cell text-xs text-gray-400">{order.fund_id}</td>
                      <td className="table-cell">{order.quantity_filled?.toFixed(2) || 0}</td>
                      <td className="table-cell">${order.avg_fill_price?.toFixed(2) || 0}</td>
                      <td className="table-cell font-mono text-xs text-gray-500">{order.broker_order_id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Positions Tab */}
      {selectedTab === 'positions' && (
        <div className="space-y-6">
          {/* Open Positions Section */}
          <div className="card">
            <h3 className="text-lg font-semibold text-white mb-4">
              Open Positions - {getFilterLabel()} ({openPositions.length})
            </h3>

            {isLoadingPositions ? (
              <div className="text-center py-12">
                <div className="inline-block animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mb-3"></div>
                <p className="text-gray-400">Loading positions...</p>
              </div>
            ) : openPositions.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-gray-400">No open positions for {getFilterLabel()}</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr>
                      <th className="table-header">Opened At</th>
                      <th className="table-header">Entry Signal</th>
                      <th className="table-header">Strategy</th>
                      <th className="table-header">Fund</th>
                      <th className="table-header">Symbol</th>
                      <th className="table-header">Quantity</th>
                      <th className="table-header">Entry Price</th>
                      <th className="table-header">Cost Basis</th>
                      <th className="table-header">Current Value</th>
                      <th className="table-header">Unrealized PnL</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {openPositions.map((position: any, idx: number) => (
                      <tr key={`${position.entry_signal_id}-${idx}`} className="hover:bg-gray-700/50">
                        <td className="table-cell text-sm">
                          <div className="flex items-center gap-2">
                            <Clock className="h-4 w-4 text-gray-400" />
                            {position.opened_at ? new Date(position.opened_at).toLocaleString() : 'N/A'}
                          </div>
                        </td>
                        <td className="table-cell">
                          <span className="px-2 py-1 bg-green-900/30 text-green-400 rounded text-xs font-medium font-mono">
                            {position.entry_signal_id}
                          </span>
                        </td>
                        <td className="table-cell">
                          <span className="px-2 py-1 bg-blue-900/30 text-blue-400 rounded text-xs font-medium">
                            {position.strategy_id}
                          </span>
                        </td>
                        <td className="table-cell text-xs text-gray-400">{position.fund_id}</td>
                        <td className="table-cell font-semibold">{position.instrument}</td>
                        <td className="table-cell">{position.quantity?.toFixed(2) || 0}</td>
                        <td className="table-cell">${position.entry_price?.toFixed(2) || 0}</td>
                        <td className="table-cell">${position.cost_basis?.toFixed(2) || 0}</td>
                        <td className="table-cell">${position.current_value?.toFixed(2) || 0}</td>
                        <td className="table-cell">
                          <span className="text-gray-500 text-xs">Pending</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Closed Positions Section */}
          <div className="card">
            <h3 className="text-lg font-semibold text-white mb-4">
              Closed Positions - {getFilterLabel()} ({closedPositions.length})
            </h3>

            {isLoadingPositions ? (
              <div className="text-center py-12">
                <div className="inline-block animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mb-3"></div>
                <p className="text-gray-400">Loading positions...</p>
              </div>
            ) : closedPositions.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-gray-400">No closed positions for {getFilterLabel()}</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr>
                      <th className="table-header">Closed At</th>
                      <th className="table-header">Entry Signal</th>
                      <th className="table-header">Exit Signal(s)</th>
                      <th className="table-header">Strategy</th>
                      <th className="table-header">Fund</th>
                      <th className="table-header">Symbol</th>
                      <th className="table-header">Quantity</th>
                      <th className="table-header">Entry Price</th>
                      <th className="table-header">Exit Price</th>
                      <th className="table-header">Cost Basis</th>
                      <th className="table-header">Proceeds</th>
                      <th className="table-header">Net PnL</th>
                      <th className="table-header">PnL %</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {closedPositions.map((position: any, idx: number) => {
                      const pnl = position.pnl || {};
                      const netPnl = pnl.net || 0;
                      const pnlPercent = pnl.percent || 0;
                      const isProfitable = netPnl > 0;

                      return (
                        <tr key={`${position.entry_signal_id}-${idx}`} className="hover:bg-gray-700/50">
                          <td className="table-cell text-sm">
                            <div className="flex items-center gap-2">
                              <Clock className="h-4 w-4 text-gray-400" />
                              {position.closed_at ? new Date(position.closed_at).toLocaleString() : 'N/A'}
                            </div>
                          </td>
                          <td className="table-cell">
                            <span className="px-2 py-1 bg-green-900/30 text-green-400 rounded text-xs font-medium font-mono">
                              {position.entry_signal_id}
                            </span>
                          </td>
                          <td className="table-cell">
                            <div className="flex flex-col gap-1">
                              {position.exit_signal_ids?.map((exitId: string, i: number) => (
                                <span key={i} className="px-2 py-1 bg-red-900/30 text-red-400 rounded text-xs font-medium font-mono">
                                  {exitId}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td className="table-cell">
                            <span className="px-2 py-1 bg-blue-900/30 text-blue-400 rounded text-xs font-medium">
                              {position.strategy_id}
                            </span>
                          </td>
                          <td className="table-cell text-xs text-gray-400">{position.fund_id}</td>
                          <td className="table-cell font-semibold">{position.instrument}</td>
                          <td className="table-cell">{position.quantity?.toFixed(2) || 0}</td>
                          <td className="table-cell">${position.entry_price?.toFixed(2) || 0}</td>
                          <td className="table-cell">${position.exit_price?.toFixed(2) || 0}</td>
                          <td className="table-cell">${position.cost_basis?.toFixed(2) || 0}</td>
                          <td className="table-cell">${position.proceeds?.toFixed(2) || 0}</td>
                          <td className="table-cell">
                            <div className="flex items-center gap-1">
                              {isProfitable ? (
                                <TrendingUp className="h-4 w-4 text-green-400" />
                              ) : (
                                <TrendingDown className="h-4 w-4 text-red-400" />
                              )}
                              <span className={isProfitable ? 'text-green-400' : 'text-red-400'}>
                                ${netPnl.toFixed(2)}
                              </span>
                            </div>
                          </td>
                          <td className="table-cell">
                            <span className={isProfitable ? 'text-green-400' : 'text-red-400'}>
                              {pnlPercent.toFixed(2)}%
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
