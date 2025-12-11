#!/usr/bin/env python3
"""
Run MVP Demo - Mathematricks Trading System
Starts all microservices with proper process management
"""
import os
import sys
import time
import json
import subprocess
import signal
import argparse
from pathlib import Path
from typing import Dict, List

# Colors for terminal output
class Colors:
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    NC = '\033[0m'  # No Color

PROJECT_ROOT = Path(__file__).parent.absolute()
VENV_PYTHON = PROJECT_ROOT / "venv" / "bin" / "python"
LOG_DIR = PROJECT_ROOT / "logs"
PID_DIR = LOG_DIR / "pids"

# IB Gateway Docker settings
IBKR_CONTAINER_NAME = "ib-gateway"
IBKR_IMAGE = "ghcr.io/gnzsnz/ib-gateway:latest"

# Global process registry
PROCESSES: Dict[str, subprocess.Popen] = {}

def load_env_file():
    """Load environment variables from .env file"""
    env_file = PROJECT_ROOT / ".env"
    env_vars = {}
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes from value
                    value = value.strip().strip('"').strip("'")
                    env_vars[key] = value
    return env_vars

def start_ibkr_gateway(use_live: bool = False):
    """Start IB Gateway Docker container"""
    print(f"\n{Colors.YELLOW}Starting IB Gateway Docker...{Colors.NC}")

    # Check if Docker is available
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"{Colors.RED}✗ Docker daemon is not running{Colors.NC}")
            print("  Please start Docker Desktop and try again")
            sys.exit(1)
    except FileNotFoundError:
        print(f"{Colors.RED}✗ Docker is not installed{Colors.NC}")
        sys.exit(1)

    # Check if container already exists and is running
    result = subprocess.run(
        ["docker", "ps", "--filter", f"name={IBKR_CONTAINER_NAME}", "--format", "{{.Names}}"],
        capture_output=True, text=True
    )
    if IBKR_CONTAINER_NAME in result.stdout:
        print(f"✓ IB Gateway container already running")
        return

    # Check if container exists but is stopped
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", f"name={IBKR_CONTAINER_NAME}", "--format", "{{.Names}}"],
        capture_output=True, text=True
    )
    if IBKR_CONTAINER_NAME in result.stdout:
        # Start existing container
        print("Starting existing IB Gateway container...")
        subprocess.run(["docker", "start", IBKR_CONTAINER_NAME], capture_output=True)
        print(f"✓ IB Gateway container started")
    else:
        # Create and start new container
        print("Creating new IB Gateway container...")

        # Load credentials from .env
        env_vars = load_env_file()

        if use_live:
            username = env_vars.get("IBKR_LIVE_USERNAME", "")
            password = env_vars.get("IBKR_LIVE_PASSWORD", "")
            trading_mode = "live"
        else:
            username = env_vars.get("IBKR_PAPER_USERNAME", "")
            password = env_vars.get("IBKR_PAPER_PASSWORD", "")
            trading_mode = "paper"

        if not username or not password:
            print(f"{Colors.RED}✗ IBKR credentials not found in .env file{Colors.NC}")
            print(f"  Please set IBKR_{'LIVE' if use_live else 'PAPER'}_USERNAME and IBKR_{'LIVE' if use_live else 'PAPER'}_PASSWORD")
            sys.exit(1)

        # Build docker command
        # gnzsnz/ib-gateway uses internal ports 4003 (live) and 4004 (paper)
        docker_cmd = [
            "docker", "run", "-d",
            "--name", IBKR_CONTAINER_NAME,
            "-p", "4001:4003",  # Live trading
            "-p", "4002:4004",  # Paper trading
            "-p", "5900:5900",  # VNC
            "-e", f"TWS_USERID={username}",
            "-e", f"TWS_PASSWORD={password}",
            "-e", f"TRADING_MODE={trading_mode}",
            "-e", "TWOFA_TIMEOUT_ACTION=restart",
            "-e", "READ_ONLY_API=no",
            "-e", "IBC_AcceptIncomingConnectionAction=accept",
            "-e", "VNC_SERVER_PASSWORD=ibgateway",  # Enable VNC with password
            IBKR_IMAGE
        ]

        result = subprocess.run(docker_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"{Colors.RED}✗ Failed to start IB Gateway container{Colors.NC}")
            print(f"  Error: {result.stderr}")
            sys.exit(1)

        print(f"✓ IB Gateway container created ({trading_mode} trading)")
        print(f"  {Colors.YELLOW}Note: First login requires 2FA approval on your IBKR mobile app{Colors.NC}")

    # Wait for API port to be ready
    port = 4001 if use_live else 4002
    print(f"Waiting for IB Gateway API (port {port})...")

    for i in range(30):  # Wait up to 30 seconds
        result = subprocess.run(
            ["lsof", "-i", f":{port}"],
            capture_output=True, text=True
        )
        if "LISTEN" in result.stdout:
            print(f"✓ IB Gateway API ready on port {port}")
            return
        time.sleep(1)

    print(f"{Colors.YELLOW}⚠️  IB Gateway API not ready yet (may need 2FA approval){Colors.NC}")
    print(f"  Check: docker logs {IBKR_CONTAINER_NAME}")

