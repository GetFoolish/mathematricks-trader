# Docker Development Setup - Mathematricks Trader

## Overview

This guide explains how development works with Docker. **TL;DR:** You code on your machine as normal, Docker runs everything in the background.

---

## Development Approach: Code Lives on Your Machine, Runs in Docker ✅

### How It Works

```
Your Mac/Windows/Linux Machine
├── mathematricks-trader/          ← Your files are HERE (on your computer)
│   ├── services/
│   │   ├── cerebro_service/
│   │   │   └── cerebro_main.py    ← You edit THIS file with VS Code/PyCharm
│   │   └── ...
│   ├── frontend-admin/
│   │   └── src/                   ← You edit React components here
│   └── docker-compose.yml
│
Docker Containers (running in background)
├── Container: cerebro-service
│   └── /app/services/             ← SAME files (volume mounted, live sync)
├── Container: mongodb
├── Container: pubsub-emulator
└── Container: frontend
```

**Key Concept:** Your code files exist on your computer. Docker **mounts** them (like a network drive), so containers see the same files. When you edit a file, containers see the change instantly.

### What This Means for You

✅ **Edit code with your normal IDE** (VS Code, PyCharm, Sublime, whatever)
✅ **Files live on your Mac/Windows/Linux** (your filesystem, your backups)
✅ **Changes appear instantly** in Docker (hot-reload)
✅ **Git works normally** (commit, push, pull on your machine)
✅ **No SSH into containers** (you never "go inside" Docker)
✅ **Debugger works** (VS Code remote debugging to containers)

❌ **Don't edit files inside containers** (changes won't persist)
❌ **Don't install packages inside containers** (use Dockerfile instead)

---

## Daily Development Workflow

### Monday Morning - Starting Work

```bash
# Navigate to project
cd /path/to/mathematricks-trader

# Start all services
make start

# Output:
# ✓ Starting mongodb...
# ✓ Starting pubsub-emulator...
# ✓ Starting ib-gateway...
# ✓ Starting account-data-service...
# ✓ Starting cerebro-service...
# ✓ Starting execution-service...
# ✓ Starting frontend...
#
# All services started!
# Admin Dashboard: http://localhost:5173

# Check status
make status

# Output:
# NAME                  STATUS      PORTS
# mongodb               healthy     27017
# pubsub-emulator       healthy     8085
# cerebro-service       running     -
# execution-service     running     -
# frontend              running     5173
```

Everything is now running. Your terminal returns to normal. Services run in background.

### During Development

#### Scenario 1: Fix a Bug in Python Service

```bash
# 1. Open your IDE on your machine
code .  # VS Code
# OR
pycharm .  # PyCharm

# 2. Navigate to the file (on YOUR machine)
# File: services/cerebro_service/cerebro_main.py
# Line 150: Fix the position sizing bug

# 3. Save the file (Cmd+S / Ctrl+S)
# → Docker sees the change instantly
# → Python service auto-reloads (if configured)
# → New code is running

# 4. View logs to verify fix
make logs-cerebro

# Output (live tail):
# cerebro-service | [2024-12-01 10:30:00] INFO: Position size calculated: 100 shares
# cerebro-service | [2024-12-01 10:30:01] INFO: Margin check passed
# cerebro-service | [2024-12-01 10:30:02] INFO: Order approved

# 5. Test the fix
# Send test signal, verify it works
python tests/signals_testing/send_test_signal.py
```

**No container restart needed!** Hot-reload handles it.

#### Scenario 2: Work on Frontend (React)

```bash
# 1. Open file in your editor
# File: frontend-admin/src/components/Dashboard.tsx

# 2. Make changes (add a new chart component)

# 3. Save file
# → Vite hot-reload triggers automatically
# → Browser updates immediately (no refresh needed)

# 4. View browser
# Open http://localhost:5173
# See your changes instantly
```

**Vite HMR (Hot Module Replacement) works with Docker!**

#### Scenario 3: Add a New Python Package

```bash
# 1. Edit requirements.txt on your machine
echo "pandas-ta==0.3.14" >> services/cerebro_service/requirements.txt

# 2. Rebuild the service container
docker-compose build cerebro-service

# Output:
# Building cerebro-service...
# Step 1/8 : FROM python:3.11-slim
# Step 2/8 : WORKDIR /app
# ...
# Successfully built abc123

# 3. Restart just that service
docker-compose restart cerebro-service

# OR use make command
make restart-cerebro
```

