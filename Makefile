.PHONY: start stop restart status logs clean help logs-signal-ingestion logs-portfolio logs-dashboard logs-mongodb send-test-signal restart-cerebro restart-execution restart-signal-ingestion restart-portfolio restart-dashboard clean-old-logs export-seed-data reseed-db

# Auto-detect timezone from system
export TZ := $(shell readlink /etc/localtime 2>/dev/null | sed 's|^.*/zoneinfo/||' || echo "UTC")

# MongoDB Deployment Target (use DEPLOY=cloud or DEPLOY=local)
# Usage: make start DEPLOY=cloud
#        make restart DEPLOY=local
DEPLOY ?= local

# MongoDB Connection Strings
MONGODB_URI_LOCAL := mongodb://mongodb:27018/?replicaSet=rs0
MONGODB_URI_CLOUD := mongodb+srv://vandan_db_user:pY3qmfZmpWqleff3@mathematricks-signalscl.bmgnpvs.mongodb.net/mathematricks_trading
MONGODB_CONN_LOCAL := mongodb://mongodb:27018/mathematricks_trading?replicaSet=rs0&directConnection=true
MONGODB_CONN_CLOUD := mongodb+srv://vandan_db_user:pY3qmfZmpWqleff3@mathematricks-signalscl.bmgnpvs.mongodb.net/mathematricks_trading

# Set MongoDB URI based on deployment target
ifeq ($(DEPLOY),cloud)
    export MONGODB_URI=$(MONGODB_URI_CLOUD)
    export mongodbconnectionstring=$(MONGODB_CONN_CLOUD)
    MONGO_LABEL=☁️  Cloud MongoDB (Atlas)
else
    export MONGODB_URI=$(MONGODB_URI_LOCAL)
    export mongodbconnectionstring=$(MONGODB_CONN_LOCAL)
    MONGO_LABEL=🏠 Local MongoDB (Docker)
endif

# Default target
help:
	@echo "Mathematricks Trader - Docker Management"
	@echo "----------------------------------------"
	@echo "make start              - Start core services with LOCAL MongoDB (default)"
	@echo "make start DEPLOY=cloud - Start core services with CLOUD MongoDB"
	@echo "make start-dev          - Start all services with LOCAL MongoDB (dev mode)"
	@echo "make stop               - Stop all services"
	@echo "make restart            - Restart all services with LOCAL MongoDB (default)"
	@echo "make restart DEPLOY=cloud - Restart all services with CLOUD MongoDB"
	@echo "make status             - Check status of services"
	@echo "make logs               - View logs of all services"
	@echo "make logs-cerebro  - View logs of cerebro-service"
	echo "make logs-execution - View logs of execution-service (includes account management)"
	echo "make logs-signal-ingestion - View logs of signal-ingestion"
	echo "make logs-frontend-admin - View logs of frontend-admin (admin dashboard)"
	echo "make logs-frontend - View logs of frontend (website + API)"
	echo "make logs-website  - View logs of frontend (website + API)"
	@echo "make logs-portfolio - View logs of portfolio-builder"
	@echo "make logs-dashboard - View logs of dashboard-creator"
	@echo "make logs-mongodb  - View logs of mongodb"
	@echo "make send-test-signal - Send test ENTRY+EXIT signal for AAPL"
	@echo "make rebuild       - Rebuild all containers"
	@echo "make clean         - Stop and remove all containers and volumes (DATA LOSS!)"
	@echo "make clean-old-logs - Truncate Docker container logs (keeps containers running)"
	@echo "make export-seed-data - Export current MongoDB data as seed data"
	@echo "make reseed-db     - Restore MongoDB from latest seed data"
	@echo ""
	@echo "MongoDB Deployment:"
	@echo "  Default: Local MongoDB (Docker)"
	@echo "  Use DEPLOY=cloud for Cloud MongoDB (Atlas)"
	@echo "  Example: make start DEPLOY=cloud"
	@echo ""
	@echo "Admin Dashboard @ http://localhost:3001/"
	@echo "Website + API @ http://localhost:3000/"


start:
	@echo "Starting core services (production mode - no website/API)..."
	@echo "📊 MongoDB: $(MONGO_LABEL)"
	@echo ""
	docker-compose up -d mongodb cerebro-service execution-service signal-ingestion portfolio-builder dashboard-creator frontend-admin
	@echo ""
	@echo "✅ Core services started"
	@echo "📊 MongoDB: $(MONGO_LABEL)"
	@echo "Frontend Admin: http://localhost:3001/"

