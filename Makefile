.PHONY: start stop restart status logs clean help logs-signal-ingestion logs-account-data logs-portfolio logs-dashboard logs-mongodb send-test-signal restart-cerebro restart-execution restart-signal-ingestion restart-account-data restart-portfolio restart-dashboard clean-old-logs export-seed-data reseed-db

# Auto-detect timezone from system
export TZ := $(shell readlink /etc/localtime 2>/dev/null | sed 's|^.*/zoneinfo/||' || echo "UTC")

# Default target
help:
	@echo "Mathematricks Trader - Docker Management"
	@echo "----------------------------------------"
	@echo "make start         - Start core services (production mode - no signal-receiver)"
	@echo "make start-dev     - Start all services including signal-receiver (development mode)"
	@echo "make stop          - Stop all services"
	@echo "make restart       - Restart all services"
	@echo "make status        - Check status of services"
	@echo "make logs          - View logs of all services"
	@echo "make logs-cerebro  - View logs of cerebro-service"
	@echo "make logs-execution - View logs of execution-service"
	@echo "make logs-signal-ingestion - View logs of signal-ingestion"
	@echo "make logs-signal-receiver - View logs of signal-receiver"
	@echo "make logs-account-data - View logs of account-data-service"
	@echo "make logs-portfolio - View logs of portfolio-builder"
	@echo "make logs-dashboard - View logs of dashboard-creator"
	@echo "make logs-mongodb  - View logs of mongodb"
	@echo "make send-test-signal - Send test ENTRY+EXIT signal for AAPL"
	@echo "make rebuild       - Rebuild all containers"
	@echo "make clean         - Stop and remove all containers and volumes (DATA LOSS!)"
	@echo "make clean-old-logs - Truncate Docker container logs (keeps containers running)"
	@echo "make export-seed-data - Export current MongoDB data as seed data"
	@echo "make reseed-db     - Restore MongoDB from latest seed data"
	@echo "Frontend running @ http://localhost:5173/"


start:
	@echo "Starting core services (production mode - no signal-receiver)..."
	docker-compose up -d mongodb cerebro-service execution-service account-data-service signal-ingestion portfolio-builder dashboard-creator frontend
	@echo "✅ Core services started"
	@echo "Frontend running @ http://localhost:5173/"

start-dev:
	@echo "Starting all services (development mode - with signal-receiver)..."
	docker-compose up -d
	@echo "✅ All services started (including signal-receiver)"
	@echo "Frontend running @ http://localhost:5173/"
	@echo "Signal Receiver API @ http://localhost:3000/api/v1/signals"

stop:
	docker-compose stop

restart:
	@echo "Restarting services (excluding mongodb-init)..."
	docker-compose restart cerebro-service execution-service account-data-service signal-ingestion portfolio-builder dashboard-creator frontend
	@echo "Frontend running @ http://localhost:5173/"

status:
	@echo "=== Docker Compose Services ==="
	docker-compose ps
	@echo ""
	@echo "=== All Project Containers (including dynamic IBGateway) ==="
	docker ps --filter "network=tradenet" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
	@echo ""
	@echo "Frontend running @ http://localhost:5173/"

logs:
	docker-compose logs -f cerebro-service execution-service signal-ingestion account-data-service portfolio-builder dashboard-creator

logs-cerebro:
	docker-compose logs -f cerebro-service

logs-execution:
	docker-compose logs -f execution-service

logs-frontend:
	docker-compose logs -f frontend

logs-signal-ingestion:
	docker-compose logs -f signal-ingestion

logs-account-data:
	docker-compose logs -f account-data-service

logs-portfolio:
	docker-compose logs -f portfolio-builder

logs-dashboard:
	docker-compose logs -f dashboard-creator

logs-mongodb:
	docker-compose logs -f mongodb

logs-signal-receiver:
	docker-compose logs -f signal-receiver

send-test-signal:
	python3 ./tests/signals_testing/send_test_signal.py --file ./tests/signals_testing/sample_signals/equity_simple_signal_1.json

restart-cerebro:
	docker-compose restart cerebro-service

restart-execution:
	docker-compose restart execution-service

restart-signal-ingestion:
	docker-compose restart signal-ingestion

restart-account-data:
	docker-compose restart account-data-service

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
	@docker-compose stop cerebro-service execution-service signal-ingestion account-data-service portfolio-builder dashboard-creator frontend 2>/dev/null || true
	@echo ""
	@echo "Removing service containers (logs will be cleared)..."
	@docker-compose rm -f cerebro-service execution-service signal-ingestion account-data-service portfolio-builder dashboard-creator frontend 2>/dev/null || true
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
