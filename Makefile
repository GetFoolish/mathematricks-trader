.PHONY: start stop restart status logs clean help logs-signal-ingestion logs-account-data logs-portfolio logs-dashboard logs-mongodb send-test-signal restart-cerebro restart-execution restart-signal-ingestion restart-account-data restart-portfolio restart-dashboard

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

start:
	docker-compose up -d

stop:
	docker-compose stop

restart:
	docker-compose restart

status:
	docker-compose ps

logs:
	docker-compose logs -f cerebro-service execution-service signal-ingestion account-data-service portfolio-builder dashboard-creator frontend pubsub-emulator

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
	docker-compose down -v
