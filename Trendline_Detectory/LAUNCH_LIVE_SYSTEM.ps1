# LAUNCH LIVE ARSENAL SYSTEM
# Continuous market monitoring with full trade execution logic (monitoring mode)

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "   ____  ____  _________________ ____  _   __    ___    ___   ____ ______  _____   ___    __ " -ForegroundColor Cyan
Write-Host "  / __ \/ __ \/ ____/ ____/  _// ___// | / /   /   |  / _ \ / __// ____/ / ___/  /   |  / / " -ForegroundColor Cyan
Write-Host " / /_/ / /_/ / __/ / /    / /  \__ \/  |/ /   / /| | / , _/_\ \ / __/   / (_ /  / /| | / /__" -ForegroundColor Cyan
Write-Host "/ ____/ _, _/ /___/ /___ _/ /  ___/ / /|  /   / ___ |/ /| /___/ / /___  \___/  / ___ |/ /___/" -ForegroundColor Cyan
Write-Host "/_/   /_/ |_/_____/\____//___//____/_/ |_/   /_/  |_/_/ |_|____//_____/       /_/  |_/_____/" -ForegroundColor Cyan
Write-Host ""
Write-Host "LIVE ARSENAL SYSTEM - MONITORING MODE" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This mode analyzes the market WITHOUT executing real trades." -ForegroundColor Yellow
Write-Host "To enable LIVE TRADING on Bybit, use: .\LAUNCH_LIVE_SYSTEM_EXECUTION.ps1" -ForegroundColor Red
Write-Host ""
Write-Host "What it does:" -ForegroundColor Green
Write-Host "  ✓ Continuously fetches live market data from Binance" -ForegroundColor White
Write-Host "  ✓ Runs complete 11-module arsenal analysis every 60 seconds" -ForegroundColor White
Write-Host "  ✓ Identifies high-quality trade setups with 2:1+ RR" -ForegroundColor White
Write-Host "  ✓ Creates complete battle plan with all scenarios" -ForegroundColor White
Write-Host "  ✓ Monitors active trades in real-time" -ForegroundColor White
Write-Host "  ✓ Shows detailed reasoning for every decision" -ForegroundColor White
Write-Host ""
Write-Host "When Bybit integration is added, it will:" -ForegroundColor Yellow
Write-Host "  → Place limit orders at optimal entry zones" -ForegroundColor White
Write-Host "  → Adjust stops dynamically based on market structure" -ForegroundColor White
Write-Host "  → Execute partial TPs with market orders when needed" -ForegroundColor White
Write-Host "  → Exit immediately on invalidation" -ForegroundColor White
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Prompt user
Write-Host "Ready to launch LIVE ARSENAL SYSTEM?" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Symbol: SOLUSDT" -ForegroundColor White
Write-Host "  Timeframe: 5m" -ForegroundColor White
Write-Host "  Analysis Interval: 60 seconds" -ForegroundColor White
Write-Host "  Mode: MONITORING (shows what it would do)" -ForegroundColor White
Write-Host ""
Write-Host "Press any key to start, or Ctrl+C to cancel..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Green
Write-Host "LAUNCHING LIVE SYSTEM" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Green
Write-Host ""

# Change to the correct directory
Set-Location "G:\python files\precision9\Simulation Environment\Trendline_Detectory"

# Use the correct Python interpreter from venv
$pythonPath = "G:\python files\precision9\myenv_fixed\Scripts\python.exe"

Write-Host "Python: $pythonPath" -ForegroundColor Gray
Write-Host "Working Directory: $(Get-Location)" -ForegroundColor Gray
Write-Host ""
Write-Host "Starting continuous monitoring... (Press Ctrl+C to stop)" -ForegroundColor Yellow
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Run the live system
& $pythonPath live_arsenal_system.py
