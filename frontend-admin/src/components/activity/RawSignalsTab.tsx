import { useState, useEffect } from 'react';
import { api } from '../../services/api';

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
  const [selectedSignal, setSelectedSignal] = useState<RawSignal | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRawSignals();
  }, []);

  const fetchRawSignals = async () => {
    try {
      setLoading(true);
      const data = await api.getRawSignals({ limit: 100 });
      setRawSignals(data.raw_signals || []);
      setError(null);
    } catch (err: any) {
      console.error('Error fetching raw signals:', err);
      setError(err.message || 'Failed to fetch raw signals');
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

  if (loading) {
    return <div className="flex justify-center items-center p-8">Loading...</div>;
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 m-4">
        <p className="text-red-800">Error: {error}</p>
        <button
          onClick={fetchRawSignals}
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
            <h2 className="text-xl font-bold">Raw Signals ({rawSignals.length})</h2>
            <button
              onClick={fetchRawSignals}
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
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mode</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Environment</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Received At</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {rawSignals.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                      No raw signals found
                    </td>
                  </tr>
                ) : (
                  rawSignals.map((signal) => (
                    <tr
                      key={signal._id}
                      onClick={() => setSelectedSignal(signal)}
                      className={`cursor-pointer hover:bg-blue-50 ${
                        selectedSignal?._id === signal._id ? 'bg-blue-100' : ''
                      }`}
                    >
                      <td className="px-4 py-3 text-sm font-mono">{signal.signalID}</td>
                      <td className="px-4 py-3 text-sm">{signal.strategy_name || 'N/A'}</td>
                      <td className="px-4 py-3 text-sm">
                        <span
                          className={`px-2 py-1 rounded text-xs ${
                            signal.signal_type === 'ENTRY'
                              ? 'bg-green-100 text-green-800'
                              : signal.signal_type === 'EXIT'
                              ? 'bg-red-100 text-red-800'
                              : 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          {signal.signal_type || 'N/A'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm font-mono">{signal.mode || 'N/A'}</td>
                      <td className="px-4 py-3 text-sm">{signal.environment || 'N/A'}</td>
                      <td className="px-4 py-3 text-sm">{formatTimestamp(signal.received_at || signal.created_at)}</td>
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
