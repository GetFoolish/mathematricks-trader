import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, ChevronDown, ChevronUp, Loader2, AlertCircle } from 'lucide-react';
import { Pagination } from '../components/Pagination';
import { FormulaTooltip } from '../components/FormulaTooltip';
import { formatTableDate, formatTableNumber, formatCurrency } from '../utils/dataFormatters';
import type { StrategySubmission, BacktestDataPoint } from '../types';
import apiClient from '../services/api';

interface ColumnConfig {
  key: string;
  label: string;
  width: string;
  align: 'left' | 'right';
  format: (value: any) => string;
}

// Define column configurations - using actual field names from backend
const COLUMNS = [
  {
    key: 'Date',
    label: 'Date',
    width: 'w-32',
    align: 'left' as const,
    format: (v: any) => formatTableDate(v)
  },
  {
    key: 'Daily_Return_Pct',
    label: 'Daily Return %',
    width: 'w-32',
    align: 'right' as const,
    format: (v: any) => formatTableNumber(v, 4)
  },
  {
    key: 'Daily_PnL',
    label: 'Daily P&L',
    width: 'w-36',
    align: 'right' as const,
    format: (v: any) => formatCurrency(v)
  },
  {
    key: 'Account_Equity',
    label: 'Account Equity',
    width: 'w-36',
    align: 'right' as const,
    format: (v: any) => formatCurrency(v)
  },
  {
    key: 'Max_Margin_Used',
    label: 'Max Margin Used',
    width: 'w-36',
    align: 'right' as const,
    format: (v: any) => formatCurrency(v)
  },
  {
    key: 'Max_Notional_Value',
    label: 'Max Notional Value',
    width: 'w-40',
    align: 'right' as const,
    format: (v: any) => formatCurrency(v)
  },
];

// Map column keys to the names stored in synthetic_data.columns_generated
const COLUMN_KEY_TO_SYNTHETIC_NAME: Record<string, string> = {
  'Account_Equity': 'Account_Equity',
  'Daily_PnL': 'Daily_PnL',
  'Max_Margin_Used': 'Max_Margin_Used',
  'Max_Notional_Value': 'Max_Notional_Value'
};

