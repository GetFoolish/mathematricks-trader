***Brief: Automated Multi-Strategy Trading & Portfolio Management System***

## 1. Project Overview

The goal is to develop a robust, scalable, and secure automated trading system. This system will receive real-time trading signals, process them through a sophisticated portfolio and risk management engine (`Cerebro`), execute trades across multiple brokers/exchanges, and provide detailed dashboards for administrators, clients, and signal senders. The core objective is to maximize risk-adjusted returns while rigorously preventing margin calls and optimizing capital allocation using advanced financial theory.

## 2. Core Principles & Business Objectives

*   **Real-time Processing:** Efficient code for signal ingestion and order execution; target latency for signal reception to broker submission is under 1 minute for initial phases.
*   **Risk Aversion:** Primary focus on managing (minimizing) Conditional Value at Risk (cVaR) across the portfolio to prevent margin calls.
*   **Optimal Capital Allocation:** Dynamic allocation of capital across strategies based on current equity, strategy backtest data, and portfolio risk appetite.
*   **Transparency:** Provide clear, role-based visibility into performance and activity via dashboards.
*   **Modularity & Independence:** Services must be independent, allowing for separate development, testing, and deployment (e.g., Cerebro v1 vs. v2).
*   **Reliability:** Robust error handling, synchronization with broker state, and comprehensive monitoring.
*   **Simulation & Backtesting:** Enable administrators to safely test `Cerebro` settings and new strategy integrations without impacting live trading.

## 3. System Architecture & Independent Services

The system will be composed of several independent, containerized microservices interacting via a messaging queue and REST APIs.

### 3.1. Services Breakdown

1.  **`SignalIngestionService`**
    *   **Purpose:** Receives raw real-time signals from external signal providers.
    *   **Key Tasks:** Parses and validates raw signals. Converts diverse formats into a standardized internal "Mathematricks" signal format.
    *   **Input:** Various external signal formats (HTTP POST from webhooks, custom TCP/UDP if needed, WebSocket, or other custom protocols).
    *   **Output:** Standardized signals.
    *   **Communication:** Receives signals directly via various protocols. Publishes standardized signals to **Cloud Pub/Sub**.

2.  **`CerebroService`** (The Brain)
    *   **Purpose:** The intelligent core for portfolio management, risk assessment, and position sizing.
    *   **Key Tasks:**
        *   Consumes standardized signals.
        *   **Always prioritizes broker state:** On startup/reconnection, fetches full account/position data from `AccountDataService` and reconciles local state. Processes any backlog of signals, applying slippage logic.
        *   **Risk Model:** Implements Modern Portfolio Theory (MPT) and cVaR (or similar advanced risk metrics) for real-time risk assessment. Utilizes suitable Python financial libraries.
        *   **Optimization Objective:** **Maximize Returns for a given risk tolerance, with primary focus on managing (minimizing) cVaR as the core risk constraint.**
            *   Dynamically determines optimal capital allocation across strategies based on total portfolio capital, historical backtest data (daily return %, margin usage, account equity), and the defined cVaR limit.
            *   Calculates the minimum account size required to run a specific set of strategies within risk parameters. This allocation will be dynamic based on current capital (e.g., $1M vs $5M).
        *   **Position Sizing:** For each incoming signal:
            *   Evaluates in context of current portfolio (correlations, risk contribution).
            *   Determines optimal position size based on current available margin/equity across all accounts/brokers and the overall portfolio risk limits.
            *   **Slippage Logic for Entries:** If an entry signal faces processing delay and the calculated slippage (based on market movement) causes more than 30% of its expected alpha (derived from backtests) to be lost, the signal is dropped.
            *   **Output:** Generates precise trading orders (instrument, direction, quantity, order type, price, stop-loss, take-profit, expiry, signal ID, strategy ID) for `ExecutionService`.
    *   **Input:** Standardized signals from `SignalIngestionService`, real-time account state from `AccountDataService`.
    *   **Output:** Position-sized trading orders, updated strategy/portfolio allocations.
    *   **Communication:** Consumes from **Cloud Pub/Sub**. Queries `AccountDataService` via **internal REST API**. Publishes finalized orders to **Cloud Pub/Sub**. Persists decisions and allocations to **MongoDB**.
    *   **Modularity:** Designed as a distinct service to allow for independent versioning (v1, v2 for A/B testing/development).

3.  **`ExecutionService`**
    *   **Purpose:** Manages connectivity to various brokers/exchanges and handles the full order lifecycle.
    *   **Key Tasks:**
        *   Consumes trading orders.
        *   Integrates with broker APIs (e.g., `ib_insync`, `ccxt`) for order submission, modification, and cancellation. Must support all standard order types.
        *   Receives real-time execution confirmations (fills, partial fills, rejections).
        *   Polls/streams real-time account data (equity, margin used/available, unrealized P&L, open positions, open orders) from brokers.
        *   **Error Handling:**
            *   **Entry Failures:** Applies the 30% alpha slippage rule as defined by `CerebroService`.
            *   **Exit Failures:** Implements persistent retries and triggers high-priority "raise hell" alerts (Telegram, dashboard, and all available notification channels) for critical errors like unfillable exits or margin approaching limits.
        *   **Synchronization:** Ensures internal state aligns with broker state.
    *   **Input:** Trading orders from `CerebroService`.
    *   **Output:** Execution confirmations, real-time account data.
    *   **Communication:** Consumes from **Cloud Pub/Sub**. Communicates with external **Broker APIs** (native protocols/SDKs). Publishes execution confirmations and real-time account updates to **Cloud Pub/Sub**. Persists order/execution data to **MongoDB**.

