import { useState } from 'react';
import { Plus, Edit2, Trash2, Copy, CreditCard } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import type { Fund, TradingAccount, CreateAccountRequest, AssetClasses } from '../../types';

interface Props {
  funds: Fund[];
  accounts: TradingAccount[];
  setAccounts: (accounts: TradingAccount[]) => void;
}

const DEFAULT_ASSET_CLASSES: AssetClasses = {
  equity: [],
  futures: [],
  crypto: [],
  forex: [],
};

const BROKER_DEFAULT_ASSET_CLASSES: Record<string, AssetClasses> = {
  IBKR: {
    equity: ['all'],
    futures: ['all'],
    forex: ['all'],
    crypto: [],
  },
  Binance: {
    equity: [],
    futures: [],
    forex: [],
    crypto: ['all'],
  },
  Alpaca: {
    equity: ['all'],
    futures: [],
    forex: [],
    crypto: [],
  },
  Mock: {
    equity: ['all'],
    futures: ['all'],
    forex: ['all'],
    crypto: ['all'],
  },
  Mock_Paper: {
    equity: ['all'],
    futures: ['all'],
    forex: ['all'],
    crypto: ['all'],
  },
};

export default function Step2ConfigureAccounts({ funds, accounts, setAccounts }: Props) {
  const [showModal, setShowModal] = useState(false);
  const [isDuplicating, setIsDuplicating] = useState(false);
  const [selectedFund, setSelectedFund] = useState<string>('');
  const [editingAccount, setEditingAccount] = useState<TradingAccount | null>(null);
  const [formData, setFormData] = useState<CreateAccountRequest>({
    account_id: '',
    broker: 'IBKR',
    fund_id: '',
    asset_classes: DEFAULT_ASSET_CLASSES,
  });

  const queryClient = useQueryClient();

  // Fetch accounts
  const { data: fetchedAccounts, isLoading } = useQuery({
    queryKey: ['accounts', selectedFund],
    queryFn: () => apiClient.getAccounts(selectedFund || undefined),
  });

  // Update local state
  if (fetchedAccounts && JSON.stringify(fetchedAccounts) !== JSON.stringify(accounts)) {
    setAccounts(fetchedAccounts);
  }

  // Create account mutation
  const createMutation = useMutation({
    mutationFn: (data: CreateAccountRequest) => apiClient.createAccount(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
      queryClient.invalidateQueries({ queryKey: ['funds'] });
      setShowModal(false);
      resetForm();
    },
  });

  // Update account mutation
  const updateMutation = useMutation({
    mutationFn: ({ accountId, data }: { accountId: string; data: any }) =>
      apiClient.updateAccount(accountId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
      queryClient.invalidateQueries({ queryKey: ['funds'] });
      setShowModal(false);
      setEditingAccount(null);
      resetForm();
    },
  });

  // Delete account mutation
  const deleteMutation = useMutation({
    mutationFn: (accountId: string) => apiClient.deleteAccount(accountId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
      queryClient.invalidateQueries({ queryKey: ['funds'] });
    },
  });

  const resetForm = () => {
    setFormData({
      account_id: '',
      broker: 'IBKR',
      fund_id: selectedFund || (funds[0]?.fund_id || ''),
      asset_classes: DEFAULT_ASSET_CLASSES,
    });
    setIsDuplicating(false);
  };

  const handleBrokerChange = (broker: string) => {
    const defaultAssetClasses = BROKER_DEFAULT_ASSET_CLASSES[broker] || DEFAULT_ASSET_CLASSES;
    setFormData({
      ...formData,
      broker,
      asset_classes: defaultAssetClasses,
    });
  };

  const handleAssetClassToggle = (assetClass: keyof AssetClasses, enabled: boolean) => {
    setFormData({
      ...formData,
      asset_classes: {
        ...formData.asset_classes,
        [assetClass]: enabled ? ['all'] : [],
      },
    });
  };

  const handleAssetClassSymbols = (assetClass: keyof AssetClasses, symbols: string) => {
    const symbolArray = symbols.split(',').map((s) => s.trim()).filter(Boolean);
    setFormData({
      ...formData,
      asset_classes: {
        ...formData.asset_classes,
        [assetClass]: symbolArray.length > 0 ? symbolArray : [],
      },
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (editingAccount) {
      updateMutation.mutate({
        accountId: editingAccount.account_id,
        data: {
          fund_id: formData.fund_id,
          asset_classes: formData.asset_classes,
        },
      });
    } else {
      createMutation.mutate(formData);
    }
  };

  const handleAddAccount = () => {
    setEditingAccount(null);
    setIsDuplicating(false);
    setFormData({
      account_id: '',
      broker: 'IBKR',
      fund_id: selectedFund || (funds[0]?.fund_id || ''),
      asset_classes: BROKER_DEFAULT_ASSET_CLASSES['IBKR'],
    });
    setShowModal(true);
  };

  const handleDuplicateAccount = (account: TradingAccount) => {
    setEditingAccount(null);
    setIsDuplicating(true);
    setFormData({
      account_id: `${account.account_id}_copy`,
      broker: account.broker,
      fund_id: selectedFund || (funds[0]?.fund_id || ''),
      asset_classes: account.asset_classes,
    });
    setShowModal(true);
  };

  const handleEdit = (account: TradingAccount) => {
    setEditingAccount(account);
    setIsDuplicating(false);
    setFormData({
      account_id: account.account_id,
      broker: account.broker,
      fund_id: account.fund_id,
      asset_classes: account.asset_classes,
    });
    setShowModal(true);
  };

  const handleDelete = (accountId: string) => {
    if (confirm('Are you sure you want to delete this account?')) {
      deleteMutation.mutate(accountId);
    }
  };

  const filteredAccounts = selectedFund
    ? accounts.filter((a) => a.fund_id === selectedFund)
    : accounts;

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Configure Accounts
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Set up broker accounts for your funds
          </p>
        </div>
        <div className="flex space-x-3">
          <select
            value={selectedFund}
            onChange={(e) => setSelectedFund(e.target.value)}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
          >
            <option value="">All Funds</option>
            {funds.map((fund) => (
              <option key={fund.fund_id} value={fund.fund_id}>
                {fund.name}
              </option>
            ))}
          </select>
          <button
            onClick={handleAddAccount}
            disabled={funds.length === 0}
            className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Plus className="w-5 h-5 mr-2" />
            Add Account
          </button>
        </div>
      </div>

      {funds.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 dark:bg-gray-900 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600">
          <p className="text-gray-600 dark:text-gray-400 mb-4">
            Please create at least one fund first (Step 1)
          </p>
        </div>
      ) : isLoading ? (
        <div className="text-center py-12 text-gray-500">Loading accounts...</div>
      ) : filteredAccounts.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 dark:bg-gray-900 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600">
          <CreditCard className="w-16 h-16 mx-auto text-gray-400 mb-4" />
          <p className="text-gray-600 dark:text-gray-400 mb-4">
            No accounts configured yet
          </p>
          <button
            onClick={handleAddAccount}
            className="text-blue-600 hover:text-blue-700 font-medium"
          >
            Create your first account →
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Group accounts by fund */}
          {funds
            .filter((fund) => !selectedFund || fund.fund_id === selectedFund)
            .map((fund) => {
              const fundAccounts = accounts.filter((a) => a.fund_id === fund.fund_id);
              if (fundAccounts.length === 0) return null;

              return (
                <div key={fund.fund_id}>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
                    {fund.name} ({fundAccounts.length} account{fundAccounts.length !== 1 ? 's' : ''})
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                      <thead className="bg-gray-50 dark:bg-gray-900">
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                            Account ID
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                            Broker
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                            Asset Classes
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                            Equity
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                            Status
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                            Actions
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                        {fundAccounts.map((account) => (
                          <tr key={account.account_id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                            <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                              {account.account_id}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                              {account.broker}
                            </td>
                            <td className="px-6 py-4">
                              <div className="flex flex-wrap gap-1">
                                {Object.entries(account.asset_classes).map(([key, values]) =>
                                  values.length > 0 ? (
                                    <span
                                      key={key}
                                      className="px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
                                    >
                                      {key}: {values.join(', ')}
                                    </span>
                                  ) : null
                                )}
                              </div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                              ${(account.equity || 0).toLocaleString()}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className={`px-2 py-1 text-xs rounded-full ${
                                account.status === 'ACTIVE'
                                  ? 'bg-green-100 text-green-800'
                                  : 'bg-gray-100 text-gray-800'
                              }`}>
                                {account.status}
                              </span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm space-x-2">
                              <button
                                onClick={() => handleEdit(account)}
                                className="text-blue-600 hover:text-blue-700"
                                title="Edit"
                              >
                                <Edit2 className="w-4 h-4" />
                              </button>
                              <button
                                onClick={() => handleDuplicateAccount(account)}
                                className="text-green-600 hover:text-green-700"
                                title="Duplicate"
                              >
                                <Copy className="w-4 h-4" />
                              </button>
                              <button
                                onClick={() => handleDelete(account.account_id)}
                                className="text-red-600 hover:text-red-700"
                                title="Delete"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              );
            })}
        </div>
      )}

      {/* Create/Edit Account Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 overflow-y-auto">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 w-full max-w-2xl m-4">
            <h3 className="text-xl font-bold mb-4 text-gray-900 dark:text-white">
              {editingAccount ? 'Edit Account' : isDuplicating ? 'Duplicate Account' : 'Create New Account'}
            </h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Account ID *
                  </label>
                  <input
                    type="text"
                    required
                    disabled={!!editingAccount}
                    value={formData.account_id}
                    onChange={(e) => setFormData({ ...formData, account_id: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50"
                    placeholder="e.g., IBKR_Main"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Broker *
                  </label>
                  <select
                    value={formData.broker}
                    onChange={(e) => handleBrokerChange(e.target.value)}
                    disabled={!!editingAccount}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50"
                  >
                    <option value="IBKR">IBKR</option>
                    <option value="Binance">Binance</option>
                    <option value="Alpaca">Alpaca</option>
                    <option value="Mock">Mock</option>
                    <option value="Mock_Paper">Mock_Paper</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Fund Assignment *
                </label>
                <select
                  value={formData.fund_id}
                  onChange={(e) => setFormData({ ...formData, fund_id: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                >
                  {funds.map((fund) => (
                    <option key={fund.fund_id} value={fund.fund_id}>
                      {fund.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Asset Classes *
                </label>
                <div className="space-y-3 p-4 border border-gray-300 dark:border-gray-600 rounded-lg">
                  {(['equity', 'futures', 'crypto', 'forex'] as const).map((assetClass) => {
                    const isAll = formData.asset_classes[assetClass]?.[0] === 'all';
                    const isEnabled = formData.asset_classes[assetClass]?.length > 0;
                    const symbols = isAll ? '' : formData.asset_classes[assetClass]?.join(', ') || '';

                    return (
                      <div key={assetClass} className="border-b border-gray-200 dark:border-gray-700 pb-3 last:border-0">
                        <div className="flex items-center mb-2">
                          <input
                            type="checkbox"
                            id={`${assetClass}-all`}
                            checked={isAll}
                            onChange={(e) => handleAssetClassToggle(assetClass, e.target.checked)}
                            className="mr-2"
                          />
                          <label htmlFor={`${assetClass}-all`} className="font-medium capitalize">
                            {assetClass} - All
                          </label>
                        </div>
                        {isEnabled && !isAll && (
                          <input
                            type="text"
                            value={symbols}
                            onChange={(e) => handleAssetClassSymbols(assetClass, e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                            placeholder="Comma-separated symbols (e.g., SPY, QQQ, AAPL)"
                          />
                        )}
                      </div>
                    );
                  })}
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Check "All" to enable all symbols, or uncheck to specify individual symbols
                </p>
              </div>

              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setShowModal(false);
                    setEditingAccount(null);
                    resetForm();
                  }}
                  className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending || updateMutation.isPending}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
                >
                  {editingAccount ? 'Update' : 'Create'} Account
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