**Only rebuild what changed.** Other services keep running.

#### Scenario 4: Debug with Breakpoints

**Option A: Print Debugging (Simplest)**

```python
# In your code (services/cerebro_service/cerebro_main.py)
def calculate_position_size(signal):
    print(f"DEBUG: Signal received: {signal}")  # Add this
    position_size = calculate_margin(signal)
    print(f"DEBUG: Calculated size: {position_size}")  # Add this
    return position_size
```

```bash
# View output in real-time
make logs-cerebro

# You'll see:
# cerebro-service | DEBUG: Signal received: {'symbol': 'AAPL', ...}
# cerebro-service | DEBUG: Calculated size: 100
```

**Option B: VS Code Remote Debugging (Advanced)**

1. **Add debugpy to requirements.txt**
   ```
   debugpy==1.8.0
   ```

2. **Add to your service code**
   ```python
   # services/cerebro_service/cerebro_main.py
   import debugpy

   # Wait for debugger to attach
   debugpy.listen(("0.0.0.0", 5678))
   print("Waiting for debugger to attach...")
   debugpy.wait_for_client()
   print("Debugger attached!")
   ```

3. **Expose port in docker-compose.yml**
   ```yaml
   cerebro-service:
     ports:
       - "5678:5678"  # Debugger port
   ```

4. **Configure VS Code** (`.vscode/launch.json`)
   ```json
   {
     "name": "Attach to Cerebro (Docker)",
     "type": "python",
     "request": "attach",
     "connect": {
       "host": "localhost",
       "port": 5678
     },
     "pathMappings": [
       {
         "localRoot": "${workspaceFolder}",
         "remoteRoot": "/app"
       }
     ]
   }
   ```

5. **Start debugging**
   - Rebuild container: `make restart-cerebro`
   - In VS Code: Run > Start Debugging (F5)
   - Set breakpoints in your local file
   - Trigger the code (send signal)
   - Debugger stops at breakpoints!

#### Scenario 5: Database Changes

```bash
# Connect to MongoDB (running in Docker)
mongosh mongodb://localhost:27017/?replicaSet=rs0

# Run queries
use mathematricks_trading
db.signal_store.find().limit(5)

# OR use MongoDB Compass (GUI)
# Connection string: mongodb://localhost:27017/?replicaSet=rs0
```

**MongoDB data persists** even when you stop containers (Docker volume).

#### Scenario 6: View All Logs

```bash
# All services
make logs

# Specific service
make logs-cerebro
make logs-execution
make logs-frontend

# Last 100 lines
docker-compose logs --tail=100

# Follow logs (live tail)
docker-compose logs -f cerebro-service

# Multiple services
docker-compose logs -f cerebro-service execution-service
```

### Git Workflow (Important!)

**Git operates on your machine as normal. Docker doesn't interfere.**

#### Committing Changes

```bash
# You edited files on your machine
# Files: services/cerebro_service/cerebro_main.py
#        frontend-admin/src/components/Dashboard.tsx

# 1. Check what changed (on your machine)
git status

# Output:
# modified:   services/cerebro_service/cerebro_main.py
# modified:   frontend-admin/src/components/Dashboard.tsx

# 2. View diff (on your machine)
git diff services/cerebro_service/cerebro_main.py

# 3. Stage changes (on your machine)
git add services/cerebro_service/cerebro_main.py
git add frontend-admin/src/components/Dashboard.tsx

# 4. Commit (on your machine)
git commit -m "Fix position sizing bug and update dashboard UI"

# 5. Push to GitHub (on your machine)
git push origin main

# ✅ All git operations work normally!
# ✅ Docker containers keep running in background
# ✅ No special steps needed
```

**Key Point:** Docker containers don't contain your `.git` folder. Git is entirely on your machine.

#### Pulling Changes (Team Collaboration)

