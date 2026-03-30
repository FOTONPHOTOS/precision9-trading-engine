# LAUNCH_LIVE_SYSTEM_EXECUTION.ps1
# Launch the Arsenal system in LIVE EXECUTION MODE
# Executes REAL trades on Bybit with REAL money

Write-Host ""
Write-Host "====================================================================================================" -ForegroundColor Red
Write-Host "   ARSENAL LIVE SYSTEM - LIVE EXECUTION MODE" -ForegroundColor Red
Write-Host "====================================================================================================" -ForegroundColor Red
Write-Host ""
Write-Host "WARNING: THIS WILL EXECUTE REAL TRADES ON BYBIT" -ForegroundColor Red -BackgroundColor Yellow
Write-Host ""
Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  - Symbol: SOLUSDT" -ForegroundColor White
Write-Host "  - Position Size: $100 with 10x leverage (from .env)" -ForegroundColor White
Write-Host "  - Max Daily Drawdown: $20" -ForegroundColor White
Write-Host "  - Min Risk/Reward: 1.2:1" -ForegroundColor White
Write-Host "  - Analysis Interval: 60 seconds" -ForegroundColor White
Write-Host ""
Write-Host "Features:" -ForegroundColor Yellow
Write-Host "  - Complete 11-module arsenal analysis" -ForegroundColor White
Write-Host "  - Intelligent decision making with chain-of-thought reasoning" -ForegroundColor White
Write-Host "  - Precision TP/SL calculation using smart money concepts" -ForegroundColor White
Write-Host "  - 3-tier take profit system (40%, 30%, 30%)" -ForegroundColor White
Write-Host "  - Active position monitoring and risk management" -ForegroundColor White
Write-Host "  - Automatic stop loss to breakeven after TP1" -ForegroundColor White
Write-Host ""
Write-Host "Safety Checks:" -ForegroundColor Yellow
Write-Host "  - Range trap detection (prevents bad entries)" -ForegroundColor Green
Write-Host "  - Stop hunt mode detection (avoids market manipulation)" -ForegroundColor Green
Write-Host "  - Daily drawdown protection (max -$20)" -ForegroundColor Green
Write-Host "  - RRR validation (minimum 1.2:1)" -ForegroundColor Green
Write-Host "  - Position status check (no duplicate positions)" -ForegroundColor Green
Write-Host ""
Write-Host "====================================================================================================" -ForegroundColor Red
Write-Host ""
Write-Host "The system will give you 5 seconds to cancel after starting..." -ForegroundColor Yellow
Write-Host ""

# Prompt for confirmation
$confirmation = Read-Host "Type 'CONFIRM' to proceed with live execution"

if ($confirmation -ne 'CONFIRM') {
    Write-Host ""
    Write-Host "[CANCELLED] Live execution not confirmed. Exiting..." -ForegroundColor Yellow
    Write-Host ""
    exit
}

Write-Host ""
Write-Host "[CONFIRMED] Launching live execution system..." -ForegroundColor Green
Write-Host ""

# Change to the correct directory
Set-Location "G:\python files\precision9\Simulation Environment\Trendline_Detectory"

# Use the correct Python interpreter from venv
$pythonPath = "G:\python files\precision9\myenv_fixed\Scripts\python.exe"

# Run the live system in LIVE EXECUTION mode
& $pythonPath live_arsenal_system.py --live
