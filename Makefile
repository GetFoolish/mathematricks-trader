.PHONY: start dev live dev-live stop restart status logs help \
        logs-cerebro logs-execution logs-frontend-admin logs-frontend logs-signal-ingestion logs-portfolio logs-dashboard logs-mongodb \
        restart-cerebro restart-execution restart-signal-ingestion restart-portfolio restart-dashboard \
        clean-old-logs export-seed-data reseed-db rebuild clean

# Auto-detect timezone from system
export TZ := $(shell readlink /etc/localtime 2>/dev/null | sed 's|^.*/zoneinfo/||' || echo "UTC")

# MongoDB Connection Strings
MONGODB_URI_LOCAL := mongodb://mongodb:27018/?replicaSet=rs0
MONGODB_URI_CLOUD := mongodb+srv://vandan_db_user:pY3qmfZmpWqleff3@mathematricks-signalscl.bmgnpvs.mongodb.net/mathematricks_trading
MONGODB_CONN_LOCAL := mongodb://mongodb:27018/mathematricks_trading?replicaSet=rs0&directConnection=true
MONGODB_CONN_CLOUD := mongodb+srv://vandan_db_user:pY3qmfZmpWqleff3@mathematricks-signalscl.bmgnpvs.mongodb.net/mathematricks_trading

# DEPLOY variable for export-seed-data only (local|cloud)
DEPLOY ?= local

# Core services (no signal receiver - it runs in cloud for live/dev-live modes)
CORE_SERVICES = mongodb cerebro-service execution-service signal-ingestion portfolio-builder dashboard-creator frontend-admin

# Default target
help:
	@echo "Mathematricks Trader - Docker Management"
	@echo "========================================="
	@echo ""
	@echo "STARTUP MODES:"
	@echo "  make start dev      - All services, local MongoDB (signal receiver runs locally)"
	@echo "  make start live     - Core services, cloud MongoDB (signal receiver runs in cloud)"
	@echo "  make start dev-live - Core services, local MongoDB + signal-ingestion on cloud MongoDB"
	@echo ""
	@echo "RESTART:"
	@echo "  make restart dev      - Restart in dev mode"
	@echo "  make restart live     - Restart in live mode"
	@echo "  make restart dev-live - Restart in dev-live mode"
	@echo ""
	@echo "SERVICE CONTROL:"
	@echo "  make stop                      - Stop all services"
	@echo "  make status                    - Check status of all services"
	@echo "  make rebuild                   - Rebuild all containers"
	@echo "  make restart-cerebro           - Restart cerebro-service only"
	@echo "  make restart-execution         - Restart execution-service only"
	@echo "  make restart-signal-ingestion  - Restart signal-ingestion only"
	@echo "  make restart-portfolio         - Restart portfolio-builder only"
	@echo "  make restart-dashboard         - Restart dashboard-creator only"
	@echo ""
	@echo "LOGS:"
	@echo "  make logs                   - All core services"
	@echo "  make logs-cerebro"
	@echo "  make logs-execution"
	@echo "  make logs-signal-ingestion"
	@echo "  make logs-portfolio"
	@echo "  make logs-dashboard"
	@echo "  make logs-frontend-admin"
	@echo "  make logs-frontend"
	@echo "  make logs-mongodb"
	@echo ""
	@echo "DATABASE:"
	@echo "  make export-seed-data              - Export local MongoDB as seed data"
	@echo "  make export-seed-data DEPLOY=cloud - Export cloud MongoDB as seed data"
	@echo "  make reseed-db                     - Restore MongoDB from latest seed data"
	@echo "  make clean-old-logs                - Truncate container logs (keeps MongoDB running)"
	@echo "  make clean                         - Remove all containers + volumes (DATA LOSS!)"
	@echo ""
	@echo "TESTING:"
	@echo "  This section is going to be developed later"
	@echo ""
	@echo "URLs:"
	@echo "  Frontend Admin: http://localhost:3001/"
	@echo "  Website + API:  http://localhost:3000/  (dev mode only)"


# --- Startup Modes ---
# Usage: make start dev | make start live | make start dev-live

# Absorb the mode word so make doesn't error on it
dev live dev-live:
	@true