def cleanup_on_exit(signum=None, frame=None):
    """Cleanup handler for graceful shutdown"""
    print(f"\n{Colors.YELLOW}Received shutdown signal, cleaning up...{Colors.NC}")
    for name, proc in PROCESSES.items():
        try:
            proc.terminate()
            print(f"✓ Terminated {name}")
        except:
            pass

    # Stop IB Gateway Docker container
    try:
        result = subprocess.run(
            ["docker", "stop", IBKR_CONTAINER_NAME],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            print(f"✓ Stopped {IBKR_CONTAINER_NAME}")
    except:
        pass

    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, cleanup_on_exit)
signal.signal(signal.SIGTERM, cleanup_on_exit)

def check_prerequisites():
    """Check if all prerequisites are met"""
    print(f"{Colors.YELLOW}Checking prerequisites...{Colors.NC}")

    if not VENV_PYTHON.exists():
        print(f"{Colors.RED}✗ Python venv not found at {VENV_PYTHON}{Colors.NC}")
        sys.exit(1)
    print("✓ Python venv found")

    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        print(f"{Colors.RED}✗ .env file not found{Colors.NC}")
        sys.exit(1)
    print("✓ .env file found")

def start_pubsub_emulator():
    """Start Google Cloud Pub/Sub emulator"""
    print(f"\n{Colors.YELLOW}Step 1: Starting Pub/Sub emulator...{Colors.NC}")

    # Check if already running
    try:
        import requests
        response = requests.get("http://localhost:8085", timeout=1)
        print("✓ Pub/Sub emulator already running")
        return None
    except:
        pass

    # Start emulator
    print("Starting emulator in background...")
    emulator_jar = PROJECT_ROOT / "google-cloud-sdk" / "platform" / "pubsub-emulator" / "lib" / "cloud-pubsub-emulator-0.8.6.jar"
    java_path = "/opt/homebrew/opt/openjdk@11/bin/java"

    log_file = open(LOG_DIR / "pubsub_emulator.log", "w")
    proc = subprocess.Popen(
        [java_path, "-jar", str(emulator_jar), "--host=localhost", "--port=8085"],
        stdout=log_file,
        stderr=log_file,
        env={**os.environ, "PATH": "/opt/homebrew/opt/openjdk@11/bin:" + os.environ.get("PATH", "")}
    )

    # Save PID
    PID_DIR.mkdir(parents=True, exist_ok=True)
    (PID_DIR / "pubsub.pid").write_text(str(proc.pid))

    time.sleep(5)
    print(f"✓ Pub/Sub emulator started (PID: {proc.pid})")

    PROCESSES["pubsub"] = proc
    return proc

