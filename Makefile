.PHONY: start stop restart status logs clean help logs-signal-ingestion logs-account-data logs-portfolio logs-dashboard logs-mongodb send-test-signal restart-cerebro restart-execution restart-signal-ingestion restart-account-data restart-portfolio restart-dashboard clean-old-logs export-seed-data reseed-db test-signals

# Auto-detect timezone from system
export TZ := $(shell readlink /etc/localtime 2>/dev/null | sed 's|^.*/zoneinfo/||' || echo "UTC")

# Default target
help:
	@echo "Mathematricks Trader - Docker Management"
	@echo "----------------------------------------"
	@echo "make start         - Start all services in background"
	@echo "make stop          - Stop all services"
	@echo "make restart       - Restart all services"
	@echo "make status        - Check status of services"
	@echo "make logs          - View logs of all services"
	@echo "make logs-cerebro  - View logs of cerebro-service"
	@echo "make logs-execution - View logs of execution-service"
	@echo "make logs-signal-ingestion - View logs of signal-ingestion"
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
	@echo "make test-signals  - Reseed DB, start services, and run all test signals"
	@echo "Frontend running @ http://localhost:5173/"


start:
	docker-compose up -d
	@echo "Frontend running @ http://localhost:5173/"

stop:
	docker-compose stop

restart:
	@echo "Restarting services (excluding mongodb-init)..."
	docker-compose restart cerebro-service execution-service account-data-service signal-ingestion portfolio-builder dashboard-creator frontend
	@echo "Frontend running @ http://localhost:5173/"

status:
	docker-compose ps
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
	@echo "Truncating Docker container logs (no restart needed)..."
	@for container in $$(docker-compose ps -q 2>/dev/null); do \
		log_path=$$(docker inspect $$container --format='{{.LogPath}}' 2>/dev/null); \
		if [ -n "$$log_path" ] && [ -f "$$log_path" ]; then \
			name=$$(docker inspect $$container --format='{{.Name}}' | sed 's/^\///'); \
			size_before=$$(du -h "$$log_path" 2>/dev/null | cut -f1); \
			sudo truncate -s 0 "$$log_path" 2>/dev/null && \
			echo "  ✓ $$name: $$size_before -> 0"; \
		fi; \
	done
	@echo "✅ Logs truncated. Containers still running."

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
