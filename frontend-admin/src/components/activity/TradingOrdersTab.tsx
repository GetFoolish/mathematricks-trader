import { useState, useEffect } from 'react';
import { api } from '../../services/api';
import { Clock, ChevronDown, ChevronRight } from 'lucide-react';

interface TradingOrder {
  _id: string;
  order_id: string;
  signal_id?: string;
  account_id?: string;
  symbol: string;
  instrument?: string;
  action: string;
  quantity: number;
  quantity_filled?: number;
  order_type: string;
  status: string;
  environment?: string;
  mode?: string;
  signal_type?: string;
  broker?: string;
  fund_id?: string;
  avg_fill_price?: number;
  broker_order_id?: string;
  filled_at?: string;
  created_at: string;
  updated_at?: string;
  [key: string]: any;
}

export default function TradingOrdersTab() {
  const [orders, setOrders] = useState<TradingOrder[]>([]);
  const [expandedOrderId, setExpandedOrderId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchOrders();
    // Set up polling every 5 seconds
    const interval = setInterval(fetchOrders, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchOrders = async () => {
    try {
      setLoading(true);
      const data = await api.getTradingOrdersFull({ limit: 100 });
      setOrders(data.orders || []);
      setError(null);
    } catch (err: any) {
      console.error('Error fetching trading orders:', err);
      setError(err.message || 'Failed to fetch trading orders');
    } finally {
      setLoading(false);
    }
  };

  const formatTimestamp = (timestamp: string | null) => {
    if (!timestamp) return 'N/A';
    try {
      return new Date(timestamp).toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      });
    } catch {
      return timestamp;
    }
  };

  if (loading && orders.length === 0) {
    return (
      <div className="flex justify-center items-center p-12">
        <div className="inline-block animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mb-3"></div>
        <p className="text-gray-400 ml-4">Loading orders...</p>
      </div>
    );
  }

  if (error && orders.length === 0) {
    return (
      <div className="bg-red-900/20 border border-red-700 rounded-lg p-4 m-4">
        <p className="text-red-400">Error: {error}</p>
        <button
          onClick={fetchOrders}
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
          Recent Orders & Executions ({orders.length})
        </h3>
        <button
          onClick={fetchOrders}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors"
        >
          Refresh
        </button>
      </div>

      {orders.length === 0 ? (
        <div className="text-center py-12 bg-gray-800 rounded-lg">
          <p className="text-gray-400">No orders found</p>
        </div>
      ) : (
        <div className="overflow-x-auto bg-gray-800 rounded-lg">
          <table className="w-full">
            <thead className="bg-gray-900/50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase w-8"></th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Filled Timestamp</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Signal ID</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Order ID</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Symbol</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Type</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Mode</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Broker</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Fund</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Filled Qty</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Filled Price</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Broker Order ID</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {orders.map((order) => {
                const isExpanded = expandedOrderId === order._id;
                return (
                  <>
                    <tr key={order._id} className="hover:bg-gray-700/50 transition-colors">
                      <td className="px-4 py-3">
                        <button
                          onClick={() => setExpandedOrderId(isExpanded ? null : order._id)}
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
                      <td className="px-4 py-3 text-sm text-gray-300">
                        <div className="flex items-center gap-2">
                          <Clock className="h-4 w-4 text-gray-400" />
                          {formatTimestamp(order.filled_at || order.created_at)}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-1 bg-purple-900/30 text-purple-400 rounded text-xs font-medium font-mono">
                          {order.signal_id || 'N/A'}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-gray-400">{order.order_id}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`px-2 py-1 rounded text-xs font-medium ${
                            order.status === 'FILLED'
                              ? 'bg-green-900/30 text-green-400'
                              : order.status === 'PARTIAL'
                              ? 'bg-yellow-900/30 text-yellow-400'
                              : order.status === 'PENDING'
                              ? 'bg-blue-900/30 text-blue-400'
                              : 'bg-red-900/30 text-red-400'
                          }`}
                        >
                          {order.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-200 font-semibold">{order.instrument || order.symbol}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`px-2 py-1 rounded text-xs font-medium ${
                            order.signal_type === 'ENTRY'
                              ? 'bg-green-900/30 text-green-400'
                              : order.signal_type === 'EXIT'
                              ? 'bg-red-900/30 text-red-400'
                              : 'bg-gray-900/30 text-gray-400'
                          }`}
                        >
                          {order.signal_type || 'N/A'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-1 bg-purple-900/30 text-purple-400 rounded text-xs font-medium uppercase">
                          {order.mode || 'N/A'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-1 bg-blue-900/30 text-blue-400 rounded text-xs font-medium">
                          {order.broker || 'N/A'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-400">{order.fund_id || 'N/A'}</td>
                      <td className="px-4 py-3 text-gray-300">{order.quantity_filled?.toFixed(2) || 0}</td>
                      <td className="px-4 py-3 text-gray-300">${order.avg_fill_price?.toFixed(2) || 0}</td>
                      <td className="px-4 py-3 font-mono text-xs text-gray-500">{order.broker_order_id || 'N/A'}</td>
                    </tr>
                    {isExpanded && (
                      <tr key={`${order._id}-details`}>
                        <td colSpan={13} className="bg-gray-900/50 p-4">
                          <div className="space-y-2">
                            <h4 className="text-sm font-semibold text-white mb-2">Full Order Details</h4>
                            <pre className="text-xs text-gray-300 bg-gray-950 p-4 rounded border border-gray-700 overflow-auto max-h-96">
                              {JSON.stringify(order, null, 2)}
                            </pre>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
