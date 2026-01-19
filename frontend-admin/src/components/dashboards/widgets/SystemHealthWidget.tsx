/**
 * SystemHealthWidget Component
 *
 * Displays real-time system health status with traffic light indicators.
 * Shows overall health and individual service statuses.
 */
import React from 'react';
import { Activity, AlertCircle, CheckCircle, AlertTriangle, Server } from 'lucide-react';
import type { SystemHealthData } from '../../../types';

interface SystemHealthWidgetProps {
  data: SystemHealthData;
}

type HealthStatus = 'healthy' | 'degraded' | 'unhealthy';

export const SystemHealthWidget: React.FC<SystemHealthWidgetProps> = ({ data }) => {
  const getStatusColor = (status: HealthStatus): string => {
    switch (status) {
      case 'healthy':
        return 'bg-green-500';
      case 'degraded':
        return 'bg-yellow-500';
      case 'unhealthy':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  const getStatusIcon = (status: HealthStatus) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'degraded':
        return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
      case 'unhealthy':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      default:
        return <Server className="w-5 h-5 text-gray-500" />;
    }
  };

  const getStatusText = (status: HealthStatus): string => {
    switch (status) {
      case 'healthy':
        return 'All Systems Operational';
      case 'degraded':
        return 'Partial Outage';
      case 'unhealthy':
        return 'System Issues Detected';
      default:
        return 'Unknown';
    }
  };

  const formatUptime = (seconds: number): string => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) {
      return `${days}d ${hours}h ${minutes}m`;
    } else if (hours > 0) {
      return `${hours}h ${minutes}m`;
    } else {
      return `${minutes}m`;
    }
  };

  return (
    <div className="space-y-4">
      {/* Overall System Health */}
      <div className={`rounded-lg p-6 border-2 ${
        data.overall_status === 'healthy' 
          ? 'bg-green-900/20 border-green-500/50' 
          : data.overall_status === 'degraded'
          ? 'bg-yellow-900/20 border-yellow-500/50'
          : 'bg-red-900/20 border-red-500/50'
      }`}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-3">
            <div className={`w-12 h-12 rounded-full ${getStatusColor(data.overall_status)} animate-pulse`} />
            <div>
              <div className="text-sm text-gray-400 mb-1">System Status</div>
              <div className="text-2xl font-bold text-white">
                {getStatusText(data.overall_status)}
              </div>
            </div>
          </div>
          <Activity className="w-8 h-8 text-gray-400" />
        </div>
        <div className="text-sm text-gray-400">
          Last updated: {new Date(data.timestamp).toLocaleString()}
        </div>
      </div>

      {/* Individual Services */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <div className="text-sm font-semibold text-white mb-3">Services</div>
        <div className="space-y-2">
          {data.services.map((service) => (
            <div 
              key={service.name}
              className="flex items-center justify-between p-3 bg-gray-900 rounded border border-gray-700 hover:border-gray-600 transition-colors"
            >
              <div className="flex items-center space-x-3 flex-1">
                {getStatusIcon(service.status)}
                <div className="flex-1">
                  <div className="text-sm font-medium text-white">{service.name}</div>
                  {service.message && (
                    <div className="text-xs text-gray-400 mt-1">{service.message}</div>
                  )}
                </div>
              </div>
              <div className="flex items-center space-x-4 text-right">
                {service.uptime !== undefined && (
                  <div className="text-xs text-gray-400">
                    Uptime: {formatUptime(service.uptime)}
                  </div>
                )}
                {service.response_time !== undefined && (
                  <div className="text-xs text-gray-400">
                    {service.response_time.toFixed(0)}ms
                  </div>
                )}
                <div className={`w-3 h-3 rounded-full ${getStatusColor(service.status)}`} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* System Metrics */}
      {data.metrics && (
        <div className="grid grid-cols-2 gap-3">
          {data.metrics.active_strategies !== undefined && (
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-3">
              <div className="text-xs text-gray-400 mb-1">Active Strategies</div>
              <div className="text-2xl font-bold text-white">{data.metrics.active_strategies}</div>
            </div>
          )}
          {data.metrics.active_accounts !== undefined && (
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-3">
              <div className="text-xs text-gray-400 mb-1">Active Accounts</div>
              <div className="text-2xl font-bold text-white">{data.metrics.active_accounts}</div>
            </div>
          )}
          {data.metrics.pending_orders !== undefined && (
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-3">
              <div className="text-xs text-gray-400 mb-1">Pending Orders</div>
              <div className="text-2xl font-bold text-white">{data.metrics.pending_orders}</div>
            </div>
          )}
          {data.metrics.signals_today !== undefined && (
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-3">
              <div className="text-xs text-gray-400 mb-1">Signals Today</div>
              <div className="text-2xl font-bold text-white">{data.metrics.signals_today}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
