import { useState } from 'react';
import { ArrowLeft, ArrowRight, Check } from 'lucide-react';
import Step1CreateFunds from './FundSetup/Step1CreateFunds';
import Step2ConfigureAccounts from './FundSetup/Step2ConfigureAccounts';
import Step3MapStrategies from './FundSetup/Step3MapStrategies';
import Step4ReviewExport from './FundSetup/Step4ReviewExport';
import type { Fund, TradingAccount } from '../types';

const STEPS = [
  { id: 1, title: 'Create Funds', description: 'Define top-level fund structure' },
  { id: 2, title: 'Configure Accounts', description: 'Set up broker accounts' },
  { id: 3, title: 'Map Strategies', description: 'Assign strategies to accounts' },
  { id: 4, title: 'Review & Export', description: 'Validate and export configuration' },
];

export default function FundSetup() {
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [funds, setFunds] = useState<Fund[]>([]);
  const [accounts, setAccounts] = useState<TradingAccount[]>([]);

  const handleNext = () => {
    if (currentStep < STEPS.length) {
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

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            Fund & Account Setup Wizard
          </h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            Configure your fund architecture, broker accounts, and strategy mappings
          </p>
        </div>

        {/* Stepper */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            {STEPS.map((step, index) => (
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
                {index < STEPS.length - 1 && (
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
            <Step1CreateFunds funds={funds} setFunds={setFunds} />
          )}
          {currentStep === 2 && (
            <Step2ConfigureAccounts 
              funds={funds} 
              accounts={accounts} 
              setAccounts={setAccounts} 
            />
          )}
          {currentStep === 3 && (
            <Step3MapStrategies funds={funds} accounts={accounts} />
          )}
          {currentStep === 4 && (
            <Step4ReviewExport funds={funds} accounts={accounts} />
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
            disabled={currentStep === STEPS.length}
            className={`
              flex items-center px-6 py-3 rounded-lg font-medium transition-colors
              ${
                currentStep === STEPS.length
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