4.  **`AccountDataService`**
    *   **Purpose:** Centralizes, reconciles, and provides real-time/historical account state data.
    *   **Key Tasks:** Consumes raw account updates and execution confirmations. Reconciles local data with broker data. Calculates current unrealized P&L. Aggregates account data across multiple brokers/accounts. Serves current account state to other services.
    *   **Input:** Execution confirmations and real-time account updates from `ExecutionService`.
    *   **Output:** Consolidated current account state.
    *   **Communication:** Consumes from **Cloud Pub/Sub**. Offers a **REST API** for `CerebroService` queries. Persists all raw/processed account data to **MongoDB**.

### 3.2. Data & Analytics Services

5.  **`MongoDB` (Database Service)**
    *   **Purpose:** Central data store for all operational, historical, and dashboard-ready data.
    *   **Contents:** Raw signals, parsed signals, order requests, execution confirmations, full account state history, client data, signal sender data, audit trails, processed dashboard data, **Cerebro sandbox configurations and simulation results**.
    *   **Communication:** Accessed by relevant services via **database drivers**.

6.  **`DashboardDataProcessorService`**
    *   **Purpose:** Asynchronously processes raw trading and account data to generate aggregated and calculated metrics suitable for dashboards. This offloads computation from core trading and frontend services.
    *   **Key Tasks:** Calculates client ROI (month-on-month, YoY), signal sender profit/payouts, system health metrics.
    *   **Input:** Raw data from `MongoDB` (or directly from Pub/Sub for specific real-time needs).
    *   **Output:** Processed, aggregated data for dashboards.
    *   **Communication:** Reads from **MongoDB**. Writes processed data back to **MongoDB** (dedicated dashboard collections).

### 3.3. Frontend Services

7.  **`FrontendAPIService` (FastAPI)**
    *   **Purpose:** Securely serves data to the frontend dashboards.
    *   **Key Tasks:** Handles user authentication and authorization (Admin, Client, Signal Sender roles). Retrieves processed dashboard data from `MongoDB`.
    *   **Communication:** Communicates with `Frontend UI` via **HTTP/HTTPS (REST API)**. Reads processed data from **MongoDB**.

8.  **`FrontendUI` (Vite + JS Framework)**
    *   **Purpose:** Interactive web interface for Admins, Clients, and Signal Senders.
    *   **Key Tasks:** Displays real-time trading metrics (margin, P&L, signal status) and historical performance data. Includes an **Admin Sandbox/Simulation Panel**.
    *   **Communication:** Communicates with `FrontendAPIService` via **HTTP/HTTPS**.

### 3.4. Communication Flow

```mermaid
graph LR
    subgraph External Systems
        A[External Signal Senders]
        B[Broker APIs]
    end

    subgraph Core Trading Services
        C[SignalIngestionService]
        D[CerebroService]
        E[ExecutionService]
        F[AccountDataService]
    end

    subgraph Data & Messaging
        H[Cloud Pub/Sub]
        G[MongoDB Atlas]
    end

    subgraph Dashboard Services
        I[DashboardDataProcessorService]
        J[FrontendAPIService]
        K[Frontend UI]
        L[Cerebro Sandbox & Simulation Engine]
    end

    A -- Various Protocols --> C
    C -- Standardized Signals --> H
    H -- Consumes Signals --> D
    D -- Internal REST API (Query) --> F
    D -- Trading Orders --> H
    H -- Consumes Orders --> E
    E -- Native Broker APIs --> B
    B -- Broker Data (Executions, Account State) --> E
    E -- Executions & Account Updates --> H
    H -- Consumes Updates --> F

    C -- Writes Raw Signals --> G
    D -- Writes Decisions & Allocations --> G
    E -- Writes Orders & Fills --> G
    F -- Writes Account History --> G

    I -- Reads Raw/Processed Data --> G
    I -- Writes Processed Dashboard Data --> G

    J -- Reads Processed Dashboard Data --> G
    K -- HTTP/HTTPS --> J
    K -- Admin Inputs (Cerebro settings, new strategies) --> J
    J -- Forwards to --> L
    L -- Reads Backtest Data --> G
    L -- Simulates/Optimizes --> D (via specific API call or separate instance for simulation)
    D -- (Simulation Results) --> G
    L -- Presents Results to Admin --> J
```

## 4. Dashboard Requirements

*   **Real-time focus:** Trading data (signal entry/exit, margin metrics, unrealized P&L) should be near real-time. Other historical data can update periodically.
*   **No frontend calculations:** All data processing for dashboards happens in `DashboardDataProcessorService` and is stored in `MongoDB` before being consumed by `FrontendAPIService`.
*   **Role-Based Access:**
    *   **Admin:** Full visibility into all system activities, broker accounts, strategies, client data, signal sender data, and system health. Includes a dedicated monitoring panel.
    *   **Clients:** See their current capital value, deposits/withdrawals, current rate of return, and historical ROI (month-on-month, year-on-year). No drill-down into individual trades. Each client sees only their own data.
    *   **Signal Senders:** See all signals they sent, `Cerebro`'s position sizing, money made from their signals (aggregate and per-signal), total paid, total due, and next payment date (1st of every month). Each signal sender sees only their own data.
