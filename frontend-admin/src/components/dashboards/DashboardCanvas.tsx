/**
 * DashboardCanvas Component
 *
 * Main dashboard canvas with drag-and-drop grid layout.
 * Supports locking/unlocking, widget rearrangement, and "Reload All" functionality.
 */
import React, { useState, useCallback, useEffect } from 'react';
import GridLayout from 'react-grid-layout';
import type { Layout } from 'react-grid-layout';
import { Lock, Unlock, RefreshCw } from 'lucide-react';
import { WidgetWrapper } from './WidgetWrapper';
import { apiClient } from '../../services/api';
import type { Dashboard } from '../../types';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

interface DashboardCanvasProps {
  dashboard: Dashboard;
  onLayoutChange: (updatedWidgets: Dashboard['widgets']) => Promise<void>;
  onReloadAll: () => Promise<void>;
}

export const DashboardCanvas: React.FC<DashboardCanvasProps> = ({
  dashboard,
  onLayoutChange,
  onReloadAll,
}) => {
  const [isLocked, setIsLocked] = useState(dashboard.is_locked);
  const [isReloading, setIsReloading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [refreshCountdown, setRefreshCountdown] = useState(5);

  // Auto-refresh every 5 seconds
  useEffect(() => {
    const interval = setInterval(async () => {
      setIsReloading(true);
      try {
        await onReloadAll();
      } catch (error) {
        console.error('Auto-refresh failed:', error);
      } finally {
        setIsReloading(false);
      }
      setRefreshCountdown(5);
    }, 5000);

    const countdownInterval = setInterval(() => {
      setRefreshCountdown(prev => prev > 0 ? prev - 1 : 5);
    }, 1000);

    return () => {
      clearInterval(interval);
      clearInterval(countdownInterval);
    };
  }, [onReloadAll]);

  // Convert dashboard widgets to react-grid-layout format
  const layout: Layout[] = dashboard.widgets.map((widget) => ({
    i: widget.widget_id,
    x: widget.position.x,
    y: widget.position.y,
    w: widget.position.w,
    h: widget.position.h,
    minW: 2,
    minH: 2,
  }));

  const handleLayoutChange = useCallback(
    async (newLayout: Layout[]) => {
      if (isLocked) return;

      // Convert layout back to dashboard widgets format
      const updatedWidgets = dashboard.widgets.map((widget) => {
        const layoutItem = newLayout.find((l) => l.i === widget.widget_id);
        if (!layoutItem) return widget;

        return {
          ...widget,
          position: {
            x: layoutItem.x,
            y: layoutItem.y,
            w: layoutItem.w,
            h: layoutItem.h,
          },
        };
      });

      // Only save if positions actually changed
      const hasChanged = updatedWidgets.some((widget, index) => {
        const original = dashboard.widgets[index];
        return (
          widget.position.x !== original.position.x ||
          widget.position.y !== original.position.y ||
          widget.position.w !== original.position.w ||
          widget.position.h !== original.position.h
        );
      });

      if (hasChanged) {
        setIsSaving(true);
        try {
          await onLayoutChange(updatedWidgets);
        } finally {
          setIsSaving(false);
        }
      }
    },
    [dashboard.widgets, isLocked, onLayoutChange]
  );

  const toggleLock = async () => {
    const newLockState = !isLocked;
    setIsLocked(newLockState);

    // Save lock state to backend
    try {
      await apiClient.updateDashboard(dashboard.dashboard_id, {
        is_locked: newLockState,
      });
    } catch (error) {
      console.error('Failed to update lock state:', error);
      // Revert on error
      setIsLocked(!newLockState);
    }
  };

  const handleReloadAll = async () => {
    setIsReloading(true);
    try {
      await onReloadAll();
    } finally {
      setIsReloading(false);
    }
  };

  const handleManualRefresh = () => {
    handleReloadAll();
    setRefreshCountdown(5);
  };

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-6 py-4 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center space-x-4">
          <h2 className="text-xl font-bold text-white">{dashboard.name}</h2>
          {dashboard.description && (
            <span className="text-sm text-gray-400">{dashboard.description}</span>
          )}
          {isSaving && (
            <span className="text-xs text-blue-400 flex items-center space-x-1">
              <RefreshCw className="w-3 h-3 animate-spin" />
              <span>Saving...</span>
            </span>
          )}
        </div>

        <div className="flex items-center space-x-2">
          {/* Reload All Button with Countdown */}
          <button
            onClick={handleManualRefresh}
            disabled={isReloading}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded flex items-center space-x-2 transition-colors disabled:opacity-50"
            title="Reload all widgets"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" className="transform -rotate-90">
              <circle
                cx="8"
                cy="8"
                r="6"
                fill="none"
                stroke="rgba(255,255,255,0.3)"
                strokeWidth="2"
              />
              {[0, 1, 2, 3, 4].map((slice) => {
                const sliceAngle = 360 / 5;
                const startAngle = slice * sliceAngle;
                const endAngle = (slice + 1) * sliceAngle;
                
                const startRad = (startAngle - 90) * Math.PI / 180;
                const endRad = (endAngle - 90) * Math.PI / 180;
                
                const x1 = 8 + 6 * Math.cos(startRad);
                const y1 = 8 + 6 * Math.sin(startRad);
                const x2 = 8 + 6 * Math.cos(endRad);
                const y2 = 8 + 6 * Math.sin(endRad);
                
                const largeArc = sliceAngle > 180 ? 1 : 0;
                
                return (
                  <path
                    key={slice}
                    d={`M 8 8 L ${x1} ${y1} A 6 6 0 ${largeArc} 1 ${x2} ${y2} Z`}
                    fill="white"
                    opacity={refreshCountdown > slice ? 0.9 : 0.2}
                    className="transition-opacity duration-200"
                  />
                );
              })}
            </svg>
            <span>Refresh</span>
          </button>

          {/* Lock/Unlock Button */}
          <button
            onClick={toggleLock}
            className={`px-3 py-1.5 text-sm rounded flex items-center space-x-2 transition-colors ${
              isLocked
                ? 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                : 'bg-yellow-600 hover:bg-yellow-700 text-white'
            }`}
            title={isLocked ? 'Unlock dashboard' : 'Lock dashboard'}
          >
            {isLocked ? (
              <>
                <Lock className="w-4 h-4" />
                <span>Locked</span>
              </>
            ) : (
              <>
                <Unlock className="w-4 h-4" />
                <span>Unlocked</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Grid Layout */}
      <div className="flex-1 overflow-auto p-6 bg-gray-950">
        {dashboard.widgets.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center text-gray-500">
              <div className="text-lg mb-2">No widgets on this dashboard</div>
              <div className="text-sm">Add widgets from the library to get started</div>
            </div>
          </div>
        ) : (
          <GridLayout
            className="layout"
            layout={layout}
            cols={dashboard.grid_config.cols}
            rowHeight={dashboard.grid_config.row_height}
            width={1200}
            isDraggable={!isLocked}
            isResizable={!isLocked}
            onLayoutChange={handleLayoutChange}
            draggableHandle=".drag-handle"
            compactType="vertical"
            preventCollision={false}
          >
            {dashboard.widgets.map((widget) => (
              <div key={widget.widget_id} className="grid-item">
                <div className="drag-handle absolute top-0 left-0 right-0 h-8 cursor-move z-20" />
                <WidgetWrapper widget={widget} fundId={dashboard.fund_id} />
              </div>
            ))}
          </GridLayout>
        )}
      </div>
    </div>
  );
};
