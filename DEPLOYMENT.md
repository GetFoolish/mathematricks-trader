# Mathematricks Trader - Deployment & Security Guide

**Purpose**: This document explains the container architecture, secure defaults, service discovery, volumes, logs, and local development instructions for the Dockerized Mathematricks Trader V1.

**Repository layout (Dockerized)**

```
mathematricks-trader/
├── docker/                       # Dockerfiles for services
│   ├── signal_collector/Dockerfile
│   ├── trader_engine/Dockerfile
│   ├── frontend/Dockerfile
│   └── telegram_notifier/Dockerfile
├── docker-compose.yml            # Production compose file
├── .env.example                  # Environment variable template
├── DEPLOYMENT.md                 # This document
├── requirements.txt
├── src/
├── frontend/
├── telegram/
├── main.py
├── signal_collector.py
└── ...
```

**High-level architecture**

- `mongodb` : persistent DB (no host port published)
- `trader_engine` : main engine processing signals, risk, orders
- `signal_collector` : polls MongoDB for TradingView signals and forwards them to trader engine
- `telegram_notifier` : sends Telegram alerts
- `frontend` : Streamlit dashboard, publishes a single host port (8501)

Networks:
- `internal_net` (internal: true) – used by backend services (trader, collector, telegram)
- `frontend_net` – used by frontend and mongodb (frontend accesses DB but cannot reach trader engine)

Service connectivity rules:
- All services reach MongoDB by the DNS name `mongodb` (Docker service name).
- `trader_engine` and `signal_collector` run on `internal_net` and can reach each other.
- `frontend` runs on `frontend_net` and can reach `mongodb` (mongodb is attached to both networks).
- Only `frontend` exposes a host port: `8501`.

Security Hardening (applied in compose and Dockerfiles):

- Base image: `python:3.12-slim` to reduce attack surface.
- Non-root user: Dockerfiles create `appuser` with UID/GID 1000 and switch to this user.
- Drop Linux capabilities: `cap_drop: ["ALL"]` in `docker-compose.yml` for services.
- Disable privilege escalation: `security_opt: ["no-new-privileges:true"]`.
- Read-only root filesystem: `read_only: true` for services that do not require writing to the container root (logs go to mounted volumes).
- Minimal packages installed in images; build deps removed after pip install.
- MongoDB is not published to the host and requires credentials (set via env vars).

Volumes & Logs:
- `mongo_data` – persistent DB storage at `/data/db` (named volume). Back up with standard Docker volume backups.
- `trader_logs` – mounted at `/app/logs` so the engine can write logs without making root filesystem writable.
- `frontend_cache` – Streamlit cache directory.

Environment variable strategy:
- Use `.env` in production populated from `.env.example`.
- Secrets should be stored and mounted via secret managers (e.g., Docker secrets, Vault, or cloud KMS), not in plain `.env` in production.
- The compose file references `.env` via `env_file: .env` for services that need runtime settings.

Service discovery:
- Services use Docker DNS and compose service names. Examples:
  - `mongodb` -> `mongodb:27017` (no published port)
  - `trader_engine` -> `trader_engine`
  - `signal_collector` -> `signal_collector`

Health checks & reliability (recommended additions):
- Add application-level health endpoints where possible (HTTP or small TCP) and reference them in `healthcheck` entries.
- Use `depends_on` with `condition: service_healthy` for graceful startup ordering.
- Restart policy: `unless-stopped` in compose; consider `on-failure` with limits for some services.

TLS & network-level security:
- Internal service traffic currently is unencrypted inside the Docker bridge network. For sensitive deployments, run an overlay network with mTLS or place services behind a service mesh (Linkerd/Consul) or terminate TLS via a sidecar reverse-proxy.

Production notes:
- Do NOT store `.env` in source control. Use a secret manager and inject variables at deploy time.
- Lock down host Docker daemon and use container runtime scanning.
- Use a minimal, immutable CI-built image registry (use pinned image digests in production compose or deployment manifests).

Local development (hot reloading)

1. Create a `.env` from `.env.example` and set development credentials.
2. Use a development override compose that binds your source code into containers. Example quick command (temporary bind):

```bash
# Run development with a bind mount for hot reload (NOT for production)
docker compose -f docker-compose.yml up --build \
  -d

# OR, to mount the src and frontend directories into the containers interactively:
docker run --rm -it \
  -v "${PWD}/src:/app/src:ro" \
  -v "${PWD}/frontend:/app/frontend:ro" \
  -e SYSTEM_MODE=development \
  -p 8501:8501 your_local_frontend_image
```

For hot reloading, prefer running Streamlit locally on the host during development and run only backend services in Docker.

Optional improvements / future work:
- Add `docker-compose.prod.yml` with pinned image digests and more strict resource limits.
- Add reverse-proxy (Traefik/Nginx) with TLS termination for the frontend.
- Move secrets to Docker secrets or external secret store.
- Add CI pipeline to build images and run integration tests before deploy.

-- End of document