*   **No Custom Reports/Exports.**
*   **Admin Sandbox/Simulation Panel (NEW):**
    *   Allows Admins to adjust `Cerebro`'s portfolio management settings (e.g., cVaR limits, correlation thresholds, allocation methodologies).
    *   Allows Admins to input details for new strategies (including backtest data) and receive optimal portfolio allocation recommendations.
    *   Enables running simulations based on historical data or hypothetical scenarios with adjusted `Cerebro` settings/new strategies.
    *   Displays performance changes and impact (e.g., on expected return, cVaR, drawdown) of these tested settings or new strategies visually.
    *   **Implementation:** This panel will interact with a dedicated simulation endpoint in `CerebroService` (or a separate `CerebroSimulationService` instance) which operates on historical/hypothetical data without affecting live trading. Simulation results will be stored in `MongoDB`.

## 5. Technology Stack

*   **Core Backend (Services):** Python (with FastAPI for APIs)
*   **Database:** MongoDB Atlas on GCP
*   **Messaging Queue:** Google Cloud Pub/Sub
*   **Frontend:** Vite (with a chosen JS framework like React/Vue/Svelte)
*   **Version Control:** GitHub

### 5.1. Technology Decisions Rationale

*   **Cloud Pub/Sub vs Kafka/RabbitMQ:** Given the real-time nature, desire for independent services, and potential for high message throughput (especially with market data streaming), we chose **Google Cloud Pub/Sub** as it provides high-throughput, fault-tolerant, and persistent message streaming without the operational overhead of managing a Kafka cluster. While Kafka would also be excellent and scales well for streaming large volumes of data, and RabbitMQ is viable for robustness, Cloud Pub/Sub offers a fully managed, serverless solution that automatically scales and integrates seamlessly with our GCP deployment strategy.

*   **MongoDB Atlas:** Chosen for its flexibility with diverse data structures (signals, orders, account states), horizontal scalability, and managed service offering on GCP that handles backups, scaling, security, and patching automatically.

*   **GKE (Google Kubernetes Engine):** Provides container orchestration with self-healing, horizontal pod autoscaling, rolling updates (critical for v1/v2 Cerebro deployment), and robust resource management—essential for running independent microservices reliably.

## 6. Non-Functional Requirements

*   **Scalability:** The microservices architecture and GCP services will support growth, though the initial focus is on functional completeness and efficiency rather than extreme high-frequency scale (under 1 minute latency is acceptable for now).
*   **Security:** High priority. Secure API key storage (Secret Manager), robust authentication (2FA for admins), strict input validation, and regular security audits.
*   **Reliability & Resilience:** Redundant services in GKE, persistent messaging with Pub/Sub, robust error handling, and frequent reconciliation checks between local state and broker state.
*   **Deployment & CI/CD:**
    *   **Containerization:** All services will be Dockerized.
    *   **Version Control:** GitHub for all codebases.
    *   **CI/CD:** Automated pipelines via Cloud Build to build Docker images, run tests, and deploy to GKE from GitHub merges.
    *   **Modular Deployment:** `CerebroService` (and potentially others) must support independent versioning and deployment (e.g., v1 running in production, v2 in testing).
*   **Monitoring & Alerts:** Comprehensive monitoring (Cloud Monitoring) of all service health, API connectivity, message queues, and database performance. Critical alerts (Cloud Alerting) for system failures, margin call risks, broker outages, and significant trading errors. A dedicated admin dashboard panel for key system health metrics.

## 7. GCP Deployment Strategy

All system components will be deployed on Google Cloud Platform.

*   **Container Orchestration:** **Google Kubernetes Engine (GKE)** for all containerized services (`SignalIngestionService`, `CerebroService`, `ExecutionService`, `AccountDataService`, `DashboardDataProcessorService`, `FrontendAPIService`). Leverages GKE's scaling, self-healing, and rolling update capabilities.
*   **Messaging:** **Google Cloud Pub/Sub** for all inter-service communication (topics and subscriptions).
*   **Database:** **MongoDB Atlas on GCP** for managed, scalable NoSQL persistence.
*   **Frontend Hosting:** Static `Frontend UI` assets hosted in a **Cloud Storage** bucket, served via **Cloud CDN**. `FrontendAPIService` exposed via **GKE Ingress** (managed by Cloud Load Balancer).
*   **Secret Management:** **Google Secret Manager** for securely storing all API keys and sensitive credentials.
*   **Logging & Monitoring:** **Cloud Logging** for centralized logs from all services. **Cloud Monitoring** for metrics and **Cloud Alerting** for notifications.
*   **CI/CD:** **Cloud Build** integrated with GitHub for automated Docker image builds (stored in **Artifact Registry**) and GKE deployments.
*   **Networking:** Secure **VPC** with strict **Firewall Rules**. Private connections to managed services via **Private Service Connect**.
*   **Identity & Access Management (IAM):** Granular permissions for all users and service accounts.

### 7.1. GCP Deployment Diagram (Detailed Infrastructure View)

