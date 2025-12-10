.PHONY: start stop restart status logs clean help

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
	docker-compose logs -f

logs-cerebro:
	docker-compose logs -f cerebro-service

logs-execution:
	docker-compose logs -f execution-service

logs-frontend:
	docker-compose logs -f frontend

restart-cerebro:
	docker-compose restart cerebro-service

rebuild:
	docker-compose build

clean:
	@echo "WARNING: This will remove all containers and volumes."
	@echo "Press Ctrl+C to cancel or wait 5 seconds..."
	@sleep 5
	docker-compose down -v
