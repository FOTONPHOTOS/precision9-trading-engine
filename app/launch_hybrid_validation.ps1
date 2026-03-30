# Precision9 Hybrid Validation Test Launcher
# Runs Arsenal + Horus systems simultaneously for complementary validation

Write-Host "`n" -NoNewline
Write-Host "="*100 -ForegroundColor Cyan
Write-Host " PRECISION9 HYBRID VALIDATION TEST" -ForegroundColor Cyan
Write-Host "="*100 -ForegroundColor Cyan
Write-Host ""

# Paths
$PYTHON_EXE = "G:\python files\precision9\myenv_fixed\Scripts\python.exe"
$WORKING_DIR = "G:\python files\precision9\Simulation Environment\Trendline_Detectory"
$SPECTRA_DIR = "G:\python files\precision9\Simulation Environment\spectra_integrator_trading_test"

Write-Host "[1/4] Checking prerequisites..." -ForegroundColor Yellow
Write-Host ""

# Check Python executable
if (!(Test-Path $PYTHON_EXE)) {
    Write-Host "ERROR: Python executable not found at:" -ForegroundColor Red
    Write-Host "  $PYTHON_EXE" -ForegroundColor Red
    Write-Host ""
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

Write-Host "  Python: OK" -ForegroundColor Green

# Check if Horus Unified Processor is running
Write-Host ""
Write-Host "[2/4] Checking if Horus Unified Processor is running..." -ForegroundColor Yellow

$horusRunning = $false
$horusPort = 8899

try {
    $connection = Test-NetConnection -ComputerName "localhost" -Port $horusPort -InformationLevel Quiet -WarningAction SilentlyContinue
    if ($connection) {
        $horusRunning = $true
        Write-Host "  Horus Unified Processor: RUNNING on port $horusPort" -ForegroundColor Green
    }
} catch {
    # Port not open
}

if (!$horusRunning) {
    Write-Host "  Horus Unified Processor: NOT RUNNING" -ForegroundColor Red
    Write-Host ""
    Write-Host "Starting Horus Unified Processor..." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Run this command in a separate terminal:" -ForegroundColor Cyan
    Write-Host "  cd `"$SPECTRA_DIR`"" -ForegroundColor White
    Write-Host "  & `"$PYTHON_EXE`" horus_dashboard_backend.py" -ForegroundColor White
    Write-Host ""
    Write-Host "Then press any key to continue..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

    # Check again
    try {
        $connection = Test-NetConnection -ComputerName "localhost" -Port $horusPort -InformationLevel Quiet -WarningAction SilentlyContinue
        if (!$connection) {
            Write-Host ""
            Write-Host "ERROR: Horus still not running. Please start it manually." -ForegroundColor Red
            Write-Host "Press any key to exit..."
            $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
            exit 1
        }
    } catch {
        Write-Host ""
        Write-Host "ERROR: Could not verify Horus is running." -ForegroundColor Red
        Write-Host "Press any key to exit..."
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        exit 1
    }
}

Write-Host ""
Write-Host "[3/4] Starting Horus Data Collector..." -ForegroundColor Yellow
Write-Host ""

# Start Horus collector in background
$horusCollector = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$WORKING_DIR'; & '$PYTHON_EXE' horus_data_collector.py" -PassThru -WindowStyle Normal

Write-Host "  Horus Collector: STARTED (PID: $($horusCollector.Id))" -ForegroundColor Green

Write-Host ""
Write-Host "[4/4] Starting Hybrid Validator..." -ForegroundColor Yellow
Write-Host ""
Write-Host "The validator will:" -ForegroundColor Cyan
Write-Host "  1. Collect data from Horus Unified Processor" -ForegroundColor White
Write-Host "  2. Wait for Arsenal snapshot (you'll need to provide this)" -ForegroundColor White
Write-Host "  3. Perform side-by-side complementary analysis" -ForegroundColor White
Write-Host "  4. Generate validation report" -ForegroundColor White
Write-Host ""

# Give Horus collector time to connect
Write-Host "Waiting 5 seconds for Horus collector to initialize..."
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "="*100 -ForegroundColor Cyan
Write-Host " LAUNCHING HYBRID VALIDATOR" -ForegroundColor Cyan
Write-Host "="*100 -ForegroundColor Cyan
Write-Host ""

# Run validator in this window
cd $WORKING_DIR
& $PYTHON_EXE hybrid_validator.py

Write-Host ""
Write-Host "="*100 -ForegroundColor Cyan
Write-Host " HYBRID VALIDATION TEST COMPLETE" -ForegroundColor Cyan
Write-Host "="*100 -ForegroundColor Cyan
Write-Host ""
Write-Host "Check the generated JSON files for collected data." -ForegroundColor Green
Write-Host ""
Write-Host "Press any key to cleanup and exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

# Cleanup: Stop Horus collector
if (!$horusCollector.HasExited) {
    Write-Host ""
    Write-Host "Stopping Horus Collector (PID: $($horusCollector.Id))..." -ForegroundColor Yellow
    Stop-Process -Id $horusCollector.Id -Force -ErrorAction SilentlyContinue
    Write-Host "  Stopped" -ForegroundColor Green
}

Write-Host ""
Write-Host "Done!" -ForegroundColor Green
Write-Host ""