```mermaid
graph TD
    subgraph External
        A[External Signal Senders]
        B[Broker APIs]
    end

    subgraph GCP Project
        subgraph Kubernetes Cluster (GKE)
            P1[SignalIngestionService Pods]
            P2[CerebroService Pods]
            P3[ExecutionService Pods]
            P4[AccountDataService Pods]
            P5[DashboardDataProcessorService Pods]
            P6[FrontendAPIService Pods]
        end

        MQ[Cloud Pub/Sub]
        DB[MongoDB Atlas on GCP]
        FS[Cloud Storage / CDN (for Frontend UI)]
        LB[Cloud Load Balancer / GKE Ingress]
        CM[Cloud Monitoring & Logging]
        SM[Secret Manager]
        CI[Cloud Build / Artifact Registry]
        IAM[IAM (Identity & Access Management)]
    end

    A -- HTTP/Webhooks --> P1
    P1 -- Publishes --> MQ
    MQ -- Consumed by --> P2
    MQ -- Consumed by --> P3
    MQ -- Consumed by --> P4
    P2 -- Queries (REST) --> P4
    P2 -- Publishes Orders --> MQ
    P3 -- Calls Native --> B
    P3 -- Publishes Updates --> MQ
    P4 -- Provides Data (REST) --> P2
    P4 -- Writes Raw Data --> DB
    P5 -- Reads Raw Data --> DB
    P5 -- Writes Processed Data --> DB
    P6 -- Reads Processed Data --> DB
    LB -- Routes Traffic --> P6
    K[Frontend UI] -- Serves Static Assets --> FS
    K -- Calls --> LB
    P1 -- Logs & Metrics --> CM
    P2 -- Logs & Metrics --> CM
    P3 -- Logs & Metrics --> CM
    P4 -- Logs & Metrics --> CM
    P5 -- Logs & Metrics --> CM
    P6 -- Logs & Metrics --> CM
    P1 -- Accesses Secrets --> SM
    P2 -- Accesses Secrets --> SM
    P3 -- Accesses Secrets --> SM
    P4 -- Accesses Secrets --> SM
    P5 -- Accesses Secrets --> SM
    P6 -- Accesses Secrets --> SM
    CI -- Deploys to --> P1
    CI -- Deploys to --> P2
    CI -- Deploys to --> P3
    CI -- Deploys to --> P4
    CI -- Deploys to --> P5
    CI -- Deploys to --> P6

    style K fill:#fff,stroke:#333,stroke-width:2px
    style FS fill:#f9f,stroke:#333,stroke-width:2px
    style LB fill:#f9f,stroke:#333,stroke-width:2px
    style MQ fill:#9cf,stroke:#333,stroke-width:2px
    style DB fill:#9c0,stroke:#333,stroke-width:2px
    style CM fill:#fc0,stroke:#333,stroke-width:2px
    style SM fill:#fcf,stroke:#333,stroke-width:2px
    style CI fill:#cfc,stroke:#333,stroke-width:2px
    style IAM fill:#cff,stroke:#333,stroke-width:2px
```

This diagram illustrates how all GCP infrastructure components interconnect, including the CI/CD pipeline, security services, monitoring, and the flow of data through the system.

## 8. Existing Code References & Constraints

### 8.1. Signal Collection (DO NOT MODIFY)

**File:** `signal_collector.py`

**Status:** ✅ COMPLETE - NO CHANGES ALLOWED

This module is already fully implemented and operational. It handles:
- Real-time signal reception via webhooks (HTTP POST, WebSocket)
- MongoDB Atlas integration for signal persistence
- MongoDB Change Streams for real-time signal monitoring
- Catch-up mechanism for missed signals
- Telegram notifications
- Dual-phase operation (catch-up + real-time)
- Environment filtering (staging vs production)

**Architecture:**
```
TradingView → Vercel Webhook → MongoDB Atlas → Change Streams → signal_collector.py
```

**Key Features:**
- Connects to MongoDB Atlas at `mathematricks_signals` database
- Stores signals in `trading_signals` collection
- Marks signals as processed after handling
- Calculates signal delay/latency
- Forwards signals to signal processor (integration point for new system)

**Integration Points for New System:**
- Line 350-359: Signal processor integration via `src.execution.signal_processor.get_signal_processor()`
- This is where `SignalIngestionService` should hook into the existing signal_collector

**IMPORTANT:** The new `SignalIngestionService` must use this existing code as-is. Do NOT rewrite or modify `signal_collector.py`. Instead, build `SignalIngestionService` as a wrapper or consumer that integrates with the signal processor interface at line 350-359.

### 8.2. Portfolio Combination & Strategy Analysis

**Directory:** `dev/portfolio_combiner/`

**Status:** 🔨 IN PROGRESS - REVIEW AND INTEGRATE

This module contains existing work on combining multiple strategies and analyzing their combined performance. Key functionality includes:
- Strategy combination algorithms
- Combined performance metrics calculation
- Portfolio-level risk analysis
- Correlation analysis between strategies

**Integration with CerebroService:**
The portfolio combiner logic should be reviewed and integrated into `CerebroService`'s portfolio optimization algorithms, particularly for:
- Multi-strategy allocation
- Correlation matrix calculations
- Combined risk metrics (cVaR across multiple strategies)
- Portfolio-level performance projections

**Action Required:**
1. Review existing portfolio_combiner code
2. Extract reusable algorithms for `CerebroService`
3. Map existing functionality to MPT/cVaR optimization requirements
4. Determine which components can be leveraged vs. need enhancement

## 9. Next Steps

