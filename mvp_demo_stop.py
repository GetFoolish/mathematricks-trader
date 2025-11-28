#!/usr/bin/env python3
"""
Stop all MVP services gracefully
"""
import os
import signal
import time
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).parent.absolute()
LOG_DIR = PROJECT_ROOT / "logs"
PID_DIR = LOG_DIR / "pids"

class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    NC = '\033[0m'

def read_pids(pid_file: Path) -> List[int]:
    """Read PIDs from a file"""
    if not pid_file.exists():
        return []

    try:
        content = pid_file.read_text().strip()
        return [int(pid) for pid in content.split('\n') if pid.strip()]
    except:
        return []

def is_process_running(pid: int) -> bool:
    """Check if a process is running"""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def stop_service(service_name: str, timeout: int = 10):
    """Stop a service by its PID file"""
    pid_file = PID_DIR / f"{service_name}.pid"
    pids = read_pids(pid_file)

    if not pids:
        return

    killed_count = 0
    for pid in pids:
        if not is_process_running(pid):
            continue

        try:
            # Try graceful shutdown first (SIGTERM)
            os.kill(pid, signal.SIGTERM)

            # Wait for process to exit
            for _ in range(timeout):
                if not is_process_running(pid):
                    killed_count += 1
                    break
                time.sleep(1)
            else:
                # Force kill if still running
                os.kill(pid, signal.SIGKILL)
                time.sleep(1)
                killed_count += 1
        except OSError:
            pass

    if killed_count > 0:
        print(f"✓ {service_name} stopped ({killed_count} process(es))")

    # Remove PID file
    if pid_file.exists():
        pid_file.unlink()

def kill_by_pattern(pattern: str, service_name: str):
    """Kill processes matching a pattern using pgrep"""
    import subprocess

    try:
        # Use pgrep to find processes
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True
        )

        if result.stdout:
            pids = [int(pid) for pid in result.stdout.strip().split('\n') if pid]
            if pids:
                print(f"✓ Killing orphaned {service_name} processes:")
                for pid in pids:
                    try:
                        print(f"  - PID {pid}")
                        os.kill(pid, signal.SIGKILL)
                    except OSError:
                        pass
    except:
        pass

def kill_port(port: int, service_name: str):
    """Kill process listening on a port"""
    import subprocess

    try:
        # Use lsof to find process on port
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True
        )

        if result.stdout:
            pids = [int(pid) for pid in result.stdout.strip().split('\n') if pid]
            if pids:
                print(f"✓ Killed process on port {port} ({service_name}): PIDs {pids}")
                for pid in pids:
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except OSError:
                        pass
    except:
        pass

def main():
    """Main entry point"""
    print("Stopping MVP services...")

    # Stop services in reverse order (via PID files)
    services = [
        "frontend",
        "signal_ingestion",
        "execution_service",
        "cerebro_service",
        "dashboard_creator",
        "portfolio_builder",
        "account_data_service",
        "pubsub"
    ]

    for service in services:
        stop_service(service)

    # Cleanup orphaned processes
    print("\nChecking for orphaned processes...")

    kill_by_pattern("signal_ingestion/main.py --staging", "signal_ingestion (staging)")
    kill_by_pattern("signal_ingestion/main.py", "signal_ingestion")
    kill_by_pattern("services/cerebro_service/main.py", "cerebro_service")
    kill_by_pattern("services/execution_service/main.py", "execution_service")
    kill_by_pattern("services/dashboard_creator/main.py", "dashboard_creator")
    kill_by_pattern("services/account_data_service/main.py", "account_data_service")
    kill_by_pattern("services/portfolio_builder/main.py", "portfolio_builder")

    # Kill processes on known ports
    print("\nCleaning up ports...")
    kill_port(8082, "account_data")
    kill_port(8003, "portfolio_builder")
    kill_port(8004, "dashboard_creator")
    kill_port(8085, "pubsub")
    kill_port(5173, "frontend")

    print(f"\n{Colors.GREEN}✓ All services stopped{Colors.NC}")

if __name__ == "__main__":
    main()
