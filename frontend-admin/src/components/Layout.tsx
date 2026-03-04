import React, { useState, useEffect } from 'react';
import { Link, useLocation, Outlet } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  LayoutDashboard,
  PieChart,
  Activity,
  Settings,
  LogOut,
  TrendingUp,
  Wrench,
  CheckCircle,
  CreditCard,
  ChevronDown,
  Cloud,
  HardDrive,
} from 'lucide-react';

export const Layout: React.FC = () => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [mongoDbMode, setMongoDbMode] = useState<'cloud' | 'local'>('cloud');

  const navigation = [
    { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
    { name: 'Activity', href: '/activity', icon: Activity },
    { name: 'Allocations', href: '/allocations', icon: PieChart },
    { name: 'Approved Strategies', href: '/strategies', icon: Settings },
    { name: 'Fresh Strategies', href: '/strategy-approval', icon: CheckCircle },
    { name: 'Accounts', href: '/accounts', icon: CreditCard },
    { name: 'Hedged Funds', href: '/hedged-funds', icon: Wrench },
  ];

  // Get API base URL from environment
  const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  // Fetch current MongoDB mode on mount
  useEffect(() => {
    const fetchMongoDbMode = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/mongodb-mode`);
        const data = await response.json();
        setMongoDbMode(data.mode);
      } catch (error) {
        console.error('Failed to fetch MongoDB mode:', error);
      }
    };
    fetchMongoDbMode();
  }, []);

  // Toggle MongoDB connection
  const toggleMongoDb = async () => {
    const newMode = mongoDbMode === 'cloud' ? 'local' : 'cloud';
    try {
      const response = await fetch(`${API_BASE_URL}/api/mongodb-mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: newMode }),
      });
      
      if (response.ok) {
        setMongoDbMode(newMode);
        // Reload the page to refresh all data with new connection
        window.location.reload();
      } else {
        console.error('Failed to switch MongoDB mode');
      }
    } catch (error) {
      console.error('Error switching MongoDB mode:', error);
    }
  };

  const isActive = (path: string) => {
    if (path === '/activity') {
      return location.pathname.startsWith('/activity');
    }
    return location.pathname === path;
  };

  return (
    <div className="h-screen bg-gray-900 flex flex-col overflow-hidden">
      {/* Header with Navigation */}
      <header className="bg-gray-800 border-b border-gray-700 flex-shrink-0">
        <div className="px-6 py-4 flex items-center justify-between">
          {/* Logo/Brand */}
          <div className="flex items-center space-x-2 px-4 py-2 border border-gray-600 rounded-lg">
            <TrendingUp className="h-7 w-7 text-blue-500" />
            <div>
              <h1 className="text-lg font-bold text-white">Mathematricks</h1>
              <p className="text-xs text-gray-400">Trading Admin</p>
            </div>
          </div>

          {/* Navigation Menu */}
          <nav className="flex items-center space-x-1">
            {navigation.map((item, index) => {
              const Icon = item.icon;
              const active = isActive(item.href);
              return (
                <React.Fragment key={item.name}>
                  {index > 0 && (
                    <div className="h-8 w-px bg-gray-600 mx-1"></div>
                  )}
                  <Link
                    to={item.href}
                    className={`flex items-center space-x-2 px-4 py-2.5 rounded-lg transition-colors ${
                      active
                        ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/30'
                        : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                    }`}
                  >
                    <Icon className="h-5 w-5" />
                    <span className="font-medium">{item.name}</span>
                  </Link>
                </React.Fragment>
              );
            })}
          </nav>

          {/* User Section */}
          <div className="relative">
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="flex items-center space-x-3 px-4 py-2 hover:bg-gray-700 rounded-lg transition-colors"
            >
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm font-semibold">
                {user?.username?.[0]?.toUpperCase() || 'A'}
              </div>
              <div className="text-left">
                <p className="text-sm font-medium text-white">{user?.username || 'Admin'}</p>
                <p className="text-xs text-gray-400">{user?.role || 'ADMIN'}</p>
              </div>
              <ChevronDown className={`h-4 w-4 text-gray-400 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
            </button>
            
            {/* Dropdown Menu */}
            {dropdownOpen && (
              <div className="absolute right-0 mt-2 w-64 bg-gray-800 border border-gray-700 rounded-lg shadow-lg z-50">
                {/* MongoDB Connection Toggle */}
                <div className="px-4 py-3 border-b border-gray-700">
                  <p className="text-xs text-gray-400 mb-2">Database Connection</p>
                  <button
                    onClick={toggleMongoDb}
                    className="w-full flex items-center justify-between px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
                  >
                    <div className="flex items-center space-x-2">
                      {mongoDbMode === 'cloud' ? (
                        <Cloud className="h-4 w-4 text-blue-400" />
                      ) : (
                        <HardDrive className="h-4 w-4 text-green-400" />
                      )}
                      <span className="text-sm font-medium text-white">
                        {mongoDbMode === 'cloud' ? 'Cloud (Atlas)' : 'Local (27018)'}
                      </span>
                    </div>
                    <div className={`w-10 h-5 rounded-full transition-colors ${mongoDbMode === 'cloud' ? 'bg-blue-600' : 'bg-green-600'} relative`}>
                      <div className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform ${mongoDbMode === 'cloud' ? 'translate-x-5' : 'translate-x-0'}`}></div>
                    </div>
                  </button>
                  <p className="text-xs text-gray-500 mt-1 text-center">
                    Click to switch
                  </p>
                </div>
                
                {/* Logout Button */}
                <button
                  onClick={() => {
                    logout();
                    setDropdownOpen(false);
                  }}
                  className="w-full flex items-center space-x-2 px-4 py-3 hover:bg-gray-700 text-white rounded-b-lg transition-colors"
                >
                  <LogOut className="h-4 w-4" />
                  <span className="text-sm font-medium">Logout</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto p-8">
        <Outlet />
      </main>
    </div>
  );
};