start:
	@MODE=$(filter dev live dev-live, $(MAKECMDGOALS)); \
	if [ "$$MODE" = "dev" ]; then \
		echo "Starting all services (dev mode - local MongoDB, local signal receiver)..."; \
		MONGODB_URI=$(MONGODB_URI_LOCAL) mongodbconnectionstring=$(MONGODB_CONN_LOCAL) docker-compose up -d --wait; \
		echo ""; \
		echo "✅ All services started"; \
		echo "📊 MongoDB: 🏠 Local"; \
		echo "Frontend Admin:      http://localhost:3001/"; \
		echo "Website + API:       http://localhost:3000"; \
		echo "Signal Receiver API: http://localhost:3000/api/v1/signals"; \
	elif [ "$$MODE" = "live" ]; then \
		echo "Starting core services (live mode - cloud MongoDB, signal receiver in cloud)..."; \
		MONGODB_URI=$(MONGODB_URI_CLOUD) mongodbconnectionstring=$(MONGODB_CONN_CLOUD) docker-compose up -d --wait $(CORE_SERVICES); \
		echo ""; \
		echo "✅ Core services started"; \
		echo "📊 MongoDB: ☁️  Cloud (Atlas)"; \
		echo "Frontend Admin: http://localhost:3001/"; \
	elif [ "$$MODE" = "dev-live" ]; then \
		echo "Starting core services (dev-live mode - local MongoDB, signal-ingestion on cloud)..."; \
		MONGODB_URI=$(MONGODB_URI_LOCAL) mongodbconnectionstring=$(MONGODB_CONN_LOCAL) SIGNAL_INGESTION_MONGODB_URI=$(MONGODB_URI_CLOUD) docker-compose up -d --wait $(CORE_SERVICES); \
		echo ""; \
		echo "✅ Core services started"; \
		echo "📊 MongoDB: 🏠 Local (signal-ingestion: ☁️  Cloud)"; \
		echo "Frontend Admin: http://localhost:3001/"; \
	else \
		echo "Usage:"; \
		echo "  make start dev      - local MongoDB, local signal receiver"; \
		echo "  make start live     - cloud MongoDB, signal receiver in cloud"; \
		echo "  make start dev-live - local MongoDB, signal-ingestion on cloud MongoDB"; \
	fi


# --- Stop ---

stop:
	@echo "Stopping all services..."
	docker-compose stop
	@echo "Stopping and removing IB Gateway containers..."
	@docker ps -a --filter "name=ib-gateway-" --format "{{.Names}}" | xargs -r docker rm -f 2>/dev/null || true
	@echo "✅ All services stopped"


# --- Restart ---
# Usage: make restart dev | make restart live | make restart dev-live

restart:
	@MODE=$(filter dev live dev-live, $(MAKECMDGOALS)); \
	if [ "$$MODE" = "dev" ]; then \
		echo "Restarting services (dev mode)..."; \
		docker-compose stop; \
		docker ps -a --filter "name=ib-gateway-" --format "{{.Names}}" | xargs -r docker stop 2>/dev/null || true; \
		docker ps -a --filter "name=ib-gateway-" --format "{{.Names}}" | xargs -r docker rm 2>/dev/null || true; \
		MONGODB_URI=$(MONGODB_URI_LOCAL) mongodbconnectionstring=$(MONGODB_CONN_LOCAL) docker-compose up -d --wait; \
		echo ""; \
		echo "=== Service Status ==="; \
		docker-compose ps; \
		echo ""; \
		echo "=== IB Gateway Status ==="; \
		docker ps --filter "name=ib-gateway-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "⚠️  No IB Gateway containers running"; \
		echo ""; \
		echo "✅ Restarted (dev mode)"; \
		echo "📊 MongoDB: 🏠 Local"; \
		echo "Frontend Admin: http://localhost:3001/"; \
	elif [ "$$MODE" = "live" ]; then \
		echo "Restarting services (live mode)..."; \
		docker-compose stop $(CORE_SERVICES) frontend; \
		docker ps -a --filter "name=ib-gateway-" --format "{{.Names}}" | xargs -r docker stop 2>/dev/null || true; \
		docker ps -a --filter "name=ib-gateway-" --format "{{.Names}}" | xargs -r docker rm 2>/dev/null || true; \
		MONGODB_URI=$(MONGODB_URI_CLOUD) mongodbconnectionstring=$(MONGODB_CONN_CLOUD) docker-compose up -d --wait $(CORE_SERVICES); \
		echo ""; \
		echo "=== Service Status ==="; \
		docker-compose ps; \
		echo ""; \
		echo "=== IB Gateway Status ==="; \
		docker ps --filter "name=ib-gateway-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "⚠️  No IB Gateway containers running"; \
		echo ""; \
		echo "✅ Restarted (live mode)"; \
		echo "📊 MongoDB: ☁️  Cloud (Atlas)"; \
		echo "Frontend Admin: http://localhost:3001/"; \
	elif [ "$$MODE" = "dev-live" ]; then \
		echo "Restarting services (dev-live mode)..."; \
		docker-compose stop $(CORE_SERVICES) frontend; \
		docker ps -a --filter "name=ib-gateway-" --format "{{.Names}}" | xargs -r docker stop 2>/dev/null || true; \
		docker ps -a --filter "name=ib-gateway-" --format "{{.Names}}" | xargs -r docker rm 2>/dev/null || true; \
		MONGODB_URI=$(MONGODB_URI_LOCAL) mongodbconnectionstring=$(MONGODB_CONN_LOCAL) SIGNAL_INGESTION_MONGODB_URI=$(MONGODB_URI_CLOUD) docker-compose up -d --wait $(CORE_SERVICES); \
		echo ""; \
		echo "=== Service Status ==="; \
		docker-compose ps; \
		echo ""; \
		echo "=== IB Gateway Status ==="; \
		docker ps --filter "name=ib-gateway-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "⚠️  No IB Gateway containers running"; \
		echo ""; \
		echo "✅ Restarted (dev-live mode)"; \
		echo "📊 MongoDB: 🏠 Local (signal-ingestion: ☁️  Cloud)"; \
		echo "Frontend Admin: http://localhost:3001/"; \
	else \
		echo "Usage:"; \
		echo "  make restart dev      - Restart in dev mode"; \
		echo "  make restart live     - Restart in live mode"; \
		echo "  make restart dev-live - Restart in dev-live mode"; \
	fi


