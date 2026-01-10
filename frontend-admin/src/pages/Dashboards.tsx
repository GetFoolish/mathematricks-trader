/**
 * Dashboards Page (v5)
 *
 * Main dashboard management page with:
 * - Dashboard list/selector
 * - Dashboard canvas with widgets
 * - SSE for real-time updates
 */
import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2, AlertCircle } from 'lucide-react';
import { DashboardCanvas } from '../components/dashboards/DashboardCanvas';
import { useWidgetSSE } from '../hooks/useWidgetSSE';
import { apiClient } from '../services/api';
import type { Dashboard } from '../types';

export const Dashboards: React.FC = () => {
  const [selectedDashboardId, setSelectedDashboardId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [newDashboardName, setNewDashboardName] = useState('');
  const queryClient = useQueryClient();

  // Enable SSE for real-time widget updates
  useWidgetSSE(selectedDashboardId || undefined);

  // Fetch all dashboards
  const { data: dashboards, isLoading: isLoadingDashboards } = useQuery({
    queryKey: ['dashboards'],
    queryFn: () => apiClient.getDashboards(),
  });

  // Fetch selected dashboard details
  const { data: dashboard, isLoading: isLoadingDashboard } = useQuery({
    queryKey: ['dashboard', selectedDashboardId],
    queryFn: () => apiClient.getDashboard(selectedDashboardId!),
    enabled: !!selectedDashboardId,
  });

  // Auto-select first dashboard if none selected
  React.useEffect(() => {
    if (!selectedDashboardId && dashboards && dashboards.length > 0) {
      setSelectedDashboardId(dashboards[0].dashboard_id);
    }
  }, [dashboards, selectedDashboardId]);

  const handleCreateDashboard = async () => {
    if (!newDashboardName.trim()) return;

    try {
      const result = await apiClient.createDashboard({
        name: newDashboardName,
        created_by: 'admin', // TODO: Get from auth context
        widgets: [],
      });

      // Refresh dashboard list
      await queryClient.invalidateQueries({ queryKey: ['dashboards'] });

      // Select the new dashboard
      setSelectedDashboardId(result.dashboard_id);

      // Reset form
      setNewDashboardName('');
      setIsCreating(false);
    } catch (error) {
      console.error('Failed to create dashboard:', error);
      alert('Failed to create dashboard');
    }
  };

  const handleDeleteDashboard = async (dashboardId: string) => {
    if (!confirm('Are you sure you want to delete this dashboard?')) {
      return;
    }

    try {
      await apiClient.deleteDashboard(dashboardId);

      // Refresh dashboard list
      await queryClient.invalidateQueries({ queryKey: ['dashboards'] });

      // Deselect if this was the selected dashboard
      if (selectedDashboardId === dashboardId) {
        setSelectedDashboardId(null);
      }
    } catch (error) {
      console.error('Failed to delete dashboard:', error);
      alert('Failed to delete dashboard');
    }
  };

  const handleLayoutChange = async (updatedWidgets: Dashboard['widgets']) => {
    if (!selectedDashboardId) return;

    try {
      await apiClient.updateDashboard(selectedDashboardId, {
        widgets: updatedWidgets,
      });

      // Refresh dashboard
      await queryClient.invalidateQueries({
        queryKey: ['dashboard', selectedDashboardId],
      });
    } catch (error) {
      console.error('Failed to update dashboard layout:', error);
    }
  };

  const handleReloadAll = async () => {
    if (!selectedDashboardId) return;

    try {
      await apiClient.reloadAllWidgets(selectedDashboardId);

      // Invalidate all widget queries to trigger refetch
      await queryClient.invalidateQueries({ queryKey: ['widget'] });
    } catch (error) {
      console.error('Failed to reload widgets:', error);
    }
  };

  return (
    <div className="h-full flex bg-gray-900">
      {/* Sidebar - Dashboard List */}
      <div className="w-64 bg-gray-800 border-r border-gray-700 flex flex-col overflow-hidden">
        <div className="p-4 border-b border-gray-700">
          <h1 className="text-xl font-bold text-white mb-4">Dashboards</h1>

          {/* Create Dashboard Button */}
          {!isCreating ? (
            <button
              onClick={() => setIsCreating(true)}
              className="w-full px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded flex items-center justify-center space-x-2 transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span>New Dashboard</span>
            </button>
          ) : (
            <div className="space-y-2">
              <input
                type="text"
                placeholder="Dashboard name"
                value={newDashboardName}
                onChange={(e) => setNewDashboardName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleCreateDashboard();
                  if (e.key === 'Escape') setIsCreating(false);
                }}
                className="w-full px-3 py-2 bg-gray-900 text-white text-sm border border-gray-600 rounded focus:outline-none focus:border-blue-500"
                autoFocus
              />
              <div className="flex space-x-2">
                <button
                  onClick={handleCreateDashboard}
                  className="flex-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded"
                >
                  Create
                </button>
                <button
                  onClick={() => {
                    setIsCreating(false);
                    setNewDashboardName('');
                  }}
                  className="flex-1 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Dashboard List */}
        <div className="flex-1 overflow-y-auto">
          {isLoadingDashboards ? (
            <div className="p-4 text-center text-gray-500 text-sm">
              Loading dashboards...
            </div>
          ) : dashboards && dashboards.length > 0 ? (
            <div className="space-y-1 p-2">
              {dashboards.map((dash) => (
                <div
                  key={dash.dashboard_id}
                  className={`group flex items-center justify-between px-3 py-2 rounded cursor-pointer transition-colors ${
                    selectedDashboardId === dash.dashboard_id
                      ? 'bg-blue-600 text-white'
                      : 'hover:bg-gray-700 text-gray-300'
                  }`}
                  onClick={() => setSelectedDashboardId(dash.dashboard_id)}
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">{dash.name}</div>
                    <div className="text-xs text-gray-400">
                      {dash.widgets.length} widget{dash.widgets.length !== 1 ? 's' : ''}
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteDashboard(dash.dashboard_id);
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-600 rounded transition-opacity"
                    title="Delete dashboard"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-4 text-center text-gray-500 text-sm">
              No dashboards yet. Create one to get started!
            </div>
          )}
        </div>
      </div>

      {/* Main Content - Dashboard Canvas */}
      <div className="flex-1 flex flex-col">
        {selectedDashboardId ? (
          isLoadingDashboard ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-gray-500">Loading dashboard...</div>
            </div>
          ) : dashboard ? (
            <DashboardCanvas
              dashboard={dashboard}
              onLayoutChange={handleLayoutChange}
              onReloadAll={handleReloadAll}
            />
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="flex flex-col items-center space-y-2 text-red-500">
                <AlertCircle className="w-8 h-8" />
                <span>Failed to load dashboard</span>
              </div>
            </div>
          )
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center text-gray-500">
              <div className="text-lg mb-2">No dashboard selected</div>
              <div className="text-sm">Select a dashboard from the sidebar or create a new one</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
