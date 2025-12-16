# Mathematricks Trader - One-Command Setup Script (Windows PowerShell)
# Usage: .\setup.ps1 [-TestSignal]

param(
    [switch]$TestSignal
)

$ErrorActionPreference = "Stop"

# Color output functions
function Write-Success {
    param($Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Error-Message {
    param($Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Write-Warning-Message {
    param($Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Write-Info {
    param($Message)
    Write-Host "ℹ $Message" -ForegroundColor Cyan
}

function Write-Header {
    param($Message)
    Write-Host ""
    Write-Host "=========================================" -ForegroundColor Blue
    Write-Host "  $Message" -ForegroundColor Blue
    Write-Host "=========================================" -ForegroundColor Blue
    Write-Host ""
}

# Check if Docker is installed
function Test-DockerInstalled {
    try {
        $null = Get-Command docker -ErrorAction Stop
        Write-Success "Docker is installed"
        return $true
    }
    catch {
        Write-Error-Message "Docker is not installed"
        Write-Host "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop"
        exit 1
    }
}

# Check if Docker daemon is running
function Test-DockerRunning {
    try {
        $null = docker info 2>$null
        if ($LASTEXITCODE -ne 0) {
            throw "Docker daemon not running"
        }
        Write-Success "Docker daemon is running"
        return $true
    }
    catch {
        Write-Error-Message "Docker daemon is not running"
        Write-Host "Please start Docker Desktop and try again"
        exit 1
    }
}

# Check docker-compose availability
function Test-DockerCompose {
    $script:ComposeCmd = $null

    # Try modern CLI first
    try {
        $null = docker compose version 2>$null
        if ($LASTEXITCODE -eq 0) {
            $script:ComposeCmd = "docker", "compose"
            Write-Success "Docker Compose is available (modern CLI)"
            return $true
        }
    }
    catch {}

    # Try legacy CLI
    try {
        $null = docker-compose --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            $script:ComposeCmd = "docker-compose"
            Write-Success "Docker Compose is available (legacy CLI)"
            return $true
        }
    }
    catch {}

    Write-Error-Message "Docker Compose is not available"
    Write-Host "Please install Docker Desktop which includes Docker Compose"
    exit 1
}

# Check if .env file exists
function Test-EnvFile {
    if (-not (Test-Path ".env")) {
        Write-Error-Message ".env file not found"
        Write-Host ""
        Write-Host "Please create a .env file from the template:"
        Write-Host "  Copy-Item .env.sample .env"
        Write-Host ""
        Write-Host "Then edit .env with your credentials"
        exit 1
    }
    Write-Success ".env file found"
}

# Build Docker containers
function Build-Containers {
    Write-Info "Building Docker containers (this may take a few minutes)..."

    .\make.bat rebuild

    if ($LASTEXITCODE -ne 0) {
        Write-Error-Message "Failed to build containers"
        Write-Host "Check the error messages above for details"
        exit 1
    }
    Write-Success "Containers built successfully"
}

# Start all services
function Start-Services {
    Write-Info "Starting all services..."

    .\make.bat start

    if ($LASTEXITCODE -ne 0) {
        Write-Error-Message "Failed to start services"
        Write-Host "Run 'make logs' to check for errors"
        exit 1
    }
    Write-Success "All services started"
}

# Wait for MongoDB replica set
function Wait-ForMongoDB {
    Write-Info "Waiting for MongoDB replica set (max 60 seconds)..."
    $maxAttempts = 30
    $attempt = 1

    while ($attempt -le $maxAttempts) {
        try {
            $result = if ($script:ComposeCmd -is [array]) {
                & $script:ComposeCmd[0] $script:ComposeCmd[1] exec -T mongodb mongosh --quiet --eval "rs.status().ok" 2>$null
            }
            else {
                & $script:ComposeCmd exec -T mongodb mongosh --quiet --eval "rs.status().ok" 2>$null
            }

            if ($result -match "1") {
                Write-Success "MongoDB replica set is ready"
                return $true
            }
        }
        catch {}

        if ($attempt % 5 -eq 0) {
            Write-Host "  Still waiting... (attempt $attempt/$maxAttempts)"
        }

        Start-Sleep -Seconds 2
        $attempt++
    }

    Write-Error-Message "MongoDB did not become ready in time"
    Write-Host "Check MongoDB logs with: make logs-cerebro"
    return $false
}

# Wait for PubSub emulator
function Wait-ForPubSub {
    Write-Info "Waiting for PubSub emulator (max 60 seconds)..."
    $maxAttempts = 30
    $attempt = 1

    while ($attempt -le $maxAttempts) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8085/" -TimeoutSec 1 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                Write-Success "PubSub emulator is ready"
                return $true
            }
        }
        catch {}

        if ($attempt % 5 -eq 0) {
            Write-Host "  Still waiting... (attempt $attempt/$maxAttempts)"
        }

        Start-Sleep -Seconds 2
        $attempt++
    }

    Write-Error-Message "PubSub emulator did not start in time"
    Write-Host "Check logs with: make logs"
    return $false
}

# Verify MongoDB seed data
function Test-SeedData {
    Write-Info "Verifying MongoDB seed data..."

    try {
        $collectionCount = if ($script:ComposeCmd -is [array]) {
            & $script:ComposeCmd[0] $script:ComposeCmd[1] exec -T mongodb mongosh --quiet --eval "db.getSiblingDB('mathematricks_trading').getCollectionNames().length" 2>$null | Select-Object -Last 1
        }
        else {
            & $script:ComposeCmd exec -T mongodb mongosh --quiet --eval "db.getSiblingDB('mathematricks_trading').getCollectionNames().length" 2>$null | Select-Object -Last 1
        }

        $count = [int]$collectionCount.Trim()

        if ($count -ge 9) {
            Write-Success "Seed data loaded successfully ($count collections)"
            return $true
        }
        else {
            Write-Warning-Message "Expected 9 collections, found $count"
            Write-Host "Seed data may not be fully loaded"
            return $false
        }
    }
    catch {
        Write-Warning-Message "Could not verify seed data"
        return $false
    }
}

# Wait for application services
function Wait-ForServices {
    Write-Info "Waiting for application services to start (10 seconds)..."
    Start-Sleep -Seconds 10

    try {
        $logs = if ($script:ComposeCmd -is [array]) {
            & $script:ComposeCmd[0] $script:ComposeCmd[1] logs --tail=50 2>&1
        }
        else {
            & $script:ComposeCmd logs --tail=50 2>&1
        }

        if ($logs -match "error.*failed to start|fatal|crashed") {
            Write-Warning-Message "Some services may have errors"
            Write-Host "Check logs with: make logs"
        }
        else {
            Write-Success "Application services started successfully"
        }
    }
    catch {
        Write-Warning-Message "Could not check service logs"
    }
}

# Send test signal
function Send-TestSignal {
    Write-Header "SENDING TEST SIGNAL"

    Write-Info "This will send a test ENTRY+EXIT signal pair for AAPL"
    Write-Info "Watch the logs to see signal propagation through services"
    Write-Host ""

    # Check if Python is available
    $pythonPath = ".\venv\Scripts\python.exe"
    if (-not (Test-Path $pythonPath)) {
        $pythonPath = "python"
        try {
            $null = Get-Command python -ErrorAction Stop
        }
        catch {
            Write-Error-Message "Python is required to send test signals"
            Write-Host "Please install Python 3.11+ and try again"
            return
        }
    }

    # Install required Python packages
    Write-Info "Installing Python dependencies..."
    & $pythonPath -m pip install -q pymongo python-dotenv 2>&1 | Out-Null

    # Send signal
    Write-Info "Sending test signal..."
    Write-Host ""

    & $pythonPath tests\signals_testing\send_test_signal.py --file tests\signals_testing\sample_signals\equity_simple_signal_1.json

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Success "Test signal sent successfully"
    }
    else {
        Write-Error-Message "Failed to send test signal"
        return
    }

    Write-Host ""
    Write-Info "Watching for signal flow in logs..."
    Write-Info "You should see: signal-ingestion → cerebro-service → execution-service"
    Write-Info "Press Ctrl+C to stop watching logs"
    Write-Host ""
    Start-Sleep -Seconds 3

    # Display filtered logs
    if ($script:ComposeCmd -is [array]) {
        & $script:ComposeCmd[0] $script:ComposeCmd[1] logs -f --tail=100 2>&1 | Select-String -Pattern "signal-ingestion|cerebro-service|execution-service" | Select-String -Pattern "signal|ENTRY|EXIT|AAPL|Processing|Order"
    }
    else {
        & $script:ComposeCmd logs -f --tail=100 2>&1 | Select-String -Pattern "signal-ingestion|cerebro-service|execution-service" | Select-String -Pattern "signal|ENTRY|EXIT|AAPL|Processing|Order"
    }
}

# Print summary
function Show-Summary {
    Write-Header "✓ SETUP COMPLETE!"

    Write-Host "Access points:"
    Write-Host "  Frontend Dashboard:  http://localhost:5173"
    Write-Host "                      (username: admin, password: admin)"
    Write-Host "  MongoDB:            mongodb://localhost:27018"
    Write-Host "  PubSub Emulator:    http://localhost:8085"
    Write-Host "  Portfolio Builder:  http://localhost:8003"
    Write-Host "  Dashboard Creator:  http://localhost:8004"
    Write-Host ""
    Write-Host "Useful commands:"
    Write-Host "  make status         - Check service status"
    Write-Host "  make logs           - View all logs (streaming)"
    Write-Host "  make logs-cerebro   - View cerebro service logs"
    Write-Host "  make stop           - Stop all services"
    Write-Host "  make restart        - Restart all services"
    Write-Host ""
    Write-Host "Send test signal:"
    Write-Host "  python tests\signals_testing\send_test_signal.py \"
    Write-Host "    --file tests\signals_testing\sample_signals\equity_simple_signal_1.json"
    Write-Host ""
    Write-Host "Documentation:"
    Write-Host "  SETUP.md           - Detailed setup guide"
    Write-Host "  TESTING.md         - Testing procedures"
    Write-Host ""
}

# Main execution
try {
    Write-Header "Mathematricks Trader Setup"

    # Prerequisite checks
    Test-DockerInstalled
    Test-DockerRunning
    Test-DockerCompose
    Test-EnvFile

    Write-Host ""

    # Build and start
    Build-Containers
    Write-Host ""
    Start-Services

    Write-Host ""

    # Health checks
    Wait-ForMongoDB
    Wait-ForPubSub
    Wait-ForServices

    Write-Host ""

    # Verify data
    Test-SeedData

    Write-Host ""

    # Print summary
    Show-Summary

    # Optional: Send test signal
    if ($TestSignal) {
        Send-TestSignal
    }
}
catch {
    Write-Error-Message "Setup failed: $_"
    exit 1
}
