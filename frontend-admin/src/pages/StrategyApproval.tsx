import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../services/api';
import { CheckCircle, XCircle, Eye, Filter, Clock, CheckCheck, Ban, Upload, Trash2, ArrowLeft, ArrowRight, FileText } from 'lucide-react';
import type { StrategySubmission, ApproveSubmissionRequest } from '../types';

const UPLOAD_STEPS = [
  { id: 1, title: 'Upload CSV', description: 'Select your backtest file' },
  { id: 2, title: 'Map Columns', description: 'Align columns to our format' },
  { id: 3, title: 'Developer Info', description: 'Provide contact details' },
];

export const StrategyApproval: React.FC = () => {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>('PENDING_APPROVAL');
  const [selectedSubmission, setSelectedSubmission] = useState<StrategySubmission | null>(null);
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [showRejectionModal, setShowRejectionModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showUploadWizard, setShowUploadWizard] = useState(false);

  const { data: submissions, isLoading } = useQuery({
    queryKey: ['strategy-submissions', statusFilter],
    queryFn: () => apiClient.getStrategySubmissions(statusFilter),
  });

  const approveMutation = useMutation({
    mutationFn: ({ submissionId, data }: { submissionId: string; data: ApproveSubmissionRequest }) =>
      apiClient.approveSubmission(submissionId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strategy-submissions'] });
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
      setShowApprovalModal(false);
      setSelectedSubmission(null);
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ submissionId, reason }: { submissionId: string; reason: string }) =>
      apiClient.rejectSubmission(submissionId, { rejection_reason: reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strategy-submissions'] });
      setShowRejectionModal(false);
      setSelectedSubmission(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (submissionId: string) => apiClient.deleteSubmission(submissionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strategy-submissions'] });
      setShowDeleteModal(false);
      setSelectedSubmission(null);
    },
  });

  const handleViewDetails = (submission: StrategySubmission) => {
    setSelectedSubmission(submission);
  };

  const handleApprove = (submission: StrategySubmission) => {
    setSelectedSubmission(submission);
    setShowApprovalModal(true);
  };

  const handleReject = (submission: StrategySubmission) => {
    setSelectedSubmission(submission);
    setShowRejectionModal(true);
  };

  const handleDelete = (submission: StrategySubmission) => {
    setSelectedSubmission(submission);
    setShowDeleteModal(true);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  const formatNumber = (num: number, decimals: number = 2) => {
    return num.toFixed(decimals);
  };

  const getStatusBadge = (status: string) => {
    const styles = {
      PENDING_APPROVAL: 'bg-yellow-900 text-yellow-300',
      APPROVED: 'bg-green-900 text-green-300',
      REJECTED: 'bg-red-900 text-red-300',
    };
    return styles[status as keyof typeof styles] || 'bg-gray-700 text-gray-300';
  };

  const getStatusIcon = (status: string) => {
    if (status === 'PENDING_APPROVAL') return <Clock className="h-4 w-4" />;
    if (status === 'APPROVED') return <CheckCheck className="h-4 w-4" />;
    if (status === 'REJECTED') return <Ban className="h-4 w-4" />;
    return null;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Fresh Strategies</h2>
          <p className="text-gray-400 mt-1">Review and approve strategy submissions from developers</p>
        </div>
        <button
          onClick={() => setShowUploadWizard(true)}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
        >
          <Upload className="h-5 w-5" />
          <span>Upload Strategy</span>
        </button>
      </div>

      <div className="flex items-center space-x-4">
        <Filter className="h-5 w-5 text-gray-400" />
        <div className="flex space-x-2">
          {['PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'ALL'].map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status === 'ALL' ? '' : status)}
              className={`px-4 py-2 rounded-lg transition-colors ${
                (status === 'ALL' && statusFilter === '') || statusFilter === status
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              {status.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="bg-gray-800 rounded-lg p-8 text-center">
          <p className="text-gray-400">Loading submissions...</p>
        </div>
      ) : submissions && submissions.length > 0 ? (
        <div className="bg-gray-800 rounded-lg overflow-hidden">
          <table className="w-full divide-y divide-gray-700">
            <thead className="bg-gray-900">
              <tr>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-400 uppercase">Status</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-400 uppercase">Strategy</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-400 uppercase">Developer</th>
                <th className="px-2 py-2 text-left text-xs font-medium text-gray-400 uppercase">CAGR</th>
                <th className="px-2 py-2 text-left text-xs font-medium text-gray-400 uppercase">Sharpe</th>
                <th className="px-2 py-2 text-left text-xs font-medium text-gray-400 uppercase">Max DD</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-400 uppercase">Submitted</th>
                <th className="px-3 py-2 text-right text-xs font-medium text-gray-400 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {submissions.map((submission) => (
                <tr key={submission.submission_id} className="hover:bg-gray-750">
                  <td className="px-3 py-2 whitespace-nowrap">
                    <div className={`inline-flex items-center space-x-1 px-2 py-1 rounded-full text-xs ${getStatusBadge(submission.status)}`}>
                      {getStatusIcon(submission.status)}
                      <span>{submission.status === 'PENDING_APPROVAL' ? 'PENDING' : submission.status}</span>
                      {submission.tearsheet_generated && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            window.open(`http://localhost:8003/api/v1/public/submission/${submission.submission_id}/tearsheet`, '_blank');
                          }}
                          className="text-blue-400 hover:text-blue-300 transition-colors"
                          title="View Tearsheet"
                        >
                          <FileText className="h-3 w-3" />
                        </button>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap text-sm font-medium text-white">{submission.strategy_name}</td>
                  <td className="px-3 py-2 whitespace-nowrap text-xs text-gray-300">
                    <div>{submission.developer_info.name}</div>
                    <div className="text-xs text-gray-500">{submission.developer_info.email}</div>
                  </td>
                  <td className="px-2 py-2 whitespace-nowrap text-xs text-white">{formatNumber(submission.metrics.cagr, 1)}%</td>
                  <td className="px-2 py-2 whitespace-nowrap text-xs text-white">{formatNumber(submission.metrics.sharpe_ratio, 2)}</td>
                  <td className="px-2 py-2 whitespace-nowrap text-xs text-white">{formatNumber(submission.metrics.max_drawdown, 1)}%</td>
                  <td className="px-3 py-2 whitespace-nowrap text-xs text-gray-400">{formatDate(submission.submitted_at)}</td>
                  <td className="px-3 py-2 whitespace-nowrap text-right text-xs space-x-1">
                    <button
                      onClick={() => handleViewDetails(submission)}
                      className="inline-flex items-center px-2 py-1 bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors"
                    >
                      <Eye className="h-3 w-3 mr-1" />
                      View
                    </button>
                    {submission.status === 'PENDING_APPROVAL' && (
                      <>
                        <button
                          onClick={() => handleApprove(submission)}
                          className="inline-flex items-center px-2 py-1 bg-green-600 hover:bg-green-700 text-white rounded transition-colors"
                        >
                          <CheckCircle className="h-3 w-3 mr-1" />
                          Approve
                        </button>
                        <button
                          onClick={() => handleReject(submission)}
                          className="inline-flex items-center px-2 py-1 bg-red-600 hover:bg-red-700 text-white rounded transition-colors"
                        >
                          <XCircle className="h-3 w-3 mr-1" />
                          Reject
                        </button>
                      </>
                    )}
                    <button
                      onClick={() => handleDelete(submission)}
                      className="inline-flex items-center px-2 py-1 bg-red-900 hover:bg-red-800 text-white rounded transition-colors"
                    >
                      <Trash2 className="h-3 w-3 mr-1" />
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="bg-gray-800 rounded-lg p-8 text-center">
          <p className="text-gray-400">No submissions found for this status</p>
        </div>
      )}

      {selectedSubmission && !showApprovalModal && !showRejectionModal && !showDeleteModal && (
        <DetailsModal submission={selectedSubmission} onClose={() => setSelectedSubmission(null)} />
      )}

      {showApprovalModal && selectedSubmission && (
        <ApprovalModal
          submission={selectedSubmission}
          onApprove={(data) => approveMutation.mutate({ submissionId: selectedSubmission.submission_id, data })}
          onClose={() => { setShowApprovalModal(false); setSelectedSubmission(null); }}
          isLoading={approveMutation.isPending}
        />
      )}

      {showRejectionModal && selectedSubmission && (
        <RejectionModal
          submission={selectedSubmission}
          onReject={(reason) => rejectMutation.mutate({ submissionId: selectedSubmission.submission_id, reason })}
          onClose={() => { setShowRejectionModal(false); setSelectedSubmission(null); }}
          isLoading={rejectMutation.isPending}
        />
      )}

      {showDeleteModal && selectedSubmission && (
        <DeleteConfirmationModal
          submission={selectedSubmission}
          onDelete={() => deleteMutation.mutate(selectedSubmission.submission_id)}
          onClose={() => { setShowDeleteModal(false); setSelectedSubmission(null); }}
          isLoading={deleteMutation.isPending}
        />
      )}

      {showUploadWizard && (
        <UploadWizard
          onClose={() => setShowUploadWizard(false)}
          onSuccess={() => {
            setShowUploadWizard(false);
            queryClient.invalidateQueries({ queryKey: ['strategy-submissions'] });
          }}
        />
      )}
    </div>
  );
};

const DeleteConfirmationModal: React.FC<{
  submission: StrategySubmission;
  onDelete: () => void;
  onClose: () => void;
  isLoading: boolean;
}> = ({ submission, onDelete, onClose, isLoading }) => {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-lg shadow-xl max-w-md w-full p-6">
        <div className="flex items-center space-x-3 mb-4">
          <Trash2 className="h-6 w-6 text-red-500" />
          <h3 className="text-xl font-bold text-white">Confirm Delete</h3>
        </div>
        <p className="text-gray-300 mb-4">Are you sure you want to permanently delete this strategy submission?</p>
        <div className="bg-gray-900 rounded-lg p-4 mb-6">
          <div className="text-sm text-gray-400">Strategy Name:</div>
          <div className="text-white font-semibold">{submission.strategy_name}</div>
          <div className="text-sm text-gray-400 mt-2">Developer:</div>
          <div className="text-white">{submission.developer_info.name}</div>
          <div className="text-gray-500 text-sm">{submission.developer_info.email}</div>
        </div>
        <div className="bg-red-900 bg-opacity-20 border border-red-700 rounded-lg p-3 mb-6">
          <p className="text-red-300 text-sm">⚠️ This action cannot be undone. The submission will be permanently removed.</p>
        </div>
        <div className="flex justify-end space-x-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isLoading}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onDelete}
            disabled={isLoading}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors disabled:opacity-50"
          >
            {isLoading ? 'Deleting...' : 'Delete Permanently'}
          </button>
        </div>
      </div>
    </div>
  );
};

const UploadWizard: React.FC<{
  onClose: () => void;
  onSuccess: () => void;
}> = ({ onClose, onSuccess }) => {
  const [currentStep, setCurrentStep] = useState(1);
  const [file, setFile] = useState<File | null>(null);
  const [csvColumns, setCsvColumns] = useState<string[]>([]);
  const [columnMapping, setColumnMapping] = useState<Record<string, string>>({});
  const [developerInfo, setDeveloperInfo] = useState({
    name: '',
    email: '',
    phone: '',
    countryCode: '+1',
    comment: '',
  });
  const [strategyName, setStrategyName] = useState('');
  const [isUploading, setIsUploading] = useState(false);

  const handleFileSelect = async (selectedFile: File) => {
    setFile(selectedFile);
    // Auto-populate strategy name from filename
    setStrategyName(selectedFile.name.replace('.csv', ''));
    const text = await selectedFile.text();
    const lines = text.split('\n');
    if (lines.length > 0) {
      const headers = lines[0].split(',').map(h => h.trim());
      setCsvColumns(headers);
      const autoMapping: Record<string, string> = {};
      headers.forEach(col => {
        const lowerCol = col.toLowerCase();
        if (lowerCol.includes('date')) autoMapping['Date'] = col;
        if (lowerCol.includes('return')) autoMapping['Daily_Return_Pct'] = col;
        if (lowerCol.includes('equity')) autoMapping['Account_Equity'] = col;
        if (lowerCol.includes('pnl') || lowerCol.includes('profit')) autoMapping['Daily_PnL'] = col;
        if (lowerCol.includes('margin')) autoMapping['Max_Margin_Used'] = col;
        if (lowerCol.includes('notional')) autoMapping['Max_Notional_Value'] = col;
      });
      setColumnMapping(autoMapping);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('strategy_name', strategyName);
      formData.append('developer_name', developerInfo.name);
      formData.append('developer_email', developerInfo.email);
      formData.append('developer_note', `${developerInfo.comment}\n\nPhone: ${developerInfo.countryCode}${developerInfo.phone}`);

      const response = await fetch('http://localhost:8003/api/v1/public/submit-strategy', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Upload failed');
      }
      onSuccess();
    } catch (error) {
      alert(`Upload failed: ${error}`);
    } finally {
      setIsUploading(false);
    }
  };

  const canProceedToStep2 = file !== null;
  const canProceedToStep3 = columnMapping['Date'] && columnMapping['Daily_Return_Pct'];
  const canSubmit = strategyName && developerInfo.name && developerInfo.email && developerInfo.phone;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex items-center justify-between pb-4 border-b border-gray-700 mb-6">
            <h3 className="text-2xl font-bold text-white">Upload Strategy</h3>
            <button onClick={onClose} disabled={isUploading} className="text-gray-400 hover:text-white">
              <XCircle className="h-6 w-6" />
            </button>
          </div>

          <div className="mb-8">
            <div className="flex items-center justify-between">
              {UPLOAD_STEPS.map((step, index) => (
                <React.Fragment key={step.id}>
                  <div className="flex flex-col items-center flex-1">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold mb-2 ${
                      currentStep >= step.id ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-400'
                    }`}>
                      {step.id}
                    </div>
                    <div className={`text-sm font-medium ${currentStep >= step.id ? 'text-white' : 'text-gray-400'}`}>
                      {step.title}
                    </div>
                    <div className="text-xs text-gray-500">{step.description}</div>
                  </div>
                  {index < UPLOAD_STEPS.length - 1 && (
                    <div className={`flex-1 h-1 mx-4 rounded ${currentStep > step.id ? 'bg-blue-600' : 'bg-gray-700'}`} />
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>

          <div className="min-h-[400px]">
            {currentStep === 1 && <Step1UploadFile file={file} onFileSelect={handleFileSelect} />}
            {currentStep === 2 && <Step2MapColumns csvColumns={csvColumns} columnMapping={columnMapping} onMappingChange={setColumnMapping} />}
            {currentStep === 3 && <Step3DeveloperInfo developerInfo={developerInfo} onInfoChange={setDeveloperInfo} strategyName={strategyName} onStrategyNameChange={setStrategyName} />}
          </div>

          <div className="flex justify-between pt-6 border-t border-gray-700">
            <button
              onClick={() => setCurrentStep(Math.max(1, currentStep - 1))}
              disabled={currentStep === 1 || isUploading}
              className="flex items-center space-x-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors disabled:opacity-50"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>Previous</span>
            </button>

            {currentStep < 3 ? (
              <button
                onClick={() => setCurrentStep(currentStep + 1)}
                disabled={(currentStep === 1 && !canProceedToStep2) || (currentStep === 2 && !canProceedToStep3)}
                className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50"
              >
                <span>Next</span>
                <ArrowRight className="h-4 w-4" />
              </button>
            ) : (
              <button
                onClick={handleUpload}
                disabled={!canSubmit || isUploading}
                className="flex items-center space-x-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors disabled:opacity-50"
              >
                {isUploading ? <span>Uploading...</span> : (
                  <>
                    <Upload className="h-4 w-4" />
                    <span>Upload Strategy</span>
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

const Step1UploadFile: React.FC<{ file: File | null; onFileSelect: (file: File) => void; }> = ({ file, onFileSelect }) => {
  const [isDragging, setIsDragging] = useState(false);

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      const droppedFile = files[0];
      if (droppedFile.name.endsWith('.csv')) {
        onFileSelect(droppedFile);
      } else {
        alert('Please upload a CSV file');
      }
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h4 className="text-lg font-semibold text-white mb-2">Select Your Backtest CSV File</h4>
        <p className="text-gray-400 text-sm mb-4">Upload a CSV file containing your strategy's backtest data.</p>
      </div>
      <div
        className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
          isDragging
            ? 'border-blue-500 bg-blue-500 bg-opacity-10'
            : 'border-gray-600 hover:border-blue-500'
        }`}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        <input
          type="file"
          accept=".csv"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) onFileSelect(f); }}
          className="hidden"
          id="file-upload"
        />
        <label htmlFor="file-upload" className="cursor-pointer block">
          <Upload className="h-12 w-12 mx-auto mb-4 text-gray-400" />
          <p className="text-white font-medium mb-2">{file ? file.name : 'Click to select a CSV file'}</p>
          <p className="text-gray-500 text-sm">or drag and drop</p>
        </label>
      </div>
      {file && (
        <div className="bg-gray-900 rounded-lg p-4">
          <div className="flex items-center space-x-2 text-green-400">
            <CheckCircle className="h-5 w-5" />
            <span className="font-medium">File selected: {file.name}</span>
          </div>
          <p className="text-gray-400 text-sm mt-1">Size: {(file.size / 1024).toFixed(2)} KB</p>
        </div>
      )}
      <div className="bg-blue-900 bg-opacity-20 border border-blue-700 rounded-lg p-4">
        <h5 className="text-blue-300 font-medium mb-2">Required Columns:</h5>
        <ul className="text-gray-300 text-sm space-y-1">
          <li>• <span className="font-mono">Date</span> - Date of each data point</li>
          <li>• <span className="font-mono">Daily_Return_Pct</span> - Daily return percentage</li>
        </ul>
      </div>
    </div>
  );
};

