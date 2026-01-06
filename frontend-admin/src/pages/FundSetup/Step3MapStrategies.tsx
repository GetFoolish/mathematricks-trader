import { useState, useEffect } from 'react';
import { CheckCircle2, AlertCircle, Save } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import type { Fund, TradingAccount, Strategy } from '../../types';

interface Props {
  funds: Fund[];
  accounts: TradingAccount[];
}

export default function Step3MapStrategies({ funds, accounts }: Props) {
  const [strategyMappings, setStrategyMappings] = useState<Record<string, string[]>>({});
  const queryClient = useQueryClient();

  // Fetch strategies
  const { data: strategies, isLoading } = useQuery({
    queryKey: ['strategies'],
    queryFn: async () => {
      const response = await apiClient.portfolioBuilderClient.get('/api/v1/strategies');
      return response.data.strategies || response.data;
    },
  });

  // Initialize mappings from existing strategy.accounts
  useEffect(() => {
    if (strategies) {
      const mappings: Record<string, string[]> = {};
      strategies.forEach((strategy: Strategy) => {
        mappings[strategy.strategy_id] = strategy.accounts || [];
      });
      setStrategyMappings(mappings);
    }
  }, [strategies]);

  // Update strategy accounts mutation
  const updateMutation = useMutation({
    mutationFn: ({ strategyId, accounts }: { strategyId: string; accounts: string[] }) =>
      apiClient.updateStrategyAccounts(strategyId, accounts),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
    },
  });

  const handleAccountsChange = (strategyId: string, selectedAccounts: string[]) => {
    setStrategyMappings({
      ...strategyMappings,
      [strategyId]: selectedAccounts,
    });
  };

  const handleSaveAll = async () => {
    const promises = Object.entries(strategyMappings).map(([strategyId, accounts]) =>
      updateMutation.mutateAsync({ strategyId, accounts })
    );
    await Promise.all(promises);
    alert('All strategy mappings saved successfully!');
  };

  const getCompatibleAccounts = (strategyAssetClass: string) => {
    return accounts.filter((account) => {
      const assetClasses = account.asset_classes;
      const key = strategyAssetClass.toLowerCase() as keyof typeof assetClasses;
      return assetClasses[key]?.length > 0;
    });
  };

  if (isLoading) {
    return <div className="text-center py-12 text-gray-500">Loading strategies...</div>;
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Map Strategies to Accounts
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Assign which accounts each strategy can trade on
          </p>
        </div>
        <button
          onClick={handleSaveAll}
          disabled={updateMutation.isPending}
          className="flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50"
        >
          <Save className="w-5 h-5 mr-2" />
          Save All Mappings
        </button>
      </div>

      {accounts.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 dark:bg-gray-900 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600">
          <p className="text-gray-600 dark:text-gray-400">
            Please create accounts first (Step 2)
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {strategies?.map((strategy: Strategy) => {
            const compatibleAccounts = getCompatibleAccounts(strategy.asset_class || 'equity');
            const selectedAccounts = strategyMappings[strategy.strategy_id] || [];
            const hasMapping = selectedAccounts.length > 0;

            return (
              <div
                key={strategy.strategy_id}
                className={`border-2 rounded-lg p-4 ${
                  hasMapping
                    ? 'border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20'
                    : 'border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3 mb-2">
                      {hasMapping ? (
                        <CheckCircle2 className="w-5 h-5 text-green-600" />
                      ) : (
                        <AlertCircle className="w-5 h-5 text-red-600" />
                      )}
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                        {strategy.strategy_id}
                      </h3>
                      <span className="px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                        {strategy.asset_class || 'equity'}
                      </span>
                    </div>

                    <div className="mt-3">
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Allowed Accounts ({compatibleAccounts.length} compatible)
                      </label>
                      <div className="flex flex-wrap gap-2">
                        {compatibleAccounts.map((account) => {
                          const isSelected = selectedAccounts.includes(account.account_id);
                          return (
                            <button
                              key={account.account_id}
                              onClick={() => {
                                const newSelection = isSelected
                                  ? selectedAccounts.filter((id) => id !== account.account_id)
                                  : [...selectedAccounts, account.account_id];
                                handleAccountsChange(strategy.strategy_id, newSelection);
                              }}
                              className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                                isSelected
                                  ? 'bg-blue-600 text-white'
                                  : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
                              }`}
                            >
                              {account.account_id}
                              <span className="ml-2 text-xs opacity-75">({account.broker})</span>
                            </button>
                          );
                        })}
                      </div>
                      {compatibleAccounts.length === 0 && (
                        <p className="text-sm text-red-600 mt-2">
                          ⚠️ No accounts support {strategy.asset_class} asset class
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {strategies && strategies.length > 0 && (
        <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
          <p className="text-sm text-blue-800 dark:text-blue-200">
            <strong>Tip:</strong> Strategies are automatically filtered to show only accounts with compatible asset classes.
            For example, equity strategies only show accounts with equity enabled.
          </p>
        </div>
      )}
    </div>
  );
}
