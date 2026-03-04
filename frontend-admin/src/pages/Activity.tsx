import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import RawSignalsTab from '../components/activity/RawSignalsTab';
import SignalStoreTab from '../components/activity/SignalStoreTab';

type TabType = 'raw-signals' | 'signal-store';

export default function Activity() {
  const { tab } = useParams<{ tab?: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabType>('raw-signals');

  // Update active tab from URL
  useEffect(() => {
    if (tab === 'signal-store' || tab === 'signal_store') {
      setActiveTab('signal-store');
    } else if (tab === 'raw-signals' || tab === 'raw_signals') {
      setActiveTab('raw-signals');
    } else if (!tab) {
      // Default to raw-signals if no tab specified
      setActiveTab('raw-signals');
    }
  }, [tab]);

  const tabs: { key: TabType; label: string; description: string }[] = [
    { key: 'raw-signals', label: 'Raw Signals', description: 'trading_signals_raw collection' },
    { key: 'signal-store', label: 'Signal Store', description: 'signal_store collection' },
  ];

  return (
    <div className="flex flex-col h-screen bg-gray-900">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 px-6 py-4">
        <h1 className="text-2xl font-bold text-white">Activity</h1>
        <p className="text-sm text-gray-400 mt-1">Monitor signals, orders, and trading activity</p>
      </div>

      {/* Tab Navigation */}
      <div className="bg-gray-800 border-b border-gray-700">
        <nav className="flex space-x-8 px-6" aria-label="Tabs">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => {
                setActiveTab(tab.key);
                navigate(`/activity/${tab.key}`);
              }}
              className={`
                py-4 px-1 border-b-2 font-medium text-sm transition-colors
                ${
                  activeTab === tab.key
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-gray-400 hover:text-gray-200 hover:border-gray-500'
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
      </div>
    </div>
  );
}
