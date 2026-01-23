import { useState } from 'react';
import RawSignalsTab from '../components/activity/RawSignalsTab';
import SignalStoreTab from '../components/activity/SignalStoreTab';
import TradingOrdersTab from '../components/activity/TradingOrdersTab';
import SignalStatusTab from '../components/activity/SignalStatusTab';

type TabType = 'raw-signals' | 'signal-store' | 'trading-orders' | 'signal-status';

export default function Activity() {
  const [activeTab, setActiveTab] = useState<TabType>('raw-signals');

  const tabs: { key: TabType; label: string; description: string }[] = [
    { key: 'raw-signals', label: 'Raw Signals', description: 'trading_signals_raw collection' },
    { key: 'signal-store', label: 'Signal Store', description: 'signal_store collection' },
    { key: 'trading-orders', label: 'Trading Orders', description: 'trading_orders collection' },
    { key: 'signal-status', label: 'Signal Status', description: 'Summary view (one row per signal)' },
  ];

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <h1 className="text-2xl font-bold text-gray-900">Activity</h1>
        <p className="text-sm text-gray-500 mt-1">Monitor signals, orders, and trading activity</p>
      </div>

      {/* Tab Navigation */}
      <div className="bg-white border-b border-gray-200">
        <nav className="flex space-x-8 px-6" aria-label="Tabs">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`
                py-4 px-1 border-b-2 font-medium text-sm transition-colors
                ${
                  activeTab === tab.key
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }
              `}
            >
              <div>
                <div>{tab.label}</div>
                <div className="text-xs text-gray-400 mt-1">{tab.description}</div>
              </div>
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'raw-signals' && <RawSignalsTab />}
        {activeTab === 'signal-store' && <SignalStoreTab />}
        {activeTab === 'trading-orders' && <TradingOrdersTab />}
        {activeTab === 'signal-status' && <SignalStatusTab />}
      </div>
    </div>
  );
}