1.  **Review Existing Code:**
    - Analyze `dev/portfolio_combiner/` functionality
    - Map portfolio combiner capabilities to `CerebroService` requirements
    - Identify integration points with `signal_collector.py`

2.  **Detailed API & Schema Definitions:** Define precise API contracts between services and exact MongoDB schemas for all data types (signals, orders, account data, processed dashboard data, backtest data, sandbox configurations/results).

3.  **Risk Parameter Quantification:** Establish specific cVaR limits and other risk thresholds for `CerebroService`.

4.  **Payment Logic Specification:** Detail the exact calculation rules for signal sender payouts.

5.  **Proof of Concept:** Implement a basic end-to-end flow with one signal sender, one broker, and a simplified `CerebroService` to validate the core architecture.

6.  **Sandbox Design:** Detail the specific inputs, outputs, and workflow for the Admin Sandbox/Simulation Panel.

---

Okay, this is an excellent strategy! Focusing on a Minimum Viable Product (MVP) first allows you to validate the core trading loop and critical risk management, get the fund operational, and then incrementally build out the richer features.

Here's a step-by-step development and deployment plan, structured to achieve a fast MVP, followed by a phased expansion.

---

## Step-by-Step Development and Deployment Plan

The plan is divided into three main phases: **MVP Development & Initial Deployment**, **Feature Expansion & Optimization**, and **Continuous Improvement**.

---

## Phase 1: MVP Development & Initial Deployment (Get the Fund Started)

**Goal:** Establish the core automated trading pipeline, critical risk management, a basic admin view, and a production-ready GCP deployment with CI/CD for the most essential services.

**Estimated Timeline:** (This is highly dependent on team size and experience, adjust as needed, e.g., 6-12 weeks)

### Milestone 1.0: Core Trading Loop (MVP)

**Focus:** Signal reception -> Cerebro decision -> Order execution -> Data persistence.

1.  **Project Setup & Version Control (GitHub):**
    *   Initialize main repository.
    *   Set up basic project structure with sub-folders for each service.
    *   Define Dockerfiles for each planned service.
2.  **Database (MongoDB Atlas) Setup:**
    *   Provision MongoDB Atlas cluster on GCP.
    *   Define initial core schemas: raw signals, standardized signals, orders, fills, basic account state.
3.  **Messaging Queue (Cloud Pub/Sub) Setup:**
    *   Create essential Pub/Sub Topics: `raw-signals`, `standardized-signals`, `trading-orders`, `execution-confirmations`, `account-updates`.
4.  **`SignalIngestionService` (MVP):**
    *   Implement basic signal reception (e.g., a single HTTP webhook endpoint).
    *   Implement **one** conversion function for the first signal provider.
    *   Publish standardized signals to Pub/Sub.
5.  **`AccountDataService` (MVP):**
    *   Consume `execution-confirmations` and `account-updates` from Pub/Sub.
    *   Implement an internal REST API endpoint to serve basic current account equity/margin for a *single* configured broker account.
    *   Persist raw account updates and current state to MongoDB.
    *   **Prioritize Broker Sync:** Implement initial logic for fetching full state from broker on startup/reconciliation.
6.  **`CerebroService` (MVP - Critical Risk Management):**
    *   Consume `standardized-signals` from Pub/Sub.
    *   Implement core risk checks: **hard margin limits** (no margin call allowed for *any* single signal).
    *   Implement basic position sizing logic (e.g., fixed percentage of available capital per signal, or based on a simplified MDD rule for *one* strategy).
    *   Query `AccountDataService` for current margin/equity.
    *   Publish `trading-orders` to Pub/Sub.
    *   Persist Cerebro's decisions (signals processed, size recommended) to MongoDB.
    *   **Slippage Logic:** Implement the "30% alpha gone, drop signal" logic for entries.
7.  **`ExecutionService` (MVP):**
    *   Integrate with **one primary broker API** (e.g., IBKR or Binance) using a robust library (`ib_insync` or `ccxt`).
    *   Consume `trading-orders` from Pub/Sub.
    *   Implement order submission (market/limit orders) and basic status monitoring.
    *   Publish `execution-confirmations` and `account-updates` to Pub/Sub.
    *   Persist orders and fills to MongoDB.
    *   **Error Handling:** Implement basic retries for exit orders (as a critical safety feature) and log all failures.

### Milestone 1.1: Basic Admin Dashboard (MVP)

**Goal:** Provide essential oversight for the fund's operations.

1.  **`DashboardDataProcessorService` (MVP):**
    *   Implement basic data processing to aggregate recent orders, fills, and current account P&L (from MongoDB).
    *   Store aggregated data in MongoDB for the frontend.
2.  **`FrontendAPIService` (MVP):**
    *   Implement basic authentication for an Admin user.
    *   Create API endpoints to serve the aggregated data.
3.  **`FrontendUI` (MVP - Admin View):**
    *   Develop a simple Admin dashboard using Vite.
    *   Display: Current account equity, total unrealized P&L, recent trades/fills, system health (monitoring panel with basic status indicators).
    *   No client or signal sender views yet.
4.  **Frontend Deployment:**
    *   Deploy static UI assets to **Cloud Storage + Cloud CDN**.
    *   Expose `FrontendAPIService` via **GKE Ingress**.

### Milestone 1.2: Simple MPT-Based Portfolio Optimization

