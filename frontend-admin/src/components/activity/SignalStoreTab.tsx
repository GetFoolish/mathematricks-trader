import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { api } from '../../services/api';
import { StatusDot, getServiceStatus } from './StatusIndicators';

interface SignalStore {
  _id: string;
  signal_id: string;
  base_signal_id: string;
  strategy_id: string;
  instrument: string;
  environment?: string;
  mode?: string;
  legs?: any[];
  position?: {
    status?: string;
    entry_quantity?: number;
    exit_quantity?: number;
    remaining_quantity?: number;
    pnl?: {
      net?: number;
      percent?: number;
    };
    opened_at?: string;
    closed_at?: string;
  };
  created_at: string;
  updated_at: string;
  processing_complete?: boolean;
  [key: string]: any;
}

export default function SignalStoreTab() {
  const [signals, setSignals] = useState<SignalStore[]>([]);
  const [expandedSignalId, setExpandedSignalId] = useState<string | null>(null);
  const [expandedLegId, setExpandedLegId] = useState<string | null>(null);
  const [showSignalDict, setShowSignalDict] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSignals();
  }, []);

  const fetchSignals = async () => {
    try {
      setLoading(true);
      const data = await api.getSignalStore({ limit: 100 });
      setSignals(data.signals || []);
      setError(null);
    } catch (err: any) {
      console.error('Error fetching signal store:', err);
      setError(err.message || 'Failed to fetch signal store');
    } finally {
      setLoading(false);
    }
  };

  const formatTimestamp = (timestamp: string) => {
    if (!timestamp) return 'N/A';
    try {
      const date = new Date(timestamp);
      return date.toLocaleString();
    } catch {
      return timestamp;
    }
  };

  const formatDate = (date: any) => {
    if (!date) return 'N/A';
    try {
      return new Date(date).toLocaleString();
    } catch {
      return 'Invalid Date';
    }
  };

  const getPositionStatus = (signal: SignalStore) => {
    return signal.position?.status || 'UNKNOWN';
  };

  const getLegsCount = (signal: SignalStore) => {
    const legs = signal.legs || [];
    const entryCount = legs.filter((leg: any) => leg.leg_type === 'ENTRY').length;
    const exitCount = legs.filter((leg: any) => leg.leg_type === 'EXIT').length;
    return { entry: entryCount, exit: exitCount, total: legs.length };
  };

  if (loading) {
    return <div className="flex justify-center items-center p-8 text-gray-400">Loading...</div>;
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-700 rounded-lg p-4 m-4">
        <p className="text-red-400">Error: {error}</p>
        <button
          onClick={fetchSignals}
          className="mt-2 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-full bg-gray-900">
      {/* Table View */}
      <div className="w-full overflow-auto">
        <div className="p-4">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold text-white">Signal Store ({signals.length})</h2>
            <button
              onClick={fetchSignals}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              Refresh
            </button>
          </div>

          <div className="overflow-x-auto bg-gray-800 rounded-lg shadow">
            <table className="min-w-full divide-y divide-gray-700">
              <thead className="bg-gray-900/50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase w-8"></th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Signal ID</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Strategy</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Instrument</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Mode</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Position</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Legs</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Created</th>
                </tr>
              </thead>
              <tbody className="bg-gray-800 divide-y divide-gray-700">
                {signals.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-gray-400">
                      No signals found in signal store
                    </td>
                  </tr>
                ) : (
                  signals.map((signal) => {
                    const legsCount = getLegsCount(signal);
                    const entryQty = signal.position?.entry_quantity || 0;
                    const exitQty = signal.position?.exit_quantity || 0;
                    const remainingQty = signal.position?.remaining_quantity || 0;
                    const isExpanded = expandedSignalId === signal._id;
                    const legs = signal.legs || [];                  
                  // Helper function to calculate lag in seconds from timestamps
                  const calculateLag = (startTime: string | undefined, endTime: string | undefined): string => {
                    if (!startTime || !endTime) return '-';
                    try {
                      const start = new Date(startTime).getTime();
                      const end = new Date(endTime).getTime();
                      const lagMs = end - start;
                      return `${(lagMs / 1000).toFixed(3)}s`;
                    } catch {
                      return '-';
                    }
                  };
                    return (
                      <React.Fragment key={signal._id}>
                        <tr
                          onClick={() => setExpandedSignalId(isExpanded ? null : signal._id)}
                          className="hover:bg-gray-700/50 transition-colors cursor-pointer"
                        >
                          <td className="px-4 py-3">
                            <div className="text-gray-400 hover:text-gray-200">
                              {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                            </div>
                          </td>
                          <td className="px-4 py-3 text-sm font-mono text-gray-300">
                            {signal.signal_id}
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-300">{signal.strategy_id}</td>
                          <td className="px-4 py-3 text-sm text-gray-200">{signal.instrument}</td>
                          <td className="px-4 py-3 text-sm font-mono text-gray-300">{signal.mode || 'N/A'}</td>
                          <td className="px-4 py-3">
                            {(() => {
                              const filledPercent = entryQty === 0 ? 0 : (exitQty / entryQty) * 100;
                              const isFullyClosed = remainingQty === 0 && exitQty > 0;
                              const hasOpenPosition = remainingQty > 0;

                              return (
                                <div className="flex flex-col gap-1 min-w-[120px]">
                                  <div className="flex items-center gap-2">
                                    <span className="text-xs font-medium text-gray-300 whitespace-nowrap">
                                      {exitQty}/{entryQty}
                                    </span>
                                  </div>
                                  <div className="w-full bg-gray-700 rounded-full h-2 overflow-hidden">
                                    <div
                                      className={`h-full transition-all duration-300 ${
                                        isFullyClosed ? 'bg-green-500' : hasOpenPosition ? 'bg-orange-500' : 'bg-gray-600'
                                      }`}
                                      style={{ width: `${Math.min(filledPercent, 100)}%` }}
                                    />
                                  </div>
                                </div>
                              );
                            })()}
                          </td>
                          <td className="px-4 py-3 text-xs text-gray-400">
                            {legsCount.entry} ENTRY + {legsCount.exit} EXIT
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-300">{formatTimestamp(signal.created_at)}</td>
                        </tr>
                        
                        {/* Expanded Legs Section */}
                        {isExpanded && legs.length > 0 && (
                          <tr>
                            <td colSpan={8} className="p-0 bg-gray-850">
                              <div className="p-4 space-y-2 overflow-visible">
                                {/* Header with Signal Dict Toggle */}
                                <div className="flex items-center justify-between mb-3">
                                  <h4 className="text-sm font-semibold text-gray-300">Signal Legs ({legs.length})</h4>
                                  <div className="flex items-center gap-3">
                                    <span className="text-xs font-semibold text-gray-400">Signal Dict</span>
                                    <label className="relative inline-flex items-center cursor-pointer">
                                      <input
                                        type="checkbox"
                                        checked={showSignalDict === signal._id}
                                        onChange={(e) => {
                                          e.stopPropagation();
                                          setShowSignalDict(showSignalDict === signal._id ? null : signal._id);
                                        }}
                                        className="sr-only peer"
                                      />
                                      <div className="w-9 h-5 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
                                    </label>
                                  </div>
                                </div>
                                
                                {/* Signal Dict Display */}
                                {showSignalDict === signal._id && (
                                  <div className="mb-4 bg-gray-900 p-4 rounded">
                                    <pre className="text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap">
                                      {JSON.stringify(signal, null, 2)}
                                    </pre>
                                  </div>
                                )}
                                
                                {legs.map((leg: any, legIdx: number) => {
                                  const legId = `${signal._id}-${legIdx}`;
                                  const isLegExpanded = expandedLegId === legId;
                                  const decision = leg.decision || {};
                                  const decisionStatus = decision.status || 'PENDING';
                                  const serviceStatus = getServiceStatus(leg);
                                  
                                  return (
                                    <div key={legIdx} className="border border-gray-700 rounded-lg overflow-visible">
                                      {/* Leg Header */}
                                      <div
                                        onClick={() => setExpandedLegId(isLegExpanded ? null : legId)}
                                        className="flex items-center justify-between p-3 bg-gray-750 hover:bg-gray-700 cursor-pointer"
                                      >
                                        <div className="flex items-center gap-4">
                                          {isLegExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                          <span className="text-sm font-medium text-white">
                                            Leg {leg.leg_index !== undefined ? leg.leg_index + 1 : legIdx + 1}: {leg.leg_type || 'N/A'}
                                          </span>
                                          <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                                            decisionStatus === 'APPROVED' ? 'bg-green-900/30 text-green-400' :
                                            decisionStatus === 'REJECTED' ? 'bg-red-900/30 text-red-400' :
                                            'bg-yellow-900/30 text-yellow-400'
                                          }`}>
                                            {decisionStatus}
                                          </span>
                                          <div className="flex items-center gap-1.5">
                                            <StatusDot status={serviceStatus.ingestion.status} tooltip={serviceStatus.ingestion.tooltip} />
                                            <StatusDot status={serviceStatus.cerebro.status} tooltip={serviceStatus.cerebro.tooltip} />
                                            <StatusDot status={serviceStatus.execution.status} tooltip={serviceStatus.execution.tooltip} />
                                          </div>
                                          {decision.reason && (
                                            <span className="text-xs text-gray-400 truncate max-w-md">
                                              {decision.reason}
                                            </span>
                                          )}
                                        </div>
                                      </div>
                                      
                                      {/* Leg Expanded Content */}
                                      {isLegExpanded && (
                                        <div className="p-4 bg-gray-800 space-y-4">
                                          {/* Quantities Summary - Top Left */}
                                          <div className="flex gap-6 text-sm">
                                            <div>
                                              <span className="text-gray-500">Raw Quantity:</span>{' '}
                                              <span className="text-white font-semibold">
                                                {leg.raw?.quantity || leg.raw?.legs?.[0]?.quantity || 'N/A'}
                                              </span>
                                            </div>
                                            <div>
                                              <span className="text-gray-500">Cerebro Quantity:</span>{' '}
                                              <span className="text-white font-semibold">
                                                {decision.quantity !== undefined ? decision.quantity : (decision.legs?.[0]?.quantity || 'N/A')}
                                              </span>
                                            </div>
                                          </div>

                                          {/* Processing Timeline Table */}
                                          <div className="space-y-2">
                                            <h5 className="text-xs font-semibold text-gray-400">Processing Timeline</h5>
                                            <div className="overflow-x-auto">
                                              <table className="min-w-full bg-gray-900 rounded text-xs">
                                                <thead className="bg-gray-950">
                                                  <tr>
                                                    <th className="px-3 py-2 text-left text-gray-400">Service</th>
                                                    <th className="px-3 py-2 text-left text-gray-400">Timestamp</th>
                                                    <th className="px-3 py-2 text-left text-gray-400">Lag (s)</th>
                                                    <th className="px-3 py-2 text-left text-gray-400">Status</th>
                                                  </tr>
                                                </thead>
                                                <tbody className="divide-y divide-gray-800">
                                                  <tr>
                                                    <td className="px-3 py-2 text-white">Signal Ingestion</td>
                                                    <td className="px-3 py-2 text-gray-300 font-mono">
                                                      {leg.processing_timestamps?.signal_received ? formatDate(leg.processing_timestamps.signal_received) : (leg.raw?.received_at ? formatDate(leg.raw.received_at) : 'N/A')}
                                                    </td>
                                                    <td className="px-3 py-2 text-gray-300 font-mono">
                                                      {leg.processing_lag?.service_lags?.signal_ingestion ? `${(leg.processing_lag.service_lags.signal_ingestion / 1000).toFixed(3)}s` : '-'}
                                                    </td>
                                                    <td className="px-3 py-2">
                                                      <StatusDot status={serviceStatus.ingestion.status} tooltip={serviceStatus.ingestion.tooltip} />
                                                    </td>
                                                  </tr>
                                                  <tr>
                                                    <td className="px-3 py-2 text-white">Cerebro</td>
                                                    <td className="px-3 py-2 text-gray-300 font-mono">
                                                      {leg.processing_timestamps?.cerebro_processed ? formatDate(leg.processing_timestamps.cerebro_processed) : (decision.timestamp ? formatDate(decision.timestamp) : 'N/A')}
                                                    </td>
                                                    <td className="px-3 py-2 text-gray-300 font-mono">
                                                      {leg.processing_lag?.service_lags?.cerebro ? `${(leg.processing_lag.service_lags.cerebro / 1000).toFixed(3)}s` : '-'}
                                                    </td>
                                                    <td className="px-3 py-2">
                                                      <StatusDot status={serviceStatus.cerebro.status} tooltip={serviceStatus.cerebro.tooltip} />
                                                    </td>
                                                  </tr>
                                                  <tr>
                                                    <td className="px-3 py-2 text-white">Execution</td>
                                                    <td className="px-3 py-2 text-gray-300 font-mono">
                                                      {leg.processing_timestamps?.execution_completed ? formatDate(leg.processing_timestamps.execution_completed) : (leg.execution?.timestamp ? formatDate(leg.execution.timestamp) : 'N/A')}
                                                    </td>
                                                    <td className="px-3 py-2 text-gray-300 font-mono">
                                                      {leg.processing_lag?.service_lags?.execution ? `${(leg.processing_lag.service_lags.execution / 1000).toFixed(3)}s` : '-'}
                                                    </td>
                                                    <td className="px-3 py-2">
                                                      <StatusDot status={serviceStatus.execution.status} tooltip={serviceStatus.execution.tooltip} />
                                                    </td>
                                                  </tr>
                                                </tbody>
                                              </table>
                                            </div>
                                          </div>

                                          {/* Three Column Layout: Raw Signal | Cerebro (with Math) | Execution */}
                                          <div className="grid grid-cols-3 gap-4">
                                            {/* Raw Signal */}
                                            <div className="space-y-2">
                                              <h5 className="text-xs font-semibold text-gray-400">Raw Signal</h5>
                                              <div className="bg-gray-900 p-3 rounded text-xs font-mono space-y-1 h-full overflow-auto max-h-96">
                                                {leg.raw ? (
                                                  <pre className="text-gray-300 whitespace-pre-wrap">
                                                    {JSON.stringify(leg.raw, null, 2)}
                                                  </pre>
                                                ) : (
                                                  <div className="text-gray-500 italic">No raw signal data</div>
                                                )}
                                              </div>
                                            </div>

                                            {/* Cerebro Decision with Math */}
                                            <div className="space-y-2">
                                              <h5 className="text-xs font-semibold text-gray-400">Cerebro Decision</h5>
                                              <div className="bg-gray-900 p-3 rounded text-xs font-mono space-y-3 h-full overflow-auto max-h-96">
                                                {/* Decision Details */}
                                                <div className="space-y-1">
                                                  <div><span className="text-gray-500">Status:</span> <span className="text-white">{decision.status || 'N/A'}</span></div>
                                                  <div><span className="text-gray-500">Reason:</span> <span className="text-white">{decision.reason || 'N/A'}</span></div>
                                                  {decision.timestamp && (
                                                    <div><span className="text-gray-500">Timestamp:</span> <span className="text-white">{formatDate(decision.timestamp)}</span></div>
                                                  )}
                                                  {decision.quantity !== undefined && (
                                                    <div><span className="text-gray-500">Quantity:</span> <span className="text-white">{decision.quantity}</span></div>
                                                  )}
                                                  {decision.legs && decision.legs.length > 0 && (
                                                    <div className="mt-2">
                                                      <span className="text-gray-500">Decision Legs:</span>
                                                      <div className="ml-3 mt-1 space-y-1">
                                                        {decision.legs.map((dLeg: any, dLegIdx: number) => (
                                                          <div key={dLegIdx} className="text-gray-300">
                                                            • {dLeg.action} {dLeg.quantity} {dLeg.instrument} @ {dLeg.price}
                                                          </div>
                                                        ))}
                                                      </div>
                                                    </div>
                                                  )}
                                                </div>

                                                {/* Calculation Breakdown */}
                                                {decision.math && (
                                                  <div className="border-t border-gray-700 pt-3">
                                                    <div className="text-gray-500 font-semibold mb-2">Calculation:</div>
                                                    <pre className="text-gray-300 whitespace-pre-wrap">
                                                      {decision.math}
                                                    </pre>
                                                  </div>
                                                )}
                                              </div>
                                            </div>

                                            {/* Execution Details */}
                                            <div className="space-y-2">
                                              <h5 className="text-xs font-semibold text-gray-400">Execution Results</h5>
                                              {leg.execution ? (
                                                <div className="bg-gray-900 p-3 rounded text-xs font-mono space-y-1 h-full">
                                                  <div><span className="text-gray-500">Status:</span> <span className="text-white">{leg.execution.status || 'N/A'}</span></div>
                                                  <div><span className="text-gray-500">Quantity Filled:</span> <span className="text-white">{leg.execution.total_quantity_filled || leg.execution.filled_quantity || 0}</span></div>
                                                  {leg.execution.weighted_avg_price && (
                                                    <div><span className="text-gray-500">Avg Fill Price:</span> <span className="text-white">${leg.execution.weighted_avg_price.toFixed(2)}</span></div>
                                                  )}
                                                  {leg.execution.total_cost_basis && (
                                                    <div><span className="text-gray-500">Total Cost:</span> <span className="text-white">${leg.execution.total_cost_basis.toFixed(2)}</span></div>
                                                  )}
                                                  {leg.execution.total_proceeds && (
                                                    <div><span className="text-gray-500">Total Proceeds:</span> <span className="text-white">${leg.execution.total_proceeds.toFixed(2)}</span></div>
                                                  )}
                                                  {leg.execution.orders && leg.execution.orders.length > 0 && (
                                                    <div className="mt-2">
                                                      <span className="text-gray-500">Orders ({leg.execution.orders.length}):</span>
                                                      <div className="ml-3 mt-1 space-y-1">
                                                        {leg.execution.orders.map((order: any, orderIdx: number) => (
                                                          <div key={orderIdx} className="text-gray-300 text-xs">
                                                            • {order.fund_id}/{order.account_id}: {order.quantity_filled} @ ${order.avg_fill_price?.toFixed(2)}
                                                          </div>
                                                        ))}
                                                      </div>
                                                    </div>
                                                  )}
                                                </div>
                                              ) : (
                                                <div className="bg-gray-900 p-3 rounded text-xs text-gray-500 italic text-center py-8">
                                                  NONE
                                                </div>
                                              )}
                                            </div>
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
