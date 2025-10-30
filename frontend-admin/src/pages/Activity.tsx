import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../services/api';
import { Activity as ActivityIcon, TrendingUp, TrendingDown, Clock } from 'lucide-react';

export const Activity: React.FC = () => {
  const [selectedTab, setSelectedTab] = useState<'signals' | 'orders' | 'decisions'>('signals');
  const [environment, setEnvironment] = useState<'production' | 'staging'>('staging');

  // Fetch signals
  const { data: signalsData, isLoading: isLoadingSignals } = useQuery({
    queryKey: ['signals', environment],
    queryFn: () => apiClient.getRecentSignals(50, environment),
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  // Fetch orders
  const { data: ordersData, isLoading: isLoadingOrders } = useQuery({
    queryKey: ['orders', environment],
    queryFn: () => apiClient.getRecentOrders(50, environment),
    refetchInterval: 5000,
  });

  // Fetch decisions
  const { data: decisionsData, isLoading: isLoadingDecisions } = useQuery({
    queryKey: ['decisions', environment],
    queryFn: () => apiClient.getCerebroDecisions(50, environment),
    refetchInterval: 5000,
  });

  const signals = signalsData?.signals || [];
  const orders = ordersData?.orders || [];
  const decisions = decisionsData?.decisions || [];

  return (
    <div className="space-y-6">
      {/* Environment Toggle */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">Trading Activity</h2>

        {/* Apple-style Toggle */}
        <div className="flex items-center gap-3">
          <span className={`text-sm font-medium ${environment === 'production' ? 'text-white' : 'text-gray-400'}`}>
            Production
          </span>
          <button
            onClick={() => setEnvironment(environment === 'production' ? 'staging' : 'production')}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-900 ${
              environment === 'staging' ? 'bg-blue-600' : 'bg-gray-600'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                environment === 'staging' ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
          <span className={`text-sm font-medium ${environment === 'staging' ? 'text-white' : 'text-gray-400'}`}>
            Staging
          </span>
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
          Recent Signals ({signals.length})
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
          onClick={() => setSelectedTab('decisions')}
          className={`px-6 py-3 font-medium transition-colors ${
            selectedTab === 'decisions'
              ? 'border-b-2 border-blue-500 text-blue-500'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          Cerebro Decisions ({decisions.length})
        </button>
      </div>

      {/* Recent Signals Tab */}
      {selectedTab === 'signals' && (
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">
            Recent Signals - {environment.toUpperCase()}
          </h3>

          {isLoadingSignals ? (
            <div className="text-center py-12">
              <div className="inline-block animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mb-3"></div>
              <p className="text-gray-400">Loading signals...</p>
            </div>
          ) : signals.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-400">No signals found for {environment}</p>
              <p className="text-sm text-gray-500 mt-2">Send test signals using live_signal_tester.py</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="table-header">Timestamp</th>
                    <th className="table-header">Signal ID</th>
                    <th className="table-header">Strategy</th>
                    <th className="table-header">Symbol</th>
                    <th className="table-header">Action</th>
                    <th className="table-header">Direction</th>
                    <th className="table-header">Price</th>
                    <th className="table-header">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {signals.map((signal: any) => (
                    <tr key={signal.signal_id} className="hover:bg-gray-700/50">
                      <td className="table-cell text-sm">
                        <div className="flex items-center gap-2">
                          <Clock className="h-4 w-4 text-gray-400" />
                          {new Date(signal.created_at || signal.timestamp).toLocaleString()}
                        </div>
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
                      <td className="table-cell">${signal.price?.toFixed(2) || 'N/A'}</td>
                      <td className="table-cell">
                        <span className="px-2 py-1 bg-green-900/30 text-green-400 rounded text-xs font-medium">
                          {signal.processed_by_cerebro ? 'PROCESSED' : 'PENDING'}
                        </span>
                      </td>
                    </tr>
                  ))}
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
            Recent Orders & Executions - {environment.toUpperCase()}
          </h3>

          {isLoadingOrders ? (
            <div className="text-center py-12">
              <div className="inline-block animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mb-3"></div>
              <p className="text-gray-400">Loading orders...</p>
            </div>
          ) : orders.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-400">No orders found for {environment}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="table-header">Timestamp</th>
                    <th className="table-header">Order ID</th>
                    <th className="table-header">Strategy</th>
                    <th className="table-header">Symbol</th>
                    <th className="table-header">Quantity</th>
                    <th className="table-header">Price</th>
                    <th className="table-header">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {orders.map((order: any) => (
                    <tr key={order.order_id} className="hover:bg-gray-700/50">
                      <td className="table-cell text-sm">
                        <div className="flex items-center gap-2">
                          <Clock className="h-4 w-4 text-gray-400" />
                          {new Date(order.timestamp).toLocaleString()}
                        </div>
                      </td>
                      <td className="table-cell font-mono text-xs">{order.order_id}</td>
                      <td className="table-cell">
                        <span className="px-2 py-1 bg-blue-900/30 text-blue-400 rounded text-xs font-medium">
                          {order.strategy_id}
                        </span>
                      </td>
                      <td className="table-cell font-semibold">{order.instrument}</td>
                      <td className="table-cell">{order.quantity?.toFixed(2) || 0}</td>
                      <td className="table-cell">${order.price?.toFixed(2) || 0}</td>
                      <td className="table-cell">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          order.status === 'FILLED' ? 'bg-green-900/30 text-green-400' :
                          order.status === 'PENDING' ? 'bg-yellow-900/30 text-yellow-400' :
                          'bg-red-900/30 text-red-400'
                        }`}>
                          {order.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Cerebro Decisions Tab */}
      {selectedTab === 'decisions' && (
        <div className="space-y-4">
          <div className="card">
            <h3 className="text-lg font-semibold text-white mb-4">
              Cerebro Decision Log - {environment.toUpperCase()}
            </h3>
            <p className="text-sm text-gray-400 mb-4">
              Detailed position sizing calculations and risk assessments
            </p>
          </div>

          {isLoadingDecisions ? (
            <div className="card">
              <div className="text-center py-12">
                <div className="inline-block animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mb-3"></div>
                <p className="text-gray-400">Loading decisions...</p>
              </div>
            </div>
          ) : decisions.length === 0 ? (
            <div className="card text-center py-12">
              <ActivityIcon className="h-16 w-16 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400 text-lg">No Cerebro decisions yet for {environment}</p>
              <p className="text-gray-500 text-sm mt-2">Decisions will appear here when signals are processed</p>
            </div>
          ) : (
            decisions.map((decision: any) => (
              <div key={decision.signal_id} className="card">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <ActivityIcon className="h-5 w-5 text-blue-500" />
                    <div>
                      <p className="text-white font-medium">Signal: {decision.signal_id}</p>
                      <p className="text-sm text-gray-400">{new Date(decision.timestamp).toLocaleString()}</p>
                    </div>
                  </div>
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                    decision.decision === 'APPROVED' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'
                  }`}>
                    {decision.decision}
                  </span>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4 p-4 bg-gray-700/30 rounded-lg">
                  <div>
                    <p className="text-xs text-gray-400 mb-1">Strategy</p>
                    <p className="text-white font-medium">{decision.strategy_id}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400 mb-1">Final Quantity</p>
                    <p className="text-white font-medium">{decision.final_quantity?.toFixed(2) || 0}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400 mb-1">Allocated Capital</p>
                    <p className="text-white font-medium">
                      ${decision.risk_assessment?.allocated_capital?.toLocaleString() || 0}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400 mb-1">Margin Required</p>
                    <p className="text-white font-medium">
                      ${decision.risk_assessment?.margin_required?.toLocaleString() || 0}
                    </p>
                  </div>
                </div>

                {decision.risk_assessment && (
                  <div className="grid grid-cols-2 gap-4 p-4 bg-gray-700/30 rounded-lg">
                    <div>
                      <p className="text-xs text-gray-400 mb-1">Margin Utilization Before</p>
                      <p className="text-white font-semibold">
                        {decision.risk_assessment.margin_utilization_before_pct?.toFixed(1) || 0}%
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-400 mb-1">Margin Utilization After</p>
                      <p className={`font-semibold ${
                        (decision.risk_assessment.margin_utilization_after_pct || 0) > 40
                          ? 'text-red-500'
                          : 'text-green-500'
                      }`}>
                        {decision.risk_assessment.margin_utilization_after_pct?.toFixed(1) || 0}%
                      </p>
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};