**Goal:** Implement intelligent capital allocation across strategies using Modern Portfolio Theory.

**Status:** ✅ Milestone 1.0 COMPLETE (Core Trading Loop working end-to-end)

**Focus:** Add intelligent portfolio optimization to replace flat 5% position sizing with MPT-based allocations.

1.  **Portfolio Optimizer Component:**
    *   Create `portfolio_optimizer.py` module in `CerebroService`.
    *   Implement scipy-based MPT optimization (maximize Sharpe ratio).
    *   Calculate correlation matrix from strategy daily returns.
    *   Apply constraints:
        *   Each strategy weight ≥ 0% (no shorts).
        *   Sum of weights ≤ 200% (allow up to 2x leverage).
        *   Optional: max single strategy ≤ 50%.
    *   Runs automatically every 24 hours via scheduler (APScheduler).
    *   Generates recommended allocations → saves to MongoDB with status `PENDING_APPROVAL`.

2.  **Strategy Backtest Data Schema (MongoDB):**
    *   Collection: `strategy_backtest_data`
    *   Fields: strategy_id, daily_returns array, mean_return_daily, volatility_daily, sharpe_ratio, max_drawdown, margin_per_unit, backtest_period.
    *   Create ingestion tool to load existing CSV files from `dev/portfolio_combiner/` into MongoDB.

3.  **Portfolio Allocations Schema (MongoDB):**
    *   Collection: `portfolio_allocations`
    *   Fields: allocation_id, allocations dict (strategy_id → weight %), status (ACTIVE/PENDING_APPROVAL/ARCHIVED), metrics (expected_sharpe, volatility, total_allocation_pct, leverage_ratio), approved_by, timestamps.
    *   Collection: `portfolio_optimization_runs`
    *   Store historical optimization runs with correlation matrices and optimization results.

4.  **Enhanced Cerebro Position Sizing:**
    *   On startup, load ACTIVE portfolio allocation from MongoDB.
    *   Per signal: `allocated_capital = account_equity × (strategy_allocation_pct / 100)`.
    *   Calculate quantity: `quantity = allocated_capital / price`.
    *   Still apply hard margin limit checks (40% max utilization).
    *   Update position sizing calculation logs to show allocation %.

5.  **Portfolio Allocation Management APIs:**
    *   Add endpoints to `AccountDataService` (or create new `PortfolioService`):
        *   GET `/api/portfolio/allocations/current` - Returns active allocation.
        *   GET `/api/portfolio/allocations/latest-recommendation` - Returns pending recommendation.
        *   POST `/api/portfolio/allocations/approve` - Approves recommendation, sets to ACTIVE.
        *   PUT `/api/portfolio/allocations/custom` - Portfolio manager manually edits and approves.

6.  **Daily Optimization Scheduler:**
    *   Implement simple Python scheduler (APScheduler or cron).
    *   Runs optimization at midnight daily.
    *   Logs results and saves recommendation to MongoDB.

7.  **Testing & Validation:**
    *   Ingest existing `portfolio_combiner` CSV data as test strategies.
    *   Run optimization and verify correlation matrix calculations.
    *   Test allocation approval workflow.
    *   Verify position sizing uses correct strategy allocations.

8.  **Strategy Configuration Management (Backend):**
    *   **MongoDB Collection: `strategy_configurations`**
        *   Purpose: Central registry of all strategies with their operational settings.
        *   Fields:
            *   `strategy_id`: Unique identifier (e.g., "SPX_1-D_Opt", "Forex").
            *   `strategy_name`: Human-readable name.
            *   `status`: ACTIVE | INACTIVE | TESTING.
            *   `trading_mode`: LIVE | PAPER.
            *   `account`: IBKR_Main | IBKR_Futures | Binance_Main.
            *   `include_in_optimization`: Boolean - whether to include in portfolio optimization.
            *   `risk_limits`: { max_position_size, max_daily_loss }.
            *   `developer_contact`: Email/Slack for strategy developer.
            *   `notes`: Free-text notes.
            *   `created_at`, `updated_at`: Timestamps.
    *   **Strategy Management APIs:**
        *   GET `/api/strategies` - List all strategies with configs.
        *   GET `/api/strategies/{strategy_id}` - Get single strategy config.
        *   POST `/api/strategies` - Create new strategy config.
        *   PUT `/api/strategies/{strategy_id}` - Update strategy config.
        *   DELETE `/api/strategies/{strategy_id}` - Delete strategy config.
        *   POST `/api/strategies/{strategy_id}/sync-backtest` - Trigger backtest data ingestion for this strategy.
    *   **Integration Points:**
        *   **SignalIngestionService**: Before processing signal, check if `strategy.status == ACTIVE`. Reject if INACTIVE.
        *   **CerebroService**:
            *   Load strategy configs on startup.
            *   Only include strategies with `include_in_optimization == true` in portfolio optimization.
            *   When sizing positions, respect strategy's `risk_limits`.
            *   Log which strategies are excluded from optimization.
        *   **ExecutionService**:
            *   Route orders to correct `account` based on strategy config.
            *   Respect `trading_mode` (LIVE vs PAPER) - if PAPER, log order but don't submit to broker.
    *   **Workflow:**
        1. Developer uploads backtest CSV → runs ingestion tool → data in `strategy_backtest_data`.
        2. Portfolio manager creates entry in `strategy_configurations` via frontend.
        3. Sets: Status=ACTIVE, Account=IBKR_Main, Mode=PAPER, Include in optimization=Yes.
        4. Portfolio optimizer runs → only considers ACTIVE strategies with optimization flag.
        5. Signal arrives → system checks config → routes to correct account + mode.

