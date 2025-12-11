import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../services/api';
import { Plus, Edit, Trash2, RefreshCw, Search, X } from 'lucide-react';
import type { Strategy } from '../types';

export const Strategies: React.FC = () => {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editingStrategy, setEditingStrategy] = useState<Strategy | null>(null);
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());

  // Fetch all strategies
  const { data: strategies, isLoading } = useQuery({
    queryKey: ['strategies'],
    queryFn: () => apiClient.getAllStrategies(),
  });

  // Create strategy mutation
  const createMutation = useMutation({
    mutationFn: (data: Partial<Strategy>) => apiClient.createStrategy(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
      setShowModal(false);
      setEditingStrategy(null);
    },
  });

  // Update strategy mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Strategy> }) =>
      apiClient.updateStrategy(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
    },
  });

  // Delete strategy mutation with optimistic update
  const deleteMutation = useMutation({
    mutationFn: (strategyId: string) => apiClient.deleteStrategy(strategyId),
    onMutate: async (strategyId) => {
      // Mark as deleting for animation
      setDeletingIds(prev => new Set(prev).add(strategyId));

      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['strategies'] });

      // Snapshot previous value
      const previousStrategies = queryClient.getQueryData<Strategy[]>(['strategies']);

      // Optimistically remove from UI after animation starts
      setTimeout(() => {
        queryClient.setQueryData<Strategy[]>(['strategies'], (old) =>
          old?.filter((s) => s.strategy_id !== strategyId)
        );
      }, 300); // Match animation duration

      return { previousStrategies };
    },
    onError: (err, strategyId, context) => {
      // Rollback on error
      if (context?.previousStrategies) {
        queryClient.setQueryData(['strategies'], context.previousStrategies);
      }
      setDeletingIds(prev => {
        const next = new Set(prev);
        next.delete(strategyId);
        return next;
      });
    },
    onSuccess: (data, strategyId) => {
      // Remove from deleting set after animation completes
      setTimeout(() => {
        setDeletingIds(prev => {
          const next = new Set(prev);
          next.delete(strategyId);
          return next;
        });
      }, 300);
    },
    onSettled: () => {
      // Refetch to ensure sync with server
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
    },
  });

  const filteredStrategies = strategies?.filter(
    (s) =>
      s.strategy_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleToggleStatus = (strategy: Strategy) => {
    const newStatus = strategy.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE';
    updateMutation.mutate({
      id: strategy.strategy_id,
      data: { status: newStatus },
    });
  };

  const handleToggleMode = (strategy: Strategy) => {
    const newMode = strategy.trading_mode === 'LIVE' ? 'PAPER' : 'LIVE';
    updateMutation.mutate({
      id: strategy.strategy_id,
      data: { trading_mode: newMode },
    });
  };

  const handleToggleOptimization = (strategy: Strategy) => {
    updateMutation.mutate({
      id: strategy.strategy_id,
      data: { include_in_optimization: !strategy.include_in_optimization },
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-white text-xl">Loading strategies...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with Search and Add Button */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex-1 max-w-md relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search strategies..."
            className="input pl-10"
          />
        </div>
        <button
          onClick={() => {
            setEditingStrategy(null);
            setShowModal(true);
          }}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          Add Strategy
        </button>
      </div>

      {/* Strategies Table */}
      <div className="card">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr>
                <th className="table-header">Strategy ID</th>
                <th className="table-header">Asset Class</th>
                <th className="table-header">Status</th>
                <th className="table-header">Trading Mode</th>
                <th className="table-header">Account</th>
                <th className="table-header">In Optimization</th>
                <th className="table-header">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {filteredStrategies?.map((strategy) => (
                <tr
                  key={strategy.strategy_id}
                  className={`hover:bg-gray-700/50 transition-all duration-300 ${
                    deletingIds.has(strategy.strategy_id)
                      ? 'opacity-0 scale-95 bg-red-900/20'
                      : 'opacity-100 scale-100'
                  }`}
                >
                  <td className="table-cell font-mono text-xs">{strategy.strategy_id}</td>
                  <td className="table-cell">{strategy.asset_class}</td>
                  <td className="table-cell">
                    <button
                      onClick={() => handleToggleStatus(strategy)}
                      disabled={updateMutation.isPending}
                      className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                        strategy.status === 'ACTIVE'
                          ? 'bg-green-900/30 text-green-400 hover:bg-green-900/50'
                          : strategy.status === 'TESTING'
                          ? 'bg-yellow-900/30 text-yellow-400 hover:bg-yellow-900/50'
                          : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                      }`}
                    >
                      {strategy.status}
                    </button>
                  </td>
                  <td className="table-cell">
                    <button
                      onClick={() => handleToggleMode(strategy)}
                      disabled={updateMutation.isPending}
                      className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                        strategy.trading_mode === 'LIVE'
                          ? 'bg-blue-900/30 text-blue-400 hover:bg-blue-900/50'
                          : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                      }`}
                    >
                      {strategy.trading_mode || 'PAPER'}
                    </button>
                  </td>
                  <td className="table-cell text-sm">{strategy.account || 'N/A'}</td>
                  <td className="table-cell">
                    <button
                      onClick={() => handleToggleOptimization(strategy)}
                      disabled={updateMutation.isPending}
                      className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                        strategy.include_in_optimization
                          ? 'bg-green-900/30 text-green-400 hover:bg-green-900/50'
                          : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                      }`}
                    >
                      {strategy.include_in_optimization ? 'Yes' : 'No'}
                    </button>
                  </td>
                  <td className="table-cell">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => {
                          setEditingStrategy(strategy);
                          setShowModal(true);
                        }}
                        className="p-2 hover:bg-gray-700 rounded transition-colors"
                        title="Edit"
                      >
                        <Edit className="h-4 w-4 text-gray-400" />
                      </button>
                      <button
                        onClick={() => {
                          if (confirm(`Delete strategy ${strategy.strategy_id}?`)) {
                            deleteMutation.mutate(strategy.strategy_id);
                          }
                        }}
                        className="p-2 hover:bg-gray-700 rounded transition-colors"
                        title="Delete"
                        disabled={deleteMutation.isPending}
                      >
                        <Trash2 className="h-4 w-4 text-red-400" />
                      </button>
                      <button
                        className="p-2 hover:bg-gray-700 rounded transition-colors"
                        title="Sync Backtest"
                      >
                        <RefreshCw className="h-4 w-4 text-blue-400" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {filteredStrategies?.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-400 text-lg">No strategies found</p>
            <p className="text-gray-500 text-sm mt-2">
              {searchQuery ? 'Try a different search term' : 'Add your first strategy to get started'}
            </p>
          </div>
        )}
      </div>

      {/* Add/Edit Strategy Modal */}
      {showModal && (
        <StrategyModal
          strategy={editingStrategy}
          onClose={() => {
            setShowModal(false);
            setEditingStrategy(null);
          }}
          onSave={(data) => {
            if (editingStrategy) {
              updateMutation.mutate({ id: editingStrategy.strategy_id, data });
            } else {
              createMutation.mutate(data);
            }
          }}
          isLoading={createMutation.isPending || updateMutation.isPending}
        />
      )}
    </div>
  );
};

// Strategy Modal Component
interface StrategyModalProps {
  strategy: Strategy | null;
  onClose: () => void;
  onSave: (data: Partial<Strategy>) => void;
  isLoading: boolean;
}

const StrategyModal: React.FC<StrategyModalProps> = ({ strategy, onClose, onSave, isLoading }) => {
  const [formData, setFormData] = useState<Partial<Strategy>>({
    strategy_id: strategy?.strategy_id || '',
    name: strategy?.name || '',
    asset_class: strategy?.asset_class || '',
    instruments: strategy?.instruments || [],
    status: strategy?.status || 'ACTIVE',
    trading_mode: strategy?.trading_mode || 'PAPER',
    account: strategy?.account || 'IBKR_Main',
    include_in_optimization: strategy?.include_in_optimization ?? true,
    risk_limits: strategy?.risk_limits || {},
    developer_contact: strategy?.developer_contact || '',
    notes: strategy?.notes || '',
  });

  const [instrumentsInput, setInstrumentsInput] = useState(
    strategy?.instruments?.join(', ') || ''
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const instruments = instrumentsInput
      .split(',')
      .map((i) => i.trim())
      .filter((i) => i);

    onSave({
      ...formData,
      instruments,
    });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-bold text-white">
            {strategy ? 'Edit Strategy' : 'Add New Strategy'}
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="h-6 w-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Strategy ID */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Strategy ID <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={formData.strategy_id}
              onChange={(e) => setFormData({ ...formData, strategy_id: e.target.value })}
              required
              disabled={!!strategy}
              className="input"
              placeholder="e.g., SPX_1-D_Opt"
            />
          </div>

          {/* Strategy Name */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Strategy Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
              className="input"
              placeholder="e.g., S&P 500 1-Day Options"
            />
          </div>

          {/* Asset Class */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Asset Class <span className="text-red-500">*</span>
            </label>
            <select
              value={formData.asset_class}
              onChange={(e) => setFormData({ ...formData, asset_class: e.target.value })}
              required
              className="input"
            >
              <option value="">Select asset class</option>
              <option value="equities">Equities</option>
              <option value="options">Options</option>
              <option value="futures">Futures</option>
              <option value="forex">Forex</option>
              <option value="crypto">Crypto</option>
              <option value="commodities">Commodities</option>
            </select>
          </div>

          {/* Instruments */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Instruments <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={instrumentsInput}
              onChange={(e) => setInstrumentsInput(e.target.value)}
              required
              className="input"
              placeholder="e.g., ES, SPX, SPY (comma-separated)"
            />
            <p className="text-xs text-gray-400 mt-1">Separate multiple instruments with commas</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Status */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Status</label>
              <select
                value={formData.status}
                onChange={(e) =>
                  setFormData({ ...formData, status: e.target.value as Strategy['status'] })
                }
                className="input"
              >
                <option value="ACTIVE">ACTIVE</option>
                <option value="INACTIVE">INACTIVE</option>
                <option value="TESTING">TESTING</option>
              </select>
            </div>

            {/* Trading Mode */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Trading Mode</label>
              <select
                value={formData.trading_mode}
                onChange={(e) =>
                  setFormData({ ...formData, trading_mode: e.target.value as 'LIVE' | 'PAPER' })
                }
                className="input"
              >
                <option value="PAPER">PAPER</option>
                <option value="LIVE">LIVE</option>
              </select>
            </div>
          </div>

          {/* Account */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Account</label>
            <select
              value={formData.account}
              onChange={(e) => setFormData({ ...formData, account: e.target.value })}
              className="input"
            >
              <option value="IBKR_Main">IBKR_Main</option>
              <option value="IBKR_Futures">IBKR_Futures</option>
              <option value="Binance_Main">Binance_Main</option>
            </select>
          </div>

          {/* Include in Optimization */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="include_in_optimization"
              checked={formData.include_in_optimization}
              onChange={(e) =>
                setFormData({ ...formData, include_in_optimization: e.target.checked })
              }
              className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
            />
            <label htmlFor="include_in_optimization" className="text-sm text-gray-300">
              Include in portfolio optimization
            </label>
          </div>

          {/* Developer Contact */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Developer Contact
            </label>
            <input
              type="email"
              value={formData.developer_contact}
              onChange={(e) => setFormData({ ...formData, developer_contact: e.target.value })}
              className="input"
              placeholder="developer@example.com"
            />
          </div>

          {/* Notes */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Notes</label>
            <textarea
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              className="input"
              rows={3}
              placeholder="Additional notes..."
            />
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <button type="submit" disabled={isLoading} className="btn-primary flex-1">
              {isLoading ? 'Saving...' : strategy ? 'Update Strategy' : 'Create Strategy'}
            </button>
            <button type="button" onClick={onClose} disabled={isLoading} className="btn-secondary">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