const Step2MapColumns: React.FC<{
  csvColumns: string[];
  columnMapping: Record<string, string>;
  onMappingChange: (mapping: Record<string, string>) => void;
}> = ({ csvColumns, columnMapping, onMappingChange }) => {
  const COLUMNS = {
    Date: { required: true, description: 'Date of each data point' },
    Daily_Return_Pct: { required: true, description: 'Daily return percentage' },
    Account_Equity: { required: false, description: 'Account equity (will be generated if missing)' },
    Daily_PnL: { required: false, description: 'Daily profit/loss (will be generated if missing)' },
    Max_Margin_Used: { required: false, description: 'Maximum margin (will be generated if missing)' },
    Max_Notional_Value: { required: false, description: 'Maximum notional value (will be generated if missing)' },
  };

  return (
    <div className="space-y-4">
      <div>
        <h4 className="text-lg font-semibold text-white mb-2">Map Your Columns</h4>
        <p className="text-gray-400 text-sm mb-4">Match your CSV columns to our standard format.</p>
      </div>
      <div className="space-y-3">
        {Object.entries(COLUMNS).map(([ourColumn, config]) => (
          <div key={ourColumn} className="bg-gray-900 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2">
                <span className="text-white font-medium">{ourColumn}</span>
                {config.required && (
                  <span className="text-xs bg-red-900 text-red-300 px-2 py-1 rounded">Required</span>
                )}
              </div>
            </div>
            <p className="text-gray-400 text-sm mb-3">{config.description}</p>
            <select
              value={columnMapping[ourColumn] || ''}
              onChange={(e) => onMappingChange({ ...columnMapping, [ourColumn]: e.target.value })}
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500"
            >
              <option value="">-- Select Column --</option>
              {csvColumns.map((col) => (
                <option key={col} value={col}>{col}</option>
              ))}
            </select>
          </div>
        ))}
      </div>
      {(!columnMapping['Date'] || !columnMapping['Daily_Return_Pct']) && (
        <div className="bg-red-900 bg-opacity-20 border border-red-700 rounded-lg p-4">
          <p className="text-red-300 text-sm">⚠️ You must map the required columns to proceed.</p>
        </div>
      )}
    </div>
  );
};