### Milestone 1.3: Simple Admin Frontend

**Goal:** Build a basic web dashboard for portfolio managers to monitor trading and manage allocations.

**Tech Stack:**
*   **Frontend:** Vite + React + TailwindCSS
*   **Charts:** Recharts (for correlation heatmap, equity curves)
*   **Data Fetching:** React Query
*   **Deployment:** Local dev server initially, Cloud Storage + CDN later

**Pages:**

1.  **Dashboard Home (`/dashboard`):**
    *   Display current portfolio metrics:
        *   Current Equity
        *   Today's P&L ($ and %)
        *   Margin Used (% of max)
        *   Open Positions count
    *   Recent activity feed (last 10 signals/orders).

2.  **Strategy Allocations (`/allocations`):**
    *   **Current Allocations Table:**
        *   Columns: Strategy Name, Allocation %, Capital Allocated ($), Status.
        *   Show which allocation is currently ACTIVE.
    *   **Recommended Allocations Section:**
        *   Display latest PENDING_APPROVAL recommendation.
        *   Show comparison table: Strategy | Current % | Recommended % | Change.
        *   Action buttons: Approve, Edit & Approve, Reject.
    *   **Correlation Matrix Heatmap:**
        *   Visual heatmap showing strategy return correlations.
        *   Use Recharts or similar library.
    *   **Allocation History:**
        *   Table showing past allocations with timestamps and who approved them.

3.  **Trading Activity (`/activity`):**
    *   **Recent Signals Table:**
        *   Columns: Timestamp, Strategy, Symbol, Action, Price, Status.
        *   Show last 50 signals.
    *   **Recent Orders & Executions Table:**
        *   Columns: Timestamp, Order ID, Strategy, Symbol, Quantity, Status, Filled Price.
        *   Show last 50 orders.
    *   **Cerebro Decisions Log:**
        *   Show detailed position sizing calculations from Cerebro logs.

4.  **Strategy Management (`/strategies`):**
    *   **Purpose:** Control panel for which strategies are active, where they trade, and in what mode.
    *   **Strategies Table:**
        *   Columns:
            *   Strategy ID
            *   Strategy Name
            *   Status (Toggle: ACTIVE / INACTIVE / TESTING)
            *   Account (Dropdown: IBKR_Main, IBKR_Futures, Binance_Main)
            *   Trading Mode (Toggle: LIVE / PAPER)
            *   Include in Optimization (Toggle: Yes / No)
            *   Actions (Edit, Sync Backtest, Delete)
        *   Filters: Status, Account, Mode
        *   Search by strategy ID or name
    *   **Add New Strategy Button:**
        *   Opens modal with form:
            *   Strategy ID (text input, required)
            *   Strategy Name (text input, required)
            *   Status (dropdown)
            *   Account (dropdown)
            *   Trading Mode (radio buttons)
            *   Include in Optimization (checkbox)
            *   Risk Limits: Max Position Size ($), Max Daily Loss ($)
            *   Developer Contact (email)
            *   Notes (textarea)
    *   **Edit Strategy Modal:**
        *   Same form as add, pre-populated with existing data.
    *   **Sync Backtest Button:**
        *   Triggers `/api/strategies/{id}/sync-backtest` endpoint.
        *   Shows progress indicator.
        *   Displays success/error message.
    *   **Visual Indicators:**
        *   Green badge for ACTIVE strategies.
        *   Yellow badge for TESTING.
        *   Gray badge for INACTIVE.
        *   Red border for strategies missing backtest data.
        *   Blue badge for LIVE mode, Gray for PAPER.
    *   **Backtest Data Link:**
        *   For each strategy, show "View Backtest Data" link.
        *   Opens expandable row showing: Sharpe Ratio, Max Drawdown, Win Rate, Backtest Period.

5.  **Login Page (`/login`):**
    *   Simple username/password authentication.
    *   Store hashed passwords in MongoDB (`users` collection).
    *   Use JWT tokens for session management.

**API Integration:**
*   Connect to `AccountDataService` for account metrics, portfolio allocations, and strategy management.
*   Strategy Management endpoints: `/api/strategies/*`
*   Portfolio Allocation endpoints: `/api/portfolio/allocations/*`
*   Trading Activity endpoints: `/api/signals/*`, `/api/orders/*`
*   Use React Query for caching and real-time updates.

**Deployment:**
*   Run locally with `npm run dev` initially.
*   Build static assets with `npm run build`.
*   Deploy to Cloud Storage + CDN in Milestone 1.4.

### Milestone 1.4: GCP Deployment & CI/CD (MVP)

**Goal:** Get the MVP services running reliably in production with automated deployment.

1.  **GCP Project Setup:**
    *   Configure GCP Project, VPC, and basic firewall rules.
    *   Set up **Google Kubernetes Engine (GKE)** cluster.
    *   Configure **Google Secret Manager** for broker API keys and other credentials.
    *   Set up **IAM** roles for service accounts.
2.  **Containerization & Artifact Registry:**
    *   Refine Dockerfiles for all MVP services.
    *   Set up **Artifact Registry** for Docker image storage.
