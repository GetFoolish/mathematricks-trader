import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../services/api';
import { Plus, Edit, Trash2, Search, X, CreditCard } from 'lucide-react';
import type { TradingAccount, Fund } from '../types';

export const Accounts: React.FC = () => {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFund, setSelectedFund] = useState<string>('');
  const [selectedBroker, setSelectedBroker] = useState<string>('');
  const [showModal, setShowModal] = useState(false);
  const [editingAccount, setEditingAccount] = useState<TradingAccount | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    account_id: '',
    broker: 'Mock',
    broker_account_number: '',
    fund_id: '',
    asset_classes: {
      equity: [] as string[],
      futures: [] as string[],
      options: [] as string[],
      crypto: [] as string[],
      forex: [] as string[],
      commodities: [] as string[],
    },
    authentication_details: {
      auth_type: 'MOCK',
      initial_equity: 1000000,
    },
  });

  // Fetch accounts
  const { data: accountsData, isLoading: accountsLoading } = useQuery({
    queryKey: ['accounts'],
    queryFn: () => apiClient.getAccounts(),
  });

  const accounts = accountsData || [];

  // Fetch funds for dropdown
  const { data: fundsData } = useQuery({
    queryKey: ['funds'],
    queryFn: () => apiClient.getFunds(),
  });

  const funds = fundsData || [];

  // Create account mutation
  const createMutation = useMutation({
    mutationFn: (data: any) => apiClient.createAccount(data),
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
      broker: 'Mock',
      broker_account_number: '',
      fund_id: '',
      asset_classes: {
        equity: [],
        futures: [],
        options: [],
        crypto: [],
        forex: [],
        commodities: [],
      },
      authentication_details: {
        auth_type: 'MOCK',
        initial_equity: 1000000,
      },
    });
    setEditingAccount(null);
  };

  const handleEdit = (account: TradingAccount) => {
    setEditingAccount(account);
    setFormData({
      account_id: account.account_id,
      broker: account.broker,
      broker_account_number: account.broker_account_number || '',
      fund_id: account.fund_id || '',
      asset_classes: account.asset_classes,
      authentication_details: account.authentication_details || {
        auth_type: 'MOCK',
        initial_equity: 1000000,
      },
    });
    setShowModal(true);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (editingAccount) {
      updateMutation.mutate({
        accountId: editingAccount.account_id,
        data: {
          fund_id: formData.fund_id,
          asset_classes: formData.asset_classes,
          broker_account_number: formData.broker_account_number,
        },
      });
    } else {
      createMutation.mutate(formData);
    }
  };

  const handleDelete = (accountId: string) => {
    if (confirm(`Are you sure you want to delete account ${accountId}?`)) {
      deleteMutation.mutate(accountId);
    }
  };

  const handleAssetClassToggle = (assetClass: keyof typeof formData.asset_classes) => {
    setFormData(prev => ({
      ...prev,
      asset_classes: {
        ...prev.asset_classes,
        [assetClass]: prev.asset_classes[assetClass].includes('all')
          ? []
          : ['all'],
      },
    }));
  };

  // Filter accounts
  const filteredAccounts = accounts.filter((acc) => {
    const matchesSearch =
      acc.account_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      acc.broker.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesFund = !selectedFund || acc.fund_id === selectedFund;
    const matchesBroker = !selectedBroker || acc.broker === selectedBroker;
    return matchesSearch && matchesFund && matchesBroker;
  });

  const brokers = ['Mock', 'IBKR', 'Binance', 'Alpaca', 'Oanda', 'Bybit'];

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Trading Accounts</h1>
          <p className="text-gray-400 mt-1">Manage broker accounts and configurations</p>
        </div>
        <button
          onClick={() => {
            resetForm();
            setShowModal(true);
          }}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
        >
          <Plus className="h-5 w-5" />
          <span>Add Account</span>
        </button>
      </div>

      {/* Filters */}
      <div className="bg-gray-800 rounded-lg p-4 flex flex-wrap gap-4">
        <div className="flex-1 min-w-64">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search accounts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        <select
          value={selectedFund}
          onChange={(e) => setSelectedFund(e.target.value)}
          className="px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Funds</option>
          {funds.map((fund) => (
            <option key={fund.fund_id} value={fund.fund_id}>
              {fund.name || fund.fund_id}
            </option>
          ))}
        </select>
        <select
          value={selectedBroker}
          onChange={(e) => setSelectedBroker(e.target.value)}
          className="px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Brokers</option>
          {brokers.map((broker) => (
            <option key={broker} value={broker}>
              {broker}
            </option>
          ))}
        </select>
      </div>

      {/* Accounts Table */}
      {accountsLoading ? (
        <div className="text-center py-12 text-gray-400">Loading accounts...</div>
      ) : filteredAccounts.length === 0 ? (
        <div className="text-center py-12 text-gray-400">No accounts found</div>
      ) : (
        <div className="bg-gray-800 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-700">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                  Account ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                  Broker
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                  Fund
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                  Equity
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                  Asset Classes
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-300 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {filteredAccounts.map((account) => {
                const equity = account.balances?.equity || 0;
                const activeAssetClasses = Object.entries(account.asset_classes || {})
                  .filter(([_, val]) => Array.isArray(val) && val.length > 0)
                  .map(([key]) => key);

                return (
                  <tr key={account.account_id} className="hover:bg-gray-700/50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <CreditCard className="h-5 w-5 text-blue-400 mr-2" />
                        <span className="text-white font-medium">{account.account_id}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="text-gray-300">{account.broker}</span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="text-gray-300">{account.fund_id || '-'}</span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="text-green-400 font-medium">
                        ${equity.toLocaleString()}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-wrap gap-1">
                        {activeAssetClasses.map((ac) => (
                          <span
                            key={ac}
                            className="px-2 py-1 text-xs bg-blue-900/50 text-blue-300 rounded"
                          >
                            {ac}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`px-2 py-1 text-xs rounded ${
                          account.status === 'ACTIVE'
                            ? 'bg-green-900/50 text-green-300'
                            : 'bg-gray-600 text-gray-300'
                        }`}
                      >
                        {account.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right space-x-2">
                      <button
                        onClick={() => handleEdit(account)}
                        className="text-blue-400 hover:text-blue-300 transition-colors"
                      >
                        <Edit className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(account.account_id)}
                        className="text-red-400 hover:text-red-300 transition-colors"
                        disabled={deleteMutation.isPending}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-gray-800 rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-bold text-white">
                {editingAccount ? 'Edit Account' : 'Create Account'}
              </h2>
              <button
                onClick={() => {
                  setShowModal(false);
                  resetForm();
                }}
                className="text-gray-400 hover:text-white"
              >
                <X className="h-6 w-6" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Account ID */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Account ID *
                </label>
                <input
                  type="text"
                  value={formData.account_id}
                  onChange={(e) => setFormData({ ...formData, account_id: e.target.value })}
                  disabled={!!editingAccount}
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                  required
                />
              </div>

              {/* Broker */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Broker *
                </label>
                <select
                  value={formData.broker}
                  onChange={(e) => setFormData({ ...formData, broker: e.target.value })}
                  disabled={!!editingAccount}
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                  required
                >
                  {brokers.map((broker) => (
                    <option key={broker} value={broker}>
                      {broker}
                    </option>
                  ))}
                </select>
              </div>

              {/* Fund */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Fund</label>
                <select
                  value={formData.fund_id}
                  onChange={(e) => setFormData({ ...formData, fund_id: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">No Fund</option>
                  {funds.map((fund) => (
                    <option key={fund.fund_id} value={fund.fund_id}>
                      {fund.name || fund.fund_id}
                    </option>
                  ))}
                </select>
              </div>

              {/* Broker Account Number */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Broker Account Number
                </label>
                <input
                  type="text"
                  value={formData.broker_account_number}
                  onChange={(e) =>
                    setFormData({ ...formData, broker_account_number: e.target.value })
                  }
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Asset Classes */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Asset Classes
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {Object.keys(formData.asset_classes).map((assetClass) => (
                    <label
                      key={assetClass}
                      className="flex items-center space-x-2 text-gray-300 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={formData.asset_classes[assetClass as keyof typeof formData.asset_classes].includes('all')}
                        onChange={() =>
                          handleAssetClassToggle(assetClass as keyof typeof formData.asset_classes)
                        }
                        className="w-4 h-4 rounded bg-gray-700 border-gray-600 text-blue-600 focus:ring-blue-500"
                      />
                      <span className="capitalize">{assetClass}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Authentication Details (only for new accounts) */}
              {!editingAccount && formData.broker === 'Mock' && (
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">
                    Initial Equity
                  </label>
                  <input
                    type="number"
                    value={formData.authentication_details.initial_equity}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        authentication_details: {
                          ...formData.authentication_details,
                          initial_equity: Number(e.target.value),
                        },
                      })
                    }
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              )}

              {/* Actions */}
              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setShowModal(false);
                    resetForm();
                  }}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending || updateMutation.isPending}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50"
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
};
