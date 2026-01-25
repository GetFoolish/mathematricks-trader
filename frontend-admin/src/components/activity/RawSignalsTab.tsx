import { useState, useEffect } from 'react';
import { api } from '../../services/api';
import { StatusDot, getServiceStatusForRawSignal } from './StatusIndicators';

interface RawSignal {
  _id: string;
  signalID: string;
  strategy_name: string;
  signal_type?: string;
  environment?: string;
  mode?: string;
  received_at: string;
  created_at?: string;
  [key: string]: any;
}

export default function RawSignalsTab() {
  const [rawSignals, setRawSignals] = useState<RawSignal[]>([]);
  const [signalStore, setSignalStore] = useState<any[]>([]);
  const [selectedSignal, setSelectedSignal] = useState<RawSignal | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshCountdown, setRefreshCountdown] = useState(5);

  useEffect(() => {
    fetchData();
    
    // Poll every 5 seconds for updates
    const interval = setInterval(() => {
      fetchData();
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

  const fetchData = async () => {
    try {
      // Don't show loading spinner on refresh, only on initial load
      const [rawData, storeData] = await Promise.all([
        api.getRawSignals({ limit: 100 }),
        api.getSignalStore({ limit: 100 })
      ]);
      setRawSignals(rawData.raw_signals || []);
      setSignalStore(storeData.signals || []);
      setError(null);
    } catch (err: any) {
      console.error('Error fetching data:', err);
      setError(err.message || 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  };

  const getSignalStatus = (signalID: string) => {
    // Check if signal exists in signal_store by matching signal_id or base_signal_id
    const found = signalStore.find(s => 
      s.signal_id === signalID || s.base_signal_id === signalID
    );
    return found ? 'sent_to_cerebro' : 'pending';
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

  if (loading) {
    return <div className="flex justify-center items-center p-8 text-gray-400">Loading...</div>;
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-700 rounded-lg p-4 m-4">
        <p className="text-red-400">Error: {error}</p>
        <button
          onClick={fetchData}
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
      <div className={`${selectedSignal ? 'w-1/2' : 'w-full'} overflow-auto`}>
        <div className="p-4">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold text-white">Raw Signals ({rawSignals.length})</h2>
            <button
              onClick={() => {
                fetchData();
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

          <div className="overflow-x-auto bg-gray-800 rounded-lg shadow">
            <table className="min-w-full divide-y divide-gray-700">
              <thead className="bg-gray-900/50">
                <tr>
                  <th className="px-2 py-3 text-left text-xs font-medium text-gray-400 uppercase w-24">Signal ID</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Strategy</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Type</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Mode</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Environment</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Received At</th>
                </tr>
              </thead>
              <tbody className="bg-gray-800 divide-y divide-gray-700">
                {rawSignals.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                      No raw signals found
                    </td>
                  </tr>
                ) : (
                  rawSignals.map((signal) => (
                    <tr
                      key={signal._id}
                      onClick={() => setSelectedSignal(signal)}
                      className={`cursor-pointer hover:bg-gray-700/50 transition-colors ${
                        selectedSignal?._id === signal._id ? 'bg-gray-700' : ''
                      }`}
                    >
                      <td className="px-2 py-3 text-sm font-mono text-gray-300" title={signal.signalID}>
                        ...{signal.signalID.slice(-6)}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-300">{signal.strategy_name || 'N/A'}</td>
                      <td className="px-4 py-3 text-sm">
                        <span
                          className={`px-2 py-1 rounded text-xs ${
                            signal.signal_type === 'ENTRY'
                              ? 'bg-green-900/30 text-green-400'
                              : signal.signal_type === 'EXIT'
                              ? 'bg-red-900/30 text-red-400'
                              : 'bg-gray-700 text-gray-300'
                          }`}
                        >
                          {signal.signal_type || 'N/A'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm font-mono text-gray-300">{signal.mode || 'N/A'}</td>
                      <td className="px-4 py-3 text-sm text-gray-300">{signal.environment || 'N/A'}</td>
                      <td className="px-4 py-3">
                        {(() => {
                          const serviceStatus = getServiceStatusForRawSignal(signal, signalStore);
                          return (
                            <div className="flex items-center gap-1.5">
                              <StatusDot status={serviceStatus.ingestion.status} tooltip={serviceStatus.ingestion.tooltip} />
                              <StatusDot status={serviceStatus.cerebro.status} tooltip={serviceStatus.cerebro.tooltip} />
                              <StatusDot status={serviceStatus.execution.status} tooltip={serviceStatus.execution.tooltip} />
                            </div>
                          );
                        })()}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-300">{formatTimestamp(signal.received_at || signal.created_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Detail View */}
      {selectedSignal && (
        <div className="w-1/2 border-l border-gray-700 overflow-auto bg-gray-900">
          <div className="p-4">
            <div className="flex justify-between items-center mb-4">
              <div>
                <h3 className="text-lg font-bold text-white">Signal Details</h3>
                <p className="text-xs font-mono text-gray-400 mt-1">{selectedSignal.signalID}</p>
              </div>
              <button
                onClick={() => setSelectedSignal(null)}
                className="text-gray-400 hover:text-gray-200"
              >
                ✕
              </button>
            </div>
            <pre className="bg-gray-900 text-green-400 p-4 rounded-lg overflow-auto text-xs font-mono">
              {JSON.stringify(selectedSignal, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
