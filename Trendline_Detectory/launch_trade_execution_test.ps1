# Launch Trade Execution System Test
# Complete test of arsenal + precision TP/SL + scenario planning + real-time monitoring

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "PRECISION9 - TRADE EXECUTION SYSTEM TEST" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This test demonstrates the complete trade execution flow:" -ForegroundColor Yellow
Write-Host "  1. Arsenal analyzes 11 dimensions of market structure" -ForegroundColor White
Write-Host "  2. Precision calculator finds optimal 2:1+ RR setups" -ForegroundColor White
Write-Host "  3. Scenario planner creates battle plan BEFORE entry" -ForegroundColor White
Write-Host "  4. Real-time monitor executes intelligently" -ForegroundColor White
Write-Host ""
Write-Host "Fixes all Horus failures:" -ForegroundColor Yellow
Write-Host "  - No closing on minor pullbacks (40% retracement required)" -ForegroundColor White
Write-Host "  - Market orders when needed (fixes \$206 TP miss)" -ForegroundColor White
Write-Host "  - Smart stop trailing (knows when to stop)" -ForegroundColor White
Write-Host "  - Reversal prediction before it happens" -ForegroundColor White
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Change to the correct directory
Set-Location "G:\python files\precision9\Simulation Environment\Trendline_Detectory"

# Use the correct Python interpreter from venv
$pythonPath = "G:\python files\precision9\myenv_fixed\Scripts\python.exe"

Write-Host "[LAUNCHING] Complete Trade Execution System Test..." -ForegroundColor Green
Write-Host "Python: $pythonPath" -ForegroundColor Gray
Write-Host ""

# Run the test
& $pythonPath test_trade_execution_system.py

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "TEST COMPLETE" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Review the detailed logs above to see:" -ForegroundColor Yellow
Write-Host "  - Arsenal's 11-module market analysis" -ForegroundColor White
Write-Host "  - Precision TP/SL calculation with reasoning" -ForegroundColor White
Write-Host "  - Scenario planning for all future events" -ForegroundColor White
Write-Host "  - Real-time monitoring and decision making" -ForegroundColor White
Write-Host ""
Write-Host "Ready for Bybit API integration!" -ForegroundColor Green
Write-Host ""
