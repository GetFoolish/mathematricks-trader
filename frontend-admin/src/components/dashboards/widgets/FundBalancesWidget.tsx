/**
 * FundBalancesWidget Component
 *
 * Displays fund totals with expandable account breakdowns.
 * Shows equity, cash, margin, and unrealized P&L for each account.
 */
import React, { useState } from 'react';
import { ChevronDown, ChevronUp, TrendingUp, TrendingDown } from 'lucide-react';
import type { FundBalancesData } from '../../../types';

interface FundBalancesWidgetProps {
  data: FundBalancesData;
}

export const FundBalancesWidget: React.FC<FundBalancesWidgetProps> = ({ data }) => {
  const [expandedFunds, setExpandedFunds] = useState<Set<string>>(new Set());

  const toggleFund = (fundId: string) => {
    const newExpanded = new Set(expandedFunds);
    if (newExpanded.has(fundId)) {
      newExpanded.delete(fundId);
    } else {
      newExpanded.add(fundId);
    }
    setExpandedFunds(newExpanded);
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  const getPnLColor = (pnl: number) => {
    if (pnl > 0) return 'text-green-500';
    if (pnl < 0) return 'text-red-500';
    return 'text-gray-400';
  };

  return (
    <div className="space-y-4">
      {/* Total Equity Header */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">Total Equity</div>
        <div className="text-3xl font-bold text-white">
          {formatCurrency(data.total_equity)}
        </div>
      </div>

      {/* Funds List */}
      <div className="space-y-2">
        {data.funds.map((fund) => (
          <div key={fund.fund_id} className="bg-gray-800 rounded-lg border border-gray-700">
            {/* Fund Header - Clickable */}
            <button
              onClick={() => toggleFund(fund.fund_id)}
              className="w-full p-4 flex items-center justify-between hover:bg-gray-750 transition-colors"
            >
              <div className="flex items-center space-x-3">
                <div className="text-left">
                  <div className="text-sm font-medium text-white">{fund.fund_name}</div>
                  <div className="text-xs text-gray-400">{fund.fund_id}</div>
                </div>
              </div>
              <div className="flex items-center space-x-3">
                <div className="text-right">
                  <div className="text-sm font-semibold text-white">
                    {formatCurrency(fund.total_balance)}
                  </div>
                  <div className="text-xs text-gray-400">
                    {fund.accounts.length} account{fund.accounts.length !== 1 ? 's' : ''}
                  </div>
                </div>
                {expandedFunds.has(fund.fund_id) ? (
                  <ChevronUp className="w-5 h-5 text-gray-400" />
                ) : (
                  <ChevronDown className="w-5 h-5 text-gray-400" />
                )}
              </div>
            </button>

            {/* Account Breakdown - Expandable */}
            {expandedFunds.has(fund.fund_id) && (
              <div className="px-4 pb-4 space-y-2 border-t border-gray-700">
                {fund.accounts.map((account) => (
                  <div
                    key={account.account_id}
                    className="bg-gray-900 rounded p-3 space-y-2"
                  >
                    {/* Account Header */}
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-sm font-medium text-white">
                          {account.account_id}
                        </div>
                        <div className="text-xs text-gray-400">{account.broker}</div>
                      </div>
                      <div className="text-sm font-semibold text-white">
                        {formatCurrency(account.equity)}
                      </div>
                    </div>

                    {/* Account Details Grid */}
                    <div className="grid grid-cols-3 gap-2 pt-2 border-t border-gray-800">
                      <div>
                        <div className="text-xs text-gray-500">Cash</div>
                        <div className="text-sm text-gray-300">
                          {formatCurrency(account.cash)}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-500">Margin Used</div>
                        <div className="text-sm text-gray-300">
                          {formatCurrency(account.margin_used)}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-500">Unrealized P&L</div>
                        <div className={`text-sm font-medium flex items-center space-x-1 ${getPnLColor(account.unrealized_pnl)}`}>
                          {account.unrealized_pnl > 0 ? (
                            <TrendingUp className="w-3 h-3" />
                          ) : account.unrealized_pnl < 0 ? (
                            <TrendingDown className="w-3 h-3" />
                          ) : null}
                          <span>{formatCurrency(account.unrealized_pnl)}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Empty State */}
      {data.funds.length === 0 && (
        <div className="text-center py-8 text-gray-500">
          <div className="text-sm">No active funds found</div>
        </div>
      )}
    </div>
  );
};
