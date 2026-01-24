import React from 'react';

// StatusDot Component
export const StatusDot = ({ status, tooltip }: { status: 'gray' | 'green' | 'orange' | 'red'; tooltip: string }) => {
  const colorClasses = {
    gray: 'bg-gray-500',
    green: 'bg-green-500',
    orange: 'bg-orange-500',
    red: 'bg-red-500',
  };

  return (
    <div className="relative group inline-block">
      <div className={`w-3.5 h-3.5 rounded-full ${colorClasses[status]}`}></div>
      <div className="absolute hidden group-hover:block bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 border border-gray-600 text-white text-xs rounded shadow-xl whitespace-nowrap z-[9999] pointer-events-none">
        {tooltip}
        <div className="absolute top-full left-1/2 transform -translate-x-1/2 -mt-1">
          <div className="border-4 border-transparent border-t-gray-900"></div>
        </div>
      </div>
    </div>
  );
};

// Get service status for a leg from signal_store
export const getServiceStatus = (leg: any) => {
  // Signal Ingestion Status
  // If the leg exists in signal_store, ingestion was successful
  let ingestionStatus: 'gray' | 'green' | 'orange' | 'red' = 'green';
  let ingestionTooltip = 'Signal Ingestion: Successfully received';
  
  if (leg.raw?.error || leg.raw?.failed) {
    ingestionStatus = 'red';
    ingestionTooltip = 'Signal Ingestion: Failed/Error';
  }

  // Cerebro Decision Status
  let cerebroStatus: 'gray' | 'green' | 'orange' | 'red' = 'gray';
  let cerebroTooltip = 'Cerebro: No decision';
  
  if (leg.decision) {
    if (leg.decision.status === 'REJECTED') {
      cerebroStatus = 'red';
      cerebroTooltip = 'Cerebro: Rejected';
    } else if (leg.decision.status === 'APPROVED') {
      cerebroStatus = 'green';
      cerebroTooltip = 'Cerebro: Approved';
    } else if (leg.decision.status === 'PENDING') {
      cerebroStatus = 'orange';
      cerebroTooltip = 'Cerebro: Pending';
    }
  }

  // Execution Status
  let executionStatus: 'gray' | 'green' | 'orange' | 'red' = 'gray';
  let executionTooltip = 'Execution: No execution data';
  
  if (leg.execution) {
    const execStatus = leg.execution.status?.toUpperCase();
    if (['REJECTED', 'CANCELLED', 'ERROR', 'FAILED'].includes(execStatus)) {
      executionStatus = 'red';
      executionTooltip = `Execution: ${execStatus}`;
    } else if (['FILLED', 'COMPLETED'].includes(execStatus)) {
      executionStatus = 'green';
      executionTooltip = `Execution: ${execStatus}`;
    } else if (['PENDING', 'SUBMITTED', 'WORKING', 'PARTIAL'].includes(execStatus)) {
      executionStatus = 'orange';
      executionTooltip = `Execution: ${execStatus}`;
    }
  }

  return {
    ingestion: { status: ingestionStatus, tooltip: ingestionTooltip },
    cerebro: { status: cerebroStatus, tooltip: cerebroTooltip },
    execution: { status: executionStatus, tooltip: executionTooltip },
  };
};

// Get service status for a raw signal by finding it in signal_store
export const getServiceStatusForRawSignal = (rawSignal: any, signalStore: any[]) => {
  const signalID = rawSignal.signalID;
  const mathematricksSignalId = rawSignal.mathematricks_signal_id;
  
  // Try to find the signal in signal_store by signal_id or base_signal_id or _id
  let signal = signalStore.find(s => 
    s.signal_id === signalID || s.base_signal_id === signalID || s._id === mathematricksSignalId
  );
  
  // Default: not sent to signal_store yet
  if (!signal || !signal.legs || signal.legs.length === 0) {
    return {
      ingestion: { status: 'gray' as const, tooltip: 'Signal Ingestion: Not processed' },
      cerebro: { status: 'gray' as const, tooltip: 'Cerebro: No decision' },
      execution: { status: 'gray' as const, tooltip: 'Execution: No execution data' }
    };
  }
  
  // For EXIT signals, find the specific leg that matches this signal
  if (rawSignal.signal_type === 'EXIT') {
    const matchingLeg = signal.legs.find((leg: any) => 
      leg.leg_id && leg.leg_id.startsWith(signalID)
    );
    if (matchingLeg) {
      return getServiceStatus(matchingLeg);
    }
  }
  
  // For ENTRY signals or when leg not found, use the first leg
  return getServiceStatus(signal.legs[0]);
};
