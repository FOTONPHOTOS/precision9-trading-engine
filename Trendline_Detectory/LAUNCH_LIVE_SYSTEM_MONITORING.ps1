# LAUNCH_LIVE_SYSTEM_MONITORING.ps1
# Launch the Arsenal system in MONITORING MODE
# Shows what it would do without executing real trades

Write-Host ""
Write-Host "====================================================================================================" -ForegroundColor Cyan
Write-Host "   ARSENAL LIVE SYSTEM - MONITORING MODE" -ForegroundColor Cyan
Write-Host "====================================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This mode:" -ForegroundColor Yellow
Write-Host "  - Analyzes market every 60 seconds" -ForegroundColor White
Write-Host "  - Shows complete arsenal analysis (11 modules)" -ForegroundColor White
Write-Host "  - Displays trade setups when found" -ForegroundColor White
Write-Host "  - Does NOT execute real trades" -ForegroundColor Green
Write-Host ""
Write-Host "To enable LIVE TRADING, use: .\LAUNCH_LIVE_SYSTEM_EXECUTION.ps1" -ForegroundColor Yellow
Write-Host ""
Write-Host "====================================================================================================" -ForegroundColor Cyan
Write-Host ""

# Change to the correct directory
Set-Location "G:\python files\precision9\Simulation Environment\Trendline_Detectory"

# Use the correct Python interpreter from venv
$pythonPath = "G:\python files\precision9\myenv_fixed\Scripts\python.exe"

# Run the live system in monitoring mode (default)
& $pythonPath live_arsenal_system.py