const RawDataViewer: React.FC = () => {
  const { submissionId } = useParams<{ submissionId: string }>();
  const navigate = useNavigate();

  const [submission, setSubmission] = useState<StrategySubmission | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [expandedColumns, setExpandedColumns] = useState<Set<string>>(new Set());

  // Load submission data
  useEffect(() => {
    const loadSubmission = async () => {
      if (!submissionId) {
        setError('No submission ID provided');
        setIsLoading(false);
        return;
      }

      try {
        // Try sessionStorage first
        const dataKey = `raw-data-${submissionId}`;
        const cached = sessionStorage.getItem(dataKey);

        if (cached) {
          const parsedData = JSON.parse(cached);
          setSubmission(parsedData);
          setIsLoading(false);
        } else {
          // Fallback to API fetch
          const data = await apiClient.getSubmission(submissionId);
          setSubmission(data);
          setIsLoading(false);
        }
      } catch (err: any) {
        setError(err.message || 'Failed to load submission data');
        setIsLoading(false);
      }
    };

    loadSubmission();
  }, [submissionId]);

  // Calculate paginated data
  const paginatedData = useMemo(() => {
    if (!submission?.raw_data_backtest_full) return [];
    const start = (currentPage - 1) * pageSize;
    const end = start + pageSize;
    return submission.raw_data_backtest_full.slice(start, end);
  }, [submission, currentPage, pageSize]);

  // Get synthetic columns set
  const syntheticColumnsSet = useMemo(() => {
    if (!submission?.synthetic_data?.columns_generated) return new Set<string>();
    return new Set(submission.synthetic_data.columns_generated);
  }, [submission]);

  // Check if a column is synthetic
  const isColumnSynthetic = (columnKey: string): boolean => {
    const syntheticName = COLUMN_KEY_TO_SYNTHETIC_NAME[columnKey];
    return syntheticName ? syntheticColumnsSet.has(syntheticName) : false;
  };

  // Toggle formula expansion
  const toggleFormula = (columnKey: string) => {
    setExpandedColumns(prev => {
      const newSet = new Set(prev);
      if (newSet.has(columnKey)) {
        newSet.delete(columnKey);
      } else {
        newSet.add(columnKey);
      }
      return newSet;
    });
  };

  // Handle page changes
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handlePageSizeChange = (size: number) => {
    setPageSize(size);
    setCurrentPage(1); // Reset to first page
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-12 w-12 text-purple-500 animate-spin mx-auto mb-4" />
          <p className="text-gray-400">Loading backtest data...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !submission) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center p-4">
        <div className="bg-gray-800 rounded-lg p-6 max-w-md w-full text-center">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-white mb-2">Error Loading Data</h2>
          <p className="text-gray-400 mb-4">{error || 'Submission not found'}</p>
          <button
            onClick={() => navigate('/strategy-approval')}
            className="btn-primary"
          >
            Back to Fresh Strategies
          </button>
        </div>
      </div>
    );
  }

  // Empty data state
  if (!submission.raw_data_backtest_full || submission.raw_data_backtest_full.length === 0) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center p-4">
        <div className="bg-gray-800 rounded-lg p-6 max-w-md w-full text-center">
          <AlertCircle className="h-12 w-12 text-yellow-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-white mb-2">No Data Available</h2>
          <p className="text-gray-400 mb-4">This submission has no backtest data.</p>
          <button
            onClick={() => navigate('/strategy-approval')}
            className="btn-primary"
          >
            Back to Fresh Strategies
          </button>
        </div>
      </div>
    );
  }

  const totalPages = Math.ceil(submission.raw_data_backtest_full.length / pageSize);
  const startDate = submission.raw_data_backtest_full[0]?.Date;
  const endDate = submission.raw_data_backtest_full[submission.raw_data_backtest_full.length - 1]?.Date;
  const syntheticCount = submission.synthetic_data?.columns_generated?.length || 0;

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 sticky top-0 z-20">
        <div className="max-w-[1800px] mx-auto px-6 py-4">
          <div className="flex items-center gap-4">
            <button
              onClick={() => window.close()}
              className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
            >
              <ArrowLeft className="h-5 w-5" />
              <span>Close</span>
            </button>
            <div className="flex-1">
              <h1 className="text-2xl font-semibold">{submission.strategy_name}</h1>
              <p className="text-sm text-gray-400">Raw Backtest Data</p>
            </div>
          </div>
        </div>
      </div>

      {/* Metadata Cards */}
      <div className="max-w-[1800px] mx-auto px-6 py-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-gray-800 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Date Range</div>
            <div className="text-lg font-semibold">
              {formatTableDate(startDate)} - {formatTableDate(endDate)}
            </div>
          </div>
          <div className="bg-gray-800 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Total Data Points</div>
            <div className="text-lg font-semibold">
              {submission.raw_data_backtest_full.length.toLocaleString()} days
            </div>
          </div>
          <div className="bg-gray-800 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Synthetic Columns</div>
            <div className="text-lg font-semibold">
              {syntheticCount === 0 ? (
                <span className="text-green-400">None (all original)</span>
              ) : (
                <span className="text-purple-400">
                  {syntheticCount} column{syntheticCount !== 1 ? 's' : ''} generated
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Legend */}
        {syntheticCount > 0 && (
          <div className="bg-purple-900/20 border border-purple-700 rounded-lg p-4 mb-6">
            <h3 className="text-sm font-semibold text-purple-300 mb-2">Column Legend</h3>
            <div className="flex flex-wrap gap-6 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-white rounded"></div>
                <span>Original Data (uploaded by developer)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-gray-400 rounded"></div>
                <span className="italic">Synthetic Data (calculated by system)</span>
              </div>
            </div>
            <p className="text-xs text-gray-400 mt-2">
              Click the + button on synthetic column headers to view calculation formulas
            </p>
          </div>
        )}

        {/* Table */}
        <div className="bg-gray-800 rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="table-sticky-header">
                  {COLUMNS.map((column) => {
                    const synthetic = isColumnSynthetic(column.key);
                    const isExpanded = expandedColumns.has(column.key);
                    const syntheticName = COLUMN_KEY_TO_SYNTHETIC_NAME[column.key];

                    return (
                      <th
                        key={column.key}
                        className={`table-header ${column.width} ${column.align === 'right' ? 'text-right' : 'text-left'} ${
                          synthetic ? 'synthetic-column' : ''
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className={column.align === 'right' ? 'ml-auto' : ''}>
                            {column.label}
                          </span>
                          {synthetic && syntheticName && (
                            <button
                              onClick={() => toggleFormula(column.key)}
                              className="p-1 hover:bg-purple-700/50 rounded transition-colors"
                              title="View calculation formula"
                            >
                              {isExpanded ? (
                                <ChevronUp className="h-4 w-4" />
                              ) : (
                                <ChevronDown className="h-4 w-4" />
                              )}
                            </button>
                          )}
                        </div>
                        {synthetic && syntheticName && (
                          <FormulaTooltip
                            columnName={syntheticName}
                            isExpanded={isExpanded}
                            onToggle={() => toggleFormula(column.key)}
                          />
                        )}
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {paginatedData.map((row, index) => (
                  <tr key={index} className="table-row-hover border-t border-gray-700">
                    {COLUMNS.map((column) => {
                      const synthetic = isColumnSynthetic(column.key);
                      return (
                        <td
                          key={column.key}
                          className={`table-cell ${column.align === 'right' ? 'text-right' : 'text-left'} ${
                            synthetic ? 'synthetic-column' : ''
                          }`}
                        >
                          {column.format(row[column.key])}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="border-t border-gray-700 p-4">
            <Pagination
              currentPage={currentPage}
              totalPages={totalPages}
              pageSize={pageSize}
              totalItems={submission.raw_data_backtest_full.length}
              onPageChange={handlePageChange}
              onPageSizeChange={handlePageSizeChange}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default RawDataViewer;
