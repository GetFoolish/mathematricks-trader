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
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8002';
const CEREBRO_BASE_URL = import.meta.env.VITE_CEREBRO_BASE_URL || 'http://localhost:8001';

class ApiClient {
  private client: AxiosInstance;
  private cerebroClient: AxiosInstance;

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
  // Portfolio Allocation APIs
  // ============================================================================

  async getCurrentAllocation(): Promise<PortfolioAllocation | null> {
    const response = await this.client.get('/api/v1/portfolio/allocations/current');
    return response.data.allocation;
  }

  async getLatestRecommendation(): Promise<PortfolioAllocation | null> {
    const response = await this.client.get('/api/v1/portfolio/allocations/latest-recommendation');
    return response.data.allocation;
  }

  async approveAllocation(allocationId: string, approvedBy: string) {
    const response = await this.client.post('/api/v1/portfolio/allocations/approve', null, {
      params: { allocation_id: allocationId, approved_by: approvedBy },
    });
    return response.data;
  }

  async createCustomAllocation(allocations: Record<string, number>, createdBy: string, notes?: string) {
    const response = await this.client.put('/api/v1/portfolio/allocations/custom', {
      allocations,
      created_by: createdBy,
      notes,
    });
    return response.data;
  }

  async createAndApproveCustomAllocation(allocations: Record<string, number>, approvedBy: string, notes?: string) {
    // Step 1: Create custom allocation
    const createResponse = await this.client.put('/api/v1/portfolio/allocations/custom', {
      allocations,
      created_by: approvedBy,
      notes,
    });

    const allocationId = createResponse.data.allocation_id;

    // Step 2: Approve it immediately
    const approveResponse = await this.approveAllocation(allocationId, approvedBy);

    return { ...createResponse.data, ...approveResponse };
  }

  async getAllocationHistory(limit = 10): Promise<PortfolioAllocation[]> {
    const response = await this.client.get('/api/v1/portfolio/allocations/history', {
      params: { limit },
    });
    return response.data.allocations;
  }

  async getLatestOptimizationRun(): Promise<OptimizationRun | null> {
    const response = await this.client.get('/api/v1/portfolio/optimization/latest');
    return response.data.run;
  }

  async simulateAllocation(allocationId: string) {
    const response = await this.client.get(`/api/v1/portfolio/allocations/${allocationId}/simulate`);
    return response.data.simulation;
  }

  async generateTearsheet(allocationId: string, startingCapital = 1000000) {
    const response = await this.client.get(`/api/v1/portfolio/allocations/${allocationId}/tearsheet`, {
      params: { starting_capital: startingCapital },
    });
    return response.data;
  }

  // ============================================================================
  // Strategy Management APIs
  // ============================================================================

  async getAllStrategies(): Promise<Strategy[]> {
    const response = await this.cerebroClient.get('/api/v1/strategies');
    return response.data.strategies;
  }

  async getStrategy(strategyId: string): Promise<Strategy> {
    const response = await this.cerebroClient.get(`/api/v1/strategies/${strategyId}`);
    return response.data.strategy;
  }

  async createStrategy(strategyData: Partial<Strategy>): Promise<{status: string; strategy_id: string}> {
    const response = await this.cerebroClient.post('/api/v1/strategies', strategyData);
    return response.data;
  }

  async updateStrategy(strategyId: string, updates: Partial<Strategy>) {
    const response = await this.cerebroClient.put(`/api/v1/strategies/${strategyId}`, updates);
    return response.data;
  }

  async deleteStrategy(strategyId: string) {
    const response = await this.cerebroClient.delete(`/api/v1/strategies/${strategyId}`);
    return response.data;
  }

  async syncStrategyBacktest(strategyId: string, backtestData: Partial<BacktestData>) {
    const response = await this.cerebroClient.post(`/api/v1/strategies/${strategyId}/sync-backtest`, backtestData);
    return response.data;
  }

  // ============================================================================
  // NEW: Portfolio Research & Testing APIs (Cerebro)
  // ============================================================================

  // Part 1: Current Allocation
  async getCurrentAllocation() {
    const response = await this.cerebroClient.get('/api/v1/allocations/current');
    return response.data;
  }

  // Part 2: Approve Allocation (makes it current)
  async approveAllocation(allocations: Record<string, number>) {
    const response = await this.cerebroClient.post('/api/v1/allocations/approve', {
      allocations
    });
    return response.data;
  }

  // Part 3: Portfolio Tests
  async getPortfolioTests() {
    const response = await this.cerebroClient.get('/api/v1/portfolio-tests');
    return response.data;
  }

  async deletePortfolioTest(testId: string) {
    const response = await this.cerebroClient.delete(`/api/v1/portfolio-tests/${testId}`);
    return response.data;
  }

  // Part 4: Run Portfolio Test (Research Lab)
  async runPortfolioTest(strategies: string[], constructor: string) {
    const response = await this.cerebroClient.post('/api/v1/portfolio-tests/run', {
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