```bash
# Teammate pushed changes to GitHub
# You want to pull them

# 1. Pull changes (on your machine)
git pull origin main

# Output:
# Updating abc123..def456
# Fast-forward
#  services/execution_service/execution_main.py | 10 +++++++---
#  requirements.txt                              |  1 +
#  2 files changed, 8 insertions(+), 3 deletions(-)

# 2. Check if requirements.txt changed
git show --name-only | grep requirements.txt

# If YES (new package added):
# 3. Rebuild affected containers
docker-compose build execution-service

# 4. Restart service
docker-compose restart execution-service

# If NO (just code changes):
# Docker hot-reload handles it automatically!
# No action needed.
```

**Workflow for pulling changes:**
- Python code changes → Auto hot-reload (no action)
- Frontend code changes → Vite HMR (no action)
- requirements.txt changes → Rebuild container
- docker-compose.yml changes → Restart all (`make restart`)
- dockerfile changes → Rebuild all (`docker-compose build`)

#### Working on a Feature Branch

```bash
# 1. Create branch (on your machine)
git checkout -b feature/new-risk-model

# 2. Make changes (edit files on your machine)
# Edit: services/cerebro_service/risk_calculator.py

# 3. Test with Docker (still running)
make logs-cerebro
# Verify your changes work

# 4. Commit (on your machine)
git add .
git commit -m "Implement Kelly Criterion risk model"

# 5. Push branch (on your machine)
git push origin feature/new-risk-model

# 6. Create Pull Request on GitHub
# (Browser, GitHub UI)

# 7. Teammate reviews
# They pull your branch:
git fetch origin
git checkout feature/new-risk-model

# They test with Docker:
make restart-cerebro
# Docker runs your code automatically!

# 8. Merge via GitHub
# Switch back to main:
git checkout main
git pull origin main

# 9. Rebuild if needed
make restart
```

**Branches work perfectly with Docker!** Containers use whatever code is in your current branch.

#### Handling Merge Conflicts

```bash
# 1. Pull main (conflict occurs)
git pull origin main

# Output:
# Auto-merging services/cerebro_service/cerebro_main.py
# CONFLICT (content): Merge conflict in services/cerebro_service/cerebro_main.py

# 2. Docker keeps running (using old code)
# Don't worry, services still work

# 3. Resolve conflict in your editor (on your machine)
code services/cerebro_service/cerebro_main.py

# Fix conflict markers:
# <<<<<<< HEAD
# your code
# =======
# their code
# >>>>>>> origin/main

# 4. Save resolved file

# 5. Test immediately (Docker auto-reloads)
make logs-cerebro
# Verify it works

# 6. Commit resolution
git add services/cerebro_service/cerebro_main.py
git commit -m "Merge main and resolve position sizing conflict"
git push
```

**Docker hot-reload lets you test conflict resolutions immediately!**

### End of Day

```bash
# Stop all services
make stop

# Output:
# Stopping cerebro-service... done
# Stopping execution-service... done
# Stopping frontend... done
# Stopping mongodb... done
# ...

# Your code is still on your machine
# Containers are stopped (not deleted)
# Data persists (MongoDB volumes)
```

**Next morning:** `make start` and everything comes back exactly as you left it.

---

## File Structure: What Lives Where?

### On Your Machine (Persistent) ✅

```
mathematricks-trader/
├── .git/                  ← Git repository (your commits, history)
├── services/              ← YOUR CODE (edit with VS Code/PyCharm)
│   ├── cerebro_service/
│   │   ├── cerebro_main.py
│   │   └── ...
│   └── ...
├── frontend-admin/        ← YOUR FRONTEND CODE
│   └── src/
├── documentation/         ← THIS FILE
├── .env                   ← YOUR SECRETS (not in git!)
├── logs/                  ← LOG FILES (volume mounted, persists)
├── docker-compose.yml     ← DOCKER CONFIG
└── README.md
```

**These files never go "into" Docker.** They're mounted (shared).

### In Docker Containers (Ephemeral) 🐳

```
Container: cerebro-service
├── /app/services/         ← MOUNTED from your machine (same files!)
├── /app/venv/            ← Python packages (installed from requirements.txt)
├── /usr/bin/python       ← Python interpreter (from Docker image)
└── /etc/...              ← Operating system (Ubuntu/Debian)
```

