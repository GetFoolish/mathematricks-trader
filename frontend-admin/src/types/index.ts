// Account & Portfolio Types
export interface AccountState {
  account: string;
  equity: number;
  cash_balance: number;
  margin_used: number;
  margin_available: number;
  unrealized_pnl: number;
  realized_pnl: number;
  open_positions: Position[];
  open_orders: Order[];
  timestamp?: string;
}

export interface Position {
  instrument: string;
  quantity: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  strategy_id?: string;
}

export interface Order {
  order_id: string;
  instrument: string;
  direction: 'LONG' | 'SHORT';
  quantity: number;
  price: number;
  status: string;
  timestamp: string;
}

// Portfolio Allocation Types
export interface PortfolioAllocation {
  allocation_id: string;
  timestamp: string;
  status: 'ACTIVE' | 'PENDING_APPROVAL' | 'ARCHIVED';
  allocations: Record<string, number>; // strategy_id -> allocation_pct
  expected_metrics: PortfolioMetrics;
  optimization_run_id?: string;
  approved_by?: string;
  approved_at?: string;
  archived_at?: string;
  notes?: string;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface PortfolioMetrics {
  expected_daily_return?: number;
  expected_daily_volatility?: number;
  expected_sharpe_daily?: number;
  expected_sharpe_annual?: number;
  total_allocation_pct: number;
  leverage_ratio: number;
  custom?: boolean;
}

export interface OptimizationRun {
  run_id: string;
  timestamp: string;
  strategies_used: string[];
  correlation_matrix: number[][];
  covariance_matrix: number[][];
  constraints: {
    max_leverage: number;
    max_single_strategy: number;
    risk_free_rate: number;
  };
  optimization_result: {
    success: boolean;
    message: string;
    converged: boolean;
    iterations?: number;
  };
  recommended_allocations: Record<string, number>;
  portfolio_metrics: PortfolioMetrics;
  execution_time_ms: number;
  created_at: string;
}

// Strategy Types
export interface Strategy {
  strategy_id: string;
  name: string;
  asset_class: string;
  instruments: string[];
  status: 'ACTIVE' | 'INACTIVE' | 'TESTING' | StrategyStatus;  // Support both old and new formats
  trading_mode?: 'LIVE' | 'PAPER';
  account?: string; // Legacy field
  accounts?: {
    mock?: string[];
    paper?: string[];
    live?: string[];
  }; // Mode-aware accounts (v5)
  include_in_optimization?: boolean;
  risk_limits?: {
    max_position_size?: number;
    max_daily_loss?: number;
  };
  developer_contact?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
  backtest_data?: BacktestData;
}

// New format for strategy.status field with defaults
export interface StrategyStatus {
  active: boolean;
  mode?: 'mock_mock' | 'mock_live' | 'paper_live' | 'live_live';
  account_type?: 'mock' | 'paper' | 'live';
  data_source?: 'mock' | 'live';
}

export interface BacktestData {
  strategy_id: string;
  daily_returns: number[];
  mean_return_daily: number;
  volatility_daily: number;
  sharpe_ratio?: number;
  max_drawdown?: number;
  margin_per_unit?: number;
  backtest_period?: string;
  synced_at?: string;
  created_at: string;
}

// Signal & Trading Types
export interface Signal {
  signal_id: string;
  strategy_id: string;
  timestamp: string;
  instrument: string;
  direction: 'LONG' | 'SHORT';
  action: 'ENTRY' | 'EXIT';
  order_type: string;
  price: number;
  quantity?: number;
  stop_loss?: number;
  take_profit?: number;
  expiry?: string;
  status: string;
  metadata?: Record<string, any>;
}

export interface TradingOrder {
  order_id: string;
  signal_id: string;
  strategy_id: string;
  account: string;
  timestamp: string;
  instrument: string;
  direction: 'LONG' | 'SHORT';
  action: 'ENTRY' | 'EXIT';
  order_type: string;
  price: number;
  quantity: number;
  stop_loss?: number;
  take_profit?: number;
  expiry?: string;
  status: string;
  cerebro_decision?: CerebroDecision;
  created_at: string;
}

export interface CerebroDecision {
  signal_id: string;
  decision: 'APPROVED' | 'REJECTED';
  timestamp: string;
  reason: string;
  original_quantity: number;
  final_quantity: number;
  risk_assessment: {
    margin_required: number;
    allocated_capital: number;
    margin_utilization_before_pct: number;
    margin_utilization_after_pct: number;
  };
  created_at: string;
}

// API Response Types
export interface ApiResponse<T> {
  status: string;
  data?: T;
  message?: string;
  error?: string;
}

// Fund Architecture Types (v5)
export interface Fund {
  fund_id: string;
  name: string;
  description?: string;
  total_equity: number;
  currency: string;
  accounts: string[];
  status: 'ACTIVE' | 'PAUSED' | 'CLOSED';
  created_at: string;
  updated_at: string;
}

export interface AssetClasses {
  equity: string[];  // ['all'] or specific symbols
  futures: string[];
  options: string[];
  crypto: string[];
  forex: string[];
  commodities: string[];
}

export interface TradingAccount {
  account_id: string;
  broker: 'IBKR' | 'Binance' | 'Alpaca' | 'Mock';
  fund_id: string;
  asset_classes: AssetClasses;
  equity: number;
  cash_balance: number;
  margin_used: number;
  margin_available: number;
  available_margin: number;
  unrealized_pnl: number;
  open_positions: Position[];
  status: 'ACTIVE' | 'INACTIVE';
  authentication_details?: Record<string, any>;
  last_updated?: string;
  created_at?: string;
}

export interface CreateFundRequest {
  name: string;
  description?: string;
  currency: string;
  accounts?: string[];
}

export interface UpdateFundRequest {
  name?: string;
  description?: string;
  accounts?: string[];
  status?: 'ACTIVE' | 'PAUSED' | 'CLOSED';
}

export interface CreateAccountRequest {
  account_id: string;
  broker: string;
  fund_id: string;
  asset_classes: AssetClasses;
  authentication_details?: Record<string, any>;
}

export interface UpdateAccountRequest {
  fund_id?: string;
  asset_classes?: AssetClasses;
  authentication_details?: Record<string, any>;
  status?: 'ACTIVE' | 'INACTIVE';
}

export interface StrategyAccountMapping {
  strategy_id: string;
  accounts: string[];
  asset_class: string;
}

// Auth Types
export interface User {
  username: string;
  role: 'ADMIN' | 'CLIENT' | 'SIGNAL_SENDER';
  email?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  token: string;
  user: User;
}

// Dashboard Types (v5)
export interface Dashboard {
  dashboard_id: string;
  name: string;
  description?: string;
  created_by: string;
  fund_id: string | null;
  is_locked: boolean;
  widgets: DashboardWidget[];
  grid_config: GridConfig;
  created_at: string;
  updated_at: string;
}

export interface DashboardWidget {
  widget_id: string;
  widget_type: WidgetType;
  position: WidgetPosition;
  config: WidgetConfig;
}

export interface WidgetPosition {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface GridConfig {
  cols: number;
  row_height: number;
}

export type WidgetType = 'FundBalances' | 'AccountStatement' | 'SystemHealth';

export interface WidgetConfig {
  account_filter?: string;
  fund_filter?: string;
  date_range_days?: number;
  group_by?: 'date' | 'account';
}

export interface WidgetData<T = any> {
  data: T;
  computed_at: string;
  age_seconds: number;
  is_stale: boolean;
}

// Fund Balances Widget Data
export interface FundBalancesData {
  total_equity: number;
  funds: FundBalance[];
}

export interface FundBalance {
  fund_id: string;
  fund_name: string;
  total_balance: number;
  accounts: AccountBalance[];
}

export interface AccountBalance {
  account_id: string;
  broker: string;
  equity: number;
  cash: number;
  margin_used: number;
  unrealized_pnl: number;
}

// Account Statement Widget Data
export interface AccountStatementData {
  transactions: Transaction[];
  summary: TransactionSummary;
}

export interface Transaction {
  date: string;
  timestamp: string;
  account_id: string;
  fund_id?: string;
  strategy_id?: string;
  type: 'TRADE' | 'DEPOSIT' | 'WITHDRAWAL' | 'FEE' | 'OPENING_BALANCE';
  description: string;
  signal_id?: string;
  symbol?: string;
  debit: number;
  credit: number;
  balance: number;
  realized_pnl: number;
  commission?: number;
}

export interface TransactionSummary {
  total_debits: number;
  total_credits: number;
  net_pnl: number;
  transaction_count: number;
  date_range_days: number;
  start_date: string;
  end_date: string;
}

// Dashboard API Request Types
export interface CreateDashboardRequest {
  name: string;
  description?: string;
  created_by: string;
  fund_id?: string | null;
  widgets?: DashboardWidget[];
  grid_config?: GridConfig;
}

export interface UpdateDashboardRequest {
  name?: string;
  description?: string;
  is_locked?: boolean;
  widgets?: DashboardWidget[];
  grid_config?: GridConfig;
}

// Strategy Submission Types
export interface StrategySubmission {
  submission_id: string;
  status: 'PENDING_APPROVAL' | 'APPROVED' | 'REJECTED';
  strategy_name: string;
  developer_info: {
    name: string;
    email: string;
    note: string;
  };
  raw_data_backtest_full: BacktestDataPoint[];
  metrics: StrategyMetrics;
  synthetic_data: {
    columns_generated: string[];
    starting_capital: number;
  };
  approved_strategy_id?: string;
  rejection_reason?: string;
  reviewed_at?: string;
  submitted_at: string;
  created_at: string;
  updated_at: string;
  tearsheet_generated?: boolean;
  tearsheet_path?: string;
  tearsheet_error?: string;
}

export interface BacktestDataPoint {
  date: string;
  return: number;
  pnl: number;
  margin_used: number;
  notional_value: number;
  account_equity: number;
}

export interface StrategyMetrics {
  cagr: number;
  sharpe_ratio: number;
  calmar_ratio: number;
  max_drawdown: number;
  total_return: number;
  volatility_annual: number;
  sortino_ratio: number;
  win_rate: number;
  profit_factor: number;
  num_days: number;
  start_date: string;
  end_date: string;
  num_trades: number;
}

export interface ApproveSubmissionRequest {
  strategy_id: string;
  asset_class: string;
  instruments: string[];
  accounts?: string[];
  status?: 'ACTIVE' | 'INACTIVE' | 'TESTING';
  trading_mode?: 'PAPER' | 'LIVE';
  include_in_optimization?: boolean;
  developer_contact?: string;
  notes?: string;
  risk_limits?: {
    max_position_size?: number;
    max_daily_loss?: number;
  };
}

export interface RejectSubmissionRequest {
  rejection_reason: string;
}

// System Health Types
export interface SystemHealthData {
  overall_status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  services: ServiceHealth[];
  metrics?: {
    active_strategies?: number;
    active_accounts?: number;
    pending_orders?: number;
    signals_today?: number;
  };
}

export interface ServiceHealth {
  name: string;
  status: 'healthy' | 'degraded' | 'unhealthy';
  message?: string;
  uptime?: number;
  response_time?: number;
}

