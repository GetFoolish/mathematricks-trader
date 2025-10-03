#!/usr/bin/env python3
"""
Mathematricks Trader V1 - Unified Launcher
Starts all components: trading system, signal collector, and dashboard
"""

import subprocess
import sys
import time
import signal
import os
from pathlib import Path


class Colors:
    """ANSI color codes for terminal output"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'


class MathematricksLauncher:
    """Launch and manage all Mathematricks Trader components"""

    def __init__(self):
        self.processes = {}
        self.running = True

    def print_header(self):
        """Print startup header"""
        print(f"\n{Colors.BOLD}{Colors.CYAN}🚀 Starting Mathematricks Trader V1{Colors.RESET}")
        print(f"{Colors.CYAN}{'━' * 60}{Colors.RESET}\n")

    def check_dependencies(self):
        """Check if required files exist"""
        required_files = [
            'main.py',
            'signal_collector.py',
            'frontend/app.py',
            'requirements.txt'
        ]

        missing = []
        for file in required_files:
            if not Path(file).exists():
                missing.append(file)

        if missing:
            print(f"{Colors.RED}❌ Missing required files:{Colors.RESET}")
            for file in missing:
                print(f"   - {file}")
            print(f"\n{Colors.YELLOW}Please ensure you're in the project root directory{Colors.RESET}")
            return False

        return True

    def start_process(self, name, command, color):
        """Start a subprocess"""
        print(f"{color}[{name}] Starting...{Colors.RESET}", end='', flush=True)

        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            self.processes[name] = {
                'process': process,
                'color': color,
                'command': ' '.join(command)
            }

            # Give it a moment to fail if there's an immediate error
            time.sleep(0.5)

            if process.poll() is None:
                print(f"\r{color}[{name}] Starting...{Colors.GREEN} ✅{Colors.RESET}")
                return True
            else:
                print(f"\r{color}[{name}] Starting...{Colors.RED} ❌{Colors.RESET}")
                stderr = process.stderr.read()
                print(f"{Colors.RED}Error: {stderr}{Colors.RESET}")
                return False

        except Exception as e:
            print(f"\r{color}[{name}] Starting...{Colors.RED} ❌{Colors.RESET}")
            print(f"{Colors.RED}Error: {e}{Colors.RESET}")
            return False

    def wait_for_streamlit(self, max_wait=10):
        """Wait for Streamlit to start and return the URL"""
        streamlit_proc = self.processes.get('Dashboard', {}).get('process')
        if not streamlit_proc:
            return None

        print(f"\n{Colors.YELLOW}⏳ Waiting for dashboard to start...{Colors.RESET}", end='', flush=True)

        start_time = time.time()
        url = None

        while time.time() - start_time < max_wait:
            # Check if process is still running
            if streamlit_proc.poll() is not None:
                print(f"\r{Colors.RED}❌ Dashboard failed to start{Colors.RESET}")
                return None

            # Try to read output
            try:
                line = streamlit_proc.stderr.readline()
                if 'Local URL:' in line or 'Network URL:' in line:
                    # Extract URL
                    url = line.split(':', 1)[1].strip()
                    if url.startswith('http'):
                        print(f"\r{Colors.GREEN}✅ Dashboard started successfully{Colors.RESET}")
                        return url
            except:
                pass

            time.sleep(0.1)

        print(f"\r{Colors.YELLOW}⚠️  Dashboard starting (URL not detected yet){Colors.RESET}")
        return "http://localhost:8501"  # Default Streamlit URL

    def print_status(self, dashboard_url):
        """Print status of all components"""
        print(f"\n{Colors.CYAN}{'━' * 60}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.GREEN}✅ All components running{Colors.RESET}")
        print(f"{Colors.CYAN}{'━' * 60}{Colors.RESET}\n")

        if dashboard_url:
            print(f"{Colors.BOLD}📊 Dashboard URL:{Colors.RESET} {Colors.CYAN}{dashboard_url}{Colors.RESET}")
        else:
            print(f"{Colors.YELLOW}📊 Dashboard URL: http://localhost:8501 (default){Colors.RESET}")

        print(f"\n{Colors.BOLD}Running Components:{Colors.RESET}")
        for name, info in self.processes.items():
            color = info['color']
            status = "🟢 Running" if info['process'].poll() is None else "🔴 Stopped"
            print(f"  {color}{name}:{Colors.RESET} {status}")

        print(f"\n{Colors.YELLOW}Press Ctrl+C to stop all processes{Colors.RESET}\n")
        print(f"{Colors.CYAN}{'━' * 60}{Colors.RESET}\n")

    def monitor_processes(self):
        """Monitor running processes and show their output"""
        try:
            while self.running:
                for name, info in self.processes.items():
                    process = info['process']
                    color = info['color']

                    # Check if process is still running
                    if process.poll() is not None:
                        print(f"{Colors.RED}❌ {name} stopped unexpectedly{Colors.RESET}")
                        self.running = False
                        break

                    # Read and display stdout (non-blocking)
                    try:
                        import select
                        if hasattr(select, 'select'):
                            # Unix-like systems
                            if process.stdout in select.select([process.stdout], [], [], 0)[0]:
                                line = process.stdout.readline()
                                if line:
                                    print(f"{color}[{name}]{Colors.RESET} {line.strip()}")
                    except:
                        # Windows or reading error
                        pass

                time.sleep(0.1)

        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}🛑 Shutting down...{Colors.RESET}\n")
            self.running = False

    def shutdown(self):
        """Gracefully shutdown all processes"""
        for name, info in self.processes.items():
            process = info['process']
            color = info['color']

            print(f"{color}Stopping {name}...{Colors.RESET}", end='', flush=True)

            try:
                # Send SIGTERM (graceful shutdown)
                process.terminate()

                # Wait up to 5 seconds for graceful shutdown
                try:
                    process.wait(timeout=5)
                    print(f" {Colors.GREEN}✅{Colors.RESET}")
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't respond
                    process.kill()
                    process.wait()
                    print(f" {Colors.YELLOW}⚠️  (forced){Colors.RESET}")

            except Exception as e:
                print(f" {Colors.RED}❌ {e}{Colors.RESET}")

        print(f"\n{Colors.GREEN}✅ All processes stopped{Colors.RESET}\n")

    def run(self):
        """Main run method"""
        self.print_header()

        # Check dependencies
        if not self.check_dependencies():
            sys.exit(1)

        # Start components in order
        components = [
            ("Trading System", ["python3", "main.py"], Colors.BLUE),
            ("Signal Collector", ["python3", "signal_collector.py"], Colors.MAGENTA),
            ("Dashboard", ["streamlit", "run", "frontend/app.py"], Colors.GREEN)
        ]

        success = True
        for i, (name, command, color) in enumerate(components, 1):
            print(f"{Colors.BOLD}[{i}/{len(components)}]{Colors.RESET} ", end='')
            if not self.start_process(name, command, color):
                success = False
                break
            time.sleep(1)  # Small delay between starts

        if not success:
            print(f"\n{Colors.RED}❌ Failed to start all components{Colors.RESET}")
            self.shutdown()
            sys.exit(1)

        # Wait for Streamlit to be ready
        dashboard_url = self.wait_for_streamlit()

        # Print status
        self.print_status(dashboard_url)

        # Monitor processes
        self.monitor_processes()

        # Shutdown on exit
        self.shutdown()


def main():
    """Entry point"""
    launcher = MathematricksLauncher()
    launcher.run()


if __name__ == "__main__":
    main()
