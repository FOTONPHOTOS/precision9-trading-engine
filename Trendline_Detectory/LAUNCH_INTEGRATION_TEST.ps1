# LAUNCH_INTEGRATION_TEST.ps1
# Test Arsenal + Horus integration to verify all features work

Write-Host ""
Write-Host "====================================================================================================" -ForegroundColor Cyan
Write-Host "   ARSENAL + HORUS INTEGRATION TEST SUITE" -ForegroundColor Cyan
Write-Host "====================================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This test suite will verify:" -ForegroundColor Yellow
Write-Host "  1. Horus initialization (~15 minutes)" -ForegroundColor White
Write-Host "  2. CVD, Liquidity, and Orderbook collectors" -ForegroundColor White
Write-Host "  3. Entry confirmation system" -ForegroundColor White
Write-Host "  4. Stop placement optimization" -ForegroundColor White
Write-Host "  5. Market intelligence quality" -ForegroundColor White
Write-Host ""
Write-Host "PRESERVED FEATURES VERIFICATION:" -ForegroundColor Yellow
Write-Host "  - 3m Candle Closure Exit (Heightened Security)" -ForegroundColor White
Write-Host "  - Breakeven Movement at 75% to TP1" -ForegroundColor White
Write-Host "  - Reversal Detection with Volume" -ForegroundColor White
Write-Host "  - Progressive Trailing Stops" -ForegroundColor White
Write-Host "  - No TP1 if No Impact Zone" -ForegroundColor White
Write-Host "  - All 11 Arsenal Detection Modules" -ForegroundColor White
Write-Host ""
Write-Host "====================================================================================================" -ForegroundColor Cyan
Write-Host ""

$confirmation = Read-Host "Press ENTER to start test (or Ctrl+C to cancel)"

Write-Host ""
Write-Host "[INFO] Starting integration test..." -ForegroundColor Green
Write-Host ""

# Change directory
Set-Location 'G:\python files\precision9\Simulation Environment\Trendline_Detectory'

# Python path
$pythonPath = 'G:\python files\precision9\myenv_fixed\Scripts\python.exe'

# Run test
& $pythonPath test_arsenal_horus_integration.py
