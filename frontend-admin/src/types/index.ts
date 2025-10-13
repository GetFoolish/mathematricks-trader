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
  status: 'ACTIVE' | 'INACTIVE' | 'TESTING';
  trading_mode?: 'LIVE' | 'PAPER';
  account?: string;
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
