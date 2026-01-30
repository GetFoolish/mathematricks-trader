import React, { useState } from 'react';
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
} from 'lucide-react';

export const Layout: React.FC = () => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const navigation = [
    { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
    { name: 'Activity', href: '/activity', icon: Activity },
    { name: 'Allocations', href: '/allocations', icon: PieChart },
    { name: 'Approved Strategies', href: '/strategies', icon: Settings },
    { name: 'Fresh Strategies', href: '/strategy-approval', icon: CheckCircle },
    { name: 'Accounts', href: '/accounts', icon: CreditCard },
    { name: 'Hedged Funds', href: '/hedged-funds', icon: Wrench },
  ];

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
              <div className="absolute right-0 mt-2 w-48 bg-gray-800 border border-gray-700 rounded-lg shadow-lg z-50">
                <button
                  onClick={() => {
                    logout();
                    setDropdownOpen(false);
                  }}
                  className="w-full flex items-center space-x-2 px-4 py-3 hover:bg-gray-700 text-white rounded-lg transition-colors"
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
