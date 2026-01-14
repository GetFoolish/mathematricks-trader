import React from 'react';

interface FormulaData {
  formula: string;
  explanation: string;
  example: string;
}

const FORMULA_EXPLANATIONS: Record<string, FormulaData> = {
  'Account_Equity': {
    formula: 'equity[i] = equity[i-1] × (1 + return/100)',
    explanation: 'Calculated by compounding daily returns starting from $100,000',
    example: 'Day 1: $100,000 × (1 + 2.5/100) = $102,500'
  },
  'Daily_PnL': {
    formula: 'pnl[i] = equity[i] - equity[i-1]',
    explanation: 'Difference between consecutive equity values',
    example: 'If equity went from $100,000 to $102,500, PnL = $2,500'
  },
  'Max_Margin_Used': {
    formula: 'margin[i] = (|return[i]| / max_return) × equity[i] × 0.8',
    explanation: 'Normalized by maximum return, scaled to 80% of equity',
    example: 'If |return| = 2%, max_return = 5%, equity = $100k → margin = (2/5) × $100k × 0.8 = $32k'
  },
  'Max_Notional_Value': {
    formula: 'notional[i] = margin[i] × 3',
    explanation: 'Assumes 3x leverage on margin used',
    example: 'If margin = $32,000 → notional = $96,000'
  }
};

export interface FormulaTooltipProps {
  columnName: string;
  isExpanded: boolean;
  onToggle: () => void;
}

export const FormulaTooltip: React.FC<FormulaTooltipProps> = React.memo(({
  columnName,
  isExpanded
}) => {
  const formulaData = FORMULA_EXPLANATIONS[columnName];

  if (!formulaData) {
    return null;
  }

  return (
    <div className="relative">
      {isExpanded && (
        <div className="formula-tooltip animate-expand text-left">
          <div className="mb-2">
            <div className="text-xs font-semibold text-purple-300 mb-1">Formula:</div>
            <code className="text-xs text-white bg-gray-900/50 px-2 py-1 rounded block">
              {formulaData.formula}
            </code>
          </div>
          <div className="mb-2">
            <div className="text-xs font-semibold text-purple-300 mb-1">Explanation:</div>
            <p className="text-xs text-gray-300">{formulaData.explanation}</p>
          </div>
          <div>
            <div className="text-xs font-semibold text-purple-300 mb-1">Example:</div>
            <p className="text-xs text-gray-300">{formulaData.example}</p>
          </div>
        </div>
      )}
    </div>
  );
});

FormulaTooltip.displayName = 'FormulaTooltip';

export { FORMULA_EXPLANATIONS };
