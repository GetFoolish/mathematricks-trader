import React from 'react';
import { Clock, AlertCircle, CheckCircle } from 'lucide-react';

interface ProcessingLag {
  service_lags: {
    signal_ingestion?: number;
    cerebro?: number;
    execution?: number;
  };
  total_lag_ms: number;
  sum_of_service_lags_ms: number;
  unaccounted_lag_ms: number;
  stages: Array<{
    service: string;
    lag_ms: number;
    timestamp: string;
  }>;
  summary: string;
}

interface ProcessingLagDisplayProps {
  processingLag: ProcessingLag | null;
  processingTimestamps?: {
    signal_received?: string;
    signal_ingestion_processed?: string;
    cerebro_processed?: string;
    execution_started?: string;
    execution_completed?: string;
  };
  compact?: boolean;
}

export const ProcessingLagDisplay: React.FC<ProcessingLagDisplayProps> = ({ 
  processingLag, 
  processingTimestamps,
  compact = false 
}) => {
  if (!processingLag && !processingTimestamps) {
    return (
      <div className="text-xs text-gray-500 italic">
        No timing data available
      </div>
    );
  }

  // If we have timestamps but no calculated lag, show timestamps
  if (!processingLag && processingTimestamps) {
    return (
      <div className="text-xs space-y-1">
        <div className="text-gray-400">Processing Timestamps:</div>
        {processingTimestamps.signal_received && (
          <div className="text-gray-300">
            • Received: {new Date(processingTimestamps.signal_received).toLocaleTimeString()}
          </div>
        )}
        {processingTimestamps.signal_ingestion_processed && (
          <div className="text-gray-300">
            • Ingestion: {new Date(processingTimestamps.signal_ingestion_processed).toLocaleTimeString()}
          </div>
        )}
        {processingTimestamps.cerebro_processed && (
          <div className="text-gray-300">
            • Cerebro: {new Date(processingTimestamps.cerebro_processed).toLocaleTimeString()}
          </div>
        )}
        {processingTimestamps.execution_completed && (
          <div className="text-gray-300">
            • Execution: {new Date(processingTimestamps.execution_completed).toLocaleTimeString()}
          </div>
        )}
      </div>
    );
  }

  const formatLag = (ms: number): string => {
    // Always display in seconds with milliseconds as decimals
    const seconds = ms / 1000;
    if (seconds < 0.01) return `${seconds.toFixed(4)}s`;  // Very small: 4 decimals
    if (seconds < 1) return `${seconds.toFixed(3)}s`;     // Sub-second: 3 decimals
    if (seconds < 10) return `${seconds.toFixed(2)}s`;    // Single digit: 2 decimals
    return `${seconds.toFixed(1)}s`;                       // Larger: 1 decimal
  };

  const getLagColor = (ms: number): string => {
    if (ms < 10) return 'text-green-400';
    if (ms < 100) return 'text-yellow-400';
    if (ms < 1000) return 'text-orange-400';
    return 'text-red-400';
  };

  const unaccountedColor = Math.abs(processingLag.unaccounted_lag_ms) > 10 
    ? 'text-orange-400' 
    : 'text-gray-400';

  if (compact) {
    return (
      <div className="flex items-center gap-2 text-xs">
        <Clock size={12} className="text-gray-400" />
        <span className={getLagColor(processingLag.total_lag_ms)}>
          {formatLag(processingLag.total_lag_ms)}
        </span>
        {Math.abs(processingLag.unaccounted_lag_ms) > 1 && (
          <span className={unaccountedColor} title="Unaccounted lag (network/queue time)">
            (+{formatLag(processingLag.unaccounted_lag_ms)})
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Service-by-Service Breakdown */}
      <div className="space-y-2">
        <div className="text-xs font-semibold text-gray-400 flex items-center gap-2">
          <Clock size={14} />
          Processing Pipeline
        </div>
        
        <div className="space-y-1.5">
          {processingLag.stages.map((stage, idx) => (
            <div key={idx} className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-blue-500"></div>
                <span className="text-gray-300 capitalize">
                  {stage.service.replace('_', ' ')}
                </span>
              </div>
              <span className={`font-mono font-semibold ${getLagColor(stage.lag_ms)}`}>
                {formatLag(stage.lag_ms)}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Total and Summary */}
      <div className="border-t border-gray-700 pt-2 space-y-1.5">
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-400">Sum of Service Lags:</span>
          <span className="font-mono text-gray-300">
            {formatLag(processingLag.sum_of_service_lags_ms)}
          </span>
        </div>
        
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-400">Total End-to-End:</span>
          <span className={`font-mono font-bold ${getLagColor(processingLag.total_lag_ms)}`}>
            {formatLag(processingLag.total_lag_ms)}
          </span>
        </div>
        
        {Math.abs(processingLag.unaccounted_lag_ms) > 0.1 && (
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-1">
              <span className="text-gray-400">Unaccounted:</span>
              <AlertCircle 
                size={12} 
                className={unaccountedColor}
                title="Network latency, queue time, or other overhead"
              />
            </div>
            <span className={`font-mono ${unaccountedColor}`}>
              {formatLag(processingLag.unaccounted_lag_ms)}
            </span>
          </div>
        )}
      </div>

      {/* Quick Summary Badge */}
      <div className="flex items-center gap-2 text-xs bg-gray-800 rounded px-2 py-1">
        <CheckCircle size={12} className="text-green-400" />
        <span className="text-gray-300 font-mono">
          {processingLag.summary}
        </span>
      </div>
    </div>
  );
};
