/**
 * useWidgetSSE Hook
 *
 * Connects to the Dashboard Creator SSE endpoint for real-time widget updates.
 * When widget data is regenerated on the backend, this hook invalidates the
 * React Query cache, triggering automatic re-fetches of stale widget data.
 */
import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';

interface WidgetUpdateEvent {
  widget_type: string;
  fund_id: string | null;
  timestamp: string;
}

const DASHBOARD_CREATOR_URL = import.meta.env.VITE_DASHBOARD_CREATOR_URL || 'http://localhost:8004';

export const useWidgetSSE = (dashboardId?: string) => {
  const queryClient = useQueryClient();
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!dashboardId) {
      return;
    }

    // Connect to SSE endpoint
    const eventSource = new EventSource(`${DASHBOARD_CREATOR_URL}/api/v1/widgets/events`);
    eventSourceRef.current = eventSource;

    console.log('[SSE] Connected to widget updates stream');

    eventSource.onmessage = (event) => {
      try {
        const data: WidgetUpdateEvent = JSON.parse(event.data);

        console.log('[SSE] Widget updated:', data.widget_type, 'for fund:', data.fund_id || 'all');

        // Invalidate React Query cache for this widget type
        // This will trigger automatic re-fetch of the widget data
        queryClient.invalidateQueries({
          queryKey: ['widget', data.widget_type, data.fund_id],
        });
      } catch (error) {
        console.error('[SSE] Error parsing event:', error);
      }
    };

    eventSource.onerror = (error) => {
      console.error('[SSE] Connection error:', error);
      // EventSource automatically reconnects on error
    };

    eventSource.onopen = () => {
      console.log('[SSE] Connection established');
    };

    // Cleanup on unmount
    return () => {
      console.log('[SSE] Disconnecting from widget updates stream');
      eventSource.close();
      eventSourceRef.current = null;
    };
  }, [dashboardId, queryClient]);
};