const Step3DeveloperInfo: React.FC<{
  developerInfo: { name: string; email: string; phone: string; countryCode: string; comment: string; };
  onInfoChange: (info: any) => void;
  strategyName: string;
  onStrategyNameChange: (name: string) => void;
}> = ({ developerInfo, onInfoChange, strategyName, onStrategyNameChange }) => {
  return (
    <div className="space-y-4">
      <div>
        <h4 className="text-lg font-semibold text-white mb-2">Strategy & Developer Information</h4>
        <p className="text-gray-400 text-sm mb-4">Provide strategy name and your contact details.</p>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">
          Strategy Name <span className="text-red-400">*</span>
        </label>
        <input
          type="text"
          value={strategyName}
          onChange={(e) => onStrategyNameChange(e.target.value)}
          className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500"
          placeholder="e.g., SPX_Mean_Reversion"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">
          Full Name <span className="text-red-400">*</span>
        </label>
        <input
          type="text"
          value={developerInfo.name}
          onChange={(e) => onInfoChange({ ...developerInfo, name: e.target.value })}
          className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500"
          placeholder="John Doe"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">
          Email <span className="text-red-400">*</span>
        </label>
        <input
          type="email"
          value={developerInfo.email}
          onChange={(e) => onInfoChange({ ...developerInfo, email: e.target.value })}
          className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500"
          placeholder="john@example.com"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">
          Phone <span className="text-red-400">*</span>
        </label>
        <div className="flex space-x-2">
          <select
            value={developerInfo.countryCode}
            onChange={(e) => onInfoChange({ ...developerInfo, countryCode: e.target.value })}
            className="w-32 px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500"
          >
            <option value="+1">+1 (US)</option>
            <option value="+44">+44 (UK)</option>
            <option value="+91">+91 (IN)</option>
          </select>
          <input
            type="tel"
            value={developerInfo.phone}
            onChange={(e) => onInfoChange({ ...developerInfo, phone: e.target.value })}
            className="flex-1 px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500"
            placeholder="555-123-4567"
          />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">Comments</label>
        <textarea
          value={developerInfo.comment}
          onChange={(e) => onInfoChange({ ...developerInfo, comment: e.target.value })}
          rows={4}
          className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500"
          placeholder="Describe your strategy..."
        />
      </div>
    </div>
  );
};

