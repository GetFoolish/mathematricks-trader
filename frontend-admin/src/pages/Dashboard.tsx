import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../services/api';
import { DollarSign, TrendingUp, AlertCircle, Target } from 'lucide-react';

export const Dashboard: React.FC = () => {
  // Fetch account state
  const { data: accountState, isLoading: accountLoading } = useQuery({
    queryKey: ['accountState'],
    queryFn: () => apiClient.getAccountState('IBKR_Main'),
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  // Fetch current allocation
  const { data: currentAllocation } = useQuery({
    queryKey: ['currentAllocation'],
    queryFn: () => apiClient.getCurrentAllocation(),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // Calculate today's P&L (simplified - would use historical data in production)
  const todayPnl = accountState?.unrealized_pnl || 0;
  const todayPnlPct = accountState
    ? ((todayPnl / accountState.equity) * 100).toFixed(2)
    : '0.00';

  const marginUtilizationPct = accountState
    ? ((accountState.margin_used / accountState.equity) * 100).toFixed(1)
    : '0.0';

  const totalAllocationPct = currentAllocation
    ? Object.values(currentAllocation.allocations).reduce((sum, val) => sum + val, 0).toFixed(1)
    : '0.0';

  if (accountLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-white text-xl">Loading dashboard...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Current Equity */}
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400 mb-1">Current Equity</p>
              <p className="text-2xl font-bold text-white">
                ${accountState?.equity.toLocaleString() || '0'}
              </p>
            </div>
            <div className="bg-blue-900/30 p-3 rounded-lg">
              <DollarSign className="h-8 w-8 text-blue-500" />
            </div>
          </div>
        </div>

        {/* Today's P&L */}
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400 mb-1">Today's P&L</p>
              <p className={`text-2xl font-bold ${todayPnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                ${todayPnl.toLocaleString()}
              </p>
              <p className={`text-sm ${todayPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {todayPnl >= 0 ? '+' : ''}{todayPnlPct}%
              </p>
            </div>
            <div className={`p-3 rounded-lg ${todayPnl >= 0 ? 'bg-green-900/30' : 'bg-red-900/30'}`}>
              <TrendingUp className={`h-8 w-8 ${todayPnl >= 0 ? 'text-green-500' : 'text-red-500'}`} />
            </div>
          </div>
        </div>

        {/* Margin Used */}
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400 mb-1">Margin Used</p>
              <p className="text-2xl font-bold text-white">{marginUtilizationPct}%</p>
              <p className="text-sm text-gray-400">
                ${accountState?.margin_used.toLocaleString() || '0'}
              </p>
            </div>
            <div className={`p-3 rounded-lg ${
              Number(marginUtilizationPct) > 40 ? 'bg-red-900/30' : 'bg-gray-700'
            }`}>
              <AlertCircle className={`h-8 w-8 ${
                Number(marginUtilizationPct) > 40 ? 'text-red-500' : 'text-gray-400'
              }`} />
            </div>
          </div>
        </div>

        {/* Open Positions */}
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400 mb-1">Open Positions</p>
              <p className="text-2xl font-bold text-white">
                {accountState?.open_positions?.length || 0}
              </p>
              <p className="text-sm text-gray-400">Active trades</p>
            </div>
            <div className="bg-purple-900/30 p-3 rounded-lg">
              <Target className="h-8 w-8 text-purple-500" />
            </div>
          </div>
        </div>
      </div>

      {/* Current Allocation Summary */}
      {currentAllocation && (
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">Current Portfolio Allocation</h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center pb-3 border-b border-gray-700">
              <span className="text-gray-400 font-medium">Total Allocation</span>
              <span className="text-white font-bold text-lg">{totalAllocationPct}%</span>
            </div>
            {Object.entries(currentAllocation.allocations)
              .sort(([, a], [, b]) => b - a)
              .map(([strategyId, allocation]) => (
                <div key={strategyId} className="flex items-center justify-between">
                  <div className="flex-1">
                    <p className="text-white font-medium">{strategyId}</p>
                    <div className="mt-1 bg-gray-700 rounded-full h-2 overflow-hidden">
                      <div
                        className="bg-blue-500 h-full transition-all"
                        style={{ width: `${allocation}%` }}
                      />
                    </div>
                  </div>
                  <span className="ml-4 text-white font-semibold w-16 text-right">
                    {allocation.toFixed(1)}%
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Open Positions */}
      {accountState && accountState.open_positions && accountState.open_positions.length > 0 && (
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">Open Positions</h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="table-header">Instrument</th>
                  <th className="table-header">Quantity</th>
                  <th className="table-header">Entry Price</th>
                  <th className="table-header">Current Price</th>
                  <th className="table-header">Unrealized P&L</th>
                  <th className="table-header">Strategy</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {accountState.open_positions.map((position, idx) => (
                  <tr key={idx} className="hover:bg-gray-700/50">
                    <td className="table-cell font-medium">{position.instrument}</td>
                    <td className="table-cell">{position.quantity}</td>
                    <td className="table-cell">${position.entry_price.toFixed(2)}</td>
                    <td className="table-cell">${position.current_price.toFixed(2)}</td>
                    <td className={`table-cell font-semibold ${
                      position.unrealized_pnl >= 0 ? 'text-green-500' : 'text-red-500'
                    }`}>
                      ${position.unrealized_pnl.toLocaleString()}
                    </td>
                    <td className="table-cell text-gray-400 text-xs">{position.strategy_id || 'N/A'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* No positions message */}
      {accountState && accountState.open_positions && accountState.open_positions.length === 0 && (
        <div className="card text-center py-12">
          <Target className="h-16 w-16 text-gray-600 mx-auto mb-4" />
          <p className="text-gray-400 text-lg">No open positions</p>
          <p className="text-gray-500 text-sm mt-2">Positions will appear here when trades are executed</p>
        </div>
      )}
    </div>
  );
};
