import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../services/api';
import { Check, X, Edit, ChevronDown, ChevronRight, TrendingUp, BarChart, ExternalLink, FileText } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

export const Allocations: React.FC = () => {
  const queryClient = useQueryClient();
  const [showApproveModal, setShowApproveModal] = useState(false);
  const [approverName, setApproverName] = useState('');
  const [expandedAllocationId, setExpandedAllocationId] = useState<string | null>(null);
  const [selectedAllocationForApproval, setSelectedAllocationForApproval] = useState<any>(null);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editedAllocations, setEditedAllocations] = useState<Record<string, number>>({});
  const [allocationName, setAllocationName] = useState('');
  const [simulationResults, setSimulationResults] = useState<Record<string, any>>({});
  const [simulationErrors, setSimulationErrors] = useState<Record<string, string>>({});
  const [tearsheetResults, setTearsheetResults] = useState<Record<string, any>>({});
  const [tearsheetErrors, setTearsheetErrors] = useState<Record<string, string>>({});

  // Fetch current allocation
  const { data: currentAllocation } = useQuery({
    queryKey: ['currentAllocation'],
    queryFn: () => apiClient.getCurrentAllocation(),
  });

  // Fetch latest recommendation
  const { data: latestRecommendation } = useQuery({
    queryKey: ['latestRecommendation'],
    queryFn: () => apiClient.getLatestRecommendation(),
  });

  // Fetch allocation history
  const { data: allocationHistory } = useQuery({
    queryKey: ['allocationHistory'],
    queryFn: () => apiClient.getAllocationHistory(20),
  });

  // Fetch latest optimization run (for correlation matrix)
  const { data: optimizationRun } = useQuery({
    queryKey: ['latestOptimizationRun'],
    queryFn: () => apiClient.getLatestOptimizationRun(),
  });

  // Fetch all strategies (for tearsheet URLs)
  const { data: strategies } = useQuery({
    queryKey: ['strategies'],
    queryFn: () => apiClient.getAllStrategies(),
  });

  // Approve allocation mutation
  const approveMutation = useMutation({
    mutationFn: (data: { allocationId: string; approvedBy: string }) =>
      apiClient.approveAllocation(data.allocationId, data.approvedBy),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['currentAllocation'] });
      queryClient.invalidateQueries({ queryKey: ['latestRecommendation'] });
      queryClient.invalidateQueries({ queryKey: ['allocationHistory'] });
      setShowApproveModal(false);
      setApproverName('');
    },
  });

  // Create custom allocation mutation (PENDING_APPROVAL)
  const createCustomAllocationMutation = useMutation({
    mutationFn: (data: { allocations: Record<string, number>; createdBy: string; notes?: string }) =>
      apiClient.createCustomAllocation(data.allocations, data.createdBy, data.notes),
    onSuccess: (data) => {
      console.log('✅ Custom allocation created:', data);
      queryClient.invalidateQueries({ queryKey: ['currentAllocation'] });
      queryClient.invalidateQueries({ queryKey: ['latestRecommendation'] });
      queryClient.invalidateQueries({ queryKey: ['allocationHistory'] });
      setShowEditModal(false);
      setShowApproveModal(false);
      setApproverName('');
      setEditedAllocations({});
      setAllocationName('');
    },
    onError: (error: any) => {
      console.error('❌ Failed to create custom allocation:', error);
      alert(`Failed to create allocation: ${error?.response?.data?.detail || error.message || 'Unknown error'}`);
    },
  });

  // Simulation mutation
  const simulationMutation = useMutation({
    mutationFn: (allocationId: string) => apiClient.simulateAllocation(allocationId),
    onSuccess: (data, allocationId) => {
      setSimulationResults(prev => ({ ...prev, [allocationId]: data }));
      setSimulationErrors(prev => ({ ...prev, [allocationId]: '' }));
    },
    onError: (error: any, allocationId) => {
      const errorMsg = error?.response?.data?.detail || error.message || 'Simulation failed';
      setSimulationErrors(prev => ({ ...prev, [allocationId]: errorMsg }));
      console.error('Simulation error:', error);
    },
  });

  // Tearsheet generation mutation
  const tearsheetMutation = useMutation({
    mutationFn: (allocationId: string) => apiClient.generateTearsheet(allocationId),
    onSuccess: (data, allocationId) => {
      setTearsheetResults(prev => ({ ...prev, [allocationId]: data }));
      setTearsheetErrors(prev => ({ ...prev, [allocationId]: '' }));
    },
    onError: (error: any, allocationId) => {
      const errorMsg = error?.response?.data?.detail || error.message || 'Tearsheet generation failed';
      setTearsheetErrors(prev => ({ ...prev, [allocationId]: errorMsg }));
      console.error('Tearsheet error:', error);
    },
  });

  // Auto-simulate when allocation is expanded
  useEffect(() => {
    if (expandedAllocationId &&
        !simulationResults[expandedAllocationId] &&
        !simulationErrors[expandedAllocationId] &&
        !simulationMutation.isPending) {
      console.log(`Auto-simulating allocation: ${expandedAllocationId}`);
      simulationMutation.mutate(expandedAllocationId);
    }
  }, [expandedAllocationId]);

  // Auto-generate tearsheet when allocation is expanded
  useEffect(() => {
    if (expandedAllocationId &&
        !tearsheetResults[expandedAllocationId] &&
        !tearsheetErrors[expandedAllocationId] &&
        !tearsheetMutation.isPending) {
      console.log(`Auto-generating tearsheet for allocation: ${expandedAllocationId}`);
      tearsheetMutation.mutate(expandedAllocationId);
    }
  }, [expandedAllocationId]);

  const handleApprove = () => {
    if (selectedAllocationForApproval && approverName.trim()) {
      approveMutation.mutate({
        allocationId: selectedAllocationForApproval.allocation_id,
        approvedBy: approverName,
      });
    }
  };

  const handleApproveClick = (allocation: any) => {
    setSelectedAllocationForApproval(allocation);
    setShowApproveModal(true);
  };

  const handleEditClick = (allocation: any) => {
    setSelectedAllocationForApproval(allocation);
    setEditedAllocations({ ...allocation.allocations });
    setAllocationName(''); // Clear name for new allocation
    setShowEditModal(true);
  };

  const handleAllocationChange = (strategyId: string, value: string) => {
    const numValue = parseFloat(value) || 0;
    setEditedAllocations(prev => ({ ...prev, [strategyId]: numValue }));
  };

  const getTotalAllocation = () => {
    return Object.values(editedAllocations).reduce((sum, val) => sum + val, 0);
  };

  const handleSaveCustomAllocation = () => {
    console.log('🔵 handleSaveCustomAllocation called');
    console.log('  - selectedAllocationForApproval:', selectedAllocationForApproval?.allocation_id);
    console.log('  - approverName:', approverName);
    console.log('  - allocationName:', allocationName);
    console.log('  - editedAllocations:', editedAllocations);
    console.log('  - totalAllocation:', getTotalAllocation());

    if (selectedAllocationForApproval && approverName.trim()) {
      const baseName = allocationName.trim() || 'Custom Portfolio';
      const notes = `${baseName} | Edited from ${selectedAllocationForApproval.allocation_id} - ${selectedAllocationForApproval.optimization_label || selectedAllocationForApproval.optimization_mode || 'N/A'}`;

      console.log('  - Creating allocation with notes:', notes);

      createCustomAllocationMutation.mutate({
        allocations: editedAllocations,
        createdBy: approverName,
        notes,
      });
    } else {
      console.log('  ❌ Validation failed - not calling mutation');
      console.log('  - Has selectedAllocationForApproval?', !!selectedAllocationForApproval);
      console.log('  - Has approverName?', !!approverName.trim());
    }
  };

  const getTearsheetUrl = (strategyId: string) => {
    const strategy = strategies?.find((s: any) => s.strategy_id === strategyId);
    return strategy?.tearsheet_url;
  };

  return (
    <div className="space-y-6">
      {/* Current Active Allocation */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">Current Active Allocation</h3>
          {currentAllocation && (
            <span className="px-3 py-1 bg-green-900/30 text-green-400 rounded-full text-sm font-medium">
              ACTIVE
            </span>
          )}
        </div>

        {currentAllocation ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 pb-4 border-b border-gray-700">
              <div>
                <p className="text-sm text-gray-400">Allocation ID</p>
                <p className="text-white font-medium">{currentAllocation.allocation_id}</p>
              </div>
              <div>
                <p className="text-sm text-gray-400">Total Allocation</p>
                <p className="text-white font-medium">
                  {currentAllocation.expected_metrics.total_allocation_pct.toFixed(1)}%
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-400">Leverage Ratio</p>
                <p className="text-white font-medium">
                  {currentAllocation.expected_metrics.leverage_ratio.toFixed(2)}x
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-400">Expected Sharpe (Annual)</p>
                <p className="text-white font-medium">
                  {currentAllocation.expected_metrics.expected_sharpe_annual?.toFixed(2) || 'N/A'}
                </p>
              </div>
            </div>

            <div className="space-y-3">
              {Object.entries(currentAllocation.allocations)
                .sort(([, a], [, b]) => b - a)
                .map(([strategyId, allocation]) => (
                  <div key={strategyId} className="flex items-center justify-between">
                    <div className="flex-1">
                      <p className="text-white font-medium">{strategyId}</p>
                      <div className="mt-1 bg-gray-700 rounded-full h-2.5 overflow-hidden">
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
        ) : (
          <div className="text-center py-8">
            <p className="text-gray-400">No active allocation found</p>
          </div>
        )}
      </div>

      {/* Recommended Allocation (Pending Approval) */}
      {latestRecommendation && (
        <div className="card border-2 border-yellow-500/50">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-lg font-semibold text-white">Recommended Allocation</h3>
              <p className="text-sm text-gray-400 mt-1">
                Generated: {new Date(latestRecommendation.timestamp).toLocaleString()}
              </p>
            </div>
            <span className="px-3 py-1 bg-yellow-900/30 text-yellow-400 rounded-full text-sm font-medium">
              PENDING APPROVAL
            </span>
          </div>

          {/* Comparison Table */}
          {currentAllocation && (
            <div className="mb-6 overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="table-header">Strategy</th>
                    <th className="table-header">Current %</th>
                    <th className="table-header">Recommended %</th>
                    <th className="table-header">Change</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {Object.keys({ ...currentAllocation.allocations, ...latestRecommendation.allocations })
                    .map((strategyId) => {
                      const current = currentAllocation.allocations[strategyId] || 0;
                      const recommended = latestRecommendation.allocations[strategyId] || 0;
                      const change = recommended - current;
                      return (
                        <tr key={strategyId} className="hover:bg-gray-700/50">
                          <td className="table-cell font-medium">{strategyId}</td>
                          <td className="table-cell">{current.toFixed(1)}%</td>
                          <td className="table-cell font-semibold">{recommended.toFixed(1)}%</td>
                          <td className={`table-cell font-semibold ${
                            change > 0 ? 'text-green-500' : change < 0 ? 'text-red-500' : 'text-gray-400'
                          }`}>
                            {change > 0 ? '+' : ''}{change.toFixed(1)}%
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-3">
            <button
              onClick={() => handleApproveClick(latestRecommendation)}
              disabled={approveMutation.isPending}
              className="btn-success flex items-center gap-2"
            >
              <Check className="h-4 w-4" />
              Approve
            </button>
            <button
              onClick={() => handleEditClick(latestRecommendation)}
              className="btn-secondary flex items-center gap-2"
            >
              <Edit className="h-4 w-4" />
              Edit & Approve
            </button>
            <button className="btn-danger flex items-center gap-2">
              <X className="h-4 w-4" />
              Reject
            </button>
          </div>
        </div>
      )}

      {/* Correlation Matrix Heatmap */}
      {optimizationRun && optimizationRun.correlation_matrix && (
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">Strategy Correlation Matrix</h3>
          <p className="text-sm text-gray-400 mb-4">
            Correlation values range from -1 (perfectly negatively correlated) to +1 (perfectly positively correlated)
          </p>
          <div className="overflow-x-auto">
            <div className="inline-block min-w-full">
              <div className="grid gap-1" style={{
                gridTemplateColumns: `100px repeat(${optimizationRun.strategies_used.length}, minmax(80px, 1fr))`
              }}>
                {/* Header row */}
                <div></div>
                {optimizationRun.strategies_used.map((strategy) => (
                  <div key={strategy} className="text-xs text-gray-400 font-medium p-2 text-center">
                    <div className="transform -rotate-45 origin-left">{strategy}</div>
                  </div>
                ))}

                {/* Data rows */}
                {optimizationRun.strategies_used.map((rowStrategy, rowIdx) => (
                  <React.Fragment key={rowStrategy}>
                    <div className="text-xs text-gray-400 font-medium p-2 flex items-center">
                      {rowStrategy}
                    </div>
                    {optimizationRun.correlation_matrix[rowIdx].map((correlation, colIdx) => {
                      const intensity = Math.abs(correlation);
                      const isPositive = correlation >= 0;
                      const bgColor = isPositive
                        ? `rgba(34, 197, 94, ${intensity * 0.7})`
                        : `rgba(239, 68, 68, ${intensity * 0.7})`;

                      return (
                        <div
                          key={colIdx}
                          className="p-2 text-center text-xs font-medium text-white rounded"
                          style={{ backgroundColor: bgColor }}
                          title={`${rowStrategy} vs ${optimizationRun.strategies_used[colIdx]}: ${correlation.toFixed(3)}`}
                        >
                          {correlation.toFixed(2)}
                        </div>
                      );
                    })}
                  </React.Fragment>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Allocation History */}
      <div className="card">
        <h3 className="text-lg font-semibold text-white mb-4">Allocation History</h3>
        <div className="space-y-2">
          {allocationHistory?.map((allocation) => {
            const isExpanded = expandedAllocationId === allocation.allocation_id;
            const isPending = allocation.status === 'PENDING_APPROVAL';

            return (
              <div key={allocation.allocation_id} className="border border-gray-700 rounded-lg overflow-hidden">
                {/* Header Row (Clickable) */}
                <div
                  onClick={() => setExpandedAllocationId(isExpanded ? null : allocation.allocation_id)}
                  className="flex items-center justify-between p-4 hover:bg-gray-700/50 cursor-pointer"
                >
                  <div className="flex items-center gap-4 flex-1">
                    <div className="text-gray-400">
                      {isExpanded ? <ChevronDown className="h-5 w-5" /> : <ChevronRight className="h-5 w-5" />}
                    </div>
                    <div className="flex-1 grid grid-cols-6 gap-4">
                      <div>
                        <p className="text-xs text-gray-400">Allocation ID</p>
                        <p className="text-white font-mono text-xs">{allocation.allocation_id}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-400">Mode</p>
                        <p className="text-white text-sm">{allocation.optimization_label || allocation.optimization_mode || 'N/A'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-400">Status</p>
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                          allocation.status === 'ACTIVE'
                            ? 'bg-green-900/30 text-green-400'
                            : allocation.status === 'PENDING_APPROVAL'
                            ? 'bg-yellow-900/30 text-yellow-400'
                            : 'bg-gray-700 text-gray-400'
                        }`}>
                          {allocation.status}
                        </span>
                      </div>
                      <div>
                        <p className="text-xs text-gray-400">Total Allocation</p>
                        <p className="text-white font-medium">{allocation.expected_metrics.total_allocation_pct.toFixed(1)}%</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-400">Sharpe (Annual)</p>
                        <p className="text-white font-medium">{allocation.expected_metrics.expected_sharpe_annual?.toFixed(2) || 'N/A'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-400">Date</p>
                        <p className="text-white text-sm">{new Date(allocation.created_at).toLocaleDateString()}</p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Expanded Details */}
                {isExpanded && (
                  <div className="border-t border-gray-700 p-6 bg-gray-800/50">
                    <div className="grid grid-cols-2 gap-6 mb-6">
                      {/* Metrics */}
                      <div>
                        <h4 className="text-sm font-semibold text-white mb-3">Expected Metrics</h4>
                        <div className="space-y-2">
                          <div className="flex justify-between">
                            <span className="text-gray-400">Total Allocation:</span>
                            <span className="text-white font-medium">{allocation.expected_metrics.total_allocation_pct.toFixed(1)}%</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-400">Leverage Ratio:</span>
                            <span className="text-white font-medium">{allocation.expected_metrics.leverage_ratio.toFixed(2)}x</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-400">Sharpe (Annual):</span>
                            <span className="text-white font-medium">{allocation.expected_metrics.expected_sharpe_annual?.toFixed(2) || 'N/A'}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-400">Daily Return:</span>
                            <span className="text-white font-medium">{(allocation.expected_metrics.expected_daily_return * 100)?.toFixed(4) || 'N/A'}%</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-400">Daily Volatility:</span>
                            <span className="text-white font-medium">{(allocation.expected_metrics.expected_daily_volatility * 100)?.toFixed(4) || 'N/A'}%</span>
                          </div>
                        </div>
                      </div>

                      {/* Info */}
                      <div>
                        <h4 className="text-sm font-semibold text-white mb-3">Details</h4>
                        <div className="space-y-2">
                          <div className="flex justify-between">
                            <span className="text-gray-400">Optimization Mode:</span>
                            <span className="text-white font-medium">{allocation.optimization_label || 'N/A'}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-400">Approved By:</span>
                            <span className="text-white font-medium">{allocation.approved_by || '-'}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-400">Created:</span>
                            <span className="text-white font-medium">{new Date(allocation.created_at).toLocaleString()}</span>
                          </div>
                          {allocation.approved_at && (
                            <div className="flex justify-between">
                              <span className="text-gray-400">Approved:</span>
                              <span className="text-white font-medium">{new Date(allocation.approved_at).toLocaleString()}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Strategy Allocations */}
                    <div className="mb-6">
                      <h4 className="text-sm font-semibold text-white mb-3">Strategy Allocations</h4>
                      <div className="space-y-3">
                        {Object.entries(allocation.allocations)
                          .sort(([, a], [, b]) => (b as number) - (a as number))
                          .map(([strategyId, pct]) => {
                            const tearsheetUrl = getTearsheetUrl(strategyId);
                            return (
                              <div key={strategyId} className="flex items-center justify-between">
                                <div className="flex-1">
                                  <div className="flex items-center gap-2">
                                    <p className="text-white font-medium text-sm">{strategyId}</p>
                                    {tearsheetUrl && (
                                      <a
                                        href={tearsheetUrl}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        onClick={(e) => e.stopPropagation()}
                                        className="text-blue-400 hover:text-blue-300"
                                        title="View Strategy Tearsheet"
                                      >
                                        <ExternalLink className="h-3 w-3" />
                                      </a>
                                    )}
                                  </div>
                                  <div className="mt-1 bg-gray-700 rounded-full h-2 overflow-hidden">
                                    <div
                                      className="bg-blue-500 h-full transition-all"
                                      style={{ width: `${pct}%` }}
                                    />
                                  </div>
                                </div>
                                <span className="ml-4 text-white font-semibold w-20 text-right">
                                  {(pct as number).toFixed(2)}%
                                </span>
                              </div>
                            );
                          })}
                      </div>
                    </div>

                    {/* Simulation & Equity Curve */}
                    <div className="border-t border-gray-700 pt-4">
                      <div className="flex items-center justify-between mb-4">
                        <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                          <BarChart className="h-4 w-4" />
                          Portfolio Simulation
                        </h4>
                        <div className="flex gap-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              simulationMutation.mutate(allocation.allocation_id);
                            }}
                            disabled={simulationMutation.isPending}
                            className="btn-primary text-sm py-1 px-3 flex items-center gap-2"
                          >
                            <TrendingUp className="h-3 w-3" />
                            {simulationMutation.isPending ? 'Running...' : 'Run Simulation'}
                          </button>
                          {/* Tearsheet Button - Auto-generated on expand */}
                          {tearsheetMutation.isPending ? (
                            <div className="btn-secondary text-sm py-1 px-3 flex items-center gap-2 opacity-70 cursor-wait">
                              <FileText className="h-3 w-3 animate-pulse" />
                              Generating Tearsheet...
                            </div>
                          ) : tearsheetResults[allocation.allocation_id] ? (
                            <a
                              href={`http://localhost:8002${tearsheetResults[allocation.allocation_id].tearsheet_url}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="btn-success text-sm py-1 px-3 flex items-center gap-2"
                            >
                              <ExternalLink className="h-3 w-3" />
                              Open Tearsheet
                            </a>
                          ) : null}
                        </div>
                      </div>

                      {simulationErrors[allocation.allocation_id] ? (
                        <div className="bg-red-900/30 border border-red-500 rounded-lg p-4">
                          <p className="text-red-400 text-sm font-semibold mb-2">Simulation Error:</p>
                          <p className="text-red-300 text-sm">{simulationErrors[allocation.allocation_id]}</p>
                          <p className="text-red-400/70 text-xs mt-3">
                            This usually means strategy backtest data is missing the required fields (daily_returns and dates).
                          </p>
                        </div>
                      ) : simulationResults[allocation.allocation_id] ? (
                        <div className="space-y-4">
                          {/* Validation Status Banner */}
                          {simulationResults[allocation.allocation_id]?.validation_status && (
                            <div className={`p-4 rounded-lg border-2 ${
                              simulationResults[allocation.allocation_id].validation_status === 'PASS'
                                ? 'bg-green-900/20 border-green-500'
                                : simulationResults[allocation.allocation_id].validation_status === 'WARNING'
                                ? 'bg-yellow-900/20 border-yellow-500'
                                : 'bg-red-900/20 border-red-500'
                            }`}>
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                  <span className={`text-2xl ${
                                    simulationResults[allocation.allocation_id].validation_status === 'PASS'
                                      ? 'text-green-400'
                                      : simulationResults[allocation.allocation_id].validation_status === 'WARNING'
                                      ? 'text-yellow-400'
                                      : 'text-red-400'
                                  }`}>
                                    {simulationResults[allocation.allocation_id].validation_status === 'PASS' ? '✅' :
                                     simulationResults[allocation.allocation_id].validation_status === 'WARNING' ? '⚠️' : '❌'}
                                  </span>
                                  <div>
                                    <h4 className={`font-bold ${
                                      simulationResults[allocation.allocation_id].validation_status === 'PASS'
                                        ? 'text-green-400'
                                        : simulationResults[allocation.allocation_id].validation_status === 'WARNING'
                                        ? 'text-yellow-400'
                                        : 'text-red-400'
                                    }`}>
                                      Validation: {simulationResults[allocation.allocation_id].validation_status}
                                    </h4>
                                    <p className="text-sm text-gray-300">
                                      {simulationResults[allocation.allocation_id].validation_status === 'PASS'
                                        ? 'Portfolio meets all risk thresholds'
                                        : simulationResults[allocation.allocation_id].validation_status === 'WARNING'
                                        ? 'Portfolio approaching risk limits - review recommended'
                                        : 'Portfolio exceeds risk limits - requires adjustment'}
                                    </p>
                                  </div>
                                </div>
                                <div className="flex gap-4">
                                  <div className="text-right">
                                    <p className="text-xs text-gray-400">Max Margin</p>
                                    <p className={`font-bold ${
                                      (simulationResults[allocation.allocation_id].max_margin_utilization || 0) > 80
                                        ? 'text-red-400'
                                        : (simulationResults[allocation.allocation_id].max_margin_utilization || 0) > 70
                                        ? 'text-yellow-400'
                                        : 'text-green-400'
                                    }`}>
                                      {(simulationResults[allocation.allocation_id].max_margin_utilization || 0).toFixed(2)}%
                                    </p>
                                  </div>
                                  <div className="text-right">
                                    <p className="text-xs text-gray-400">Max Leverage</p>
                                    <p className={`font-bold ${
                                      (simulationResults[allocation.allocation_id].max_leverage || 0) > 2.0
                                        ? 'text-red-400'
                                        : (simulationResults[allocation.allocation_id].max_leverage || 0) > 1.5
                                        ? 'text-yellow-400'
                                        : 'text-green-400'
                                    }`}>
                                      {(simulationResults[allocation.allocation_id].max_leverage || 0).toFixed(2)}x
                                    </p>
                                  </div>
                                </div>
                              </div>
                            </div>
                          )}

                          {/* Simulated Metrics */}
                          {simulationResults[allocation.allocation_id]?.metrics && (
                            <div className="grid grid-cols-3 gap-4 p-4 bg-gray-700/50 rounded-lg">
                              <div>
                                <p className="text-xs text-gray-400">CAGR</p>
                                <p className="text-white font-bold text-lg">{simulationResults[allocation.allocation_id].metrics.cagr || 'N/A'}%</p>
                              </div>
                              <div>
                                <p className="text-xs text-gray-400">Sharpe Ratio</p>
                                <p className="text-white font-bold text-lg">{simulationResults[allocation.allocation_id].metrics.sharpe_ratio || 'N/A'}</p>
                              </div>
                              <div>
                                <p className="text-xs text-gray-400">Max Drawdown</p>
                                <p className="text-red-400 font-bold text-lg">{simulationResults[allocation.allocation_id].metrics.max_drawdown || 'N/A'}%</p>
                              </div>
                              <div>
                                <p className="text-xs text-gray-400">Volatility (Annual)</p>
                                <p className="text-white font-semibold">{simulationResults[allocation.allocation_id].metrics.volatility_annual || 'N/A'}%</p>
                              </div>
                              <div>
                                <p className="text-xs text-gray-400">Period</p>
                                <p className="text-white font-semibold">{simulationResults[allocation.allocation_id].metrics.total_days || 'N/A'} days</p>
                              </div>
                              <div>
                                <p className="text-xs text-gray-400">Date Range</p>
                                <p className="text-white text-xs">{simulationResults[allocation.allocation_id].metrics.start_date || 'N/A'} to {simulationResults[allocation.allocation_id].metrics.end_date || 'N/A'}</p>
                              </div>
                            </div>
                          )}

                          {/* Equity Curve */}
                          {simulationResults[allocation.allocation_id]?.equity_curve?.dates && simulationResults[allocation.allocation_id]?.equity_curve?.values && (
                            <div className="bg-gray-900/50 rounded-lg p-4">
                              <h5 className="text-sm font-semibold text-white mb-3">Equity Curve</h5>
                              <ResponsiveContainer width="100%" height={300}>
                                <LineChart
                                  data={simulationResults[allocation.allocation_id].equity_curve.dates.map((date: string, idx: number) => ({
                                    date,
                                    value: simulationResults[allocation.allocation_id].equity_curve.values[idx]
                                  }))}
                                  margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                                >
                                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                                <XAxis
                                  dataKey="date"
                                  stroke="#9CA3AF"
                                  tick={{ fontSize: 10 }}
                                  tickFormatter={(value) => {
                                    const date = new Date(value);
                                    return `${date.getMonth() + 1}/${date.getFullYear().toString().slice(2)}`;
                                  }}
                                  interval="preserveStartEnd"
                                  minTickGap={50}
                                />
                                <YAxis stroke="#9CA3AF" tick={{ fontSize: 12 }} />
                                <Tooltip
                                  contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '8px' }}
                                  labelStyle={{ color: '#9CA3AF' }}
                                  itemStyle={{ color: '#3B82F6' }}
                                  formatter={(value: any) => [`$${value.toFixed(4)}`, 'Portfolio Value']}
                                  labelFormatter={(label) => `Date: ${label}`}
                                />
                                <Legend wrapperStyle={{ color: '#9CA3AF' }} />
                                <Line
                                  type="monotone"
                                  dataKey="value"
                                  stroke="#3B82F6"
                                  strokeWidth={2}
                                  dot={false}
                                  name="Portfolio Value"
                                />
                              </LineChart>
                            </ResponsiveContainer>
                          </div>
                          )}

                          {/* Margin Utilization Chart */}
                          {simulationResults[allocation.allocation_id]?.margin_utilization?.dates && simulationResults[allocation.allocation_id]?.margin_utilization?.values && (
                            <div className="bg-gray-900/50 rounded-lg p-4">
                              <h5 className="text-sm font-semibold text-white mb-3">Margin Utilization (%)</h5>
                              <ResponsiveContainer width="100%" height={250}>
                                <LineChart
                                  data={simulationResults[allocation.allocation_id].margin_utilization.dates.map((date: string, idx: number) => ({
                                    date,
                                    value: simulationResults[allocation.allocation_id].margin_utilization.values[idx]
                                  }))}
                                  margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                                >
                                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                                  <XAxis
                                    dataKey="date"
                                    stroke="#9CA3AF"
                                    tick={{ fontSize: 10 }}
                                    tickFormatter={(value) => {
                                      const date = new Date(value);
                                      return `${date.getMonth() + 1}/${date.getFullYear().toString().slice(2)}`;
                                    }}
                                    interval="preserveStartEnd"
                                    minTickGap={50}
                                  />
                                  <YAxis stroke="#9CA3AF" tick={{ fontSize: 12 }} />
                                  <Tooltip
                                    contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '8px' }}
                                    labelStyle={{ color: '#9CA3AF' }}
                                    itemStyle={{ color: '#F59E0B' }}
                                    formatter={(value: any) => [`${value.toFixed(2)}%`, 'Margin Used']}
                                    labelFormatter={(label) => `Date: ${label}`}
                                  />
                                  <Legend wrapperStyle={{ color: '#9CA3AF' }} />
                                  <Line
                                    type="monotone"
                                    dataKey="value"
                                    stroke="#F59E0B"
                                    strokeWidth={2}
                                    dot={false}
                                    name="Margin Utilization"
                                  />
                                </LineChart>
                              </ResponsiveContainer>
                            </div>
                          )}

                          {/* Leverage History Chart */}
                          {simulationResults[allocation.allocation_id]?.leverage_history?.dates && simulationResults[allocation.allocation_id]?.leverage_history?.values && (
                            <div className="bg-gray-900/50 rounded-lg p-4">
                              <h5 className="text-sm font-semibold text-white mb-3">Notional Leverage</h5>
                              <ResponsiveContainer width="100%" height={250}>
                                <LineChart
                                  data={simulationResults[allocation.allocation_id].leverage_history.dates.map((date: string, idx: number) => ({
                                    date,
                                    value: simulationResults[allocation.allocation_id].leverage_history.values[idx]
                                  }))}
                                  margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                                >
                                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                                  <XAxis
                                    dataKey="date"
                                    stroke="#9CA3AF"
                                    tick={{ fontSize: 10 }}
                                    tickFormatter={(value) => {
                                      const date = new Date(value);
                                      return `${date.getMonth() + 1}/${date.getFullYear().toString().slice(2)}`;
                                    }}
                                    interval="preserveStartEnd"
                                    minTickGap={50}
                                  />
                                  <YAxis stroke="#9CA3AF" tick={{ fontSize: 12 }} />
                                  <Tooltip
                                    contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '8px' }}
                                    labelStyle={{ color: '#9CA3AF' }}
                                    itemStyle={{ color: '#10B981' }}
                                    formatter={(value: any) => [`${value.toFixed(2)}x`, 'Leverage']}
                                    labelFormatter={(label) => `Date: ${label}`}
                                  />
                                  <Legend wrapperStyle={{ color: '#9CA3AF' }} />
                                  <Line
                                    type="monotone"
                                    dataKey="value"
                                    stroke="#10B981"
                                    strokeWidth={2}
                                    dot={false}
                                    name="Notional Leverage"
                                  />
                                </LineChart>
                              </ResponsiveContainer>
                            </div>
                          )}
                        </div>
                      ) : (
                        <p className="text-gray-500 text-sm text-center py-4">
                          Click "Run Simulation" to calculate historical performance and view equity curve
                        </p>
                      )}

                      {/* Tearsheet Result */}
                      {tearsheetResults[allocation.allocation_id] && (
                        <div className="mt-4 p-4 bg-green-900/20 border border-green-500 rounded-lg">
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="text-green-400 font-semibold mb-1">✅ Tearsheet Generated Successfully</p>
                              <p className="text-sm text-gray-300">
                                Trading days: {tearsheetResults[allocation.allocation_id].trading_days} |
                                Period: {tearsheetResults[allocation.allocation_id].date_range.start} to {tearsheetResults[allocation.allocation_id].date_range.end}
                              </p>
                            </div>
                            <a
                              href={`http://localhost:8002${tearsheetResults[allocation.allocation_id].tearsheet_url}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="btn-primary text-sm py-2 px-4 flex items-center gap-2"
                            >
                              <ExternalLink className="h-4 w-4" />
                              View Tearsheet
                            </a>
                          </div>
                        </div>
                      )}

                      {/* Tearsheet Error */}
                      {tearsheetErrors[allocation.allocation_id] && (
                        <div className="mt-4 p-4 bg-red-900/20 border border-red-500 rounded-lg">
                          <p className="text-red-400 font-semibold mb-1">❌ Tearsheet Generation Failed</p>
                          <p className="text-sm text-red-300">{tearsheetErrors[allocation.allocation_id]}</p>
                        </div>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex gap-3 pt-4 border-t border-gray-700">
                      {isPending && (
                        <>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleApproveClick(allocation);
                            }}
                            className="btn-success flex items-center gap-2"
                          >
                            <Check className="h-4 w-4" />
                            Approve
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleEditClick(allocation);
                            }}
                            className="btn-secondary flex items-center gap-2"
                          >
                            <Edit className="h-4 w-4" />
                            Edit & Approve
                          </button>
                          <button className="btn-danger flex items-center gap-2">
                            <X className="h-4 w-4" />
                            Reject
                          </button>
                        </>
                      )}
                      {!isPending && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleEditClick(allocation);
                          }}
                          className="btn-secondary flex items-center gap-2"
                        >
                          <Edit className="h-4 w-4" />
                          Duplicate & Edit
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Approve Modal */}
      {showApproveModal && selectedAllocationForApproval && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-xl font-bold text-white mb-4">Approve Allocation</h3>
            <p className="text-gray-400 mb-2">
              Are you sure you want to approve allocation:
            </p>
            <p className="font-mono text-sm text-white mb-1">{selectedAllocationForApproval.allocation_id}</p>
            <p className="text-sm text-gray-400 mb-4">
              Mode: {selectedAllocationForApproval.optimization_label || selectedAllocationForApproval.optimization_mode || 'N/A'}
            </p>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Your Name
              </label>
              <input
                type="text"
                value={approverName}
                onChange={(e) => setApproverName(e.target.value)}
                className="input"
                placeholder="Enter your name"
                autoFocus
              />
            </div>
            <div className="flex gap-3">
              <button
                onClick={handleApprove}
                disabled={!approverName.trim() || approveMutation.isPending}
                className="btn-success flex-1"
              >
                {approveMutation.isPending ? 'Approving...' : 'Confirm'}
              </button>
              <button
                onClick={() => {
                  setShowApproveModal(false);
                  setSelectedAllocationForApproval(null);
                }}
                disabled={approveMutation.isPending}
                className="btn-secondary"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {showEditModal && selectedAllocationForApproval && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 overflow-y-auto">
          <div className="bg-gray-800 rounded-lg p-6 max-w-2xl w-full mx-4 my-8">
            <h3 className="text-xl font-bold text-white mb-4">Edit Allocation</h3>
            <p className="text-gray-400 mb-4">
              Adjust allocation percentages for: <span className="font-mono text-sm text-white">{selectedAllocationForApproval.allocation_id}</span>
            </p>

            {/* Allocation Name */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Allocation Name / Label
              </label>
              <input
                type="text"
                value={allocationName}
                onChange={(e) => setAllocationName(e.target.value)}
                className="input"
                placeholder="e.g., Q4 2025 Conservative Mix"
              />
              <p className="text-xs text-gray-400 mt-1">
                Give this allocation a descriptive name (optional - will auto-generate if empty)
              </p>
            </div>

            {/* Total Allocation Display */}
            <div className={`mb-4 p-4 rounded-lg ${
              getTotalAllocation() > 200 ? 'bg-red-900/30 border border-red-500' :
              getTotalAllocation() > 100 ? 'bg-yellow-900/30 border border-yellow-500' :
              'bg-green-900/30 border border-green-500'
            }`}>
              <div className="flex justify-between items-center">
                <span className="text-white font-semibold">Total Allocation:</span>
                <span className={`text-2xl font-bold ${
                  getTotalAllocation() > 200 ? 'text-red-400' :
                  getTotalAllocation() > 100 ? 'text-yellow-400' :
                  'text-green-400'
                }`}>
                  {getTotalAllocation().toFixed(2)}%
                </span>
              </div>
              {getTotalAllocation() > 200 && (
                <p className="text-red-400 text-sm mt-2">⚠️ Total exceeds maximum leverage (200%)</p>
              )}
            </div>

            {/* Strategy Allocations (Editable) */}
            <div className="space-y-3 max-h-96 overflow-y-auto mb-4">
              {Object.entries(editedAllocations)
                .sort(([, a], [, b]) => b - a)
                .map(([strategyId, allocation]) => (
                  <div key={strategyId} className="flex items-center gap-4 p-3 bg-gray-700/50 rounded-lg">
                    <div className="flex-1">
                      <label className="text-white font-medium text-sm">{strategyId}</label>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        value={allocation}
                        onChange={(e) => handleAllocationChange(strategyId, e.target.value)}
                        step="0.1"
                        min="0"
                        max="50"
                        className="input w-24 text-right"
                      />
                      <span className="text-gray-400">%</span>
                    </div>
                  </div>
                ))}
            </div>

            {/* Creator Name */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Your Name (Creator) <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={approverName}
                onChange={(e) => setApproverName(e.target.value)}
                className="input"
                placeholder="Enter your name"
              />
              {!approverName.trim() && (
                <p className="text-xs text-red-400 mt-1">⚠️ Required field</p>
              )}
            </div>

            {/* Actions */}
            <div className="flex gap-3">
              <button
                onClick={() => {
                  console.log('🔵 Button clicked!');
                  console.log('  - approverName filled?', !!approverName.trim());
                  console.log('  - total allocation:', getTotalAllocation());
                  console.log('  - is pending?', createCustomAllocationMutation.isPending);
                  handleSaveCustomAllocation();
                }}
                disabled={!approverName.trim() || getTotalAllocation() > 200 || createCustomAllocationMutation.isPending}
                className="btn-primary flex-1"
                title={
                  !approverName.trim() ? 'Please enter your name' :
                  getTotalAllocation() > 200 ? 'Total allocation exceeds 200%' :
                  createCustomAllocationMutation.isPending ? 'Creating...' :
                  'Create this allocation'
                }
              >
                {createCustomAllocationMutation.isPending ? 'Creating...' : 'Create Allocation'}
              </button>
              <button
                onClick={() => {
                  setShowEditModal(false);
                  setSelectedAllocationForApproval(null);
                  setEditedAllocations({});
                  setAllocationName('');
                }}
                disabled={createCustomAllocationMutation.isPending}
                className="btn-secondary"
              >
                Cancel
              </button>
            </div>

            <p className="text-xs text-gray-400 mt-4">
              ✅ Your edited allocations will be saved as a new CUSTOM allocation (PENDING_APPROVAL). You can review the simulation and approve it later.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