3.  **CI/CD Pipeline (Cloud Build):**
    *   Configure Cloud Build to trigger on GitHub pushes to a `main` branch (for production).
    *   Pipeline steps: build Docker images, push to Artifact Registry, update GKE deployments.
    *   Implement basic health checks for services in GKE.
4.  **Initial GKE Deployment:**
    *   Deploy all MVP services to GKE.
    *   Configure GKE Services for internal communication.
5.  **Monitoring & Logging (MVP):**
    *   Verify **Cloud Logging** is collecting logs from all GKE pods.
    *   Set up basic **Cloud Monitoring** dashboards for service health (CPU, Memory, Pub/Sub message rates).
    *   Configure essential **Cloud Alerting** for critical failures (e.g., service crashes, Pub/Sub errors).

---

## Phase 2: Feature Expansion & Optimization

**Goal:** Enhance Cerebro's intelligence, broaden broker support, add client/signal sender dashboards, and introduce the sandbox.

**Estimated Timeline:** (This phase will be ongoing, possibly 2-4 month iterations per major feature set)

### Milestone 2.1: Cerebro & Risk Management Enhancement

1.  **Advanced Portfolio Optimization (Cerebro):**
    *   Implement full MPT/cVaR calculations based on all available backtest data (correlation matrix, volatility, MDD).
    *   Refine dynamic capital allocation based on total capital and target cVaR.
    *   Implement calculation for **minimum account size** for a given strategy set.
    *   Integrate comprehensive backtest data schema from signal providers into Cerebro's decision-making.
2.  **Multi-Broker & Multi-Strategy Support:**
    *   Expand `ExecutionService` to integrate with **additional broker APIs**.
    *   Enhance `AccountDataService` to consolidate and reconcile data across *all* connected brokers.
    *   Refine `CerebroService` to consider overall margin across all accounts/brokers when sizing.
3.  **Robust Error Handling & Alerts:**
    *   Implement comprehensive "raise hell" alert mechanism for critical errors (e.g., unfillable exits, margin nearing limits, broker API failures).
    *   Integrate multi-channel notifications: Telegram, email, SMS, and dashboard alerts via Cloud Functions or a dedicated alerting service.
    *   Ensure alerts escalate appropriately based on severity and time-sensitivity.

### Milestone 2.2: Comprehensive Dashboards & Sandbox

1.  **Client Dashboard:**
    *   `DashboardDataProcessorService`: Calculate client-specific ROI (MoM, YoY), track deposits/withdrawals.
    *   `FrontendAPIService`: Add client authentication and data endpoints.
    *   `FrontendUI`: Develop client view displaying capital, deposits/withdrawals, current rate of return, historical ROI.
2.  **Signal Sender Dashboard:**
    *   `DashboardDataProcessorService`: Calculate per-signal profits, aggregate profits, track paid/due amounts, project next payment date (1st of month).
    *   `FrontendAPIService`: Add signal sender authentication and data endpoints.
    *   `FrontendUI`: Develop signal sender view displaying their signals, position sizing, money made, paid, due.
3.  **Cerebro Sandbox & Simulation Panel:**
    *   `CerebroService`: Develop a dedicated internal API endpoint or deploy a separate `CerebroSimulationService` instance specifically for sandbox simulations (operating on historical/hypothetical data).
    *   `FrontendAPIService`: Add endpoints for configuring sandbox settings, submitting simulation requests, and retrieving results.
    *   `FrontendUI` (Admin Panel):
        *   Develop UI for adjusting `Cerebro` parameters (cVaR target, allocation methods, etc.).
        *   Implement UI for adding hypothetical new strategies (inputting backtest data).
        *   Display simulation results (visualizations of performance, risk metrics, optimal allocations).
        *   Allow testing new strategies against existing ones.
    *   `MongoDB`: Define schema for storing sandbox configurations and simulation results.

---

## Phase 3: Continuous Improvement & Advanced Features

**Goal:** Refine performance, resilience, and introduce advanced capabilities.

**Estimated Timeline:** Ongoing iterations after Phase 2 is complete.

1.  **Performance Optimization:**
    *   Profiling and optimizing hot paths in `SignalIngestionService` and `CerebroService`.
    *   Exploring more granular streaming data for account updates where available.
2.  **Advanced Cash Management:**
    *   Develop policies and potentially automation for intra-broker capital reallocation or limited inter-broker transfers (requires careful design and security).
3.  **Enhanced Monitoring & Alerting:**
    *   Implement custom metrics in Cloud Monitoring for key trading statistics (e.g., number of dropped signals, average fill price vs. order price).
    *   More sophisticated anomaly detection.
4.  **Robust Versioning & A/B Testing for Cerebro:**
    *   Formalize the process for running `Cerebro` v1 in production alongside `Cerebro` v2 in a paper trading or simulation environment on live data.
5.  **Audit & Compliance Features:**
    *   Detailed audit trails for all critical actions and decisions.
    *   Reporting tools for regulatory compliance if applicable.
6.  **Advanced Signal Processing:**
    *   Machine learning for signal validation or noise filtering if signal sources become highly diverse.

---

This plan prioritizes getting a functional, secure, and risk-managed trading system online quickly, allowing you to begin operating your hedge fund, and then progressively adding sophisticated features. Regular review and adaptation based on real-world usage will be key.