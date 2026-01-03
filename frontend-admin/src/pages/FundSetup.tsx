import { useState } from 'react';
import { ArrowLeft, ArrowRight, Check, Plus, Edit2, Trash2, AlertCircle, ChevronDown, ChevronRight } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Step1CreateFunds from './FundSetup/Step1CreateFunds';
import Step2ConfigureAccounts from './FundSetup/Step2ConfigureAccounts';
import Step4ReviewExport from './FundSetup/Step4ReviewExport';
import { apiClient } from '../services/api';
import type { Fund, TradingAccount } from '../types';

const WIZARD_STEPS = [
  { id: 1, title: 'Fund Details', description: 'Define fund structure' },
  { id: 2, title: 'Configure Accounts', description: 'Set up broker accounts' },
  { id: 3, title: 'Review & Finish', description: 'Validate configuration' },
];

export default function HedgedFunds() {
  const [showWizard, setShowWizard] = useState<boolean>(false);
  const [editingFund, setEditingFund] = useState<Fund | null>(null);
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [wizardFunds, setWizardFunds] = useState<Fund[]>([]);
  const [wizardAccounts, setWizardAccounts] = useState<TradingAccount[]>([]);
  const [expandedFundId, setExpandedFundId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  // Fetch all funds
  const { data: funds, isLoading } = useQuery({
    queryKey: ['funds'],
    queryFn: async () => {
      const response = await apiClient.getFunds();
      return response;
    },
  });

  // Fetch all accounts
  const { data: allAccounts } = useQuery({
    queryKey: ['accounts'],
    queryFn: async () => {
      const response = await apiClient.getAccounts();
      return response;
    },
  });

  // Delete fund mutation
  const deleteFundMutation = useMutation({
    mutationFn: (fundId: string) => apiClient.deleteFund(fundId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['funds'] });
    },
    onError: (error: any) => {
      alert(`Failed to delete fund: ${error.response?.data?.detail || error.message}`);
    },
  });

  const handleAddFund = () => {
    setEditingFund(null);
    setWizardFunds([]);
    setWizardAccounts([]);
    setCurrentStep(1);
    setShowWizard(true);
  };

  const handleEditFund = (fund: Fund) => {
    setEditingFund(fund);
    setWizardFunds([fund]);
    // Load accounts for this fund
    const fundAccounts = allAccounts?.filter((a: TradingAccount) => a.fund_id === fund.fund_id) || [];
    setWizardAccounts(fundAccounts);
    setCurrentStep(1);
    setShowWizard(true);
  };

  const handleDeleteFund = async (fundId: string) => {
    if (confirm('Are you sure you want to delete this fund? This action cannot be undone.')) {
      deleteFundMutation.mutate(fundId);
    }
  };

  const handleToggleExpand = (fundId: string) => {
    setExpandedFundId(expandedFundId === fundId ? null : fundId);
  };

  const handleCloseWizard = () => {
    setShowWizard(false);
    setEditingFund(null);
    setWizardFunds([]);
    setWizardAccounts([]);
    setCurrentStep(1);
    queryClient.invalidateQueries({ queryKey: ['funds'] });
    queryClient.invalidateQueries({ queryKey: ['accounts'] });
  };

  const handleNext = () => {
    if (currentStep < WIZARD_STEPS.length) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handlePrevious = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleStepClick = (stepId: number) => {
    setCurrentStep(stepId);
  };

  // MAIN FUND LIST VIEW (DEFAULT)
  if (!showWizard) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="mb-8 flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
                Hedged Funds
              </h1>
              <p className="mt-2 text-gray-600 dark:text-gray-400">
                Manage your fund structure, broker accounts, and allocations
              </p>
            </div>
            <button
              onClick={handleAddFund}
              className="flex items-center px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-semibold"
            >
              <Plus className="w-5 h-5 mr-2" />
              Add Fund
            </button>
          </div>

          {/* Fund List */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg overflow-hidden">
            {isLoading ? (
              <div className="p-8 text-center text-gray-500">Loading funds...</div>
            ) : funds && funds.length > 0 ? (
              <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                <thead className="bg-gray-50 dark:bg-gray-900">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Fund Name
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Fund ID
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Total Equity
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Currency
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Accounts
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                  {funds.map((fund: Fund) => {
                    const isExpanded = expandedFundId === fund.fund_id;
                    const fundAccounts = allAccounts?.filter((a: TradingAccount) => a.fund_id === fund.fund_id) || [];
                    
                    return (
                      <>
                        <tr 
                          key={fund.fund_id} 
                          className="hover:bg-gray-50 dark:hover:bg-gray-700"
                        >
                          <td 
                            className="px-6 py-4 whitespace-nowrap cursor-pointer"
                            onClick={() => handleToggleExpand(fund.fund_id)}
                          >
                            <div className="flex items-center">
                              {isExpanded ? (
                                <ChevronDown className="w-5 h-5 text-gray-500 mr-2" />
                              ) : (
                                <ChevronRight className="w-5 h-5 text-gray-500 mr-2" />
                              )}
                              <div>
                                <div className="text-sm font-medium text-gray-900 dark:text-white">
                                  {fund.name}
                                </div>
                                {fund.description && (
                                  <div className="text-xs text-gray-500">
                                    {fund.description}
                                  </div>
                                )}
                              </div>
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                            {fund.fund_id}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white font-semibold">
                            ${fund.total_equity?.toLocaleString() || '0'}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                            {fund.currency}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                            {fund.accounts?.length || 0}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${
                              fund.status === 'ACTIVE'
                                ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                                : fund.status === 'PAUSED'
                                ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                                : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                            }`}>
                              {fund.status}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                            <button
                              onClick={(e) => { e.stopPropagation(); handleEditFund(fund); }}
                              className="text-blue-600 hover:text-blue-900 dark:text-blue-400 dark:hover:text-blue-300 mr-4"
                              title="Edit fund"
                            >
                              <Edit2 className="w-5 h-5 inline" />
                            </button>
                            <button
                              onClick={(e) => { e.stopPropagation(); handleDeleteFund(fund.fund_id); }}
                              className="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300"
                              title="Delete fund"
                            >
                              <Trash2 className="w-5 h-5 inline" />
                            </button>
                          </td>
                        </tr>
                        
                        {/* Expanded Details Row */}
                        {isExpanded && (
                          <tr className="bg-gray-100 dark:bg-gray-800">
                            <td colSpan={7} className="px-6 py-4">
                              <div className="space-y-4">
                                <div>
                                  <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">
                                    Fund Details
                                  </h4>
                                  <div className="grid grid-cols-2 gap-4 text-sm">
                                    <div>
                                      <span className="text-gray-500 dark:text-gray-400">Currency:</span>
                                      <span className="ml-2 text-gray-900 dark:text-white">{fund.currency}</span>
                                    </div>
                                    <div>
                                      <span className="text-gray-500 dark:text-gray-400">Total Equity:</span>
                                      <span className="ml-2 text-gray-900 dark:text-white font-semibold">
                                        ${fund.total_equity?.toLocaleString() || '0'}
                                      </span>
                                    </div>
                                    {fund.description && (
                                      <div className="col-span-2">
                                        <span className="text-gray-500 dark:text-gray-400">Description:</span>
                                        <p className="mt-1 text-gray-900 dark:text-white">{fund.description}</p>
                                      </div>
                                    )}
                                  </div>
                                </div>

                                {/* Accounts Section */}
                                <div>
                                  <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">
                                    Accounts ({fundAccounts.length})
                                  </h4>
                                  {fundAccounts.length > 0 ? (
                                    <div className="space-y-2">
                                      {fundAccounts.map((account: TradingAccount) => (
                                        <div 
                                          key={account.account_id}
                                          className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700"
                                        >
                                          <div className="flex justify-between items-start">
                                            <div>
                                              <div className="text-sm font-medium text-gray-900 dark:text-white">
                                                {account.account_id}
                                              </div>
                                              <div className="text-xs text-gray-500 mt-1">
                                                Broker: {account.broker} | Equity: ${account.equity?.toLocaleString() || '0'}
                                              </div>
                                              <div className="mt-2 flex flex-wrap gap-1">
                                                {Object.entries(account.asset_classes || {})
                                                  .filter(([_, values]) => values.length > 0)
                                                  .map(([assetClass, values]) => (
                                                    <span 
                                                      key={assetClass}
                                                      className="px-2 py-1 text-xs bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded"
                                                    >
                                                      {assetClass}: {values.join(', ')}
                                                    </span>
                                                  ))}
                                              </div>
                                            </div>
                                            <span className={`px-2 py-1 text-xs font-semibold rounded ${
                                              account.status === 'ACTIVE'
                                                ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                                                : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                                            }`}>
                                              {account.status}
                                            </span>
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  ) : (
                                    <p className="text-sm text-gray-500 dark:text-gray-400">
                                      No accounts configured for this fund.
                                    </p>
                                  )}
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <div className="p-12 text-center">
                <AlertCircle className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
                  No funds configured
                </h3>
                <p className="text-gray-500 dark:text-gray-400 mb-6">
                  Get started by creating your first fund
                </p>
                <button
                  onClick={handleAddFund}
                  className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  <Plus className="w-5 h-5 mr-2" />
                  Create First Fund
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // WIZARD VIEW (WHEN ADDING/EDITING FUND)
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8 flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
              {editingFund ? `Edit Fund: ${editingFund.name}` : 'Add New Fund'}
            </h1>
            <p className="mt-2 text-gray-600 dark:text-gray-400">
              Configure fund details and broker accounts
            </p>
          </div>
          <button
            onClick={handleCloseWizard}
            className="px-4 py-2 bg-gray-300 dark:bg-gray-700 text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-400 dark:hover:bg-gray-600 transition-colors"
          >
            Cancel
          </button>
        </div>

        {/* Stepper */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            {WIZARD_STEPS.map((step, index) => (
              <div key={step.id} className="flex items-center flex-1">
                {/* Step Circle */}
                <button
                  onClick={() => handleStepClick(step.id)}
                  className={`
                    relative flex items-center justify-center w-12 h-12 rounded-full
                    border-2 transition-all
                    ${
                      currentStep === step.id
                        ? 'border-blue-600 bg-blue-600 text-white'
                        : currentStep > step.id
                        ? 'border-green-600 bg-green-600 text-white'
                        : 'border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-400'
                    }
                    hover:scale-110
                  `}
                >
                  {currentStep > step.id ? (
                    <Check className="w-6 h-6" />
                  ) : (
                    <span className="text-lg font-semibold">{step.id}</span>
                  )}
                </button>

                {/* Step Info */}
                <div className="ml-4">
                  <p className={`text-sm font-medium ${
                    currentStep >= step.id ? 'text-gray-900 dark:text-white' : 'text-gray-400'
                  }`}>
                    {step.title}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {step.description}
                  </p>
                </div>

                {/* Connector Line */}
                {index < WIZARD_STEPS.length - 1 && (
                  <div className="flex-1 mx-4">
                    <div className={`h-1 rounded ${
                      currentStep > step.id
                        ? 'bg-green-600'
                        : 'bg-gray-300 dark:bg-gray-600'
                    }`} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Step Content */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-8 min-h-[600px]">
          {currentStep === 1 && (
            <Step1CreateFunds funds={wizardFunds} setFunds={setWizardFunds} />
          )}
          {currentStep === 2 && (
            <Step2ConfigureAccounts 
              funds={wizardFunds} 
              accounts={wizardAccounts} 
              setAccounts={setWizardAccounts} 
            />
          )}
          {currentStep === 3 && (
            <Step4ReviewExport 
              funds={wizardFunds} 
              accounts={wizardAccounts}
              onFinish={handleCloseWizard}
            />
          )}
        </div>

        {/* Navigation Buttons */}
        <div className="mt-6 flex justify-between">
          <button
            onClick={handlePrevious}
            disabled={currentStep === 1}
            className={`
              flex items-center px-6 py-3 rounded-lg font-medium transition-colors
              ${
                currentStep === 1
                  ? 'bg-gray-200 dark:bg-gray-700 text-gray-400 cursor-not-allowed'
                  : 'bg-gray-300 dark:bg-gray-700 text-gray-700 dark:text-gray-200 hover:bg-gray-400 dark:hover:bg-gray-600'
              }
            `}
          >
            <ArrowLeft className="w-5 h-5 mr-2" />
            Previous
          </button>

          <button
            onClick={handleNext}
            disabled={currentStep === WIZARD_STEPS.length}
            className={`
              flex items-center px-6 py-3 rounded-lg font-medium transition-colors
              ${
                currentStep === WIZARD_STEPS.length
                  ? 'bg-gray-200 dark:bg-gray-700 text-gray-400 cursor-not-allowed'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
              }
            `}
          >
            Next
            <ArrowRight className="w-5 h-5 ml-2" />
          </button>
        </div>
      </div>
    </div>
  );
}
