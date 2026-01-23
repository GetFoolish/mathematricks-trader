import { useState, useEffect } from 'react';
import { api } from '../../services/api';

interface SignalStore {
  _id: string;
  signal_id: string;
  base_signal_id: string;
  strategy_id: string;
  instrument: string;
  environment?: string;
  mode?: string;
  legs?: any[];
  position?: any;
  created_at: string;
  updated_at: string;
  processing_complete?: boolean;
  [key: string]: any;
}

export default function SignalStoreTab() {
  const [signals, setSignals] = useState<SignalStore[]>([]);
  const [selectedSignal, setSelectedSignal] = useState<SignalStore | null>(null);
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
    return <div className="flex justify-center items-center p-8">Loading...</div>;
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 m-4">
        <p className="text-red-800">Error: {error}</p>
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
    <div className="flex h-full">
      {/* Table View */}
      <div className={`${selectedSignal ? 'w-1/2' : 'w-full'} overflow-auto`}>
        <div className="p-4">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold">Signal Store ({signals.length})</h2>
            <button
              onClick={fetchSignals}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              Refresh
            </button>
          </div>

          <div className="overflow-x-auto bg-white rounded-lg shadow">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Signal ID</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Strategy</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Instrument</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mode</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Position</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Legs</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {signals.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-gray-500">
                      No signals found in signal store
                    </td>
                  </tr>
                ) : (
                  signals.map((signal) => {
                    const legsCount = getLegsCount(signal);
                    const positionStatus = getPositionStatus(signal);

                    return (
                      <tr
                        key={signal._id}
                        onClick={() => setSelectedSignal(signal)}
                        className={`cursor-pointer hover:bg-blue-50 ${
                          selectedSignal?._id === signal._id ? 'bg-blue-100' : ''
                        }`}
                      >
                        <td className="px-4 py-3 text-sm font-mono">{signal.signal_id}</td>
                        <td className="px-4 py-3 text-sm">{signal.strategy_id}</td>
                        <td className="px-4 py-3 text-sm">{signal.instrument}</td>
                        <td className="px-4 py-3 text-sm font-mono">{signal.mode || 'N/A'}</td>
                        <td className="px-4 py-3 text-sm">
                          <span
                            className={`px-2 py-1 rounded text-xs ${
                              positionStatus === 'OPEN'
                                ? 'bg-green-100 text-green-800'
                                : positionStatus === 'CLOSED'
                                ? 'bg-gray-100 text-gray-800'
                                : positionStatus === 'PENDING'
                                ? 'bg-yellow-100 text-yellow-800'
                                : 'bg-red-100 text-red-800'
                            }`}
                          >
                            {positionStatus}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm">
                          <span className="text-green-600">E:{legsCount.entry}</span>
                          {' / '}
                          <span className="text-red-600">X:{legsCount.exit}</span>
                        </td>
                        <td className="px-4 py-3 text-sm">{formatTimestamp(signal.created_at)}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Detail View */}
      {selectedSignal && (
        <div className="w-1/2 border-l border-gray-200 overflow-auto">
          <div className="p-4">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold">Signal Details</h3>
              <button
                onClick={() => setSelectedSignal(null)}
                className="text-gray-500 hover:text-gray-700"
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
