import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../services/api';
import { ChevronDown, ChevronUp, X } from 'lucide-react';
import { ProcessingLagDisplay } from '../components/ProcessingLagDisplay';

export const Activity: React.FC = () => {
  const [selectedTab, setSelectedTab] = useState<'raw-signals' | 'signal-store' | 'signal-status'>('raw-signals');
  const [showStaging, setShowStaging] = useState(true);
  const [showProduction, setShowProduction] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState<any | null>(null);
  const [expandedOrderId, setExpandedOrderId] = useState<string | null>(null);
  const [expandedSignalId, setExpandedSignalId] = useState<string | null>(null);
  const [expandedLegId, setExpandedLegId] = useState<string | null>(null);
  const [showMathForLeg, setShowMathForLeg] = useState<string | null>(null);

  // Determine environment filter
  const environmentFilter = React.useMemo(() => {
    if (showStaging && showProduction) return undefined;
    if (showStaging) return 'staging';
    if (showProduction) return 'production';
    return undefined;
  }, [showStaging, showProduction]);

  // Fetch data for all tabs
  const { data: rawSignalsData, isLoading: isLoadingRaw } = useQuery({
    queryKey: ['raw-signals', environmentFilter],
    queryFn: () => apiClient.getRawSignals(100, environmentFilter),
    refetchInterval: 5000,
  });

  const { data: signalStoreData, isLoading: isLoadingStore } = useQuery({
    queryKey: ['signal-store', environmentFilter],
    queryFn: () => apiClient.getSignalStore(100, environmentFilter),
    refetchInterval: 5000,
  });

  const { data: signalStatusData, isLoading: isLoadingStatus } = useQuery({
    queryKey: ['signal-status', environmentFilter],
    queryFn: () => apiClient.getSignalStatus(100, environmentFilter),
    refetchInterval: 5000,
  });

  const rawSignals = rawSignalsData?.raw_signals || [];
  const signalStore = signalStoreData?.signals || [];
  const signalStatus = signalStatusData?.signals || [];

  const getFilterLabel = () => {
    if (showStaging && showProduction) return 'ALL';
    if (showStaging) return 'STAGING';
    if (showProduction) return 'PRODUCTION';
    return 'ALL';
  };

  const formatDate = (date: any) => {
    if (!date) return 'N/A';
    try {
      return new Date(date).toLocaleString();
    } catch {
      return 'Invalid Date';
    }
  };

  const handleRowClick = (doc: any) => {
    setSelectedDocument(doc);
  };

  const closeDetailView = () => {
    setSelectedDocument(null);
  };

  return (
    <div className="space-y-6">
      {/* Header with Environment Filters */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">Trading Activity</h2>
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
          onClick={() => setSelectedTab('raw-signals')}
          className={`px-6 py-3 font-medium transition-colors ${
            selectedTab === 'raw-signals'
              ? 'border-b-2 border-blue-500 text-blue-500'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          Raw Signals ({rawSignals.length})
        </button>
        <button
          onClick={() => setSelectedTab('signal-store')}
          className={`px-6 py-3 font-medium transition-colors ${
            selectedTab === 'signal-store'
              ? 'border-b-2 border-blue-500 text-blue-500'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          Signal Store ({signalStore.length})
        </button>
        <button
          onClick={() => setSelectedTab('signal-status')}
          className={`px-6 py-3 font-medium transition-colors ${
            selectedTab === 'signal-status'
              ? 'border-b-2 border-blue-500 text-blue-500'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          Signal Status ({signalStatus.length})
        </button>
      </div>

      {/* Tab Content */}
      <div className="card">
        {/* Tab 1: Raw Signals */}
        {selectedTab === 'raw-signals' && (
          <div>
            <h3 className="text-lg font-semibold text-white mb-4">
              Raw Signals (trading_signals_raw) - {getFilterLabel()}
            </h3>
            {isLoadingRaw ? (
              <div className="text-center py-12">
                <div className="inline-block animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mb-3"></div>
                <p className="text-gray-400">Loading raw signals...</p>
              </div>
            ) : rawSignals.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-gray-400">No raw signals found</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr>
                      <th className="table-header">Received At</th>
                      <th className="table-header">Signal ID</th>
                      <th className="table-header">Strategy</th>
                      <th className="table-header">Signal Type</th>
                      <th className="table-header">Mode</th>
                      <th className="table-header">Environment</th>
                      <th className="table-header">Test</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rawSignals.map((signal: any, idx: number) => (
                      <tr
                        key={signal._id || idx}
                        onClick={() => handleRowClick(signal)}
                        className="cursor-pointer hover:bg-gray-700"
                      >
                        <td className="table-cell">{formatDate(signal.received_at)}</td>
                        <td className="table-cell font-mono text-xs">{signal.signalID || 'N/A'}</td>
                        <td className="table-cell">{signal.strategy_name || 'N/A'}</td>
                        <td className="table-cell">
                          <span className={`px-2 py-1 rounded text-xs font-semibold ${
                            signal.signal_type === 'ENTRY' ? 'bg-green-900 text-green-300' :
                            signal.signal_type === 'EXIT' ? 'bg-red-900 text-red-300' :
                            'bg-gray-700 text-gray-300'
                          }`}>
                            {signal.signal_type || 'N/A'}
                          </span>
                        </td>
                        <td className="table-cell">
                          <span className="px-2 py-1 rounded text-xs bg-purple-900 text-purple-300">
                            {signal.mode || 'N/A'}
                          </span>
                        </td>
                        <td className="table-cell">
                          <span className={`px-2 py-1 rounded text-xs ${
                            signal.environment === 'staging' ? 'bg-blue-900 text-blue-300' : 'bg-green-900 text-green-300'
                          }`}>
                            {signal.environment || 'production'}
                          </span>
                        </td>
                        <td className="table-cell">{signal.test ? 'Yes' : 'No'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Signal Store */}
        {selectedTab === 'signal-store' && (
          <div>
            <h3 className="text-lg font-semibold text-white mb-4">
              Signal Store (signal_store)
            </h3>
            {isLoadingStore ? (
              <div className="text-center py-12">
                <div className="inline-block animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mb-3"></div>
                <p className="text-gray-400">Loading signal store...</p>
              </div>
            ) : signalStore.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-gray-400">No signals in signal_store</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr>
                      <th className="table-header w-8"></th>
                      <th className="table-header">Created At</th>
                      <th className="table-header">Signal ID</th>
                      <th className="table-header">Strategy</th>
                      <th className="table-header">Instrument</th>
                      <th className="table-header">Mode</th>
                      <th className="table-header">Position Status</th>
                      <th className="table-header">Legs</th>
                      <th className="table-header">Environment</th>
                    </tr>
                  </thead>
                  <tbody>
                    {signalStore.map((signal: any, idx: number) => {
                      const signal_legs = signal.signal_legs || [];
                      const position = signal.position || {};
                      const isExpanded = expandedSignalId === signal._id;
                      
                      return (
                        <React.Fragment key={signal._id || idx}>
                          <tr
                            onClick={() => setExpandedSignalId(isExpanded ? null : signal._id)}
                            className="cursor-pointer hover:bg-gray-700"
                          >
                            <td className="table-cell">
                              {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                            </td>
                            <td className="table-cell">{formatDate(signal.created_at)}</td>
                            <td className="table-cell font-mono text-xs">{signal.signal_id || 'N/A'}</td>
                            <td className="table-cell">{signal.strategy_id || 'N/A'}</td>
                            <td className="table-cell">{signal.instrument || 'N/A'}</td>
                            <td className="table-cell">
                              <span className="px-2 py-1 rounded text-xs bg-purple-900 text-purple-300">
                                {signal.mode || 'N/A'}
                              </span>
                            </td>
                            <td className="table-cell">
                              <span className={`px-2 py-1 rounded text-xs font-semibold ${
                                position.status === 'PENDING' ? 'bg-yellow-900 text-yellow-300' :
                                position.status === 'OPEN' ? 'bg-green-900 text-green-300' :
                                position.status === 'PARTIAL' ? 'bg-orange-900 text-orange-300' :
                                position.status === 'CLOSED' ? 'bg-gray-700 text-gray-300' :
                                'bg-gray-700 text-gray-300'
                              }`}>
                                {position.status || 'N/A'}
                              </span>
                            </td>
                            <td className="table-cell">{legs.length}</td>
                            <td className="table-cell">
                              <span className={`px-2 py-1 rounded text-xs ${
                                signal.environment === 'staging' ? 'bg-blue-900 text-blue-300' : 'bg-green-900 text-green-300'
                              }`}>
                                {signal.environment || 'production'}
                              </span>
                            </td>
                          </tr>
                          
                          {/* Expanded Legs Section */}
                          {isExpanded && legs.length > 0 && (
                            <tr>
                              <td colSpan={9} className="p-0 bg-gray-800">
                                <div className="p-4 space-y-2">
                                  <h4 className="text-sm font-semibold text-gray-300 mb-3">Signal Legs ({legs.length})</h4>
                                  
                                  {legs.map((leg: any, legIdx: number) => {
                                    const legId = `${signal._id}-${legIdx}`;
                                    const isLegExpanded = expandedLegId === legId;
                                    const showMath = showMathForLeg === legId;
                                    const cerebro = leg.cerebro || {};
                                    const decisionStatus = cerebro.status || 'PENDING';
                                    const execution = leg.execution || {};
                                    const executionStatus = execution.status;
                                    const executionError = execution.error_reason;
                                    
                                    return (
                                      <div key={legIdx} className="border border-gray-700 rounded-lg overflow-hidden">
                                        {/* Leg Header */}
                                        <div
                                          onClick={() => setExpandedLegId(isLegExpanded ? null : legId)}
                                          className="flex items-center justify-between p-3 bg-gray-750 hover:bg-gray-700 cursor-pointer"
                                        >
                                          <div className="flex items-center gap-4">
                                            {isLegExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                            <span className="text-sm font-medium text-white">
                                              Leg {leg.leg_index + 1}: {leg.leg_type || 'N/A'}
                                            </span>
                                            <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                                              decisionStatus === 'APPROVED' ? 'bg-green-900 text-green-300' :
                                              decisionStatus === 'REJECTED' ? 'bg-red-900 text-red-300' :
                                              'bg-yellow-900 text-yellow-300'
                                            }`}>
                                              {decisionStatus}
                                            </span>
                                            {executionStatus === 'ERROR' && (
                                              <span className="px-2 py-0.5 rounded text-xs font-semibold bg-red-900 text-red-300">
                                                EXEC ERROR
                                              </span>
                                            )}
                                            {executionError && (
                                              <span className="text-xs text-red-400 truncate max-w-md">
                                                {executionError}
                                              </span>
                                            )}
                                            {!executionError && cerebro.reason && (
                                              <span className="text-xs text-gray-400 truncate max-w-md">
                                                {cerebro.reason}
                                              </span>
                                            )}
                                          </div>
                                          {cerebro.math && (
                                            <button
                                              onClick={(e) => {
                                                e.stopPropagation();
                                                setShowMathForLeg(showMath ? null : legId);
                                              }}
                                              className="px-2 py-1 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded"
                                            >
                                              {showMath ? 'Hide Math' : 'Show Math'}
                                            </button>
                                          )}
                                        </div>
                                        
                                        {/* Leg Expanded Content */}
                                        {isLegExpanded && (
                                          <div className="p-4 bg-gray-800 space-y-3">
                                            {/* Processing Timing & Lag */}
                                            {(leg.processing_lag || leg.processing_timestamps) && (
                                              <div className="space-y-2">
                                                <h5 className="text-xs font-semibold text-gray-400">⏱️ Processing Timing</h5>
                                                <div className="bg-gray-900 p-3 rounded">
                                                  <ProcessingLagDisplay 
                                                    processingLag={leg.processing_lag}
                                                    processingTimestamps={leg.processing_timestamps}
                                                  />
                                                </div>
                                              </div>
                                            )}

                                            {/* Execution Details */}
                                            {leg.execution && (
                                              <div className="space-y-2">
                                                <h5 className="text-xs font-semibold text-gray-400">Execution Results</h5>
                                                <div className="bg-gray-900 p-3 rounded text-xs font-mono space-y-1">
                                                  <div><span className="text-gray-500">Status:</span> <span className="text-white">{leg.execution.status || 'N/A'}</span></div>
                                                  {leg.execution.error_reason && (
                                                    <div><span className="text-gray-500">Error:</span> <span className="text-red-300">{leg.execution.error_reason}</span></div>
                                                  )}
                                                  <div><span className="text-gray-500">Quantity Filled:</span> <span className="text-white">{leg.execution.total_quantity_filled || 0}</span></div>
                                                  <div><span className="text-gray-500">Avg Fill Price:</span> <span className="text-white">${leg.execution.weighted_avg_price?.toFixed(2) || 'N/A'}</span></div>
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
                                              </div>
                                            )}

                                            {/* Cerebro Decision Details */}
                                            {cerebro && Object.keys(cerebro).length > 0 && (
                                              <div className="space-y-2">
                                                <h5 className="text-xs font-semibold text-gray-400">Cerebro Decision</h5>
                                                <div className="bg-gray-900 p-3 rounded text-xs font-mono space-y-1">
                                                  <div><span className="text-gray-500">Status:</span> <span className="text-white">{cerebro.status || 'N/A'}</span></div>
                                                  <div><span className="text-gray-500">Reason:</span> <span className="text-white">{cerebro.reason || 'N/A'}</span></div>
                                                  {cerebro.timestamp && (
                                                    <div><span className="text-gray-500">Timestamp:</span> <span className="text-white">{formatDate(cerebro.timestamp)}</span></div>
                                                  )}
                                                  {cerebro.created_orders && cerebro.created_orders.length > 0 && (
                                                    <div className="mt-2">
                                                      <span className="text-gray-500">Cerebro Orders:</span>
                                                      <div className="ml-3 mt-1 space-y-1">
                                                        {cerebro.created_orders.map((order: any, orderIdx: number) => (
                                                          <div key={orderIdx} className="text-gray-300">
                                                            • {order.action} {order.quantity} {order.instrument} @ {order.price}
                                                          </div>
                                                        ))}
                                                      </div>
                                                    </div>
                                                  )}
                                                </div>
                                              </div>
                                            )}
                                            
                                            {/* Math Details */}
                                            {showMath && cerebro.math && (
                                              <div className="space-y-2">
                                                <h5 className="text-xs font-semibold text-gray-400">Calculation Breakdown</h5>
                                                <pre className="bg-gray-900 p-3 rounded text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap">
                                                  {cerebro.math}
                                                </pre>
                                              </div>
                                            )}
                                            
                                            {/* Raw Leg Data */}
                                            <div className="space-y-2">
                                              <h5 className="text-xs font-semibold text-gray-400">Raw Signal Data</h5>
                                              <pre className="bg-gray-900 p-3 rounded text-xs text-gray-300 overflow-x-auto">
                                                {JSON.stringify(leg.raw, null, 2)}
                                              </pre>
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
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Tab 3: Signal Status */}
        {selectedTab === 'signal-status' && (
          <div>
            <h3 className="text-lg font-semibold text-white mb-4">
              Trading Signals (Overview) - {getFilterLabel()}
            </h3>
            {isLoadingStatus ? (
              <div className="text-center py-12">
                <div className="inline-block animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mb-3"></div>
                <p className="text-gray-400">Loading trading signals...</p>
              </div>
            ) : signalStatus.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-gray-400">No trading signals found</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr>
                      <th className="table-header">Signal ID</th>
                      <th className="table-header">Instrument</th>
                      <th className="table-header">Strategy</th>
                      <th className="table-header">Mode</th>
                      <th className="table-header">Status</th>
                      <th className="table-header">Position</th>
                      <th className="table-header">Entry Time</th>
                      <th className="table-header">Exit Time</th>
                      <th className="table-header">P&L</th>
                      <th className="table-header">Legs</th>
                    </tr>
                  </thead>
                  <tbody>
                    {signalStatus.map((signal: any, idx: number) => {
                      const entryQty = signal.entry_quantity || 0;
                      const exitQty = signal.exit_quantity || 0;
                      const remainingQty = signal.remaining_quantity || 0;
                      const filledPercent = entryQty > 0 ? (exitQty / entryQty) * 100 : 0;
                      const isFullyClosed = remainingQty === 0 && exitQty > 0;
                      const hasOpenPosition = remainingQty > 0;
                      const exitLegsCount = signal.exit_legs_count || signal.exit_legs?.length || 0;
                      
                      return (
                        <tr
                          key={signal._id || idx}
                          onClick={() => handleRowClick(signal.raw_document || signal)}
                          className="cursor-pointer hover:bg-gray-700"
                        >
                          <td className="table-cell">
                            <span className="px-2 py-1 bg-blue-900/30 text-blue-400 rounded text-xs font-medium font-mono">
                              {signal.signal_id || 'N/A'}
                            </span>
                          </td>
                          <td className="table-cell font-semibold">{signal.instrument || 'N/A'}</td>
                          <td className="table-cell">
                            <span className="px-2 py-1 bg-purple-900/30 text-purple-400 rounded text-xs font-medium">
                              {signal.strategy_id || 'N/A'}
                            </span>
                          </td>
                          <td className="table-cell">
                            <span className="px-2 py-1 bg-purple-900/30 text-purple-400 rounded text-xs font-medium uppercase">
                              {signal.mode || 'N/A'}
                            </span>
                          </td>
                          <td className="table-cell">
                            <span className={`px-2 py-1 rounded text-xs font-semibold ${
                              signal.signal_status?.status === 'open' ? 'bg-green-900/30 text-green-400' :
                              signal.signal_status?.status === 'closed' ? 'bg-gray-700 text-gray-300' :
                              signal.signal_status?.status === 'rejected' ? 'bg-red-900/30 text-red-400' :
                              'bg-yellow-900/30 text-yellow-400'
                            }`}>
                              {signal.signal_status?.status || 'pending'}
                              {signal.signal_status?.status === 'partial' && remainingQty > 0 && (
                                <span className="ml-1 text-xs">({remainingQty} left)</span>
                              )}
                            </span>
                          </td>
                          <td className="table-cell">
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
                          </td>
                          <td className="table-cell text-sm">
                            {signal.opened_at ? new Date(signal.opened_at).toLocaleString('en-US', {
                              month: 'short',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit'
                            }) : '-'}
                          </td>
                          <td className="table-cell text-sm">
                            {signal.closed_at ? new Date(signal.closed_at).toLocaleString('en-US', {
                              month: 'short',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit'
                            }) : '-'}
                          </td>
                          <td className="table-cell">
                            {signal.pnl?.net !== null && signal.pnl?.net !== undefined ? (
                              <span className={signal.pnl.net >= 0 ? 'text-green-400 font-semibold' : 'text-red-400 font-semibold'}>
                                ${signal.pnl.net.toFixed(2)}
                              </span>
                            ) : signal.pnl !== null && signal.pnl !== undefined && typeof signal.pnl === 'number' ? (
                              <span className={signal.pnl >= 0 ? 'text-green-400 font-semibold' : 'text-red-400 font-semibold'}>
                                ${signal.pnl.toFixed(2)}
                              </span>
                            ) : (
                              <span className="text-gray-500">-</span>
                            )}
                          </td>
                          <td className="table-cell text-xs text-gray-400">
                            1 ENTRY + {exitLegsCount} EXIT
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Document Detail Modal */}
      {selectedDocument && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-800 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-gray-700">
              <h3 className="text-lg font-semibold text-white">Raw Document</h3>
              <button
                onClick={closeDetailView}
                className="text-gray-400 hover:text-white transition-colors"
              >
                <X className="h-6 w-6" />
              </button>
            </div>
            <div className="overflow-auto p-4 flex-1">
              <pre className="text-xs text-gray-300 bg-gray-900 p-4 rounded overflow-x-auto">
                {JSON.stringify(selectedDocument, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