def setup_pubsub_topics():
    """Create Pub/Sub topics and subscriptions"""
    print(f"\n{Colors.YELLOW}Step 2: Creating Pub/Sub topics and subscriptions...{Colors.NC}")

    setup_script = """
from google.cloud import pubsub_v1
import time

project_id = 'mathematricks-trader'
publisher = pubsub_v1.PublisherClient()
subscriber = pubsub_v1.SubscriberClient()

# Create topics
topics = ['standardized-signals', 'trading-orders', 'execution-confirmations', 'account-updates', 'order-commands']
for topic_name in topics:
    topic_path = publisher.topic_path(project_id, topic_name)
    try:
        publisher.create_topic(request={"name": topic_path})
        print(f"✓ Created topic: {topic_name}")
    except Exception as e:
        if 'AlreadyExists' in str(e):
            print(f"  Topic {topic_name} already exists")
        else:
            print(f"✗ Error creating {topic_name}: {e}")

time.sleep(1)

# Create subscriptions
subscriptions = [
    ('standardized-signals-sub', 'standardized-signals', 600),
    ('trading-orders-sub', 'trading-orders', 600),
    ('execution-confirmations-sub', 'execution-confirmations', 600),
    ('account-updates-sub', 'account-updates', 600),
    ('order-commands-sub', 'order-commands', 600)
]

for sub_name, topic_name, ack_deadline in subscriptions:
    topic_path = publisher.topic_path(project_id, topic_name)
    sub_path = subscriber.subscription_path(project_id, sub_name)
    try:
        subscriber.create_subscription(
            request={
                "name": sub_path,
                "topic": topic_path,
                "ack_deadline_seconds": ack_deadline
            }
        )
        print(f"✓ Created subscription: {sub_name}")
    except Exception as e:
        if 'AlreadyExists' in str(e):
            print(f"  Subscription {sub_name} already exists")
        else:
            print(f"✗ Error creating {sub_name}: {e}")

print("✓ All topics and subscriptions ready!")
"""

    subprocess.run(
        [str(VENV_PYTHON), "-c", setup_script],
        env={**os.environ, "PUBSUB_EMULATOR_HOST": "localhost:8085"}
    )

def start_service(name: str, command: List[str], cwd: Path, env: Dict = None, port: int = None):
    """Start a service as a background process"""
    step_num = len(PROCESSES) + 1
    port_info = f" (port {port})" if port else ""
    print(f"\n{Colors.YELLOW}Step {step_num}: Starting {name}{port_info}...{Colors.NC}")

    # Prepare environment
    service_env = os.environ.copy()
    service_env["PUBSUB_EMULATOR_HOST"] = "localhost:8085"
    if env:
        service_env.update(env)

    # Open log file
    log_file = open(LOG_DIR / f"{name}.log", "w")

    # Start process
    proc = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=log_file,
        stderr=log_file,
        env=service_env
    )

    # Save PID
    (PID_DIR / f"{name}.pid").write_text(str(proc.pid))

    print(f"✓ {name} started (PID: {proc.pid})")

    PROCESSES[name] = proc
    return proc

def check_service_health(name: str, check_func, timeout: int = 10):
    """Check if a service is healthy"""
    for _ in range(timeout):
        try:
            if check_func():
                return True
        except:
            pass
        time.sleep(1)
    return False

def print_status(use_mock_broker: bool = False, use_live: bool = False):
    """Print final status of all services"""
    print("\n" + "=" * 70)
    print(f"{Colors.GREEN}✓ ALL SERVICES STARTED!{Colors.NC}")
    print("=" * 70)
    print("\nServices:")
    trading_mode = "Live" if use_live else "Paper"
    port = 4001 if use_live else 4002
    print(f"  • IB Gateway Docker: localhost:{port} ({trading_mode} Trading)")
    print("  • Pub/Sub Emulator: localhost:8085")
    print("  • AccountDataService: http://localhost:8082")
    print("  • PortfolioBuilderService: http://localhost:8003")
    print("  • DashboardCreatorService: http://localhost:8004")
    print("  • CerebroService: Background (consumes from Pub/Sub)")

    # Show mock mode indicator if enabled
    exec_status = "  • ExecutionService: Background (consumes from Pub/Sub)"
    if use_mock_broker:
        exec_status += f" {Colors.YELLOW}[MOCK MODE]{Colors.NC}"
    print(exec_status)

    print("  • SignalIngestionService: Monitoring staging.mathematricks.fund")
    print("  • Admin Frontend: http://localhost:5173")
    print("\nAdmin Dashboard:")
    print("  Open browser: http://localhost:5173")
    print("  Login: username=admin, password=admin")
    print("\nLogs:")
    print("  tail -f logs/signal_ingestion.log     # Signal collection")
    print("  tail -f logs/cerebro_service.log      # Position sizing decisions")
    print("  tail -f logs/execution_service.log    # Order execution")
    print("  tail -f logs/account_data_service.log # Account data")
    print("  tail -f logs/portfolio_builder.log    # Portfolio optimization")
    print("  tail -f logs/dashboard_creator.log    # Dashboard generation")
    print("\nManagement:")
    print("  python check_status_mvp_demo.py       # Check service status")
    print("  python stop_mvp_demo.py               # Stop all services")
    print("")