**If you delete a container and recreate it:**
- ✅ Your code is safe (on your machine)
- ✅ Git history is safe (on your machine)
- ✅ Database data is safe (Docker volume)
- ❌ Python packages reinstall (from requirements.txt)
- ❌ Container OS resets (no problem, it's standardized)

---

## Common Tasks

### Restart Everything

```bash
make restart
# OR
docker-compose restart
```

### Restart One Service

```bash
docker-compose restart cerebro-service
```

### Rebuild After Dependency Changes

```bash
# Edit requirements.txt
echo "new-package==1.0.0" >> services/cerebro_service/requirements.txt

# Rebuild
docker-compose build cerebro-service

# Restart
docker-compose restart cerebro-service
```

### Clean Slate (Nuclear Option)

```bash
# Stop and remove everything (including volumes)
docker-compose down -v

# Rebuild everything
docker-compose build

# Start fresh
make start
```

⚠️ **This deletes MongoDB data!** Export data first if you need it.

### View Resource Usage

```bash
docker stats

# Output:
# CONTAINER         CPU %     MEM USAGE / LIMIT     MEM %
# cerebro-service   5.2%      150MiB / 4GiB         3.75%
# mongodb           2.1%      300MiB / 4GiB         7.50%
# frontend          1.5%      80MiB / 4GiB          2.00%
```

### Access Service Shell (Rare)

```bash
# Only if you need to investigate something inside container
docker-compose exec cerebro-service /bin/bash

# You're now inside container
root@abc123:/app# ls
root@abc123:/app# python --version
root@abc123:/app# exit
```

**Usually not needed!** All development happens on your machine.

---

## Troubleshooting

### "My changes aren't appearing!"

**Check:**
1. Did you save the file? (Cmd+S / Ctrl+S)
2. Is the service still running? `make status`
3. Does the service support hot-reload? (Python services need `watchdog` or similar)
4. Check logs: `make logs-cerebro`

**Fix:**
```bash
docker-compose restart cerebro-service
```

### "Port already in use"

**Error:**
```
Error: bind: address already in use
```

**Cause:** Something else using port 8082, 5173, etc.

**Fix:**
```bash
# Find what's using the port
lsof -i :8082

# Kill the process
kill -9 <PID>

# OR change port in docker-compose.yml
ports:
  - "8090:8082"  # Use 8090 externally instead
```

### "MongoDB connection failed"

**Check:**
```bash
docker-compose ps mongodb

# Should show: healthy
```

**Fix:**
```bash
docker-compose restart mongodb

# Wait 10 seconds, then:
docker-compose restart cerebro-service
```

### "Lost all my data!"

**Don't panic:**
- Your code is on your machine (safe)
- Git history is on your machine (safe)
- Only container data is lost

**Prevent:**
- Commit often: `git commit`
- Push often: `git push`
- Don't use `docker-compose down -v` unless you mean it

---

## Performance Tips

### Speed Up Builds

**Use BuildKit:**
```bash
# Add to ~/.bashrc or ~/.zshrc
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
```

### Reduce Image Size

**Multi-stage builds** (already in our Dockerfiles):
```dockerfile
FROM python:3.11-slim AS builder
# Install build dependencies
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim
# Copy only runtime dependencies
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
```

### Faster Container Startup

**Increase Docker resources:**
- Docker Desktop → Settings → Resources
- RAM: 4GB minimum (8GB recommended)
- CPUs: 4 cores recommended
- Disk: 20GB minimum

---

## What You DON'T Need to Know

❌ **Docker internals** (just use `make start`)
❌ **Container networking** (it's configured)
❌ **Volume syntax** (it's in docker-compose.yml)
❌ **Dockerfile syntax** (they're already written)
❌ **Orchestration theory** (Docker Compose handles it)

**Just code normally.** Docker runs in the background.

---

## Summary: Your New Workflow

```bash
# Morning
make start          # Start everything (30 seconds)

# During day
code .              # Edit files normally on your machine
git add/commit/push # Git works normally
make logs-cerebro   # View logs when needed

# Evening
make stop           # Stop everything
```

**That's it!** Develop exactly as you did before, but without environment issues.

---

## Questions?

- **Do I need to learn Docker?** No, just use the Makefile commands.
- **Can I use PyCharm?** Yes! It works the same as VS Code.
- **Does Git work?** Yes, exactly as before.
- **Can I debug?** Yes, with VS Code remote debugging.
- **What if I break something?** `make restart` fixes most issues.
- **Where are my files?** On your machine, where they've always been.

**The golden rule:** Code lives on your machine. Docker just runs it.
