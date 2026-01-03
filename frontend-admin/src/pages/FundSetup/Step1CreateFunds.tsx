import { useState } from 'react';
import { Plus, Edit2, Trash2, Building2 } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import type { Fund, CreateFundRequest } from '../../types';

interface Props {
  funds: Fund[];
  setFunds: (funds: Fund[]) => void;
}

export default function Step1CreateFunds({ funds, setFunds }: Props) {
  const [showModal, setShowModal] = useState(false);
  const [editingFund, setEditingFund] = useState<Fund | null>(null);
  const [formData, setFormData] = useState<CreateFundRequest>({
    name: '',
    description: '',
    currency: 'USD',
    accounts: [],
  });

  const queryClient = useQueryClient();

  // Fetch funds
  const { data: fetchedFunds, isLoading } = useQuery({
    queryKey: ['funds'],
    queryFn: () => apiClient.getFunds(),
  });

  // Update local state when funds are fetched
  if (fetchedFunds && fetchedFunds.length !== funds.length) {
    setFunds(fetchedFunds);
  }

  // Create fund mutation
  const createMutation = useMutation({
    mutationFn: (data: CreateFundRequest) => apiClient.createFund(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['funds'] });
      setShowModal(false);
      resetForm();
    },
  });

  // Update fund mutation
  const updateMutation = useMutation({
    mutationFn: ({ fundId, data }: { fundId: string; data: any }) =>
      apiClient.updateFund(fundId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['funds'] });
      setShowModal(false);
      setEditingFund(null);
      resetForm();
    },
  });

  // Delete fund mutation
  const deleteMutation = useMutation({
    mutationFn: (fundId: string) => apiClient.deleteFund(fundId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['funds'] });
    },
  });

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      currency: 'USD',
      accounts: [],
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (editingFund) {
      updateMutation.mutate({
        fundId: editingFund.fund_id,
        data: formData,
      });
    } else {
      createMutation.mutate(formData);
    }
  };

  const handleEdit = (fund: Fund) => {
    setEditingFund(fund);
    setFormData({
      name: fund.name,
      description: fund.description || '',
      currency: fund.currency,
      accounts: fund.accounts || [],
    });
    setShowModal(true);
  };

  const handleDelete = (fundId: string) => {
    if (confirm('Are you sure you want to delete this fund?')) {
      deleteMutation.mutate(fundId);
    }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Create Funds
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Define your top-level fund structure
          </p>
        </div>
        <button
          onClick={() => {
            setEditingFund(null);
            resetForm();
            setShowModal(true);
          }}
          className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="w-5 h-5 mr-2" />
          Add Fund
        </button>
      </div>

      {/* Funds Table */}
      {isLoading ? (
        <div className="text-center py-12 text-gray-500">Loading funds...</div>
      ) : funds.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 dark:bg-gray-900 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600">
          <Building2 className="w-16 h-16 mx-auto text-gray-400 mb-4" />
          <p className="text-gray-600 dark:text-gray-400 mb-4">
            No funds created yet
          </p>
          <button
            onClick={() => setShowModal(true)}
            className="text-blue-600 hover:text-blue-700 font-medium"
          >
            Create your first fund →
          </button>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-900">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Fund Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Fund ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Total Equity
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Currency
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Accounts
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
              {funds.map((fund) => (
                <tr key={fund.fund_id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900 dark:text-white">
                      {fund.name}
                    </div>
                    {fund.description && (
                      <div className="text-sm text-gray-500">{fund.description}</div>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {fund.fund_id}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                    ${fund.total_equity.toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {fund.currency}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {fund.accounts.length} account(s)
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 py-1 text-xs rounded-full ${
                      fund.status === 'ACTIVE'
                        ? 'bg-green-100 text-green-800'
                        : fund.status === 'PAUSED'
                        ? 'bg-yellow-100 text-yellow-800'
                        : 'bg-gray-100 text-gray-800'
                    }`}>
                      {fund.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <button
                      onClick={() => handleEdit(fund)}
                      className="text-blue-600 hover:text-blue-700 mr-3"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDelete(fund.fund_id)}
                      className="text-red-600 hover:text-red-700"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create/Edit Fund Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 w-full max-w-md">
            <h3 className="text-xl font-bold mb-4 text-gray-900 dark:text-white">
              {editingFund ? 'Edit Fund' : 'Create New Fund'}
            </h3>
            <form onSubmit={handleSubmit}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Fund Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="e.g., Mathematricks Fund 1"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Description
                  </label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    rows={3}
                    placeholder="Optional description"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Currency *
                  </label>
                  <select
                    value={formData.currency}
                    onChange={(e) => setFormData({ ...formData, currency: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  >
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                    <option value="GBP">GBP</option>
                  </select>
                </div>
              </div>

              <div className="mt-6 flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => {
                    setShowModal(false);
                    setEditingFund(null);
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
                  {editingFund ? 'Update' : 'Create'} Fund
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
