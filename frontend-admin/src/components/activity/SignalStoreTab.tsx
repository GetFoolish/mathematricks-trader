import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronUp, Download, Copy, Check } from 'lucide-react';
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
  signal_status?: {
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
  const [rawSignals, setRawSignals] = useState<{ [signalId: string]: any }>({});
  const [expandedSignalId, setExpandedSignalId] = useState<string | null>(null);
  const [expandedLegId, setExpandedLegId] = useState<string | null>(null);
  const [showSignalDict, setShowSignalDict] = useState<string | null>(null);
  const [copiedBox, setCopiedBox] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshCountdown, setRefreshCountdown] = useState(5);

  useEffect(() => {
    fetchSignals();
    
    // Poll every 5 seconds for updates
    const interval = setInterval(() => {
      fetchSignals();
      setRefreshCountdown(5);
    }, 5000);
    
    // Update countdown every second
    const countdownInterval = setInterval(() => {
      setRefreshCountdown(prev => prev > 0 ? prev - 1 : 5);
    }, 1000);
    
    return () => {
      clearInterval(interval);
      clearInterval(countdownInterval);
    };
  }, []);

  const copyToClipboard = async (text: string, boxId: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedBox(boxId);
      setTimeout(() => setCopiedBox(null), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const fetchSignals = async () => {
    try {
      // Don't show loading spinner on refresh, only on initial load
      const data = await api.getSignalStore({ limit: 100 });
      setSignals(data.signals || []);
      
      // Fetch raw signals from trading_signals_raw using signal_id (or fallback to _id)
      const rawSignalPromises = (data.signals || []).map(async (signal: SignalStore) => {
        if (signal.signal_id && !rawSignals[signal.signal_id]) {
          try {
            // Try using signal_id first (will match signal_id or signalID or _id in backend)
            const rawData = await api.getRawSignalById(signal.signal_id);
            return { signalId: signal.signal_id, rawSignal: rawData.raw_signal };
          } catch (err) {
            console.error(`Failed to fetch raw signal for ${signal.signal_id}:`, err);
            // Fallback to embedded raw_signal if fetch fails
            return { signalId: signal.signal_id, rawSignal: signal.raw_signal };
          }
        }
        return null;
      });
      
      const rawSignalResults = await Promise.all(rawSignalPromises);
      const newRawSignals = { ...rawSignals };
      rawSignalResults.forEach((result) => {
        if (result) {
          newRawSignals[result.signalId] = result.rawSignal;
        }
      });
      setRawSignals(newRawSignals);
      
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
    return signal.signal_status?.status || 'UNKNOWN';
  };

  const getLegsCount = (signal: SignalStore) => {
    const signal_legs = signal.signal_legs || [];
    const entryCount = signal_legs.filter((leg: any) => leg.leg_type === 'ENTRY').length;
    const exitCount = signal_legs.filter((leg: any) => leg.leg_type === 'EXIT').length;
    return { entry: entryCount, exit: exitCount, total: signal_legs.length };
  };

  const exportToCSV = () => {
    // Convert signals to CSV format
    const headers = [
      'Signal ID',
      'Strategy ID',
      'Instrument',
      'Mode',
      'Environment',
      'Direction',
      'Position Status',
      'Entry Quantity',
      'Exit Quantity',
      'Remaining Quantity',
      'Entry Price',
      'Exit Price',
      'Gross PnL',
      'Net PnL',
      'PnL %',
      'Commission',
      'Holding Time (s)',
      'Account ID',
      'Broker Name',
      'Broker Order ID (Entry)',
      'Broker Order ID (Exit)',
      'Fund ID',
      'Entry Filled At',
      'Exit Filled At',
      'Leg Count',
      'Entry Legs',
      'Exit Legs',
      'Created At',
      'Updated At'
    ];

    const rows = signals.map(signal => {
      const signal_legs = signal.signal_legs || [];
      const entryLeg = signal_legs.find((leg: any) => leg.leg_type === 'ENTRY');
      const exitLegs = signal_legs.filter((leg: any) => leg.leg_type === 'EXIT' || leg.leg_type === 'SCALE_OUT');
      
      // Get entry data
      const entryExec = entryLeg?.execution || {};
      const entryPrice = entryExec.weighted_avg_price || '';
      const entryFilledAt = entryExec.orders?.[0]?.filled_at || '';
      const entryBrokerOrderId = entryExec.orders?.[0]?.broker_order_id || '';
      
      // Get exit data (aggregate if multiple exits)
      const exitPrice = exitLegs.length > 0 
        ? (exitLegs.reduce((sum: number, leg: any) => sum + (leg.execution?.weighted_avg_price || 0), 0) / exitLegs.length).toFixed(2)
        : '';
      const exitFilledAt = exitLegs[0]?.execution?.orders?.[0]?.filled_at || '';
      const exitBrokerOrderId = exitLegs[0]?.execution?.orders?.[0]?.broker_order_id || '';
      
      // Get account, broker, and fund IDs
      const accountId = entryLeg?.execution?.orders?.[0]?.account_id || '';
      const brokerName = entryLeg?.execution?.orders?.[0]?.broker_name || '';
      const fundId = entryLeg?.execution?.orders?.[0]?.fund_id || '';
      
      // Get leg counts
      const legsCount = getLegsCount(signal);

      return [
        signal.signal_id || '',
        signal.strategy_id || '',
        signal.instrument || '',
        signal.mode || '',
        signal.environment || '',
        signal.direction || '',
        signal.position?.status || '',
        signal.signal_status?.entry_quantity || '',
        signal.signal_status?.exit_quantity || '',
        signal.position?.remaining_quantity || '',
        entryPrice,
        exitPrice,
        signal.signal_status?.pnl?.gross || '',
        signal.signal_status?.pnl?.net || '',
        signal.signal_status?.pnl?.percent || '',
        signal.signal_status?.pnl?.commission || '',
        signal.signal_status?.pnl?.holding_seconds || '',
        accountId,
        brokerName,
        entryBrokerOrderId,
        exitBrokerOrderId,
        fundId,
        entryFilledAt,
        exitFilledAt,
        legsCount.total,
        legsCount.entry,
        legsCount.exit,
        signal.created_at || '',
        signal.updated_at || ''
      ];
    });

    // Build CSV content
    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => {
        // Escape cells containing commas, quotes, or newlines
        const cellStr = String(cell);
        if (cellStr.includes(',') || cellStr.includes('"') || cellStr.includes('\n')) {
          return `"${cellStr.replace(/"/g, '""')}"`;
        }
        return cellStr;
      }).join(','))
    ].join('\n');

    // Create blob and download
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    
    link.setAttribute('href', url);
    link.setAttribute('download', `signal_store_export_${timestamp}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
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
            <div className="flex gap-2">
              <button
                onClick={exportToCSV}
                className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 flex items-center gap-2"
                disabled={signals.length === 0}
              >
                <Download size={16} />
                Download CSV
              </button>
              <button
                onClick={() => {
                  fetchSignals();
                  setRefreshCountdown(5);
                }}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 flex items-center gap-2"
              >
              <svg width="16" height="16" viewBox="0 0 16 16" className="transform -rotate-90">
                <circle
                  cx="8"
                  cy="8"
                  r="6"
                  fill="none"
                  stroke="rgba(255,255,255,0.3)"
                  strokeWidth="2"
                />
                {[0, 1, 2, 3, 4].map((slice) => {
                  const sliceAngle = 360 / 5;
                  const startAngle = slice * sliceAngle;
                  const endAngle = (slice + 1) * sliceAngle;
                  
                  const startRad = (startAngle - 90) * Math.PI / 180;
                  const endRad = (endAngle - 90) * Math.PI / 180;
                  
                  const x1 = 8 + 6 * Math.cos(startRad);
                  const y1 = 8 + 6 * Math.sin(startRad);
                  const x2 = 8 + 6 * Math.cos(endRad);
                  const y2 = 8 + 6 * Math.sin(endRad);
                  
                  const largeArc = sliceAngle > 180 ? 1 : 0;
                  
                  return (
                    <path
                      key={slice}
                      d={`M 8 8 L ${x1} ${y1} A 6 6 0 ${largeArc} 1 ${x2} ${y2} Z`}
                      fill="white"
                      opacity={refreshCountdown > slice ? 0.9 : 0.2}
                      className="transition-opacity duration-200"
                    />
                  );
                })}
              </svg>
              Refresh
            </button>
            </div>
          </div>

          <div className="overflow-x-auto bg-gray-800 rounded-lg shadow">
            <table className="min-w-full divide-y divide-gray-700">
              <thead className="bg-gray-900/50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase w-8"></th>
                  <th className="px-2 py-3 text-left text-xs font-medium text-gray-400 uppercase w-24">Signal ID</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Strategy</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Instrument</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Mode</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Environment</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Position</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase" colSpan={2}>PnL</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Legs</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Created</th>
                </tr>
                <tr>
                  <th className="px-4 py-1 text-left"></th>
                  <th className="px-2 py-1 text-left"></th>
                  <th className="px-4 py-1 text-left"></th>
                  <th className="px-4 py-1 text-left"></th>
                  <th className="px-4 py-1 text-left"></th>
                  <th className="px-4 py-1 text-left"></th>
                  <th className="px-4 py-1 text-left"></th>
                  <th className="px-2 py-1 text-left text-xs font-medium text-gray-500 uppercase">Realized</th>
                  <th className="px-2 py-1 text-left text-xs font-medium text-gray-500 uppercase">Unrealized</th>
                  <th className="px-4 py-1 text-left"></th>
                  <th className="px-4 py-1 text-left"></th>
                </tr>
              </thead>
              <tbody className="bg-gray-800 divide-y divide-gray-700">
                {signals.length === 0 ? (
                  <tr>
                    <td colSpan={11} className="px-4 py-8 text-center text-gray-400">
                      No signals found in signal store
                    </td>
                  </tr>
                ) : (
                  signals.map((signal) => {
                    const legsCount = getLegsCount(signal);
                    const entryQty = signal.signal_status?.entry_quantity || 0;
                    const exitQty = signal.signal_status?.exit_quantity || 0;
                    const remainingQty = signal.signal_status?.remaining_quantity || 0;
                    const isExpanded = expandedSignalId === signal._id;
                    const signal_legs = signal.signal_legs || [];                  
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
                          <td className="px-2 py-3 text-sm font-mono text-gray-300" title={signal.signal_id}>
                            ...{signal.signal_id.slice(-6)}
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-300">{signal.strategy_id}</td>
                          <td className="px-4 py-3 text-sm text-gray-200">{signal.instrument}</td>
                          <td className="px-4 py-3 text-sm font-mono text-gray-300">{signal.mode || 'N/A'}</td>
                          <td className="px-4 py-3 text-sm">
                            <span
                              className={`px-2 py-1 rounded text-xs ${
                                signal.environment === 'live'
                                  ? 'bg-green-900/30 text-green-400'
                                  : signal.environment === 'staging'
                                  ? 'bg-gray-700 text-gray-300'
                                  : 'bg-gray-800 text-gray-400'
                              }`}
                            >
                              {signal.environment || 'N/A'}
                            </span>
                          </td>
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
                          <td className="px-2 py-3 text-sm">
                            {(() => {
                              const pnl = signal.signal_status?.pnl?.net;
                              if (pnl === undefined || pnl === null) return <span className="text-gray-500">-</span>;
                              const pnlClass = pnl >= 0 ? 'text-green-400' : 'text-red-400';
                              return <span className={pnlClass}>${pnl.toFixed(2)}</span>;
                            })()}
                          </td>
                          <td className="px-2 py-3 text-xs text-gray-500">
                            coming soon...
                          </td>
                          <td className="px-4 py-3 text-xs text-gray-400">
                            {legsCount.entry} ENTRY + {legsCount.exit} EXIT
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-300">{formatTimestamp(signal.created_at)}</td>
                        </tr>
                        
                        {/* Expanded Legs Section */}
                        {isExpanded && signal_legs.length > 0 && (
                          <tr>
                            <td colSpan={11} className="p-0 bg-gray-850">
                              <div className="p-4 space-y-2 overflow-visible">
                                {/* Header with Signal Dict Toggle */}
                                <div className="flex items-center justify-between mb-3">
                                  <div>
                                    <p className="text-xs font-mono text-gray-400 mb-2">Signal ID: {signal.signal_id}</p>
                                    <h4 className="text-sm font-semibold text-gray-300">Signal Legs ({signal_legs.length})</h4>
                                  </div>
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
                                
                                {signal_legs.map((leg: any, legIdx: number) => {
                                  const legId = `${signal._id}-${legIdx}`;
                                  const isLegExpanded = expandedLegId === legId;
                                  const cerebro = leg.cerebro || {};
                                  const cerebroStatus = cerebro.status || 'PENDING';
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
                                            cerebroStatus === 'APPROVED' ? 'bg-green-900/30 text-green-400' :
                                            cerebroStatus === 'REJECTED' ? 'bg-red-900/30 text-red-400' :
                                            'bg-yellow-900/30 text-yellow-400'
                                          }`}>
                                            {cerebroStatus}
                                          </span>
                                          <div className="flex items-center gap-1.5">
                                            <StatusDot status={serviceStatus.ingestion.status} tooltip={serviceStatus.ingestion.tooltip} />
                                            <StatusDot status={serviceStatus.cerebro.status} tooltip={serviceStatus.cerebro.tooltip} />
                                            <StatusDot status={serviceStatus.execution.status} tooltip={serviceStatus.execution.tooltip} />
                                          </div>
                                          {cerebro.reason && (
                                            <span className="text-xs text-gray-400 truncate max-w-md">
                                              {cerebro.reason}
                                            </span>
                                          )}
                                        </div>
                                      </div>
                                      
                                      {/* Leg Expanded Content */}
                                      {isLegExpanded && (
                                        <div className="p-4 bg-gray-800 space-y-4">
                                          {/* Leg ID */}
                                          <div className="text-sm">
                                            <span className="text-gray-500">Leg ID:</span>{' '}
                                            <span className="text-white font-mono">{legId}</span>
                                          </div>
                                          
                                          {/* Quantities Summary - Top Left */}
                                          <div className="flex gap-6 text-sm">
                                            <div>
                                              <span className="text-gray-500">Raw Quantity:</span>{' '}
                                              <span className="text-white font-semibold">
                                                {leg.raw?.quantity || leg.raw?.signal_legs?.[0]?.quantity || 'N/A'}
                                              </span>
                                            </div>
                                            <div>
                                              <span className="text-gray-500">Cerebro Quantity:</span>{' '}
                                              <span className="text-white font-semibold">
                                                {cerebro.quantity !== undefined ? cerebro.quantity : (cerebro.created_orders?.[0]?.quantity || 'N/A')}
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
                                                      {leg.processing_timestamps?.cerebro_processed ? formatDate(leg.processing_timestamps.cerebro_processed) : (cerebro.timestamp ? formatDate(cerebro.timestamp) : 'N/A')}
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
                                              <h5 className="text-xs font-semibold text-gray-400">Raw Signal (from trading_signals_raw)</h5>
                                              <div className="bg-gray-900 p-3 rounded text-xs font-mono space-y-1 h-full overflow-auto max-h-96">
                                                {rawSignals[signal.signal_id] ? (
                                                  <pre className="text-gray-300 whitespace-pre-wrap">
                                                    {JSON.stringify(rawSignals[signal.signal_id], null, 2)}
                                                  </pre>
                                                ) : (
                                                  <div className="text-gray-500 italic">Loading raw signal from trading_signals_raw...</div>
                                                )}
                                              </div>
                                            </div>

                                            {/* Cerebro Decision with Math */}
                                            <div className="space-y-2">
                                              <h5 className="text-xs font-semibold text-gray-400">Cerebro Decision</h5>
                                              <div className="bg-gray-900 p-3 rounded text-xs font-mono space-y-3 h-full overflow-auto max-h-96 relative">
                                                {/* Copy Button */}
                                                <button
                                                  onClick={() => {
                                                    const boxId = `cerebro-${signal._id}-${legIdx}`;
                                                    let text = `Signal ID: ${signal.signal_id}\nLeg ID: ${leg.leg_id}\n\nStatus: ${cerebro.status || 'N/A'}\nReason: ${cerebro.reason || 'N/A'}\nTimestamp: ${cerebro.timestamp ? formatDate(cerebro.timestamp) : 'N/A'}`;
                                                    if (cerebro.quantity !== undefined) {
                                                      text += `\nQuantity: ${cerebro.quantity}`;
                                                    }
                                                    if (cerebro.created_orders && cerebro.created_orders.length > 0) {
                                                      text += '\n\nCreated Orders:\n';
                                                      cerebro.created_orders.forEach((order: any, idx: number) => {
                                                        text += `\nOrder ${idx + 1}:\n`;
                                                        text += `  Broker: ${order.broker || 'N/A'}\n`;
                                                        text += `  Account: ${order.account_id || 'N/A'}\n`;
                                                        text += `  Fund: ${order.fund_id || 'N/A'}\n`;
                                                        text += `  Action: ${order.action || 'N/A'}\n`;
                                                        text += `  Instrument: ${order.instrument || 'N/A'}\n`;
                                                        text += `  Quantity: ${order.quantity || 0}\n`;
                                                        text += `  Price: $${order.price?.toFixed(2) || 'N/A'}\n`;
                                                        text += `  Order Type: ${order.order_type || 'N/A'}\n`;
                                                        if (order.allocated_capital) {
                                                          text += `  Allocated Capital: $${order.allocated_capital.toLocaleString()}\n`;
                                                        }
                                                        if (order.margin_required) {
                                                          text += `  Margin Required: $${order.margin_required.toLocaleString()}\n`;
                                                        }
                                                      });
                                                    }
                                                    if (cerebro.math) {
                                                      text += '\n\nCalculation:\n' + cerebro.math;
                                                    }
                                                    copyToClipboard(text, boxId);
                                                  }}
                                                  className="absolute top-2 right-2 p-1.5 bg-gray-800 hover:bg-gray-700 rounded transition-colors"
                                                  title="Copy to clipboard"
                                                >
                                                  {copiedBox === `cerebro-${signal._id}-${legIdx}` ? (
                                                    <Check className="h-3.5 w-3.5 text-green-400" />
                                                  ) : (
                                                    <Copy className="h-3.5 w-3.5 text-gray-400" />
                                                  )}
                                                </button>

                                                {/* Cerebro Details */}
                                                <div className="space-y-1">
                                                  <div><span className="text-gray-500">Signal ID:</span> <span className="text-white text-xs">{signal.signal_id}</span></div>
                                                  <div><span className="text-gray-500">Leg ID:</span> <span className="text-white text-xs">{leg.leg_id}</span></div>
                                                  <div className="border-t border-gray-800 my-2"></div>
                                                  <div><span className="text-gray-500">Status:</span> <span className="text-white">{cerebro.status || 'N/A'}</span></div>
                                                  <div><span className="text-gray-500">Reason:</span> <span className="text-white">{cerebro.reason || 'N/A'}</span></div>
                                                  {cerebro.timestamp && (
                                                    <div><span className="text-gray-500">Timestamp:</span> <span className="text-white">{formatDate(cerebro.timestamp)}</span></div>
                                                  )}
                                                  {cerebro.quantity !== undefined && (
                                                    <div><span className="text-gray-500">Quantity:</span> <span className="text-white">{cerebro.quantity}</span></div>
                                                  )}
                                                </div>

                                                {/* Orders Created by Cerebro */}
                                                {cerebro.created_orders && cerebro.created_orders.length > 0 && (
                                                  <div className="border-t border-gray-700 pt-3">
                                                    <div className="text-gray-500 font-semibold mb-2">Orders Created ({cerebro.created_orders.length}):</div>
                                                    <div className="ml-3 space-y-2">
                                                      {cerebro.created_orders.map((order: any, orderIdx: number) => (
                                                        <div key={orderIdx} className="bg-gray-950 p-2 rounded text-xs">
                                                          <div className="grid grid-cols-2 gap-x-3 gap-y-1">
                                                            <div><span className="text-gray-500">Fund:</span> <span className="text-white">{order.fund_id || 'N/A'}</span></div>
                                                            <div><span className="text-gray-500">Account:</span> <span className="text-white">{order.account_id || 'N/A'}</span></div>
                                                            <div><span className="text-gray-500">Broker:</span> <span className="text-white">{order.broker || 'N/A'}</span></div>
                                                            <div><span className="text-gray-500">Data Source:</span> <span className="text-white">{order.data_source || 'N/A'}</span></div>
                                                            <div><span className="text-gray-500">Action:</span> <span className="text-white">{order.action || 'N/A'}</span></div>
                                                            <div><span className="text-gray-500">Instrument:</span> <span className="text-white">{order.instrument || 'N/A'}</span></div>
                                                            <div><span className="text-gray-500">Quantity:</span> <span className="text-white">{order.quantity || 0}</span></div>
                                                            <div><span className="text-gray-500">Price:</span> <span className="text-white">${order.price?.toFixed(2) || 'N/A'}</span></div>
                                                            <div><span className="text-gray-500">Order Type:</span> <span className="text-white">{order.order_type || 'N/A'}</span></div>
                                                            <div><span className="text-gray-500">Direction:</span> <span className="text-white">{order.direction || 'N/A'}</span></div>
                                                            {order.allocated_capital && (
                                                              <div className="col-span-2">
                                                                <span className="text-gray-500">Allocated Capital:</span>{' '}
                                                                <span className="text-white">${order.allocated_capital.toLocaleString()}</span>
                                                              </div>
                                                            )}
                                                            {order.margin_required && (
                                                              <div className="col-span-2">
                                                                <span className="text-gray-500">Margin Required:</span>{' '}
                                                                <span className="text-white">${order.margin_required.toLocaleString()}</span>
                                                              </div>
                                                            )}
                                                          </div>
                                                        </div>
                                                      ))}
                                                    </div>
                                                  </div>
                                                )}

                                                {/* Execution Orders (after order is sent) */}
                                                {leg.execution?.orders && leg.execution.orders.length > 0 && (
                                                  <div className="border-t border-gray-700 pt-3">
                                                    <div className="text-gray-500 font-semibold mb-2">Execution Results ({leg.execution.orders.length}):</div>
                                                    <div className="ml-3 space-y-2">
                                                      {leg.execution.orders.map((order: any, orderIdx: number) => (
                                                        <div key={orderIdx} className="bg-gray-950 p-2 rounded text-xs">
                                                          <div className="grid grid-cols-2 gap-x-3 gap-y-1">
                                                            <div><span className="text-gray-500">Fund/Account:</span> <span className="text-white">{order.fund_id}/{order.account_id}</span></div>
                                                            <div><span className="text-gray-500">Exec Broker:</span> <span className="text-white">{order.broker || order.broker_name || 'N/A'}</span></div>
                                                            <div><span className="text-gray-500">Data Source:</span> <span className="text-white">{order.data_source || 'N/A'}</span></div>
                                                            <div><span className="text-gray-500">Price Broker:</span> <span className="text-white">{order.price_broker || 'N/A'}</span></div>
                                                            <div><span className="text-gray-500">Qty Filled:</span> <span className="text-white">{order.quantity_filled || order.quantity}</span></div>
                                                            <div><span className="text-gray-500">Avg Price:</span> <span className="text-white">${(order.avg_fill_price || order.price)?.toFixed(2)}</span></div>
                                                            {order.broker_order_id && (
                                                              <div className="col-span-2">
                                                                <span className="text-gray-500">Broker Order ID:</span>{' '}
                                                                <span className="text-blue-400 font-mono text-[10px]">{order.broker_order_id}</span>
                                                              </div>
                                                            )}
                                                            {order.filled_at && (
                                                              <div className="col-span-2">
                                                                <span className="text-gray-500">Filled At:</span>{' '}
                                                                <span className="text-white">{formatDate(order.filled_at)}</span>
                                                              </div>
                                                            )}
                                                          </div>
                                                        </div>
                                                      ))}
                                                    </div>
                                                  </div>
                                                )}

                                                {/* Calculation Breakdown */}
                                                {cerebro.math && (
                                                  <div className="border-t border-gray-700 pt-3">
                                                    <div className="text-gray-500 font-semibold mb-2">Calculation:</div>
                                                    <pre className="text-gray-300 whitespace-pre-wrap">
                                                      {cerebro.math}
                                                    </pre>
                                                  </div>
                                                )}
                                              </div>
                                            </div>

                                            {/* Execution Details */}
                                            <div className="space-y-2">
                                              <h5 className="text-xs font-semibold text-gray-400">Execution Results</h5>
                                              {leg.execution ? (
                                                <div className="bg-gray-900 p-3 rounded text-xs font-mono space-y-1 h-full relative">
                                                  {/* Copy Button */}
                                                  <button
                                                    onClick={() => {
                                                      const boxId = `execution-${signal._id}-${legIdx}`;
                                                      let text = `Signal ID: ${signal.signal_id}\nLeg ID: ${leg.leg_id}\n\nStatus: ${leg.execution.status || 'N/A'}`;
                                                      if (leg.execution.status === 'ERROR') {
                                                        if (leg.execution.error_reason) text += `\nError: ${leg.execution.error_reason}`;
                                                      }
                                                      if (leg.execution.status === 'REJECTED') {
                                                        if (leg.execution.rejection_reason) text += `\nRejection Reason: ${leg.execution.rejection_reason}`;
                                                        if (leg.execution.rejected_at) text += `\nRejected At: ${new Date(leg.execution.rejected_at).toLocaleString()}`;
                                                      }
                                                      text += `\nQuantity Filled: ${leg.execution.total_quantity_filled || leg.execution.filled_quantity || 0}`;
                                                      if (leg.execution.weighted_avg_price) text += `\nAvg Fill Price: $${leg.execution.weighted_avg_price.toFixed(2)}`;
                                                      if (leg.execution.total_cost_basis) text += `\nTotal Cost: $${leg.execution.total_cost_basis.toFixed(2)}`;
                                                      if (leg.execution.total_proceeds) text += `\nTotal Proceeds: $${leg.execution.total_proceeds.toFixed(2)}`;
                                                      if (leg.execution.completed_at) text += `\nCompleted At: ${new Date(leg.execution.completed_at).toLocaleString()}`;
                                                      if (leg.execution.orders && leg.execution.orders.length > 0) {
                                                        text += `\n\nOrders (${leg.execution.orders.length}):`;
                                                        leg.execution.orders.forEach((order: any, idx: number) => {
                                                          text += `\n\nOrder ${idx + 1}:`;
                                                          text += `\n  Order ID: ${order.order_id}`;
                                                          if (order.broker_order_id) text += `\n  Broker Order ID: ${order.broker_order_id}`;
                                                          if (order.fund_id) text += `\n  Fund: ${order.fund_id}`;
                                                          if (order.account_id) text += `\n  Account: ${order.account_id}`;
                                                          if (order.broker) text += `\n  Broker: ${order.broker}`;
                                                          if (order.data_source) text += `\n  Data Source: ${order.data_source}`;
                                                          if (order.price_broker) text += `\n  Price Broker: ${order.price_broker}`;
                                                          if (order.quantity_filled) text += `\n  Filled: ${order.quantity_filled}${order.quantity_requested ? `/${order.quantity_requested}` : ''}`;
                                                          if (order.avg_fill_price) text += ` @ $${order.avg_fill_price.toFixed(2)}`;
                                                          if (order.filled_at) text += `\n  Filled At: ${new Date(order.filled_at).toLocaleString()}`;
                                                        });
                                                      }
                                                      copyToClipboard(text, boxId);
                                                    }}
                                                    className="absolute top-2 right-2 p-1.5 bg-gray-800 hover:bg-gray-700 rounded transition-colors z-10"
                                                    title="Copy to clipboard"
                                                  >
                                                    {copiedBox === `execution-${signal._id}-${legIdx}` ? (
                                                      <Check className="h-3.5 w-3.5 text-green-400" />
                                                    ) : (
                                                      <Copy className="h-3.5 w-3.5 text-gray-400" />
                                                    )}
                                                  </button>

                                                  <div><span className="text-gray-500">Signal ID:</span> <span className="text-white text-xs">{signal.signal_id}</span></div>
                                                  <div><span className="text-gray-500">Leg ID:</span> <span className="text-white text-xs">{leg.leg_id}</span></div>
                                                  <div className="border-t border-gray-800 my-2"></div>
                                                  <div><span className="text-gray-500">Status:</span> <span className="text-white">{leg.execution.status || 'N/A'}</span></div>
                                                  
                                                  {/* Error Details */}
                                                  {leg.execution.status === 'ERROR' && leg.execution.error_reason && (
                                                    <div><span className="text-gray-500">Error:</span> <span className="text-red-400">{leg.execution.error_reason}</span></div>
                                                  )}
                                                  
                                                  {/* Rejection Details */}
                                                  {leg.execution.status === 'REJECTED' && leg.execution.rejection_reason && (
                                                    <div><span className="text-gray-500">Rejection Reason:</span> <span className="text-red-400">{leg.execution.rejection_reason}</span></div>
                                                  )}
                                                  {leg.execution.status === 'REJECTED' && leg.execution.rejected_at && (
                                                    <div><span className="text-gray-500">Rejected At:</span> <span className="text-white">{new Date(leg.execution.rejected_at).toLocaleString()}</span></div>
                                                  )}
                                                  
                                                  {/* Fill Details */}
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
                                                  
                                                  {/* Execution Timestamps */}
                                                  {leg.execution.completed_at && (
                                                    <div><span className="text-gray-500">Completed At:</span> <span className="text-white">{new Date(leg.execution.completed_at).toLocaleString()}</span></div>
                                                  )}
                                                  
                                                  {/* Position Information (for EXIT signals) */}
                                                  {leg.execution.final_position !== undefined && (
                                                    <div className="mt-2 pt-2 border-t border-gray-800">
                                                      <div><span className="text-gray-500">Final Position:</span> <span className="text-white">{leg.execution.final_position}</span></div>
                                                      {leg.execution.target_position !== undefined && (
                                                        <div><span className="text-gray-500">Target Position:</span> <span className="text-white">{leg.execution.target_position}</span></div>
                                                      )}
                                                      {leg.execution.needs_manual_intervention !== undefined && (
                                                        <div>
                                                          <span className="text-gray-500">Needs Manual Intervention:</span> 
                                                          <span className={leg.execution.needs_manual_intervention ? 'text-red-400' : 'text-green-400'}>
                                                            {' '}{leg.execution.needs_manual_intervention ? 'YES' : 'NO'}
                                                          </span>
                                                        </div>
                                                      )}
                                                    </div>
                                                  )}
                                                  
                                                  {/* Reconciliation Attempts (for EXIT signals) */}
                                                  {leg.execution.reconciliation_attempts && leg.execution.reconciliation_attempts.length > 0 && (
                                                    <div className="mt-2 pt-2 border-t border-gray-800">
                                                      <div className="text-gray-400 font-semibold mb-1">Reconciliation Attempts ({leg.execution.reconciliation_attempts.length})</div>
                                                      {leg.execution.reconciliation_attempts.map((attempt: any, idx: number) => (
                                                        <div key={idx} className="ml-2 mb-2 p-2 bg-gray-950 rounded">
                                                          <div><span className="text-gray-500">Attempt:</span> <span className="text-white">{attempt.attempt}</span></div>
                                                          <div><span className="text-gray-500">Timestamp:</span> <span className="text-white">{new Date(attempt.timestamp).toLocaleString()}</span></div>
                                                          {attempt.position_before !== undefined && (
                                                            <div><span className="text-gray-500">Position Before:</span> <span className="text-white">{attempt.position_before}</span></div>
                                                          )}
                                                          {attempt.position_after !== undefined && (
                                                            <div><span className="text-gray-500">Position After:</span> <span className="text-white">{attempt.position_after}</span></div>
                                                          )}
                                                          {attempt.exit_results && attempt.exit_results.length > 0 && (
                                                            <div className="mt-1">
                                                              <div className="text-gray-500">Exit Results:</div>
                                                              {attempt.exit_results.map((result: any, ridx: number) => (
                                                                <div key={ridx} className="ml-2 text-xs">
                                                                  • {result.success ? '✓' : '✗'} Qty: {result.quantity} @ ${result.avg_price} ({result.status})
                                                                </div>
                                                              ))}
                                                            </div>
                                                          )}
                                                        </div>
                                                      ))}
                                                    </div>
                                                  )}
                                                  
                                                  {/* Orders (for ENTRY signals) */}
                                                  {leg.execution.orders && leg.execution.orders.length > 0 && (
                                                    <div className="mt-2 pt-2 border-t border-gray-800">
                                                      <span className="text-gray-400 font-semibold">Orders ({leg.execution.orders.length}):</span>
                                                      <div className="ml-2 mt-1 space-y-2">
                                                        {leg.execution.orders.map((order: any, orderIdx: number) => (
                                                          <div key={orderIdx} className="bg-gray-950 p-2 rounded">
                                                            <div><span className="text-gray-500">Order ID:</span> <span className="text-white">{order.order_id}</span></div>
                                                            <div><span className="text-gray-500">Broker Order ID:</span> <span className="text-white">{order.broker_order_id}</span></div>
                                                            <div><span className="text-gray-500">Fund/Account:</span> <span className="text-white">{order.fund_id}/{order.account_id}</span></div>
                                                            {order.broker && (
                                                              <div><span className="text-gray-500">Broker:</span> <span className="text-white">{order.broker}</span></div>
                                                            )}
                                                            {order.data_source && (
                                                              <div><span className="text-gray-500">Data Source:</span> <span className="text-white">{order.data_source}</span></div>
                                                            )}
                                                            {order.price_broker && (
                                                              <div><span className="text-gray-500">Price Broker:</span> <span className="text-white">{order.price_broker}</span></div>
                                                            )}
                                                            <div><span className="text-gray-500">Filled:</span> <span className="text-white">{order.quantity_filled}/{order.quantity_requested} @ ${order.avg_fill_price?.toFixed(2)}</span></div>
                                                            {order.filled_at && (
                                                              <div><span className="text-gray-500">Filled At:</span> <span className="text-white">{new Date(order.filled_at).toLocaleString()}</span></div>
                                                            )}
                                                            {order.fills && order.fills.length > 0 && (
                                                              <div className="mt-1">
                                                                <div className="text-gray-500 text-xs">Fills ({order.fills.length}):</div>
                                                                {order.fills.map((fill: any, fidx: number) => (
                                                                  <div key={fidx} className="ml-2 text-xs text-gray-400">
                                                                    • {fill.quantity} @ ${fill.price} on {fill.exchange}
                                                                  </div>
                                                                ))}
                                                              </div>
                                                            )}
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
