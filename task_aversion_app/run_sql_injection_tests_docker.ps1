# PowerShell script to run SQL injection tests with Docker PostgreSQL
# This uses port 5433 to avoid conflicts with local PostgreSQL on port 5432

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "SQL Injection Test Setup (Docker)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Remove existing container if it exists
Write-Host "[1/4] Checking for existing postgres-test container..." -ForegroundColor Yellow
$existing = docker ps -a --filter "name=postgres-test" --format "{{.Names}}"
if ($existing -eq "postgres-test") {
    Write-Host "  Found existing container, removing..." -ForegroundColor Yellow
    docker stop postgres-test 2>$null
    docker rm postgres-test 2>$null
    Write-Host "  [OK] Removed existing container" -ForegroundColor Green
} else {
    Write-Host "  [OK] No existing container found" -ForegroundColor Green
}

# Step 2: Create new container on port 5433
Write-Host ""
Write-Host "[2/4] Creating PostgreSQL container on port 5433..." -ForegroundColor Yellow
docker run --name postgres-test `
  -e POSTGRES_PASSWORD=testpass `
  -e POSTGRES_DB=test_task_aversion `
  -p 5433:5432 `
  -d postgres:15

if ($LASTEXITCODE -eq 0) {
    Write-Host "  [OK] Container created successfully" -ForegroundColor Green
    Write-Host "  Waiting 3 seconds for PostgreSQL to start..." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
} else {
    Write-Host "  [ERROR] Failed to create container" -ForegroundColor Red
    exit 1
}

# Step 3: Verify container is running
Write-Host ""
Write-Host "[3/4] Verifying container is running..." -ForegroundColor Yellow
$running = docker ps --filter "name=postgres-test" --format "{{.Names}}"
if ($running -eq "postgres-test") {
    Write-Host "  [OK] Container is running" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] Container is not running" -ForegroundColor Red
    exit 1
}

# Step 4: Set DATABASE_URL and run tests
Write-Host ""
Write-Host "[4/4] Setting DATABASE_URL and running tests..." -ForegroundColor Yellow
$env:DATABASE_URL = "postgresql://postgres:testpass@localhost:5433/test_task_aversion"
Write-Host "  DATABASE_URL = $env:DATABASE_URL" -ForegroundColor Cyan
Write-Host ""

# Change to app directory
Set-Location $PSScriptRoot

# Run the tests
Write-Host "Running SQL injection tests..." -ForegroundColor Cyan
Write-Host ""
python tests/test_sql_injection.py

$testExitCode = $LASTEXITCODE

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Test Complete" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To stop and remove the container, run:" -ForegroundColor Yellow
Write-Host "  docker stop postgres-test" -ForegroundColor White
Write-Host "  docker rm postgres-test" -ForegroundColor White
Write-Host ""

exit $testExitCode
