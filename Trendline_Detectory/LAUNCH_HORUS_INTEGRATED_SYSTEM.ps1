# LAUNCH_HORUS_INTEGRATED_SYSTEM.ps1
# Launch Arsenal + Horus integrated system
# Enhanced with order flow intelligence for precision entries

Write-Host ''
Write-Host '====================================================================================================' -ForegroundColor Cyan
Write-Host '   ARSENAL + HORUS INTEGRATED SYSTEM' -ForegroundColor Cyan
Write-Host '====================================================================================================' -ForegroundColor Cyan
Write-Host ''
Write-Host 'ENHANCED FEATURES:' -ForegroundColor Green
Write-Host '  - CVD Order Flow Confirmation' -ForegroundColor White
Write-Host '  - Orderbook Imbalance Detection' -ForegroundColor White
Write-Host '  - Liquidity Wall Awareness' -ForegroundColor White
Write-Host '  - Precision Entry Timing' -ForegroundColor White
Write-Host '  - Tighter Stop Placement' -ForegroundColor White
Write-Host ''
Write-Host 'ALL PRESERVED FEATURES:' -ForegroundColor Yellow
Write-Host '  - 3m Candle Closure Exit (Heightened Security)' -ForegroundColor White
Write-Host '  - Breakeven Movement at 75% to TP1' -ForegroundColor White
Write-Host '  - Reversal Detection with Volume' -ForegroundColor White
Write-Host '  - Progressive Trailing Stops' -ForegroundColor White
Write-Host '  - No TP1 if No Impact Zone' -ForegroundColor White
Write-Host '  - All 11 Arsenal Detection Modules' -ForegroundColor White
Write-Host ''
Write-Host 'INITIALIZATION:' -ForegroundColor Yellow
Write-Host '  - Horus will take ~15 minutes to initialize (builds historical context)' -ForegroundColor White
Write-Host '  - This happens ONCE on startup' -ForegroundColor White
Write-Host '  - After initialization, system runs at full speed' -ForegroundColor White
Write-Host ''
Write-Host '====================================================================================================' -ForegroundColor Cyan
Write-Host ''

# Ask for mode
Write-Host 'Select mode:' -ForegroundColor Yellow
Write-Host '  1) MONITORING MODE (Safe - no real execution)' -ForegroundColor Green
Write-Host '  2) LIVE EXECUTION MODE (Real trades with real money)' -ForegroundColor Red
Write-Host ''

$mode = Read-Host 'Enter 1 or 2'

if ($mode -eq '2') {
    Write-Host ''
    Write-Host '====================================================================================================' -ForegroundColor Red -BackgroundColor Yellow
    Write-Host '   WARNING: LIVE EXECUTION MODE' -ForegroundColor Red -BackgroundColor Yellow
    Write-Host '====================================================================================================' -ForegroundColor Red -BackgroundColor Yellow
    Write-Host ''
    Write-Host 'This will execute REAL trades on Bybit with REAL money!' -ForegroundColor Red
    Write-Host ''
    Write-Host 'Configuration:' -ForegroundColor Yellow
    Write-Host '  - Symbol: SOLUSDT' -ForegroundColor White
    Write-Host '  - Position Size: 100 USD with 10x leverage' -ForegroundColor White
    Write-Host '  - Max Daily Drawdown: 20 USD' -ForegroundColor White
    Write-Host ''

    $confirmation = Read-Host 'Type CONFIRM to proceed with live execution'

    if ($confirmation -ne 'CONFIRM') {
        Write-Host ''
        Write-Host '[CANCELLED] Live execution not confirmed' -ForegroundColor Yellow
        Write-Host ''
        exit
    }

    Write-Host ''
    Write-Host '[CONFIRMED] Launching live execution system...' -ForegroundColor Green
    Write-Host ''

    $liveFlag = '--live'
} else {
    Write-Host ''
    Write-Host '[MONITORING MODE] No live execution - shows what it would do' -ForegroundColor Green
    Write-Host ''
    $liveFlag = ''
}

# Change directory
Set-Location 'G:\python files\precision9\Simulation Environment\Trendline_Detectory'

# Python path
$pythonPath = 'G:\python files\precision9\myenv_fixed\Scripts\python.exe'

# Run integrated system
if ($liveFlag) {
    & $pythonPath live_arsenal_horus_integrated.py $liveFlag
} else {
    & $pythonPath live_arsenal_horus_integrated.py
}
