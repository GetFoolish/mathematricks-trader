import axios from 'axios';
import type { AxiosInstance } from 'axios';
import type {
  AccountState,
  PortfolioAllocation,
  OptimizationRun,
  Strategy,
  BacktestData,
  LoginRequest,
  LoginResponse,
  Fund,
  TradingAccount,
  CreateFundRequest,
  UpdateFundRequest,
  CreateAccountRequest,
  UpdateAccountRequest,
  StrategyAccountMapping,
  Dashboard,
  CreateDashboardRequest,
  UpdateDashboardRequest,
  WidgetData,
  WidgetType,
  WidgetConfig,
  StrategySubmission,
  ApproveSubmissionRequest,
  RejectSubmissionRequest,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8002';
const CEREBRO_BASE_URL = import.meta.env.VITE_CEREBRO_BASE_URL || 'http://localhost:8001';
const PORTFOLIO_BUILDER_BASE_URL = import.meta.env.VITE_PORTFOLIO_BUILDER_BASE_URL || 'http://localhost:8003';
const FRONTEND_API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class ApiClient {
  private client: AxiosInstance;
  private cerebroClient: AxiosInstance;
  private portfolioBuilderClient: AxiosInstance;
  private frontendApiClient: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.cerebroClient = axios.create({
      baseURL: CEREBRO_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.portfolioBuilderClient = axios.create({
      baseURL: PORTFOLIO_BUILDER_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.frontendApiClient = axios.create({
      baseURL: FRONTEND_API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add request interceptor to include JWT token
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem('auth_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    this.cerebroClient.interceptors.request.use((config) => {
      const token = localStorage.getItem('auth_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    this.portfolioBuilderClient.interceptors.request.use((config) => {
      const token = localStorage.getItem('auth_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });
  }

  // ============================================================================
  // Account APIs
  // ============================================================================

  async getAccountState(accountName: string): Promise<AccountState> {
    const response = await this.client.get(`/api/v1/account/${accountName}/state`);
    return response.data.state;
  }

  async getAccountMargin(accountName: string) {
    const response = await this.client.get(`/api/v1/account/${accountName}/margin`);
    return response.data;
  }

  async syncAccount(accountName: string) {
    const response = await this.client.post(`/api/v1/account/${accountName}/sync`);
    return response.data;
  }

  // ============================================================================
  // Strategy Management APIs (PortfolioBuilder Service)
  // ============================================================================

  async getAllStrategies(): Promise<Strategy[]> {
    const response = await this.portfolioBuilderClient.get('/api/v1/strategies');
    return response.data.strategies;
  }

  async getStrategy(strategyId: string): Promise<Strategy> {
    const response = await this.portfolioBuilderClient.get(`/api/v1/strategies/${strategyId}`);
    return response.data.strategy;
  }

  async createStrategy(strategyData: Partial<Strategy>): Promise<{status: string; strategy_id: string}> {
    const response = await this.portfolioBuilderClient.post('/api/v1/strategies', strategyData);
    return response.data;
  }

  async updateStrategy(strategyId: string, updates: Partial<Strategy>) {
    const response = await this.portfolioBuilderClient.put(`/api/v1/strategies/${strategyId}`, updates);
    return response.data;
  }

  async deleteStrategy(strategyId: string) {
    const response = await this.portfolioBuilderClient.delete(`/api/v1/strategies/${strategyId}`);
    return response.data;
  }

  async syncStrategyBacktest(strategyId: string, backtestData: Partial<BacktestData>) {
    const response = await this.portfolioBuilderClient.post(`/api/v1/strategies/${strategyId}/sync-backtest`, backtestData);
    return response.data;
  }

  // ============================================================================
  // Portfolio Research & Testing APIs (PortfolioBuilder Service)
  // ============================================================================

  // Part 1: Current Allocation
  async getCurrentAllocation() {
    const response = await this.portfolioBuilderClient.get('/api/v1/allocations/current');
    return response.data;
  }

  // Part 2: Approve Allocation (makes it current)
  async approveAllocation(portfolio_test_id: string, fund_id: string) {
    const response = await this.portfolioBuilderClient.post('/api/v1/allocations/approve', {
      portfolio_test_id,
      fund_id
    });
    return response.data;
  }

  // Part 3: Portfolio Tests
  async getPortfolioTests() {
    const response = await this.portfolioBuilderClient.get('/api/v1/portfolio-tests');
    return response.data;
  }

  async deletePortfolioTest(testId: string) {
    const response = await this.portfolioBuilderClient.delete(`/api/v1/portfolio-tests/${testId}`);
    return response.data;
  }

  // Part 4: Run Portfolio Test (Research Lab)
  async runPortfolioTest(strategies: string[], constructor: string) {
    const response = await this.portfolioBuilderClient.post('/api/v1/portfolio-tests/run', {
      strategies,
      constructor
    });
    return response.data;
  }

  // ============================================================================
  // Cerebro Service APIs
  // ============================================================================

  async getCerebroHealth() {
    const response = await this.cerebroClient.get('/health');
    return response.data;
  }

  async getCerebroAllocations() {
    const response = await this.cerebroClient.get('/api/v1/allocations');
    return response.data;
  }

  async reloadCerebroAllocations() {
    const response = await this.cerebroClient.post('/api/v1/reload-allocations');
    return response.data;
  }

  // ============================================================================
  // Activity Tab APIs (Frontend API Server)
  // ============================================================================

  async getRecentSignals(limit: number = 50, environment?: string) {
    const params: any = { limit };
    if (environment) params.environment = environment;
    const response = await this.frontendApiClient.get('/api/v1/activity/signals', { params });
    return response.data;
  }

  async getRecentOrders(limit: number = 50, environment?: string) {
    const params: any = { limit };
    if (environment) params.environment = environment;
    const response = await this.frontendApiClient.get('/api/v1/activity/orders', { params });
    return response.data;
  }

  async getPositions(limit: number = 50, environment?: string, status?: 'OPEN' | 'CLOSED') {
    const params: any = { limit };
    if (environment) params.environment = environment;
    if (status) params.status = status;
    const response = await this.frontendApiClient.get('/api/v1/activity/positions', { params });
    return response.data;
  }

  async getTradingSignals(limit: number = 50, environment?: string) {
    const params: any = { limit };
    if (environment) params.environment = environment;
    const response = await this.frontendApiClient.get('/api/v1/activity/trading-signals', { params });
    return response.data;
  }

  // ============================================================================
  // Fund Management APIs (v5)
  // ============================================================================

  async createFund(data: CreateFundRequest): Promise<Fund> {
    const response = await this.portfolioBuilderClient.post('/api/v1/funds', data);
    return response.data;
  }

  async getFunds(status?: string): Promise<Fund[]> {
    const params = status ? { status } : {};
    const response = await this.portfolioBuilderClient.get('/api/v1/funds', { params });
    return response.data.funds || response.data;
  }

  async getFund(fundId: string): Promise<Fund> {
    const response = await this.portfolioBuilderClient.get(`/api/v1/funds/${fundId}`);
    return response.data;
  }

  async updateFund(fundId: string, data: UpdateFundRequest): Promise<Fund> {
    const response = await this.portfolioBuilderClient.put(`/api/v1/funds/${fundId}`, data);
    return response.data;
  }

  async deleteFund(fundId: string): Promise<void> {
    await this.portfolioBuilderClient.delete(`/api/v1/funds/${fundId}`);
  }

  // ============================================================================
  // Account Management APIs (v5)
  // ============================================================================

  async createAccount(data: CreateAccountRequest): Promise<TradingAccount> {
    const response = await this.portfolioBuilderClient.post('/api/v1/accounts', data);
    return response.data;
  }

  async getAccounts(fundId?: string): Promise<TradingAccount[]> {
    const params = fundId ? { fund_id: fundId } : {};
    const response = await this.portfolioBuilderClient.get('/api/v1/accounts', { params });
    return response.data.accounts || response.data;
  }

  async updateAccount(accountId: string, data: UpdateAccountRequest): Promise<TradingAccount> {
    const response = await this.portfolioBuilderClient.put(`/api/v1/accounts/${accountId}`, data);
    return response.data;
  }

  async deleteAccount(accountId: string): Promise<void> {
    await this.portfolioBuilderClient.delete(`/api/v1/accounts/${accountId}`);
  }

  // ============================================================================
  // Strategy-Account Mapping APIs (v5)
  // ============================================================================

  async updateStrategyAccounts(strategyId: string, accounts: string[]): Promise<Strategy> {
    const response = await this.portfolioBuilderClient.put(`/api/v1/strategies/${strategyId}/accounts`, { accounts });
    return response.data;
  }

  async getStrategyAccounts(strategyId: string): Promise<StrategyAccountMapping> {
    const response = await this.portfolioBuilderClient.get(`/api/v1/strategies/${strategyId}/accounts`);
    return response.data;
  }

  // ============================================================================
  // Dashboard Management (v5)
  // ============================================================================

  async getDashboards(fundId?: string, createdBy?: string): Promise<Dashboard[]> {
    const params = new URLSearchParams();
    if (fundId) params.append('fund_id', fundId);
    if (createdBy) params.append('created_by', createdBy);

    const response = await this.frontendApiClient.get<{ status: string; dashboards: Dashboard[] }>(
      `/api/v1/dashboards?${params.toString()}`
    );
    return response.data.dashboards;
  }

  async getDashboard(dashboardId: string): Promise<Dashboard> {
    const response = await this.frontendApiClient.get<Dashboard>(
      `/api/v1/dashboards/${dashboardId}`
    );
    return response.data;
  }

  async createDashboard(data: CreateDashboardRequest): Promise<{ dashboard_id: string }> {
    const response = await this.frontendApiClient.post<{ status: string; dashboard_id: string }>(
      '/api/v1/dashboards',
      data
    );
    return { dashboard_id: response.data.dashboard_id };
  }

  async updateDashboard(dashboardId: string, updates: UpdateDashboardRequest): Promise<void> {
    await this.frontendApiClient.put(`/api/v1/dashboards/${dashboardId}`, updates);
  }

  async deleteDashboard(dashboardId: string): Promise<void> {
    await this.frontendApiClient.delete(`/api/v1/dashboards/${dashboardId}`);
  }

  // ============================================================================
  // Widget Data (v5)
  // ============================================================================

  async getWidgetData<T = any>(
    widgetType: WidgetType,
    fundId?: string,
    config?: WidgetConfig
  ): Promise<WidgetData<T>> {
    const params = new URLSearchParams();
    if (fundId) params.append('fund_id', fundId);
    if (config?.account_filter) params.append('account_filter', config.account_filter);
    if (config?.date_range_days) params.append('date_range_days', config.date_range_days.toString());
    if (config?.group_by) params.append('group_by', config.group_by);

    const response = await this.frontendApiClient.get<WidgetData<T>>(
      `/api/v1/widgets/${widgetType}/data?${params.toString()}`
    );
    return response.data;
  }

  async reloadWidget(widgetType: WidgetType, fundId?: string, config?: WidgetConfig): Promise<void> {
    await this.frontendApiClient.post(`/api/v1/widgets/${widgetType}/reload`, {
      fund_id: fundId,
      ...config,
    });
  }

  async reloadAllWidgets(dashboardId: string): Promise<void> {
    await this.frontendApiClient.post(`/api/v1/dashboards/${dashboardId}/reload-all`);
  }

  // ============================================================================
  // Strategy Submission APIs
  // ============================================================================

  async getStrategySubmissions(status?: string): Promise<StrategySubmission[]> {
    const params = status ? `?status=${status}` : '';
    const response = await this.portfolioBuilderClient.get(`/api/v1/admin/submissions${params}`);
    return response.data.submissions;
  }

  async getSubmission(submissionId: string): Promise<StrategySubmission> {
    const response = await this.portfolioBuilderClient.get(`/api/v1/public/submission/${submissionId}`);
    return response.data.submission;
  }

  async approveSubmission(
    submissionId: string,
    approvalData: ApproveSubmissionRequest
  ): Promise<{ strategy_id: string; submission_id: string }> {
    const response = await this.portfolioBuilderClient.post(
      `/api/v1/admin/submissions/${submissionId}/approve`,
      approvalData
    );
    return response.data;
  }

  async rejectSubmission(
    submissionId: string,
    rejectionData: RejectSubmissionRequest
  ): Promise<void> {
    await this.portfolioBuilderClient.post(
      `/api/v1/admin/submissions/${submissionId}/reject`,
      rejectionData
    );
  }

  async deleteSubmission(submissionId: string): Promise<void> {
    await this.portfolioBuilderClient.delete(`/api/v1/admin/submissions/${submissionId}`);
  }

  // ============================================================================
  // Authentication APIs (Mock for MVP - replace with real impl)
  // ============================================================================

  async login(credentials: LoginRequest): Promise<LoginResponse> {
    // For MVP, mock authentication
    // In production, this would call a real auth endpoint
    if (credentials.username === 'admin' && credentials.password === 'admin') {
      const mockResponse: LoginResponse = {
        token: 'mock-jwt-token-' + Date.now(),
        user: {
          username: credentials.username,
          role: 'ADMIN',
          email: 'admin@mathematricks.com',
        },
      };
      return mockResponse;
    }
    throw new Error('Invalid credentials');
  }

  logout() {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user');
  }
}

export const apiClient = new ApiClient();
export default apiClient;
