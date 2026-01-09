/**
 * WidgetWrapper Component
 *
 * Wraps individual widgets with:
 * - Reload button for on-demand refresh
 * - Staleness indicator (orange border if >5 minutes old)
 * - Loading and error states
 * - Timestamp display
 */
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { RefreshCw, Clock, AlertCircle } from 'lucide-react';
import { apiClient } from '../../services/api';
import { FundBalancesWidget } from './widgets/FundBalancesWidget';
import { AccountStatementWidget } from './widgets/AccountStatementWidget';
import type { DashboardWidget, FundBalancesData, AccountStatementData } from '../../types';

interface WidgetWrapperProps {
  widget: DashboardWidget;
  fundId?: string | null;
}

export const WidgetWrapper: React.FC<WidgetWrapperProps> = ({ widget, fundId }) => {
  // Fetch widget data with React Query
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['widget', widget.widget_type, fundId, widget.config],
    queryFn: async () => {
      return await apiClient.getWidgetData(
        widget.widget_type,
        fundId || undefined,
        widget.config
      );
    },
    staleTime: 30000, // Consider data fresh for 30 seconds
    refetchOnMount: false,
    refetchOnWindowFocus: false,
  });

  const handleReload = async () => {
    try {
      // Force reload from backend
      await apiClient.reloadWidget(
        widget.widget_type,
        fundId || undefined,
        widget.config
      );
      // Refetch the data
      await refetch();
    } catch (error) {
      console.error('Failed to reload widget:', error);
    }
  };

  const isStale = data?.is_stale || false;
  const borderColor = isStale ? 'border-orange-500' : 'border-gray-700';

  const formatTimeAgo = (seconds: number) => {
    if (seconds < 60) return `${Math.floor(seconds)}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    return `${Math.floor(seconds / 3600)}h ago`;
  };

  const getWidgetTitle = () => {
    switch (widget.widget_type) {
      case 'FundBalances':
        return 'Fund Balances';
      case 'AccountStatement':
        return 'Account Statement';
      default:
        return widget.widget_type;
    }
  };

  return (
    <div className={`h-full flex flex-col bg-gray-900 rounded-lg border-2 ${borderColor} overflow-hidden`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center space-x-2">
          <h3 className="text-sm font-semibold text-white">{getWidgetTitle()}</h3>
          {isStale && (
            <div
              className="px-2 py-0.5 bg-orange-500/20 text-orange-500 text-xs rounded flex items-center space-x-1"
              title="Data is older than 5 minutes"
            >
              <Clock className="w-3 h-3" />
              <span>Stale</span>
            </div>
          )}
        </div>
        <button
          onClick={handleReload}
          disabled={isFetching}
          className="p-1 hover:bg-gray-700 rounded transition-colors disabled:opacity-50"
          title="Reload widget"
        >
          <RefreshCw className={`w-4 h-4 text-gray-400 ${isFetching ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {isLoading && (
          <div className="flex items-center justify-center h-full">
            <div className="flex flex-col items-center space-y-2 text-gray-500">
              <RefreshCw className="w-8 h-8 animate-spin" />
              <span className="text-sm">Loading widget data...</span>
            </div>
          </div>
        )}

        {error && (
          <div className="flex items-center justify-center h-full">
            <div className="flex flex-col items-center space-y-2 text-red-500">
              <AlertCircle className="w-8 h-8" />
              <span className="text-sm">Failed to load widget</span>
              <button
                onClick={handleReload}
                className="text-xs text-blue-400 hover:text-blue-300 underline"
              >
                Try again
              </button>
            </div>
          </div>
        )}

        {data && !isLoading && !error && (
          <>
            {widget.widget_type === 'FundBalances' && (
              <FundBalancesWidget data={data.data as FundBalancesData} />
            )}
            {widget.widget_type === 'AccountStatement' && (
              <AccountStatementWidget
                data={data.data as AccountStatementData}
                config={widget.config}
              />
            )}
          </>
        )}
      </div>

      {/* Footer with timestamp */}
      {data && !isLoading && (
        <div className="px-4 py-2 bg-gray-800 border-t border-gray-700">
          <div className="flex items-center justify-between text-xs text-gray-500">
            <span>Updated {formatTimeAgo(data.age_seconds)}</span>
            {isStale && (
              <span className="text-orange-500">Data may be outdated</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