const DetailsModal: React.FC<{ submission: StrategySubmission; onClose: () => void; }> = ({ submission, onClose }) => {
  const formatNumber = (num: number, decimals: number = 2) => num.toFixed(decimals);
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex items-center justify-between pb-4 border-b border-gray-700 mb-6">
            <h3 className="text-2xl font-bold text-white">Strategy Details</h3>
            <button onClick={onClose} className="text-gray-400 hover:text-white">
              <XCircle className="h-6 w-6" />
            </button>
          </div>
          <div className="grid grid-cols-2 gap-6 mb-6">
            <div>
              <h4 className="text-sm font-medium text-gray-400 mb-2">Strategy Information</h4>
              <div className="bg-gray-900 rounded-lg p-4 space-y-2">
                <div><span className="text-gray-400 text-sm">Name:</span><p className="text-white font-medium">{submission.strategy_name}</p></div>
                <div><span className="text-gray-400 text-sm">ID:</span><p className="text-white font-mono text-sm">{submission.submission_id}</p></div>
              </div>
            </div>
            <div>
              <h4 className="text-sm font-medium text-gray-400 mb-2">Developer Information</h4>
              <div className="bg-gray-900 rounded-lg p-4 space-y-2">
                <div><span className="text-gray-400 text-sm">Name:</span><p className="text-white">{submission.developer_info.name}</p></div>
                <div><span className="text-gray-400 text-sm">Email:</span><p className="text-white">{submission.developer_info.email}</p></div>
              </div>
            </div>
          </div>
          <div className="mb-6">
            <h4 className="text-sm font-medium text-gray-400 mb-3">Performance Metrics</h4>
            <div className="grid grid-cols-3 gap-4">
              <MetricCard label="CAGR" value={`${formatNumber(submission.metrics.cagr, 2)}%`} />
              <MetricCard label="Sharpe" value={formatNumber(submission.metrics.sharpe_ratio, 2)} />
              <MetricCard label="Max DD" value={`${formatNumber(submission.metrics.max_drawdown, 2)}%`} />
            </div>
          </div>
          <div className="mb-6 border-t border-gray-700 pt-4">
            <button
              onClick={() => {
                const dataKey = `raw-data-${submission.submission_id}`;
                sessionStorage.setItem(dataKey, JSON.stringify(submission));
                window.open(`/raw-data/${submission.submission_id}`, '_blank');
              }}
              className="w-full flex items-center justify-center space-x-2 px-4 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
            >
              <FileText className="h-5 w-5" />
              <span className="font-medium">View Raw Backtest Data</span>
            </button>
            {submission.synthetic_data?.columns_generated?.length > 0 && (
              <p className="text-xs text-gray-400 mt-2 text-center">
                Includes {submission.synthetic_data.columns_generated.length} synthetic column(s)
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

const ApprovalModal: React.FC<{
  submission: StrategySubmission;
  onApprove: (data: ApproveSubmissionRequest) => void;
  onClose: () => void;
  isLoading: boolean;
}> = ({ submission, onApprove, onClose, isLoading }) => {
  // Fetch all accounts from database
  const { data: allAccounts } = useQuery({
    queryKey: ['accounts'],
    queryFn: async () => {
      const response = await apiClient.getAccounts();
      return response;
    },
  });

  const [formData, setFormData] = useState<ApproveSubmissionRequest>({
    strategy_id: '',
    asset_class: 'equities',
    instruments: [],
    accounts: [],
    status: 'TESTING',
    trading_mode: 'PAPER',
    include_in_optimization: true,
    notes: '',
  });
  const [instrumentInput, setInstrumentInput] = useState('');

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <form onSubmit={(e) => { e.preventDefault(); onApprove(formData); }} className="p-6 space-y-4">
          <div className="flex items-center justify-between pb-4 border-b border-gray-700">
            <h3 className="text-xl font-bold text-white">Approve Strategy</h3>
            <button type="button" onClick={onClose} className="text-gray-400 hover:text-white">
              <XCircle className="h-6 w-6" />
            </button>
          </div>

          {/* Strategy ID */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Strategy ID <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              required
              value={formData.strategy_id}
              onChange={(e) => setFormData({ ...formData, strategy_id: e.target.value })}
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500"
              placeholder="e.g., SPX_1-D_Opt"
            />
          </div>

          {/* Asset Class */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Asset Class <span className="text-red-400">*</span>
            </label>
            <select
              value={formData.asset_class}
              onChange={(e) => setFormData({ ...formData, asset_class: e.target.value })}
              required
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500"
            >
              <option value="equities">Equities</option>
              <option value="options">Options</option>
              <option value="futures">Futures</option>
              <option value="forex">Forex</option>
              <option value="crypto">Crypto</option>
              <option value="commodities">Commodities</option>
            </select>
          </div>

          {/* Instruments */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Instruments <span className="text-red-400">*</span>
            </label>
            <div className="flex space-x-2 mb-2">
              <input
                type="text"
                value={instrumentInput}
                onChange={(e) => setInstrumentInput(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    if (instrumentInput.trim()) {
                      setFormData({ ...formData, instruments: [...formData.instruments, instrumentInput.trim()] });
                      setInstrumentInput('');
                    }
                  }
                }}
                placeholder="e.g., SPX, ES, SPY"
                className="flex-1 px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500"
              />
              <button
                type="button"
                onClick={() => {
                  if (instrumentInput.trim()) {
                    setFormData({ ...formData, instruments: [...formData.instruments, instrumentInput.trim()] });
                    setInstrumentInput('');
                  }
                }}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
              >
                Add
              </button>
            </div>
            {formData.instruments.length === 0 && (
              <p className="text-xs text-red-400 mb-2">⚠️ At least one instrument is required</p>
            )}
            <div className="flex flex-wrap gap-2">
              {formData.instruments.map((inst) => (
                <div key={inst} className="bg-gray-700 px-3 py-1 rounded-lg flex items-center space-x-2">
                  <span className="text-white text-sm">{inst}</span>
                  <button
                    type="button"
                    onClick={() => setFormData({ ...formData, instruments: formData.instruments.filter(i => i !== inst) })}
                    className="text-red-400 hover:text-red-300"
                  >
                    <XCircle className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Accounts (Multi-select) */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Accounts <span className="text-gray-500 text-xs">(Select one or more)</span>
            </label>
            <div className="border border-gray-600 rounded-lg p-3 max-h-48 overflow-y-auto bg-gray-900">
              {allAccounts && allAccounts.length > 0 ? (
                allAccounts.map((account: any) => (
                  <label
                    key={account.account_id}
                    className="flex items-center gap-2 py-2 px-2 hover:bg-gray-700 rounded cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={formData.accounts?.includes(account.account_id) || false}
                      onChange={(e) => {
                        const accounts = formData.accounts || [];
                        if (e.target.checked) {
                          setFormData({ ...formData, accounts: [...accounts, account.account_id] });
                        } else {
                          setFormData({
                            ...formData,
                            accounts: accounts.filter((id) => id !== account.account_id),
                          });
                        }
                      }}
                      className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-300">
                      {account.account_id}
                      <span className="text-xs text-gray-500 ml-2">({account.broker})</span>
                    </span>
                  </label>
                ))
              ) : (
                <p className="text-sm text-gray-500">No accounts available</p>
              )}
            </div>
            {formData.accounts && formData.accounts.length > 0 && (
              <p className="text-xs text-gray-400 mt-2">
                Selected: {formData.accounts.join(', ')}
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Status */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Status</label>
              <select
                value={formData.status}
                onChange={(e) => setFormData({ ...formData, status: e.target.value as 'ACTIVE' | 'TESTING' })}
                className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500"
              >
                <option value="TESTING">TESTING</option>
                <option value="ACTIVE">ACTIVE</option>
              </select>
            </div>

            {/* Trading Mode */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Trading Mode</label>
              <select
                value={formData.trading_mode}
                onChange={(e) => setFormData({ ...formData, trading_mode: e.target.value as 'PAPER' | 'LIVE' })}
                className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500"
              >
                <option value="PAPER">PAPER</option>
                <option value="LIVE">LIVE</option>
              </select>
            </div>
          </div>

          {/* Include in Optimization */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="include_in_optimization"
              checked={formData.include_in_optimization}
              onChange={(e) => setFormData({ ...formData, include_in_optimization: e.target.checked })}
              className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
            />
            <label htmlFor="include_in_optimization" className="text-sm text-gray-300">
              Include in portfolio optimization
            </label>
          </div>

          {/* Notes */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Notes</label>
            <textarea
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500"
              rows={3}
              placeholder="Additional notes about this strategy..."
            />
          </div>

          <div className="flex justify-end space-x-3 pt-4 border-t border-gray-700">
            <button type="button" onClick={onClose} disabled={isLoading} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors disabled:opacity-50">
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading || !formData.strategy_id || formData.instruments.length === 0}
              className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? 'Approving...' : 'Approve Strategy'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

const RejectionModal: React.FC<{
  submission: StrategySubmission;
  onReject: (reason: string) => void;
  onClose: () => void;
  isLoading: boolean;
}> = ({ submission, onReject, onClose, isLoading }) => {
  const [reason, setReason] = useState('');
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full">
        <form onSubmit={(e) => { e.preventDefault(); onReject(reason); }} className="p-6 space-y-6">
          <div className="flex items-center justify-between pb-4 border-b border-gray-700">
            <h3 className="text-xl font-bold text-white">Reject Strategy</h3>
            <button type="button" onClick={onClose} className="text-gray-400 hover:text-white">
              <XCircle className="h-6 w-6" />
            </button>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Reason <span className="text-red-400">*</span></label>
            <textarea
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={4}
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div className="flex justify-end space-x-3 pt-4 border-t border-gray-700">
            <button type="button" onClick={onClose} className="px-4 py-2 bg-gray-700 text-white rounded-lg">Cancel</button>
            <button type="submit" disabled={isLoading || !reason.trim()} className="px-4 py-2 bg-red-600 text-white rounded-lg">
              {isLoading ? 'Rejecting...' : 'Reject'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

const MetricCard: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="bg-gray-750 p-4 rounded-lg">
    <p className="text-gray-400 text-sm mb-1">{label}</p>
    <p className="text-white text-lg font-semibold">{value}</p>
  </div>
);
