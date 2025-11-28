#!/usr/bin/env python3
"""
Check status of all Mathematricks Trader services
"""
import os
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

PROJECT_ROOT = Path(__file__).parent.absolute()
LOG_DIR = PROJECT_ROOT / "logs"
PID_DIR = LOG_DIR / "pids"

class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    NC = '\033[0m'

def is_process_running(pid: int) -> bool:
    """Check if a process is running"""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def get_process_info(pid: int) -> Tuple[Optional[str], Optional[float]]:
    """Get process uptime and memory usage"""
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "etime=,rss="],
            capture_output=True,
            text=True
        )
        if result.stdout:
            parts = result.stdout.strip().split()
            uptime = parts[0] if len(parts) > 0 else None
            memory_kb = float(parts[1]) if len(parts) > 1 else None
            memory_mb = memory_kb / 1024 if memory_kb else None
            return uptime, memory_mb
    except:
        pass
    return None, None

def is_port_listening(port: int) -> bool:
    """Check if a port is listening"""
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{port}"],
            capture_output=True,
            text=True
        )
        return "LISTEN" in result.stdout
    except:
        return False

def find_process_by_pattern(pattern: str) -> Optional[int]:
    """Find process PID by pattern"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True
        )
        if result.stdout:
            return int(result.stdout.strip().split('\n')[0])
    except:
        pass
    return None

def check_service(service_name: str, search_pattern: str, port: Optional[int] = None, display_name: str = None):
    """Check status of a service"""
    # Use display_name if provided, otherwise format service_name nicely
    if not display_name:
        display_name = service_name.replace('_', ' ').title()

    print(f"📋 {display_name}")

    # Check PID file first
    pid_file = PID_DIR / f"{service_name}.pid"
    pid = None

    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            if not is_process_running(pid):
                pid = None
        except:
            pid = None

    # If no PID from file, search by pattern (fallback)
    if not pid:
        pid = find_process_by_pattern(search_pattern)

    # Check process status
    if pid:
        uptime, memory = get_process_info(pid)
        print(f"   Process: {Colors.GREEN}✅ Running{Colors.NC} (PID: {pid})")
        if uptime:
            print(f"   Uptime: {uptime}")
        if memory:
            print(f"   Memory: {memory:.1f} MB")
    else:
        print(f"   Process: {Colors.RED}❌ Not running{Colors.NC}")

    # Check port if specified
    if port:
        if is_port_listening(port):
            print(f"   Port {port}: {Colors.GREEN}✅ Listening{Colors.NC}")
        else:
            print(f"   Port {port}: {Colors.RED}❌ Not listening{Colors.NC}")

    print("")
    return pid is not None

def check_mongodb():
    """Check MongoDB status"""
    print("📋 MongoDB (Local Replica Set)")

    # Check mongod process
    pid = find_process_by_pattern("mongod")
    if pid:
        print(f"   Process: {Colors.GREEN}✅ Running{Colors.NC} (PID: {pid})")

        # Check replica set status
        try:
            result = subprocess.run(
                ["mongosh", "--quiet", "--eval", "rs.status().ok"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if "1" in result.stdout:
                # Get replica set name
                result = subprocess.run(
                    ["mongosh", "--quiet", "--eval", "rs.status().set"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                replica_set = result.stdout.strip().strip('"')
                print(f"   Replica Set: {Colors.GREEN}✅ {replica_set}{Colors.NC}")
            else:
                print(f"   Replica Set: {Colors.YELLOW}⚠️  Not initialized{Colors.NC}")
        except:
            print(f"   Replica Set: {Colors.YELLOW}⚠️  Cannot check{Colors.NC}")
    else:
        print(f"   Process: {Colors.RED}❌ Not running{Colors.NC}")

    print("")

def check_tws():
    """Check IBKR TWS/Gateway status"""
    print("📋 IBKR TWS/Gateway")
    if is_port_listening(7497):
        print(f"   Port 7497: {Colors.GREEN}✅ Listening{Colors.NC}")
    else:
        print(f"   Port 7497: {Colors.RED}❌ Not listening{Colors.NC}")
        print("   (Start TWS or IB Gateway on port 7497)")
    print("")

def check_pubsub():
    """Check Pub/Sub emulator status"""
    print("📋 Pub/Sub Emulator (Optional)")
    if is_port_listening(8085):
        print(f"   Port 8085: {Colors.GREEN}✅ Running{Colors.NC}")
    else:
        print(f"   Port 8085: {Colors.YELLOW}⚠️  Not running{Colors.NC} (optional for local dev)")
    print("")

def show_recent_logs():
    """Show last 5 lines of each service log"""
    print("\n4️⃣  SERVICE LOGS (Last 5 lines each)")
    print("=" * 80)

    services = [
        "signal_ingestion",
        "cerebro_service",
        "account_data_service",
        "execution_service",
        "portfolio_builder",
        "dashboard_creator"
    ]

    for service in services:
        log_file = LOG_DIR / f"{service}.log"
        if log_file.exists():
            print(f"\n📄 logs/{service}.log (last 5 lines):")
            try:
                result = subprocess.run(
                    ["tail", "-5", str(log_file)],
                    capture_output=True,
                    text=True
                )
                for line in result.stdout.split('\n'):
                    if line:
                        print(f"   {line}")
            except:
                print("   (Unable to read log)")

def main():
    """Main entry point"""
    print("=" * 80)
    print("Mathematricks Trader - Service Status Check")
    print("=" * 80)
    print("")

    # Check core services
    print("1️⃣  CORE SERVICES")
    print("=" * 80)

    services_status = []
    services_status.append(check_service(
        "signal_ingestion",
        "python.*signal_ingestion/main.py"
    ))
    services_status.append(check_service(
        "cerebro_service",
        "python.*cerebro_service/main.py"
    ))
    services_status.append(check_service(
        "account_data_service",
        "python.*account_data_service/main.py",
        port=8082
    ))
    services_status.append(check_service(
        "execution_service",
        "python.*execution_service/main.py"
    ))

    # Check support services
    print("\n2️⃣  SUPPORT SERVICES")
    print("=" * 80)
    services_status.append(check_service(
        "portfolio_builder",
        "python.*portfolio_builder/main.py",
        port=8003
    ))
    services_status.append(check_service(
        "dashboard_creator",
        "python.*dashboard_creator/main.py",
        port=8004
    ))

    # Check infrastructure
    print("\n3️⃣  INFRASTRUCTURE")
    print("=" * 80)
    check_mongodb()
    check_tws()
    check_pubsub()

    # Show recent logs
    show_recent_logs()

    # Summary
    print("\n")
    print("=" * 80)
    print("Summary")
    print("=" * 80)

    running = sum(services_status)
    total = len(services_status)

    print(f"Services: {running}/{total} running")

    if running == total:
        print(f"Status: {Colors.GREEN}✅ All services running{Colors.NC}")
    elif running > 0:
        print(f"Status: {Colors.YELLOW}⚠️  Some services down{Colors.NC}")
    else:
        print(f"Status: {Colors.RED}❌ No services running{Colors.NC}")

    print("")
    print("Tip: To restart a specific service, check logs/ folder for error details")
    print("=" * 80)
    print("")

if __name__ == "__main__":
    main()
