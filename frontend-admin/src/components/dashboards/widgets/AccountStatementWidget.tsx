/**
 * AccountStatementWidget Component
 *
 * Displays transaction history for a specific account.
 * Shows opening balance, debits, credits, running balance, and realized P&L.
 */
import React, { useState } from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../../services/api';
import type { AccountStatementData, WidgetConfig } from '../../../types';

interface AccountStatementWidgetProps {
  data: AccountStatementData;
  config: WidgetConfig;
}

export const AccountStatementWidget: React.FC<AccountStatementWidgetProps> = ({ data, config }) => {
  const [selectedAccount, setSelectedAccount] = useState<string>(config.account_filter || 'all');

  // Fetch available accounts for the dropdown
  const { data: accounts } = useQuery({
    queryKey: ['accounts'],
    queryFn: async () => {
      // Extract unique account IDs from transactions
      const accountIds = new Set(data.transactions.map(t => t.account_id));
      return Array.from(accountIds).sort();
    },
    enabled: data.transactions.length > 0,
  });

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getPnLColor = (pnl: number) => {
    if (pnl > 0) return 'text-green-500';
    if (pnl < 0) return 'text-red-500';
    return 'text-gray-400';
  };

  // Filter transactions by selected account
  const filteredTransactions = selectedAccount === 'all'
    ? data.transactions
    : data.transactions.filter(t => t.account_id === selectedAccount);

  // Calculate summary stats from filtered transactions (excluding opening balance rows)
  const filteredSummary = {
    total_debits: filteredTransactions
      .filter(t => t.type !== 'OPENING_BALANCE')
      .reduce((sum, t) => sum + t.debit, 0),
    total_credits: filteredTransactions
      .filter(t => t.type !== 'OPENING_BALANCE')
      .reduce((sum, t) => sum + t.credit, 0),
    net_pnl: filteredTransactions
      .filter(t => t.type !== 'OPENING_BALANCE')
      .reduce((sum, t) => sum + t.realized_pnl, 0),
  };

  return (
    <div className="space-y-4">
      {/* Account Dropdown */}
      {accounts && accounts.length > 1 && (
        <div className="flex items-center space-x-2">
          <label className="text-sm text-gray-400">Account:</label>
          <select
            value={selectedAccount}
            onChange={(e) => setSelectedAccount(e.target.value)}
            className="bg-gray-800 border border-gray-700 text-white text-sm rounded px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Accounts</option>
            {accounts.map(accountId => (
              <option key={accountId} value={accountId}>
                {accountId}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-gray-800 rounded-lg p-3 border border-gray-700">
          <div className="text-xs text-gray-400 mb-1">Total Debits</div>
          <div className="text-lg font-semibold text-red-400">
            {formatCurrency(filteredSummary.total_debits)}
          </div>
        </div>
        <div className="bg-gray-800 rounded-lg p-3 border border-gray-700">
          <div className="text-xs text-gray-400 mb-1">Total Credits</div>
          <div className="text-lg font-semibold text-green-400">
            {formatCurrency(filteredSummary.total_credits)}
          </div>
        </div>
        <div className="bg-gray-800 rounded-lg p-3 border border-gray-700">
          <div className="text-xs text-gray-400 mb-1">Net P&L</div>
          <div className={`text-lg font-semibold flex items-center space-x-1 ${getPnLColor(filteredSummary.net_pnl)}`}>
            {filteredSummary.net_pnl > 0 ? (
              <TrendingUp className="w-4 h-4" />
            ) : filteredSummary.net_pnl < 0 ? (
              <TrendingDown className="w-4 h-4" />
            ) : null}
            <span>{formatCurrency(filteredSummary.net_pnl)}</span>
          </div>
        </div>
      </div>

      {/* Transactions Table */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
        <div className="overflow-x-auto max-h-96">
          <table className="w-full text-sm">
            <thead className="bg-gray-900 sticky top-0 z-10">
              <tr className="text-left text-xs text-gray-400 border-b border-gray-700">
                <th className="px-3 py-2">Date</th>
                <th className="px-3 py-2">Description</th>
                <th className="px-3 py-2 text-right">Debit</th>
                <th className="px-3 py-2 text-right">Credit</th>
                <th className="px-3 py-2 text-right">P&L</th>
                <th className="px-3 py-2 text-right">Account Balance</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {filteredTransactions.map((transaction, index) => {
                const isOpeningBalance = transaction.type === 'OPENING_BALANCE';

                return (
                  <tr
                    key={`${transaction.signal_id}-${index}`}
                    className={`transition-colors ${
                      isOpeningBalance
                        ? 'bg-gray-750 font-bold'
                        : 'hover:bg-gray-750'
                    }`}
                  >
                    <td className="px-3 py-2 whitespace-nowrap">
                      <div className={isOpeningBalance ? 'text-gray-300' : 'text-white'}>
                        {formatDate(transaction.date)}
                      </div>
                      {!isOpeningBalance && (
                        <div className="text-xs text-gray-500">{formatTime(transaction.timestamp)}</div>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <div className={isOpeningBalance ? 'text-gray-300 font-bold' : 'text-white'}>
                        {transaction.description}
                      </div>
                      {!isOpeningBalance && (
                        <div className="text-xs text-gray-500">
                          {transaction.signal_id && (
                            <span className="mr-2">{transaction.signal_id}</span>
                          )}
                          {transaction.account_id}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {transaction.debit > 0 && (
                        <span className="text-red-400">
                          {formatCurrency(transaction.debit)}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {transaction.credit > 0 && (
                        <span className="text-green-400">
                          {formatCurrency(transaction.credit)}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {transaction.realized_pnl !== 0 && (
                        <span className={getPnLColor(transaction.realized_pnl)}>
                          {formatCurrency(transaction.realized_pnl)}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <span className={`font-medium ${isOpeningBalance ? 'text-gray-300 font-bold' : 'text-white'}`}>
                        {formatCurrency(transaction.balance)}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Empty State */}
        {filteredTransactions.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            <div className="text-sm">No transactions in the last {config.date_range_days || 30} days</div>
          </div>
        )}
      </div>

      {/* Footer Info */}
      <div className="text-xs text-gray-500 text-right">
        Showing {filteredTransactions.length} transaction{filteredTransactions.length !== 1 ? 's' : ''}
        {' '}from last {config.date_range_days || 30} days
      </div>
    </div>
  );
};
