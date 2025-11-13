import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../services/api';
import { Check, Edit, Trash2, Play, TrendingUp, X, FileText } from 'lucide-react';

export const Allocations: React.FC = () => {
  const queryClient = useQueryClient();

  // State for Part 1: Edit mode
  const [isEditingCurrent, setIsEditingCurrent] = useState(false);

  // State for Part 2: Allocation Editor
  const [editorAllocations, setEditorAllocations] = useState<Record<string, number>>({});
  const [selectedTestId, setSelectedTestId] = useState<string | null>(null);
  const [targetTotalAllocation, setTargetTotalAllocation] = useState<number | null>(null);
  const [isEditingTotal, setIsEditingTotal] = useState(false);

  // State for Part 3: Table sorting
  const [sortField, setSortField] = useState<string>('created_at');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  // State for Part 4: Research Lab
  const [selectedStrategies, setSelectedStrategies] = useState<string[]>([]);
  const [selectedConstructor, setSelectedConstructor] = useState<string>('max_hybrid');
  const [isStrategyModalOpen, setIsStrategyModalOpen] = useState(false);

  // ============================================================================
  // API QUERIES
  // ============================================================================

  // Fetch current allocation (Part 1)
  const { data: currentAllocation } = useQuery({
    queryKey: ['currentAllocation'],
    queryFn: () => apiClient.getCurrentAllocation(),
  });

  // Fetch all strategies (for Part 4: Research Lab)
  const { data: strategiesData } = useQuery({
    queryKey: ['strategies'],
    queryFn: () => apiClient.getAllStrategies(),
  });

  // Fetch portfolio tests list (Part 3)
  const { data: portfolioTests, isLoading: isLoadingTests, error: testsError } = useQuery({
    queryKey: ['portfolioTests'],
    queryFn: () => apiClient.getPortfolioTests(),
  });

  // ============================================================================
  // MUTATIONS
  // ============================================================================

  // Approve allocation (Part 2 -> Part 1)
  const approveMutation = useMutation({
    mutationFn: (allocations: Record<string, number>) =>
      apiClient.approveAllocation(allocations),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['currentAllocation'] });
      setEditorAllocations({});
      setSelectedTestId(null);
    },
  });

  // Delete portfolio test (Part 3)
  const deleteTestMutation = useMutation({
    mutationFn: (testId: string) => apiClient.deletePortfolioTest(testId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolioTests'] });
      if (selectedTestId === arguments[0]) {
        setEditorAllocations({});
        setSelectedTestId(null);
      }
    },
  });

  // Run new portfolio test (Part 4)
  const runTestMutation = useMutation({
    mutationFn: (params: { strategies: string[]; constructor: string }) =>
      apiClient.runPortfolioTest(params.strategies, params.constructor),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolioTests'] });
      // Auto-scroll to Part 3 after test completes
      setTimeout(() => {
        document.querySelector('[data-part="portfolio-tests"]')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    },
  });

  // ============================================================================
  // HANDLERS
  // ============================================================================

  const handleEditCurrent = () => {
    if (currentAllocation?.allocation?.allocations) {
      // Sort once when entering edit mode, preserve order during editing
      const sortedEntries = Object.entries(currentAllocation.allocation.allocations)
        .sort(([, a], [, b]) => (b as number) - (a as number));
      const sortedAllocations = Object.fromEntries(sortedEntries);
      setEditorAllocations(sortedAllocations);
      setSelectedTestId(null);
      setIsEditingCurrent(true);
    }
  };

  const handleCancelEdit = () => {
    setIsEditingCurrent(false);
    setEditorAllocations({});
    setSelectedTestId(null);
  };

  const handleSaveEdit = () => {
    if (Object.keys(editorAllocations).length > 0) {
      approveMutation.mutate(editorAllocations);
      setIsEditingCurrent(false);
    }
  };

  const handleNormalize = () => {
    const total = getTotalAllocation();
    if (total === 0) return;

    const normalized: Record<string, number> = {};
    Object.entries(editorAllocations).forEach(([strategyId, allocation]) => {
      normalized[strategyId] = (allocation / total) * 100;
    });
    setEditorAllocations(normalized);
  };

  const handleLoadTest = (test: any) => {
    // Sort once when loading test, preserve order during editing
    const sortedEntries = Object.entries(test.allocations)
      .sort(([, a], [, b]) => (b as number) - (a as number));
    const sortedAllocations = Object.fromEntries(sortedEntries);
    setEditorAllocations(sortedAllocations);
    setSelectedTestId(test.test_id);
    setIsEditingCurrent(false);
  };

  const handleAllocationChange = (strategyId: string, value: string) => {
    const numValue = parseFloat(value) || 0;
    setEditorAllocations(prev => ({ ...prev, [strategyId]: numValue }));
  };

  const handleApprove = () => {
    if (Object.keys(editorAllocations).length > 0) {
      approveMutation.mutate(editorAllocations);
    }
  };

  const handleDeleteTest = (testId: string) => {
    if (confirm('Are you sure you want to delete this test?')) {
      deleteTestMutation.mutate(testId);
    }
  };

  const handleRunTest = () => {
    if (selectedStrategies.length === 0) {
      alert('Please select at least one strategy');
      return;
    }
    runTestMutation.mutate({
      strategies: selectedStrategies,
      constructor: selectedConstructor,
    });
  };

  const toggleStrategy = (strategyId: string) => {
    setSelectedStrategies(prev =>
      prev.includes(strategyId)
        ? prev.filter(id => id !== strategyId)
        : [...prev, strategyId]
    );
  };

  const getTotalAllocation = () => {
    return Object.values(editorAllocations).reduce((sum, val) => sum + val, 0);
  };

  const strategies = strategiesData || [];
  const tests = portfolioTests?.tests || [];

  // Sort tests
  const sortedTests = [...tests].sort((a, b) => {
    let aVal, bVal;

    switch (sortField) {
      case 'cagr':
        aVal = a.performance?.cagr || 0;
        bVal = b.performance?.cagr || 0;
        break;
      case 'sharpe':
        aVal = a.performance?.sharpe || 0;
        bVal = b.performance?.sharpe || 0;
        break;
      case 'max_drawdown':
        aVal = a.performance?.max_drawdown || 0;
        bVal = b.performance?.max_drawdown || 0;
        break;
      case 'volatility':
        aVal = a.performance?.volatility || 0;
        bVal = b.performance?.volatility || 0;
        break;
      case 'num_strategies':
        aVal = a.strategies?.length || 0;
        bVal = b.strategies?.length || 0;
        break;
      case 'created_at':
        aVal = new Date(a.created_at).getTime();
        bVal = new Date(b.created_at).getTime();
        break;
      default:
        aVal = 0;
        bVal = 0;
    }

    return sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
  });

  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  return (
    <div className="space-y-6">
      {/* ====================================================================== */}
      {/* PART 1: CURRENT ALLOCATION                                            */}
      {/* ====================================================================== */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-bold text-white">Part 1: Current Allocation</h3>
          {currentAllocation?.allocation && !isEditingCurrent && (
            <button
              onClick={handleEditCurrent}
              className="btn-secondary flex items-center gap-2"
            >
              <Edit className="h-4 w-4" />
              Edit
            </button>
          )}
          {isEditingCurrent && (
            <div className="flex gap-2">
              <button
                onClick={handleCancelEdit}
                className="btn-secondary flex items-center gap-2"
              >
                <X className="h-4 w-4" />
                Cancel
              </button>
              <button
                onClick={handleSaveEdit}
                disabled={approveMutation.isPending || getTotalAllocation() === 0}
                className="btn-success flex items-center gap-2"
              >
                <Check className="h-4 w-4" />
                {approveMutation.isPending ? 'Saving...' : 'Save'}
              </button>
            </div>
          )}
        </div>

        {(isEditingCurrent ? Object.keys(editorAllocations).length > 0 : currentAllocation?.allocation?.allocations) ? (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-4 pb-4 border-b border-gray-700">
              <div>
                <p className="text-sm text-gray-400">Total Allocation</p>
                <p className="text-white font-bold text-xl">
                  {isEditingCurrent
                    ? getTotalAllocation().toFixed(1)
                    : Object.values(currentAllocation.allocation.allocations).reduce((sum, val) => sum + val, 0).toFixed(1)
                  }%
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-400">Number of Strategies</p>
                <p className="text-white font-bold text-xl">
                  {isEditingCurrent
                    ? Object.keys(editorAllocations).length
                    : Object.keys(currentAllocation.allocation.allocations).length
                  }
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-400">Last Updated</p>
                <p className="text-white font-medium">
                  {new Date(currentAllocation.allocation.updated_at).toLocaleString()}
                </p>
              </div>
            </div>

            {isEditingCurrent && (
              <button
                onClick={handleNormalize}
                className="btn-secondary text-sm"
              >
                Normalize to 100%
              </button>
            )}

            <div className="space-y-3">
              {Object.entries(isEditingCurrent ? editorAllocations : currentAllocation.allocation.allocations)
                .sort(isEditingCurrent ? () => 0 : ([, a], [, b]) => (b as number) - (a as number))
                .map(([strategyId, allocation]) => (
                  <div key={strategyId}>
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-white font-medium">{strategyId}</p>
                      <span className="text-white font-semibold w-20 text-right">
                        {(allocation as number).toFixed(1)}%
                      </span>
                    </div>
                    {isEditingCurrent ? (
                      <input
                        type="range"
                        value={allocation as number}
                        onChange={(e) => handleAllocationChange(strategyId, e.target.value)}
                        min="0"
                        max="100"
                        step="0.1"
                        className="w-full h-2.5 bg-gray-700 rounded-full appearance-none cursor-pointer accent-blue-500"
                      />
                    ) : (
                      <div className="bg-gray-700 rounded-full h-2.5 overflow-hidden">
                        <div
                          className="bg-green-500 h-full transition-all"
                          style={{ width: `${(allocation as number)}%` }}
                        />
                      </div>
                    )}
                  </div>
                ))}
            </div>
          </div>
        ) : (
          <div className="text-center py-12">
            <p className="text-gray-400 mb-2">No active allocation found</p>
            <p className="text-sm text-gray-500">Run a test in Research Lab and approve it to set current allocation</p>
          </div>
        )}
      </div>

      {/* ====================================================================== */}
      {/* PART 2: ALLOCATION EDITOR                                             */}
      {/* ====================================================================== */}
      {!isEditingCurrent && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xl font-bold text-white">Part 2: Allocation Editor</h3>
            {Object.keys(editorAllocations).length > 0 && (
              <button
                onClick={handleApprove}
                disabled={approveMutation.isPending || getTotalAllocation() === 0}
                className="btn-success flex items-center gap-2"
              >
                <Check className="h-4 w-4" />
                {approveMutation.isPending ? 'Approving...' : 'Approve'}
              </button>
            )}
          </div>

          {Object.keys(editorAllocations).length > 0 ? (
            <div className="space-y-4">
              {/* Total Allocation Display */}
              <div className="grid grid-cols-3 gap-4 pb-4 border-b border-gray-700">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <p className="text-sm text-gray-400">Total Allocation</p>
                    {!isEditingTotal && (
                      <button
                        onClick={() => {
                          setTargetTotalAllocation(getTotalAllocation());
                          setIsEditingTotal(true);
                        }}
                        className="p-0.5 hover:bg-gray-700 rounded"
                        title="Edit total allocation"
                      >
                        <Edit className="h-3 w-3 text-gray-400 hover:text-white" />
                      </button>
                    )}
                  </div>
                  {isEditingTotal ? (
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        value={targetTotalAllocation || ''}
                        onChange={(e) => setTargetTotalAllocation(parseFloat(e.target.value) || 0)}
                        className="w-24 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xl font-bold"
                        step="0.1"
                        min="0"
                        max="300"
                        autoFocus
                      />
                      <span className="text-xl font-bold text-gray-400">%</span>
                      <button
                        onClick={() => {
                          if (targetTotalAllocation && targetTotalAllocation > 0) {
                            // Scale all allocations proportionally
                            const currentTotal = getTotalAllocation();
                            const scaleFactor = targetTotalAllocation / currentTotal;
                            const scaledAllocations: Record<string, number> = {};
                            Object.entries(editorAllocations).forEach(([strategyId, allocation]) => {
                              scaledAllocations[strategyId] = allocation * scaleFactor;
                            });
                            setEditorAllocations(scaledAllocations);
                          }
                          setIsEditingTotal(false);
                        }}
                        className="p-1 bg-green-600 hover:bg-green-700 rounded"
                        title="Apply"
                      >
                        <Check className="h-4 w-4 text-white" />
                      </button>
                      <button
                        onClick={() => {
                          setIsEditingTotal(false);
                          setTargetTotalAllocation(null);
                        }}
                        className="p-1 bg-gray-600 hover:bg-gray-700 rounded"
                        title="Cancel"
                      >
                        <X className="h-4 w-4 text-white" />
                      </button>
                    </div>
                  ) : (
                    <p className={`font-bold text-xl ${
                      getTotalAllocation() > 230 ? 'text-red-400' :
                      getTotalAllocation() > 200 ? 'text-yellow-400' :
                      'text-green-400'
                    }`}>
                      {getTotalAllocation().toFixed(1)}%
                    </p>
                  )}
                </div>
                <div>
                  <p className="text-sm text-gray-400">Number of Strategies</p>
                  <p className="text-white font-bold text-xl">
                    {Object.keys(editorAllocations).length}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-400">Source</p>
                  <p className="text-white font-medium">
                    {selectedTestId || 'Current Allocation'}
                  </p>
                </div>
              </div>

              {getTotalAllocation() > 230 && (
                <div className="p-3 bg-red-900/30 border border-red-500 rounded-lg">
                  <p className="text-red-400 text-sm">⚠️ Total exceeds maximum leverage (230%)</p>
                </div>
              )}

              <button
                onClick={handleNormalize}
                className="btn-secondary text-sm"
              >
                Normalize to 100%
              </button>

              {/* Editable Strategy Allocations with Sliders */}
              <div className="space-y-3">
                {Object.entries(editorAllocations)
                  .map(([strategyId, allocation]) => (
                    <div key={strategyId}>
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-white font-medium">{strategyId}</p>
                        <span className="text-white font-semibold w-20 text-right">
                          {allocation.toFixed(1)}%
                        </span>
                      </div>
                      <input
                        type="range"
                        value={allocation}
                        onChange={(e) => handleAllocationChange(strategyId, e.target.value)}
                        min="0"
                        max="100"
                        step="0.1"
                        className="w-full h-2.5 bg-gray-700 rounded-full appearance-none cursor-pointer accent-blue-500"
                      />
                    </div>
                  ))}
              </div>
            </div>
          ) : (
            <div className="text-center py-12">
              <p className="text-gray-400 mb-2">No allocation loaded</p>
              <p className="text-sm text-gray-500">Click "Edit" on Current Allocation or select a test from Portfolio Tests List</p>
            </div>
          )}
        </div>
      )}

      {/* ====================================================================== */}
      {/* PART 3: PORTFOLIO TESTS LIST                                          */}
      {/* ====================================================================== */}
      <div className="card" data-part="portfolio-tests">
        <h3 className="text-xl font-bold text-white mb-4">Part 3: Portfolio Tests List</h3>

        {isLoadingTests ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mb-3"></div>
            <p className="text-gray-400">Loading portfolio tests...</p>
          </div>
        ) : testsError ? (
          <div className="text-center py-12">
            <p className="text-red-400 mb-2">❌ Error loading tests</p>
            <p className="text-sm text-gray-500">{(testsError as any)?.message || 'Unknown error occurred'}</p>
          </div>
        ) : tests.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-700">
                  <th className="text-left p-3 text-gray-400 font-medium text-sm">Test ID</th>
                  <th className="text-left p-3 text-gray-400 font-medium text-sm">Constructor</th>
                  <th
                    className="text-left p-3 text-gray-400 font-medium text-sm cursor-pointer hover:text-white"
                    onClick={() => handleSort('num_strategies')}
                    title="Click to sort"
                  >
                    <div className="flex items-center gap-1">
                      # Strategies {sortField === 'num_strategies' && (sortDirection === 'asc' ? '↑' : '↓')}
                    </div>
                  </th>
                  <th
                    className="text-right p-3 text-gray-400 font-medium text-sm cursor-pointer hover:text-white"
                    onClick={() => handleSort('cagr')}
                    title="Click to sort"
                  >
                    <div className="flex items-center justify-end gap-1">
                      CAGR % {sortField === 'cagr' && (sortDirection === 'asc' ? '↑' : '↓')}
                    </div>
                  </th>
                  <th
                    className="text-right p-3 text-gray-400 font-medium text-sm cursor-pointer hover:text-white"
                    onClick={() => handleSort('sharpe')}
                    title="Click to sort"
                  >
                    <div className="flex items-center justify-end gap-1">
                      Sharpe {sortField === 'sharpe' && (sortDirection === 'asc' ? '↑' : '↓')}
                    </div>
                  </th>
                  <th
                    className="text-right p-3 text-gray-400 font-medium text-sm cursor-pointer hover:text-white"
                    onClick={() => handleSort('max_drawdown')}
                    title="Click to sort"
                  >
                    <div className="flex items-center justify-end gap-1">
                      Max DD % {sortField === 'max_drawdown' && (sortDirection === 'asc' ? '↑' : '↓')}
                    </div>
                  </th>
                  <th
                    className="text-right p-3 text-gray-400 font-medium text-sm cursor-pointer hover:text-white"
                    onClick={() => handleSort('volatility')}
                    title="Click to sort"
                  >
                    <div className="flex items-center justify-end gap-1">
                      Vol % {sortField === 'volatility' && (sortDirection === 'asc' ? '↑' : '↓')}
                    </div>
                  </th>
                  <th
                    className="text-left p-3 text-gray-400 font-medium text-sm cursor-pointer hover:text-white"
                    onClick={() => handleSort('created_at')}
                    title="Click to sort"
                  >
                    <div className="flex items-center gap-1">
                      Created {sortField === 'created_at' && (sortDirection === 'asc' ? '↑' : '↓')}
                    </div>
                  </th>
                  <th className="text-center p-3 text-gray-400 font-medium text-sm">Actions</th>
                </tr>
              </thead>
              <tbody>
                {sortedTests.map((test: any) => (
                  <tr
                    key={test.test_id}
                    className={`border-b border-gray-700/50 cursor-pointer transition-colors ${
                      selectedTestId === test.test_id
                        ? 'bg-blue-900/20'
                        : 'hover:bg-gray-700/30'
                    }`}
                    onClick={() => handleLoadTest(test)}
                  >
                    <td className="p-3 text-white font-mono text-sm">{test.test_id}</td>
                    <td className="p-3 text-white">{test.constructor}</td>
                    <td className="p-3 text-white" title={test.strategies?.join(', ')}>
                      <span className="cursor-help">{test.strategies?.length || 0}</span>
                    </td>
                    <td className={`p-3 text-right font-semibold ${
                      (test.performance?.cagr || 0) > 50 ? 'text-green-400' :
                      (test.performance?.cagr || 0) > 20 ? 'text-blue-400' :
                      'text-white'
                    }`}>
                      {test.performance?.cagr ? test.performance.cagr.toFixed(1) : '-'}
                    </td>
                    <td className={`p-3 text-right font-semibold ${
                      (test.performance?.sharpe || 0) > 2 ? 'text-green-400' :
                      (test.performance?.sharpe || 0) > 1 ? 'text-blue-400' :
                      'text-white'
                    }`}>
                      {test.performance?.sharpe ? test.performance.sharpe.toFixed(2) : '-'}
                    </td>
                    <td className="p-3 text-right text-red-400">
                      {test.performance?.max_drawdown ? test.performance.max_drawdown.toFixed(1) : '-'}
                    </td>
                    <td className="p-3 text-right text-white">
                      {test.performance?.volatility ? test.performance.volatility.toFixed(1) : '-'}
                    </td>
                    <td className="p-3 text-white text-sm">
                      {new Date(test.created_at).toLocaleString()}
                    </td>
                    <td className="p-3">
                      <div className="flex items-center justify-center gap-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            window.open(`http://localhost:8003/api/v1/portfolio-tests/${test.test_id}/tearsheet`, '_blank');
                          }}
                          className="text-blue-400 hover:text-blue-300 transition-colors"
                          title="View Tearsheet"
                        >
                          <FileText className="h-4 w-4" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteTest(test.test_id);
                          }}
                          disabled={deleteTestMutation.isPending}
                          className="text-red-400 hover:text-red-300 transition-colors"
                          title="Delete test"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-12">
            <p className="text-gray-400 mb-2">No portfolio tests found</p>
            <p className="text-sm text-gray-500">Run a test in Research Lab below to get started</p>
          </div>
        )}
      </div>

      {/* ====================================================================== */}
      {/* PART 4: RESEARCH LAB                                                  */}
      {/* ====================================================================== */}
      <div className="card">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-xl font-bold text-white flex items-center gap-2">
              <TrendingUp className="h-6 w-6 text-blue-500" />
              Part 4: Research Lab
            </h3>
            <p className="text-sm text-gray-400 mt-1">Select strategies and run portfolio optimization tests</p>
          </div>
          <button
            onClick={handleRunTest}
            disabled={runTestMutation.isPending || selectedStrategies.length === 0}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-semibold transition-all ${
              runTestMutation.isPending
                ? 'bg-yellow-600 text-white cursor-wait'
                : selectedStrategies.length === 0
                ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-500 text-white'
            }`}
          >
            <Play className={`h-4 w-4 ${runTestMutation.isPending ? 'animate-spin' : ''}`} />
            {runTestMutation.isPending ? 'Running Test...' : 'Run Test'}
          </button>
        </div>

        {/* Loading/Success Banner */}
        {runTestMutation.isPending && (
          <div className="mb-4 p-4 bg-yellow-900/30 border border-yellow-500 rounded-lg">
            <div className="flex items-center gap-3">
              <div className="animate-spin h-5 w-5 border-2 border-yellow-500 border-t-transparent rounded-full"></div>
              <div>
                <p className="text-yellow-400 font-semibold">Test is running...</p>
                <p className="text-sm text-yellow-300">
                  Optimizing portfolio with {selectedStrategies.length} strategies using {selectedConstructor}
                </p>
              </div>
            </div>
          </div>
        )}

        {runTestMutation.isSuccess && !runTestMutation.isPending && (
          <div className="mb-4 p-4 bg-green-900/30 border border-green-500 rounded-lg">
            <p className="text-green-400 font-semibold">✅ Test completed successfully!</p>
            <p className="text-sm text-green-300 mt-1">Results added to Portfolio Tests List above</p>
          </div>
        )}

        {runTestMutation.isError && (
          <div className="mb-4 p-4 bg-red-900/30 border border-red-500 rounded-lg">
            <p className="text-red-400 font-semibold">❌ Test Failed</p>
            <p className="text-sm text-red-300 mt-1">
              {(runTestMutation.error as any)?.message || 'Unknown error occurred'}
            </p>
          </div>
        )}

        {/* Constructor Selection */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Portfolio Constructor
          </label>
          <select
            value={selectedConstructor}
            onChange={(e) => setSelectedConstructor(e.target.value)}
            className="input w-full max-w-xs"
          >
            <option value="max_hybrid">MaxHybrid - Balanced Sharpe + CAGR</option>
            <option value="max_sharpe">MaxSharpe - Risk-Adjusted Returns</option>
            <option value="max_cagr">MaxCAGR - Maximum Growth</option>
            <option value="max_cagr_v2">MaxCAGR v2 - Growth Optimized</option>
            <option value="max_cagr_sharpe">MaxCAGR+Sharpe - Hybrid Growth</option>
          </select>
        </div>

        {/* Strategy Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-3">
            Selected Strategies ({selectedStrategies.length})
          </label>
          <div className="space-y-3">
            {selectedStrategies.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {selectedStrategies.map((strategyId) => (
                  <div
                    key={strategyId}
                    className="px-3 py-2 bg-blue-900/30 border border-blue-500 rounded-lg flex items-center gap-2"
                  >
                    <span className="text-blue-400 font-medium">{strategyId}</span>
                    <button
                      onClick={() => toggleStrategy(strategyId)}
                      className="text-blue-400 hover:text-blue-300"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 text-sm">No strategies selected</p>
            )}
            <button
              onClick={() => setIsStrategyModalOpen(true)}
              className="btn-secondary"
            >
              Select Strategies
            </button>
          </div>
        </div>
      </div>

      {/* ====================================================================== */}
      {/* STRATEGY SELECTION MODAL                                              */}
      {/* ====================================================================== */}
      {isStrategyModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-800 rounded-lg shadow-xl max-w-3xl w-full max-h-[80vh] flex flex-col">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-700">
              <h3 className="text-xl font-bold text-white">Select Strategies</h3>
              <button
                onClick={() => setIsStrategyModalOpen(false)}
                className="text-gray-400 hover:text-white"
              >
                <X className="h-6 w-6" />
              </button>
            </div>

            {/* Modal Body - Scrollable */}
            <div className="flex-1 overflow-y-auto p-6">
              {strategies.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-gray-400">No strategies available</p>
                  <p className="text-sm text-gray-500 mt-2">
                    Add strategies in the Strategies tab first
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {strategies.map((strategy: any) => (
                  <div
                    key={strategy.strategy_id}
                    onClick={() => toggleStrategy(strategy.strategy_id)}
                    className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                      selectedStrategies.includes(strategy.strategy_id)
                        ? 'border-blue-500 bg-blue-900/20'
                        : 'border-gray-700 hover:border-gray-600 hover:bg-gray-700/50'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 ${
                        selectedStrategies.includes(strategy.strategy_id)
                          ? 'border-blue-500 bg-blue-500'
                          : 'border-gray-600'
                      }`}>
                        {selectedStrategies.includes(strategy.strategy_id) && (
                          <Check className="h-3 w-3 text-white" />
                        )}
                      </div>
                      <div className="flex-1">
                        <p className="text-white font-medium">{strategy.strategy_id}</p>
                        <div className="flex items-center gap-3 mt-1">
                          <p className="text-xs text-gray-400">{strategy.asset_class || 'Unknown'}</p>
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                            strategy.status === 'ACTIVE'
                              ? 'bg-green-900/30 text-green-400'
                              : 'bg-gray-700 text-gray-400'
                          }`}>
                            {strategy.status}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                  ))}
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-6 border-t border-gray-700 flex justify-between items-center">
              <p className="text-gray-400 text-sm">
                {selectedStrategies.length} strateg{selectedStrategies.length === 1 ? 'y' : 'ies'} selected
              </p>
              <button
                onClick={() => setIsStrategyModalOpen(false)}
                className="btn-primary"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