# --- Status & Logs ---

status:
	@echo "=== Docker Compose Services ==="
	docker-compose ps
	@echo ""
	@echo "=== All Project Containers (including dynamic IBGateway) ==="
	docker ps --filter "network=tradenet" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
	@echo ""
	@echo "Frontend Admin: http://localhost:3001/"
	@echo "Website: http://localhost:3000"

logs:
	docker-compose logs -f cerebro-service execution-service signal-ingestion portfolio-builder dashboard-creator

logs-cerebro:
	docker-compose logs -f cerebro-service

logs-execution:
	docker-compose logs -f execution-service

logs-frontend-admin:
	docker-compose logs -f frontend-admin

logs-frontend:
	docker-compose logs -f frontend

logs-signal-ingestion:
	docker-compose logs -f signal-ingestion

logs-portfolio:
	docker-compose logs -f portfolio-builder

logs-dashboard:
	docker-compose logs -f dashboard-creator

logs-mongodb:
	docker-compose logs -f mongodb


# --- Individual Service Restarts ---

restart-cerebro:
	docker-compose restart cerebro-service

restart-execution:
	docker-compose restart execution-service

restart-signal-ingestion:
	docker-compose restart signal-ingestion

restart-portfolio:
	docker-compose restart portfolio-builder

restart-dashboard:
	docker-compose restart dashboard-creator


# --- Build & Clean ---

rebuild:
	docker-compose build

clean-old-logs:
	@echo "🗑️  Clearing Docker container logs..."
	@echo ""
	@echo "⚠️  This will restart all containers to clear logs."
	@echo "Stopping services (preserving MongoDB)..."
	@docker-compose stop cerebro-service execution-service signal-ingestion portfolio-builder dashboard-creator frontend-admin frontend 2>/dev/null || true
	@echo ""
	@echo "Removing service containers (logs will be cleared)..."
	@docker-compose rm -f cerebro-service execution-service signal-ingestion portfolio-builder dashboard-creator frontend-admin frontend 2>/dev/null || true
	@echo ""
	@echo "Starting services with fresh logs..."
	@docker-compose up -d
	@echo ""
	@echo "✅ Service containers restarted with cleared logs!"
	@echo "💡 MongoDB was preserved to avoid replica set reinitialization."

clean:
	@echo "WARNING: This will remove all containers and volumes."
	@echo "Press Ctrl+C to cancel or wait 5 seconds..."
	@sleep 5
	docker-compose down -v


# --- Database ---

export-seed-data:
	@bash scripts/export_seed_data.sh $(DEPLOY)

reseed-db:
	@bash scripts/restore_seed_data.sh


# --- Testing ---

send-test-signal test-signals test test-preflight test-comprehensive test-unit test-integration test-e2e test-fast test-coverage test-clean:
	@echo "This section is going to be developed later"