start-dev:
	@echo "Starting all services (development mode - with website + API)..."
	@echo "📊 MongoDB: 🏠 Local MongoDB (Docker) - ALWAYS LOCAL IN DEV MODE"
	@echo ""
	@MONGODB_URI=$(MONGODB_URI_LOCAL) mongodbconnectionstring=$(MONGODB_CONN_LOCAL) docker-compose up -d
	@echo ""
	@echo "✅ All services started (including website + API)"
	@echo "📊 MongoDB: 🏠 Local MongoDB (Docker)"
	@echo "Frontend Admin: http://localhost:3001/"
	@echo "Website + API: http://localhost:3000"
	@echo "Signal Receiver API: http://localhost:3000/api/v1/signals"

stop:
	@echo "Stopping all services..."
	docker-compose stop
	@echo "Stopping and removing IB Gateway containers..."
	@docker ps -a --filter "name=ib-gateway-" --format "{{.Names}}" | xargs -r docker rm -f 2>/dev/null || true
	@echo "✅ All services stopped"

restart:
	@echo "Restarting all services..."
	@echo "📊 MongoDB: $(MONGO_LABEL)"
	@echo ""
	@echo "Stopping services..."
	@docker-compose stop mongodb cerebro-service execution-service signal-ingestion portfolio-builder dashboard-creator frontend-admin frontend
	@echo ""
	@echo "Stopping and removing IB Gateway containers..."
	@docker ps -a --filter "name=ib-gateway-" --format "{{.Names}}" | xargs -r docker stop 2>/dev/null || true
	@docker ps -a --filter "name=ib-gateway-" --format "{{.Names}}" | xargs -r docker rm 2>/dev/null || true
	@echo ""
	@echo "Starting and waiting for all services..."
	@docker-compose up -d --wait mongodb cerebro-service execution-service signal-ingestion portfolio-builder dashboard-creator frontend-admin frontend
	@echo ""
	@echo "=== Service Status ==="
	@docker-compose ps cerebro-service execution-service signal-ingestion portfolio-builder dashboard-creator frontend-admin frontend
	@echo ""
	@echo "=== IB Gateway Status ==="
	@docker ps --filter "name=ib-gateway-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "⚠️  No IB Gateway containers running"
	@echo ""
	@echo "✅ All services restarted!"
	@echo "📊 MongoDB: $(MONGO_LABEL)"
	@echo "Frontend Admin: http://localhost:3001/"
	@echo "Website: http://localhost:3000"

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

logs-website:
	docker-compose logs -f frontend

send-test-signal:
	python3 ./tests/signals_testing/send_test_signal.py --file ./tests/signals_testing/sample_signals/equity_simple_signal_1.json

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

rebuild:
	docker-compose build

clean:
	@echo "WARNING: This will remove all containers and volumes."
	@echo "Press Ctrl+C to cancel or wait 5 seconds..."
	@sleep 5

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
	@echo "Frontend running @ http://localhost:5173/"

clean:
	@echo "WARNING: This will remove all containers and volumes."
	@echo "Press Ctrl+C to cancel or wait 5 seconds..."
	@sleep 5
	docker-compose down -v

export-seed-data:
	@bash scripts/export_seed_data.sh

reseed-db:
	@bash scripts/restore_seed_data.sh

test-signals:
	@echo "🔄 Reseeding database..."
	@bash scripts/restore_seed_data.sh
	@echo ""
	@echo "🚀 Starting services..."
	@$(MAKE) start
	@echo ""
	@echo "⏳ Waiting 15 seconds for services to initialize..."
	@sleep 15
	@echo ""
	@echo "🧪 Running test signals..."
	@.venv/bin/python tests/signals_testing/run_full_test.py --folder tests/signals_testing/sample_signals

# Test Framework Targets
test:
	@echo "🧪 Running all tests with preflight checks..."
	@python tests/run_tests.py 9

test-preflight:
	@echo "� Running preflight checks only..."
	@python tests/run_tests.py preflight

test-comprehensive:
	@echo "🚀 Running comprehensive test suite..."
	@python tests/run_tests.py all

test-unit:
	@echo "🧪 Running unit tests with preflight checks..."
	@python tests/run_tests.py 1

test-integration:
	@echo "🧪 Running integration tests with preflight checks..."
	@python tests/run_tests.py 2

test-e2e:
	@echo "🧪 Running end-to-end tests with preflight checks..."
	@python tests/run_tests.py 3

test-fast:
	@echo "🧪 Running fast tests with preflight checks..."
	@python tests/run_tests.py 4

test-coverage:
	@echo "🧪 Running tests with coverage and preflight checks..."
	@python tests/run_tests.py 8
	@echo ""
	@echo "📊 Coverage report generated in htmlcov/index.html"

test-clean:
	@echo "🧹 Cleaning test artifacts..."
	@python tests/run_tests.py clean
