import { useState, useEffect } from 'react';
import { api } from '../../services/api';

interface SignalStatus {
  _id: string;
  signal_id: string;
  base_signal_id?: string;
  strategy_id: string;
  instrument: string;
  environment?: string;
  mode?: string;
  status: string;
  position_status?: string;
  entry_quantity: number;
  exit_quantity: number;
  remaining_quantity: number;
  pnl?: {
    net: number;
    percent?: number;
  };
  opened_at?: string;
  closed_at?: string;
  created_at: string;
  updated_at: string;
  entry_legs_count?: number;
  exit_legs_count?: number;
  exit_legs?: any[];
  decision_status?: string;
  processing_complete?: boolean;
  raw_document?: any;
  [key: string]: any;
}

export default function SignalStatusTab() {
  const [signals, setSignals] = useState<SignalStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSignals();
    // Set up polling every 5 seconds
    const interval = setInterval(fetchSignals, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchSignals = async () => {
    try {
      setLoading(true);
      const data = await api.getSignalStatus({ limit: 100 });
      
      // Sort signals: PENDING > OPEN > PARTIAL > CLOSED, then by entry time (latest first)
      const sorted = (data.signals || []).sort((a: SignalStatus, b: SignalStatus) => {
        const statusPriority = (status: string) => {
          if (status === 'PENDING') return 4;
          if (status === 'OPEN') return 3;
          if (status === 'PARTIAL') return 2;
          return 1; // CLOSED, etc.
        };

        const priorityA = statusPriority(a.status || a.position_status || '');
        const priorityB = statusPriority(b.status || b.position_status || '');

        if (priorityA !== priorityB) {
          return priorityB - priorityA;
        }

        const timeA = a.opened_at ? new Date(a.opened_at).getTime() : 0;
        const timeB = b.opened_at ? new Date(b.opened_at).getTime() : 0;
        return timeB - timeA;
      });

      setSignals(sorted);
      setError(null);
    } catch (err: any) {
      console.error('Error fetching signal status:', err);
      setError(err.message || 'Failed to fetch signal status');
    } finally {
      setLoading(false);
    }
  };

  const formatTimestamp = (timestamp: string | null) => {
    if (!timestamp) return '-';
    try {
      return new Date(timestamp).toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return timestamp;
    }
  };

  if (loading && signals.length === 0) {
    return (
      <div className="flex justify-center items-center p-12">
        <div className="inline-block animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mb-3"></div>
        <p className="text-gray-400 ml-4">Loading signals...</p>
      </div>
    );
  }

  if (error && signals.length === 0) {
    return (
      <div className="bg-red-900/20 border border-red-700 rounded-lg p-4 m-4">
        <p className="text-red-400">Error: {error}</p>
        <button
          onClick={fetchSignals}
          className="mt-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold text-white">
          Trading Signals ({signals.length})
        </h3>
        <button
          onClick={fetchSignals}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors"
        >
          Refresh
        </button>
      </div>

      {signals.length === 0 ? (
        <div className="text-center py-12 bg-gray-800 rounded-lg">
          <p className="text-gray-400">No trading signals found</p>
        </div>
      ) : (
        <div className="overflow-x-auto bg-gray-800 rounded-lg">
          <table className="w-full">
            <thead className="bg-gray-900/50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Signal ID</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Instrument</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Strategy</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Mode</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Position</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Entry Time</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Exit Time</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">P&L</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Legs</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {signals.map((signal) => {
                const status = signal.status || signal.position_status || 'UNKNOWN';
                const exitLegsCount = signal.exit_legs_count || signal.exit_legs?.length || 0;
                
                return (
                  <tr key={signal._id} className="hover:bg-gray-700/50 transition-colors">
                    <td className="px-4 py-3">
                      <span className="px-2 py-1 bg-blue-900/30 text-blue-400 rounded text-xs font-medium font-mono">
                        {signal.signal_id}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-200 font-semibold">{signal.instrument}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-1 bg-purple-900/30 text-purple-400 rounded text-xs font-medium">
                        {signal.strategy_id}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-1 bg-purple-900/30 text-purple-400 rounded text-xs font-medium uppercase">
                        {signal.mode || 'N/A'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-1 rounded text-xs font-medium ${
                          status === 'OPEN'
                            ? 'bg-green-900/30 text-green-400'
                            : status === 'CLOSED'
                            ? 'bg-gray-700 text-gray-300'
                            : status === 'PARTIAL'
                            ? 'bg-yellow-900/30 text-yellow-400'
                            : 'bg-yellow-900/30 text-yellow-400'
                        }`}
                      >
                        {status}
                        {status === 'PARTIAL' && signal.remaining_quantity !== undefined && (
                          <span className="ml-1 text-xs">({signal.remaining_quantity} left)</span>
                        )}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {(() => {
                        const entryQty = signal.entry_quantity || 0;
                        const exitQty = signal.exit_quantity || 0;
                        const remainingQty = signal.remaining_quantity || 0;

                        if (entryQty === 0) {
                          return <span className="text-gray-500 text-xs">-</span>;
                        }

                        const filledPercent = (exitQty / entryQty) * 100;
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
                    <td className="px-4 py-3 text-sm text-gray-300">{formatTimestamp(signal.opened_at || null)}</td>
                    <td className="px-4 py-3 text-sm text-gray-300">{formatTimestamp(signal.closed_at || null)}</td>
                    <td className="px-4 py-3">
                      {signal.pnl && signal.pnl.net !== undefined ? (
                        <span className={signal.pnl.net >= 0 ? 'text-green-400 font-semibold' : 'text-red-400 font-semibold'}>
                          ${signal.pnl.net.toFixed(2)}
                        </span>
                      ) : (
                        <span className="text-gray-500">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-400">
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
  );
}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
