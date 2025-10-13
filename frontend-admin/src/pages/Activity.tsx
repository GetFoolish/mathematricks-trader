import React, { useState } from 'react';
import { Activity as ActivityIcon, TrendingUp, TrendingDown, Clock } from 'lucide-react';

// Mock data for MVP - replace with real API calls when endpoints are available
const mockSignals = [
  {
    signal_id: 'SIG_20251012_140530_001',
    strategy_id: 'SPX_1-D_Opt',
    timestamp: '2025-10-12T14:05:30Z',
    instrument: 'ES',
    direction: 'LONG' as const,
    action: 'ENTRY' as const,
    price: 4520.50,
    status: 'PROCESSED',
  },
  {
    signal_id: 'SIG_20251012_133015_002',
    strategy_id: 'Forex',
    timestamp: '2025-10-12T13:30:15Z',
    instrument: 'EUR/USD',
    direction: 'SHORT' as const,
    action: 'ENTRY' as const,
    price: 1.0875,
    status: 'PROCESSED',
  },
];

const mockOrders = [
  {
    order_id: 'SIG_20251012_140530_001_ORD',
    signal_id: 'SIG_20251012_140530_001',
    strategy_id: 'SPX_1-D_Opt',
    timestamp: '2025-10-12T14:05:35Z',
    instrument: 'ES',
    quantity: 3.81,
    price: 4520.50,
    status: 'FILLED',
    filled_price: 4520.75,
  },
  {
    order_id: 'SIG_20251012_133015_002_ORD',
    signal_id: 'SIG_20251012_133015_002',
    strategy_id: 'Forex',
    timestamp: '2025-10-12T13:30:20Z',
    instrument: 'EUR/USD',
    quantity: 100000,
    price: 1.0875,
    status: 'FILLED',
    filled_price: 1.0874,
  },
];

const mockCerebroDecisions = [
  {
    signal_id: 'SIG_20251012_140530_001',
    strategy_id: 'SPX_1-D_Opt',
    decision: 'APPROVED' as const,
    timestamp: '2025-10-12T14:05:32Z',
    reason: 'APPROVED',
    original_quantity: 0,
    final_quantity: 3.81,
    risk_assessment: {
      margin_required: 8565.00,
      allocated_capital: 17130.00,
      margin_utilization_before_pct: 12.5,
      margin_utilization_after_pct: 21.1,
    },
  },
  {
    signal_id: 'SIG_20251012_133015_002',
    strategy_id: 'Forex',
    decision: 'APPROVED' as const,
    timestamp: '2025-10-12T13:30:18Z',
    reason: 'APPROVED',
    original_quantity: 0,
    final_quantity: 100000,
    risk_assessment: {
      margin_required: 3625.00,
      allocated_capital: 7250.00,
      margin_utilization_before_pct: 21.1,
      margin_utilization_after_pct: 24.7,
    },
  },
];

export const Activity: React.FC = () => {
  const [selectedTab, setSelectedTab] = useState<'signals' | 'orders' | 'decisions'>('signals');

  return (
    <div className="space-y-6">
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
          Recent Signals
        </button>
        <button
          onClick={() => setSelectedTab('orders')}
          className={`px-6 py-3 font-medium transition-colors ${
            selectedTab === 'orders'
              ? 'border-b-2 border-blue-500 text-blue-500'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          Orders & Executions
        </button>
        <button
          onClick={() => setSelectedTab('decisions')}
          className={`px-6 py-3 font-medium transition-colors ${
            selectedTab === 'decisions'
              ? 'border-b-2 border-blue-500 text-blue-500'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          Cerebro Decisions
        </button>
      </div>

      {/* Recent Signals Tab */}
      {selectedTab === 'signals' && (
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">Recent Signals (Last 50)</h3>
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
                {mockSignals.map((signal) => (
                  <tr key={signal.signal_id} className="hover:bg-gray-700/50">
                    <td className="table-cell text-sm">
                      <div className="flex items-center gap-2">
                        <Clock className="h-4 w-4 text-gray-400" />
                        {new Date(signal.timestamp).toLocaleString()}
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
                        signal.action === 'ENTRY' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'
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
                    <td className="table-cell">${signal.price.toFixed(2)}</td>
                    <td className="table-cell">
                      <span className="px-2 py-1 bg-green-900/30 text-green-400 rounded text-xs font-medium">
                        {signal.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Orders & Executions Tab */}
      {selectedTab === 'orders' && (
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">Recent Orders & Executions (Last 50)</h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="table-header">Timestamp</th>
                  <th className="table-header">Order ID</th>
                  <th className="table-header">Strategy</th>
                  <th className="table-header">Symbol</th>
                  <th className="table-header">Quantity</th>
                  <th className="table-header">Order Price</th>
                  <th className="table-header">Fill Price</th>
                  <th className="table-header">Slippage</th>
                  <th className="table-header">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {mockOrders.map((order) => {
                  const slippage = order.filled_price ? order.filled_price - order.price : 0;
                  return (
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
                      <td className="table-cell">{order.quantity.toLocaleString()}</td>
                      <td className="table-cell">${order.price.toFixed(4)}</td>
                      <td className="table-cell font-semibold">
                        ${order.filled_price?.toFixed(4) || '-'}
                      </td>
                      <td className={`table-cell ${slippage > 0 ? 'text-red-500' : 'text-green-500'}`}>
                        {slippage !== 0 ? `${slippage > 0 ? '+' : ''}${slippage.toFixed(4)}` : '-'}
                      </td>
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
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Cerebro Decisions Tab */}
      {selectedTab === 'decisions' && (
        <div className="space-y-4">
          <div className="card">
            <h3 className="text-lg font-semibold text-white mb-4">Cerebro Decision Log</h3>
            <p className="text-sm text-gray-400 mb-4">
              Detailed position sizing calculations and risk assessments
            </p>
          </div>

          {mockCerebroDecisions.map((decision) => (
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
                  <p className="text-white font-medium">{decision.final_quantity.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400 mb-1">Allocated Capital</p>
                  <p className="text-white font-medium">
                    ${decision.risk_assessment.allocated_capital.toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-400 mb-1">Margin Required</p>
                  <p className="text-white font-medium">
                    ${decision.risk_assessment.margin_required.toLocaleString()}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 p-4 bg-gray-700/30 rounded-lg">
                <div>
                  <p className="text-xs text-gray-400 mb-1">Margin Utilization Before</p>
                  <p className="text-white font-semibold">
                    {decision.risk_assessment.margin_utilization_before_pct.toFixed(1)}%
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-400 mb-1">Margin Utilization After</p>
                  <p className={`font-semibold ${
                    decision.risk_assessment.margin_utilization_after_pct > 40
                      ? 'text-red-500'
                      : 'text-green-500'
                  }`}>
                    {decision.risk_assessment.margin_utilization_after_pct.toFixed(1)}%
                  </p>
                </div>
              </div>
            </div>
          ))}

          {mockCerebroDecisions.length === 0 && (
            <div className="card text-center py-12">
              <ActivityIcon className="h-16 w-16 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400 text-lg">No Cerebro decisions yet</p>
              <p className="text-gray-500 text-sm mt-2">Decisions will appear here when signals are processed</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
