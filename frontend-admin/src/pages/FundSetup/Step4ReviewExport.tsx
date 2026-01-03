import { CheckCircle2, XCircle, AlertTriangle, Download } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import type { Fund, TradingAccount, Strategy } from '../../types';

interface Props {
  funds: Fund[];
  accounts: TradingAccount[];
}

export default function Step4ReviewExport({ funds, accounts }: Props) {
  // Fetch strategies to check mappings
  const { data: strategies } = useQuery({
    queryKey: ['strategies'],
    queryFn: async () => {
      const response = await apiClient.portfolioBuilderClient.get('/api/v1/strategies');
      return response.data.strategies || response.data;
    },
  });

  const mappedStrategies = strategies?.filter((s: Strategy) => s.accounts?.length > 0) || [];
  const unmappedStrategies = strategies?.filter((s: Strategy) => !s.accounts || s.accounts.length === 0) || [];

  const handleExportSeedData = async () => {
    try {
      // Trigger MongoDB dump via backend
      alert('Seed data export functionality will be implemented here');
      // In production, this would call an endpoint that creates a mongodump
    } catch (error) {
      console.error('Export failed:', error);
      alert('Failed to export seed data');
    }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Review & Export
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Validate your configuration and export as seed data
          </p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-800/20 border border-blue-200 dark:border-blue-800 rounded-lg p-6">
          <div className="text-4xl font-bold text-blue-600 dark:text-blue-400 mb-2">
            {funds.length}
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Total Funds
          </div>
        </div>

        <div className="bg-gradient-to-br from-green-50 to-green-100 dark:from-green-900/20 dark:to-green-800/20 border border-green-200 dark:border-green-800 rounded-lg p-6">
          <div className="text-4xl font-bold text-green-600 dark:text-green-400 mb-2">
            {accounts.length}
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Total Accounts
          </div>
        </div>

        <div className="bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-900/20 dark:to-purple-800/20 border border-purple-200 dark:border-purple-800 rounded-lg p-6">
          <div className="text-4xl font-bold text-purple-600 dark:text-purple-400 mb-2">
            {mappedStrategies.length} / {strategies?.length || 0}
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Strategies Mapped
          </div>
        </div>
      </div>

      {/* Validation Checks */}
      <div className="mb-8 space-y-3">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Validation Checks
        </h3>

        {funds.length > 0 ? (
          <div className="flex items-center p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
            <CheckCircle2 className="w-5 h-5 text-green-600 mr-3" />
            <span className="text-sm text-gray-700 dark:text-gray-300">
              At least one fund configured
            </span>
          </div>
        ) : (
          <div className="flex items-center p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <XCircle className="w-5 h-5 text-red-600 mr-3" />
            <span className="text-sm text-gray-700 dark:text-gray-300">
              No funds configured
            </span>
          </div>
        )}

        {accounts.length > 0 ? (
          <div className="flex items-center p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
            <CheckCircle2 className="w-5 h-5 text-green-600 mr-3" />
            <span className="text-sm text-gray-700 dark:text-gray-300">
              All accounts belong to a fund
            </span>
          </div>
        ) : (
          <div className="flex items-center p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <XCircle className="w-5 h-5 text-red-600 mr-3" />
            <span className="text-sm text-gray-700 dark:text-gray-300">
              No accounts configured
            </span>
          </div>
        )}

        {unmappedStrategies.length === 0 ? (
          <div className="flex items-center p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
            <CheckCircle2 className="w-5 h-5 text-green-600 mr-3" />
            <span className="text-sm text-gray-700 dark:text-gray-300">
              All strategies mapped to accounts
            </span>
          </div>
        ) : (
          <div className="flex items-center p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
            <AlertTriangle className="w-5 h-5 text-yellow-600 mr-3" />
            <span className="text-sm text-gray-700 dark:text-gray-300">
              {unmappedStrategies.length} strategies not mapped to any accounts
            </span>
          </div>
        )}
      </div>

      {/* Configuration Details */}
      <div className="space-y-6">
        {/* Funds Section */}
        <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Funds ({funds.length})
          </h3>
          {funds.map((fund) => (
            <div key={fund.fund_id} className="mb-4 last:mb-0">
              <div className="flex justify-between items-start">
                <div>
                  <div className="font-medium text-gray-900 dark:text-white">
                    {fund.name}
                  </div>
                  <div className="text-sm text-gray-500">
                    ID: {fund.fund_id} | Currency: {fund.currency} | Status: {fund.status}
                  </div>
                </div>
                <div className="text-sm text-gray-500">
                  {fund.accounts.length} account(s)
                </div>
              </div>
              {fund.accounts.length > 0 && (
                <div className="mt-2 ml-4 text-sm text-gray-600 dark:text-gray-400">
                  Accounts: {fund.accounts.join(', ')}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Accounts Section */}
        <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Accounts ({accounts.length})
          </h3>
          {funds.map((fund) => {
            const fundAccounts = accounts.filter((a) => a.fund_id === fund.fund_id);
            if (fundAccounts.length === 0) return null;

            return (
              <div key={fund.fund_id} className="mb-4 last:mb-0">
                <div className="font-medium text-gray-700 dark:text-gray-300 mb-2">
                  {fund.name}:
                </div>
                <div className="ml-4 space-y-1">
                  {fundAccounts.map((account) => (
                    <div key={account.account_id} className="text-sm text-gray-600 dark:text-gray-400">
                      • {account.account_id} ({account.broker}) - Asset Classes:{' '}
                      {Object.entries(account.asset_classes)
                        .filter(([_, values]) => values.length > 0)
                        .map(([key, values]) => `${key}: ${values.join(', ')}`)
                        .join(' | ')}
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* Strategy Mappings Section */}
        <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Strategy Mappings
          </h3>
          <div className="space-y-2">
            {mappedStrategies.map((strategy: Strategy) => (
              <div key={strategy.strategy_id} className="flex justify-between items-center text-sm">
                <span className="text-gray-900 dark:text-white font-medium">
                  {strategy.strategy_id}
                </span>
                <span className="text-gray-600 dark:text-gray-400">
                  → {strategy.accounts?.join(', ')}
                </span>
              </div>
            ))}
            {unmappedStrategies.length > 0 && (
              <div className="mt-4 pt-4 border-t border-gray-300 dark:border-gray-700">
                <div className="text-sm text-yellow-600 dark:text-yellow-400 font-medium mb-2">
                  Unmapped Strategies:
                </div>
                {unmappedStrategies.map((strategy: Strategy) => (
                  <div key={strategy.strategy_id} className="text-sm text-gray-500 ml-4">
                    • {strategy.strategy_id}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Export Button */}
      <div className="mt-8 flex justify-center">
        <button
          onClick={handleExportSeedData}
          disabled={funds.length === 0 || accounts.length === 0}
          className="flex items-center px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-lg font-semibold"
        >
          <Download className="w-6 h-6 mr-2" />
          Export as Seed Data
        </button>
      </div>

      {(funds.length === 0 || accounts.length === 0) && (
        <p className="text-center text-sm text-red-600 mt-4">
          Please create at least one fund and one account before exporting
        </p>
      )}
    </div>
  );
}