def main():
    """Main entry point"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Mathematricks MVP Demo - Start all services')
    parser.add_argument('--use-mock-broker', action='store_true',
                        help='Use Mock broker for all orders (testing mode, overrides strategy account routing)')
    parser.add_argument('--live', action='store_true',
                        help='Use live trading mode (default: paper trading)')
    args = parser.parse_args()

    print("=" * 70)
    print("MATHEMATRICKS MVP DEMO")
    print("=" * 70)

    # Show mock mode warning if enabled
    if args.use_mock_broker:
        print(f"{Colors.YELLOW}")
        print("=" * 70)
        print("🧪 MOCK MODE ENABLED: All orders will be routed to Mock_Paper broker")
        print("=" * 70)
        print(f"{Colors.NC}")

    # Show live trading warning if enabled
    if args.live:
        print(f"{Colors.RED}")
        print("=" * 70)
        print("⚠️  LIVE TRADING MODE: Real money will be used!")
        print("=" * 70)
        print(f"{Colors.NC}")

    print("")

    # Check prerequisites
    check_prerequisites()

    # Create log directory
    LOG_DIR.mkdir(exist_ok=True)
    PID_DIR.mkdir(exist_ok=True)

    try:
        # Start IB Gateway Docker
        start_ibkr_gateway(use_live=args.live)

        # Start Pub/Sub emulator
        start_pubsub_emulator()

        # Setup Pub/Sub topics
        setup_pubsub_topics()

        # Start services
        start_service(
            "account_data_service",
            [str(VENV_PYTHON), "account_data_main.py"],
            PROJECT_ROOT / "services" / "account_data_service",
            port=8082
        )
        time.sleep(2)

        start_service(
            "portfolio_builder",
            [str(VENV_PYTHON), "main.py"],
            PROJECT_ROOT / "services" / "portfolio_builder",
            port=8003
        )
        time.sleep(2)

        start_service(
            "dashboard_creator",
            [str(VENV_PYTHON), "dashboard_creator_main.py"],
            PROJECT_ROOT / "services" / "dashboard_creator",
            port=8004
        )
        time.sleep(2)

        start_service(
            "cerebro_service",
            [str(VENV_PYTHON), "cerebro_main.py"],
            PROJECT_ROOT / "services" / "cerebro_service",
            env={
                "ACCOUNT_DATA_SERVICE_URL": "http://localhost:8082",
                "USE_MOCK_BROKER": "true" if args.use_mock_broker else "false"
            }
        )
        time.sleep(2)

        # Start execution service (conditionally add mock broker flag)
        exec_command = [str(VENV_PYTHON), "execution_main.py"]
        if args.use_mock_broker:
            exec_command.append("--use-mock-broker")

        start_service(
            "execution_service",
            exec_command,
            PROJECT_ROOT / "services" / "execution_service"
        )
        time.sleep(2)

        start_service(
            "signal_ingestion",
            [str(VENV_PYTHON), "signal_ingestion_main.py", "--staging"],
            PROJECT_ROOT / "services" / "signal_ingestion"
        )
        time.sleep(2)

        # Start frontend
        print(f"\n{Colors.YELLOW}Step 9: Starting Admin Frontend (port 5173)...{Colors.NC}")
        frontend_dir = PROJECT_ROOT / "frontend-admin"

        # Check if node_modules exists
        if not (frontend_dir / "node_modules").exists():
            print("Installing frontend dependencies...")
            subprocess.run(["npm", "install"], cwd=frontend_dir)

        log_file = open(LOG_DIR / "frontend.log", "w")
        proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=frontend_dir,
            stdout=log_file,
            stderr=log_file
        )
        (PID_DIR / "frontend.pid").write_text(str(proc.pid))
        print(f"✓ Admin Frontend started (PID: {proc.pid})")
        PROCESSES["frontend"] = proc

        # Print status
        print_status(use_mock_broker=args.use_mock_broker, use_live=args.live)

        # Keep main process alive
        print(f"{Colors.YELLOW}Services running. Press Ctrl+C to stop all services.{Colors.NC}\n")

        # Monitor processes
        while True:
            time.sleep(5)
            # Check if any process died
            for name, proc in list(PROCESSES.items()):
                if proc.poll() is not None:
                    print(f"{Colors.RED}✗ {name} exited unexpectedly (exit code: {proc.returncode}){Colors.NC}")
                    print(f"  Check logs/{name}.log for details")

    except KeyboardInterrupt:
        cleanup_on_exit()
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.NC}")
        cleanup_on_exit()
        sys.exit(1)

if __name__ == "__main__":
    main()
